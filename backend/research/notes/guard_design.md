# Grounding Guard: Architecture & Verification Design

## 0. Purpose and Honest Limit

The grounding guard is a separate, post-generation fact-checking program designed to work downstream of any AI language model and any Retrieval-Augmented Generation (RAG) architecture. Its sole function is to evaluate a candidate response against the retrieved source context provided to the model.

**Honest limits and operational boundaries:**
- The guard reduces and catches errors by a measured amount; we never claim it removes all of them.
- The guard only checks an answer against the specific context it was given. It cannot determine whether the retrieved context itself is factually accurate, current, or complete. If the source database contains stale or erroneous clinic data, the guard will treat that data as ground truth.
- The guard is not a medical advisor, diagnostic tool, or autonomous decision-maker; it operates strictly as an automated consistency and boundary verification filter.

---

## 1. The Interface

The guard exposes the following Python interface (copied unchanged):

```python
apply_guard(answer: str, context: list[str], instructions: str, lang: str) -> GuardResult
GuardResult:
  final_answer : str    # the answer after the guard
  claims       : list   # each: text, verdict (supported / unsupported / contradicted), evidence
  conflicts    : list   # data-vs-instruction or data-vs-answer clashes found
  fact_lock    : list   # numbers/times/names checked, and whether each survived
  changed      : bool   # did the guard alter the answer?
```

*Operational note on inputs:* What exactly the runner passes in `context` (one string per passage?) and `instructions` (admin free text only, or the whole prompt?) is [LEAD TO DECIDE: confirm with Track 1, task M-08].

---

## 2. Part 1, Claim Check

### a. Splitting
- PROPOSED: The candidate answer is first split into sentences using standard punctuation boundaries (`.`, `?`, `!`, and newline delimiters).
- Sentences containing multiple assertions are further split into discrete factual clauses when coordinated by conjunctions (e.g., "and", "but", "while") or semicolons. For instance, the compound sentence *"Dr. Test One is available Monday 9-1 and the fee is 500"* is decomposed into two factual claims:
  1. *"Dr. Test One is available Monday 9-1"*
  2. *"the fee is 500"*
- Non-factual sentences that do not express verifiable clinic facts (such as conversational greetings like *"Hello"*, *"Good morning"*, or polite closing remarks like *"I hope this helps"*) are identified via a PROPOSED rule-based filter and skipped.

### b. Checking
- For each extracted claim, the guard performs pairwise entailment comparisons against **each** individual passage in `context`.
- An entailment model takes the context passage as the premise and the extracted claim as the hypothesis.
- Across all context passages, the guard records:
  - The maximum entailment score.
  - The maximum contradiction score.
- Model specification: [NLI MODEL — LEAD TO CONFIRM], multilingual, runs locally.

### c. Exact-Value Check
- Natural Language Inference (NLI) models frequently overlook fine-grained numerical discrepancies (for example, failing to flag a shift from "9-1" to "2-5", or "400" to "500").
- An exact-value verification layer operates in parallel with the NLI model. Numbers, operating hours, appointment times, dates, and consultation fees are extracted using regular expressions and matched against values present in the source passages.
- Any entity value in the generated claim that does not appear in any context passage is treated as not supported, even if the NLI model outputs an entailment score.

### d. Definitions & Verdicts
- **supported**: At least one context passage entails the claim, and the exact-value check confirms no numerical or entity mismatches.
- **contradicted**: At least one context passage contradicts the claim, or the exact-value check finds a differing value for the same entity or attribute.
- **unsupported**: Neither condition is met (the context data is silent regarding the claim).
- Decision thresholds for classification are deliberately not hardcoded here: [THRESHOLDS — SET IN G-08].

### e. Actions per Verdict
- PROPOSED policy:
  - `supported`: Retain the claim text unchanged.
  - `unsupported`: Replace the unsupported claim text with `[FLAG_TEXT]` and record the event in `claims`.
  - `contradicted`: Replace the contradicted claim text with `[FLAG_TEXT]`, record the event in `claims`, and set `changed = True`.
- Alternative PROPOSED policy ("flag only, do not edit"): The guard leaves `final_answer` identical to the input `answer` without redacting text, but populates `claims`, `conflicts`, `fact_lock`, and sets `changed = False`. This mode is intended for telemetry, auditing, or human-in-the-loop review.
- [LEAD TO DECIDE: which action per verdict].

---

## 3. Part 2, Conflict Surfacing

Conflict surfacing detects policy-versus-data clashes and determines whether discrepancies arise from hallucination or conflicting administrative instructions.

