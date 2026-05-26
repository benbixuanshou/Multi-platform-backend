"""Post routes — list, detail."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_posts():
    return {"items": [], "total": 0}


@router.get("/{post_id}")
async def get_post(post_id: str):
    return {"id": post_id, "message": "not implemented"}
