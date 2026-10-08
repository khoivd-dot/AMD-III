"""Error-injection evaluation of Homeward's deterministic checks.

Takes a reviewed, correct packet for each sample case, injects the error
types reported in the literature (omissions, hallucinated medicines, dose
changes, stop/keep flips in the draft and in translation, lost contact
details, broken dates), and measures how many the checks catch without any
help from the safety model. Also measures false alarms on the clean packets.

Usage: python -m eval.mutation_eval [--out docs/eval-report.md]
"""

import argparse
import asyncio
import copy
import json
import re
from pathlib import Path

from homeward import lexicon, pipeline
from homeward.llm import ReplayClient
from homeward.verify import coverage, verify_sentence

ROOT = Path(__file__).resolve().parent.parent
GOLD_FIXES = ROOT / "eval" / "gold_fixes.json"


async def gold_packet(sample_id: str) -> dict:
    sample = json.loads((ROOT / "data" / "samples" / f"{sample_id}.json").read_text())
    case = pipeline.new_case(sample["source"], sample["language"], sample.get("patient_name", ""), sample_id)
    await pipeline.run(case, ReplayClient())
    assert case["stage"] == "ready", case["error"]
    fixes = json.loads(GOLD_FIXES.read_text()).get(sample_id, {})
    for sid, change in fixes.get("edit", {}).items():
        s = next(s for s in case["sentences"] if s["id"] == sid)
        s.update(change)
    for sid in fixes.get("remove", []):
        case["sentences"] = [s for s in case["sentences"] if s["id"] != sid]
    for add in fixes.get("add", []):
        case["sentences"].append(add)
    # The deterministic layer is what we measure: drop the model's verdicts.
    for s in case["sentences"]:
        s.pop("judge_en", None)
    return case


def check_all(case: dict) -> tuple[dict, list[dict]]:
    by_id = {f["id"]: f for f in case["facts"]}
    for s in case["sentences"]:
        verify_sentence(s, by_id, case["facts"], case["language"])
    return {s["id"]: s for s in case["sentences"]}, coverage(case["facts"], case["sentences"])


def med_facts(case, s, actions=None):
    by_id = {f["id"]: f for f in case["facts"]}
    out = []
    for fid in s["fact_ids"]:
        f = by_id.get(fid)
        if f and f["kind"] == "medication" and (actions is None or f["med_action"] in actions):
            drug = lexicon.canonical_drug(f["drug"])
            if drug and drug in lexicon.drugs_in(s["text_en"]):
                out.append(f)
    return out


def bump_number(text: str) -> str | None:
    m = re.search(r"\d+(?:[.,]\d+)?", text)
    if not m:
        return None
    old = m.group(0)
    new = str(int(float(old.replace(",", ".")) * 10)) if float(old.replace(",", ".")) >= 1 else "5"
    return text[:m.start()] + new + text[m.end():]


