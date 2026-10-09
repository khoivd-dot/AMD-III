"""Number extraction, readability and fuzzy matching. No model calls."""

import re
from difflib import SequenceMatcher

# ASCII-only lookbehind: in Chinese a digit sits right next to a character ("14单位"),
# and \w would match that character and hide the number.
_NUM = re.compile(r"(?<![0-9A-Za-z.])\d+(?:[.,]\d+)?")
_PLACEHOLDER = re.compile(r"\[[A-Z_]+_\d+\]")
_HOUR_H = re.compile(r"\b(\d{1,2})\s?h\s?(\d{2})\b")  # French "11h00", "11 h 00"
_WORD_NUMBERS = {
    "once": "1", "twice": "2", "thrice": "3",
    "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
    "bid": "2", "b.i.d": "2", "tid": "3", "t.i.d": "3", "qid": "4", "q.i.d": "4",
    "half": "0.5",
}
_WORD_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in _WORD_NUMBERS) + r")\b", re.I)


def _norm(num: str) -> str:
    num = num.replace(",", ".")
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    return num.lstrip("0") or "0"


def numbers_in(text: str, words: bool = True) -> set[str]:
    """All numeric values in a text, normalised (2,5 == 2.5, 'twice' == 2)."""
    if not text:
        return set()
    # Drop thousands separators like 1,000 before the decimal-comma logic.
    cleaned = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    cleaned = _PLACEHOLDER.sub(" ", cleaned)  # [CLINICIAN_1] holds no number
    cleaned = _HOUR_H.sub(r"\1:\2", cleaned)
    found = {_norm(m) for m in _NUM.findall(cleaned)}
    if words:
        found |= {_WORD_NUMBERS[m.lower()] for m in _WORD_RE.findall(cleaned)}
    return found


def digits_in(text: str) -> set[str]:
    """Numbers written as digits only; used to compare across languages."""
    return numbers_in(text, words=False)


_VOWELS = re.compile(r"[aeiouy]+")


def _syllables(word: str) -> int:
    word = word.lower().strip(".,;:!?'\"()")
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    word = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", word)
    word = re.sub(r"^y", "", word)
    return max(1, len(_VOWELS.findall(word)))


def fk_grade(text: str) -> float:
    """Flesch-Kincaid grade level for English text."""
    sentences = [s for s in re.split(r"[.!?]+(?:\s|$)|\n+", text) if re.search(r"[A-Za-z]", s)]
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if not sentences or not words:
        return 0.0
    syl = sum(_syllables(w) for w in words)
    grade = 0.39 * (len(words) / len(sentences)) + 11.8 * (syl / len(words)) - 15.59
    return round(max(grade, 0.0), 1)


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.]", " ", text.lower())).strip()


