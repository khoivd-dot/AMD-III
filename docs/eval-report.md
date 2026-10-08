# Homeward error-injection evaluation

Cases: hf-maria-es, knee-giulia-it. Deterministic checks only (the safety model's verdicts are removed), so this is the floor the product guarantees even if the model judge is wrong.

| Injected error | Injected | Flagged by checks | Blocked (red) | Flag rate | Reaches a human anyway* |
|---|---|---|---|---|---|
| as needed dropped (blind spot) | 1 | 0 | 0 | 0% | 100% |
| contact lost in translation | 4 | 4 | 4 | 100% | 100% |
| emergency number dropped | 2 | 2 | 2 | 100% | 100% |
| flip stop to keep | 3 | 3 | 3 | 100% | 100% |
| hallucinated medicine | 33 | 33 | 33 | 100% | 100% |
| hold as permanent stop | 1 | 1 | 0 | 100% | 100% |
| number changed | 26 | 26 | 26 | 100% | 100% |
| omission | 15 | 15 | 15 | 100% | 100% |
| translation flip | 3 | 3 | 3 | 100% | 100% |
| translation number changed | 26 | 26 | 26 | 100% | 100% |
| unsupported sentence | 33 | 33 | 33 | 100% | 100% |
| wrong medicine named | 14 | 14 | 13 | 100% | 100% |
| **all** | **161** | **160** | | **99.4%** | |

False alarms on the clean, reviewed packets: 0 across 33 sentences.

Missed:
- knee-giulia-it S4: 'only if needed' removed

Flagged means the sentence turned amber or red, or the packet raised an omission; either way it cannot reach the patient without a person deciding.

\* Reaches a human anyway: flagged, or the sentence carries a high-risk instruction (anticoagulant, insulin, opioid, any stop/pause/change, warning sign), which Homeward always sends for sign-off even when every check passes.

## How to read this honestly
- The mutations are synthetic and the checks were written with these failure types in mind, so a high rate here is a regression floor, not a claim about real-world accuracy.
- Rows marked *blind spot* are errors the deterministic layer cannot see (meaning changes with no number, medicine, contact or stop/keep word involved). They rely on the safety model and on mandatory review of high-risk sentences.
- Re-run against recorded AMD runs with `python -m eval.mutation_eval` after `scripts/record_samples.py`.
