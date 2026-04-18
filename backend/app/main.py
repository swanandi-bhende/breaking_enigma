from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings

app = FastAPI(title="ADWF Pipeline Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .api.routes import health, runs
app.include_router(health.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from .api.ws import handle_websocket
    await handle_websocket(websocket)
