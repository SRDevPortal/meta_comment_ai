from __future__ import annotations

import frappe
from frappe.utils.background_jobs import get_queue, get_redis_conn, get_workers

from meta_comment_ai.security import require_admin


@frappe.whitelist()
def get_runtime_health():
    """Return bounded operational signals without scanning Redis keys."""
    require_admin()
    cache_health = _redis_health(frappe.cache())
    queue_health = _redis_health(get_redis_conn())
    queues = {
        queue_name: len(get_queue(queue_name))
        for queue_name in ("short", "default", "long")
    }
    workers = get_workers()
    return {
        "status": "degraded" if not workers or max(queues.values(), default=0) > 1000 else "ok",
        "workers_online": len(workers),
        "queues": queues,
        "redis_cache": cache_health,
        "redis_queue": queue_health,
    }


def _redis_health(redis) -> dict:
    memory = redis.info("memory")
    stats = redis.info("stats")
    return {
        "used_memory": memory.get("used_memory"),
        "maxmemory": memory.get("maxmemory"),
        "mem_fragmentation_ratio": memory.get("mem_fragmentation_ratio"),
        "evicted_keys": stats.get("evicted_keys"),
        "rejected_connections": stats.get("rejected_connections"),
    }
