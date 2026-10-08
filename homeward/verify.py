"""Deterministic verification of facts and patient sentences.

Every check returns {"name", "status": pass|warn|fail, "message"}. Messages are
written for the nurse or reviewer reading them, not for engineers.
"""

import re

from . import lexicon
from .phi import placeholders_in
from .textutil import digits_in, numbers_in, quote_in_source

CRITICAL_KINDS = ("medication", "warning_sign", "follow_up")
EMERGENCY_NUMBERS = {"911", "999", "112", "000", "111"}
DATE_OR_TIME = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{1,2}:\d{2}\b")
ACTION_WORDS = {
    "stop": ["stop", "discontinue", "discontinued", "do not resume", "no longer take"],
    "hold": ["hold", "pause", "do not take until", "until told", "until your"],
    "new": ["new", "start", "begin", "started"],
    "changed": ["changed", "increase", "increased", "decrease", "decreased", "reduce",
                "reduced", "change", "now take"],
    "continue": ["continue", "resume", "keep taking", "unchanged", "no change"],
}


def check(name: str, status: str, message: str = "") -> dict:
    return {"name": name, "status": status, "message": message}


def status_of(checks: list[dict]) -> str:
    states = {c["status"] for c in checks}
    return "red" if "fail" in states else "amber" if "warn" in states else "green"


# ---------------------------------------------------------------- facts

def fact_numbers(fact: dict) -> set[str]:
    text = " ".join(str(fact.get(k) or "") for k in ("dose", "frequency", "detail", "source_quote"))
    return numbers_in(text)


def fact_drugs(fact: dict) -> set[str]:
    found = set()
    canon = lexicon.canonical_drug(fact.get("drug"))
    if canon:
        found.add(canon)
    found |= lexicon.drugs_in(fact.get("source_quote") or "")
    found |= lexicon.drugs_in(fact.get("detail") or "")
    return found


def fact_risk(fact: dict) -> str:
    if fact.get("kind") == "warning_sign":
        return "high"
    if fact.get("kind") == "medication":
        if fact.get("med_action") in ("stop", "hold", "changed"):
            return "high"
        if lexicon.is_high_alert(fact.get("drug")):
            return "high"
    return "normal"


def verify_facts(facts: list[dict], source: str) -> None:
    for f in facts:
        checks = []
        quote = f.get("source_quote") or ""
        if quote_in_source(quote, source):
            checks.append(check("quote", "pass"))
        else:
            checks.append(check("quote", "fail", "Could not find this in the clinician's text."))
        claimed = numbers_in(" ".join(str(f.get(k) or "") for k in ("dose", "frequency")))
        missing = claimed - numbers_in(quote)
        if missing:
            checks.append(check("numbers", "fail",
                                f"Number {', '.join(sorted(missing))} is not in the quoted source."))
        if f.get("kind") == "medication":
            canon = lexicon.canonical_drug(f.get("drug"))
            if canon and canon not in lexicon.drugs_in(quote):
                checks.append(check("drug", "warn", f"{f.get('drug')} is not named in the quote."))
            if not f.get("med_action"):
                checks.append(check("action", "warn", "Unclear whether to start, change, keep or stop."))
        f["risk"] = fact_risk(f)
        f["checks"] = checks
        f["status"] = status_of(checks)


def parse_med_lines(source: str) -> list[dict]:
    """Rule-based medicine list, used only to cross-check the model's facts."""
    meds, context = [], None
    for raw in source.splitlines():
        line = raw.strip()
        if not line:
            context = None
            continue
        lowered = line.lower()
        action = None
        for name, words in ACTION_WORDS.items():
            if any(re.search(rf"\b{re.escape(w)}\b", lowered) for w in words):
                action = name
                break
        drugs = lexicon.drugs_in(line)
        if not drugs:
            if action and line.endswith(":"):
                context = action
            continue
        for d in drugs:
            meds.append({"drug": d, "action": action or context, "line": line})
    return meds


