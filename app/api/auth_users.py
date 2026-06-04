from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header

from app.core.auth import LoginUser, current_user, issue_token, require_admin, revoke_token
from app.core.errors import AppError
from app.core.responses import success
from app.db.repository import repository

router = APIRouter()


@router.post("/auth/login")
async def login(payload: dict[str, Any]) -> dict[str, Any]:
    user = repository.find_user_by_credentials(payload.get("username"), payload.get("password"))
    if not user:
        raise AppError("用户名或密码错误", "A000003")
    token = issue_token(LoginUser(user_id=user["id"], username=user["username"], role=user["role"], avatar=user.get("avatar")))
    return success({"userId": user["id"], "username": user["username"], "role": user["role"], "token": token, "avatar": user.get("avatar")})


@router.post("/auth/logout")
async def logout(authorization: Annotated[str | None, Header(alias="Authorization")] = None) -> dict[str, Any]:
    revoke_token(authorization)
    return success()


@router.get("/user/me")
async def user_me(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success({"userId": user.user_id, "username": user.username, "role": user.role, "avatar": user.avatar})


@router.get("/users")
async def users(current: int = 1, size: int = 10, username: str | None = None, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    return success(repository.list_users(current, size, username))


@router.post("/users")
async def create_user(payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    return success(repository.create_user(payload))


@router.put("/users/{item_id}")
async def update_user(item_id: str, payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    repository.update_user(item_id, payload)
    return success()


@router.delete("/users/{item_id}")
async def delete_user(item_id: str, user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    require_admin(user)
    repository.delete_user(item_id)
    return success()


@router.put("/user/password")
async def change_password(payload: dict[str, Any], user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    repository.change_password(user.user_id, payload.get("newPassword") or payload.get("password"))
    return success()
