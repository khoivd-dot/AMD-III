# Build prompt: Homeward

You are building **Homeward** for the AMD Developer Hackathon: ACT III, Health and Wellbeing track. Read `research.md` next to this file first; it holds the verified event rules and the evidence behind every claim below. Treat it as the source of truth and do not invent statistics.

## One-line pitch
Homeward turns a clinician's discharge instructions into plain-language instructions in the patient's own language, checks every sentence against the chart, sends only the risky sentences to a human, and confirms the patient understood before they leave. It runs on an open model served by vLLM on an AMD Instinct MI300X, so patient data never goes to a third-party API.

## Who it serves
- **Discharging nurse** (primary user): pastes or uploads the discharge instructions, picks the patient's language, gets a packet ready to review in under a minute.
- **Clinician or pharmacist reviewer**: sees only the sentences that failed a check or touch a high-risk fact, approves or edits them, signs off.
- **Patient and caregiver**: get a bilingual packet (their language beside English), large text, read-aloud, and a short teach-back quiz. Wrong answers alert the nurse to re-explain that item.

## Non-negotiable safety rules
1. Homeward never diagnoses, never recommends treatment, never adds medical content that is not in the source. It only restates what a clinician wrote.
2. Every patient-facing sentence must cite the source facts it restates. A sentence with no supporting fact is blocked.
3. Nothing reaches the patient until a named human signs off. High-risk facts (anticoagulants, insulin, opioids, any stop or hold of a medicine, warning signs that mean "come back now") always need explicit sign-off, even when every check passes.
4. Uncertainty is shown, never hidden: each sentence carries a green (verified), amber (needs a human look) or red (blocked) status with the reason in plain words.
5. If the language is not supported or checks fail repeatedly, the packet routes to a professional interpreter instead of guessing.
6. Direct identifiers (names, MRN, dates of birth, phone, email, address) are masked before any model call and are not written to logs. Demo uses synthetic patients only.

## Pipeline
1. **Ingest**: text or PDF. Mask identifiers (regex + known-name list), keep a reversible map in memory only.
2. **Fact ledger** (LLM, JSON schema output): atomic facts `{id, kind: medication|follow_up|warning_sign|activity|diet|wound_care|pending_result|other, med_action: new|changed|stop|hold|continue|null, drug, dose, frequency, detail, source_quote}`. Deterministic checks: the quote must exist in the source, every number in a fact must appear in its quote. A rule-based medication line parser cross-checks the LLM list; disagreements become amber.
3. **Plain-language draft** (LLM): short sentences at grade 6 or below, grouped into sections (Why you were in hospital, Your medicines, Warning signs, Appointments, Daily care). Each sentence lists `fact_ids`.
4. **Translation** (LLM): sentence by sentence; drug names and numbers kept verbatim.
5. **Back-translation** (LLM): target language back to English for checking.
6. **Verification**, per sentence:
   - citations exist;
   - numbers in the sentence and in its back-translation are a subset of numbers in the cited facts;
   - drug names mentioned match the cited facts;
   - polarity: a stop/hold fact must read as stop/hold in the back-translation and a continue fact must not;
   - LLM judge: supported / partially supported / unsupported / contradicts, with a one-line reason;
   - coverage: every medication, warning-sign and follow-up fact is cited by at least one sentence, otherwise an omission is raised on the packet;
   - readability: Flesch-Kincaid grade of the English draft.
   Combine into green/amber/red and a risk tier.
7. **Review**: reviewer queue shows red and amber sentences plus high-risk sentences. Edits re-run verification on that sentence. Sign-off records reviewer name and time in an audit log (masked).
8. **Patient packet**: bilingual view, read-aloud via the browser's speech synthesis, print view, teach-back quiz built deterministically from high-risk facts (no model call, so the quiz cannot hallucinate). Wrong answers create nurse alerts.
9. **Metrics**: source vs output reading grade, word counts, sentences needing human review vs total (review load), checks run, issues caught, time from paste to sign-off, model latency and tokens per second on the AMD endpoint.

## Validation
- Unit tests for masking, number/drug/polarity checks, coverage, readability, quiz generation.
- Mutation harness: take a verified packet and inject the error types the literature reports (drop a medicine sentence, flip stop to continue, change a dose, add an unsupported medicine, change a follow-up time, drop a warning sign). Report the share caught per type. Target 100% on deterministic types.
- End-to-end runs of 5+ synthetic cases (heart failure, AF on apixaban, type 1 diabetes on insulin, post-op knee on opioids, COPD exacerbation, pneumonia) in at least Spanish, Vietnamese, Simplified Chinese and Italian (judges are in Italy).
- With the AMD endpoint live: record latency, tokens/sec and cost per packet.

## Stack
- Python 3.11+, FastAPI, httpx, pydantic, pypdf. Vanilla HTML/CSS/JS frontend served by FastAPI, no build step.
- LLM: any OpenAI-compatible endpoint, configured by env (`HOMEWARD_LLM_BASE_URL`, `HOMEWARD_LLM_MODEL`, `HOMEWARD_LLM_API_KEY`). Target: vLLM on one MI300X serving a strong multilingual open model (Qwen2.5-72B-Instruct in bf16 fits in 192 GB; Qwen2.5-7B-Instruct as the cheap fallback).
- Without an endpoint the app runs in **replay mode** from recorded outputs and says so on screen.
- Docker image for the app; `deploy/amd/` scripts for the droplet.

## Demo story (under 5 minutes)
Maria, 72, Spanish-speaking, discharged after heart failure with a new medicine, a dose change, and "hold your ibuprofen". The nurse pastes the instructions; Homeward shows the fact ledger, the Spanish packet, one amber sentence (ambiguous "hold") and one red omission caught by coverage. The reviewer fixes both in two clicks and signs off. Maria (her daughter) takes the quiz, misses the ibuprofen question, the nurse gets an alert and re-explains. Metrics: grade 11 to 5, 4 of 22 sentences needed human eyes, all on one MI300X.

## Out of scope
Diagnosis, treatment suggestions, EHR write-back, real patient data, user accounts.
