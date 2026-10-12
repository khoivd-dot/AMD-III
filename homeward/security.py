"""Web hardening: response headers, cross-site checks, sign-in throttling, name and log hygiene."""

import logging
import re
import time
import unicodedata

# Pages load only their own files: no inline scripts or styles, other origins or framing.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self'",
    "font-src 'self'",
    "connect-src 'self'",
    "media-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # The patient's link carries its token in the path; never pass it on as a referrer.
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
# Responses that can carry health data must not sit in a shared or browser cache.
NO_STORE_PATHS = ("/api/", "/p/")


def headers_for(path: str, https: bool) -> dict[str, str]:
    out = dict(HEADERS)
    if path.startswith(NO_STORE_PATHS) or path == "/":
        out["Cache-Control"] = "no-store"
    if https:
        out["Strict-Transport-Security"] = "max-age=31536000"
    return out


def cross_site(method: str, headers, host: str) -> bool:
    """True for a state-changing request sent by another site's page.

    Browsers attach saved staff credentials to any request to this host, so a page
    elsewhere could post a form here. Fetch metadata and Origin show where it came from.
    """
    if method in ("GET", "HEAD", "OPTIONS"):
        return False
    site = headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "none"):
        return True
    origin = headers.get("origin")
    if origin and origin != "null":
        return re.sub(r"^[a-z]+://", "", origin.lower()).rstrip("/") != (host or "").lower()
    return origin == "null"


class Throttle:
    """Refuse sign-in from an address after too many wrong passwords in a window."""

    def __init__(self, limit: int = 10, window: float = 600.0, max_keys: int = 10000):
        self.limit, self.window, self.max_keys = limit, window, max_keys
        self.fails: dict[str, list[float]] = {}

    def _recent(self, key: str, now: float) -> list[float]:
        times = [t for t in self.fails.get(key, []) if now - t < self.window]
        if times:
            self.fails[key] = times
        else:
            self.fails.pop(key, None)
        return times

    def blocked(self, key: str) -> bool:
        return len(self._recent(key, time.monotonic())) >= self.limit

    def fail(self, key: str) -> None:
        now = time.monotonic()
        if len(self.fails) >= self.max_keys:  # bound memory under a spray from many addresses
            for k in list(self.fails)[: self.max_keys // 10]:
                self._recent(k, now)
        self.fails.setdefault(key, []).append(now)

    def clear(self, key: str) -> None:
        self.fails.pop(key, None)


def clean_name(value: str) -> str:
    """A reviewer name as people will read it: no invisible or control characters."""
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFC", value or ""))
    return re.sub(r" +", " ", "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")).strip()


def is_real_name(value: str) -> bool:
    return sum(ch.isalpha() for ch in value) >= 2


_TOKEN_IN_PATH = re.compile(r"(/(?:p|api/patient)/)[A-Za-z0-9_-]+")


class RedactPatientLinks(logging.Filter):
    """Keep patient link tokens out of access logs; a token opens the unmasked packet."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.args = tuple(_TOKEN_IN_PATH.sub(r"\1<token>", a) if isinstance(a, str) else a
                                for a in record.args)
        return True