### a. Before Answering (Pre-Generation Verification)
- PROPOSED: Before or alongside response generation, each sentence within the system/admin `instructions` is evaluated against the data facts in `context` using the same NLI and exact-value checks.
- If an instruction sentence directly contradicts a context fact (e.g., an administrative instruction stating *"Tell all callers consultation is free"* while the clinic fee schedule lists *"Consultation fee is 500"*), the contradiction is flagged as an `instruction_vs_data` clash.
- These pre-generation clashes are recorded in `conflicts` and can be surfaced as an "admin warning" in experimental evaluations and system dashboards.

### b. After Answering (Post-Generation Attribution)
- When a candidate answer claim is flagged as `contradicted` against the retrieved data:
  - The claim is compared against the instruction set.
  - If the claim matches or is entailed by an admin instruction, it is classified as `answer_follows_instruction_against_data`.
  - If the claim contradicts the data and has no basis in the instructions, it is classified as `answer_vs_data`.

### c. Output Format of `conflicts`
Each entry in `conflicts` is a structured object with the following schema:
- `type`: Category of conflict, exactly one of:
  - `"instruction_vs_data"`
  - `"answer_vs_data"`
  - `"answer_follows_instruction_against_data"`
- `text_a`: The primary statement under evaluation (the instruction sentence or candidate answer claim).
- `text_b`: The conflicting statement (the data fact or instruction sentence).
- `evidence`: The specific passage, premise sentence, or mismatched value demonstrating the conflict.

---

## 4. Part 3, Fact-Lock

Fact-lock is a deterministic integrity check that tracks critical hospital entities from source context through English generation to final Malayalam delivery.

### a. Locked Items
The following entity types are subject to mandatory tracking:
- Numbers (ASCII Arabic digits `0-9` and Malayalam script numerals `൦-൯`).
- Times (e.g., "9 am", "09:00", "1:00 PM").
- Consultation fees and test prices (e.g., "500", "Rs 500", "₹500").
- Calendar dates (e.g., "12/10/2026", "October 12").
- Weekdays (e.g., "Monday", "തിങ്കളാഴ്ച").
- Doctor names (e.g., "Dr. Test One").
- Diagnostic test names (e.g., "Blood Glucose Test", "Lipid Profile").

### b. Extraction & Normalisation
- PROPOSED: Regular expressions and entity pattern matchers extract locked entities from three points:
  1. The source context passages.
  2. The generated English answer.
  3. The final Malayalam answer.
- Prior to comparison, values undergo normalisation:
  - Malayalam digits (`൦-൯`) are converted to standard ASCII digits (`0-9`).
  - Time representations are parsed into canonical 24-hour stamps or standard 12-hour AM/PM representations.
  - Weekday names across languages are mapped to canonical day indices (0 for Monday through 6 for Sunday).

### c. Reporting in `fact_lock`
Each tracked entity is recorded in the `fact_lock` list with one of three status markers:
- `survived`: The entity exists in the source context and appears unchanged and verified in the final response.
- `changed`: The entity value was altered during generation or translation (e.g., a fee shifted from 400 to 500, or a morning clinic hour shifted to afternoon).
- `lost`: The entity was present in the source context relevant to the user query but was omitted from the final answer.

### d. Script and Language Mapping Constraints
- The Malayalam mapping tables (script digits, weekday names, and relative time phrases) will be written in task G-10 and must be checked by a Malayalam reader. Do not invent them here.
- Cross-script phonetic transliteration of doctor names and medical terms (e.g., "Dr. Test One" vs "ഡോ. ടെസ്റ്റ് വൺ") is a known weak point of deterministic string matching and requires dedicated phoneme/n-gram tolerance rules defined in G-10.

---

## 5. Malayalam at Each Step

Evaluating Malayalam responses presents a choice between two primary pipeline architectures. Task G-08 will experimentally evaluate both; their trade-offs are detailed below without prejudging the outcome.

### Option A: Direct Multilingual Verification
Verify the Malayalam claim directly against Malayalam context using a multilingual NLI model.
- **Pros:**
  - Avoids an extra translation step, eliminating translation latency and translation error propagation.
  - Preserves exact source phrasing, dialectal nuances, and native honorifics.
- **Cons:**
  - Multilingual NLI models generally exhibit lower inference accuracy and higher variance on Indic languages compared to English.
  - Malayalam's agglutinative morphology compounds tokenization and semantic alignment challenges.

### Option B: Pivot Translation Verification
Translate candidate Malayalam claims into English first, then run checking and NLI against English context passages.
- **Pros:**
  - Enables the use of higher-capacity English NLI models.
  - Sentence boundary detection, clause parsing, and entity extraction are substantially more mature in English.
- **Cons:**
  - Pivot translation can introduce semantic shifts or invert polarity (for example, erroneously flipping "ലഭ്യമാണ്" [available] to "not available" or swapping AM/PM qualifiers).
  - Translating every extracted claim adds processing latency.

