"""Scripted sample run for knee-giulia-it (stands in until a recorded AMD run replaces it)."""
import json, pathlib

def F(i, kind, detail, quote, action=None, drug=None, dose=None, freq=None):
    return {"id": i, "kind": kind, "med_action": action, "drug": drug, "dose": dose, "frequency": freq,
            "detail": detail, "source_quote": quote}

facts = [
 F("F1","diagnosis","You had surgery to replace your right knee on 10/12/2026.","Right total knee arthroplasty on 10/12/2026."),
 F("F2","medication","Inject enoxaparin 40 mg under the skin once a day for 14 days to prevent blood clots; last dose 10/26/2026.",
   "NEW: Enoxaparin 40 mg subcutaneous injection once daily for 14 days to prevent blood clots. Last dose 10/26/2026.","new","Enoxaparin","40 mg","once daily for 14 days"),
 F("F3","medication","Take oxycodone 5 mg every 6 hours only if needed for severe pain; no more than 4 tablets in 24 hours.",
   "NEW: Oxycodone 5 mg by mouth every 6 hours only if needed for severe pain. Maximum 4 tablets in 24 hours.","new","Oxycodone","5 mg","every 6 hours as needed"),
 F("F4","medication","Take paracetamol 1000 mg every 8 hours for pain; no more than 3000 mg in 24 hours.",
   "NEW: Paracetamol 1000 mg by mouth every 8 hours for pain. Do not exceed 3000 mg in 24 hours.","new","Paracetamol","1000 mg","every 8 hours"),
 F("F5","medication","Take docusate 100 mg twice a day while taking oxycodone.",
   "NEW: Docusate 100 mg by mouth twice daily while taking oxycodone.","new","Docusate","100 mg","twice daily"),
 F("F6","medication","Keep taking amlodipine 5 mg once a day.","CONTINUE: Amlodipine 5 mg by mouth once daily.","continue","Amlodipine","5 mg","once daily"),
 F("F7","activity","Do not drive or drink alcohol while taking oxycodone.","Do not drive or drink alcohol while taking oxycodone."),
 F("F8","wound_care","Keep the dressing clean and dry; you may shower after 48 hours but do not soak the knee until the staples are removed.",
   "Keep the dressing clean and dry. You may shower after 48 hours; do not soak the knee in a bath or pool until staples are removed."),
 F("F9","activity","Use the walker at all times for 2 weeks and do the home exercises 3 times a day.",
   "Use the walker at all times for 2 weeks. Do the home exercises from physiotherapy 3 times a day."),
 F("F10","warning_sign","Call 999 for chest pain or sudden shortness of breath.","Call 999 for chest pain or sudden shortness of breath."),
 F("F11","warning_sign","Call the orthopaedic ward on [PHONE_1] for calf pain or swelling, fever above 38.5 C, or redness, warmth or drainage from the wound.",
   "Call the orthopaedic ward on [PHONE_1] for calf pain or swelling, fever above 38.5 C, or redness, warmth or drainage from the wound."),
 F("F12","follow_up","Physiotherapy at home on 10/15/2026.","Physiotherapy at home on 10/15/2026."),
 F("F13","follow_up","Orthopaedic clinic with [CLINICIAN_1] on 10/26/2026 to remove the staples.","Orthopaedic clinic with [CLINICIAN_1] on 10/26/2026 for staple removal."),
]

# S6 is a hallucination of the kind reported for LLM rewrites: a common pain
# medicine the surgeon never prescribed (and that adds bleeding risk on enoxaparin).
draft = [
 ("S1","why","You had an operation to replace your right knee on 10/12/2026.",["F1"]),
 ("S2","medicines","Inject enoxaparin 40 mg under your skin once a day for 14 days. It stops blood clots.",["F2"]),
 ("S3","medicines","Your last enoxaparin shot is on 10/26/2026.",["F2"]),
 ("S4","medicines","Take oxycodone 5 mg only if pain is very bad. Wait at least 6 hours between doses.",["F3"]),
 ("S5","medicines","Never take more than 4 oxycodone tablets in 24 hours.",["F3"]),
 ("S6","medicines","You can also take ibuprofen if the pain is not too bad.",["F4"]),
 ("S7","medicines","Take paracetamol 1000 mg every 8 hours for pain. Do not take more than 3000 mg in 24 hours.",["F4"]),
 ("S8","medicines","Take docusate 100 mg 2 times a day while you take oxycodone. It helps you poop.",["F5"]),
 ("S9","medicines","Keep taking amlodipine 5 mg once a day, as before.",["F6"]),
 ("S10","daily_care","Do not drive or drink alcohol while you take oxycodone.",["F7"]),
 ("S11","daily_care","Keep the bandage clean and dry. You can shower after 48 hours.",["F8"]),
 ("S12","daily_care","Do not soak your knee in a bath or pool until the staples are out.",["F8"]),
 ("S13","daily_care","Use your walker all the time for 2 weeks. Do your exercises 3 times a day.",["F9"]),
 ("S14","warning_signs","Call 999 if you have chest pain or suddenly cannot breathe well.",["F10"]),
 ("S15","warning_signs","Call the ward at [PHONE_1] if your calf hurts or swells, you have a fever over 38.5 C, or the wound is red, warm or leaking.",["F11"]),
 ("S16","appointments","A physiotherapist will visit you at home on 10/15/2026.",["F12"]),
 ("S17","appointments","See [CLINICIAN_1] at the bone clinic on 10/26/2026 to take out the staples.",["F13"]),
]

