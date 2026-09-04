import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useMicVAD, utils } from "@ricky0123/vad-react";

interface Message {
  role: 'user' | 'assistant';
  content: string;
  isWelcome?: boolean;
  isStreaming?: boolean;
}

type MicState = 'idle' | 'recording' | 'transcribing';

const FALLBACK_SUGGESTIONS = {
  en: ["What can you help me with?", "Which doctors are available?", "How do I contact the hospital?", "Tell me about this hospital"],
  ml: ["നിങ്ങൾക്ക് എന്നെ എങ്ങനെ സഹായിക്കാനാകും?", "ഏത് ഡോക്ടർമാരുണ്ട്?", "ആശുപത്രിയുമായി എങ്ങനെ ബന്ധപ്പെടാം?", "ഈ ആശുപത്രിയെക്കുറിച്ച് പറയൂ"],
};

// Shown instead of a blank assistant bubble when the chat-stream connection
// closes having produced no content (backend crash, network drop) or emits
// the [STREAM_ERROR] sentinel. No dedicated i18n mechanism exists in this
// project (see .agents/REPORT.md) — this project's convention is a hardcoded
// per-language literal at the point of use, same as the other strings in this
// file. The `ml` value is intentionally left empty pending developer-approved
// Malayalam wording; until then the English string is shown for both
// languages so the user is never shown nothing.
const STREAM_FALLBACK_MESSAGE = {
  en: "Sorry, something went wrong and I couldn't generate a response. Please try again.",
  ml: "",
};

function getBaseURL(): string {
  return (import.meta as any).env?.VITE_API_URL
    || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://localhost:8000/api/v1'
      : 'https://hospital-ai-platform.onrender.com/api/v1');
}

