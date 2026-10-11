"""Red-team regression: 20 subtle errors injected into 5 new cases, one at a time.

The cases and errors in eval/redteam/ were written by an independent tester that
played the model (vi, zh, fr, es; units, dates, AM/PM, "only if needed", omitted
warnings, invented reassurance, swapped insulin scales). Each error runs on its own
and is compared with the clean run of the same case.

    python -m eval.redteam_eval            # writes docs/redteam-report.md

The checks were improved after seeing these errors, so this is a regression suite,
not a held-out measure.
"""
import asyncio
import copy
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval" / "redteam"))
from homeward import pipeline  # noqa: E402

from build import MODULES, build  # noqa: E402
from sources import CASES  # noqa: E402


class Canned:
    """Serves one variant's model outputs, stage by stage."""
    mode = "replay"

    def __init__(self, responses: dict):
        self.responses = responses

    async def complete_json(self, stage, key, messages, schema, usage, case_id=None):
        return copy.deepcopy(self.responses[stage])


def run(case_id: str, responses: dict) -> dict:
    c = CASES[case_id]
    case = pipeline.new_case(c["source"], c["language"], c["patient_name"])
    asyncio.run(pipeline.run(case, Canned(responses)))
    assert case["stage"] == "ready", case["error"]
    return case


def _bad(checks):
    return {(c["name"], c["status"]) for c in checks if c["status"] != "pass"}


def classify(mut: dict, clean: dict, run_: dict) -> dict:
    cs = {s["id"]: s for s in clean["sentences"]}
    cf = {f["id"]: f for f in clean["facts"]}
    signals, hard, review = [], False, False
    for sid in mut["targets"].get("sentences", []):
        s = next((x for x in run_["sentences"] if x["id"] == sid), None)
        if not s:
            continue
        for name, status in sorted(_bad(s["checks"]) - (_bad(cs[sid]["checks"]) if sid in cs else set())):
            signals.append(f"{sid} {name}")
            hard = hard or status == "fail"
        review = review or s["needs_review"]
    for fid in mut["targets"].get("facts", []):
        f = next((x for x in run_["facts"] if x["id"] == fid), None)
        if f:
            signals += [f"{fid} {n}" for n, _ in sorted(_bad(f["checks"]) - (_bad(cf[fid]["checks"]) if fid in cf else set()))]
    # Any omission or medicine-list issue the clean run did not have. This includes
    # instructions the rule check found missing from the ledger (R-facts).
    clean_om = {o["message"] for o in clean["omissions"]}
    for o in run_["omissions"]:
        if o["message"] not in clean_om:
            signals.append(f"missing: {o['message'][:90]}")
            hard = True
    clean_mi = {m["message"] for m in clean["med_issues"]}
    for m in run_["med_issues"]:
        if m["message"] not in clean_mi:
            signals.append(f"medicine list: {m['message'][:90]}")
            hard = True
    outcome = ("blocked" if hard else "flagged" if signals else
               "not detected, in review" if review else "slipped through")
    return {"id": mut["id"], "kind": mut["kind"], "outcome": outcome, "signals": signals}


def evaluate() -> dict:
    results = {}
    for name in MODULES:
        mod = importlib.import_module(name)
        clean = run(mod.CASE_ID, build(mod, []))
        rows = [classify(m, clean, run(mod.CASE_ID, build(mod, [m]))) for m in mod.MUTATIONS]
        false_alarms = [{"id": s["id"], "status": s["status"],
                         "why": [c["message"] for c in s["checks"] if c["status"] != "pass"]}
                        for s in clean["sentences"] if s["status"] != "green"]
        results[mod.CASE_ID] = {"title": CASES[mod.CASE_ID]["title"], "rows": rows,
                                "clean_sentences": len(clean["sentences"]), "false_alarms": false_alarms}
    return results


def report(results: dict) -> str:
    rows = [r for c in results.values() for r in c["rows"]]
    count = {k: sum(r["outcome"] == k for r in rows) for k in ("blocked", "flagged", "not detected, in review",
                                                                 "slipped through")}
    clean_n = sum(c["clean_sentences"] for c in results.values())
    fa = [f for c in results.values() for f in c["false_alarms"]]
    out = ["# Red-team regression", "",
           "Five new discharge documents (Vietnamese, Simplified Chinese, French, Spanish) with 20 subtle errors, "
           "written by an independent tester that played the model. Each error is injected on its own and compared "
           "with the clean run of the same case. Deterministic checks plus the canned safety-model verdicts the "
           "tester wrote (often wrongly \"supported\").", "",
           f"**{count['blocked'] + count['flagged']} of {len(rows)} errors flagged** "
           f"({count['blocked']} blocked, {count['flagged']} sent to review as uncertain); "
           f"{count['not detected, in review']} not detected but in review as high-risk; "
           f"{count['slipped through']} slipped through. "
           f"On the clean versions, {len(fa)} of {clean_n} sentences were flagged.", "",
           "Before the fixes on this branch the same suite caught 7 of 20, 8 slipped through, and 23 of 92 clean "
           "sentences were flagged.", "",
           "| Case | Error | Outcome | What fired |", "|---|---|---|---|"]
    for cid, c in results.items():
        for r in c["rows"]:
            out.append(f"| {cid} | {r['id']}: {r['kind']} | {r['outcome']} | {'; '.join(r['signals'][:3]) or '–'} |")
    if fa:
        out += ["", "Flagged on the clean versions:", ""]
        out += [f"- {f['id']} ({f['status']}): {'; '.join(f['why'])}" for f in fa]
    out += ["", "## How to read this honestly", "",
            "- The checks on this branch were written after seeing these 20 errors, so this is now a regression "
            "suite, not a held-out measure. A fresh set of cases and errors written by someone else is the next test.",
            "- The canned safety-model verdicts are the tester's; a real model may do better or worse.",
            "- Sentences that cite a high-alert medicine, a stop, pause or change, or a warning sign go to a person "
            "even when nothing is flagged."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    res = evaluate()
    text = report(res)
    (ROOT / "docs" / "redteam-report.md").write_text(text)
    print(text)
