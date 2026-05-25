"""Post routes — list, detail."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_posts():
    ...


@router.get("/{post_id}")
async def get_post(post_id: str):
    ...
