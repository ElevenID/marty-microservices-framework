import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from .models import Category, UserWatchHistory, Video, WatchProgress

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Video Catalog Service",
    description="Manages video metadata and user watch history.",
    version="1.0.0"
)

@app.middleware("http")
async def add_pod_name_header(request, call_next):
    response = await call_next(request)
    response.headers["X-Pod-Name"] = os.getenv("HOSTNAME", "local-dev")
    return response

# --- In-Memory Data Store ---

# Public Domain Videos (Blender Foundation)
VIDEOS: Dict[str, Video] = {
    "big_buck_bunny": Video(
        id="big_buck_bunny",
        title="Big Buck Bunny",
        description="A giant rabbit with a heart bigger than himself.",
        category="animation",
        thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Big_buck_bunny_poster_big.jpg/800px-Big_buck_bunny_poster_big.jpg",
        stream_url="http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        duration_seconds=596,
        release_year=2008,
        director="Sacha Goedegebure"
    ),
    "sintel": Video(
        id="sintel",
        title="Sintel",
        description="A lonely young woman searches for a dragon she befriended.",
        category="fantasy",
        thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Sintel_poster.jpg/800px-Sintel_poster.jpg",
        stream_url="http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
        duration_seconds=888,
        release_year=2010,
        director="Colin Levy"
    ),
    "tears_of_steel": Video(
        id="tears_of_steel",
        title="Tears of Steel",
        description="A group of warriors and scientists gather at the Oude Kerk in Amsterdam to stage a crucial event from the past.",
        category="sci-fi",
        thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Tears_of_Steel_poster.jpg/800px-Tears_of_Steel_poster.jpg",
        stream_url="http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
        duration_seconds=734,
        release_year=2012,
        director="Ian Hubert"
    ),
    "elephants_dream": Video(
        id="elephants_dream",
        title="Elephants Dream",
        description="The story of two men, Emo and Proog, in a strange and infinite machine world.",
        category="sci-fi",
        thumbnail_url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Elephants_Dream_poster.jpg/800px-Elephants_Dream_poster.jpg",
        stream_url="http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
        duration_seconds=653,
        release_year=2006,
        director="Bassam Kurdali"
    )
}

CATEGORIES: Dict[str, Category] = {
    "animation": Category(id="animation", name="Animation", description="Animated feature films and shorts"),
    "sci-fi": Category(id="sci-fi", name="Sci-Fi", description="Science Fiction movies"),
    "fantasy": Category(id="fantasy", name="Fantasy", description="Fantasy movies"),
}

# User Watch History Store (In-Memory)
# Map: user_id -> UserWatchHistory
WATCH_HISTORY: Dict[str, UserWatchHistory] = {}

# --- Endpoints ---

@app.get("/health")
async def health():
    return {"status": "ok", "videos_count": len(VIDEOS)}

@app.get("/videos", response_model=List[Video])
async def list_videos(category: Optional[str] = None):
    if category:
        return [v for v in VIDEOS.values() if v.category == category]
    return list(VIDEOS.values())

@app.get("/videos/{video_id}", response_model=Video)
async def get_video(video_id: str):
    if video_id not in VIDEOS:
        raise HTTPException(status_code=404, detail="Video not found")
    return VIDEOS[video_id]

@app.get("/categories", response_model=List[Category])
async def list_categories():
    return list(CATEGORIES.values())

@app.get("/users/{user_id}/history", response_model=UserWatchHistory)
async def get_user_history(user_id: str):
    if user_id not in WATCH_HISTORY:
        return UserWatchHistory(user_id=user_id, history=[])
    return WATCH_HISTORY[user_id]

@app.post("/users/{user_id}/history", response_model=WatchProgress)
async def update_watch_progress(user_id: str, progress: WatchProgress):
    if progress.video_id not in VIDEOS:
        raise HTTPException(status_code=404, detail="Video not found")

    if user_id not in WATCH_HISTORY:
        WATCH_HISTORY[user_id] = UserWatchHistory(user_id=user_id, history=[])

    history = WATCH_HISTORY[user_id]

    # Update existing entry or append new one
    existing_entry = next((p for p in history.history if p.video_id == progress.video_id), None)

    if existing_entry:
        existing_entry.timestamp_seconds = progress.timestamp_seconds
        existing_entry.last_watched = progress.last_watched
        existing_entry.completed = progress.completed
    else:
        history.history.append(progress)

    return progress
