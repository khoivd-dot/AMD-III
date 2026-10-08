"""Run every sample case against the live AMD endpoint and save the outputs for replay.

    export HOMEWARD_LLM_BASE_URL=http://<droplet-ip>:8000/v1
    export HOMEWARD_LLM_API_KEY=...            # the key you passed to vLLM
    export HOMEWARD_LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
    export HOMEWARD_HARDWARE="AMD Instinct MI300X (192 GB) · vLLM · ROCm"
    python scripts/record_samples.py [sample-id ...]

Scripted sample runs are moved to data/replay/scripted/ so nothing is lost.
"""
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from homeward import pipeline  # noqa: E402
from homeward.llm import REPLAY_DIR, RecordingClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


async def record(sample: dict, client: RecordingClient) -> dict:
    path = REPLAY_DIR / f"{sample['id']}.json"
    if path.exists():
        old = json.loads(path.read_text())
        if old.get("_meta", {}).get("source") == "scripted":
            (REPLAY_DIR / "scripted").mkdir(exist_ok=True)
            shutil.move(path, REPLAY_DIR / "scripted" / path.name)
        else:
            path.unlink()
    case = pipeline.new_case(sample["source"], sample["language"], sample.get("patient_name", ""), sample["id"])
    await pipeline.run(case, client)
    if case["stage"] != "ready":
        raise SystemExit(f"{sample['id']}: {case['error']}")
    for o in case["omissions"]:
        await pipeline.suggest(case, client, o["fact_id"])
    m = pipeline.metrics(case)
    return {"id": sample["id"], "facts": m["facts"], "sentences": m["sentences"],
            "flagged": m["sentences_flagged"], "red": m["by_status"]["red"], "amber": m["by_status"]["amber"],
            "omissions": m["omissions"], "grade": f"{m['source_grade']} -> {m['output_grade']}",
            "model_seconds": m["model"]["seconds"], "tokens_per_s": m["model"]["tokens_per_second"],
            "gpu_cost_usd": m["gpu_cost_usd"]}


async def main(ids):
    if not os.environ.get("HOMEWARD_LLM_BASE_URL"):
        raise SystemExit("Set HOMEWARD_LLM_BASE_URL to the vLLM endpoint first.")
    client = RecordingClient(os.environ["HOMEWARD_LLM_BASE_URL"],
                             os.environ.get("HOMEWARD_LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
                             os.environ.get("HOMEWARD_LLM_API_KEY", ""), os.environ.get("HOMEWARD_HARDWARE", ""))
    samples = [json.loads(p.read_text()) for p in sorted((ROOT / "data" / "samples").glob("*.json"))]
    rows = [await record(s, client) for s in samples if not ids or s["id"] in ids]
    for r in rows:
        print(json.dumps(r))
    (ROOT / "docs" / "recorded-runs.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
