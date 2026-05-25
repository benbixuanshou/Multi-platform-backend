"""Comment routes — GET list, GET detail, PATCH, ignore, spam."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_comments():
    ...


@router.get("/{comment_id}")
async def get_comment(comment_id: str):
    ...


@router.patch("/{comment_id}")
async def update_comment(comment_id: str):
    ...


@router.post("/{comment_id}/ignore")
async def ignore_comment(comment_id: str):
    ...


@router.post("/{comment_id}/spam")
async def mark_spam(comment_id: str):
    ...
