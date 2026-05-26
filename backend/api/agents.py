"""Agent status routes — status, resume."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def agent_status():
    return {
        "classify_router": {"status": "running", "queue_length": 0, "error_rate": 0},
        "reply_generate": {"status": "running", "queue_length": 0, "error_rate": 0},
        "insight_mining": {"status": "running", "queue_length": 0, "last_run_at": None},
    }


@router.post("/{agent_name}/resume")
async def resume_agent(agent_name: str):
    return {"agent": agent_name, "status": "resumed"}
