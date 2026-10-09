"""Discharge packet pipeline: mask, extract, draft, translate, check, review."""

import re
import time
import uuid

from . import prompts, quiz
from .lexicon import LANGUAGES
from .llm import LLMError, Usage
from .phi import mask
from .textutil import fk_grade, spell_dates, word_count
from .verify import coverage, cross_check_meds, uncovered_instructions, verify_facts, verify_sentence

GPU_DOLLARS_PER_HOUR = 1.99  # AMD Developer Cloud, 1x MI300X
INTERPRETER_RED_SHARE = 0.3  # above this share of blocked sentences, call an interpreter

STAGES = ["masking", "facts", "draft", "translate", "back_translate", "judge", "checks", "ready"]


def new_case(source: str, language: str, patient_name: str = "", sample_id: str | None = None) -> dict:
    masked = mask(source, [patient_name] if patient_name else None)
    return {
        "id": uuid.uuid4().hex[:10],
        "sample_id": sample_id,
        "created_at": time.time(),
        "language": language,
        "language_name": LANGUAGES.get(language, language),
        "stage": "queued",
        "error": None,
        "source_masked": masked.text,
        "_mask": masked,  # never serialised
        "phi_counts": masked.counts(),
        "facts": [], "med_issues": [], "sentences": [], "omissions": [],
        "usage": Usage(),
        "signoff": None, "quiz": [], "alerts": [], "audit": [],
        "route": "standard",
    }


def audit(case: dict, actor: str, action: str, detail: str = "") -> None:
    case["audit"].append({"at": time.time(), "actor": actor, "action": action, "detail": detail})


async def run(case: dict, client) -> dict:
    usage: Usage = case["usage"]
    key = case["language"]
    cid = case.get("sample_id")
    try:
        audit(case, "system", "masked identifiers",
              ", ".join(f"{k.lower()} x{v}" for k, v in case["phi_counts"].items()) or "none found")

        case["stage"] = "facts"
        out = await client.complete_json("facts", "en", prompts.facts_messages(case["source_masked"]),
                                         prompts.FACTS_SCHEMA, usage, cid)
        facts = _norm_facts(out)
        verify_facts(facts, case["source_masked"])
        # Instructions the model left out become rule-found facts, so the draft must cover them.
        missed = uncovered_instructions(facts, case["source_masked"])
        facts += missed
        if missed:
            audit(case, "system", "rule check found instructions the model missed",
                  "; ".join(f["source_quote"] for f in missed))
        case["facts"] = facts
        case["med_issues"] = cross_check_meds(facts, case["source_masked"])

        case["stage"] = "draft"
        out = await client.complete_json("draft", "en", prompts.draft_messages(facts),
                                         prompts.DRAFT_SCHEMA, usage, cid)
        sentences = _norm_sentences(out)
        for s in sentences:
            s["text_en"] = spell_dates(s["text_en"])  # 10/12/2026 is 10 December outside the US
        case["sentences"] = sentences

        if case["language"] not in LANGUAGES:
            case["route"] = "interpreter"
        elif case["language"] != "en":
            name = LANGUAGES[case["language"]]
            case["stage"] = "translate"
            out = await client.complete_json("translate", key, prompts.translate_messages(sentences, name),
                                             prompts.TRANSLATION_SCHEMA, usage, cid)
            tl = _by_id(out, "items", "text")
            for s in sentences:
                s["text_tl"] = tl.get(s["id"], "")
            case["stage"] = "back_translate"
            items = [{"id": s["id"], "text": s["text_tl"]} for s in sentences if s["text_tl"]]
            out = await client.complete_json("back_translate", key,
                                             prompts.back_translate_messages(items, name),
                                             prompts.TRANSLATION_SCHEMA, usage, cid)
            back = _by_id(out, "items", "text")
            for s in sentences:
                s["back_en"] = back.get(s["id"], "")

        case["stage"] = "judge"
        by_id = {f["id"]: f for f in facts}
        rows = []
        for s in sentences:
            row = {"id": s["id"], "sentence": s["text_en"],
                   "facts": [by_id[i]["detail"] for i in s["fact_ids"] if i in by_id]}
            if s.get("text_tl"):
                row["translation"] = s["text_tl"]
            if s.get("back_en"):
                row["back_translation"] = s["back_en"]
            rows.append(row)
        try:
            out = await client.complete_json("judge", key, prompts.judge_messages(rows),
                                             prompts.JUDGE_SCHEMA, usage, cid)
            verdicts = {v["id"]: v for v in (out.get("verdicts") or []) if isinstance(v, dict) and v.get("id")}
        except LLMError as exc:
            # The deterministic checks still stand; every sentence shows it was not model-reviewed.
            verdicts = {}
            audit(case, "system", "safety model unavailable", str(exc))
        for s in sentences:
            s["judge_en"] = verdicts.get(s["id"])

        case["stage"] = "checks"
        recheck(case)
        # Freeze what the checks found on the model's draft, before any human edits.
        draft = metrics(case)
        case["at_draft"] = {k: draft[k] for k in ("sentences", "sentences_flagged", "by_status",
                                                  "issues_caught", "omissions", "med_issues", "high_risk")}
        red = sum(1 for s in sentences if s["status"] == "red")
        if case["route"] == "standard" and case["language"] != "en" and sentences \
                and red / len(sentences) > INTERPRETER_RED_SHARE:
            case["route"] = "interpreter"
        audit(case, "system", "packet drafted",
              f"{len(facts)} facts, {len(sentences)} sentences, {red} blocked")
        case["stage"] = "ready"
    except (LLMError, ValueError) as exc:
        _failed(case, str(exc))
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        _failed(case, f"The model's {case['stage'].replace('_', ' ')} output was incomplete, so this packet "
                      f"stopped there. Try again; if it keeps happening, the model needs checking. "
                      f"({type(exc).__name__})")
    return case


