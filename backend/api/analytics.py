"""Analytics routes — overview, insights."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/overview")
async def overview():
    ...


@router.get("/insights")
async def insights():
    ...
