import asyncio
import json
from pathlib import Path

import pytest

from homeward import pipeline
from homeward.lexicon import drugs_in, polarity
from homeward.llm import ReplayClient, parse_json
from homeward.phi import mask
from homeward.textutil import dates_in, fk_grade, numbers_in, quantities, quote_in_source, spell_dates, times_in
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


# ---------------------------------------------------------------- failure modes found in simulated user testing

def test_numbers_next_to_chinese_characters():
    assert numbers_in("每天服用14单位") == {"14"}
    assert numbers_in("à 11h00") == {"11", "0"}
    assert quantities("注射14单位, 14 毫升, Advair 50 mcg, 10 pound") == {("14", "unit"), ("14", "ml"), ("50", "mcg"), ("10", "lb")}


def test_dates_and_times_are_read_as_a_local_reader_would():
    assert dates_in("10/12/2026") == {(2026, 10, 12)} and dates_in("10/12/2026", "it") == {(2026, 12, 10)}
    assert dates_in("el 21 de octubre de 2026", "es") == dates_in("2026年10月21日", "zh") == {(2026, 10, 21)}
    assert dates_in("1/2 cup of juice") == set()
    assert spell_dates("Clinic on 10/21/2026, 1/2 cup") == "Clinic on October 21, 2026, 1/2 cup"
    assert times_in("Hẹn lúc 2:15 chiều", "vi") == {(2, 15, "pm")} and times_in("8 AM and 2 PM") == {(8, 0, "am"), (2, 0, "pm")}
    assert times_in("every 4 hours") == set()


MEDS = [{"id": "F1", "kind": "medication", "med_action": "new", "drug": "Oxycodone", "dose": "5 mg",
         "frequency": "every 6 hours", "detail": "", "status": "green", "checks": [],
         "source_quote": "Oxycodone 5 mg every 6 hours only if needed for severe pain. Maximum 4 tablets in 24 hours."},
        {"id": "F2", "kind": "medication", "med_action": "new", "drug": "Furosemide", "dose": "40 mg",
         "frequency": "twice daily", "detail": "", "status": "green", "checks": [],
         "source_quote": "Furosemide 40 mg twice daily. Sodium restriction 2 g/day. Lift no more than 10 lb."},
        {"id": "F3", "kind": "medication", "med_action": "new", "drug": "Insulin lispro", "dose": None,
         "frequency": None, "detail": "", "status": "green", "checks": [],
         "source_quote": "Insulin lispro: glucose 151-200 give 2 units; 201-250 give 4 units."},
        {"id": "F4", "kind": "follow_up", "med_action": None, "drug": None, "dose": None, "frequency": None,
         "detail": "", "status": "green", "checks": [], "source_quote": "Clinic on 10/14/2026 at 3:30 PM."}]
MEDS_BY_ID = {f["id"]: f for f in MEDS}


def names(text, fid, lang="en", tl=None):
    s = {"id": "S1", "text_en": text, "fact_ids": [fid], "text_tl": tl, "back_en": None}
    verify_sentence(s, MEDS_BY_ID, MEDS, lang)
    return {c["name"] for c in s["checks"] if c["status"] == "fail"}


def test_meaning_errors_with_the_same_digits_are_blocked():
    assert "as_needed" in names("Take oxycodone 5 mg every 6 hours.", "F1")
    assert "as_needed" not in names("Never take more than 4 oxycodone tablets in 24 hours.", "F1")
    assert "frequency" in names("Take furosemide 40 mg once a day.", "F2")
    assert "units" in names("Take furosemide 40 g twice a day.", "F2")
    assert "units" in names("Do not lift more than 10 kg.", "F2")
    assert "salt_sodium" in names("Eat no more than 2 g of salt a day.", "F2")
    assert "scale" in names("If it is 201 to 250, give 2 units.", "F3")
    assert "dates" in names("Go to the clinic on December 10, 2026.", "F4")


