"""Batch routes — generate drafts, send."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/generate-drafts")
async def batch_generate():
    return {"tasks": []}


@router.post("/send")
async def batch_send():
    return {"results": []}
