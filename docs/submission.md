# Submission kit

Everything lablab.ai asks for, ready to paste. Items marked TODO need the live AMD run or a decision from the team.

## Title
Homeward: verified discharge instructions in every patient's language

## Short description (under 255 characters)
Homeward rewrites discharge instructions in plain language and the patient's own language, checks every sentence against the chart, sends only risky ones to a nurse, and confirms understanding. Open model on AMD MI300X.

## Track
Health and Wellbeing

## Tags
AMD Developer Cloud, AMD Instinct MI300X, ROCm, vLLM, Qwen, Healthcare, Patient Safety, Multilingual, Human-in-the-loop, FastAPI

## Long description
Going home from hospital is where instructions get lost. In one study only 48% of patients knew what their medicines were for, and patients with limited English were less likely to know their follow-up appointment (50% vs 66%). Discharge notes are written around a 10th-grade level when the AMA recommends 6th.

Language models can rewrite and translate, but unchecked they are unsafe: in a 2024 JAMA Network Open study, GPT-4 made discharge summaries readable, yet 18% of physician reviews raised a safety concern, mostly from omissions. Machine translation once turned "hold the kidney medicine" into "keep taking" it.

Homeward makes AI-rewritten instructions trustworthy enough to hand over:

- **Fact ledger.** The model lists every instruction, each tied to an exact quote from the clinician's text, and a rule-based medicine parser cross-checks it.
- **Cited plain-language draft.** Grade 6 or lower, and every sentence cites the facts it restates.
- **Translation with back-translation** into Spanish, Italian, Vietnamese, Chinese or French; unsupported languages route to a professional interpreter.
- **Checks on every sentence:** numbers, units and doses, doses a day, "only if needed", dates and AM/PM, insulin scale steps, medicine names, stop vs keep taking (including the "hold" vs "stop" trap), invented reassurance, invented names or contacts, and coverage of every instruction in the source, including ones the model left out of its ledger. Translations are checked in the target language itself, not only by back-translation. A safety model gives a second verdict. Each sentence is green, amber or red, with the reason in plain words.
- **Human review where it matters.** The reviewer sees only flagged sentences, every high-risk instruction (anticoagulants, insulin, opioids, any stop or dose change, warning signs) and anything missing. Nothing reaches the patient without a named sign-off.
- **Teach-back.** The patient gets a bilingual packet with read-aloud and a short quiz built from the approved sentences, so it cannot hallucinate. Wrong answers alert the nurse.
- **Privacy by design.** Identifiers are masked before any model call (labels in every supported language, international phone numbers, IDs, dates of birth and addresses) and restored only in the signed-off packet. The model is open-weight and self-hosted with vLLM and ROCm on an AMD Instinct MI300X, so no text goes to a third-party model API, and a 72B multilingual model fits on one 192 GB GPU a hospital could run itself.

Results: in the two scripted demo cases the reading grade drops from 8.7 to 4.1 and from 7.0 to 4.4, 53 to 62% of sentences need no human review, and every planted error (a 1.5 L fluid limit translated as 15 L, an invented ibuprofen for a patient on a blood thinner, a dropped weight-gain warning) is stopped before the patient sees it. An independent red team wrote 5 new cases with 20 subtle errors (units, AM/PM, "only if needed", omitted warnings): the first version caught 7, the current one flags all 20 while flagging 1 of 92 honest sentences. On real output from an open 3B model, the checks caught a dropped new medicine, dropped fluid and sodium limits, "must not stop" for a STOP order, and Chinese words inside Vietnamese text.

## Judging criteria, mapped
- **Application of technology:** five schema-constrained model calls per packet (extract, simplify, translate, back-translate, judge) on a self-hosted MI300X; the model is wrapped by deterministic checks so its mistakes are caught, not trusted. TODO: add measured latency, tokens/s and cost per packet from `scripts/benchmark.py`.
- **Presentation:** one realistic case end to end in under 5 minutes (script below).
- **Business value:** fewer post-discharge calls and readmission risk from misunderstood instructions; less interpreter and nurse time per discharge; in the demo cases the reviewer reads 38 to 47% of sentences instead of 100%. TODO: cost per packet from the benchmark (GPU time at $1.99/h).
- **Originality:** sentence-level citations, coverage checks and back-translation turn an LLM rewrite into something auditable; teach-back closes the loop with the patient.

## Video script (about 4.5 minutes)
1. **0:00 Hook (20 s).** "Maria is 72, speaks Spanish, and is going home after heart failure with five medicine changes. Half of patients leave hospital not knowing what their medicines are for." Show the clinician's discharge text.
2. **0:20 Problem (30 s).** The three numbers: 48% medicine comprehension, grade 10 notes, 18% safety concerns in GPT-4 rewrites. "Rewriting is easy. Trusting the rewrite is the problem."
3. **0:50 Prepare (40 s).** Nurse picks Spanish, clicks Create packet. Show the stages and the mode badge "Live on AMD Instinct MI300X". Open the fact ledger: every instruction tied to a quote; identifiers masked.
4. **1:30 Review (80 s).** Review screen: 16 sentences, 10 verified, the reviewer reads 6. Show the red Spanish sentence (15 L instead of 1.5 L, caught by numbers and back-translation) and fix it. Show the amber ibuprofen "hold" written as "stop" and edit it. Show the missing weight-gain warning, click "Suggest wording", add it. Approve the high-risk lines. Sign off.
5. **2:50 Patient (50 s).** Bilingual packet, read aloud in Spanish, warning signs in red. Maria's daughter takes the quiz and misses the furosemide question; switch to Impact to show the nurse alert.
6. **3:40 Impact and AMD (40 s).** Grade 8.7 to 4.1, 3 problems stopped, 6 identifiers masked, model time, tokens/s and cost per packet on the MI300X. "A 72B model on one GPU a hospital can own."
7. **4:20 Close (15 s).** "Homeward never diagnoses. It makes sure what the clinician wrote reaches the patient, in their language, and that they understood it."

## Slides (10)
1. Title and one-line pitch
2. Maria's story (the human problem)
3. The evidence (four numbers with sources)
4. Why plain AI rewriting is not enough (omissions, hallucinations, translation flips)
5. How Homeward works (pipeline diagram)
6. Safety: the six requirements and how each is handled (table from the README)
7. Demo screenshots: review screen and patient packet
8. Results: readability, review load, error-injection table
9. AMD: MI300X, vLLM, ROCm, why one 192 GB GPU matters for privacy; benchmark numbers
10. Business value, next steps (EHR integration via FHIR, more languages, pilot with a ward), team

## Links
- Repository: https://github.com/khoivd-dot/AMD-III (must be public before submitting)
- Demo platform: AMD Developer Cloud (app and vLLM on the same MI300X droplet) TODO: URL
- Fallback demo URL that works with the GPU off: TODO (any container host, replay mode)

## Open questions for the team
- The rules do not say whether code written before kickoff (12 October) is allowed. Ask in the lablab Discord, or disclose in the long description that the prototype was started before kickoff.
- Who records the video voice-over.
