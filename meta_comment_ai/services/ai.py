from __future__ import annotations

import json
import re
from types import SimpleNamespace

import frappe
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from meta_comment_ai.services.extraction import detect_language, extract_phone_numbers
from meta_comment_ai.services.policy import classify_risk, normalize_risk

ALLOWED_ACTIONS = {"draft_public_reply", "draft_private_reply", "capture_lead_and_hide", "escalate"}
ESCALATION_RISKS = {"Medical", "Urgent"}
UNSAFE_MEDICAL_REPLY_RE = re.compile(
    r"\b(take|use|start|stop|prescribe|dosage|dose|mg|tablet|capsule|medicine|medication|cure|"
    r"dawai|goli|ilaaj|ilaj)\b",
    re.I,
)
AI_HTTP = requests.Session()
AI_HTTP.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=2,
            connect=2,
            read=0,
            status=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"POST"}),
            respect_retry_after_header=True,
        ),
        pool_connections=5,
        pool_maxsize=5,
    ),
)


def generate_recommendation(comment_doc) -> dict:
    settings = frappe.get_single("Meta Comment AI Settings")
    text = comment_doc.comment_text or ""
    phones = extract_phone_numbers(text)
    risk = normalize_risk(classify_risk(text))
    language = detect_language(text)

    if phones:
        return _local_recommendation(
            "capture_lead_and_hide",
            text,
            language,
            risk,
            phones,
            "Phone number found in public comment.",
            hide_recommended=True,
        )
    if risk in ESCALATION_RISKS:
        return _local_recommendation(
            "escalate",
            text,
            language,
            risk,
            phones,
            "Medical or urgent comment requires human review.",
        )
    prompt_policy = _prompt_policy(settings, comment_doc.social_account)
    if not settings.enable_ai_drafts:
        return _local_recommendation("draft_public_reply", text, language, risk, phones, "AI drafts disabled; using safe local draft.")

    provider = _load_provider(settings)
    if not provider:
        return _local_recommendation("draft_public_reply", text, language, risk, phones, "")

    try:
        result = _call_provider(provider, settings, prompt_policy, comment_doc, language, risk, phones)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Meta Comment AI Provider Failed")
        return _local_recommendation("draft_public_reply", text, language, risk, phones, "")

    return validate_ai_result(result, fallback_text=text, fallback_language=language, fallback_risk=risk, phones=phones)


def validate_ai_result(result: dict, *, fallback_text: str, fallback_language: str, fallback_risk: str, phones: list[str]) -> dict:
    risk = normalize_risk(result.get("risk_level") or fallback_risk)
    action = result.get("action")
    if action == "skip":
        action = "draft_public_reply"
    if action not in ALLOWED_ACTIONS:
        action = "draft_public_reply"
    reply_text = str(result.get("reply_text") or "").strip()
    if risk in ESCALATION_RISKS or _looks_like_medical_advice(reply_text):
        action = "escalate"
        reply_text = ""
    if action in {"draft_public_reply", "draft_private_reply"} and not reply_text:
        reply_text = _fallback_reply(fallback_text, fallback_language, risk)
    return {
        "action": action,
        "reply_text": reply_text,
        "language": _normalize_language(result.get("language"), fallback_language),
        "risk_level": risk,
        "lead_phone_numbers": result.get("lead_phone_numbers") or phones,
        "hide_recommended": bool(result.get("hide_recommended") or phones),
        "escalation_reason": result.get("escalation_reason") or _default_escalation_reason(action, risk),
        "confidence": _confidence(result.get("confidence")),
    }


def _local_recommendation(action, text, language, risk, phones, reason, hide_recommended=False):
    return {
        "action": action,
        "reply_text": "" if action == "escalate" else _fallback_reply(text, language, risk),
        "language": language,
        "risk_level": normalize_risk(risk),
        "lead_phone_numbers": phones,
        "hide_recommended": hide_recommended,
        "escalation_reason": reason,
        "confidence": 80,
    }


def _fallback_reply(text: str, language: str, risk: str) -> str:
    clean_text = (text or "").strip()
    if language in {"hi", "hinglish"}:
        if clean_text and len(clean_text) <= 3:
            return "🙏"
        if "thanks" in clean_text.lower() or "thank" in clean_text.lower():
            return "Aapka welcome hai."
        return "Ji, iske liye please apna contact number DM karein ya humein call karein. Hamari team aapko details guide karegi."
    if clean_text and len(clean_text) <= 3:
        return "🙏"
    if "thanks" in clean_text.lower() or "thank" in clean_text.lower():
        return "You are welcome."
    return "Thanks for your comment. Please DM your contact number and our team will share the details."


