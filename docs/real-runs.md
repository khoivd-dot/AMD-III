# Real model runs

The two demo cases replay hand-written model outputs. This page is about output from a real model that nobody wrote by hand.

**What ran:** Qwen2.5-3B-Instruct (Q4_K_M GGUF) on a GitHub Actions CPU runner through llama.cpp, using the workflow in `.github/workflows/record-runs.yml`. **This is not AMD hardware**, and a 3B model is far weaker than the 72B model Homeward is designed for. It was the fastest way to get honest, unscripted output while the AMD Developer Cloud account is set up. Outputs and per-case reports are in `data/runs/<label>/`.

Speed on the CPU runner: 9 to 15 output tokens per second, 2.5 to 6 minutes of model time per packet. These are not the benchmark numbers for the deck; those come from the MI300X.

## First run (`data/runs/cpu-qwen2.5-3b`)

Five sample cases (Spanish, Italian, Vietnamese, French). Four finished. The Italian knee case failed: the model kept writing facts until it hit the 4,096-token limit, so its JSON was cut off.

### What the small model got wrong

- **Wrong labels everywhere.** It labelled almost every fact "diagnosis", including every medicine, warning sign and appointment, and dropped the "NEW:" / "STOP:" labels from its quotes.
- **Dropped instructions.** Heart failure: sacubitril/valsartan (a new medicine), the 2 g sodium limit and the 1.5 L fluid limit are missing from the ledger. Diabetes: "check blood glucose before each meal and at bedtime", "never skip insulin glargine" and "call the diabetes team if you are sick and cannot eat" are missing.
- **A stop became a keep.** Atrial fibrillation: the source says STOP aspirin; the draft says "You must not stop taking Aspirin".
- **Mixed scripts.** Two Vietnamese sentences contain Chinese words ("停止服用" for stop taking, "晕倒" for fainting). The back-translation smoothed both over ("you fall").
- **Other translation errors.** "Primary care in 1 week" became "Cardiology in one week" in Vietnamese, with the numbers written as words. "2 puffs" became "2 pincettes" (tweezers) in French. "11/04/2026" in French reads as 11 April, not 4 November.
- **Invented content.** Diabetes: "check your glucose at least 4 times a day" and "get regular exercise" are not in the source.

### What the checks did, before and after

On the same recorded outputs (re-run with `python scripts/record_samples.py --recheck --out data/runs/cpu-qwen2.5-3b`):

| Case | Before: sentences flagged / items missing | After: sentences flagged / items missing |
|---|---|---|
| Atrial fibrillation, Vietnamese | 2 of 5 / 0 | 3 of 5 / 2 |
| COPD, French | 0 of 9 / 0 | 3 of 9 / 1 |
| Diabetes, Spanish | 1 of 5 / 0 | 1 of 5 / 4 |
| Heart failure, Spanish | 0 of 9 / 0 | 0 of 9 / 3 |

Before the fixes, the wrong labels quietly switched off most checks: coverage, stop/keep and risk only look at medicines, warning signs and appointments, so a ledger of "diagnosis" facts passed. The dropped sacubitril and the "must not stop taking aspirin" both got through.

What changed (all in `homeward/verify.py` unless noted):

1. **Labels are re-derived from the clinician's text.** A fact that names a medicine with a dose or an action is a medicine. The "NEW:" / "STOP:" label on the source line decides the action, even when the model leaves it out of the quote. Any difference is shown on the fact.
2. **Instructions the model left out become facts.** Every instruction line in the source is compared with the ledger. Anything not covered is added as a rule-found fact that the draft must cover, so it blocks sign-off until it is in the packet or a reviewer explains why not.
3. **"Must not stop" and "never skip" read as keep taking**, which turns the aspirin sentence red.
4. **Mixed writing systems are blocked** in translations.
5. **Units, dates, AM/PM, doses a day and "only if needed"** are compared between source, English and translation, in every supported language (this came from the simulated user testing; see `docs/redteam-report.md`).
6. **A cut-off JSON reply is retried** with room to finish and a request to stay compact (`homeward/llm.py`).
7. **The facts prompt** now asks for the quote before the labels, and includes a short worked example (`homeward/prompts.py`).

Still not caught: the invented "get regular exercise" in the diabetes case is red only because it sits in the same sentence as an invented number. A sentence of plain invented advice that cites a real fact relies on the safety model, which a 3B model is not strong enough to be.

## Second run (`data/runs/cpu-qwen2.5-3b-v2`)

Same model and hardware, with the new prompts. See that folder's `REPORT.md` once the run finishes; this section is updated with the comparison.

## The AMD run

What the deck needs, and how it is measured, is in `deploy/amd/README.md`: the same five cases recorded on one AMD Instinct MI300X with vLLM and Qwen2.5-72B-Instruct, plus `scripts/benchmark.py` for packets per hour, output tokens per second and GPU cost per packet.
