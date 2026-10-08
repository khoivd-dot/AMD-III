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