### Comparison Across Guard Components

| Guard Component | Option A (Direct Multilingual) | Option B (Pivot Translation) |
| :--- | :--- | :--- |
| **Splitting** | PROPOSED: Rule-based Malayalam sentence tokenizer; clause splitting is complicated by agglutinative suffixes. | Standard English clause splitting applied post-translation. |
| **Checking (NLI)** | Direct premise-hypothesis NLI on native Malayalam text. | English premise-hypothesis NLI on translated claims. |
| **Conflict Surfacing** | Detects instruction-vs-data clashes directly in native text. | Operates over English translations of instructions and data. |
| **Fact-Lock** | Requires extracting Malayalam script digits, weekday words, and transliterated names directly. | Extracts English tokens, but still requires cross-checking that the translation step did not distort numerals or times. |

### Pipeline Placement Decision
[LEAD TO DECIDE: guard on the English answer before translation back to Malayalam, or on the final Malayalam answer, or both].

---

## 6. Ten Worked Examples

*Note: All context passages, instructions, doctor names, and clinic data below are completely fictional. For NLI behaviour, qualitative assessments (high / low) are illustrative, not measured.*

### English Example 1: Changed Number (Fee Mismatch)
- **INPUT**:
  - `context`: `["Hospital A - Consultation fee for Dr. Test One (General Medicine) is 400 INR."]`
  - `instructions`: `"State the doctor's consultation fee."`
  - `answer`: `"The consultation fee for Dr. Test One is 600 INR."`
  - `lang`: `"en"`
- **Claim Split**:
  - Claim 1: `"The consultation fee for Dr. Test One is 600 INR."`
- **Claim Verdict**:
  - Claim 1: `contradicted` (Exact-value mismatch: context specifies 400, answer states 600; NLI contradiction: high, entailment: low; illustrative, not measured).
- **Conflict Check**:
  - None (`answer_vs_data` numerical clash).
- **Fact-Lock Result**:
  - Number `400`: `changed` to `600`.
- **GuardResult**:
  - `final_answer`: `"[FLAG_TEXT]"`
  - `claims`: `[{"text": "The consultation fee for Dr. Test One is 600 INR.", "verdict": "contradicted", "evidence": "Hospital A - Consultation fee for Dr. Test One (General Medicine) is 400 INR."}]`
  - `conflicts`: `[{"type": "answer_vs_data", "text_a": "The consultation fee for Dr. Test One is 600 INR.", "text_b": "Consultation fee for Dr. Test One (General Medicine) is 400 INR.", "evidence": "400 vs 600"}]`
  - `fact_lock`: `[{"item": "400", "type": "price", "status": "changed"}]`
  - `changed`: `True`

### English Example 2: Invented Detail (Hallucinated Service)
- **INPUT**:
  - `context`: `["Hospital A - ENT OPD is open Monday to Wednesday from 9:00 AM to 1:00 PM."]`
  - `instructions`: `"Answer clinic schedule questions."`
  - `answer`: `"ENT OPD is open Monday to Wednesday from 9:00 AM to 1:00 PM. Complimentary valet parking is provided at the main entrance."`
  - `lang`: `"en"`
- **Claim Split**:
  - Claim 1: `"ENT OPD is open Monday to Wednesday from 9:00 AM to 1:00 PM."`
  - Claim 2: `"Complimentary valet parking is provided at the main entrance."`
- **Claim Verdict**:
  - Claim 1: `supported` (NLI entailment: high, contradiction: low; exact values match; illustrative, not measured).
  - Claim 2: `unsupported` (Context is completely silent regarding parking; NLI entailment: low, contradiction: low; illustrative, not measured).
- **Conflict Check**:
  - None.
- **Fact-Lock Result**:
  - Time `"9:00 AM to 1:00 PM"`: `survived`.
  - Weekdays `"Monday to Wednesday"`: `survived`.
- **GuardResult**:
  - `final_answer`: `"ENT OPD is open Monday to Wednesday from 9:00 AM to 1:00 PM. [FLAG_TEXT]"`
  - `claims`: `[{"text": "ENT OPD is open Monday to Wednesday from 9:00 AM to 1:00 PM.", "verdict": "supported", "evidence": "Hospital A - ENT OPD is open Monday to Wednesday from 9:00 AM to 1:00 PM."}, {"text": "Complimentary valet parking is provided at the main entrance.", "verdict": "unsupported", "evidence": "None"}]`
  - `conflicts`: `[]`
  - `fact_lock`: `[{"item": "9:00 AM to 1:00 PM", "type": "time", "status": "survived"}, {"item": "Monday to Wednesday", "type": "weekday", "status": "survived"}]`
  - `changed`: `True`

