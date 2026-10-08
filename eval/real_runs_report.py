"""Markdown report of what Homeward's checks flagged on real model output.

Usage: python eval/real_runs_report.py data/runs/<label> > REPORT.md
"""
import json
import sys
from pathlib import Path

run = Path(sys.argv[1])
summary = json.loads((run / "summary.json").read_text())
meta = summary.pop("_meta", {})
lines = [f"# Real model runs: {run.name}", "",
         f"Model: **{meta.get('model', '?')}**. Hardware: **{meta.get('hardware', '?')}**. Recorded {meta.get('recorded_at', '?')}.", "",
         "| Case | Sentences | Green | Amber | Red | Missing items | Medicine cross-check | Model calls | Model time | Output tokens/s |",
         "|---|---|---|---|---|---|---|---|---|---|"]
for cid, r in sorted(summary.items()):
    if r.get("error"):
        lines.append(f"| {cid} | failed: {r['error']} | | | | | | | | |")
        continue
    b, m = r["by_status"], r["model"]
    lines.append(f"| {cid} | {r['sentences']} | {b['green']} | {b['amber']} | {b['red']} | {len(r['omissions'])} | "
                 f"{len(r['medicine_cross_check'])} | {m['calls']} | {m['seconds']} s | {m['tokens_per_second'] or '–'} |")
for cid, r in sorted(summary.items()):
    if r.get("error"):
        continue
    lines += ["", f"## {cid}", ""]
    for o in r["omissions"]:
        lines.append(f"- **Missing** {o['fact_id']}: {o['message']}")
    for m in r["medicine_cross_check"]:
        lines.append(f"- **Medicine list** {m['message']}")
    for f in r["fact_problems"]:
        lines.append(f"- **Fact {f['id']}**: {'; '.join(f['problems'])}")
    for s in r["flagged_sentences"]:
        tl = f" / {s['text_tl']}" if s.get("text_tl") else ""
        lines.append(f"- **{s['id']} {s['status']}**: {s['text_en']}{tl}  \n  {'; '.join(s['problems'])}")
    if not (r["omissions"] or r["medicine_cross_check"] or r["fact_problems"] or r["flagged_sentences"]):
        lines.append("Nothing flagged.")
print("\n".join(lines))
