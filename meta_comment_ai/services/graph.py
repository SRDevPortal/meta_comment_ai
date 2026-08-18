from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


GRAPH_BASE = "https://graph.facebook.com"


class MetaGraphError(Exception):
    pass


class MetaGraphRateLimitError(MetaGraphError):
    pass


RATE_LIMIT_ERROR_CODES = {4, 17, 32, 613, 80004}
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 25


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=1,
        status=2,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10))
    return session


HTTP = _session()


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


def list_all_comments(account, source_id: str, limit: int = 100, max_pages: int = 100) -> dict:
    payload = list_comments(account, source_id, limit=limit)
    return _collect_pages(account, payload, max_pages=max_pages)


def list_all_replies(account, comment_id: str, limit: int = 100, max_pages: int = 100) -> dict:
    edge = "replies" if account.platform == "Instagram" else "comments"
    fields = "id,message,text,from,username,timestamp,created_time,permalink_url,parent_id,hidden"
    payload = _request(
        "GET",
        graph_url(account, f"{comment_id}/{edge}"),
        account,
        params={"fields": fields, "limit": limit},
    )
    return _collect_pages(account, payload, max_pages=max_pages)


def _collect_pages(account, payload: dict, max_pages: int | None) -> dict:
    data = list(payload.get("data") or [])
    next_url = (payload.get("paging") or {}).get("next")
    pages = 1
    while next_url and (max_pages is None or pages < max_pages):
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


def list_all_facebook_posts(account, limit: int = 100, max_pages: int | None = None) -> dict:
    return _collect_pages(account, list_facebook_posts(account, limit=limit), max_pages=max_pages)


def list_instagram_media(account, limit: int = 100) -> dict:
    ig_id = account.instagram_business_account_id
    if not ig_id:
        return {"data": []}
    fields = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,comments_count"
    return _request("GET", graph_url(account, f"{ig_id}/media"), account, params={"fields": fields, "limit": limit})


def list_all_instagram_media(account, limit: int = 100, max_pages: int | None = None) -> dict:
    return _collect_pages(account, list_instagram_media(account, limit=limit), max_pages=max_pages)


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
    return _request_once(method, url, account, **kwargs)


def _request_once(method: str, url: str, account, **kwargs) -> dict:
    token = account.get_password("access_token") if hasattr(account, "get_password") else None
    params = dict(kwargs.pop("params", {}) or {})
    data = kwargs.pop("data", None)
    if method.upper() == "GET":
        params["access_token"] = token
    else:
        data = dict(data or {})
        if token:
            data.setdefault("access_token", token)
    response = HTTP.request(
        method,
        url,
        params=params,
        data=data,
        timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        **kwargs,
    )
    try:
        payload = response.json()
    except Exception:
        payload = {"text": response.text}
    if response.status_code >= 400 or payload.get("error"):
        error = payload.get("error") or payload
        if _is_rate_limited(response, error):
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
