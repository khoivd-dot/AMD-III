"""Model access.

`OpenAICompatClient` talks to any OpenAI-compatible server; in production that
is vLLM on an AMD Instinct MI300X. `ReplayClient` serves recorded outputs so
the app still works when the GPU is switched off, and says so on screen.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

REPLAY_DIR = Path(os.environ.get("HOMEWARD_REPLAY_DIR")
                  or Path(__file__).resolve().parent.parent / "data" / "replay")


class LLMError(RuntimeError):
    pass


@dataclass
class CallStat:
    stage: str
    seconds: float
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class Usage:
    calls: list[CallStat] = field(default_factory=list)

    def summary(self) -> dict:
        secs = sum(c.seconds for c in self.calls)
        comp = sum(c.completion_tokens for c in self.calls)
        prompt = sum(c.prompt_tokens for c in self.calls)
        return {
            "calls": len(self.calls),
            "seconds": round(secs, 2),
            "prompt_tokens": prompt,
            "completion_tokens": comp,
            "tokens_per_second": round(comp / secs, 1) if secs and comp else None,
            "by_stage": [c.__dict__ for c in self.calls],
        }


def parse_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
        if start < 0:
            raise
        return json.loads(text[start:])


def _plain(exc: Exception | None) -> str:
    """Why a call failed, for a nurse: no URLs, hostnames or Python internals."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"the model server answered with error {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "the model server took too long to answer"
    if isinstance(exc, httpx.HTTPError):
        return "the model server could not be reached"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "its reply was cut off or was not valid JSON"
    return "unknown error"


RETRY_NUDGE = ("\n\nYour last reply was not complete, valid JSON. Reply with valid JSON only. "
               "Keep every field short and list each item once.")


class OpenAICompatClient:
    mode = "live"

    def __init__(self, base_url: str, model: str, api_key: str = "", hardware: str = "",
                 timeout: float = 180.0, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.hardware = hardware or "hardware not stated"
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport

    def describe(self) -> dict:
        return {"mode": self.mode, "model": self.model, "hardware": self.hardware,
                "endpoint": re.sub(r"//[^/]+", "//…", self.base_url)}

    async def complete_json(self, stage: str, key: str, messages: list[dict], schema: dict,
                            usage: Usage, case_id: str | None = None):
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 4096,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": stage, "schema": schema}},
        }
        last_error = None
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            for attempt in range(3):
                started = time.perf_counter()
                try:
                    resp = await client.post(f"{self.base_url}/chat/completions",
                                             json=body, headers=headers)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    last_error = exc
                    # Some servers reject json_schema; fall back to plain JSON prompting.
                    body.pop("response_format", None)
                    continue
                data = resp.json()
                elapsed = time.perf_counter() - started
                u = data.get("usage") or {}
                usage.calls.append(CallStat(stage, elapsed, u.get("prompt_tokens", 0),
                                            u.get("completion_tokens", 0)))
                content = data["choices"][0]["message"]["content"]
                try:
                    return parse_json(content)
                except (json.JSONDecodeError, ValueError) as exc:
                    last_error = exc
                    # Small models sometimes run past the token limit or repeat themselves.
                    # At temperature 0 a plain retry would repeat the same output, so give
                    # room to finish, a little variation, and a nudge to stay compact.
                    body["max_tokens"], body["temperature"] = 8192, 0.2
                    body["messages"] = messages[:-1] + [{**messages[-1], "content": messages[-1]["content"] + RETRY_NUDGE}]
        raise LLMError(f"The model's {stage.replace('_', ' ')} step failed: {_plain(last_error)}.")


class RecordingClient(OpenAICompatClient):
    """Live client that also saves outputs for built-in sample cases."""

    directory: Path = REPLAY_DIR

    async def complete_json(self, stage, key, messages, schema, usage, case_id=None):
        result = await super().complete_json(stage, key, messages, schema, usage, case_id)
        if case_id:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{case_id}.json"
            data = json.loads(path.read_text()) if path.exists() else {}
            data.setdefault("_meta", {}).update({
                "source": "recorded", "model": self.model, "hardware": self.hardware,
                "recorded_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
            })
            data.setdefault(stage, {})[key] = result
            stat = usage.calls[-1]
            data.setdefault("_timings", {})[f"{stage}:{key}"] = stat.__dict__
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        return result


class ReplayClient:
    mode = "replay"

    def __init__(self, directory: Path = REPLAY_DIR):
        self.directory = directory

    def available(self) -> dict[str, dict]:
        out = {}
        for path in sorted(self.directory.glob("*.json")):
            if path.stem == "summary":
                continue
            meta = json.loads(path.read_text()).get("_meta", {})
            out[path.stem] = meta
        return out

    def describe(self) -> dict:
        return {"mode": self.mode, "model": None, "hardware": None, "cases": self.available()}

    async def complete_json(self, stage, key, messages, schema, usage, case_id=None):
        path = self.directory / f"{case_id}.json" if case_id else None
        if not path or not path.exists():
            raise LLMError("No model is connected, and this text has no recorded run. "
                           "Pick a sample case, or connect the AMD endpoint.")
        data = json.loads(path.read_text())
        try:
            result = data[stage][key]
        except KeyError:
            raise LLMError(f"Recorded run for {case_id} has no {stage}/{key} output.")
        timing = data.get("_timings", {}).get(f"{stage}:{key}")
        if timing:
            usage.calls.append(CallStat(**timing))
        return result


def client_from_env():
    base = os.environ.get("HOMEWARD_LLM_BASE_URL")
    if not base:
        return ReplayClient()
    cls = RecordingClient if os.environ.get("HOMEWARD_RECORD") == "1" else OpenAICompatClient
    return cls(base, os.environ.get("HOMEWARD_LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
               os.environ.get("HOMEWARD_LLM_API_KEY", ""),
               os.environ.get("HOMEWARD_HARDWARE", ""))
