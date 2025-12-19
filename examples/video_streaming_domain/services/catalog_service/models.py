from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Video(BaseModel):
    id: str
    title: str
    description: str
    category: str
    thumbnail_url: str
    stream_url: str
    duration_seconds: int
    release_year: int
    director: str

class Category(BaseModel):
    id: str
    name: str
    description: str

class WatchProgress(BaseModel):
    video_id: str
    timestamp_seconds: int
    last_watched: datetime
    completed: bool = False

class UserWatchHistory(BaseModel):
    user_id: str
    history: List[WatchProgress] = Field(default_factory=list)