def quote_in_source(quote: str, source: str, threshold: float = 0.85) -> bool:
    """True when the quote appears in the source, allowing small differences."""
    q, s = _squash(quote), _squash(source)
    if not q:
        return False
    if q in s:
        return True
    # Slide a window the size of the quote over the source and take the best ratio.
    n = len(q)
    best = 0.0
    step = max(1, n // 8)
    for i in range(0, max(1, len(s) - n + 1), step):
        best = max(best, SequenceMatcher(None, q, s[i:i + n]).ratio())
        if best >= threshold:
            return True
    return False


# ------------------------------------------------------------- quantities

# Units in every supported language, mapped to one name. A number's unit must survive
# drafting and translation: mcg -> mg or units -> mL is a 1000x or wrong-route error.
UNITS = {
    "mg": ["mg", "milligrams?", "milligrammes?", "miligramos?", "milligrammi", "毫克", "mg"],
    "mcg": ["mcg", "µg", "μg", "micrograms?", "microgrammes?", "microgramos?", "microgrammi", "微克"],
    "g": ["g", "grams?", "grammes?", "gramos?", "grammi", "克"],
    "kg": ["kg", "kilograms?", "kilos?", "kilogrammes?", "kilogramos?", "chilogrammi", "公斤", "千克"],
    "lb": ["lbs?", "pounds?", "libras?", "livres?", "libbre", "pao", "磅"],
    "ml": ["ml", "millilit(?:er|re)s?", "mililitros?", "millilitri", "毫升"],
    "l": ["l", "lit(?:er|re)s?", "litros?", "litri", "lít", "升"],
    "unit": ["units?", "unidad(?:es)?", "unità", "unités?", "đơn vị", "单位", "个单位"],
    "tablet": ["tablets?", "tabs?", "pills?", "tabletas?", "comprimidos?", "pastillas?", "compresse?",
               "comprimés?", "viên", "片", "粒"],
    "capsule": ["capsules?", "cápsulas?", "capsule", "gélules?", "viên nang", "胶囊"],
    "puff": ["puffs?", "inhalations?", "inhalaciones", "inhalación", "bouffées?", "spruzz[io]", "inalazion[ei]",
             "nhát(?: xịt)?", "lần xịt", "喷", "吸"],
    "spoon_tbsp": ["tablespoons?", "tbsp", "cucharadas?", "cucchiai", "cuillères? à soupe", "muỗng canh", "汤匙"],
    "spoon_tsp": ["teaspoons?", "tsp", "cucharaditas?", "cucchiaini", "cuillères? à café", "muỗng cà phê", "茶匙"],
    "drop": ["drops?", "gotas?", "gocce", "gouttes?", "giọt", "滴"],
    "minute": ["minutes?", "mins?", "minutos?", "minuti", "phút", "分钟"],
    "hour": ["hours?", "hrs?", "h", "horas?", "ore", "heures?", "giờ", "tiếng", "小时", "个小时"],
    "day": ["days?", "días?", "giorni", "giorno", "jours?", "ngày", "天", "日"],
    "week": ["weeks?", "semanas?", "settimane", "settimana", "semaines?", "tuần", "周", "星期", "个星期"],
    "month": ["months?", "meses", "mes", "mesi", "mese", "mois", "tháng", "个月"],
}
_UNIT_ALT = sorted(((alt, name) for name, alts in UNITS.items() for alt in alts), key=lambda x: -len(x[0]))
_QTY = re.compile(r"(?<![0-9A-Za-z.])(\d+(?:[.,]\d+)?)\s*(?:-|to|a|à|đến|到|至)?\s*(?:\d+(?:[.,]\d+)?)?\s*(" +
                  "|".join(f"(?:{a})" for a, _ in _UNIT_ALT) + r")(?![A-Za-zÀ-ỹ])", re.I)
_UNIT_LOOKUP = [(re.compile(f"^(?:{a})$", re.I), name) for a, name in _UNIT_ALT]


def _unit_name(token: str) -> str | None:
    for pattern, name in _UNIT_LOOKUP:
        if pattern.match(token):
            return name
    return None


def quantities(text: str) -> set[tuple[str, str]]:
    """(number, unit) pairs such as ('40', 'mg') or ('3', 'day'), in any supported language."""
    if not text:
        return set()
    cleaned = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    out = set()
    for m in _QTY.finditer(cleaned):
        unit = _unit_name(m.group(2))
        if unit:
            out.add((_norm(m.group(1)), unit))
    return out


# ------------------------------------------------------------- dates

MONTHS = {
    "en": ["january", "february", "march", "april", "may", "june", "july", "august", "september",
           "october", "november", "december"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
           "octubre", "noviembre", "diciembre"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
           "ottobre", "novembre", "dicembre"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
           "octobre", "novembre", "décembre"],
}
# A year is required: "1/2 cup" is a fraction, not 2 January.
_NUMERIC_DATE = re.compile(r"(?<![0-9/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![0-9/])")
_ISO_DATE = re.compile(r"(?<![0-9/])(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?![0-9/])")
_ZH_DATE = re.compile(r"(?:(\d{4})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")
_VI_DATE = re.compile(r"ngày\s+(\d{1,2})\s*(?:tháng\s*|/)(\d{1,2})(?:\s*(?:năm\s*|/)(\d{4}))?", re.I)


def _month_re(lang: str) -> str:
    return "|".join(MONTHS.get(lang, []) + (MONTHS["en"] if lang != "en" else []))


def dates_in(text: str, lang: str = "en") -> set[tuple]:
    """Dates as (month, day) or (year, month, day). Numeric dates are read the way a
    reader of that language would: month first in US English, day first elsewhere."""
    if not text:
        return set()
    out = set()
    rest = text

    def add(y, m, d):
        m, d = int(m), int(d)
        if 1 <= m <= 12 and 1 <= d <= 31:
            out.add((int(y), m, d) if y else (m, d))

    for pattern in (_ZH_DATE, _ISO_DATE):
        for m in pattern.finditer(rest):
            add(m.group(1), m.group(2), m.group(3))
        rest = pattern.sub(" ", rest)
    for m in _VI_DATE.finditer(rest):
        add(m.group(3), m.group(2), m.group(1))
    rest = _VI_DATE.sub(" ", rest)
    months = _month_re(lang)
    if months:
        word = re.compile(rf"\b({months})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?|"
                          rf"\b(\d{{1,2}})(?:er|º|°)?\s+(?:de\s+)?({months})(?:\s+(?:de\s+|del\s+)?(\d{{4}}))?", re.I)
        for m in word.finditer(rest):
            if m.group(1):
                name, d, y = m.group(1), m.group(2), m.group(3)
            else:
                d, name, y = m.group(4), m.group(5), m.group(6)
            name = name.lower()
            idx = next(i for lst in MONTHS.values() for i, n in enumerate(lst) if n == name)
            add(y, idx + 1, d)
        rest = word.sub(" ", rest)
    for m in _NUMERIC_DATE.finditer(rest):
        a, b, y = m.group(1), m.group(2), m.group(3)
        if len(y) == 2:
            y = "20" + y
        if lang == "en" or int(b) > 12:
            add(y, a, b)
        else:
            add(y, b, a)
    return out


def strip_dates(text: str, lang: str = "en") -> str:
    """Text with dates removed, so their digits are compared as dates, not numbers."""
    if not text:
        return ""
    text = _ZH_DATE.sub(" ", text)
    text = _ISO_DATE.sub(" ", text)
    text = _VI_DATE.sub(" ", text)
    months = _month_re(lang)
    if months:
        text = re.sub(rf"\b({months})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?|"
                      rf"\b\d{{1,2}}(?:er|º|°)?\s+(?:de\s+)?({months})(?:\s+(?:de\s+|del\s+)?\d{{4}})?",
                      " ", text, flags=re.I)
    return _NUMERIC_DATE.sub(" ", text)


def ambiguous_numeric_dates(text: str) -> list[str]:
    """Numeric dates such as 10/12/2026 that read differently in the US and elsewhere."""
    return [m.group(0) for m in _NUMERIC_DATE.finditer(text or "")
            if int(m.group(1)) <= 12 and int(m.group(2)) <= 12 and m.group(1) != m.group(2)]


def spell_dates(text: str) -> str:
    """US numeric dates in English text written with the month as a word: 10/21/2026 -> October 21, 2026."""
    def repl(m: re.Match) -> str:
        mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= mo <= 12 and 1 <= d <= 31) or len(y) != 4:
            return m.group(0)
        return f"{MONTHS['en'][mo - 1].title()} {d}, {y}"
    return _NUMERIC_DATE.sub(repl, text or "")


