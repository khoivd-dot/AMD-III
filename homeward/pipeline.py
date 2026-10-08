"""Discharge packet pipeline: mask, extract, draft, translate, check, review."""

import time
import uuid

from . import prompts, quiz
from .lexicon import LANGUAGES
from .llm import LLMError, Usage
from .phi import mask
from .textutil import fk_grade, word_count
from .verify import coverage, cross_check_meds, verify_facts, verify_sentence

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
        facts = out["facts"]
        verify_facts(facts, case["source_masked"])
        case["facts"] = facts
        case["med_issues"] = cross_check_meds(facts, case["source_masked"])

        case["stage"] = "draft"
        out = await client.complete_json("draft", "en", prompts.draft_messages(facts),
                                         prompts.DRAFT_SCHEMA, usage, cid)
        sentences = [{"id": s["id"], "section": s["section"], "text_en": s["text"],
                      "fact_ids": s.get("fact_ids", []), "review": None}
                     for s in out["sentences"]]
        case["sentences"] = sentences

        if case["language"] not in LANGUAGES:
            case["route"] = "interpreter"
        elif case["language"] != "en":
            name = LANGUAGES[case["language"]]
            case["stage"] = "translate"
            out = await client.complete_json("translate", key, prompts.translate_messages(sentences, name),
                                             prompts.TRANSLATION_SCHEMA, usage, cid)
            tl = {i["id"]: i["text"] for i in out["items"]}
            for s in sentences:
                s["text_tl"] = tl.get(s["id"], "")
            case["stage"] = "back_translate"
            items = [{"id": s["id"], "text": s["text_tl"]} for s in sentences if s["text_tl"]]
            out = await client.complete_json("back_translate", key,
                                             prompts.back_translate_messages(items, name),
                                             prompts.TRANSLATION_SCHEMA, usage, cid)
            back = {i["id"]: i["text"] for i in out["items"]}
            for s in sentences:
                s["back_en"] = back.get(s["id"], "")

        case["stage"] = "judge"
        by_id = {f["id"]: f for f in facts}
        rows = []
        for s in sentences:
            row = {"id": s["id"], "sentence": s["text_en"],
                   "facts": [by_id[i]["detail"] for i in s["fact_ids"] if i in by_id]}
            if s.get("back_en"):
                row["back_translation"] = s["back_en"]
            rows.append(row)
        out = await client.complete_json("judge", key, prompts.judge_messages(rows),
                                         prompts.JUDGE_SCHEMA, usage, cid)
        verdicts = {v["id"]: v for v in out["verdicts"]}
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
    except (LLMError, KeyError, TypeError, ValueError) as exc:
        case["stage"] = "error"
        case["error"] = str(exc)
        audit(case, "system", "pipeline error", str(exc))
    return case


def recheck(case: dict) -> None:
    by_id = {f["id"]: f for f in case["facts"]}
    live = [s for s in case["sentences"] if not s.get("removed")]
    for s in live:
        verify_sentence(s, by_id, case["facts"], case["language"])
        if s.get("review") and s["review"]["state"] in ("approved", "edited"):
            # A human has accepted this exact wording; keep the checks visible but
            # do not ask again unless a check hard-fails on the edited text.
            if s["status"] != "red" or s["review"]["state"] == "approved":
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
        if m["type"] == "missing_fact" and not m.get("resolved"):
            out.append(m["message"])
    return out


# ------------------------------------------------------------- review

def approve(case: dict, sid: str, reviewer: str) -> None:
    s = _sentence(case, sid)
    if s["status"] == "red":
        raise ValueError("A blocked sentence must be edited or removed, not approved as is.")
    s["review"] = {"state": "approved", "by": reviewer, "at": time.time()}
    s["needs_review"] = False
    audit(case, reviewer, f"approved {sid}")


def edit(case: dict, sid: str, reviewer: str, text_en: str | None, text_tl: str | None,
         fact_ids: list[str] | None = None) -> None:
    s = _sentence(case, sid)
    before = {"text_en": s["text_en"], "text_tl": s.get("text_tl")}
    if text_en is not None:
        s["text_en"] = text_en.strip()
    if text_tl is not None:
        s["text_tl"] = text_tl.strip()
        # The reviewer's own wording replaces the model's back-translation.
        s["back_en"] = ""
    if fact_ids is not None:
        s["fact_ids"] = fact_ids
    s["judge_en"] = None
    s["review"] = {"state": "edited", "by": reviewer, "at": time.time(), "before": before}
    recheck(case)
    if s["status"] == "red":
        s["needs_review"] = True
    else:
        s["needs_review"] = False
    audit(case, reviewer, f"edited {sid}", f"{before['text_en']} -> {s['text_en']}")


def remove(case: dict, sid: str, reviewer: str) -> None:
    s = _sentence(case, sid)
    s["removed"] = True
    recheck(case)
    audit(case, reviewer, f"removed {sid}")


def add_sentence(case: dict, reviewer: str, fact_id: str, text_en: str, text_tl: str | None) -> dict:
    fact = next(f for f in case["facts"] if f["id"] == fact_id)
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
    s["needs_review"] = s["status"] == "red"
    audit(case, reviewer, f"added {s['id']} for {fact_id}", text_en)
    return s


def dismiss_fact(case: dict, fact_id: str, reviewer: str, reason: str) -> None:
    f = next(f for f in case["facts"] if f["id"] == fact_id)
    f["dismissed"] = reason
    recheck(case)
    audit(case, reviewer, f"dismissed {fact_id}", reason)


def resolve_med_issue(case: dict, drug: str, reviewer: str, reason: str) -> None:
    for m in case["med_issues"]:
        if m["drug"] == drug:
            m["resolved"] = reason
    audit(case, reviewer, f"resolved medicine check for {drug}", reason)


def sign_off(case: dict, reviewer: str) -> None:
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
    out = {k: v for k, v in case.items() if not k.startswith("_") and k != "usage"}
    out["metrics"] = metrics(case)
    out["blockers"] = blockers(case) if case["stage"] == "ready" else []
    return out


def packet(case: dict) -> dict:
    """Signed-off patient packet with masked details restored."""
    if not case.get("signoff"):
        raise ValueError("Packet is not signed off.")
    m = case["_mask"]
    sections = {}
    for s in case["sentences"]:
        if s.get("removed"):
            continue
        sections.setdefault(s["section"], []).append({
            "id": s["id"], "text_en": m.unmask(s["text_en"]),
            "text_tl": m.unmask(s.get("text_tl") or "") or None,
            "risk": s.get("risk"),
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
