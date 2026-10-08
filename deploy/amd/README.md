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
5. Start the app on port 80: `bash deploy/amd/run_app.sh`, then open `http://<ip>/`.
6. Record real runs of the sample cases so the public demo still works when the GPU is off:
   ```bash
   export HOMEWARD_LLM_BASE_URL=http://localhost:8000/v1 HOMEWARD_LLM_API_KEY=$VLLM_API_KEY
   python scripts/record_samples.py
   python scripts/benchmark.py --concurrency 1 4 16
   python -m eval.mutation_eval
   ```
   Commit `data/replay/*.json`, `docs/recorded-runs.json` and `docs/benchmark.json`.
7. **Destroy the droplet when you are done.** A powered-off droplet is still billed.

Security notes: Docker port mappings bypass UFW, so port 8000 is reachable from the internet. Always start vLLM with `--api-key` (the script refuses to run without one), and only ever send synthetic data.
