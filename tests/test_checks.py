import asyncio
import json
from pathlib import Path

import pytest

from homeward import pipeline
from homeward.lexicon import drugs_in, polarity
from homeward.llm import ReplayClient, parse_json
from homeward.phi import mask
from homeward.textutil import fk_grade, numbers_in, quote_in_source
from homeward.verify import (classify, coverage, cross_check_meds, uncovered_instructions, verify_facts,
                             verify_sentence)

ROOT = Path(__file__).resolve().parent.parent


def sample(sid):
    return json.loads((ROOT / "data" / "samples" / f"{sid}.json").read_text())


def run_sample(sid):
    s = sample(sid)
    case = pipeline.new_case(s["source"], s["language"], s["patient_name"], sid)
    asyncio.run(pipeline.run(case, ReplayClient()))
    assert case["stage"] == "ready", case["error"]
    return case


# ---------------------------------------------------------------- text utils

def test_numbers_normalise_words_and_decimal_commas():
    assert numbers_in("Take it twice a day") == {"2"}
    assert numbers_in("1,5 litros") == {"1.5"}
    assert numbers_in("40 mg BID") == {"40", "2"}
    assert numbers_in("10:30 on 10/21/2026") == {"10", "30", "21", "2026"}


def test_readability_orders_texts():
    hard = "Acute decompensated heart failure with reduced ejection fraction, precipitated by dietary sodium indiscretion."
    easy = "Your heart was weak. Fluid built up. Eat less salt."
    assert fk_grade(hard) > 12 > 6 > fk_grade(easy)


def test_quote_matching_tolerates_spacing_but_not_inventions():
    src = "NEW: Spironolactone 25 mg by mouth once daily"
    assert quote_in_source("Spironolactone 25 mg  by mouth once daily", src)
    assert not quote_in_source("Warfarin 5 mg nightly", src)


def test_polarity():
    assert polarity("Stop taking ibuprofen.")["stop"]
    assert polarity("Do not stop taking apixaban.")["continue"]
    assert not polarity("Do not stop taking apixaban.")["stop"]
    assert polarity("Do not take ibuprofen until your doctor says so.")["temporary"]
    assert drugs_in("Take Tylenol and paracetamol") == {"acetaminophen"}


def test_parse_json_handles_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure: {"a": [1]}') == {"a": [1]}


# ---------------------------------------------------------------- masking

def test_masking_removes_identifiers_and_restores_them():
    s = sample("hf-maria-es")
    m = mask(s["source"], [s["patient_name"]])
    for secret in ("Maria", "Lopez", "00482913", "03/14/1953", "201-3344", "Anil Patel"):
        assert secret not in m.text
    assert "[CLINICIAN_1]" in m.text and "Dr. Patel" not in m.text  # same doctor, same token
    assert "10/21/2026" in m.text  # appointment dates stay; patients need them
    assert m.unmask("See [CLINICIAN_1], call [PHONE_1]") == "See Dr. Anil Patel, call (555) 201-3344"


def test_masking_uk_phone():
    m = mask("Call the ward on 020 7946 0321 for fever.")
    assert "7946" not in m.text and "[PHONE_1]" in m.text


# ---------------------------------------------------------------- sentence checks

FACTS = [
    {"id": "F1", "kind": "medication", "med_action": "hold", "drug": "Ibuprofen", "dose": None, "frequency": None,
     "detail": "Do not take ibuprofen until kidneys are rechecked.",
     "source_quote": "HOLD: Ibuprofen - do not take until kidney function is rechecked", "risk": "high"},
    {"id": "F2", "kind": "medication", "med_action": "changed", "drug": "Furosemide", "dose": "40 mg",
     "frequency": "twice daily", "detail": "Furosemide 40 mg twice daily.",
     "source_quote": "Furosemide increased from 20 mg to 40 mg by mouth twice daily", "risk": "high"},
    {"id": "F3", "kind": "warning_sign", "med_action": None, "drug": None, "dose": None, "frequency": None,
     "detail": "Call 911 for chest pain.", "source_quote": "call 911 for chest pain", "risk": "high"},
]
BY_ID = {f["id"]: f for f in FACTS}


