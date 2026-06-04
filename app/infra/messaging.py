from __future__ import annotations

from app.core.config import settings


class RocketMqClient:
    def __init__(self) -> None:
        self.name_server = settings.rocketmq_name_server
        self._events: list[dict] = []

    def publish(self, topic: str, payload: dict) -> None:
        # Python RocketMQ client availability varies by platform; keep a durable
        # in-process event log for local fallback and expose this method as the
        # integration point for a real producer.
        self._events.append({"topic": topic, "payload": payload})

    def drain_local_events(self) -> list[dict]:
        events = list(self._events)
        self._events.clear()
        return events


rocketmq = RocketMqClient()