it = {
 "S1":"Il 10/12/2026 ha fatto un intervento per sostituire il ginocchio destro.",
 "S2":"Si inietti enoxaparin 40 mg sotto la pelle una volta al giorno per 14 giorni. Serve a evitare i coaguli di sangue.",
 "S3":"L'ultima iniezione di enoxaparin è il 10/26/2026.",
 "S4":"Prenda oxycodone 5 mg solo se il dolore è molto forte. Aspetti almeno 6 ore tra una dose e l'altra.",
 "S5":"Non prenda mai più di 4 compresse di oxycodone in 24 ore.",
 "S6":"Può prendere anche ibuprofen se il dolore non è troppo forte.",
 "S7":"Prenda paracetamol 1000 mg ogni 8 ore per il dolore. Non superi 3000 mg in 24 ore.",
 "S8":"Prenda docusate 100 mg 2 volte al giorno finché prende oxycodone. Aiuta a andare di corpo.",
 "S9":"Continui a prendere amlodipine 5 mg una volta al giorno, come prima.",
 "S10":"Non guidi e non beva alcolici finché prende oxycodone.",
 "S11":"Tenga la medicazione pulita e asciutta. Può fare la doccia dopo 48 ore.",
 "S12":"Non immerga il ginocchio nella vasca o in piscina finché non le tolgono i punti metallici.",
 "S13":"Usi sempre il deambulatore per 2 settimane. Faccia gli esercizi 3 volte al giorno.",
 "S14":"Chiami il 999 se ha dolore al petto o se all'improvviso non riesce a respirare bene.",
 "S15":"Chiami il reparto al [PHONE_1] se il polpaccio le fa male o si gonfia, se ha febbre sopra 38,5 C, o se la ferita è rossa, calda o perde liquido.",
 "S16":"Un fisioterapista verrà a casa sua il 10/15/2026.",
 "S17":"Vada da [CLINICIAN_1] all'ambulatorio di ortopedia il 10/26/2026 per togliere i punti metallici.",
}
back = {
 "S1":"On 10/12/2026 you had an operation to replace the right knee.",
 "S2":"Inject enoxaparin 40 mg under the skin once a day for 14 days. It serves to avoid blood clots.",
 "S3":"The last injection of enoxaparin is on 10/26/2026.",
 "S4":"Take oxycodone 5 mg only if the pain is very strong. Wait at least 6 hours between one dose and the other.",
 "S5":"Never take more than 4 tablets of oxycodone in 24 hours.",
 "S6":"You can also take ibuprofen if the pain is not too strong.",
 "S7":"Take paracetamol 1000 mg every 8 hours for pain. Do not exceed 3000 mg in 24 hours.",
 "S8":"Take docusate 100 mg 2 times a day while you take oxycodone. It helps to go to the toilet.",
 "S9":"Continue to take amlodipine 5 mg once a day, as before.",
 "S10":"Do not drive and do not drink alcohol while you take oxycodone.",
 "S11":"Keep the dressing clean and dry. You can take a shower after 48 hours.",
 "S12":"Do not immerse the knee in the bath or in a pool until they remove the metal stitches.",
 "S13":"Always use the walker for 2 weeks. Do the exercises 3 times a day.",
 "S14":"Call 999 if you have chest pain or if suddenly you cannot breathe well.",
 "S15":"Call the ward at [PHONE_1] if your calf hurts or swells, if you have fever above 38.5 C, or if the wound is red, warm or leaks fluid.",
 "S16":"A physiotherapist will come to your home on 10/15/2026.",
 "S17":"Go to [CLINICIAN_1] at the orthopaedic clinic on 10/26/2026 to remove the metal stitches.",
}
judge = {sid: ("supported", "Matches the cited facts.") for sid in it}
judge["S6"] = ("unsupported", "Ibuprofen is not in the discharge instructions; only paracetamol and oxycodone are.")
judge["S4"] = ("partially_supported", "Source says every 6 hours as needed; 'very bad pain' fits 'severe' but check wording.")

data = {
 "_meta": {"source": "scripted", "note": "Hand-written sample run for demo without a GPU. Replace with a recorded AMD MI300X run (scripts/record_samples.py)."},
 "facts": {"en": {"facts": facts}},
 "draft": {"en": {"sentences": [{"id": i, "section": sec, "text": t, "fact_ids": f} for i, sec, t, f in draft]}},
 "translate": {"it": {"items": [{"id": k, "text": v} for k, v in it.items()]}},
 "back_translate": {"it": {"items": [{"id": k, "text": v} for k, v in back.items()]}},
 "judge": {"it": {"verdicts": [{"id": k, "verdict": v, "reason": r} for k, (v, r) in judge.items()]}},
 "suggest": {},
}
pathlib.Path(__file__).resolve().parent.parent.joinpath("data/replay/knee-giulia-it.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
print("ok")
