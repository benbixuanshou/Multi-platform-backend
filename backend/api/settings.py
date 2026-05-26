"""Settings routes — profile, platform accounts."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/profile")
async def get_profile():
    return {"tone": "casual", "phrases": "", "bio": "", "display_name": ""}


@router.put("/profile")
async def update_profile():
    return {"message": "not implemented"}


@router.get("/platforms")
async def list_platforms():
    return []


@router.post("/platforms")
async def bind_platform():
    return {"message": "not implemented"}


@router.delete("/platforms/{platform_id}")
async def unbind_platform(platform_id: str):
    return {"id": platform_id, "status": "deleted"}
