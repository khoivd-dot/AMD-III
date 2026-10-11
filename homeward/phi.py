"""Mask direct identifiers before any text reaches a model or a log.

The map from placeholder back to the real value lives only in memory on the
case object and is applied at the very end, when the signed-off packet is
shown to the patient.

Rules, not a model: every pattern below is readable and testable. They cover
labels in each supported language, because Spanish, Italian, French and
Vietnamese documents are the normal case here, not the edge case. Free-text
names with no label or title can still slip through; a de-identification
model as a second pass is the next step for production.
"""

import re
import unicodedata
from dataclasses import dataclass, field

# A name word in any Latin script, with accents, apostrophes and hyphens: José, Núñez, O'Brien-Smith, Nguyễn.
_UPPER = "[" + "".join(re.escape(chr(c)) for r in ((0x41, 0x5B), (0xC0, 0x250), (0x1E00, 0x1F00))
                       for c in range(*r) if chr(c).isupper()) + "]"
_REST = r"[^\W\d_'’-]*(?:[-'’][^\W\d_]+)*"
_W = r"[^\W\d_]" + _REST
_CAP = _UPPER + _REST  # a capitalised name word
_NAME = rf"{_W}(?:[ ]{_W}){{0,3}}"
_HAN_NAME = r"[\u4e00-\u9fff]{2,4}"

_NAME_LABELS = (r"patient(?:'s)?(?: name)?|name(?: \(last, first\))?|full name|nombre(?: del paciente)?|paciente|"
                r"paziente|nome(?: del paziente)?|nom(?: du patient)?|patiente?|bệnh nhân|họ (?:và )?tên|tên")
_KIN = (r"daughter|son|wife|husband|mother|father|sister|brother|caregiver|carer|partner|niece|nephew|granddaughter|"
        r"grandson|next of kin|emergency contact|contact|hija|hijo|esposa|esposo|madre|padre|cuidadora?|familiar|"
        r"figlia|figlio|moglie|marito|fille|fils|épouse|mari|con gái|con trai|vợ|chồng|người chăm sóc")
_TITLES = r"Dr\.?|Doctor|Dott\.(?:ssa)?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?|Miss|Nurse|Sr\.|Sra\.|Srta\.|Sig\.(?:ra)?|Mme|Mlle|M\.|Ông|Bà|Bác sĩ|BS\."
_CLINICIAN_TITLES = ("dr", "doctor", "dott", "prof", "nurse", "bac si", "bs")  # accent-folded

_LABELLED_NAME = re.compile(rf"(?i:\b(?:{_NAME_LABELS}))[ \t]*[:：][ \t]*({_NAME}(?:,[ ]{_W}(?:[ ]{_W})?)?)")
_HAN_LABELLED = re.compile(rf"(?:姓名|患者|病人|家属|联系人)[ \t]*[:：][ \t]*({_HAN_NAME})")
_KIN_NAME = re.compile(rf"(?i:\b(?:{_KIN}))\b[ \t]*(?:[:(),]|is|es|è|est|là)?[ \t]*({_CAP}(?:[ ]{_CAP}){{0,2}})")
_TITLED = re.compile(rf"(?<!\w)({_TITLES})[ ]+({_CAP}(?:[ ]{_CAP}){{0,2}})")
_CREDENTIALED = re.compile(rf"\b({_CAP}(?:[ ]{_CAP}){{1,2}}),[ ]*(MD|RN|NP|PA|DO|PhD|MBBS|FRCS|BSN)\b")

_DATE = (r"\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}|\d{1,2}(?:st|nd|rd|th)?[ ](?:de[ ])?[A-Za-zÀ-ÿ]{3,10}\.?(?:[ ]de)?[ ]\d{4}|"
         r"[A-Za-zÀ-ÿ]{3,10}\.?[ ]\d{1,2}(?:st|nd|rd|th)?,?[ ]\d{4}|\d{4}年\d{1,2}月\d{1,2}日|"
         r"ngày[ ]\d{1,2}[ ]tháng[ ]\d{1,2}[ ]năm[ ]\d{4}")

