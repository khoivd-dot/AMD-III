"""Throughput on the AMD endpoint: N packets at once, as a ward would send them.

    python scripts/benchmark.py --concurrency 1 4 16 --sample hf-maria-es

vLLM batches concurrent requests on the MI300X, so cost per packet falls as
load rises. Prints packets/hour and GPU dollars per packet at $1.99/h.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from homeward import pipeline  # noqa: E402
from homeward.llm import OpenAICompatClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


async def one(sample, client):
    case = pipeline.new_case(sample["source"], sample["language"], sample.get("patient_name", ""))
    await pipeline.run(case, client)
    return case


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 16])
    ap.add_argument("--sample", default="hf-maria-es")
    a = ap.parse_args()
    client = OpenAICompatClient(os.environ["HOMEWARD_LLM_BASE_URL"],
                                os.environ.get("HOMEWARD_LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
                                os.environ.get("HOMEWARD_LLM_API_KEY", ""), timeout=600)
    sample = json.loads((ROOT / "data" / "samples" / f"{a.sample}.json").read_text())
    rows = []
    for n in a.concurrency:
        t = time.perf_counter()
        cases = await asyncio.gather(*[one(sample, client) for _ in range(n)])
        wall = time.perf_counter() - t
        ok = sum(c["stage"] == "ready" for c in cases)
        tokens = sum(c["usage"].summary()["completion_tokens"] for c in cases)
        row = {"concurrency": n, "ok": ok, "wall_s": round(wall, 1),
               "packets_per_hour": round(3600 * ok / wall, 1) if ok else 0,
               "gpu_usd_per_packet": round(1.99 * wall / 3600 / ok, 4) if ok else None,
               "output_tokens_per_s": round(tokens / wall, 1)}
        print(json.dumps(row))
        rows.append(row)
    (ROOT / "docs" / "benchmark.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