def _failed(case: dict, message: str) -> None:
    case["error"] = message
    audit(case, "system", f"stopped at {case['stage']}", message)
    case["stage"] = "error"


# Small or busy models sometimes return slightly off-schema JSON. Normalise it
# rather than fail; anything still unusable shows up as a failed check.
SECTIONS = ("why", "medicines", "warning_signs", "appointments", "daily_care")


_ID = re.compile(r"[A-Z]{1,2}\d{1,3}x?")


def _clean_id(value) -> str:
    """Ids come from the model and end up in the page; accept only F12-style ids."""
    text = re.sub(r"\s+", "", str(value or "")).upper().replace("X", "x")
    return text if _ID.fullmatch(text) else ""


def _norm_facts(out: dict) -> list[dict]:
    facts, seen = [], set()
    for i, f in enumerate(out.get("facts") or [], 1):
        if not isinstance(f, dict):
            continue
        fid = _clean_id(f.get("id")) or f"F{i}"
        if fid in seen:
            fid = f"F{i}x"
        seen.add(fid)
        facts.append({"id": fid, "kind": f.get("kind") if f.get("kind") in prompts.FACT_KINDS else "other",
                      "med_action": f.get("med_action") if f.get("med_action") in prompts.MED_ACTIONS else None,
                      **{k: (str(f[k]) if f.get(k) is not None else None) for k in ("drug", "dose", "frequency")},
                      "detail": str(f.get("detail") or ""), "source_quote": str(f.get("source_quote") or "")})
    if not facts:
        raise ValueError("The model returned no facts.")
    return facts


def _norm_sentences(out: dict) -> list[dict]:
    sentences, seen = [], set()
    for i, s in enumerate(out.get("sentences") or [], 1):
        if not isinstance(s, dict) or not str(s.get("text") or "").strip():
            continue
        sid = _clean_id(s.get("id")) or f"S{i}"
        if sid in seen:
            sid = f"S{i}x"
        seen.add(sid)
        ids = s.get("fact_ids") or []
        ids = ids if isinstance(ids, list) else [ids]
        sentences.append({"id": sid, "section": s.get("section") if s.get("section") in SECTIONS else "daily_care",
                          "text_en": str(s["text"]).strip(),
                          "fact_ids": [x for x in map(_clean_id, ids) if x],
                          "review": None})
    if not sentences:
        raise ValueError("The model returned no sentences.")
    return sentences


def _by_id(out: dict, key: str, field: str) -> dict[str, str]:
    return {_clean_id(i["id"]): str(i.get(field) or "") for i in (out.get(key) or [])
            if isinstance(i, dict) and i.get("id")}