export function useHospitalChat(hospitalId: string) {
  const [language, setLanguage] = useState<'en' | 'ml'>('ml');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputText, setInputText] = useState('');
  const [micState, setMicState] = useState<MicState>('idle');
  const [micError, setMicError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<{ en: string[]; ml: string[] }>(FALLBACK_SUGGESTIONS);

  const sessionToken = useRef<string>(
    sessionStorage.getItem('bookingSessionToken') || (() => {
      const t = crypto.randomUUID();
      sessionStorage.setItem('bookingSessionToken', t);
      return t;
    })()
  );
  
  const welcomeCache = useRef<{ en: string; ml: string } | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const handleSendRef = useRef<((text: string) => Promise<void>) | null>(null);
  const micActiveRef = useRef(false);
  const languageRef = useRef(language);
  useEffect(() => { languageRef.current = language; }, [language]);

  // --- 1. Fetch Welcome & Suggestions ---
  useEffect(() => {
    if (!hospitalId) return;
    const token = localStorage.getItem('token');
    
    setMessages([{ role: 'assistant', content: language === 'ml' ? "വിവരങ്ങൾ ലോഡ് ചെയ്യുന്നു..." : "Loading info...", isWelcome: true }]);

    fetch(`${getBaseURL()}/ai/welcome/${hospitalId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.en && data?.ml) {
          welcomeCache.current = { en: data.en, ml: data.ml };
          setMessages([{ role: 'assistant', content: data[language], isWelcome: true }]);
        }
      }).catch(() => {});

    fetch(`${getBaseURL()}/ai/suggestions/${hospitalId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.en && data?.ml) setSuggestions(data); })
      .catch(() => {});
  }, [hospitalId]);

  useEffect(() => {
    setMessages(prev => {
      if (!prev.length || !prev[0].isWelcome || !welcomeCache.current) return prev;
      return [{ ...prev[0], content: welcomeCache.current[language] }, ...prev.slice(1)];
    });
  }, [language]);

  // --- 2. The Text Chat Logic ---
  const handleSend = useCallback(async (text?: string) => {
    const msg = (typeof text === 'string' ? text : inputText).trim();
    if (!msg || isStreaming) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setInputText('');
    setMicError(null);

    const historySnapshot = messages.filter(m => !m.isWelcome && !m.isStreaming).map(m => ({ role: m.role, content: m.content }));
    setMessages(prev => [...prev, { role: 'user', content: msg }, { role: 'assistant', content: '', isStreaming: true }]);
    setIsStreaming(true);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${getBaseURL()}/ai/chat-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          question: msg,
          hospital_id: parseInt(hospitalId),
          language,
          history: historySnapshot,
          session_token: sessionToken.current,
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamErrored = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';
        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue;
          const payload = frame.slice(6);
          if (payload === '[DONE]') {
            setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, isStreaming: false } : m));
            break;
          }
          if (payload === '[STREAM_ERROR]') {
            streamErrored = true;
            continue;
          }
          try {
            const t = JSON.parse(payload);
            setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, content: m.content + t } : m));
          } catch { /* skip */ }
        }
      }

      // Never leave the assistant bubble blank: the backend sent [STREAM_ERROR],
      // or the connection closed (cleanly or not) without a single content
      // frame ever arriving.
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (!last || last.role !== 'assistant') return prev;
        if (!streamErrored && last.content.trim()) return prev;
        const fallback = STREAM_FALLBACK_MESSAGE[language] || STREAM_FALLBACK_MESSAGE.en;
        return prev.map((m, i) => i === prev.length - 1
          ? { ...m, content: fallback, isStreaming: false }
          : m);
      });
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setMessages(prev => prev.map((m, i) => i === prev.length - 1
        ? { ...m, content: language === 'ml' ? 'കണക്ഷൻ പ്രശ്‌നം. വീണ്ടും ശ്രമിക്കൂ.' : 'Connection error.', isStreaming: false }
        : m));
    } finally {
      setIsStreaming(false);
    }
  }, [messages, inputText, isStreaming, hospitalId, language]);

  useEffect(() => { handleSendRef.current = handleSend; }, [handleSend]);

  // --- 3. Improved VAD Mic Logic ---
  // Key improvements:
  //   • preSpeechPadFrames: 15 — captures ~250ms before VAD triggers, so the
  //     first syllable of a sentence is never clipped.
  //   • positiveSpeechThreshold lowered to 0.50 — fires sooner on quiet phones.
  //   • negativeSpeechThreshold lowered to 0.30 — less likely to cut off mid-word.
  //   • minSpeechFrames: 4 — ignores very short noise bursts while still being
  //     responsive; at 16kHz / 512-sample frames that's ~128ms.
  //   • redemptionFrames set explicitly to 12 (~384ms) — gives a comfortable
  //     natural pause before triggering onSpeechEnd.
  const vadOptions = useMemo(() => ({
    startOnLoad: false,
    baseAssetPath: "/vad-assets/",
    onnxWASMBasePath: "/vad-assets/",
    model: "legacy" as const,

    // --- Sensitivity tuning (fixes "doesn't hear first part") ---
    positiveSpeechThreshold: 0.50,   // was 0.60 — detects speech sooner
    negativeSpeechThreshold: 0.30,   // was 0.35 — less eager to cut off
    minSpeechFrames: 4,              // ~128ms at 16kHz / 512 frames
    preSpeechPadFrames: 15,          // ~480ms pre-roll captured before trigger

    // --- End-of-speech timing ---
    redemptionFrames: 12,            // ~384ms silence before onSpeechEnd fires

    onSpeechStart: () => {
      if (micActiveRef.current) setMicState('recording');
    },
    onSpeechEnd: async (audio: Float32Array) => {
      if (!micActiveRef.current) return;

      micActiveRef.current = false;  // lock immediately
      vadPause();                    // stop VAD right away
      setMicState('transcribing');

      try {
        const wavBuffer = utils.encodeWAV(audio);
        const audioBlob = new Blob([wavBuffer], { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.wav');
        formData.append('language', languageRef.current);
        formData.append('hospital_id', String(parseInt(hospitalId) || 0));
        const token = localStorage.getItem('token');
        const res = await fetch(`${getBaseURL()}/ai/transcribe`, {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData
        });
        if (!res.ok) throw new Error("Transcription failed");
        const data = await res.json();
        setMicState('idle');
        if (data.transcript?.trim() && handleSendRef.current) {
          handleSendRef.current(data.transcript.trim());
        }
      } catch {
        setMicError(languageRef.current === 'ml' ? 'ശബ്ദം മനസ്സിലാക്കാൻ കഴിഞ്ഞില്ല.' : 'Failed to transcribe audio.');
        setMicState('idle');
      }
    },
    onVADMisfire: () => {
      if (!micActiveRef.current) return;
      setMicState('idle');
    }
  }), []); // stable — language & handlers accessed via refs

  const { loading: vadLoading, errored: vadErrored, start: vadStart, pause: vadPause } = useMicVAD(vadOptions);

  const toggleMic = useCallback(() => {
    setMicError(null);
    if (micState === 'recording' || micState === 'transcribing') {
      micActiveRef.current = false;
      vadPause();
      setMicState('idle');
    } else {
      if (vadLoading) {
        setMicError(language === 'en' ? 'Voice AI is still loading...' : 'ശബ്ദ AI ലോഡുചെയ്യുന്നു...');
        return;
      }
      if (vadErrored) {
        setMicError(language === 'en' ? 'Microphone access failed. Please allow microphone permission and try again.' : 'മൈക്ക് ആക്സസ് ലഭ്യമായില്ല. അനുമതി നൽകി വീണ്ടും ശ്രമിക്കൂ.');
        return;
      }
      micActiveRef.current = true;
      vadStart();
      setMicState('recording');
    }
  }, [micState, vadLoading, vadErrored, language, vadStart, vadPause]);

  return {
    language, setLanguage, messages, isStreaming,
    inputText, setInputText, micState, micError,
    suggestions, handleSend, toggleMic,
    vadLoading
  };
}