def checked(text, fact_ids, lang="en", tl=None, back=None):
    s = {"id": "S1", "text_en": text, "fact_ids": fact_ids, "text_tl": tl, "back_en": back}
    verify_sentence(s, BY_ID, FACTS, lang)
    return s


def test_good_sentence_is_green_but_high_risk_still_needs_review():
    s = checked("Take furosemide 40 mg two times a day.", ["F2"])
    assert s["status"] == "green" and s["needs_review"]


def test_wrong_dose_blocked():
    assert checked("Take furosemide 400 mg two times a day.", ["F2"])["status"] == "red"


def test_hallucinated_drug_blocked():
    assert checked("Take furosemide 40 mg twice a day with aspirin.", ["F2"])["status"] == "red"


def test_hold_written_as_stop_is_uncertain():
    assert checked("Stop taking ibuprofen.", ["F1"])["status"] == "amber"
    assert checked("Do not take ibuprofen until your doctor checks your kidneys.", ["F1"])["status"] == "green"


def test_hold_written_as_keep_blocked():
    assert checked("Keep taking ibuprofen.", ["F1"])["status"] == "red"


def test_uncited_sentence_blocked():
    assert checked("Drink plenty of water.", [])["status"] == "red"


def test_translation_flip_blocked():
    s = checked("Do not take ibuprofen until your doctor checks your kidneys.", ["F1"], "zh",
                tl="在医生检查肾脏之前继续服用ibuprofen。", back="Keep taking ibuprofen until the doctor checks your kidneys.")
    assert s["status"] == "red"
    assert any(c["name"] == "translation_polarity" for c in s["checks"])


def test_translation_number_change_blocked():
    s = checked("Take furosemide 40 mg two times a day.", ["F2"], "es",
                tl="Tome furosemide 4 mg dos veces al día.", back="Take furosemide 4 mg two times a day.")
    assert s["status"] == "red"


def test_coverage_finds_missing_and_incomplete_facts():
    sentences = [{"id": "S1", "text_en": "Take furosemide two times a day.", "fact_ids": ["F2"]},
                 {"id": "S2", "text_en": "Get help if you have chest pain.", "fact_ids": ["F3"]}]
    found = {o["fact_id"]: o["message"] for o in coverage(FACTS, sentences)}
    assert "F1" in found                       # ibuprofen never mentioned
    assert "dose" in found["F2"]               # 40 mg never stated
    assert "911" in found["F3"]                # who to call is missing


# ---------------------------------------------------------------- full pipeline on recorded samples

def test_hero_case_flags_exactly_the_planted_problems():
    case = run_sample("hf-maria-es")
    status = {s["id"]: s["status"] for s in case["sentences"]}
    assert status["S12"] == "red"      # 1.5 L became 15 L in Spanish
    assert status["S5"] == "amber"     # hold written as stop
    assert [o["fact_id"] for o in case["omissions"]] == ["F9"]  # weight-gain warning dropped
    assert sum(v != "green" for v in status.values()) == 2
    assert case["phi_counts"]["MRN"] == 1


def test_knee_case_blocks_hallucinated_ibuprofen():
    case = run_sample("knee-giulia-it")
    s6 = next(s for s in case["sentences"] if s["id"] == "S6")
    assert s6["status"] == "red"
    assert not case["omissions"]


