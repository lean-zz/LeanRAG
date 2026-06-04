from __future__ import annotations

from typing import Any

from app.core.ids import new_id

SUCCESS_CODE = "0"
SERVICE_ERROR_CODE = "B000001"


def success(data: Any = None) -> dict[str, Any]:
    return {
        "code": SUCCESS_CODE,
        "message": None,
        "data": data,
        "requestId": new_id(),
    }


def failure(message: str, code: str = SERVICE_ERROR_CODE) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": None,
        "requestId": new_id(),
    }


def page(records: list[dict[str, Any]], current: int = 1, size: int = 10) -> dict[str, Any]:
    total = len(records)
    start = max(current - 1, 0) * size
    end = start + size
    return {
        "records": records[start:end],
        "total": total,
        "size": size,
        "current": current,
        "pages": (total + size - 1) // size if size else 0,
    }

