"""Draft routes — list, generate, edit, adopt, send."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/comments/{comment_id}/drafts")
async def list_drafts(comment_id: str):
    return {"drafts": []}


@router.post("/comments/{comment_id}/drafts/generate")
async def generate_drafts(comment_id: str):
    return {"task_id": "not-implemented"}


@router.patch("/drafts/{draft_id}")
async def edit_draft(draft_id: str):
    return {"id": draft_id, "message": "not implemented"}


@router.post("/drafts/{draft_id}/adopt")
async def adopt_draft(draft_id: str):
    return {"id": draft_id, "is_adopted": True}


@router.post("/drafts/{draft_id}/send")
async def send_draft(draft_id: str):
    return {"id": draft_id, "status": "not implemented"}
