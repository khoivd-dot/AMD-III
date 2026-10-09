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
    r"\bkeep taking\b", r"\bcontinue\b", r"\bcontinuing\b", r"\bsame as before\b",
    r"\bas usual\b", r"\bstill take\b",
    # Negated stops: "do not stop", "must not stop", "never stop", "do not hold", "don't pause".
    r"\b(?:not|never|n't)\s+(?:\w+\s+){0,2}?(?:stop|hold|pause|quit|skip)\b",
]
STOP_CUES = [
    r"\bstop\b", r"\bstopped\b", r"\bdo not take\b", r"\bdon'?t take\b", r"\bno longer\b",
    r"\bhold\b", r"\bpause\b", r"\bavoid\b", r"\bdo not use\b", r"\bdon'?t use\b",
    r"\bnot take\b", r"\bnot to take\b", r"\bnot use\b", r"\bquit\b",
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
    for p in CONTINUE_CUES:
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