def cross_check_meds(facts: list[dict], source: str) -> list[dict]:
    """Compare the model's medicine facts with the rule-based parse."""
    issues = []
    med_facts = [f for f in facts if f.get("kind") == "medication"]
    by_drug: dict[str, list[dict]] = {}
    for f in med_facts:
        canon = lexicon.canonical_drug(f.get("drug"))
        if canon:
            by_drug.setdefault(canon, []).append(f)
    any_fact_drugs = set()
    for f in facts:
        any_fact_drugs |= fact_drugs(f)
    parsed: dict[str, dict] = {}
    for med in parse_med_lines(source):
        entry = parsed.setdefault(med["drug"], {"actions": set(), "line": med["line"]})
        if med["action"]:
            if not entry["actions"]:
                entry["line"] = med["line"]
            entry["actions"].add(med["action"])
    for d, entry in parsed.items():
        if d not in any_fact_drugs:
            issues.append({"type": "missing_fact", "drug": d, "line": entry["line"],
                           "message": f"{d.title()} is in the clinician's text but the model did not list it."})
            continue
        if not entry["actions"] or d not in by_drug:
            continue
        model_actions = {f.get("med_action") for f in by_drug[d]}
        if not model_actions & entry["actions"]:
            text_actions = "/".join(sorted(entry["actions"]))
            for f in by_drug[d]:
                f["checks"].append(check(
                    "cross_check", "warn",
                    f"Text reads as '{text_actions}', model says '{f.get('med_action')}'."))
                f["status"] = status_of(f["checks"])
            issues.append({"type": "action_mismatch", "drug": d, "line": entry["line"],
                           "message": f"{d.title()}: text reads as '{text_actions}', model says "
                                      f"'{'/'.join(sorted(a or '?' for a in model_actions))}'."})
    return issues


# ------------------------------------------------------------ sentences

def _clause_for(text: str, drug: str) -> str:
    parts = re.split(r"[.;]|\bbut\b|\band\b", text)
    for p in parts:
        if drug in lexicon.drugs_in(p):
            return p
    return text


def _med_polarities(text: str, med_facts: list[dict]):
    """Yield (fact, short name, polarity of the clause about that medicine)."""
    mentioned = lexicon.drugs_in(text)
    for f in med_facts:
        drug = lexicon.canonical_drug(f.get("drug"))
        if not f.get("med_action") or not drug:
            continue
        if drug not in mentioned and len(med_facts) > 1:
            continue
        clause = _clause_for(text, drug) if drug in mentioned else text
        yield f, (f.get("drug") or drug).split()[0], lexicon.polarity(clause)


def polarity_checks(text: str, med_facts: list[dict]) -> list[dict]:
    """Does the sentence contradict what the source says to do with a medicine?"""
    out = []
    for f, name, pol in _med_polarities(text, med_facts):
        action = f["med_action"]
        if action in ("stop", "hold"):
            if pol["continue"] and not pol["stop"]:
                out.append(check("meaning_polarity", "fail",
                                 f"Source says {'stop' if action == 'stop' else 'pause'} {name}; this reads as keep taking it."))
            elif action == "hold" and pol["stop"] and not pol["temporary"]:
                out.append(check("meaning_polarity", "warn",
                                 f"Source says pause {name} until told to restart; this may read as stopping for good."))
        elif action == "continue" and pol["stop"]:
            out.append(check("meaning_polarity", "fail", f"Source says keep taking {name}; this reads as stop."))
        elif action in ("new", "changed") and pol["stop"] and not pol["continue"]:
            out.append(check("meaning_polarity", "warn",
                             f"Source says take {name}; this sentence contains a stop instruction."))
    return out


