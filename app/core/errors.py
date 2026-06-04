from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.core.responses import failure


class AppError(Exception):
    def __init__(self, message: str, code: str = "B000001", status_code: int = 200) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=failure(exc.message, exc.code))

    @app.exception_handler(HTTPException)
    async def handle_http_error(_, exc: HTTPException) -> JSONResponse:
        message = str(exc.detail) if exc.detail else "请求失败"
        return JSONResponse(status_code=exc.status_code, content=failure(message))

