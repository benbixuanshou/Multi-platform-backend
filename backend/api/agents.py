"""Agent status routes — status, resume."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def agent_status():
    ...


@router.post("/{agent_name}/resume")
async def resume_agent(agent_name: str):
    ...