def _load_provider(settings):
    provider_name = settings.llm_provider
    if not provider_name and frappe.db.exists("DocType", "WA LLM Provider"):
        rows = frappe.get_all("WA LLM Provider", filters={"is_active": 1}, fields=["name"], order_by="priority asc", limit=1)
        provider_name = rows[0].name if rows else None
    if not provider_name:
        return None
    doc = frappe.get_doc("WA LLM Provider", provider_name)
    return SimpleNamespace(
        provider_type=doc.provider_type,
        model_name=doc.model_name or settings.fallback_model_name,
        api_key=doc.get_password("api_key"),
        base_url=doc.base_url,
    )


def _call_provider(provider, settings, prompt_policy, comment_doc, language, risk, phones):
    url = provider.base_url or "https://api.openai.com/v1/chat/completions"
    if provider.provider_type == "Gemini" and not provider.base_url:
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    if url.endswith("/") and "chat/completions" not in url:
        url += "chat/completions"

    prompt = f"""{prompt_policy.system_prompt or settings.system_prompt or ''}

Medical guardrails:
{prompt_policy.medical_guardrails or settings.medical_guardrails or ''}

Multilingual policy:
{prompt_policy.multilingual_reply_policy or settings.multilingual_reply_policy or ''}

Return JSON only with keys: action, reply_text, language, risk_level, lead_phone_numbers, hide_recommended, escalation_reason, confidence.
Allowed actions: draft_public_reply, draft_private_reply, capture_lead_and_hide.
Use escalate for medical symptoms, urgent concerns, side effects, complaints requiring staff attention, or unsafe medical-advice requests.
Never diagnose, prescribe, suggest dosage, or promise a cure.
Use the same language as the comment. Keep reply_text short, specific, varied, and natural.

Human variation rules:
- Do not use one fixed template or repeated sentence pattern.
- Do not always include emoji. Use emoji only when it fits the user's tone.
- Sometimes reply with plain text only.
- Sometimes reply with a short phrase plus emoji.
- Sometimes, for emoji-only praise, reply with one suitable emoji only.
- For "thanks", "ok", "nice", hearts, folded hands, fire, or similar light comments, keep the reply extremely short.
- For questions, answer briefly but guide them to DM/call/contact team when details are needed.
- Avoid sounding like an assistant: no "Thank you for reaching out" unless it truly fits.
- Avoid over-polished lines, repeated exclamation marks, and generic marketing language.

Comment context:
Platform: {comment_doc.platform}
Detected language: {language}
Risk: {risk}
Phone numbers found: {phones}
Comment: {comment_doc.comment_text or ''}
"""
    response = AI_HTTP.post(
        url,
        headers={"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"},
        json={
            "model": provider.model_name,
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You produce strict JSON for a medical social media moderation workflow."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=(5, 30),
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def _confidence(value) -> int:
    try:
        if isinstance(value, float) and value <= 1:
            return int(value * 100)
        return max(0, min(100, int(value)))
    except Exception:
        return 70


def _normalize_language(value, fallback: str) -> str:
    language = str(value or "").strip().lower()
    aliases = {"english": "en", "hindi": "hi", "hindi (romanized)": "hinglish", "roman hindi": "hinglish"}
    language = aliases.get(language, language)
    return language if language in {"en", "hi", "hinglish", "unknown"} else fallback


def _looks_like_medical_advice(reply_text: str) -> bool:
    return bool(reply_text and UNSAFE_MEDICAL_REPLY_RE.search(reply_text))


def _default_escalation_reason(action: str, risk: str) -> str:
    if action != "escalate":
        return ""
    if risk in ESCALATION_RISKS:
        return "Medical or urgent comment requires human review."
    return "AI reply looked like medical advice and was blocked."


def _prompt_policy(settings, social_account: str | None):
    parent_account = _main_prompt_account(social_account)
    candidates = [social_account, parent_account, settings.main_social_account]
    for row in settings.get("account_prompt_maps") or []:
        if row.is_active and row.meta_social_account in candidates:
            return row
    return SimpleNamespace(
        system_prompt=settings.system_prompt,
        medical_guardrails=settings.medical_guardrails,
        multilingual_reply_policy=settings.multilingual_reply_policy,
    )


def _main_prompt_account(social_account: str | None) -> str | None:
    if not social_account:
        return None
    if not frappe.db.exists("Meta Social Account", social_account):
        return social_account
    parent = frappe.db.get_value("Meta Social Account", social_account, "parent_social_account")
    return parent or social_account
