from __future__ import annotations

import re


PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s.-]?)?(?:0[\s.-]?)?[6-9](?:[\s.-]?\d){9}(?!\d)")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
HINGLISH_WORDS = {
    "aap", "acha", "batao", "chahiye", "dawai", "den", "hai", "hain", "hoga", "hum", "humne",
    "ilaj", "ji", "ka", "kaise", "kare", "karo", "kasa", "ke", "ki", "ko", "kya", "mai", "maire",
    "madam", "mam", "me", "mein", "mera", "mere", "mujhe", "nahi", "raha", "rahi", "sir", "se",
}


def extract_phone_numbers(text: str | None) -> list[str]:
    numbers: list[str] = []
    for match in PHONE_RE.findall(text or ""):
        normalized = re.sub(r"\D", "", match)
        if normalized.startswith("91") and len(normalized) == 12:
            normalized = normalized[2:]
        if normalized.startswith("0") and len(normalized) == 11:
            normalized = normalized[1:]
        if len(normalized) == 10 and normalized[0] in "6789" and normalized not in numbers:
            numbers.append(normalized)
    return numbers


def detect_language(text: str | None) -> str:
    value = (text or "").strip()
    if not value:
        return "unknown"
    if DEVANAGARI_RE.search(value):
        return "hi"
    words = set(re.findall(r"[a-zA-Z]+", value.lower()))
    if words & HINGLISH_WORDS:
        return "hinglish"
    return "en"
