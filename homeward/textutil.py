"""Number extraction, readability and fuzzy matching. No model calls."""

import re
from difflib import SequenceMatcher

_NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?")
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