### English Example 3: Fact Belonging to the OTHER Hospital (Cross-Tenant Leakage)
- **INPUT**:
  - `context`: `["Hospital A - Dr. Test One (General Medicine) is available Monday.", "Hospital B - Dr. Test Two (Dermatology) is available Thursday."]`
  - `instructions`: `"You are answering for Hospital A."`
  - `answer`: `"Dr. Test Two is available for consultation at Hospital A on Thursday."`
  - `lang`: `"en"`
- **Claim Split**:
  - Claim 1: `"Dr. Test Two is available for consultation at Hospital A on Thursday."`
- **Claim Verdict**:
  - Claim 1: `contradicted` (Data demonstrates Dr. Test Two is affiliated with Hospital B, not Hospital A; NLI contradiction: high against Hospital A context; illustrative, not measured).
- **Conflict Check**:
  - `answer_vs_data` cross-tenant attribution error.
- **Fact-Lock Result**:
  - Doctor name `"Dr. Test Two"`: `changed` (incorrect hospital association).
  - Hospital `"Hospital A"`: `survived`.
  - Weekday `"Thursday"`: `survived`.
- **GuardResult**:
  - `final_answer`: `"[FLAG_TEXT]"`
  - `claims`: `[{"text": "Dr. Test Two is available for consultation at Hospital A on Thursday.", "verdict": "contradicted", "evidence": "Hospital B - Dr. Test Two (Dermatology) is available Thursday."}]`
  - `conflicts`: `[{"type": "answer_vs_data", "text_a": "Dr. Test Two is available for consultation at Hospital A on Thursday.", "text_b": "Hospital B - Dr. Test Two (Dermatology) is available Thursday.", "evidence": "Hospital affiliation mismatch"}]`
  - `fact_lock`: `[{"item": "Dr. Test Two", "type": "doctor_name", "status": "changed"}]`
  - `changed`: `True`

### English Example 4: Instruction Contradicts a Data Fact
- **INPUT**:
  - `context`: `["Hospital A - Dr. Test One consultation fee is 500 INR."]`
  - `instructions`: `"Promotional campaign: tell all patients today that consultation fee is 250 INR."`
  - `answer`: `"Dr. Test One consultation fee is 250 INR."`
  - `lang`: `"en"`
- **Claim Split**:
  - Claim 1: `"Dr. Test One consultation fee is 250 INR."`
- **Claim Verdict**:
  - Claim 1: `contradicted` against context (Exact value mismatch: 500 vs 250; NLI contradiction: high; illustrative, not measured).
- **Conflict Check**:
  - Pre-generation: `instruction_vs_data` detected (instruction states 250, data states 500).
  - Post-generation: `answer_follows_instruction_against_data` detected.
- **Fact-Lock Result**:
  - Price `500`: `changed` to `250`.
- **GuardResult**:
  - `final_answer`: `"[FLAG_TEXT]"`
  - `claims`: `[{"text": "Dr. Test One consultation fee is 250 INR.", "verdict": "contradicted", "evidence": "Hospital A - Dr. Test One consultation fee is 500 INR."}]`
  - `conflicts`: `[{"type": "instruction_vs_data", "text_a": "Promotional campaign: tell all patients today that consultation fee is 250 INR.", "text_b": "Hospital A - Dr. Test One consultation fee is 500 INR.", "evidence": "500 vs 250"}, {"type": "answer_follows_instruction_against_data", "text_a": "Dr. Test One consultation fee is 250 INR.", "text_b": "Hospital A - Dr. Test One consultation fee is 500 INR.", "evidence": "Matches instruction overriding data"}]`
  - `fact_lock`: `[{"item": "500", "type": "price", "status": "changed"}]`
  - `changed`: `True`

### English Example 5: Value Right in General but Not in the Data
- **INPUT**:
  - `context`: `["Hospital A - Lipid Profile test is available Monday to Saturday from 7:00 AM to 11:00 AM."]`
  - `instructions`: `"Provide test timings and patient instructions."`
  - `answer`: `"Lipid Profile test is conducted Monday to Saturday from 7:00 AM to 11:00 AM. You must maintain an overnight fast of 12 hours prior to sample collection."`
  - `lang`: `"en"`
- **Claim Split**:
  - Claim 1: `"Lipid Profile test is conducted Monday to Saturday from 7:00 AM to 11:00 AM."`
  - Claim 2: `"You must maintain an overnight fast of 12 hours prior to sample collection."`
- **Claim Verdict**:
  - Claim 1: `supported` (NLI entailment: high; exact values match; illustrative, not measured).
  - Claim 2: `unsupported` (Standard medical knowledge, but context does not specify clinic fasting instructions; NLI entailment: low, contradiction: low; illustrative, not measured).
