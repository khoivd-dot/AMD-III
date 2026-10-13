"""Homeward web app."""

import asyncio
import base64
import io
import json
import logging
import os
import re
import secrets
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import pipeline, security
from .lexicon import LANGUAGES
from .llm import LLMError, client_from_env

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT.parent / "data" / "samples"
MAX_CASES = 200
MAX_BODY = 6_000_000  # the 5 MB upload limit plus form overhead
MAX_PDF_PAGES = 60

# No interactive API docs: the API is for this app's own pages.
app = FastAPI(title="Homeward", docs_url=None, redoc_url=None, openapi_url=None)
app.state.client = client_from_env()
CASES: dict[str, dict] = {}
# Staff password. When set, every page and API call needs it (the browser asks once),
# except the patient's own link. Unset for a local demo.
STAFF_PASSWORD = os.environ.get("HOMEWARD_STAFF_PASSWORD", "")
# Static files hold no patient data; the patient page reads only its own packet.
OPEN_PATHS = ("/healthz", "/api/patient/", "/p/", "/static/")
SIGN_IN = security.Throttle()
log = logging.getLogger("homeward")
logging.getLogger("uvicorn.access").addFilter(security.RedactPatientLinks())
if not STAFF_PASSWORD and os.environ.get("HOMEWARD_LLM_BASE_URL"):
    log.warning("HOMEWARD_STAFF_PASSWORD is not set: anyone who can reach this server can read and sign off packets.")


def _staff_check(request: Request) -> Response | None:
    """None when the request may go on; otherwise the refusal to send."""
    who = request.client.host if request.client else "?"
    if SIGN_IN.blocked(who):
        return JSONResponse({"detail": "Too many wrong passwords. Wait ten minutes, then try again."}, status_code=429,
                        headers={"Retry-After": "600"})
    given = ""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        try:
            given = base64.b64decode(auth[6:], validate=True).decode().split(":", 1)[-1]
        except ValueError:
            given = ""
    if secrets.compare_digest(given.encode(), STAFF_PASSWORD.encode()):
        SIGN_IN.clear(who)
        return None
    if given:  # a browser's first, credential-less request is not a wrong guess
        SIGN_IN.fail(who)
    return JSONResponse({"detail": "Staff sign-in required."}, status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Homeward staff", charset="UTF-8"'})


def _refusal(request: Request) -> Response | None:
    size = request.headers.get("content-length")
    if size is not None and (not size.isdigit() or int(size) > MAX_BODY):
        return JSONResponse({"detail": "Request too large."}, status_code=413)
    if size is None and "chunked" in request.headers.get("transfer-encoding", "").lower():
        return JSONResponse({"detail": "Send a Content-Length."}, status_code=411)
    if security.cross_site(request.method, request.headers, request.headers.get("host", "")):
        return JSONResponse({"detail": "Requests from other sites are not accepted."}, status_code=403)
    if STAFF_PASSWORD and not request.url.path.startswith(OPEN_PATHS):
        return _staff_check(request)
    return None


@app.middleware("http")
async def guard(request: Request, call_next):
    response = _refusal(request) or await call_next(request)
    response.headers.update(security.headers_for(request.url.path, request.url.scheme == "https"))
    return response


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
    source: str = Field(max_length=30000)
    language: str = Field(max_length=20)
    patient_name: str = Field("", max_length=200)
    sample_id: str | None = Field(None, max_length=80)


# Supported languages, or a short language code that goes to an interpreter.
_LANG = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})?|other")


def _start(source: str, language: str, patient_name: str, sample_id: str | None) -> dict:
    if not source.strip():
        raise HTTPException(400, "Paste the discharge instructions first.")
    if len(source) > 30000:
        raise HTTPException(400, "That document is too long for one packet (30,000 characters max).")
    if language not in LANGUAGES and not _LANG.fullmatch(language):
        raise HTTPException(400, "Pick a language from the list.")
    if len(patient_name) > 200:
        raise HTTPException(400, "That name is too long.")
    # Sample ids select recorded runs; only honour them when the text is the sample's own.
    if sample_id:
        match = next((s for s in samples() if s["id"] == sample_id), None)
        if not match or match["source"].strip() != source.strip() or match["language"] != language:
            sample_id = None
    case = pipeline.new_case(source, language, patient_name, sample_id)
    if len(CASES) >= MAX_CASES:
        # Make room by dropping the oldest finished packet, never one still being reviewed.
        done = next((k for k, c in CASES.items() if c.get("signoff") or c["stage"] == "error"), None)
        if done is None:
            raise HTTPException(503, f"{MAX_CASES} packets are open. Sign off or close some first.")
        CASES.pop(done)
    case["patient_token"] = secrets.token_urlsafe(16)
    CASES[case["id"]] = case
    asyncio.get_running_loop().create_task(pipeline.run(case, app.state.client))
    return {"id": case["id"]}


@app.post("/api/cases")
async def create_case(body: NewCase):
    return _start(body.source, body.language, body.patient_name, body.sample_id)


