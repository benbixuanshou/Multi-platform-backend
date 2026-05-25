"""Internal routes — extension batch upload, cookie sync."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/comments/batch")
async def batch_comments():
    ...


@router.post("/cookie")
async def sync_cookie():
    ...