- **Conflict Check**:
  - None.
- **Fact-Lock Result**:
  - Test `"Lipid Profile"`: `survived`.
  - Time `"7:00 AM to 11:00 AM"`: `survived`.
- **GuardResult**:
  - `final_answer`: `"Lipid Profile test is conducted Monday to Saturday from 7:00 AM to 11:00 AM. [FLAG_TEXT]"`
  - `claims`: `[{"text": "Lipid Profile test is conducted Monday to Saturday from 7:00 AM to 11:00 AM.", "verdict": "supported", "evidence": "Hospital A - Lipid Profile test is available Monday to Saturday from 7:00 AM to 11:00 AM."}, {"text": "You must maintain an overnight fast of 12 hours prior to sample collection.", "verdict": "unsupported", "evidence": "None"}]`
  - `conflicts`: `[]`
  - `fact_lock`: `[{"item": "Lipid Profile", "type": "test_name", "status": "survived"}, {"item": "7:00 AM to 11:00 AM", "type": "time", "status": "survived"}]`
  - `changed`: `True`

---

[MALAYALAM — NOT YET VERIFIED BY A NATIVE READER]
### Malayalam Example 6: Time Changed by Translation
- **INPUT**:
  - `context`: `["Hospital A - Dr. Test One (General Medicine) is available Monday from 9:00 AM to 1:00 PM."]`
  - `instructions`: `"Doctor schedule query."`
  - `answer`: `"ഡോ. ടെസ്റ്റ് വൺ തിങ്കളാഴ്ച ഉച്ചയ്ക്ക് 2:00 മുതൽ വൈകുന്നേരം 5:00 വരെ ലഭ്യമാണ്."`
  - `lang`: `"ml"`
- **Claim Split**:
  - Claim 1: `"ഡോ. ടെസ്റ്റ് വൺ തിങ്കളാഴ്ച ഉച്ചയ്ക്ക് 2:00 മുതൽ വൈകുന്നേരം 5:00 വരെ ലഭ്യമാണ്."`
- **Claim Verdict**:
  - Claim 1: `contradicted` (Exact time mismatch: context specifies 9:00 AM - 1:00 PM, translated answer states 2:00 PM - 5:00 PM; NLI contradiction: high, entailment: low; illustrative, not measured).
- **Conflict Check**:
  - `answer_vs_data` time distortion clash.
- **Fact-Lock Result**:
  - Time `"9:00 AM to 1:00 PM"`: `changed` to `"2:00 PM to 5:00 PM"`.
  - Doctor name `"Dr. Test One"`: `survived` (`ഡോ. ടെസ്റ്റ് വൺ`).
- **GuardResult**:
  - `final_answer`: `"[FLAG_TEXT]"`
  - `claims`: `[{"text": "ഡോ. ടെസ്റ്റ് വൺ തിങ്കളാഴ്ച ഉച്ചയ്ക്ക് 2:00 മുതൽ വൈകുന്നേരം 5:00 വരെ ലഭ്യമാണ്.", "verdict": "contradicted", "evidence": "Hospital A - Dr. Test One (General Medicine) is available Monday from 9:00 AM to 1:00 PM."}]`
  - `conflicts`: `[{"type": "answer_vs_data", "text_a": "ഡോ. ടെസ്റ്റ് വൺ തിങ്കളാഴ്ച ഉച്ചയ്ക്ക് 2:00 മുതൽ വൈകുന്നേരം 5:00 വരെ ലഭ്യമാണ്.", "text_b": "9:00 AM to 1:00 PM", "evidence": "Time flipped during translation"}]`
  - `fact_lock`: `[{"item": "9:00 AM to 1:00 PM", "type": "time", "status": "changed"}]`
  - `changed`: `True`

---

[MALAYALAM — NOT YET VERIFIED BY A NATIVE READER]
### Malayalam Example 7: Changed Number (Fee Mismatch in Malayalam)
- **INPUT**:
  - `context`: `["Hospital A - Routine Hemogram test fee is 400 INR."]`
  - `instructions`: `"State lab test fee."`
  - `answer`: `"ഹോസ്പിറ്റൽ എയിൽ റൂട്ടീൻ ഹീമോഗ്രാം പരിശോധനയ്ക്ക് 800 രൂപയാണ് ഫീസ്."`
  - `lang`: `"ml"`
- **Claim Split**:
  - Claim 1: `"ഹോസ്പിറ്റൽ എയിൽ റൂട്ടീൻ ഹീമോഗ്രാം പരിശോധനയ്ക്ക് 800 രൂപയാണ് ഫീസ്."`
