from __future__ import annotations

import time

from app.core.config import settings

try:
    import redis
except Exception:  # pragma: no cover - optional dependency guard
    redis = None


class TaskStateStore:
    def __init__(self) -> None:
        self._memory_cancelled: set[str] = set()
        self._memory_active: dict[str, float] = {}
        self._redis = None
        if redis is not None:
            try:
                client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
                client.ping()
                self._redis = client
            except Exception:
                self._redis = None

    def register(self, task_id: str) -> bool:
        now = time.time()
        if self._redis is not None:
            active_key = "ragent:chat:active"
            self._redis.zremrangebyscore(active_key, 0, now - settings.chat_task_ttl_seconds)
            if self._redis.zcard(active_key) >= settings.chat_max_concurrent:
                return False
            pipe = self._redis.pipeline()
            pipe.zadd(active_key, {task_id: now})
            pipe.expire(active_key, settings.chat_task_ttl_seconds)
            pipe.execute()
            return True
        self._memory_active = {k: v for k, v in self._memory_active.items() if v >= now - settings.chat_task_ttl_seconds}
        if len(self._memory_active) >= settings.chat_max_concurrent:
            return False
        self._memory_active[task_id] = now
        return True

    def unregister(self, task_id: str) -> None:
        if self._redis is not None:
            self._redis.zrem("ragent:chat:active", task_id)
            return
        self._memory_active.pop(task_id, None)

    def cancel(self, task_id: str) -> None:
        if self._redis is not None:
            self._redis.setex(f"ragent:chat:cancel:{task_id}", settings.chat_task_ttl_seconds, "1")
            return
        self._memory_cancelled.add(task_id)

    def is_cancelled(self, task_id: str) -> bool:
        if self._redis is not None:
            return bool(self._redis.get(f"ragent:chat:cancel:{task_id}"))
        return task_id in self._memory_cancelled


task_state_store = TaskStateStore()

