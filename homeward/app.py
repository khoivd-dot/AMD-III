"""Homeward web app."""

import asyncio
import io
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pipeline
from .lexicon import LANGUAGES
from .llm import LLMError, client_from_env

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT.parent / "data" / "samples"
MAX_CASES = 200

app = FastAPI(title="Homeward")
app.state.client = client_from_env()
CASES: dict[str, dict] = {}


def samples() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(SAMPLES.glob("*.json"))]


def get_case(cid: str) -> dict:
    case = CASES.get(cid)
    if not case:
        raise HTTPException(404, "Case not found. Cases live in memory and reset when the server restarts.")
    return case


@app.get("/api/meta")
def meta():
    client = app.state.client
    info = client.describe()
    replayable = set(info.get("cases", {})) if client.mode == "replay" else None
    return {
        "llm": info,
        "languages": LANGUAGES,
        "samples": [{"id": s["id"], "title": s["title"], "language": s["language"],
                     "patient_name": s.get("patient_name", ""),
                     "available": replayable is None or s["id"] in replayable,
                     "replay": (info.get("cases") or {}).get(s["id"])}
                    for s in samples()],
    }


@app.get("/api/samples/{sid}")
def sample(sid: str):
    for s in samples():
        if s["id"] == sid:
            return s
    raise HTTPException(404, "No such sample.")


class NewCase(BaseModel):
    source: str
    language: str
    patient_name: str = ""
    sample_id: str | None = None


def _start(source: str, language: str, patient_name: str, sample_id: str | None) -> dict:
    if not source.strip():
        raise HTTPException(400, "Paste the discharge instructions first.")
    if len(source) > 30000:
        raise HTTPException(400, "That document is too long for one packet (30,000 characters max).")
    # Sample ids select recorded runs; only honour them when the text is the sample's own.
    if sample_id:
        match = next((s for s in samples() if s["id"] == sample_id), None)
        if not match or match["source"].strip() != source.strip() or match["language"] != language:
            sample_id = None
    case = pipeline.new_case(source, language, patient_name, sample_id)
    if len(CASES) >= MAX_CASES:
        CASES.pop(next(iter(CASES)))
    CASES[case["id"]] = case
    asyncio.get_running_loop().create_task(pipeline.run(case, app.state.client))
    return {"id": case["id"]}


@app.post("/api/cases")
async def create_case(body: NewCase):
    return _start(body.source, body.language, body.patient_name, body.sample_id)


@app.post("/api/cases/upload")
async def upload_case(file: UploadFile = File(...), language: str = Form(...), patient_name: str = Form("")):
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(400, "File too large (5 MB max).")
    if (file.filename or "").lower().endswith(".pdf"):
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
    else:
        text = raw.decode("utf-8", errors="replace")
    return _start(text, language, patient_name, None)


@app.get("/api/cases/{cid}")
def read_case(cid: str):
    return pipeline.public(get_case(cid))


class Review(BaseModel):
    reviewer: str
    text_en: str | None = None
    text_tl: str | None = None
    fact_id: str | None = None
    reason: str | None = None
    drug: str | None = None


def _do(cid: str, fn):
    case = get_case(cid)
    try:
        fn(case)
    except (ValueError, KeyError, StopIteration) as exc:
        raise HTTPException(400, str(exc) or "Not found.")
    return pipeline.public(case)


def _need_reviewer(body: Review) -> str:
    if not body.reviewer.strip():
        raise HTTPException(400, "Enter the reviewer's name first.")
    return body.reviewer.strip()


@app.post("/api/cases/{cid}/sentences/{sid}/approve")
def approve(cid: str, sid: str, body: Review):
    who = _need_reviewer(body)
    return _do(cid, lambda c: pipeline.approve(c, sid, who))


@app.post("/api/cases/{cid}/sentences/{sid}/edit")
def edit(cid: str, sid: str, body: Review):
    who = _need_reviewer(body)
    return _do(cid, lambda c: pipeline.edit(c, sid, who, body.text_en, body.text_tl))


@app.post("/api/cases/{cid}/sentences/{sid}/remove")
def remove(cid: str, sid: str, body: Review):
    who = _need_reviewer(body)
    return _do(cid, lambda c: pipeline.remove(c, sid, who))


@app.post("/api/cases/{cid}/sentences")
def add(cid: str, body: Review):
    who = _need_reviewer(body)
    if not body.fact_id or not (body.text_en or "").strip():
        raise HTTPException(400, "Pick the fact and write the sentence.")
    return _do(cid, lambda c: pipeline.add_sentence(c, who, body.fact_id, body.text_en, body.text_tl))


@app.post("/api/cases/{cid}/facts/{fid}/dismiss")
def dismiss(cid: str, fid: str, body: Review):
    who = _need_reviewer(body)
    if not (body.reason or "").strip():
        raise HTTPException(400, "Say why this does not need to be in the packet.")
    return _do(cid, lambda c: pipeline.dismiss_fact(c, fid, who, body.reason))


@app.post("/api/cases/{cid}/med-issues/resolve")
def resolve(cid: str, body: Review):
    who = _need_reviewer(body)
    return _do(cid, lambda c: pipeline.resolve_med_issue(c, body.drug or "", who, body.reason or "checked"))


@app.post("/api/cases/{cid}/suggest/{fid}")
async def suggest(cid: str, fid: str):
    case = get_case(cid)
    try:
        return await pipeline.suggest(case, app.state.client, fid)
    except LLMError as exc:
        raise HTTPException(409, str(exc))
    except StopIteration:
        raise HTTPException(404, "No such fact.")


@app.post("/api/cases/{cid}/signoff")
def signoff(cid: str, body: Review):
    who = _need_reviewer(body)
    return _do(cid, lambda c: pipeline.sign_off(c, who))


@app.get("/api/cases/{cid}/packet")
def packet(cid: str):
    try:
        return pipeline.packet(get_case(cid))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


class Answer(BaseModel):
    choice: int


@app.post("/api/cases/{cid}/quiz/{qid}")
def answer(cid: str, qid: str, body: Answer):
    case = get_case(cid)
    try:
        return pipeline.answer(case, qid, body.choice)
    except (StopIteration, IndexError):
        raise HTTPException(404, "No such question.")


@app.get("/healthz")
def health():
    return JSONResponse({"ok": True, "mode": app.state.client.mode})


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")
