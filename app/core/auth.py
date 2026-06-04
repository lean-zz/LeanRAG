from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from app.core.errors import AppError
from app.core.ids import new_id


@dataclass
class LoginUser:
    user_id: str
    username: str
    role: str
    avatar: str | None = None


_tokens: dict[str, LoginUser] = {}


def issue_token(user: LoginUser) -> str:
    token = new_id()
    _tokens[token] = user
    return token


def revoke_token(token: str | None) -> None:
    if token:
        _tokens.pop(token, None)


def current_user(authorization: Annotated[str | None, Header(alias="Authorization")] = None) -> LoginUser:
    if not authorization or authorization not in _tokens:
        raise AppError("未登录或登录已过期", "A000001", status_code=401)
    return _tokens[authorization]


def optional_user(authorization: Annotated[str | None, Header(alias="Authorization")] = None) -> LoginUser:
    if authorization and authorization in _tokens:
        return _tokens[authorization]
    return LoginUser(user_id="0", username="guest", role="user")


def require_admin(user: LoginUser) -> None:
    if user.role != "admin":
        raise AppError("无权限访问", "A000002", status_code=403)