def _pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader
    try:
        pages = PdfReader(io.BytesIO(raw)).pages
        if len(pages) > MAX_PDF_PAGES:
            raise HTTPException(400, f"That PDF has more than {MAX_PDF_PAGES} pages. Upload the discharge instructions only.")
        return "\n".join(page.extract_text() or "" for page in pages)
    except HTTPException:
        raise
    except Exception:  # pypdf raises many types on damaged files
        raise HTTPException(400, "Could not read that PDF. Try copying the text and pasting it instead.")


@app.post("/api/cases/upload")
async def upload_case(file: UploadFile = File(...), language: str = Form(...), patient_name: str = Form("")):
    raw = await file.read(5_000_001)
    if len(raw) > 5_000_000:
        raise HTTPException(400, "File too large (5 MB max).")
    if (file.filename or "").lower().endswith(".pdf"):
        text = await asyncio.to_thread(_pdf_text, raw)
    else:
        text = raw.decode("utf-8", errors="replace")
    return _start(text, language, patient_name, None)


@app.get("/api/cases/{cid}")
def read_case(cid: str):
    return pipeline.public(get_case(cid))


class Review(BaseModel):
    reviewer: str = Field(max_length=100)
    text_en: str | None = Field(None, max_length=2000)
    text_tl: str | None = Field(None, max_length=2000)
    fact_id: str | None = Field(None, max_length=20)
    reason: str | None = Field(None, max_length=1000)
    drug: str | None = Field(None, max_length=200)


def _do(cid: str, fn):
    case = get_case(cid)
    try:
        fn(case)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except (KeyError, StopIteration):
        raise HTTPException(404, "That sentence or fact is not in this packet.")
    return pipeline.public(case)


def _need_reviewer(body: Review) -> str:
    who = security.clean_name(body.reviewer)
    if not who:
        raise HTTPException(400, "Enter the reviewer's name first.")
    if not security.is_real_name(who):
        raise HTTPException(400, "Enter the reviewer's real name, as it should appear on the packet.")
    return who


@app.post("/api/cases/{cid}/sentences/{sid}/approve")
def approve(cid: str, sid: str, body: Review):
    who = _need_reviewer(body)
    return _do(cid, lambda c: pipeline.approve(c, sid, who))


@app.post("/api/cases/{cid}/sentences/{sid}/edit")
async def edit(cid: str, sid: str, body: Review):
    who = _need_reviewer(body)
    _do(cid, lambda c: pipeline.edit(c, sid, who, body.text_en, body.text_tl))
    case = get_case(cid)
    await pipeline.reverify(case, app.state.client, sid)
    return pipeline.public(case)


@app.post("/api/cases/{cid}/sentences/{sid}/remove")
def remove(cid: str, sid: str, body: Review):
    who = _need_reviewer(body)
    return _do(cid, lambda c: pipeline.remove(c, sid, who))


@app.post("/api/cases/{cid}/sentences")
async def add(cid: str, body: Review):
    who = _need_reviewer(body)
    if not body.fact_id or not (body.text_en or "").strip():
        raise HTTPException(400, "Pick the fact and write the sentence.")
    added = {}
    _do(cid, lambda c: added.update(pipeline.add_sentence(c, who, body.fact_id, body.text_en, body.text_tl)))
    case = get_case(cid)
    await pipeline.reverify(case, app.state.client, added["id"])
    return pipeline.public(case)


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
    except (KeyError, TypeError):
        raise HTTPException(409, "The model's suggestion came back incomplete. Try again, or write the sentence yourself.")


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
    choice: int = Field(ge=0, le=9)


class Ack(BaseModel):
    reviewer: str = Field(max_length=100)
    note: str = Field("", max_length=1000)


@app.post("/api/cases/{cid}/alerts/{aid}/acknowledge")
def acknowledge(cid: str, aid: str, body: Ack):
    who = _need_reviewer(body)
    note = security.clean_name(body.note)
    return _do(cid, lambda c: pipeline.acknowledge_alert(c, aid, who, note))


@app.post("/api/cases/{cid}/quiz/{qid}")
def answer(cid: str, qid: str, body: Answer):
    case = get_case(cid)
    try:
        return pipeline.answer(case, qid, body.choice)
    except (StopIteration, IndexError):
        raise HTTPException(404, "No such question or answer.")


# The patient's own link: the signed packet and its quiz, nothing else.
def _by_token(token: str) -> dict:
    case = next((c for c in CASES.values() if secrets.compare_digest(c.get("patient_token", ""), token)), None)
    if not case:
        raise HTTPException(404, "This link has expired. Ask your nurse for a new one.")
    return case


@app.get("/api/patient/{token}")
def patient_packet(token: str):
    try:
        return pipeline.packet(_by_token(token))
    except ValueError:
        raise HTTPException(409, "Your instructions are still being checked by your care team.")


@app.post("/api/patient/{token}/quiz/{qid}")
def patient_answer(token: str, qid: str, body: Answer):
    try:
        return pipeline.answer(_by_token(token), qid, body.choice)
    except (StopIteration, IndexError):
        raise HTTPException(404, "No such question or answer.")


@app.get("/healthz")
def health():
    return JSONResponse({"ok": True, "mode": app.state.client.mode})


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/p/{token}")
def patient_page(token: str):
    return FileResponse(ROOT / "static" / "index.html")
