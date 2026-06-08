from __future__ import annotations

import time

import requests


GRAPH_BASE = "https://graph.facebook.com"


class MetaGraphError(Exception):
    pass


class MetaGraphRateLimitError(MetaGraphError):
    pass


RATE_LIMIT_ERROR_CODES = {4, 17, 32, 613, 80004}


def graph_url(account, path: str) -> str:
    version = (account.graph_api_version or "v21.0").strip().lstrip("/")
    return f"{GRAPH_BASE}/{version}/{path.lstrip('/')}"


def get_comment(account, comment_id: str) -> dict:
    return _request(
        "GET",
        graph_url(account, comment_id),
        account,
        params={"fields": "id,message,text,from,username,timestamp,permalink_url,parent_id,hidden"},
    )


def get_object(account, object_id: str, fields: str = "id,name") -> dict:
    return _request("GET", graph_url(account, object_id), account, params={"fields": fields})


def list_comments(account, source_id: str, limit: int = 50) -> dict:
    fields = "id,message,text,from,username,timestamp,created_time,permalink_url,parent_id,hidden"
    return _request(
        "GET",
        graph_url(account, f"{source_id}/comments"),
        account,
        params={"fields": fields, "limit": limit},
    )


def list_all_comments(account, source_id: str, limit: int = 100, max_pages: int = 20) -> dict:
    payload = list_comments(account, source_id, limit=limit)
    data = list(payload.get("data") or [])
    next_url = (payload.get("paging") or {}).get("next")
    pages = 1
    while next_url and pages < max_pages:
        next_payload = _request("GET", next_url, account)
        data.extend(next_payload.get("data") or [])
        next_url = (next_payload.get("paging") or {}).get("next")
        pages += 1
    payload["data"] = data
    return payload


def list_facebook_posts(account, limit: int = 100) -> dict:
    page_id = account.page_id
    if not page_id:
        return {"data": []}
    fields = "id,message,created_time,permalink_url,comments.summary(true).limit(0)"
    return _request("GET", graph_url(account, f"{page_id}/posts"), account, params={"fields": fields, "limit": limit})


def list_instagram_media(account, limit: int = 100) -> dict:
    ig_id = account.instagram_business_account_id
    if not ig_id:
        return {"data": []}
    fields = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,comments_count"
    return _request("GET", graph_url(account, f"{ig_id}/media"), account, params={"fields": fields, "limit": limit})


def send_public_reply(account, comment_id: str, message: str) -> dict:
    if account.platform == "Instagram":
        return _request("POST", graph_url(account, f"{comment_id}/replies"), account, data={"message": message})
    return _request("POST", graph_url(account, f"{comment_id}/comments"), account, data={"message": message})


def send_private_reply(account, ig_user_id: str, comment_id: str, message: str) -> dict:
    payload = {"recipient": {"comment_id": comment_id}, "message": {"text": message}}
    return _request("POST", graph_url(account, f"{ig_user_id}/messages"), account, json=payload)


def hide_comment(account, comment_id: str, hide: bool = True) -> dict:
    if account.platform == "Instagram":
        return _request("POST", graph_url(account, comment_id), account, data={"hide": "true" if hide else "false"})
    return _request("POST", graph_url(account, comment_id), account, data={"is_hidden": "true" if hide else "false"})


def delete_comment(account, comment_id: str) -> dict:
    return _request("DELETE", graph_url(account, comment_id), account)


def _request(method: str, url: str, account, **kwargs) -> dict:
    return _request_once(method, url, account, retries=2, **kwargs)


def _request_once(method: str, url: str, account, retries: int = 0, **kwargs) -> dict:
    token = account.get_password("access_token") if hasattr(account, "get_password") else None
    params = dict(kwargs.pop("params", {}) or {})
    data = kwargs.pop("data", None)
    if method.upper() == "GET":
        params["access_token"] = token
    else:
        data = dict(data or {})
        if token:
            data.setdefault("access_token", token)
    response = requests.request(method, url, params=params, data=data, timeout=30, **kwargs)
    try:
        payload = response.json()
    except Exception:
        payload = {"text": response.text}
    if response.status_code >= 400 or payload.get("error"):
        error = payload.get("error") or payload
        if _is_rate_limited(response, error):
            if retries > 0:
                time.sleep(_retry_after(response))
                return _request_once(method, url, account, retries=retries - 1, params=params, data=data, **kwargs)
            raise MetaGraphRateLimitError(str(error))
        raise MetaGraphError(str(error))
    return payload


def _is_rate_limited(response, error) -> bool:
    if response.status_code == 429:
        return True
    if isinstance(error, dict):
        try:
            return int(error.get("code") or 0) in RATE_LIMIT_ERROR_CODES
        except Exception:
            return False
    return "rate limit" in str(error).lower() or "too many" in str(error).lower()


def _retry_after(response) -> int:
    try:
        value = int(response.headers.get("Retry-After") or 0)
        if value > 0:
            return min(value, 120)
    except Exception:
        pass
    return 60