def mutations(case: dict):
    """Yield (type, description, mutate(case_copy) -> (sentence_id or None, fact_id or None))."""
    tl = case["language"] != "en"
    facts = {f["id"]: f for f in case["facts"]}
    for s in case["sentences"]:
        sid = s["id"]
        critical = [fid for fid in s["fact_ids"] if facts.get(fid, {}).get("kind") in ("medication", "warning_sign", "follow_up")]
        for fid in critical:
            others = [o for o in case["sentences"] if o["id"] != sid and fid in o["fact_ids"]]
            if not others:
                def drop(c, sid=sid, fid=fid):
                    c["sentences"] = [x for x in c["sentences"] if x["id"] != sid]
                    return None, fid
                yield "omission", f"drop {sid} (only sentence for {fid})", drop

        for f in med_facts(case, s, ("stop", "hold")):
            name = f["drug"].split()[0].lower()

            def flip(c, sid=sid, name=name):
                x = next(x for x in c["sentences"] if x["id"] == sid)
                x["text_en"] = f"Keep taking {name} the same as before."
                if tl:
                    x["back_en"] = x["text_en"]
                return sid, None
            yield "flip_stop_to_keep", f"{sid}: {name} stop/hold -> keep taking", flip

            if tl:
                def flip_tl(c, sid=sid, name=name):
                    x = next(x for x in c["sentences"] if x["id"] == sid)
                    x["back_en"] = f"Keep taking {name}."
                    return sid, None
                yield "translation_flip", f"{sid}: translation says keep taking {name}", flip_tl

        for f in med_facts(case, s, ("hold",)):
            name = f["drug"].split()[0].lower()

            def hold_to_stop(c, sid=sid, name=name):
                x = next(x for x in c["sentences"] if x["id"] == sid)
                x["text_en"] = f"Stop taking {name}."
                if tl:
                    x["back_en"] = x["text_en"]
                return sid, None
            yield "hold_as_permanent_stop", f"{sid}: pause {name} -> stop", hold_to_stop

        if bump_number(s["text_en"]):
            def dose(c, sid=sid):
                x = next(x for x in c["sentences"] if x["id"] == sid)
                x["text_en"] = bump_number(x["text_en"])
                if tl:
                    x["text_tl"] = bump_number(x["text_tl"])
                    x["back_en"] = bump_number(x["back_en"])
                return sid, None
            yield "number_changed", f"{sid}: first number x10 in every version", dose

        if tl and bump_number(s.get("text_tl") or ""):
            def dose_tl(c, sid=sid):
                x = next(x for x in c["sentences"] if x["id"] == sid)
                x["text_tl"] = bump_number(x["text_tl"])
                return sid, None
            yield "translation_number_changed", f"{sid}: number changed only in translation", dose_tl

        if re.search(r"\b(911|999|112)\b", s["text_en"]):
            def no_emergency(c, sid=sid):
                x = next(x for x in c["sentences"] if x["id"] == sid)
                x["text_en"] = re.sub(r"[Cc]all (911|999|112)", "Call your doctor", x["text_en"])
                if tl:
                    x["back_en"] = re.sub(r"[Cc]all (911|999|112)", "Call your doctor", x["back_en"])
                    x["text_tl"] = re.sub(r"\b(911|999|112)\b", "", x["text_tl"])
                fid = next(f for f in x["fact_ids"] if facts[f]["kind"] == "warning_sign")
                return None, fid
            yield "emergency_number_dropped", f"{sid}: 'call 911' -> 'call your doctor'", no_emergency

        if re.search(r"only if|as needed|if needed", s["text_en"], re.I):
            def prn(c, sid=sid):
                x = next(x for x in c["sentences"] if x["id"] == sid)
                for k in ("text_en", "back_en"):
                    if x.get(k):
                        x[k] = re.sub(r"\s*only if pain is very bad|\s*only if the pain is very strong|\s*(only )?(if|as) needed", "", x[k], flags=re.I)
                return sid, None
            yield "as_needed_dropped (blind spot)", f"{sid}: 'only if needed' removed", prn

        def halluc(c, sid=sid):
            x = next(x for x in c["sentences"] if x["id"] == sid)
            x["text_en"] += " Also take aspirin every day."
            if tl:
                x["back_en"] += " Also take aspirin every day."
            return sid, None
        yield "hallucinated_medicine", f"{sid}: adds aspirin", halluc

        def uncite(c, sid=sid):
            x = next(x for x in c["sentences"] if x["id"] == sid)
            x["fact_ids"] = []
            return sid, None
        yield "unsupported_sentence", f"{sid}: no source fact", uncite

        if tl and "[" in (s.get("text_tl") or ""):
            def lose_ph(c, sid=sid):
                x = next(x for x in c["sentences"] if x["id"] == sid)
                x["text_tl"] = re.sub(r"\[[A-Z_]+_\d+\]", "", x["text_tl"])
                return sid, None
            yield "contact_lost_in_translation", f"{sid}: placeholder dropped", lose_ph

        own = med_facts(case, s)
        if own:
            other = next((f for f in case["facts"] if f["kind"] == "medication" and f["id"] not in s["fact_ids"]
                          and lexicon.canonical_drug(f["drug"])), None)
            if other:
                a = lexicon.canonical_drug(own[0]["drug"])
                b = other["drug"].split()[0].lower()

                def swap(c, sid=sid, a=a, b=b):
                    x = next(x for x in c["sentences"] if x["id"] == sid)

                    def sub(text):
                        # Replace whatever spelling the sentence uses (paracetamol, Tylenol, ...).
                        return re.sub(r"[A-Za-zÀ-ÿ]+", lambda m: b if lexicon.canonical_drug(m.group(0)) == a else m.group(0), text)
                    x["text_en"] = sub(x["text_en"])
                    if tl:
                        x["text_tl"] = sub(x["text_tl"])
                        x["back_en"] = sub(x["back_en"])
                    return sid, None
                yield "wrong_medicine_named", f"{sid}: {a} -> {b}", swap