def test_translation_meaning_is_checked_in_the_target_language():
    en = "Take oxycodone 5 mg only if needed, every 6 hours."
    assert "translation_as_needed" in names(en, "F1", "vi", tl="Uống oxycodone 5 mg mỗi 6 giờ.")
    assert "translation_as_needed" not in names(en, "F1", "vi", tl="Chỉ uống oxycodone 5 mg khi cần, mỗi 6 giờ.")
    appt = "Go to the clinic on October 14, 2026 at 3:30 PM."
    assert "translation_time" in names(appt, "F4", "vi", tl="Đến phòng khám ngày 14 tháng 10 năm 2026 lúc 3:30 sáng.")
    assert "translation_dates" in names(appt, "F4", "es", tl="Vaya a la clínica el 10/12/2026 a las 3:30 de la tarde.")
    assert not names(appt, "F4", "es", tl="Vaya a la clínica el 14 de octubre de 2026 a las 3:30 de la tarde.")
    assert "translation_units" in names("Give 2 units if it is 151 to 200.", "F3", "zh", tl="如果是151到200，注射2毫升。")


def test_review_rules_stop_rubber_stamping():
    case = run_sample("hf-maria-es")
    with pytest.raises(ValueError, match="Nothing was changed"):
        s12 = next(s for s in case["sentences"] if s["id"] == "S12")
        pipeline.edit(case, "S12", "RN Test", s12["text_en"], s12["text_tl"])
    pipeline.edit(case, "S12", "RN Test", "Drink no more than 1.2 liters of fluid each day.", None)
    s12 = next(s for s in case["sentences"] if s["id"] == "S12")
    assert s12["status"] == "red" and any(c["name"] == "translation_stale" for c in s12["checks"])
    high = next(f for f in case["facts"] if f["risk"] == "high")
    with pytest.raises(ValueError, match="cannot be dismissed"):
        pipeline.dismiss_fact(case, high["id"], "RN Test", "not needed for this patient")
    low = next(f for f in case["facts"] if f["risk"] == "normal")
    with pytest.raises(ValueError, match="few words"):
        pipeline.dismiss_fact(case, low["id"], "RN Test", "x")
    # An edited high-risk line stays in review until someone approves it.
    pipeline.edit(case, "S5", "RN Test", "Do not take ibuprofen until your heart doctor checks your kidneys again.",
                  "No tome ibuprofen hasta que su cardiólogo revise sus riñones otra vez.")
    s5 = next(s for s in case["sentences"] if s["id"] == "S5")
    assert s5["needs_review"]
    pipeline.approve(case, "S5", "RN Test")
    assert not s5["needs_review"]


def test_medicine_list_disagreement_blocks_until_resolved():
    case = run_sample("hf-maria-es")
    case["med_issues"] = [{"type": "action_mismatch", "drug": "lisinopril", "line": "", "message": "Lisinopril: differs."}]
    assert "Lisinopril: differs." in pipeline.blockers(case)
    with pytest.raises(ValueError):
        pipeline.resolve_med_issue(case, "lisinopril", "RN Test", "ok")
    pipeline.resolve_med_issue(case, "lisinopril", "RN Test", "checked against the medicine list")
    assert "Lisinopril: differs." not in pipeline.blockers(case)


def test_model_ids_cannot_carry_markup():
    facts = pipeline._norm_facts({"facts": [{"id": "<img src=x onerror=alert(1)>", "kind": "other", "detail": "a",
                                             "source_quote": "a"}]})
    assert facts[0]["id"] == "F1"
    sents = pipeline._norm_sentences({"sentences": [{"id": "S1", "text": "x", "fact_ids": ["F1", "<b>"]}]})
    assert sents[0]["fact_ids"] == ["F1"]


def test_masking_handles_non_english_labels_and_spares_dosing_text():
    m = mask("Paciente: María José García\nHija: Rosa, +34 612 345 678\nSSN 123-45-6789\n"
             "Fecha de nacimiento: 14 de marzo de 1953\nPriya Rao, MD\n姓名：陈建国。患者陈建国。\n"
             "Oxycodone: Max 4 tablets in 24 hours. Take at 0800 1400 2000.", ["Max Taylor"])
    for secret in ("María", "García", "Rosa", "612 345", "123-45-6789", "1953", "Priya", "陈建国"):
        assert secret not in m.text, secret
    assert "Max 4 tablets" in m.text and "0800 1400 2000" in m.text
    assert mask("Patient: José Núñez. JOSE NUNEZ is 70.").text.count("[PATIENT_1]") == 2
