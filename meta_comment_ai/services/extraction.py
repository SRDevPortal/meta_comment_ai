from __future__ import annotations

import re


PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s.-]?)?(?:0[\s.-]?)?[6-9](?:[\s.-]?\d){9}(?!\d)")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
HINGLISH_WORDS = {"hai", "hain", "kya", "kaise", "mujhe", "mere", "sir", "madam", "ilaj", "dawai"}


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
    words = {word.lower().strip(".,!?") for word in value.split()}
    if words & HINGLISH_WORDS:
        return "hinglish"
    return "en"
