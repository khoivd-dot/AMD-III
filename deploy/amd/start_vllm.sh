#!/usr/bin/env bash
# Run on the AMD Developer Cloud droplet (image: "vLLM Quick Start", 1x MI300X).
# Starts an OpenAI-compatible vLLM server with an API key, inside the preinstalled ROCm container.
#   VLLM_API_KEY=... MODEL=Qwen/Qwen2.5-72B-Instruct bash start_vllm.sh
set -euo pipefail
MODEL="${MODEL:-Qwen/Qwen2.5-72B-Instruct}"
: "${VLLM_API_KEY:?Set VLLM_API_KEY; the port is public and vLLM has no auth without it}"
MAX_LEN="${MAX_LEN:-16384}"

docker exec -d -e VLLM_API_KEY="$VLLM_API_KEY" -e HF_TOKEN="${HF_TOKEN:-}" rocm bash -lc "
  python -m vllm.entrypoints.openai.api_server \
    --model '$MODEL' \
    --host 0.0.0.0 --port 8000 \
    --api-key \"\$VLLM_API_KEY\" \
    --dtype bfloat16 \
    --max-model-len $MAX_LEN \
    --gpu-memory-utilization 0.92 \
    --enable-prefix-caching \
    > /tmp/vllm.log 2>&1"

echo "Starting $MODEL. Follow progress with:"
echo "  docker exec rocm tail -f /tmp/vllm.log   (wait for 'Application startup complete')"
echo "Then test:"
echo "  curl -s localhost:8000/v1/models -H \"Authorization: Bearer \$VLLM_API_KEY\""