# ------------------------------------------------------------- clock times

_TIME = re.compile(
    r"(?<![0-9/.,])(?:(\d{1,2})\s?(?::|h)\s?(\d{2})(?![0-9])"            # 10:30, 11h00
    r"|(\d{1,2})\s?[点時](?:\s?(\d{1,2})\s?分)?"                        # 9点, 2点15分
    r"|(\d{1,2})\s?giờ(?:\s?(\d{2}))?(?=\s?(?:sáng|chiều|tối))"         # 2 giờ chiều
    r"|(\d{1,2})(?=\s?(?:[ap]\.?\s?m\b|de la (?:mañana|tarde|noche)|del (?:mattino|pomeriggio)|"
    r"di (?:mattina|sera)|della sera|du (?:matin|soir)|de l'apr[èe]s-midi)))", re.I)   # 9 PM, 8 de la mañana
_AM = {"en": r"\ba\.?\s?m\b\.?", "es": r"de la mañana|\ba\.\s?m\.", "it": r"del mattino|di mattina",
       "fr": r"du matin", "vi": r"sáng|\bSA\b", "zh": r"上午|早上|早晨|凌晨"}
_PM = {"en": r"\bp\.?\s?m\b\.?", "es": r"de la tarde|de la noche|\bp\.\s?m\.", "it": r"del pomeriggio|di sera|della sera",
       "fr": r"de l'apr[èe]s-midi|du soir", "vi": r"chiều|tối|\bCH\b", "zh": r"下午|晚上|傍晚"}


def _period(window: str, am: str, pm: str, first: bool) -> str | None:
    """The AM/PM word nearest the time: the first one after it, or the last one before it."""
    hits = [(m.start(), "am") for m in re.finditer(am, window, re.I)] + \
           [(m.start(), "pm") for m in re.finditer(pm, window, re.I)]
    if not hits:
        return None
    return (min(hits) if first else max(hits))[1]


def times_in(text: str, lang: str = "en") -> set[tuple[int, int, str]]:
    """Clock times as (hour 0-11, minute, period) with period 'am', 'pm' or '?' (not stated).
    Only matches with minutes, or an hour followed by a period word, count as times."""
    out = set()
    am, pm = _AM.get(lang, _AM["en"]), _PM.get(lang, _PM["en"])
    for m in _TIME.finditer(text or ""):
        g = m.groups()
        h = int(next(x for x in (g[0], g[2], g[4], g[6]) if x is not None))
        mins = next((x for x in (g[1], g[3], g[5]) if x is not None), None)
        period = _period(text[m.end():m.end() + 16], am, pm, first=True) or \
            _period(text[max(0, m.start() - 6):m.start()], am, pm, first=False) or "?"
        if h > 24 or (mins and int(mins) > 59):
            continue
        if h >= 13:
            h, period = h - 12, "pm"
        elif h == 12 and period == "?":
            period = "pm"
        out.add((h % 12, int(mins or 0), period))
    return out


def strip_times(text: str) -> str:
    return _TIME.sub(" ", text or "")


# ------------------------------------------------------------- dose scales

_SCALE = re.compile(r"(?<![0-9.])(\d{2,3})\s*(?:-|–|to|a|à|al|đến|到|至)\s*(\d{2,3})(?![0-9])[^0-9;。；]{0,30}?"
                    r"(\d+(?:[.,]\d+)?)\s*(?:units?|unidad(?:es)?|unità|unités?|đơn vị|个?单位)", re.I)


def scale_steps(text: str) -> dict[tuple[str, str], str]:
    """Sliding-scale steps such as '201-250 give 4 units' -> {('201', '250'): '4'}."""
    return {(m.group(1), m.group(2)): _norm(m.group(3)) for m in _SCALE.finditer(text or "")}