def recheck(case: dict) -> None:
    by_id = {f["id"]: f for f in case["facts"]}
    live = [s for s in case["sentences"] if not s.get("removed")]
    for s in live:
        verify_sentence(s, by_id, case["facts"], case["language"])
        # An approval covers this exact wording (any edit resets it). An edit alone does
        # not: a flagged or high-risk line stays in review until someone approves it.
        if s.get("review") and s["review"]["state"] == "approved" and s["status"] != "red":
            s["needs_review"] = False
    case["omissions"] = coverage(case["facts"], live)


def blockers(case: dict) -> list[str]:
    out = []
    if case["stage"] != "ready":
        out.append("The packet is not ready yet.")
    for s in case["sentences"]:
        if s.get("removed"):
            continue
        if s["needs_review"]:
            out.append(f"{s['id']} needs a decision.")
    for o in case["omissions"]:
        out.append(f"{o['fact_id']}: {o['message']}")
    for f in case["facts"]:
        if f["status"] == "red" and not f.get("dismissed"):
            out.append(f"{f['id']}: fact not found in source.")
    for m in case["med_issues"]:
        if not m.get("resolved"):
            out.append(m["message"])
    return out


# ------------------------------------------------------------- review

def _open(case: dict) -> None:
    if case.get("signoff"):
        raise ValueError(f"This packet was signed off by {case['signoff']['by']} and is locked. "
                         "Start a new packet to change it.")


def approve(case: dict, sid: str, reviewer: str) -> None:
    _open(case)
    s = _sentence(case, sid)
    if s["status"] == "red":
        raise ValueError("A blocked sentence must be edited or removed, not approved as is.")
    s["review"] = {"state": "approved", "by": reviewer, "at": time.time()}
    s["needs_review"] = False
    audit(case, reviewer, f"approved {sid}")


def edit(case: dict, sid: str, reviewer: str, text_en: str | None, text_tl: str | None,
         fact_ids: list[str] | None = None) -> None:
    _open(case)
    s = _sentence(case, sid)
    before = {"text_en": s["text_en"], "text_tl": s.get("text_tl")}
    translated = case["language"] != "en" and case["route"] != "interpreter"
    new_en = spell_dates(text_en.strip()) if text_en is not None else s["text_en"]
    new_tl = text_tl.strip() if text_tl is not None and translated else s.get("text_tl")
    en_changed, tl_changed = new_en != s["text_en"], new_tl != s.get("text_tl")
    if not (en_changed or tl_changed or (fact_ids is not None and fact_ids != s["fact_ids"])):
        raise ValueError("Nothing was changed. Edit the wording, remove the sentence, or approve it if it is right.")
    s["text_en"], s["text_tl"] = new_en, new_tl
    if translated:
        # The old back-translation and verdict describe the old wording; reverify() redoes them.
        s["back_en"] = ""
        if en_changed and not tl_changed:
            s["tl_stale"] = True  # the patient would still read the old meaning
        elif tl_changed:
            s["tl_stale"] = False
    if fact_ids is not None:
        s["fact_ids"] = fact_ids
    s["judge_en"] = None
    s["review"] = {"state": "edited", "by": reviewer, "at": time.time(), "before": before}
    recheck(case)
    audit(case, reviewer, f"edited {sid}",
          f"{before['text_en']} -> {s['text_en']}" + (f" | {before['text_tl']} -> {s['text_tl']}" if tl_changed else ""))


async def reverify(case: dict, client, sid: str) -> None:
    """Back-translate and judge a reviewer's new wording, like the model's own."""
    s = _sentence(case, sid)
    lang = case["language"]
    try:
        if lang in LANGUAGES and lang != "en" and s.get("text_tl") and not s.get("tl_stale"):
            out = await client.complete_json(
                "back_translate", f"{lang}:edit:{sid}",
                prompts.back_translate_messages([{"id": sid, "text": s["text_tl"]}], LANGUAGES[lang]),
                prompts.TRANSLATION_SCHEMA, case["usage"], case.get("sample_id"))
            s["back_en"] = _by_id(out, "items", "text").get(sid, "")
        by_id = {f["id"]: f for f in case["facts"]}
        row = {"id": sid, "sentence": s["text_en"], "facts": [by_id[i]["detail"] for i in s["fact_ids"] if i in by_id]}
        if s.get("text_tl"):
            row["translation"] = s["text_tl"]
        if s.get("back_en"):
            row["back_translation"] = s["back_en"]
        out = await client.complete_json("judge", f"{lang}:edit:{sid}", prompts.judge_messages([row]),
                                         prompts.JUDGE_SCHEMA, case["usage"], case.get("sample_id"))
        s["judge_en"] = next((v for v in out.get("verdicts") or [] if isinstance(v, dict)), None)
    except LLMError:
        pass  # no model: the edit stays flagged as not machine-checked, and in review
    recheck(case)


