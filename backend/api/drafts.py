"""Draft routes — list, generate, edit, adopt, send."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/comments/{comment_id}/drafts")
async def list_drafts(comment_id: str):
    ...


@router.post("/comments/{comment_id}/drafts/generate")
async def generate_drafts(comment_id: str):
    ...


@router.patch("/drafts/{draft_id}")
async def edit_draft(draft_id: str):
    ...


@router.post("/drafts/{draft_id}/adopt")
async def adopt_draft(draft_id: str):
    ...


@router.post("/drafts/{draft_id}/send")
async def send_draft(draft_id: str):
    ...
