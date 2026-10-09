"""Prompts and JSON schemas for each model stage."""

import json

FACT_KINDS = ["medication", "follow_up", "warning_sign", "activity", "diet",
              "wound_care", "pending_result", "diagnosis", "other"]
MED_ACTIONS = ["new", "changed", "stop", "hold", "continue"]

FACTS_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                # The quote comes before the labels: with constrained decoding the model
                # writes fields in this order, so it reads the text before it labels it.
                "properties": {
                    "id": {"type": "string"},
                    "source_quote": {"type": "string"},
                    "kind": {"type": "string", "enum": FACT_KINDS},
                    "med_action": {"type": ["string", "null"], "enum": MED_ACTIONS + [None]},
                    "drug": {"type": ["string", "null"]},
                    "dose": {"type": ["string", "null"]},
                    "frequency": {"type": ["string", "null"]},
                    "detail": {"type": "string"},
                },
                "required": ["id", "source_quote", "kind", "med_action", "drug", "dose", "frequency",
                             "detail"],
            },
        }
    },
    "required": ["facts"],
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "section": {"type": "string", "enum": [
                        "why", "medicines", "warning_signs", "appointments", "daily_care"]},
                    "text": {"type": "string"},
                    "fact_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "section", "text", "fact_ids"],
            },
        }
    },
    "required": ["sentences"],
}

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                "required": ["id", "text"],
            },
        }
    },
    "required": ["items"],
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "verdict": {"type": "string", "enum": [
                        "supported", "partially_supported", "unsupported", "contradicts"]},
                    "reason": {"type": "string"},
                },
                "required": ["id", "verdict", "reason"],
            },
        }
    },
    "required": ["verdicts"],
}

SYSTEM = (
    "You work inside Homeward, a tool that helps hospital staff explain discharge "
    "instructions to patients. You never diagnose, never recommend treatment and never add "
    "medical content that is not in the clinician's text. Placeholders in square brackets "
    "such as [PATIENT_1] or [CLINICIAN_1] stand for masked personal details: copy them "
    "exactly and never guess what they hide. Reply with JSON only."
)


def facts_messages(source: str) -> list[dict]:
    user = f"""Extract every instruction the patient must know from the discharge text below as atomic facts.

Rules:
- source_quote: copy the exact words from the text, including any label such as "NEW:" or "STOP:".
- kind: medication (any medicine line), warning_sign (when to call or go to hospital), follow_up (appointments, tests, classes), activity, diet, wound_care, pending_result, diagnosis (only why the patient was in hospital), other.
- One fact per medicine. med_action is: new (started in hospital), changed (dose or timing changed), stop (stop permanently), hold (pause until told to restart), continue (unchanged). Use null for non-medicine facts.
- Copy drug, dose and frequency exactly as written. Use null when the text does not say.
- One fact per warning sign or group of signs that share the same action, one per appointment or pending test, one per activity, diet, monitoring or wound-care rule. Every instruction line must appear in some fact.
- detail: one short plain-English sentence stating the fact, including what to do.
- ids: F1, F2, ... in order of appearance.
- Do not infer anything that is not written.

Example. Text:
STOP: Ibuprofen - do not take while on apixaban.
Fluid restriction 1.5 L/day.
Call 911 for chest pain.
Facts:
{{"facts": [
 {{"id": "F1", "source_quote": "STOP: Ibuprofen - do not take while on apixaban.", "kind": "medication", "med_action": "stop", "drug": "Ibuprofen", "dose": null, "frequency": null, "detail": "Stop taking ibuprofen while you take apixaban."}},
 {{"id": "F2", "source_quote": "Fluid restriction 1.5 L/day.", "kind": "diet", "med_action": null, "drug": null, "dose": null, "frequency": null, "detail": "Drink no more than 1.5 litres of fluid a day."}},
 {{"id": "F3", "source_quote": "Call 911 for chest pain.", "kind": "warning_sign", "med_action": null, "drug": null, "dose": null, "frequency": null, "detail": "Call 911 if you have chest pain."}}]}}

Discharge text:
<<<
{source}
>>>"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def draft_messages(facts: list[dict], grade: int = 6) -> list[dict]:
    compact = [{k: f[k] for k in ("id", "kind", "med_action", "drug", "dose", "frequency", "detail")}
               for f in facts]
    user = f"""Write discharge instructions for the patient using only these facts.

Rules:
- Reading level: grade {grade} or lower. Short sentences (under 15 words). Everyday words. Talk to the patient as "you".
- Every sentence must list the fact ids it restates in fact_ids. Never write a sentence without a fact behind it.
- Cover every fact in the list, including every medicine, warning sign and appointment. For each medicine say its name, the dose and how often, and clearly whether to start, change, keep taking, stop, or pause it.
- A "hold" means pause until a clinician says to restart; say that, do not say stop forever.
- Keep drug names, numbers and placeholders exactly as given.
- Sections: why, medicines, warning_signs, appointments, daily_care. ids: S1, S2, ...

Facts:
{json.dumps(compact, ensure_ascii=False, indent=1)}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def translate_messages(sentences: list[dict], language: str) -> list[dict]:
    items = [{"id": s["id"], "text": s.get("text_en") or s.get("text")} for s in sentences]
    user = f"""Translate each sentence into {language} for a patient with no medical training.

Rules:
- Plain, warm, everyday {language}. Keep the meaning exactly; add and drop nothing.
- Keep drug names, all numbers (as digits) and placeholders like [CLINICIAN_1] exactly as written.
- Keep stop / do not take / pause / keep taking unmistakable.
- Return the same ids.

Sentences:
{json.dumps(items, ensure_ascii=False, indent=1)}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def back_translate_messages(items: list[dict], language: str) -> list[dict]:
    user = f"""Translate each {language} sentence into English as literally as possible, so a checker can compare meaning. Do not fix or improve anything. Keep numbers as digits, drug names and placeholders exactly. Return the same ids.

Sentences:
{json.dumps(items, ensure_ascii=False, indent=1)}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def judge_messages(rows: list[dict]) -> list[dict]:
    user = f"""You are a strict clinical safety checker. For each patient sentence, decide whether it is supported by the cited source facts.

- supported: says the same thing as the facts, nothing added.
- partially_supported: right direction, but loses or blurs something that matters (dose, timing, temporary vs permanent, who to call).
- unsupported: adds information that is not in the facts.
- contradicts: says something opposite to the facts.

If "back_translation" is present, judge that text too: the sentence is only supported if the back-translation also matches. Give a reason of at most 20 words.

Rows:
{json.dumps(rows, ensure_ascii=False, indent=1)}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {"text_en": {"type": "string"}, "text_tl": {"type": ["string", "null"]}},
    "required": ["text_en", "text_tl"],
}


def suggest_messages(fact: dict, language: str | None) -> list[dict]:
    target = (f"Then translate it into plain {language} as text_tl, keeping drug names, "
              "numbers as digits and placeholders exactly.") if language else "Set text_tl to null."
    user = f"""A reviewer found that this fact is missing from a patient's discharge instructions. Write one sentence for the patient that states it, at grade 6 or lower, as text_en. Use only this fact; add nothing. {target}

Fact:
{json.dumps({k: fact.get(k) for k in ("kind", "med_action", "drug", "dose", "frequency", "detail")}, ensure_ascii=False)}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