async def evaluate(sample_ids: list[str]) -> dict:
    results, false_alarms, clean_total = {}, [], 0
    for sample_id in sample_ids:
        gold = await gold_packet(sample_id)
        sents, omissions = check_all(copy.deepcopy(gold))
        clean_total += len(sents)
        for s in sents.values():
            if s["status"] != "green":
                false_alarms.append({"case": sample_id, "id": s["id"], "text": s["text_en"],
                                     "checks": [c["message"] for c in s["checks"] if c["status"] != "pass"]})
        false_alarms += [{"case": sample_id, "omission": o["message"]} for o in omissions]
        for kind, desc, fn in mutations(gold):
            c = copy.deepcopy(gold)
            sid, fid = fn(c)
            sents, omissions = check_all(c)
            if sid:
                caught = sents[sid]["status"] != "green"
                level = sents[sid]["status"]
                human = caught or sents[sid]["risk"] == "high"
            else:
                caught = any(o["fact_id"] == fid for o in omissions)
                level = "red" if caught else "green"
                human = caught
            r = results.setdefault(kind, {"total": 0, "caught": 0, "blocked": 0, "human": 0, "missed": []})
            r["total"] += 1
            r["caught"] += caught
            r["human"] += human
            r["blocked"] += level == "red"
            if not caught:
                r["missed"].append(f"{sample_id} {desc}")
    return {"by_type": results, "false_alarms": false_alarms, "clean_sentences": clean_total}


def report(res: dict, sample_ids: list[str]) -> str:
    lines = ["# Homeward error-injection evaluation", "",
             f"Cases: {', '.join(sample_ids)}. Deterministic checks only (the safety model's verdicts are removed), "
             "so this is the floor the product guarantees even if the model judge is wrong.", "",
             "| Injected error | Injected | Flagged by checks | Blocked (red) | Flag rate | Reaches a human anyway* |", "|---|---|---|---|---|---|"]
    tot = cau = 0
    for kind, r in sorted(res["by_type"].items()):
        tot += r["total"]; cau += r["caught"]
        hum = r["human"]
        lines.append(f"| {kind.replace('_', ' ')} | {r['total']} | {r['caught']} | {r['blocked']} | {100 * r['caught'] / r['total']:.0f}% | {100 * hum / r['total']:.0f}% |")
    lines.append(f"| **all** | **{tot}** | **{cau}** | | **{100 * cau / tot:.1f}%** | |")
    lines += ["", f"False alarms on the clean, reviewed packets: {len(res['false_alarms'])} across {res['clean_sentences']} sentences."]
    for fa in res["false_alarms"]:
        lines.append(f"- {json.dumps(fa, ensure_ascii=False)}")
    missed = [m for r in res["by_type"].values() for m in r["missed"]]
    if missed:
        lines += ["", "Missed:"] + [f"- {m}" for m in missed]
    lines += ["", "Flagged means the sentence turned amber or red, or the packet raised an omission; "
              "either way it cannot reach the patient without a person deciding.",
              "",
              "\\* Reaches a human anyway: flagged, or the sentence carries a high-risk instruction "
              "(anticoagulant, insulin, opioid, any stop/pause/change, warning sign), which Homeward always sends "
              "for sign-off even when every check passes.",
              "",
              "## How to read this honestly",
              "- The mutations are synthetic and the checks were written with these failure types in mind, so a "
              "high rate here is a regression floor, not a claim about real-world accuracy.",
              "- Rows marked *blind spot* are errors the deterministic layer cannot see (meaning changes with no "
              "number, medicine, contact or stop/keep word involved). They rely on the safety model and on "
              "mandatory review of high-risk sentences.",
              "- Re-run against recorded AMD runs with `python -m eval.mutation_eval` after `scripts/record_samples.py`."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "eval-report.md"))
    args = ap.parse_args()
    ids = list(json.loads(GOLD_FIXES.read_text()))
    res = asyncio.run(evaluate(ids))
    text = report(res, ids)
    Path(args.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
