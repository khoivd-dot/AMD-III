import base64
import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from homeward import security
from homeward.app import app

ROOT = Path(__file__).resolve().parent.parent


def test_security_headers_and_no_api_docs():
    with TestClient(app) as client:
        for path in ("/", "/api/meta", "/static/app.js", "/p/anything"):
            h = client.get(path).headers
            assert "script-src 'self'" in h["content-security-policy"] and "unsafe-inline" not in h["content-security-policy"]
            assert "frame-ancestors 'none'" in h["content-security-policy"]
            assert h["x-content-type-options"] == "nosniff"
            assert h["referrer-policy"] == "no-referrer"
        assert client.get("/api/meta").headers["cache-control"] == "no-store"
        assert client.get("/p/anything").headers["cache-control"] == "no-store"
        assert "strict-transport-security" not in client.get("/").headers
        assert client.get("/", headers={"X-Forwarded-Proto": "https"}).status_code == 200
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404
        h = client.get("/api/patient/nope").headers  # refusals carry the headers too
        assert h["referrer-policy"] == "no-referrer" and h["cache-control"] == "no-store"


def test_cross_site_posts_are_refused():
    s = json.loads((ROOT / "data/samples/hf-maria-es.json").read_text())
    body = {"source": s["source"], "language": "es"}
    with TestClient(app) as client:
        assert client.post("/api/cases", json=body, headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/cases", json=body, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert client.post("/api/cases", json=body, headers={"Origin": "null"}).status_code == 403
        r = client.post("/api/cases/upload", files={"file": ("a.txt", b"Take aspirin.")}, data={"language": "es"},
                        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
        assert r.status_code == 403
        assert client.post("/api/cases", json=body, headers={"Origin": "http://testserver",
                                                              "Sec-Fetch-Site": "same-origin"}).status_code == 200


def test_wrong_passwords_are_throttled(monkeypatch):
    import homeward.app as appmod
    monkeypatch.setattr(appmod, "STAFF_PASSWORD", "a-long-ward-password")
    monkeypatch.setattr(appmod, "SIGN_IN", security.Throttle(limit=5))
    with TestClient(app) as client:
        assert client.get("/api/meta").status_code == 401  # no credentials yet: not counted
        for i in range(5):
            assert client.get("/api/meta", auth=("nurse", f"guess{i}")).status_code == 401
        r = client.get("/api/meta", auth=("nurse", "a-long-ward-password"))
        assert r.status_code == 429 and r.headers["retry-after"]
        assert client.get("/api/patient/nope").status_code == 404  # patients are never locked out
        bad = "Basic " + base64.b64encode(b"\xff\xfe").decode()
        monkeypatch.setattr(appmod, "SIGN_IN", security.Throttle(limit=5))
        assert client.get("/api/meta", headers={"Authorization": bad}).status_code == 401
        assert client.get("/api/meta", auth=("nurse", "a-long-ward-password")).status_code == 200


def test_oversized_and_malformed_input_is_refused():
    with TestClient(app) as client:
        assert client.post("/api/cases", content=b"x", headers={"Content-Length": "7000000",
                                                                 "Content-Type": "application/json"}).status_code == 413
        assert client.post("/api/cases", json={"source": "Take aspirin.", "language": "<img src=x>"}).status_code == 400
        assert client.post("/api/cases", json={"source": "x" * 30001, "language": "es"}).status_code == 422
        assert client.post("/api/cases", json={"source": "Take aspirin.", "language": "tl"}).status_code == 200
        assert client.post("/api/cases", json={"source": "Take aspirin.", "language": "other"}).status_code == 200


def test_reviewer_names_must_be_visible():
    assert security.clean_name(" RN​ Sam\tLee ‮") == "RN Sam Lee"
    assert not security.is_real_name(security.clean_name("​"))
    assert not security.is_real_name("1")
    assert security.is_real_name("Lê") and security.is_real_name("李明")
    s = json.loads((ROOT / "data/samples/hf-maria-es.json").read_text())
    with TestClient(app) as client:
        cid = client.post("/api/cases", json={"source": s["source"], "language": "es", "sample_id": s["id"]}).json()["id"]
        assert len(cid) == 32
        for name in ("​", " x ", "12"):
            r = client.post(f"/api/cases/{cid}/sentences/S1/approve", json={"reviewer": name})
            assert r.status_code == 400 and "name" in r.json()["detail"]


def test_patient_tokens_are_kept_out_of_access_logs():
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("1.2.3.4", "GET", "/p/AbC_d-123?x=1", "1.1", 200), None)
    security.RedactPatientLinks().filter(rec)
    assert rec.getMessage() == '1.2.3.4 - "GET /p/<token>?x=1 HTTP/1.1" 200'
    rec.args = ("1.2.3.4", "POST", "/api/patient/tok123/quiz/Q1", "1.1", 200)
    security.RedactPatientLinks().filter(rec)
    assert "tok123" not in rec.getMessage()
