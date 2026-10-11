# Running Homeward on AMD Developer Cloud

Verified against the lablab.ai tutorial "AMD Developer Cloud: Host Your First LLM" (October 2026).

1. Join the AMD AI Developer Program (new members get $100 of credit, about 50 hours of one MI300X at $1.99/h). Sign in to AMD Developer Cloud and add a card under Billing, or the GPU Droplet button stays grey.
2. Create a GPU Droplet: region ATL1, 1x MI300X (192 GB HBM3), image **vLLM Quick Start**, your SSH key.
3. `ssh root@<ip>` and clone this repository.
4. Start the model (bf16 Qwen2.5-72B-Instruct fits on one MI300X with room for the KV cache):
   ```bash
   export VLLM_API_KEY=$(openssl rand -hex 16)
   bash deploy/amd/start_vllm.sh
   docker exec rocm tail -f /tmp/vllm.log   # wait for "Application startup complete"
   ```
   The first start downloads about 145 GB of weights. For a faster start use `MODEL=Qwen/Qwen2.5-32B-Instruct`.
5. Start the app on port 80: `HOMEWARD_STAFF_PASSWORD=<something> bash deploy/amd/run_app.sh`, then open `http://<ip>/`. With the password set, the browser asks for it once (any user name); patient links work without it.
6. Record real runs of the sample cases so the public demo still works when the GPU is off:
   ```bash
   export HOMEWARD_LLM_BASE_URL=http://localhost:8000/v1 HOMEWARD_LLM_API_KEY=$VLLM_API_KEY
   python scripts/record_samples.py
   python scripts/benchmark.py --concurrency 1 4 16
   python -m eval.mutation_eval
   ```
   Commit `data/replay/*.json`, `docs/recorded-runs.json` and `docs/benchmark.json`.
   Or record from GitHub without logging in to the droplet: add repository secrets `HOMEWARD_LLM_BASE_URL` (`http://<ip>:8000/v1`) and `HOMEWARD_LLM_API_KEY` (the `VLLM_API_KEY`), then run the "Record real model runs" workflow with backend `endpoint`, model `Qwen/Qwen2.5-72B-Instruct`, hardware `AMD Instinct MI300X · vLLM · ROCm` and a label such as `mi300x-qwen2.5-72b`. The outputs land on the branch `runs/<label>`.
7. **Destroy the droplet when you are done.** A powered-off droplet is still billed.

What the deck reads from these runs, and how each number is measured:

| Number | Source | Method |
|---|---|---|
| Packets per hour on one MI300X | `docs/benchmark.json` | `scripts/benchmark.py`: full pipeline (5 model calls) on the sample cases at concurrency 1, 4 and 16; packets finished divided by wall-clock time |
| Output tokens per second | `docs/benchmark.json` | completion tokens reported by vLLM across all packets, divided by wall-clock time (whole-GPU throughput) |
| Seconds per packet | `docs/benchmark.json` | `wall_s` divided by packets finished, at concurrency 1 |
| GPU cost per packet | `docs/benchmark.json` | $1.99 per GPU hour divided by packets per hour at the best concurrency |

Security notes: Docker port mappings bypass UFW, so port 8000 is reachable from the internet. Always start vLLM with `--api-key` (the script refuses to run without one), and only ever send synthetic data.