- **Claim Verdict**:
  - Claim 1: `contradicted` (Exact-value mismatch: context specifies 400, answer states 800; NLI contradiction: high, entailment: low; illustrative, not measured).
- **Conflict Check**:
  - `answer_vs_data` fee mismatch.
- **Fact-Lock Result**:
  - Number `400`: `changed` to `800`.
  - Test name `"Routine Hemogram"`: `survived` (`റൂട്ടീൻ ഹീമോഗ്രാം`).
- **GuardResult**:
  - `final_answer`: `"[FLAG_TEXT]"`
  - `claims`: `[{"text": "ഹോസ്പിറ്റൽ എയിൽ റൂട്ടീൻ ഹീമോഗ്രാം പരിശോധനയ്ക്ക് 800 രൂപയാണ് ഫീസ്.", "verdict": "contradicted", "evidence": "Hospital A - Routine Hemogram test fee is 400 INR."}]`
  - `conflicts`: `[{"type": "answer_vs_data", "text_a": "ഹോസ്പിറ്റൽ എയിൽ റൂട്ടീൻ ഹീമോഗ്രാം പരിശോധനയ്ക്ക് 800 രൂപയാണ് ഫീസ്.", "text_b": "Routine Hemogram test fee is 400 INR.", "evidence": "400 vs 800"}]`
  - `fact_lock`: `[{"item": "400", "type": "price", "status": "changed"}]`
  - `changed`: `True`

---

[MALAYALAM — NOT YET VERIFIED BY A NATIVE READER]
### Malayalam Example 8: Invented Detail (Hallucinated Free Transport)
- **INPUT**:
  - `context`: `["Hospital A - Cardiology OPD operates Tuesday and Thursday from 10:00 AM to 2:00 PM."]`
  - `instructions`: `"Inform the patient about cardiology services."`
  - `answer`: `"ഹോസ്പിറ്റൽ എയിൽ കാർഡിയോളജി ഒപി ചൊവ്വ, വ്യാഴം ദിവസങ്ങളിൽ രാവിലെ 10:00 മുതൽ ഉച്ചയ്ക്ക് 2:00 വരെ പ്രവർത്തിക്കുന്നു. കൂടാതെ രോഗികൾക്ക് സൗജന്യ ആംബുലൻസ് സർവീസ് ലഭ്യമാണ്."`
  - `lang`: `"ml"`
- **Claim Split**:
  - Claim 1: `"ഹോസ്പിറ്റൽ എയിൽ കാർഡിയോളജി ഒപി ചൊവ്വ, വ്യാഴം ദിവസങ്ങളിൽ രാവിലെ 10:00 മുതൽ ഉച്ചയ്ക്ക് 2:00 വരെ പ്രവർത്തിക്കുന്നു."`
  - Claim 2: `"കൂടാതെ രോഗികൾക്ക് സൗജന്യ ആംബുലൻസ് സർവീസ് ലഭ്യമാണ്."`
- **Claim Verdict**:
  - Claim 1: `supported` (NLI entailment: high, contradiction: low; exact values match; illustrative, not measured).
  - Claim 2: `unsupported` (Context is silent regarding ambulance service; NLI entailment: low, contradiction: low; illustrative, not measured).
- **Conflict Check**:
  - None.
- **Fact-Lock Result**:
  - Weekdays `"Tuesday and Thursday"`: `survived` (`ചൊവ്വ, വ്യാഴം`).
  - Time `"10:00 AM to 2:00 PM"`: `survived`.
- **GuardResult**:
  - `final_answer`: `"ഹോസ്പിറ്റൽ എയിൽ കാർഡിയോളജി ഒപി ചൊവ്വ, വ്യാഴം ദിവസങ്ങളിൽ രാവിലെ 10:00 മുതൽ ഉച്ചയ്ക്ക് 2:00 വരെ പ്രവർത്തിക്കുന്നു. [FLAG_TEXT]"`
  - `claims`: `[{"text": "ഹോസ്പിറ്റൽ എയിൽ കാർഡിയോളജി ഒപി ചൊവ്വ, വ്യാഴം ദിവസങ്ങളിൽ രാവിലെ 10:00 മുതൽ ഉച്ചയ്ക്ക് 2:00 വരെ പ്രവർത്തിക്കുന്നു.", "verdict": "supported", "evidence": "Hospital A - Cardiology OPD operates Tuesday and Thursday from 10:00 AM to 2:00 PM."}, {"text": "കൂടാതെ രോഗികൾക്ക് സൗജന്യ ആംബുലൻസ് സർവീസ് ലഭ്യമാണ്.", "verdict": "unsupported", "evidence": "None"}]`
  - `conflicts`: `[]`
  - `fact_lock`: `[{"item": "Tuesday and Thursday", "type": "weekday", "status": "survived"}, {"item": "10:00 AM to 2:00 PM", "type": "time", "status": "survived"}]`
  - `changed`: `True`

