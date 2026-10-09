"""Deterministic vocabularies used by the verifier.

Kept deliberately small and explicit: every entry here is something a
reviewer can read and audit, unlike a model's judgement.
"""

import re

# Generic names (and a few common brand names mapped to generics).
DRUGS = {
    "acetaminophen", "paracetamol", "ibuprofen", "naproxen", "aspirin", "celecoxib",
    "furosemide", "torsemide", "bumetanide", "hydrochlorothiazide", "chlorthalidone",
    "spironolactone", "eplerenone", "lisinopril", "enalapril", "ramipril", "losartan",
    "valsartan", "sacubitril", "metoprolol", "carvedilol", "bisoprolol", "atenolol",
    "amlodipine", "diltiazem", "verapamil", "digoxin", "amiodarone", "atorvastatin",
    "rosuvastatin", "simvastatin", "pravastatin", "warfarin", "apixaban", "rivaroxaban",
    "dabigatran", "edoxaban", "enoxaparin", "heparin", "clopidogrel", "ticagrelor",
    "prasugrel", "nitroglycerin", "isosorbide", "hydralazine", "dapagliflozin",
    "empagliflozin", "metformin", "glipizide", "glyburide", "glimepiride", "sitagliptin",
    "insulin", "semaglutide", "liraglutide", "levothyroxine", "prednisone",
    "prednisolone", "methylprednisolone", "dexamethasone", "albuterol", "salbutamol",
    "ipratropium", "tiotropium", "budesonide", "fluticasone", "formoterol", "salmeterol",
    "montelukast", "amoxicillin", "clavulanate", "azithromycin", "doxycycline",
    "cephalexin", "cefuroxime", "ceftriaxone", "levofloxacin", "ciprofloxacin",
    "nitrofurantoin", "trimethoprim", "sulfamethoxazole", "metronidazole", "vancomycin",
    "oxycodone", "hydrocodone", "morphine", "hydromorphone", "fentanyl", "tramadol",
    "methadone", "codeine", "tapentadol", "gabapentin", "pregabalin", "ondansetron",
    "metoclopramide", "docusate", "senna", "polyethylene", "omeprazole", "pantoprazole",
    "famotidine", "sertraline", "escitalopram", "fluoxetine", "trazodone", "mirtazapine",
    "quetiapine", "haloperidol", "lorazepam", "alprazolam", "diazepam", "zolpidem",
    "methotrexate", "allopurinol", "colchicine", "potassium", "magnesium", "iron",
    "tamsulosin", "finasteride", "oxybutynin", "cyclobenzaprine", "baclofen",
}

BRANDS = {
    "lasix": "furosemide", "eliquis": "apixaban", "xarelto": "rivaroxaban",
    "coumadin": "warfarin", "tylenol": "acetaminophen", "advil": "ibuprofen",
    "motrin": "ibuprofen", "aleve": "naproxen", "entresto": "sacubitril",
    "jardiance": "empagliflozin", "farxiga": "dapagliflozin", "lantus": "insulin",
    "humalog": "insulin", "novolog": "insulin", "percocet": "oxycodone",
    "norco": "hydrocodone", "zofran": "ondansetron", "lipitor": "atorvastatin",
    "toprol": "metoprolol", "plavix": "clopidogrel", "ventolin": "albuterol",
    "tachipirina": "paracetamol", "brufen": "ibuprofen", "oki": "ketoprofen",
}

# ISMP high-alert medication classes, reduced to what appears on discharge lists.
HIGH_ALERT = {
    "warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban", "enoxaparin",
    "heparin", "insulin", "oxycodone", "hydrocodone", "morphine", "hydromorphone",
    "fentanyl", "tramadol", "methadone", "codeine", "tapentadol", "digoxin",
    "methotrexate", "glipizide", "glyburide", "glimepiride", "amiodarone",
    "clopidogrel", "ticagrelor", "prasugrel", "potassium",
}

# Paracetamol and acetaminophen are the same drug; treat them as one.
SYNONYMS = {"paracetamol": "acetaminophen", "salbutamol": "albuterol"}

_WORD = re.compile(r"[A-Za-zÀ-ÿ]+")


def canonical_drug(name: str | None) -> str | None:
    if not name:
        return None
    for token in _WORD.findall(name.lower()):
        token = BRANDS.get(token, token)
        if token in DRUGS or token in BRANDS.values():
            return SYNONYMS.get(token, token)
    return None


