"""The independent tester's 20 injected errors stay caught (see eval/redteam_eval.py)."""
from eval.redteam_eval import evaluate


def test_redteam_errors_are_all_flagged_and_clean_text_is_quiet():
    results = evaluate()
    rows = [r for c in results.values() for r in c["rows"]]
    assert len(rows) == 20
    assert [r["id"] for r in rows if r["outcome"] in ("slipped through", "not detected, in review")] == []
    # The one clean flag is real: the tester's Spanish keeps 10/12/2026, which reads as 10 December.
    flagged = [f for c in results.values() for f in c["false_alarms"]]
    assert len(flagged) <= 1 and all("Dates differ" in " ".join(f["why"]) for f in flagged)