---

[MALAYALAM — NOT YET VERIFIED BY A NATIVE READER]
### Malayalam Example 9: Fact Belonging to the OTHER Hospital
- **INPUT**:
  - `context`: `["Hospital A - Dr. Test One is available Monday.", "Hospital B - Dr. Test Three is available Friday."]`
  - `instructions`: `"Query regarding Hospital A doctors."`
  - `answer`: `"ഹോസ്പിറ്റൽ എയിൽ വെള്ളിയാഴ്ച ഡോ. ടെസ്റ്റ് ത്രീ ലഭ്യമാണ്."`
  - `lang`: `"ml"`
- **Claim Split**:
  - Claim 1: `"ഹോസ്പിറ്റൽ എയിൽ വെള്ളിയാഴ്ച ഡോ. ടെസ്റ്റ് ത്രീ ലഭ്യമാണ്."`
- **Claim Verdict**:
  - Claim 1: `contradicted` (Context establishes Dr. Test Three belongs to Hospital B; NLI contradiction: high against Hospital A data; illustrative, not measured).
- **Conflict Check**:
  - `answer_vs_data` cross-tenant attribution conflict.
- **Fact-Lock Result**:
  - Doctor name `"Dr. Test Three"`: `changed` (`ഡോ. ടെസ്റ്റ് ത്രീ` attributed to wrong hospital).
- **GuardResult**:
  - `final_answer`: `"[FLAG_TEXT]"`
  - `claims`: `[{"text": "ഹോസ്പിറ്റൽ എയിൽ വെള്ളിയാഴ്ച ഡോ. ടെസ്റ്റ് ത്രീ ലഭ്യമാണ്.", "verdict": "contradicted", "evidence": "Hospital B - Dr. Test Three is available Friday."}]`
  - `conflicts`: `[{"type": "answer_vs_data", "text_a": "ഹോസ്പിറ്റൽ എയിൽ വെള്ളിയാഴ്ച ഡോ. ടെസ്റ്റ് ത്രീ ലഭ്യമാണ്.", "text_b": "Hospital B - Dr. Test Three is available Friday.", "evidence": "Hospital attribution clash"}]`
  - `fact_lock`: `[{"item": "Dr. Test Three", "type": "doctor_name", "status": "changed"}]`
  - `changed`: `True`

---

[MALAYALAM — NOT YET VERIFIED BY A NATIVE READER]
### Malayalam Example 10: Value Right in General but Not in the Data
- **INPUT**:
  - `context`: `["Hospital A - Dermatology clinic operates Wednesday 10:00 AM to 1:00 PM."]`
  - `instructions`: `"Provide consultation guidelines."`
  - `answer`: `"ഡെർമറ്റോളജി കൺസൾട്ടേഷനായി വരുമ്പോൾ രോഗി നിർബന്ധമായും മുൻ ഡിസ്ചാർജ് സമ്മറിയും തിരിച്ചറിയൽ രേഖയും കൊണ്ടുവരണം."`
  - `lang`: `"ml"`
- **Claim Split**:
  - Claim 1: `"ഡെർമറ്റോളജി കൺസൾട്ടേഷനായി വരുമ്പോൾ രോഗി നിർബന്ധമായും മുൻ ഡിസ്ചാർജ് സമ്മറിയും തിരിച്ചറിയൽ രേഖയും കൊണ്ടുവരണം."`
- **Claim Verdict**:
  - Claim 1: `unsupported` (Plausible general requirement, but Hospital A context does not contain this rule; NLI entailment: low, contradiction: low; illustrative, not measured).
- **Conflict Check**:
  - None.
- **Fact-Lock Result**:
  - Entity `"Dermatology"`: `survived` (`ഡെർമറ്റോളജി`).
- **GuardResult**:
  - `final_answer`: `"[FLAG_TEXT]"`
  - `claims`: `[{"text": "ഡെർമറ്റോളജി കൺസൾട്ടേഷനായി വരുമ്പോൾ രോഗി നിർബന്ധമായും മുൻ ഡിസ്ചാർജ് സമ്മറിയും തിരിച്ചറിയൽ രേഖയും കൊണ്ടുവരണം.", "verdict": "unsupported", "evidence": "None"}]`
  - `conflicts`: `[]`
  - `fact_lock`: `[{"item": "Dermatology", "type": "department", "status": "survived"}]`
  - `changed`: `True`

---

## 7. Known Failure Cases

The guard operates under specific structural limitations. The following failure cases are documented honestly:

1. **Complex and Double Negation**
   NLI models frequently struggle with nuanced negation (e.g., distinguishing *"not unavailable"* from *"available"*, or evaluating *"consultation is not provided on weekends"* against *"closed Saturday and Sunday"*), leading to misclassified contradiction or entailment verdicts.

2. **Multi-Passage Synthesis (Multi-Hop Entailment)**
   Pairwise comparison evaluates each claim against one passage at a time. If proving a claim requires synthesising information split across two separate passages (e.g., Passage 1: *"Dr. Test One leads Cardiology"*; Passage 2: *"Cardiology consultations are 500 INR"*), checking the claim *"Dr. Test One's fee is 500 INR"* against either passage alone will result in an erroneous `unsupported` verdict.

3. **Paraphrased Quantifiers and Relative Temporal Expressions**
   Exact-value matching fails on linguistic paraphrasing and relative dates. Expressions like *"half a grand"* (500), *"in the afternoon"*, *"tomorrow"*, or *"next Monday"* cannot be resolved deterministically without dynamic calendar context and deep numerical reasoning.

4. **Splitter Omissions in Compound Clauses**
   If the sentence splitter fails to decompose a complex sentence containing both true and fabricated clauses (e.g., *"Dr. Test One is available Monday and requires advance payment via card"* treated as a single unbroken claim), the NLI model may weigh the true premise heavily and mark the entire compound claim `supported`, allowing the ungrounded detail to slip past.

5. **Malayalam Agglutinative Morphology Breaking Splitters**
   In Malayalam, postpositions, coordinating conjunctions, and case markers attach directly to nouns and verbs as suffixes (e.g., adding `ഉം` [-um] to conjoin entities). Rule-based tokenizers calibrated on whitespace separation fail to split these agglutinated compound clauses.

6. **Degraded Multilingual NLI Quality in Low-Resource Languages**
   NLI models have substantially lower benchmark accuracy on low-resource Indic languages such as Malayalam compared to English. Cross-lingual transfer often yields low-confidence scores and erratic contradiction classification.

7. **Cross-Script Transliteration Discrepancies**
   Doctor and medication names transliterated between Latin and Malayalam scripts (e.g., "Dr. Kumar" rendered variously as "കുമാർ", "കുമാര്‍", or "ഡോക്ടർ കുമാർ") fail exact-string equality checks in `fact_lock` without complex phonetic normalization.

8. **Over-Redaction Degrading User Experience**
   Replacing every unsupported or borderline clause with `[FLAG_TEXT]` can fragment conversational answers into unreadable placeholders, causing severe user frustration over benign colloquial phrasing.

9. **Inability to Detect Outdated or Erroneous Context**
   The guard verifies consistency strictly against the retrieved passages. If the RAG retrieval pipeline fetches an outdated schedule or an incorrect hospital policy from the database, the guard will faithfully validate the generated response against that erroneous context.

10. **Conversational Coreference and Pronoun Drop**
    In multi-turn dialogues, answers frequently use pronouns (*"He is available Monday"*) or drop explicit subjects altogether (common in conversational Malayalam). Isolated claim checking lacks antecedent context and may mark valid statements as `unsupported`.

---

## 8. What Runs Locally for Free and What Needs a Paid Call

- Everything runs locally and free.
- No paid API call is planned.
- A free Colab GPU may be used for tasks G-08 and G-10 if the developer has no local GPU.
- All components—the sentence and clause splitter, the local multilingual NLI model [NLI MODEL — LEAD TO CONFIRM], regex entity extractors, and dictionary normalisers—operate entirely without external commercial API dependencies.

---

## Open Decisions for the Lead

The following open decisions collect every item requiring confirmation by the project lead:

1. **Context and Instruction Granularity:**
   `[LEAD TO DECIDE: confirm with Track 1, task M-08]` — Confirm what exactly the runner passes in `context` (one string per passage?) and `instructions` (admin free text only, or the whole prompt?).

2. **Action Policy per Verdict:**
   `[LEAD TO DECIDE: which action per verdict]` — Confirm what happens to each verdict: PROPOSED policy (supported -> keep unchanged; unsupported -> replace with `[FLAG_TEXT]`; contradicted -> replace with `[FLAG_TEXT]` and set `changed = True`) versus the alternative policy ("flag only, do not edit the answer").

3. **Pipeline Placement:**
   `[LEAD TO DECIDE: guard on the English answer before translation back to Malayalam, or on the final Malayalam answer, or both]`.

4. **NLI Model Selection:**
   `[NLI MODEL — LEAD TO CONFIRM]` — Local multilingual NLI model selection.

5. **Classification Thresholds:**
   `[THRESHOLDS — SET IN G-08]` — Entailment and contradiction score thresholds to be calibrated on the tuning half only in task G-08.
