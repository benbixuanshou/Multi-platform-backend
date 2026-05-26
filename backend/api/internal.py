"""Internal routes — extension batch upload, cookie sync."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/comments/batch")
async def batch_comments():
    return {"received": 0, "new": 0, "duplicates": 0}


@router.post("/cookie")
async def sync_cookie():
    return {"message": "not implemented"}