def drugs_in(text: str) -> set[str]:
    found = set()
    for token in _WORD.findall(text.lower()):
        token = BRANDS.get(token, token)
        if token in DRUGS or token in BRANDS.values():
            found.add(SYNONYMS.get(token, token))
    return found


def drugs_in_order(text: str) -> list[str]:
    found = []
    for token in _WORD.findall(text.lower()):
        token = BRANDS.get(token, token)
        if token in DRUGS or token in BRANDS.values():
            token = SYNONYMS.get(token, token)
            if token not in found:
                found.append(token)
    return found


def is_high_alert(drug: str | None) -> bool:
    return canonical_drug(drug) in HIGH_ALERT if drug else False


# Polarity cues are checked on English text (the draft, or the back-translation).
CONTINUE_CUES = [
    r"\bkeep (?:taking|using)\b", r"\bcontinue\b", r"\bcontinuing\b", r"\bsame as before\b",
    r"\bas usual\b", r"\bstill (?:take|use)\b",
    # Negated stops: "do not stop", "must not stop", "never stop", "do not hold", "don't pause".
    r"\b(?:not|never|n't)\s+(?:\w+\s+){0,2}?(?:stop|hold|pause|quit|skip)\b",
]
STOP_CUES = [
    r"\bstop\b", r"\bstopped\b", r"\bdo not take\b", r"\bdon'?t take\b", r"\bno longer\b",
    r"\bhold\b", r"\bpause\b", r"\bavoid\b", r"\bdo not use\b", r"\bdon'?t use\b",
    r"\bnot take\b", r"\bnot to take\b", r"\bnot use\b", r"\bquit\b", r"\bsuspend\b",
    r"\bdiscontinue[ds]?\b",
]
# Phrases that contain a stop word but are not a stop order: a dose limit, or the
# condition under which a clinician might stop it later.
NOT_A_STOP = [
    r"\b(?:do not|don't|never|not)\s+(?:take|use|have)\s+more than\b[^.;]*",
    r"\b(?:unless|until|without (?:first )?(?:talking|speaking|asking|checking))\b[^.;]*",
]
TEMPORARY_CUES = [
    r"\buntil\b", r"\bfor now\b", r"\bagain\b", r"\bfor the next\b", r"\bfor \d+ days\b",
    r"\btemporar", r"\bfor a while\b", r"\bfor a few days\b", r"\bfor now\b",
]


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def polarity(text: str) -> dict:
    """Classify an English sentence's instruction about a medicine."""
    lowered = text.lower()
    continues = _any(CONTINUE_CUES, lowered)
    # "do not stop" contains "stop"; strip continue phrases before looking for stop cues.
    stripped = lowered
    for p in NOT_A_STOP + CONTINUE_CUES:
        stripped = re.sub(p, " ", stripped)
    stops = _any(STOP_CUES, stripped)
    temporary = _any(TEMPORARY_CUES, lowered)
    return {"continue": continues, "stop": stops, "temporary": temporary}


# Languages Homeward will translate into. Anything else routes to an interpreter.
LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "it": "Italian",
    "vi": "Vietnamese",
    "zh": "Simplified Chinese",
    "fr": "French",
}


# --------------------------------------------------------- other languages
# Checked on the forward translation itself, because a back-translation can smooth
# over exactly the error it should reveal ("Tiếp tục uống" read back as "do not take").

