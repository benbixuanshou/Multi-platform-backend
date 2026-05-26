"""Comment routes — GET list, GET detail, PATCH, ignore, spam."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_comments():
    return {"items": [], "total": 0, "urgent_count": 0}


@router.get("/{comment_id}")
async def get_comment(comment_id: str):
    return {"id": comment_id, "message": "not implemented"}


@router.patch("/{comment_id}")
async def update_comment(comment_id: str):
    return {"id": comment_id, "message": "not implemented"}


@router.post("/{comment_id}/ignore")
async def ignore_comment(comment_id: str):
    return {"id": comment_id, "status": "ignored"}


@router.post("/{comment_id}/spam")
async def mark_spam(comment_id: str):
    return {"id": comment_id, "status": "spam"}