_PATTERNS = [
    ("MRN", re.compile(r"(?i:\b(?:MRN|Medical Record(?: Number| No\.?)?|Patient ID|Hospital (?:no\.?|number)|Record(?: no\.?| number)?|"
                       r"NHS (?:no\.?|number)|N[º°o]\.? de historia(?: clínica)?|Historia clínica|Cartella clinica|"
                       r"N° de dossier|Mã (?:bệnh nhân|hồ sơ)|病历号|住院号))\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{3,})")),
    ("ID", re.compile(r"(?i:\b(?:Insurance(?: ID| no\.?| number)?|Member(?: ID)?|Policy(?: no\.?| number)?|Medicare|Medicaid|"
                      r"Seguro|Tarjeta sanitaria|Tessera sanitaria|Codice fiscale|Sécurité sociale|Mutuelle|"
                      r"(?:Mã|Số) (?:BHYT|bảo hiểm)|医保卡?号?))\s*(?:ID|No\.?|number|#)?\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})")),
    ("ID", re.compile(r"(?<![\d-])(\d{3}-\d{2}-\d{4})(?![\d-])")),  # US SSN
    ("DATE_OF_BIRTH", re.compile(rf"(?i:\b(?:DOB|D\.O\.B\.|Date of Birth|Born(?: on)?|Fecha de nacimiento|F\. nac\.|Nacido el|"
                                 rf"Nacida el|Data di nascita|Nato il|Nata il|Date de naissance|Né le|Née le|Ngày sinh)|出生日期)"
                                 rf"\s*[:#]?\s*({_DATE})")),
    ("DATE", re.compile(rf"(?i:\b(?:Admission|Admit|Admitted|Discharge|Discharged)(?: date)?|Fecha de (?:ingreso|alta)|"
                        rf"Data di (?:ricovero|dimissione)|Date d'(?:admission|entrée|hospitalisation)|Date de sortie|"
                        rf"Ngày (?:nhập viện|ra viện)|(?:入院|出院)日期)\s*(?:on)?\s*[:#]?\s*({_DATE})")),
    ("EMAIL", re.compile(r"\b([\w.+-]+@[\w-]+\.[\w.]+)\b")),
    ("PHONE", re.compile(r"(?<![\w+])(\+\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,5}\d{2,4})\b")),  # international
    ("PHONE", re.compile(r"(?<![\d/])(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\b")),            # US
    ("PHONE", re.compile(r"(?<![\d/])(\(0\d{2,4}\)[ -]?\d{3,4}[ -]?\d{3,4}|0\d{2,4}[ -]\d{3,4}[ -]\d{3,4}|0\d{4}[ ]?\d{6})\b")),
    ("PHONE", re.compile(r"(?i:\b(?:call|phone|tel\.?|telephone|ring|llame|llamar|teléfono|chiami|telefono|appelez|téléphone|"
                         r"gọi|điện thoại|电话)\b[^.\n\d]{0,25})(\d{3}-\d{4})\b")),
    ("ADDRESS", re.compile(r"\b(\d{1,5}[A-Z]?\s+(?:[A-Z][\w'’-]+\s){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|"
                           r"Boulevard|Blvd|Court|Ct|Way|Place|Pl|Terrace|Close|Crescent)\.?)(?=[\s,;.]|$)")),
    ("ADDRESS", re.compile(r"\b(\d{1,5},?\s+(?i:rue|avenue|boulevard|place|chemin|allée|impasse|via|viale|calle)\s+"
                           r"(?:[\w'’-]+(?:[ ](?=[\w'’-]))?){1,4})")),
    ("ADDRESS", re.compile(r"\b((?:Calle|Avenida|Av\.|Paseo|Plaza|Carrer|Via|Viale|Piazza|Corso|Rue|Avenue|Boulevard|Chemin|"
                           r"Đường|Phố)\s+(?:[\w'’-]+\s?){1,4},?\s*\d{1,5}[A-Za-z]?(?:,\s*\d+[A-Z]?)?)")),
    ("ADDRESS", re.compile(r"\b(P\.?\s?O\.?\s+Box\s+\d+|Apartado(?: de correos)?\s+\d+|Casella postale\s+\d+)", re.I)),
    ("ADDRESS", re.compile(r"\b((?:[A-Z][a-z]+ ){0,2}[A-Z][a-z]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)\b")),  # San Jose, CA 95112
    ("ADDRESS", re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b")),                                  # UK postcode
    ("ADDRESS", re.compile(r"\b(\d{5}\s+(?!Units?\b|IU\b)[A-ZÀ-Ý][a-zà-ÿ]{2,}(?:[ -][A-ZÀ-Ý][a-zà-ÿ]+)?)\b")),  # 75002 Paris
]

# Words that are also given names. A part of a known name that is one of these is
# masked only as part of the full name, so "Max 4 tablets" keeps its meaning.
_COMMON = set("""max mark hope grace iron will may june april august rose faith joy dawn eve frank bill art rich sue pat
ray gene grant lane rob jack drew dale glen guy jay lee long white black brown green young king price hill wood stone rice
bell cook hunter miles page rush sharp shaw love day summer river sky star penny ivy ruby pearl amber clay cliff chase
hale ward early sage march ben bud chance chip dean don duke earl ernest gray hardy hunt lincoln mason mercy noble
patience prudence sunny tom sol santos luz paz rosa dolores mercedes""".split())

# 24-hour dosing times ("0800 1400 2000") are not phone numbers.
_HHMM_RUN = re.compile(r"(?:[01]\d|2[0-3])[0-5]\d(?:[\s-]+(?:[01]\d|2[0-3])[0-5]\d)+")


def _fold(text: str) -> str:
    """Lower-case, accent-free copy of the text with the same length, for matching."""
    out = []
    for ch in text:
        if ch in "Đđ":
            out.append("d")
            continue
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
        out.append((base[:1] or ch).lower())
    return "".join(out)


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
        key = (kind, _fold(value.strip()))
        if key not in reverse:
            counters[kind] = counters.get(kind, 0) + 1
            token = f"[{kind}_{counters[kind]}]"
            reverse[key] = token
            mapping[token] = value.strip()
        return reverse[key]

    def replace_folded(text: str, needle: str, token: str, whole_word: bool = True, capitalised: bool = False) -> str:
        """Replace every accent- and case-insensitive occurrence of needle."""
        folded, target = _fold(text), _fold(needle)
        if not target:
            return text
        pattern = re.compile((r"(?<![^\W_])" if whole_word else "") + re.escape(target) + (r"(?![^\W_])" if whole_word else ""))
        out, last = [], 0
        for m in pattern.finditer(folded):
            if capitalised and not text[m.start()].isupper():
                continue
            out.append(text[last:m.start()])
            out.append(token)
            last = m.end()
        out.append(text[last:])
        return "".join(out)

    # Names first, so "Patient: Maria Lopez" and later "Maria" share one token.
    names = [n for n in (known_names or []) if n and n.strip()]
    names += [m.group(1) for m in _LABELLED_NAME.finditer(text)]
    names += [m.group(1) for m in _HAN_LABELLED.finditer(text)]
    for full in sorted({n.strip().rstrip(",") for n in names}, key=len, reverse=True):
        token = placeholder("PATIENT", full)
        variants = {full}
        if "," in full:  # "O'Brien-Smith, Mary" is also "Mary O'Brien-Smith"
            last, first = [x.strip() for x in full.split(",", 1)]
            variants |= {f"{first} {last}", last, first}
        han = bool(re.fullmatch(_HAN_NAME, full))
        for v in sorted(variants, key=len, reverse=True):
            text = replace_folded(text, v, token, whole_word=not han)
        if han:
            continue
        for part in re.split(r"[\s,]+", full):
            if len(part) > 2 and _fold(part) not in _COMMON:
                text = replace_folded(text, part, token, capitalised=True)

    for m in list(_KIN_NAME.finditer(text)):
        name = m.group(1)
        if not name.startswith("["):  # a kin label is context enough, even for "Rosa" or "Grace"
            text = replace_folded(text, name, placeholder("CONTACT", name), capitalised=True)

    def titled(m: re.Match) -> str:
        title, name = m.group(1), m.group(2)
        kind = "CLINICIAN" if _fold(title).rstrip(".").startswith(_CLINICIAN_TITLES) else "PATIENT"
        # "Dr. Patel" later in the text is the same person as "Dr. Anil Patel".
        surname = _fold(name.split()[-1])
        for (k, value), token in reverse.items():
            if k == kind and value.split()[-1] == surname:
                return token
        return placeholder(kind, f"{title} {name}")

    text = _TITLED.sub(titled, text)
    text = _CREDENTIALED.sub(lambda m: placeholder("CLINICIAN", m.group(0)), text)

    for kind, pattern in _PATTERNS:
        def repl(m: re.Match, kind=kind) -> str:
            value = m.group(m.lastindex or 0)
            if kind == "PHONE" and _HHMM_RUN.fullmatch(value.strip()):
                return m.group(0)
            return m.group(0).replace(value, placeholder(kind, value))
        text = pattern.sub(repl, text)

    return Masked(text=text, mapping=mapping)


PLACEHOLDER = re.compile(r"\[(?:PATIENT|CLINICIAN|CONTACT|MRN|ID|DATE_OF_BIRTH|DATE|EMAIL|PHONE|ADDRESS)_\d+\]")


def placeholders_in(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text or ""))
