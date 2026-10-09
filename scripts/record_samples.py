"""Run sample cases against a live model endpoint and save the outputs for replay.

    export HOMEWARD_LLM_BASE_URL=http://<droplet-ip>:8000/v1
    export HOMEWARD_LLM_API_KEY=...            # the key you passed to vLLM
    export HOMEWARD_LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
    export HOMEWARD_HARDWARE="AMD Instinct MI300X (192 GB) · vLLM · ROCm"
    python scripts/record_samples.py [--out DIR] [sample-id ...]

With the default --out (data/replay) scripted sample runs are moved to
data/replay/scripted/ so nothing is lost. A summary of each run, including what
the checks flagged, is written to <out>/summary.json.

    python scripts/record_samples.py --recheck --out data/runs/<label>

re-runs today's checks over outputs recorded earlier, without calling a model.
"""
import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from homeward import pipeline  # noqa: E402
from homeward.llm import REPLAY_DIR, RecordingClient, ReplayClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def flagged(case: dict) -> list[dict]:
    out = []
    for s in case["sentences"]:
        problems = [c["message"] for c in s.get("checks", []) if c["status"] != "pass"]
        if problems:
            out.append({"id": s["id"], "status": s["status"], "text_en": s["text_en"],
                        "text_tl": s.get("text_tl"), "back_en": s.get("back_en"), "problems": problems})
    return out


async def record(sample: dict, client) -> dict:
    path = client.directory / f"{sample['id']}.json"
    if client.mode == "replay":
        if not path.exists():
            return {}
    elif path.exists():
        old = json.loads(path.read_text())
        if old.get("_meta", {}).get("source") == "scripted":
            (client.directory / "scripted").mkdir(exist_ok=True)
            shutil.move(path, client.directory / "scripted" / path.name)
        else:
            path.unlink()
    started = time.perf_counter()
    case = pipeline.new_case(sample["source"], sample["language"], sample.get("patient_name", ""), sample["id"])
    await pipeline.run(case, client)
    if case["stage"] != "ready":
        return {"id": sample["id"], "error": case["error"], "wall_seconds": round(time.perf_counter() - started, 1)}
    for o in case["omissions"]:
        try:
            await pipeline.suggest(case, client, o["fact_id"])
        except Exception as exc:  # a failed suggestion should not lose the run
            print(f"{sample['id']}: suggestion for {o['fact_id']} failed: {exc}", file=sys.stderr)
    m = pipeline.metrics(case)
    return {"id": sample["id"], "language": sample["language"], "facts": m["facts"],
            "sentences": m["sentences"], "flagged_for_human": m["sentences_flagged"], "by_status": m["by_status"],
            "omissions": case["omissions"], "medicine_cross_check": case["med_issues"],
            "fact_problems": [{"id": f["id"], "problems": [c["message"] for c in f["checks"] if c["status"] != "pass"]}
                              for f in case["facts"] if f["status"] != "green"],
            "flagged_sentences": flagged(case),
            "grade": [m["source_grade"], m["output_grade"]], "route": case["route"],
            "model": {k: m["model"][k] for k in ("calls", "seconds", "prompt_tokens", "completion_tokens", "tokens_per_second")},
            "wall_seconds": round(time.perf_counter() - started, 1)}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--out", default=str(REPLAY_DIR))
    ap.add_argument("--recheck", action="store_true", help="re-run the checks on outputs already in --out")
    a = ap.parse_args()
    summary = Path(a.out) / "summary.json"
    old = json.loads(summary.read_text()) if summary.exists() else {}
    if a.recheck:
        client = ReplayClient(Path(a.out))
        meta = old.get("_meta", {})
        client.model, client.hardware = meta.get("model"), meta.get("hardware")
    elif not os.environ.get("HOMEWARD_LLM_BASE_URL"):
        raise SystemExit("Set HOMEWARD_LLM_BASE_URL to the model endpoint first.")
    else:
        client = RecordingClient(os.environ["HOMEWARD_LLM_BASE_URL"],
                             os.environ.get("HOMEWARD_LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
                             os.environ.get("HOMEWARD_LLM_API_KEY", ""), os.environ.get("HOMEWARD_HARDWARE", ""),
                                 timeout=float(os.environ.get("HOMEWARD_LLM_TIMEOUT", "1800")))
        client.directory = Path(a.out)
    samples = [json.loads(p.read_text()) for p in sorted((ROOT / "data" / "samples").glob("*.json"))]
    rows = []
    for s in samples:
        if a.ids and s["id"] not in a.ids:
            continue
        row = await record(s, client)
        if not row:
            continue
        print(json.dumps({k: row.get(k) for k in ("id", "error", "sentences", "flagged_for_human", "by_status", "wall_seconds")}), flush=True)
        rows.append(row)
    client.directory.mkdir(parents=True, exist_ok=True)
    if a.recheck:
        for r in rows:  # keep the model timings measured when the run was recorded
            prev = old.get(r["id"], {})
            r["wall_seconds"] = prev.get("wall_seconds", r["wall_seconds"])
            if prev.get("model"):  # replay only sees the final outputs, not retries or their time
                r["model"] = prev["model"]
            r["rechecked_at"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    old.update({r["id"]: r for r in rows})
    if not a.recheck:
        old["_meta"] = {"model": client.model, "hardware": client.hardware,
                        "recorded_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    summary.write_text(json.dumps(old, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
