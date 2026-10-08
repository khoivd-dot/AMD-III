"""Merge per-sample run artifacts (one directory each) into one run directory.

Usage: python eval/merge_runs.py <artifacts-dir> <out-dir>
"""
import json
import shutil
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
summary: dict = {}
for d in sorted(p for p in src.iterdir() if p.is_dir()):
    for f in d.rglob("*.json"):
        if f.name == "summary.json":
            data = json.loads(f.read_text())
            meta = data.pop("_meta", None)
            summary.update(data)
            if meta:
                summary["_meta"] = meta
        else:
            shutil.copy(f, out / f.name)
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(f"merged {len([k for k in summary if not k.startswith('_')])} runs into {out}")
