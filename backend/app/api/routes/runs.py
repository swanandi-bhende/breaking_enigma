from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class RunRequest(BaseModel):
    idea: str
    target_platform: str = "web"

@router.post("/runs")
async def start_pipeline_run(request: RunRequest):
    # This will trigger the LangGraph executor.
    # Currently just a scaffold for Anshul's domain.
    return {"status": "accepted", "run_id": "dummy-uuid"}