def remove(case: dict, sid: str, reviewer: str) -> None:
    _open(case)
    s = _sentence(case, sid)
    s["removed"] = True
    recheck(case)
    audit(case, reviewer, f"removed {sid}")


def _fact(case: dict, fact_id: str) -> dict:
    for f in case["facts"]:
        if f["id"] == fact_id:
            return f
    raise ValueError(f"There is no fact {fact_id} in this packet.")


def add_sentence(case: dict, reviewer: str, fact_id: str, text_en: str, text_tl: str | None) -> dict:
    _open(case)
    fact = _fact(case, fact_id)
    text_en = spell_dates(text_en)
    section = {"medication": "medicines", "warning_sign": "warning_signs",
               "follow_up": "appointments"}.get(fact["kind"], "daily_care")
    n = 1 + max((int(s["id"][1:]) for s in case["sentences"] if s["id"][1:].isdigit()), default=0)
    s = {"id": f"S{n}", "section": section, "text_en": text_en.strip(), "fact_ids": [fact_id],
         "review": {"state": "edited", "by": reviewer, "at": time.time(), "before": None}}
    if case["language"] != "en":
        s["text_tl"] = (text_tl or "").strip()
        s["back_en"] = ""
    case["sentences"].append(s)
    recheck(case)
    audit(case, reviewer, f"added {s['id']} for {fact_id}", text_en)
    return s


def dismiss_fact(case: dict, fact_id: str, reviewer: str, reason: str) -> None:
    _open(case)
    f = _fact(case, fact_id)
    if f.get("risk") == "high" and f.get("status") != "red" and f.get("origin") != "rule":
        raise ValueError(f"{fact_id} is a high-risk instruction in the clinician's text, so it cannot be dismissed. "
                         "Cover it in the packet, or ask the clinician to correct the discharge text.")
    if len((reason or "").strip()) < 8:
        raise ValueError("Say in a few words why the patient does not need this.")
    f["dismissed"] = reason.strip()
    recheck(case)
    audit(case, reviewer, f"dismissed {fact_id}", reason)


def resolve_med_issue(case: dict, drug: str, reviewer: str, reason: str) -> None:
    _open(case)
    issues = [m for m in case["med_issues"] if m["drug"] == drug]
    if not issues:
        raise ValueError(f"There is no medicine check for {drug or 'that medicine'}.")
    if len((reason or "").strip()) < 8:
        raise ValueError("Say in a few words what you checked against the source.")
    for m in issues:
        m["resolved"] = reason.strip()
    audit(case, reviewer, f"resolved medicine check for {drug}", reason)


def sign_off(case: dict, reviewer: str) -> None:
    _open(case)
    open_items = blockers(case)
    if open_items:
        raise ValueError("Cannot sign off yet: " + " ".join(open_items[:5]))
    if not reviewer.strip():
        raise ValueError("A named reviewer is required.")
    case["signoff"] = {"by": reviewer, "at": time.time()}
    case["quiz"] = quiz.build_quiz(case)
    audit(case, reviewer, "signed off packet")


def answer(case: dict, qid: str, choice: int) -> dict:
    q = next(q for q in case["quiz"] if q["id"] == qid)
    if not 0 <= choice < len(q["options"]):
        raise IndexError(choice)
    if q["answer"]:  # the first answer is the teach-back result; the nurse follows up on it
        return {"correct": q["answer"]["correct"], "already_answered": True}
    correct = bool(q["options"][choice]["correct"])
    q["answer"] = {"choice": choice, "correct": correct, "at": time.time()}
    if not correct:
        fact = next(f for f in case["facts"] if f["id"] == q["fact_id"])
        case["alerts"].append({"at": time.time(), "question": qid, "fact_id": fact["id"],
                               "message": f"Re-explain: {fact['detail']}"})
        audit(case, "patient", f"missed {qid}", fact["detail"])
    else:
        audit(case, "patient", f"answered {qid} correctly")
    return {"correct": correct}