def translation_polarity(text_en: str, back_en: str, med_facts: list[dict]) -> list[dict]:
    """Did translation flip stop/keep for any medicine (the 'hold' -> 'keep taking' failure)?"""
    out = []
    before = {f["id"]: p for f, _, p in _med_polarities(text_en, med_facts)}
    for f, name, after in _med_polarities(back_en, med_facts):
        b = before.get(f["id"])
        if not b:
            continue
        if b["stop"] != after["stop"] or b["continue"] != after["continue"]:
            out.append(check("translation_polarity", "fail",
                             f"Translation changes what to do with {name} (stop vs keep taking)."))
        elif b["temporary"] and not after["temporary"] and f["med_action"] == "hold":
            out.append(check("translation_polarity", "warn",
                             f"Translation drops 'until' for {name}; may read as stopping for good."))
    return out


def clearly_instructs(f: dict, sentences: list[dict]) -> bool:
    """For stop/hold facts: does some sentence clearly say to stop or pause?"""
    for s in sentences:
        for _, _, pol in _med_polarities(s.get("text_en") or "", [f]):
            if pol["stop"] and not pol["continue"]:
                return True
    return False


def verify_sentence(s: dict, facts_by_id: dict[str, dict], all_facts: list[dict],
                    target_lang: str) -> None:
    checks = []
    text = s.get("text_en") or ""
    cited = [facts_by_id[i] for i in s.get("fact_ids", []) if i in facts_by_id]
    unknown = [i for i in s.get("fact_ids", []) if i not in facts_by_id]

    if not s.get("fact_ids"):
        checks.append(check("citation", "fail", "No source fact behind this sentence."))
    elif unknown:
        checks.append(check("citation", "fail", f"Cites facts that do not exist: {', '.join(unknown)}."))
    else:
        checks.append(check("citation", "pass"))

    allowed_numbers = set().union(*[fact_numbers(f) for f in cited]) if cited else set()
    extra = numbers_in(text) - allowed_numbers - {"1"}
    checks.append(check("numbers", "fail", f"Number {', '.join(sorted(extra))} is not in the cited source.")
                  if extra else check("numbers", "pass"))

    allowed_drugs = set().union(*[fact_drugs(f) for f in cited]) if cited else set()
    every_drug = set().union(*[fact_drugs(f) for f in all_facts]) if all_facts else set()
    named = lexicon.drugs_in(text)
    cited_meds = {lexicon.canonical_drug(f.get("drug")) for f in cited if f.get("kind") == "medication"} - {None}
    for d in sorted(named - allowed_drugs):
        if d not in every_drug:
            checks.append(check("drug", "fail", f"{d.title()} is not in the clinician's text."))
        elif cited_meds and not (cited_meds & named):
            checks.append(check("drug", "fail", f"Names {d}, but the cited instruction is about "
                                                f"{', '.join(sorted(cited_meds))}."))
        else:
            checks.append(check("drug", "warn", f"Mentions {d} but cites a different fact."))

    med_facts = [f for f in cited if f.get("kind") == "medication"]
    checks += polarity_checks(text, med_facts)

    allowed_ph = set().union(*[placeholders_in((f.get("detail") or "") + " " + (f.get("source_quote") or ""))
                               for f in cited]) if cited else set()
    invented = placeholders_in(text) - allowed_ph
    if invented:
        checks.append(check("placeholder", "fail", f"Refers to {', '.join(sorted(invented))}, not in the cited source."))

    if target_lang != "en":
        tl, back = s.get("text_tl") or "", s.get("back_en") or ""
        if not tl:
            checks.append(check("translation", "fail", "Translation is missing."))
        else:
            if digits_in(tl) != digits_in(text):
                checks.append(check("translation_numbers", "fail",
                                    f"Numbers differ after translation: {_fmt(digits_in(text))} vs {_fmt(digits_in(tl))}."))
            if placeholders_in(tl) != placeholders_in(text):
                checks.append(check("translation_placeholder", "fail", "A name or contact detail was lost in translation."))
        if back:
            if numbers_in(back) - {"1"} != numbers_in(text) - {"1"}:
                checks.append(check("back_numbers", "fail",
                                    f"Back-translation numbers differ: {_fmt(numbers_in(text))} vs {_fmt(numbers_in(back))}."))
            lost = lexicon.drugs_in(text) - lexicon.drugs_in(back)
            if lost:
                checks.append(check("back_drug", "fail", f"{', '.join(sorted(lost))} lost in translation."))
            checks += translation_polarity(text, back, med_facts)
        elif tl:
            checks.append(check("back_translation", "warn", "Could not back-translate to check meaning."))

    for key, label in (("judge_en", "model_check"), ("judge_back", "model_check_translation")):
        j = s.get(key)
        if not j:
            continue
        v = j.get("verdict")
        if v in ("unsupported", "contradicts"):
            checks.append(check(label, "fail", f"Safety model: {v.replace('_', ' ')}. {j.get('reason', '')}".strip()))
        elif v == "partially_supported":
            checks.append(check(label, "warn", f"Safety model: partly supported. {j.get('reason', '')}".strip()))
        else:
            checks.append(check(label, "pass"))

    s["checks"] = checks
    s["status"] = status_of(checks)
    s["risk"] = "high" if any(f.get("risk") == "high" for f in cited) else "normal"
    s["needs_review"] = s["status"] != "green" or s["risk"] == "high"


