"""Mask direct identifiers before any text reaches a model or a log.

The map from placeholder back to the real value lives only in memory on the
case object and is applied at the very end, when the signed-off packet is
shown to the patient.
"""

import re
from dataclasses import dataclass, field

_PATTERNS = [
    ("MRN", re.compile(r"\b(?:MRN|Medical Record(?: Number)?|Patient ID)\s*[:#]?\s*([A-Z0-9-]{4,})", re.I)),
    ("DATE_OF_BIRTH", re.compile(r"\b(?:DOB|Date of Birth|D\.O\.B\.)\s*[:#]?\s*([0-9]{1,4}[/.-][0-9]{1,2}[/.-][0-9]{1,4})", re.I)),
    ("EMAIL", re.compile(r"\b([\w.+-]+@[\w-]+\.[\w.]+)\b")),
    ("PHONE", re.compile(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\b")),
    ("PHONE", re.compile(r"(?<![\d/])(0\d{2,4}[ -]\d{3,4}[ -]\d{3,4})\b")),
    ("ADDRESS", re.compile(r"\b(\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Via|Court|Ct)\.?)(?=[\s,]|$)")),
]
_NAME_LABEL = re.compile(r"\b(?:Patient(?: name)?|Name)[ \t]*:[ \t]*([A-Z][a-zA-Z'-]+(?:[ ][A-Z][a-z][a-zA-Z'-]*){0,3})")
_TITLED = re.compile(r"\b(Dr\.?|Doctor|Mr\.?|Mrs\.?|Ms\.?|Nurse)[ ]+([A-Z][a-zA-Z'-]+(?:[ ][A-Z][a-z][a-zA-Z'-]*)?)")


@dataclass
class Masked:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original

    def unmask(self, text: str) -> str:
        for placeholder, original in self.mapping.items():
            text = text.replace(placeholder, original)
        return text

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for placeholder in self.mapping:
            kind = placeholder.strip("[]").rsplit("_", 1)[0]
            out[kind] = out.get(kind, 0) + 1
        return out


def mask(text: str, known_names: list[str] | None = None) -> Masked:
    mapping: dict[str, str] = {}
    reverse: dict[tuple[str, str], str] = {}
    counters: dict[str, int] = {}

    def placeholder(kind: str, value: str) -> str:
        key = (kind, value.strip().lower())
        if key not in reverse:
            counters[kind] = counters.get(kind, 0) + 1
            token = f"[{kind}_{counters[kind]}]"
            reverse[key] = token
            mapping[token] = value.strip()
        return reverse[key]

    # Names first, so "Patient: Maria Lopez" and later "Maria" share one token.
    names = list(known_names or [])
    names += [m.group(1) for m in _NAME_LABEL.finditer(text)]
    for full in sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True):
        token = placeholder("PATIENT", full)
        text = re.sub(re.escape(full), token, text)
        for part in full.split():
            if len(part) > 2:
                text = re.sub(rf"\b{re.escape(part)}\b", token, text)

    def titled(m: re.Match) -> str:
        title, name = m.group(1), m.group(2)
        kind = "CLINICIAN" if title.lower().startswith(("dr", "doctor", "nurse")) else "PATIENT"
        # "Dr. Patel" later in the text is the same person as "Dr. Anil Patel".
        surname = name.split()[-1].lower()
        for (k, value), token in reverse.items():
            if k == kind and value.split()[-1] == surname:
                return token
        return placeholder(kind, f"{title} {name}")

    text = _TITLED.sub(titled, text)

    for kind, pattern in _PATTERNS:
        def repl(m: re.Match, kind=kind) -> str:
            value = m.group(m.lastindex or 0)
            return m.group(0).replace(value, placeholder(kind, value))
        text = pattern.sub(repl, text)

    return Masked(text=text, mapping=mapping)


PLACEHOLDER = re.compile(r"\[(?:PATIENT|CLINICIAN|MRN|DATE_OF_BIRTH|EMAIL|PHONE|ADDRESS)_\d+\]")


def placeholders_in(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text or ""))
