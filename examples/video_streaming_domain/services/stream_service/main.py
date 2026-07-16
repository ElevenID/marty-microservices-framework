import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from .models import StreamRequest, StreamSession, WatchProgress

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Video Stream Service",
    description="Handles video streaming sessions and progress tracking.",
    version="1.0.0"
)

@app.middleware("http")
async def add_pod_name_header(request, call_next):
    response = await call_next(request)
    response.headers["X-Pod-Name"] = os.getenv("HOSTNAME", "local-dev")
    return response

# Configuration
CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://localhost:8001")

# In-memory session store
STREAM_SESSIONS: Dict[str, StreamSession] = {}

# --- Dependencies ---

async def get_current_user(
    session_id: Optional[str] = Cookie(None, alias="session_id"),
    authorization: Optional[str] = Header(None)
) -> str:
    """
    Simulates session validation.
    In a real scenario, this would call the SessionManager or Identity Service.
    For this example, we accept any non-empty session_id or Authorization header as a user_id.
    """
    if session_id:
        return session_id # Treat session_id as user_id for simplicity in this demo

    if authorization:
        # Basic Bearer token extraction
        if authorization.startswith("Bearer "):
            return authorization.split(" ")[1]
        return authorization

    # For demo purposes, if no auth is provided, we can either raise 401 or return a guest user.
    # Let's raise 401 to demonstrate security.
    raise HTTPException(status_code=401, detail="Not authenticated")

# --- Endpoints ---

@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(STREAM_SESSIONS)}

@app.post("/stream/{video_id}", response_model=StreamSession)
async def start_stream(video_id: str, user_id: str = Depends(get_current_user)):
    # 1. Validate video exists via Catalog Service
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{CATALOG_SERVICE_URL}/videos/{video_id}")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="Video not found")
            resp.raise_for_status()
            video_data = resp.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to contact catalog service: {e}")
            raise HTTPException(status_code=503, detail="Catalog service unavailable")

    # 2. Create Stream Session
    session_id = str(uuid.uuid4())
    session = StreamSession(
        session_id=session_id,
        user_id=user_id,
        video_id=video_id,
        start_time=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=4) # 4 hour lease
    )
    STREAM_SESSIONS[session_id] = session

    # In a real app, we might return a signed URL for a CDN here.
    # For this demo, we return the session which implies access is granted.
    # The client would use the video's stream_url from the catalog.

    logger.info(f"User {user_id} started streaming video {video_id}")
    return session

@app.post("/progress")
async def update_progress(progress: WatchProgress, user_id: str = Depends(get_current_user)):
    # 1. Update local session (optional, for enforcement)
    # ...

    # 2. Sync with Catalog Service (User History)
    payload = {
        "video_id": progress.video_id,
        "timestamp_seconds": progress.timestamp_seconds,
        "last_watched": datetime.utcnow().isoformat(),
        "completed": progress.completed
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{CATALOG_SERVICE_URL}/users/{user_id}/history",
                json=payload
            )
            resp.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"Failed to sync progress to catalog service: {e}")
            # We might not want to fail the client request just because history sync failed
            # but for this example we'll log it.

    return {"status": "updated", "video_id": progress.video_id}