def _fmt(nums: set[str]) -> str:
    return "{" + ", ".join(sorted(nums)) + "}" if nums else "none"


def coverage(facts: list[dict], sentences: list[dict]) -> list[dict]:
    """Critical facts that no sentence restates. Each one blocks release."""
    omissions = []
    for f in facts:
        if f.get("kind") not in CRITICAL_KINDS or f.get("dismissed"):
            continue
        citing = [s for s in sentences if f["id"] in s.get("fact_ids", []) and not s.get("removed")]
        if not citing:
            omissions.append({"fact_id": f["id"], "kind": f["kind"],
                              "message": f"Not explained to the patient: {f.get('detail')}"})
            continue
        said = set().union(*[numbers_in(s.get("text_en") or "") for s in citing])
        said_ph = set().union(*[placeholders_in(s.get("text_en") or "") for s in citing])
        quote = f.get("source_quote") or ""
        if f["kind"] == "medication" and f.get("med_action") in ("new", "changed", "continue"):
            lost = numbers_in(f.get("dose") or "", words=False) - said
            if lost:
                omissions.append({"fact_id": f["id"], "kind": f["kind"],
                                  "message": f"The dose of {f.get('drug')} ({f.get('dose')}) is never stated."})
        elif f["kind"] == "follow_up":
            lost = DATE_OR_TIME.findall(quote)
            lost = [d for d in lost if not numbers_in(d, words=False) <= said]
            if lost:
                omissions.append({"fact_id": f["id"], "kind": f["kind"],
                                  "message": f"Appointment date or time ({', '.join(lost)}) is never stated."})
        elif f["kind"] == "warning_sign":
            lost = sorted((numbers_in(quote, words=False) & EMERGENCY_NUMBERS) - said)
            lost += sorted(placeholders_in(quote) - said_ph)
            if lost:
                omissions.append({"fact_id": f["id"], "kind": f["kind"],
                                  "message": f"Who to call ({', '.join(lost)}) is never stated."})
        canon = lexicon.canonical_drug(f.get("drug"))
        if f.get("kind") == "medication" and canon:
            naming = [s for s in citing if canon in lexicon.drugs_in(s.get("text_en") or "")]
            if not naming:
                omissions.append({"fact_id": f["id"], "kind": f["kind"],
                                  "message": f"{f.get('drug')} is cited but never named for the patient."})
            elif f.get("med_action") in ("stop", "hold") and not clearly_instructs(f, naming):
                verb = "stop" if f["med_action"] == "stop" else "pause"
                omissions.append({"fact_id": f["id"], "kind": f["kind"],
                                  "message": f"No sentence clearly tells the patient to {verb} {f.get('drug')}."})
    return omissions
