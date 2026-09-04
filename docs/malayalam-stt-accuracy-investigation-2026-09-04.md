# Malayalam Speech-to-Text Accuracy — Investigation

**Date:** 2026-09-04
**Type:** Investigation only. No code was changed to produce this document.

## Incident

Same production session as the silent-empty-reply bug (see `.agents/REPORT.md`
for that fix). The patient said, in romanised Malayalam with an English
loanword:

> "enthokke doctors aan ullath" — "which doctors are available?"

The system transcribed:

> "പിന്നെ എന്തായിരിക്കും doctors ഉണ്ടാവുന്നത്?"

which is a different sentence, not a minor misspelling of the same one. The
input code-switches Malayalam with the English word "doctors" — normal for
this user base, not an edge case to special-case away.

## B1 — Where the microphone button and speech capture live

- **`frontend/src/hooks/useHospitalChat.tsx`** (lines 152–238) is where the
  actual capture happens: it configures `@ricky0123/vad-react`'s
  `useMicVAD` for voice-activity detection, and its `onSpeechEnd` handler
  (line 180) is what turns the captured audio into a WAV blob and uploads it.
  This hook is shared by every hospital theme (`iris-hospitals`,
  `bkm-hospital-payannur`, `arogya-specialty`) via
  `frontend/src/components/common/ChatCore.tsx` → `useChatCore()`, so a fix
  here is generic across tenants, not theme-specific.
- Each theme's own `Chat.tsx` (e.g.
  `frontend/src/themes/iris-hospitals/Chat.tsx`, lines ~134–143 and
  ~233–309) renders the mic button itself (`Mic`/`MicOff` icon,
  `toggleMic()` handler) and the recording/transcribing UI states. It holds
  no capture logic of its own — it only calls `toggleMic()` from the shared
  hook via `useChatCore()`.

## B2 — Which engine performs the transcription

**Server-side, third-party API — Sarvam AI's speech-to-text endpoint.** Not
the browser's Web Speech API; `SpeechRecognition` /
`webkitSpeechRecognition` do not appear anywhere in the frontend. The audio
is recorded client-side, uploaded as a WAV file to this project's own
`/transcribe` endpoint, which forwards it to Sarvam:

```python
# backend/app/api/v1/endpoints/ai.py, lines 1089–1100
with open(temp_filename, "rb") as audio_file:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": settings.SARVAM_API_KEY},
            data={
                "model": model,
                "language_code": lang_code,
                "mode": mode,
            },
            files={"file": ("recording.wav", audio_file, "audio/wav")},
        )
```

Model selection (lines 1080–1087):

```python
if language == "ml":
    model = "saaras:v3"
    lang_code = "ml-IN"
    mode = "codemix"
else:
    model = "saarika:v2.5"
    lang_code = "en-IN"
    mode = "transcribe"
```

`saaras:v3` in `codemix` mode is Sarvam's code-switching-aware model — it is
already the model chosen for this exact scenario (Malayalam mixed with
English words), so the mis-transcription in this incident is a model-level
accuracy miss, not a wrong-mode configuration bug.

This is the same Sarvam AI account already used for text translation
(`backend/app/services/translation.py`, `SARVAM_API_KEY` in
`backend/app/core/config.py`) — one vendor relationship, two different
Sarvam products.

## B3 — Language tag: hardcoded or derived?

**Derived from the UI's own language toggle, not hardcoded per hospital.**
The frontend sends whatever `language` the patient currently has selected
(`'en'` or `'ml'`, defaulting to `'ml'`) as a form field:

```javascript
// frontend/src/hooks/useHospitalChat.tsx, line 192
formData.append('language', languageRef.current);
```

The backend only maps that two-value `language` field to Sarvam's
`lang_code`/`model`/`mode` triple (`ai.py` lines 1080–1087, quoted above).
There is no `hospital_id`-conditional branch anywhere in `/transcribe` that
would special-case one tenant's language handling — **no violation of the
no-hardcoded-clinic-behaviour rule found.**

One separate observation, not a violation but worth flagging: `/transcribe`
accepts a `hospital_id: int = Form(0)` parameter (line 1065) that is never
read anywhere in the function body. It's a dead parameter — harmless, but
worth a cleanup note for whoever next touches this endpoint.

## B4 — Raw transcript, or is there a correction step?

**Sent straight through, no correction or normalisation step of any kind.**
On the frontend, the only processing applied to Sarvam's response is
`.trim()`:

```javascript
// frontend/src/hooks/useHospitalChat.tsx, lines 200–205
const data = await res.json();
setMicState('idle');
if (data.transcript?.trim() && handleSendRef.current) {
  handleSendRef.current(data.transcript.trim());
}
```

`handleSendRef.current(...)` is `handleSend`, the same function a typed
message goes through — it is sent to `/chat-stream` as `question` verbatim.
On the backend, if the language is Malayalam, the only thing that happens to
it before it reaches the model is machine translation to English for intent
classification and context-building (`ai.py` line 423,
`_translate_async(request.question, "ml", "en")`) — a *translation* step,
not a transcription-*correction* step. There is nothing anywhere in the
pipeline that would catch "this transcript is probably wrong" and recover
the original words; a wrong transcription just becomes a wrong (but
grammatically fine) Malayalam sentence that gets translated and answered
as if the patient had actually said it.

## B5 — Existing server-side transcription code, used or unused?

Only one implementation exists in the repo: the `/transcribe` endpoint
covered in B2 above (`ai.py` lines 1061–1117), and it **is** in active use —
it's exactly what `useHospitalChat.tsx`'s mic flow calls. A repo-wide search
for other speech-to-text integrations (`whisper`, `speech_to_text`,
`speech-to-text`, `stt`, `sarvam`, `saaras`, `saarika`, case-insensitive)
under `backend/app/` turned up no other implementation — nothing unused to
report.

## B6 — Possible fixes

**Option 1 — Post-transcript normalisation/correction layer.** Add a small
lookup or fuzzy-match pass over the transcript before it reaches intent
classification, correcting known code-switched loanwords and common
hospital vocabulary (similar in spirit to the existing
`services/ml_postprocess.py` normaliser, but for STT output instead of
translation output).
- *Accuracy:* Only helps the subset of errors that are "right words,
  wrong spelling/script." This incident's transcript
  (`"പിന്നെ എന്തായിരിക്കും doctors ഉണ്ടാവുന്നത്?"`) is not that — the model
  heard a different sentence, not a misspelling of the right one — so this
  specific failure would **not** be caught by this approach.
- *Cost:* Cheap; a rule table, no new API calls.
- *Latency:* Negligible (regex/dictionary lookup).
- *Offline behaviour:* Unaffected either way — capture and STT already
  require network for the Sarvam call.

**Option 2 — Tune or upgrade the Sarvam STT configuration.** Investigate
whether Sarvam's API supports vocabulary hints, domain boosting, or a newer
model/mode combination better suited to Malayalam–English code-switching in
a hospital-reception context.
- *Accuracy:* Potentially the most direct fix, if Sarvam exposes this —
  unverified in this investigation; would need their current API
  documentation, which this investigation did not have reason to fetch.
- *Cost:* Unknown — depends on whether it's a config change or a plan/tier
  change on the Sarvam account.
- *Latency:* Likely unchanged.
- *Offline behaviour:* Unaffected.
- *Risk:* Could be a dead end if Sarvam doesn't expose this for
  `saaras:v3`.

**Option 3 — Show the transcript for confirmation before sending it.**
Instead of auto-sending the transcript the moment Sarvam returns it
(`useHospitalChat.tsx` line 203–205), populate the text input with it and
let the patient see, edit, and confirm it before it's sent — the same
`inputText` state the typed-message path already uses.
- *Accuracy:* Directly closes this incident's exact failure mode and every
  other kind of STT error, because the patient — who knows what they
  actually said — gets the last word, rather than the correction being
  automated and therefore only as good as whatever pattern was anticipated.
- *Cost:* Frontend-only change; no new API calls, no vendor dependency.
- *Latency:* No added latency to the transcription call itself; adds one
  interaction step (the patient reviews/taps send) before the message goes
  out — a real UX cost against the "hands-free voice" value the mic feature
  is presumably there for.
- *Offline behaviour:* Unaffected.

**Recommendation: Option 3.** It's the only one of the three that actually
recovers a completely mis-heard sentence rather than only correcting known
error patterns, costs nothing to build against a new vendor dependency, and
degrades to exactly today's typed-message flow if a patient doesn't want to
edit anything (they can just tap send). Option 1 is worth doing later as a
cheap supplementary layer for the narrower class of errors it can actually
catch, but it would not have prevented this specific incident. Option 2 is
worth a quick check against Sarvam's current docs since it could compound
with either of the others, but nothing in this investigation confirms it's
available. Not implemented here — investigation only, per this task's scope.
