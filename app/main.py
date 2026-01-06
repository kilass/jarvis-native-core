import asyncio
from fastapi import FastAPI, WebSocket
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.websocket_endpoint import router as ws_router

settings = get_settings()
setup_logging()

app = FastAPI(title="Jarvis Native Core", version="0.1.0")

app.include_router(ws_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "project": "jarvis-native-core"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
