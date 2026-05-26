"""Analytics routes — overview, insights."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/overview")
async def overview():
    return {
        "today_new": 0, "pending": 0, "urgent": 0, "replied": 0,
        "reply_rate": 0, "adoption_rate": 0,
        "by_platform": {"xhs": 0, "douyin": 0, "bilibili": 0},
    }


@router.get("/insights")
async def insights():
    return {"message": "not implemented"}
