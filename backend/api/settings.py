"""Settings routes — profile, platform accounts."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/profile")
async def get_profile():
    ...


@router.put("/profile")
async def update_profile():
    ...


@router.get("/platforms")
async def list_platforms():
    ...


@router.post("/platforms")
async def bind_platform():
    ...


@router.delete("/platforms/{platform_id}")
async def unbind_platform(platform_id: str):
    ...
