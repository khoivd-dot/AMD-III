"""The live client against a fake OpenAI-compatible (vLLM-style) server."""
import asyncio
import json
from pathlib import Path

import httpx

from homeward import pipeline
from homeward.llm import OpenAICompatClient

ROOT = Path(__file__).resolve().parent.parent
REPLAY = json.loads((ROOT / "data/replay/hf-maria-es.json").read_text())


def fake_vllm(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        assert request.headers["authorization"] == "Bearer secret"
        stage = body["response_format"]["json_schema"]["name"]
        key = "en" if stage in ("facts", "draft") else "es"
        content = "```json\n" + json.dumps(REPLAY[stage][key], ensure_ascii=False) + "\n```"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 400},
        })
    return httpx.MockTransport(handler)


def test_pipeline_over_openai_compatible_api():
    calls = []
    client = OpenAICompatClient("http://gpu.example:8000/v1", "Qwen/Qwen2.5-72B-Instruct", "secret",
                                transport=fake_vllm(calls))
    s = json.loads((ROOT / "data/samples/hf-maria-es.json").read_text())
    case = pipeline.new_case(s["source"], "es", s["patient_name"])
    asyncio.run(pipeline.run(case, client))
    assert case["stage"] == "ready", case["error"]
    assert [c["response_format"]["json_schema"]["name"] for c in calls] == \
        ["facts", "draft", "translate", "back_translate", "judge"]
    assert all(c["temperature"] == 0 for c in calls)
    # No identifier ever left the building.
    sent = json.dumps(calls, ensure_ascii=False)
    for secret in ("Maria", "Lopez", "00482913", "03/14/1953", "201-3344", "Patel"):
        assert secret not in sent
    m = pipeline.metrics(case)
    assert m["model"]["calls"] == 5 and m["model"]["completion_tokens"] == 2000
    assert "gpu_cost_usd" in m  # mock calls take ~0 s, so the cost rounds to nothing


def test_falls_back_when_server_rejects_json_schema():
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append("response_format" in body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "unsupported"})
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})
    client = OpenAICompatClient("http://x/v1", "m", transport=httpx.MockTransport(handler))
    from homeward.llm import Usage
    out = asyncio.run(client.complete_json("facts", "en", [], {}, Usage()))
    assert out == {"ok": True} and seen == [True, False]


def test_retries_cut_off_json_with_room_to_finish():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        content = '{"facts": [{"id": "F1", "detail": "unfinish' if len(bodies) == 1 else '{"facts": []}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    client = OpenAICompatClient("http://x/v1", "m", transport=httpx.MockTransport(handler))
    from homeward.llm import Usage
    msgs = [{"role": "user", "content": "Extract facts."}]
    assert asyncio.run(client.complete_json("facts", "en", msgs, {}, Usage())) == {"facts": []}
    assert [b["max_tokens"] for b in bodies] == [4096, 8192]
    assert bodies[1]["temperature"] > 0 and "valid JSON only" in bodies[1]["messages"][-1]["content"]
    assert msgs == [{"role": "user", "content": "Extract facts."}]  # caller's prompt untouched
