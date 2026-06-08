from __future__ import annotations

import re


URGENT_RE = re.compile(
    r"\b(emergency|urgent|bleeding|breath|breathing|chest pain|severe pain|unconscious|suicide|pregnan|child|baby)\b",
    re.I,
)
MEDICAL_RE = re.compile(
    r"\b(symptom|pain|disease|medicine|dose|tablet|treatment|cure|doctor|report|side effect|operation|surgery|"
    r"bukhar|dard|bimari|dawai|ilaaj|ilaj|doctor|report)\b",
    re.I,
)
ANGRY_RE = re.compile(r"\b(fraud|scam|fake|angry|complaint|bad service|refund|cheat|bekar)\b", re.I)
SPAM_RE = re.compile(r"\b(crypto|loan|earn money|followers|promotion|whatsapp me for ads)\b", re.I)


def classify_risk(text: str | None) -> str:
    value = text or ""
    if URGENT_RE.search(value):
        return "Urgent"
    if MEDICAL_RE.search(value):
        return "Medical"
    if ANGRY_RE.search(value):
        return "Angry"
    if SPAM_RE.search(value):
        return "Spam"
    return "Low"


def needs_medical_escalation(risk: str) -> bool:
    return normalize_risk(risk) in {"Medical", "Urgent"}


def normalize_risk(risk: str | None) -> str:
    value = str(risk or "Unknown").strip().lower()
    mapping = {
        "low": "Low",
        "medical": "Medical",
        "urgent": "Urgent",
        "angry": "Angry",
        "spam": "Spam",
        "unknown": "Unknown",
    }
    return mapping.get(value, "Unknown")