def test_signoff_requires_every_decision_then_builds_quiz():
    case = run_sample("hf-maria-es")
    with pytest.raises(ValueError):
        pipeline.sign_off(case, "RN Test")
    with pytest.raises(ValueError):
        pipeline.approve(case, "S12", "RN Test")  # red cannot be approved as is
    pipeline.edit(case, "S12", "RN Test", None, "No beba más de 1,5 litros de líquido al día.")
    pipeline.edit(case, "S5", "RN Test", "Do not take ibuprofen until your heart doctor checks your kidneys again.",
                  "No tome ibuprofen hasta que su cardiólogo revise sus riñones otra vez.")
    pipeline.add_sentence(case, "RN Test", "F9",
                          "Call the heart clinic at [PHONE_1] if your weight goes up more than 2 pounds in one day or 5 pounds in one week, or if your legs swell more.",
                          "Llame a la clínica al [PHONE_1] si su peso sube más de 2 libras en un día o 5 libras en una semana, o si sus piernas se hinchan más.")
    for s in case["sentences"]:
        if s["needs_review"]:
            pipeline.approve(case, s["id"], "RN Test")
    assert pipeline.blockers(case) == []
    pipeline.sign_off(case, "RN Test")
    assert case["quiz"] and all(sum(o["correct"] for o in q["options"]) == 1 for q in case["quiz"])
    packet = pipeline.packet(case)
    text = json.dumps(packet, ensure_ascii=False)
    assert "(555) 201-3344" in text and "[PHONE_1]" not in text  # details restored for the patient
    q = case["quiz"][0]
    wrong = next(i for i, o in enumerate(q["options"]) if not o["correct"])
    assert pipeline.answer(case, q["id"], wrong) == {"correct": False}
    assert case["alerts"] and case["alerts"][0]["message"].startswith("Re-explain")


def test_public_view_never_leaks_identifiers():
    case = run_sample("hf-maria-es")
    text = json.dumps(pipeline.public(case), ensure_ascii=False, default=str)
    for secret in ("Maria", "Lopez", "00482913", "03/14/1953", "201-3344"):
        assert secret not in text


def test_unknown_language_routes_to_interpreter():
    s = sample("hf-maria-es")
    case = pipeline.new_case(s["source"], "tl", s["patient_name"], "hf-maria-es")
    # Replay has no Tagalog outputs, but facts and draft are language-independent.
    data = json.loads((ROOT / "data" / "replay" / "hf-maria-es.json").read_text())
    data["judge"]["tl"] = data["judge"]["es"]

    class Stub(ReplayClient):
        async def complete_json(self, stage, key, messages, schema, usage, case_id=None):
            return data[stage][key]
    asyncio.run(pipeline.run(case, Stub()))
    assert case["route"] == "interpreter"
    assert all("text_tl" not in s for s in case["sentences"])


def test_off_schema_model_output_is_normalised_not_fatal():
    facts = pipeline._norm_facts({"facts": [
        {"kind": "medication", "med_action": "pause", "drug": "Ibuprofen", "detail": "Hold ibuprofen.",
         "source_quote": "HOLD: Ibuprofen"},
        "not a fact",
        {"id": "F1", "kind": "made_up", "detail": "x", "source_quote": "y"}]})
    assert [f["id"] for f in facts] == ["F1", "F3x"]
    assert facts[0]["med_action"] is None and facts[1]["kind"] == "other"
    sents = pipeline._norm_sentences({"sentences": [
        {"text": "Take it.", "fact_ids": "F1", "section": "meds"}, {"id": "S9", "text": " "}]})
    assert sents == [{"id": "S1", "section": "daily_care", "text_en": "Take it.", "fact_ids": ["F1"], "review": None}]
    with pytest.raises(ValueError):
        pipeline._norm_sentences({"sentences": []})


# ---------------------------------------------------------------- failure modes seen on real model output

AF_SOURCE = """MEDICATIONS
NEW: Apixaban 5 mg by mouth twice daily, about 12 hours apart. Do not stop without talking to your cardiologist.
STOP: Aspirin 81 mg - stop, because apixaban already protects against clots.
Diet: Sodium restriction < 2 g/day; fluid restriction 1.5 L/day.
Never skip insulin glargine, even if you are not eating."""


def real_facts():
    # What a 3B model returned: every fact labelled "diagnosis", labels dropped from quotes.
    return [{"id": "F1", "kind": "diagnosis", "med_action": None, "drug": "Apixaban", "dose": "5 mg",
             "frequency": "twice daily", "detail": "Take apixaban.",
             "source_quote": "Apixaban 5 mg by mouth twice daily, about 12 hours apart."},
            {"id": "F2", "kind": "diagnosis", "med_action": "stop", "drug": "Aspirin", "dose": "81 mg",
             "frequency": None, "detail": "Stop aspirin.", "source_quote": "Aspirin 81 mg - stop"}]


