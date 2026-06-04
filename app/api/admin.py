from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import LoginUser, current_user
from app.core.responses import success
from app.db.repository import repository

router = APIRouter()


@router.get("/admin/dashboard/overview")
async def dashboard_overview(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.dashboard_overview())


@router.get("/admin/dashboard/performance")
async def dashboard_performance(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.dashboard_performance())


@router.get("/admin/dashboard/trends")
async def dashboard_trends(user: LoginUser = Depends(current_user)) -> dict[str, Any]:
    return success(repository.dashboard_trends())
