import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from homeward.app import app

ROOT = Path(__file__).resolve().parent.parent


def wait_ready(client, cid):
    for _ in range(100):
        c = client.get(f"/api/cases/{cid}").json()
        if c["stage"] in ("ready", "error"):
            return c
        time.sleep(0.02)
    raise AssertionError("pipeline did not finish")


def test_api_flow_and_replay_guard():
    s = json.loads((ROOT / "data/samples/knee-giulia-it.json").read_text())
    with TestClient(app) as client:
        meta = client.get("/api/meta").json()
        assert meta["llm"]["mode"] == "replay"
        r = client.post("/api/cases", json={"source": s["source"], "language": "it",
                                            "patient_name": s["patient_name"], "sample_id": s["id"]})
        c = wait_ready(client, r.json()["id"])
        assert c["stage"] == "ready" and "_mask" not in c
        cid = c["id"]
        assert client.post(f"/api/cases/{cid}/signoff", json={"reviewer": "RN A"}).status_code == 400
        assert client.post(f"/api/cases/{cid}/sentences/S6/approve", json={"reviewer": "RN A"}).status_code == 400
        client.post(f"/api/cases/{cid}/sentences/S6/remove", json={"reviewer": "RN A"})
        c = client.get(f"/api/cases/{cid}").json()
        for sent in c["sentences"]:
            if sent["needs_review"] and not sent.get("removed"):
                assert client.post(f"/api/cases/{cid}/sentences/{sent['id']}/approve", json={"reviewer": "RN A"}).status_code == 200
        assert client.get(f"/api/cases/{cid}/packet").status_code == 409  # not signed yet
        assert client.post(f"/api/cases/{cid}/signoff", json={"reviewer": "RN A"}).status_code == 200
        p = client.get(f"/api/cases/{cid}/packet").json()
        assert "Dr. Helen Marsh" in json.dumps(p, ensure_ascii=False)
        assert all("correct" not in o for q in p["quiz"] for o in q["options"])  # answers not sent to patient view
        meds = p["sections"]["medicines"]
        assert all("med_action" in m for m in meds) and any(m["med_action"] for m in meds)  # patient view groups by change

        # Edited text loses its recorded run: without a GPU the app says so instead of inventing output.
        r = client.post("/api/cases", json={"source": s["source"] + "\nExtra line.", "language": "it", "sample_id": s["id"]})
        c = wait_ready(client, r.json()["id"])
        assert c["stage"] == "error" and "No model is connected" in c["error"]


def _signed_knee(client):
    s = json.loads((ROOT / "data/samples/knee-giulia-it.json").read_text())
    r = client.post("/api/cases", json={"source": s["source"], "language": "it",
                                        "patient_name": s["patient_name"], "sample_id": s["id"]})
    c = wait_ready(client, r.json()["id"])
    cid = c["id"]
    client.post(f"/api/cases/{cid}/sentences/S6/remove", json={"reviewer": "RN A"})
    for sent in client.get(f"/api/cases/{cid}").json()["sentences"]:
        if sent["needs_review"] and not sent.get("removed"):
            client.post(f"/api/cases/{cid}/sentences/{sent['id']}/approve", json={"reviewer": "RN A"})
    assert client.post(f"/api/cases/{cid}/signoff", json={"reviewer": "RN A"}).status_code == 200
    return client.get(f"/api/cases/{cid}").json()


def test_signed_packet_is_locked_and_reachable_by_patient_link():
    with TestClient(app) as client:
        c = _signed_knee(client)
        cid = c["id"]
        for path, body in (("sentences/S1/edit", {"reviewer": "X", "text_en": "Changed."}),
                           ("sentences/S1/remove", {"reviewer": "X"}),
                           ("facts/F1/dismiss", {"reviewer": "X", "reason": "not needed at all"}),
                           ("signoff", {"reviewer": "X"})):
            r = client.post(f"/api/cases/{cid}/{path}", json=body)
            assert r.status_code == 400 and "locked" in r.json()["detail"]
        assert all("correct" not in o for q in c["quiz"] for o in q["options"])  # staff view has no answer key
        assert client.get(c["patient_link"]).status_code == 200  # the patient's page
        link = c["patient_link"].replace("/p/", "/api/patient/")
        p = client.get(link).json()
        assert p["signoff"]["by"] == "RN A"
        q = p["quiz"][0]["id"]
        assert client.post(f"{link}/quiz/{q}", json={"choice": -1}).status_code == 404
        first = client.post(f"{link}/quiz/{q}", json={"choice": 0}).json()
        again = client.post(f"{link}/quiz/{q}", json={"choice": 1}).json()
        assert again == {"correct": first["correct"], "already_answered": True}
        assert client.get("/api/patient/not-a-real-token").status_code == 404


def test_staff_password(monkeypatch):
    import homeward.app as appmod
    monkeypatch.setattr(appmod, "STAFF_PASSWORD", "ward7")
    with TestClient(app) as client:
        assert client.get("/api/meta").status_code == 401
        assert client.get("/api/meta", auth=("nurse", "wrong")).status_code == 401
        assert client.get("/api/meta", auth=("nurse", "ward7")).status_code == 200
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/patient/anything").status_code == 404  # patient links need no password
        assert client.get("/p/anything").status_code == 200 and client.get("/static/app.js").status_code == 200
        assert client.get("/").status_code == 401


def test_errors_are_plain_and_bad_pdfs_are_refused():
    with TestClient(app) as client:
        r = client.post("/api/cases/upload", files={"file": ("x.pdf", b"%PDF-1.4 broken", "application/pdf")},
                        data={"language": "es"})
        assert r.status_code == 400 and "PDF" in r.json()["detail"]
        s = json.loads((ROOT / "data/samples/hf-maria-es.json").read_text())
        cid = client.post("/api/cases", json={"source": s["source"], "language": "es", "sample_id": s["id"],
                                              "patient_name": s["patient_name"]}).json()["id"]
        wait_ready(client, cid)
        r = client.post(f"/api/cases/{cid}/sentences/S99/approve", json={"reviewer": "RN A"})
        assert r.status_code == 404 and "'" not in r.json()["detail"]
