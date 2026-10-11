#!/usr/bin/env bash
# Run the Homeward web app on the same droplet, next to vLLM, behind HTTPS.
#   HOMEWARD_STAFF_PASSWORD=... VLLM_API_KEY=... bash run_app.sh
# Caddy takes ports 80 and 443 and gets a certificate for <ip>.sslip.io (or $DOMAIN).
# The app itself is not published on any port, so the staff password never crosses
# the internet in plain text.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${VLLM_API_KEY:?Set VLLM_API_KEY to the key vLLM was started with}"
: "${HOMEWARD_STAFF_PASSWORD:?Set HOMEWARD_STAFF_PASSWORD; without it anyone can read and sign off packets}"
if [ "${#HOMEWARD_STAFF_PASSWORD}" -lt 12 ]; then
  echo "HOMEWARD_STAFF_PASSWORD must be at least 12 characters. Try: openssl rand -base64 18" >&2
  exit 1
fi
IP="$(curl -4fsS https://ifconfig.me 2>/dev/null || true)"
if [ -z "${DOMAIN:-}" ] && [ -n "$IP" ]; then DOMAIN="$(echo "$IP" | tr . -).sslip.io"; fi
: "${DOMAIN:?Could not find the public IP of this droplet; set DOMAIN to a name that points at it}"

docker build -t homeward .
docker network create homeward 2>/dev/null || true
docker rm -f homeward homeward-https 2>/dev/null || true
# Only Caddy can reach the app, so the app may trust Caddy's X-Forwarded-For
# (used to slow down password guessing per address).
docker run -d --name homeward --restart unless-stopped --network homeward \
  --add-host=host.docker.internal:host-gateway \
  -e FORWARDED_ALLOW_IPS='*' \
  -e HOMEWARD_STAFF_PASSWORD \
  -e HOMEWARD_LLM_BASE_URL=http://host.docker.internal:8000/v1 \
  -e HOMEWARD_LLM_API_KEY="$VLLM_API_KEY" \
  -e HOMEWARD_LLM_MODEL="${MODEL:-Qwen/Qwen2.5-72B-Instruct}" \
  -e HOMEWARD_HARDWARE="AMD Instinct MI300X (192 GB) · vLLM · ROCm" \
  homeward
docker run -d --name homeward-https --restart unless-stopped --network homeward \
  -p 80:80 -p 443:443 -v homeward-caddy:/data \
  caddy:2 caddy reverse-proxy --from "$DOMAIN" --to homeward:8080
echo "Homeward is on https://$DOMAIN/ (the certificate can take a minute on first start)"
