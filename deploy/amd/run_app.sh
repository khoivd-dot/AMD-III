#!/usr/bin/env bash
# Run the Homeward web app on the same droplet, next to vLLM, on port 80.
#   VLLM_API_KEY=... bash run_app.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
docker build -t homeward .
docker rm -f homeward 2>/dev/null || true
docker run -d --name homeward --restart unless-stopped -p 80:8080 \
  --add-host=host.docker.internal:host-gateway \
  -e HOMEWARD_LLM_BASE_URL=http://host.docker.internal:8000/v1 \
  -e HOMEWARD_LLM_API_KEY="$VLLM_API_KEY" \
  -e HOMEWARD_LLM_MODEL="${MODEL:-Qwen/Qwen2.5-72B-Instruct}" \
  -e HOMEWARD_HARDWARE="AMD Instinct MI300X (192 GB) · vLLM · ROCm" \
  homeward
echo "Homeward is on http://$(curl -s ifconfig.me 2>/dev/null || echo '<droplet-ip>')/"