def test_model_labels_are_rechecked_against_the_text():
    facts = real_facts()
    verify_facts(facts, AF_SOURCE)
    assert [(f["kind"], f["med_action"], f["risk"]) for f in facts] == \
        [("medication", "new", "high"), ("medication", "stop", "high")]  # apixaban is high-alert
    assert any(c["name"] == "classification" for c in facts[0]["checks"])


def test_negated_stop_reads_as_keep_taking():
    assert polarity("You must not stop taking aspirin.") == {"continue": True, "stop": False, "temporary": False}
    assert polarity("Never skip insulin glargine.")["continue"]
    assert polarity("You must not use the ipratropium inhaler.")["stop"]
    f = {**real_facts()[1], "kind": "medication", "checks": []}
    s = {"id": "S1", "text_en": "You must not stop taking Aspirin 81 mg.", "fact_ids": ["F2"]}
    verify_sentence(s, {"F2": f}, [f], "en")
    assert s["status"] == "red"


def test_instructions_the_model_dropped_become_facts_to_cover():
    facts = real_facts()
    verify_facts(facts, AF_SOURCE)
    missed = uncovered_instructions(facts, AF_SOURCE)
    quotes = [m["source_quote"] for m in missed]
    assert any("Sodium" in q for q in quotes) and any("fluid" in q for q in quotes)
    insulin = next(m for m in missed if "insulin" in m["source_quote"])
    assert insulin["kind"] == "medication" and insulin["med_action"] == "continue" and insulin["risk"] == "high"
    assert all(m["must_cover"] and m["status"] == "amber" for m in missed)
    omitted = {o["fact_id"] for o in coverage(facts + missed, [])}
    assert {m["id"] for m in missed} <= omitted


def test_medicine_list_label_belongs_to_the_first_medicine():
    facts = real_facts()
    verify_facts(facts, AF_SOURCE)
    assert cross_check_meds(facts, AF_SOURCE) == []  # "do not stop" and "because apixaban" are not stop orders


def test_lost_timing_is_an_omission_but_old_values_are_not():
    f = {"id": "F1", "kind": "medication", "med_action": "changed", "drug": "Albuterol", "dose": "2 puffs",
         "frequency": "every 4 hours", "detail": "", "source_quote":
         "Albuterol inhaler 2 puffs every 4 hours as needed (was every 6 hours). Wait 12 hours between doses."}
    said = [{"id": "S1", "text_en": "Use albuterol 2 puffs every 4 hours if you need it.", "fact_ids": ["F1"]}]
    msgs = [o["message"] for o in coverage([f], said)]
    assert len(msgs) == 1 and "12" in msgs[0] and "6" not in msgs[0].split("(")[0]


def test_course_end_is_not_a_contradiction():
    f = {"id": "F1", "kind": "medication", "med_action": "new", "drug": "Prednisone", "dose": "40 mg",
         "frequency": "once daily", "detail": "", "source_quote": "Prednisone 40 mg once daily for 5 days, then stop."}
    s = {"id": "S1", "text_en": "Take prednisone 40 mg once a day for 5 days, then stop.", "fact_ids": ["F1"]}
    verify_sentence(s, {"F1": f}, [f], "en")
    assert s["status"] == "green"


def test_translation_in_the_wrong_writing_system_blocked():
    s = checked("Call 911 for chest pain or fainting.", ["F3"], "vi",
                tl="Gọi 911 nếu đau ngực hoặc 晕倒.", back="Call 911 if chest pain or you fall.")
    assert s["status"] == "red" and any(c["name"] == "translation_script" for c in s["checks"])
    ok = checked("Call 911 for chest pain.", ["F3"], "zh", tl="胸痛请拨打911。", back="Call 911 for chest pain.")
    assert not any(c["name"] == "translation_script" for c in ok["checks"])
