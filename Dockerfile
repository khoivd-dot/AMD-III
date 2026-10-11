FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY homeward ./homeward
COPY data ./data
# Runs without a GPU in replay mode; set HOMEWARD_LLM_BASE_URL to use the AMD endpoint.
EXPOSE 8080
USER 1000
# Forwarded headers are trusted only from 127.0.0.1 unless FORWARDED_ALLOW_IPS says otherwise
# (deploy/amd/run_app.sh sets it for its private Caddy network).
CMD ["uvicorn", "homeward.app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-server-header"]
