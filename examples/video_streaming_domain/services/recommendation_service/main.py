import logging
import os
from typing import Any, Dict, List

import httpx
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from .models import RecommendationResponse, VideoRecommendation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Recommendation Service",
    description="Provides personalized video recommendations.",
    version="1.0.0"
)

# Configuration
CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://localhost:8001")

# --- Dependencies ---

async def get_current_user(
    session_id: str = Cookie(None, alias="session_id"),
    authorization: str = Header(None)
) -> str:
    if session_id:
        return session_id
    if authorization:
        if authorization.startswith("Bearer "):
            return authorization.split(" ")[1]
        return authorization
    raise HTTPException(status_code=401, detail="Not authenticated")

# --- Endpoints ---

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(user_id: str = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        # 1. Fetch User History
        try:
            history_resp = await client.get(f"{CATALOG_SERVICE_URL}/users/{user_id}/history")
            history_resp.raise_for_status()
            history_data = history_resp.json()
            watched_videos = history_data.get("history", [])
            watched_ids = {item["video_id"] for item in watched_videos}
        except httpx.RequestError as e:
            logger.error(f"Failed to fetch history: {e}")
            watched_ids = set()

        # 2. Fetch All Videos
        try:
            catalog_resp = await client.get(f"{CATALOG_SERVICE_URL}/videos")
            catalog_resp.raise_for_status()
            all_videos = catalog_resp.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to fetch catalog: {e}")
            raise HTTPException(status_code=503, detail="Catalog service unavailable")

    # 3. Generate Recommendations
    recommendations = []

    # Simple Algorithm:
    # - Filter out watched videos
    # - (Enhancement: prioritize categories user has watched)

    # For now, just recommend unwatched videos
    for video in all_videos:
        if video["id"] not in watched_ids:
            recommendations.append(
                VideoRecommendation(
                    video_id=video["id"],
                    title=video["title"],
                    reason="Because you haven't watched it yet",
                    score=0.8 # Default score
                )
            )

    # If user has watched everything, maybe recommend re-watching favorites?
    if not recommendations and all_videos:
         recommendations.append(
                VideoRecommendation(
                    video_id=all_videos[0]["id"],
                    title=all_videos[0]["title"],
                    reason="Watch it again!",
                    score=0.5
                )
            )

    return RecommendationResponse(
        user_id=user_id,
        recommendations=recommendations[:5] # Limit to top 5
    )
