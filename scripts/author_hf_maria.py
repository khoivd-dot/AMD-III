"""Scripted sample run for hf-maria-es (stands in until a recorded AMD run replaces it)."""
import json, pathlib

facts = [
 {"id":"F1","kind":"diagnosis","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"You were in hospital because your heart failure got worse; salt and an anti-inflammatory pain medicine played a part.",
  "source_quote":"Acute decompensated heart failure with reduced ejection fraction (EF 30%), precipitated by dietary sodium indiscretion and NSAID use."},
 {"id":"F2","kind":"medication","med_action":"new","drug":"Spironolactone","dose":"25 mg","frequency":"once daily",
  "detail":"Start spironolactone 25 mg by mouth once a day.","source_quote":"NEW: Spironolactone 25 mg by mouth once daily"},
 {"id":"F3","kind":"medication","med_action":"changed","drug":"Furosemide","dose":"40 mg","frequency":"twice daily (8 AM and 2 PM)",
  "detail":"Furosemide dose goes up from 20 mg to 40 mg, taken twice a day at 8 AM and 2 PM.",
  "source_quote":"CHANGED: Furosemide increased from 20 mg to 40 mg by mouth twice daily (8 AM and 2 PM)"},
 {"id":"F4","kind":"medication","med_action":"hold","drug":"Ibuprofen","dose":None,"frequency":None,
  "detail":"Do not take ibuprofen until your cardiologist rechecks your kidney function.",
  "source_quote":"HOLD: Ibuprofen - do not take until kidney function is rechecked by your cardiologist"},
 {"id":"F5","kind":"medication","med_action":"stop","drug":"Lisinopril","dose":"10 mg","frequency":"daily",
  "detail":"Stop taking lisinopril 10 mg.","source_quote":"STOP: Lisinopril 10 mg daily - discontinued"},
 {"id":"F6","kind":"medication","med_action":"new","drug":"Sacubitril/valsartan","dose":"24/26 mg","frequency":"twice daily",
  "detail":"Start sacubitril/valsartan 24/26 mg twice a day, but not within 36 hours of your last lisinopril dose.",
  "source_quote":"NEW: Sacubitril/valsartan 24/26 mg by mouth twice daily. Do not take within 36 hours of your last lisinopril dose."},
 {"id":"F7","kind":"medication","med_action":"continue","drug":"Metoprolol succinate","dose":"50 mg","frequency":"once daily",
  "detail":"Keep taking metoprolol succinate 50 mg once a day.","source_quote":"CONTINUE: Metoprolol succinate 50 mg by mouth once daily"},
 {"id":"F8","kind":"warning_sign","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"Call 911 or go to the Emergency Department for chest pain, shortness of breath at rest, or fainting.",
  "source_quote":"Return to the Emergency Department or call 911 for chest pain, shortness of breath at rest, or fainting."},
 {"id":"F9","kind":"warning_sign","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"Call the heart failure clinic at [PHONE_1] if your weight goes up more than 2 lb in one day or 5 lb in one week, or if your leg swelling gets worse.",
  "source_quote":"Call the heart failure clinic at [PHONE_1] if weight increases by more than 2 lb in one day or 5 lb in one week, or if leg swelling worsens."},
 {"id":"F10","kind":"diet","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"Eat less than 2 g of sodium (salt) a day.","source_quote":"Sodium restriction < 2 g/day."},
 {"id":"F11","kind":"diet","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"Drink no more than 1.5 L of fluid a day.","source_quote":"Fluid restriction 1.5 L/day."},
 {"id":"F12","kind":"activity","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"Weigh yourself every morning after you pee and before breakfast, and write it down.",
  "source_quote":"Weigh yourself every morning after urinating and before breakfast and record daily weights."},
 {"id":"F13","kind":"activity","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"Walk as much as you can manage; do not lift more than 10 lb for 2 weeks.",
  "source_quote":"Walk as tolerated; no lifting > 10 lb for 2 weeks."},
 {"id":"F14","kind":"follow_up","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"Heart failure clinic visit with [CLINICIAN_1] on 10/21/2026 at 10:30 AM.",
  "source_quote":"Heart failure clinic with [CLINICIAN_1] on 10/21/2026 at 10:30 AM."},
 {"id":"F15","kind":"follow_up","med_action":None,"drug":None,"dose":None,"frequency":None,
  "detail":"Blood test (basic metabolic panel) on 10/18/2026 at the outpatient lab.",
  "source_quote":"Basic metabolic panel (blood test) on 10/18/2026 at the outpatient lab."},
]

# The draft deliberately reproduces two failure modes reported for LLM rewrites
# (Zaretsky et al., JAMA Netw Open 2024): an omission (F9 never stated) and a
# blurred instruction (ibuprofen "hold" written as a plain stop).
draft = [
 ("S1","why","You stayed in the hospital because your heart was not pumping well and fluid built up.",["F1"]),
 ("S2","why","Too much salt and a pain medicine called an NSAID made it worse.",["F1"]),
 ("S3","medicines","Start spironolactone 25 mg. Take it once a day.",["F2"]),
 ("S4","medicines","Your furosemide dose is now 40 mg. Take it 2 times a day, at 8 AM and 2 PM.",["F3"]),
 ("S5","medicines","Stop taking ibuprofen.",["F4"]),
 ("S6","medicines","Stop taking lisinopril. Do not take it again.",["F5"]),
 ("S7","medicines","Start sacubitril/valsartan 24/26 mg, 2 times a day.",["F6"]),
 ("S8","medicines","Wait at least 36 hours after your last lisinopril before your first sacubitril/valsartan.",["F6","F5"]),
 ("S9","medicines","Keep taking metoprolol succinate 50 mg once a day, the same as before.",["F7"]),
 ("S10","warning_signs","Call 911 or go to the emergency room if you have chest pain, trouble breathing while resting, or you faint.",["F8"]),
 ("S11","daily_care","Eat less than 2 grams of salt each day.",["F10"]),
 ("S12","daily_care","Drink no more than 1.5 liters of fluid each day.",["F11"]),
 ("S13","daily_care","Weigh yourself every morning after you pee and before breakfast. Write it down.",["F12"]),
 ("S14","daily_care","Walk as much as feels OK. Do not lift more than 10 pounds for 2 weeks.",["F13"]),
 ("S15","appointments","See [CLINICIAN_1] at the heart failure clinic on 10/21/2026 at 10:30 AM.",["F14"]),
 ("S16","appointments","Get a blood test at the outpatient lab on 10/18/2026.",["F15"]),
]

# S12 carries a decimal-dropping translation error (1.5 -> 15) of the kind
# machine translation makes on numbers; the checks must catch it.
es = {
 "S1":"Usted estuvo en el hospital porque su corazón no bombeaba bien y se acumuló líquido.",
 "S2":"Demasiada sal y un medicamento para el dolor llamado AINE lo empeoraron.",
 "S3":"Empiece a tomar spironolactone 25 mg. Tómelo una vez al día.",
 "S4":"Su dosis de furosemide ahora es 40 mg. Tómela 2 veces al día, a las 8 de la mañana y a las 2 de la tarde.",
 "S5":"Deje de tomar ibuprofen.",
 "S6":"Deje de tomar lisinopril. No lo vuelva a tomar.",
 "S7":"Empiece a tomar sacubitril/valsartan 24/26 mg, 2 veces al día.",
 "S8":"Espere al menos 36 horas después de su última dosis de lisinopril antes de su primera dosis de sacubitril/valsartan.",
 "S9":"Siga tomando metoprolol succinate 50 mg una vez al día, igual que antes.",
 "S10":"Llame al 911 o vaya a la sala de emergencias si tiene dolor de pecho, dificultad para respirar en reposo o se desmaya.",
 "S11":"Coma menos de 2 gramos de sal al día.",
 "S12":"No beba más de 15 litros de líquido al día.",
 "S13":"Pésese cada mañana después de orinar y antes del desayuno. Anótelo.",
 "S14":"Camine lo que le resulte cómodo. No levante más de 10 libras durante 2 semanas.",
 "S15":"Vea a [CLINICIAN_1] en la clínica de insuficiencia cardíaca el 10/21/2026 a las 10:30 de la mañana.",
 "S16":"Hágase un análisis de sangre en el laboratorio ambulatorio el 10/18/2026.",
}
back = {
 "S1":"You were in the hospital because your heart was not pumping well and fluid accumulated.",
 "S2":"Too much salt and a medicine for pain called NSAID made it worse.",
 "S3":"Start taking spironolactone 25 mg. Take it once a day.",
 "S4":"Your dose of furosemide now is 40 mg. Take it 2 times a day, at 8 in the morning and at 2 in the afternoon.",
 "S5":"Stop taking ibuprofen.",
 "S6":"Stop taking lisinopril. Do not take it again.",
 "S7":"Start taking sacubitril/valsartan 24/26 mg, 2 times a day.",
 "S8":"Wait at least 36 hours after your last dose of lisinopril before your first dose of sacubitril/valsartan.",
 "S9":"Keep taking metoprolol succinate 50 mg once a day, the same as before.",
 "S10":"Call 911 or go to the emergency room if you have chest pain, difficulty breathing at rest, or you faint.",
 "S11":"Eat less than 2 grams of salt per day.",
 "S12":"Do not drink more than 15 liters of liquid per day.",
 "S13":"Weigh yourself every morning after urinating and before breakfast. Write it down.",
 "S14":"Walk what is comfortable for you. Do not lift more than 10 pounds for 2 weeks.",
 "S15":"See [CLINICIAN_1] at the heart failure clinic on 10/21/2026 at 10:30 in the morning.",
 "S16":"Get a blood test at the outpatient laboratory on 10/18/2026.",
}
judge = {sid: ("supported", "Matches the cited facts.") for sid in es}
judge["S5"] = ("partially_supported", "Source says hold until kidney recheck; sentence reads as a permanent stop.")
judge["S12"] = ("contradicts", "Back-translation says 15 liters; the fact says 1.5 L per day.")

suggest = {
 "F9": {"text_en": "Call the heart clinic at [PHONE_1] if your weight goes up more than 2 pounds in one day or 5 pounds in one week, or if your legs swell more.",
        "text_tl": "Llame a la clínica del corazón al [PHONE_1] si su peso sube más de 2 libras en un día o 5 libras en una semana, o si sus piernas se hinchan más."},
 "F4": {"text_en": "Do not take ibuprofen until your heart doctor checks your kidneys again and says it is OK.",
        "text_tl": "No tome ibuprofen hasta que su cardiólogo vuelva a revisar sus riñones y le diga que puede tomarlo."},
}

timings = {  # placeholders until a recorded MI300X run replaces this file
}
data = {
 "_meta": {"source": "scripted", "note": "Hand-written sample run for demo without a GPU. Replace with a recorded AMD MI300X run (scripts/record_samples.py)."},
 "facts": {"en": {"facts": facts}},
 "draft": {"en": {"sentences": [{"id": i, "section": sec, "text": t, "fact_ids": f} for i, sec, t, f in draft]}},
 "translate": {"es": {"items": [{"id": k, "text": v} for k, v in es.items()]}},
 "back_translate": {"es": {"items": [{"id": k, "text": v} for k, v in back.items()]}},
 "judge": {"es": {"verdicts": [{"id": k, "verdict": v, "reason": r} for k, (v, r) in judge.items()]}},
 "suggest": {f"es:{k}": v for k, v in suggest.items()},
}
pathlib.Path(__file__).resolve().parent.parent.joinpath("data/replay/hf-maria-es.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
print("ok")