TL_CUES = {
    "es": {"continue": [r"\bsiga (?:tomando|usando)", r"\bcontin[uú]e", r"\bno deje de\b", r"\bsigue (?:tomando|usando)"],
           "stop": [r"\bdeje de\b", r"\bsuspend[ae]", r"\bno (?:tome|use|lo tome)\b", r"\bpare de\b", r"\binterrump[ae]"],
           "prn": [r"seg[uú]n (?:la )?necesidad", r"si (?:el|le) duele", r"si (?:tiene )?(?:el )?dolor", r"si (?:es|lo) necesari[oa]", r"si lo necesita", r"\bsolo (?:si|cuando)\b", r"cuando lo necesite",
                   r"seg[uú]n sea necesario", r"en caso necesario"],
           "am": [r"de la mañana", r"\ba\.\s?m\."], "pm": [r"de la tarde", r"de la noche", r"\bp\.\s?m\."],
           "salt": [r"\bsal\b"], "sodium": [r"\bsodio\b"]},
    "it": {"continue": [r"\bcontinui\b", r"\bcontinuare\b", r"\bnon smetta\b", r"\bnon interrompa\b", r"\bprosegua\b"],
           "stop": [r"\bsmett[ae]\b", r"\bsospend[ai]\b", r"\binterromp[ai]\b", r"\bnon (?:prenda|assuma|usi)\b"],
           "prn": [r"secondo necessit[àa]", r"se (?:il|ha) dolore", r"se (?:le )?fa male", r"se necessari[oa]", r"al bisogno", r"\bsolo (?:se|quando)\b", r"quando serve", r"se serve",
                   r"in caso di bisogno"],
           "am": [r"del mattino", r"di mattina"], "pm": [r"del pomeriggio", r"di sera", r"della sera"],
           "salt": [r"\bsale\b"], "sodium": [r"\bsodio\b"]},
    "fr": {"continue": [r"\bcontinuez\b", r"\bcontinuer\b", r"\bn'arr[êe]tez pas\b", r"\bne cessez pas\b"],
           "stop": [r"\barr[êe]tez\b", r"\bcessez\b", r"\bne prenez pas\b", r"\bn'utilisez pas\b", r"\bsuspendez\b",
                    r"\binterrompez\b"],
           "prn": [r"selon (?:les|vos|le) besoins?", r"si (?:la|vous avez (?:de la|mal)) douleur", r"si vous avez mal", r"si besoin", r"au besoin", r"si n[ée]cessaire", r"\b(?:seulement|uniquement) (?:si|quand)\b",
                   r"en cas de besoin"],
           "am": [r"du matin"], "pm": [r"de l'apr[èe]s-midi", r"du soir"],
           "salt": [r"\bsel\b"], "sodium": [r"\bsodium\b"]},
    "vi": {"continue": [r"tiếp tục", r"(?:đừng|không được|không) (?:tự )?(?:ngừng|ngưng|dừng)"],
           "stop": [r"ngừng", r"ngưng", r"dừng", r"không (?:uống|dùng|sử dụng)", r"thôi uống"],
           "prn": [r"nếu (?:bị )?đau", r"khi (?:bị )?đau", r"khi (?:nào )?cần", r"nếu cần", r"chỉ khi"],
           "am": [r"sáng", r"\bSA\b"], "pm": [r"chiều", r"tối", r"\bCH\b"],
           "salt": [r"muối"], "sodium": [r"natri"]},
    "zh": {"continue": [r"继续", r"不要停", r"别停", r"不要自行停"],
           "stop": [r"停止", r"停用", r"停服", r"不要(?:服用|使用|吃)", r"暂停"],
           "prn": [r"疼痛时", r"如果疼", r"疼的时候", r"需要时", r"必要时", r"只在", r"仅在", r"如有需要", r"有需要时"],
           "am": [r"上午", r"早上", r"早晨"], "pm": [r"下午", r"晚上"],
           "salt": [r"盐"], "sodium": [r"钠"]},
    "en": {"prn": [r"\bas needed\b", r"\bif (?:you )?need(?:ed)?\b", r"\bwhen (?:you )?need(?:ed)?\b", r"\bonly (?:if|when)\b",
                   r"\bprn\b", r"\b(?:if|when) (?:you have|you feel|the pain|your pain|pain)\b"],
           "am": [r"\ba\.?m\.?(?![a-z])"], "pm": [r"\bp\.?m\.?(?![a-z])"],
           "salt": [r"\bsalt\b"], "sodium": [r"\bsodium\b"]},
}


def has_cue(text: str, lang: str, cue: str) -> bool:
    return _any(TL_CUES.get(lang, {}).get(cue, []), text or "")


def polarity_tl(text: str, lang: str) -> dict:
    """Stop or keep-taking reading of a translated sentence (whole sentence)."""
    if lang == "en":
        return polarity(text)
    cues = TL_CUES.get(lang)
    if not cues:
        return {"continue": False, "stop": False, "temporary": False}
    lowered = (text or "").lower()
    stripped = lowered
    for p in cues["continue"]:
        stripped = re.sub(p, " ", stripped)
    return {"continue": _any(cues["continue"], lowered), "stop": _any(cues["stop"], stripped), "temporary": False}


REASSURANCE = [r"\b(?:is|are|it's|that's) (?:normal|common|expected|harmless)\b", r"\bnothing to worry\b",
               r"\b(?:do not|don't|no need to) worry\b", r"\bwill (?:pass|go away|get better on its own)\b"]

LIMIT = r"\b(?:more than|no more than|maximum|max\.?|at most|up to|exceed)\b"
