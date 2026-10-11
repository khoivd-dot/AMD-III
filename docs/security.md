# Security and health-data handling

Homeward handles discharge instructions, so it is built on the assumption that what it holds is health data. This page lists what protects that data, what a deployment must set, and what is still open. Last reviewed 11 October 2026.

## What protects the data

| Area | How |
|---|---|
| Model never sees identifiers | Names, record numbers, dates of birth, phones, emails and addresses are masked before any model call and restored only in the signed-off patient packet (`homeward/phi.py`). The model is open-weight and self-hosted, so text is not sent to a third-party model API. |
| Nothing stored | Cases live in server memory only and disappear on restart. No database, no files written (except recorded runs of the built-in synthetic samples, when `HOMEWARD_RECORD=1`). |
| Staff sign-in | With `HOMEWARD_STAFF_PASSWORD` set, every staff page and API call needs it. After 10 wrong passwords from one address in 10 minutes, that address is refused for 10 minutes. The AMD deploy script refuses to start without a password of 12 or more characters. |
| Patient link | `/p/<token>` uses a 128-bit random token, opens only that patient's signed packet and quiz, never the staff view, and works only after sign-off. Tokens are kept out of access logs and are never sent on as a referrer. |
| Answer key | Quiz answers stay on the server; neither the staff nor the patient view receives them. |
| Locked after sign-off | Once a packet is signed off, it cannot be edited, removed from or signed again. |
| Encrypted in transit | `deploy/amd/run_app.sh` puts Caddy in front of the app with an automatic HTTPS certificate; the app port is not published. |
| Browser protections | Every response sends a Content Security Policy that allows only the app's own scripts, styles, fonts and images (no third-party requests), plus `nosniff`, `frame-ancestors 'none'`, `no-referrer`, and HSTS over HTTPS. Health-data responses are `Cache-Control: no-store`. |
| Cross-site requests | State-changing requests from another site's page are refused (Fetch metadata and Origin checks), so a malicious page cannot use a nurse's saved sign-in. |
| Untrusted input | Model output and pasted text are HTML-escaped before display; ids from the model are restricted to `F12`-style values. Request bodies over 6 MB, PDFs over 60 pages, over-long fields and unknown language codes are refused. Reviewer names are stripped of invisible characters and must contain at least two letters. |
| API surface | No interactive API docs (`/docs`, `/openapi.json`) are served. Errors shown to staff carry no URLs, hostnames or stack traces. |
| Secrets | No keys or passwords are in the repository or its history. The model key comes from the environment (`HOMEWARD_LLM_API_KEY`) or GitHub repository secrets. |

## Deployment checklist

1. Set `HOMEWARD_STAFF_PASSWORD` (12+ characters, e.g. `openssl rand -base64 18`) anywhere other people can reach the app.
2. Serve over HTTPS (`deploy/amd/run_app.sh` does this), or behind a host that terminates TLS.
3. Start vLLM with `--api-key` (`start_vllm.sh` refuses to run without one). Its port 8000 is plain HTTP and Docker publishes it past UFW, so send only synthetic data to it and destroy the droplet when the run is done.
4. Use only synthetic cases in any public demo.

## Known limits

- One shared staff password, not personal accounts; the reviewer name on a sign-off is typed, not proven. A hospital deployment would use its single sign-on.
- Masking is rule-based. A name written with no label or title can slip through; a de-identification model as a second pass is the next step.
- Cases in memory are lost on restart, which also means there is no audit log that survives a restart.