def _sentence(case: dict, sid: str) -> dict:
    for s in case["sentences"]:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


# ------------------------------------------------------------- metrics

def metrics(case: dict) -> dict:
    live = [s for s in case["sentences"] if not s.get("removed")]
    english = " ".join(s["text_en"] for s in live)
    checks = [c for s in live for c in s.get("checks", [])] + \
             [c for f in case["facts"] for c in f.get("checks", [])]
    caught: dict[str, int] = {}
    for c in checks:
        if c["status"] != "pass":
            caught[c["name"]] = caught.get(c["name"], 0) + 1
    usage = case["usage"].summary()
    flagged = [s for s in live if s.get("status") != "green" or s.get("risk") == "high"]
    signoff_secs = (case["signoff"]["at"] - case["created_at"]) if case.get("signoff") else None
    return {
        "source_grade": fk_grade(case["source_masked"]),
        "output_grade": fk_grade(english) if english else None,
        "source_words": word_count(case["source_masked"]),
        "output_words": word_count(english),
        "sentences": len(live),
        "sentences_flagged": len(flagged),
        "by_status": {k: sum(1 for s in live if s.get("status") == k) for k in ("green", "amber", "red")},
        "high_risk": sum(1 for s in live if s.get("risk") == "high"),
        "checks_run": len(checks),
        "issues_caught": caught,
        "omissions": len(case["omissions"]),
        "facts": len(case["facts"]),
        "med_issues": len(case["med_issues"]),
        "phi_masked": case["phi_counts"],
        "model": usage,
        "gpu_cost_usd": round(usage["seconds"] * GPU_DOLLARS_PER_HOUR / 3600, 4) if usage["seconds"] else None,
        "seconds_to_signoff": round(signoff_secs, 1) if signoff_secs else None,
        "at_draft": case.get("at_draft"),
    }


def public(case: dict) -> dict:
    """Case as sent to the browser: no mask map, no raw source."""
    out = {k: v for k, v in case.items() if not k.startswith("_") and k not in ("usage", "patient_token")}
    if case.get("signoff") and case.get("patient_token"):
        out["patient_link"] = f"/p/{case['patient_token']}"
    # Staff see answers once given, never the key.
    out["quiz"] = [q | {"options": [{"text": o["text"]} for o in q["options"]]} for q in case["quiz"]]
    out["metrics"] = metrics(case)
    out["blockers"] = blockers(case) if case["stage"] == "ready" else []
    return out


def packet(case: dict) -> dict:
    """Signed-off patient packet with masked details restored."""
    if not case.get("signoff"):
        raise ValueError("Packet is not signed off.")
    m = case["_mask"]
    facts = {f["id"]: f for f in case["facts"]}
    sections = {}
    for s in case["sentences"]:
        if s.get("removed"):
            continue
        # Lets the patient view group medicines by what changed (new, stop, keep...).
        action = next((facts[i]["med_action"] for i in s.get("fact_ids", [])
                       if facts.get(i, {}).get("med_action")), None)
        sections.setdefault(s["section"], []).append({
            "id": s["id"], "text_en": m.unmask(s["text_en"]),
            "text_tl": m.unmask(s.get("text_tl") or "") or None,
            "risk": s.get("risk"), "med_action": action,
        })
    return {"language": case["language"], "language_name": case["language_name"],
            "sections": sections, "signoff": case["signoff"],
            "quiz": [{k: v for k, v in q.items() if k != "options"} |
                     {"options": [{"text": m.unmask(o["text"])} for o in q["options"]]}
                     for q in case["quiz"]],
            "route": case["route"]}


async def suggest(case: dict, client, fact_id: str) -> dict:
    """Model-drafted wording for a missing fact. The reviewer still decides."""
    fact = next(f for f in case["facts"] if f["id"] == fact_id)
    lang = case["language"] if case["language"] != "en" else None
    key = f"{case['language']}:{fact_id}"
    out = await client.complete_json("suggest", key, prompts.suggest_messages(fact, LANGUAGES.get(lang) if lang else None),
                                     prompts.SUGGEST_SCHEMA, case["usage"], case.get("sample_id"))
    return {"fact_id": fact_id, "text_en": out["text_en"], "text_tl": out.get("text_tl")}
