from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class StreamSession(BaseModel):
    session_id: str
    user_id: str
    video_id: str
    start_time: datetime
    expires_at: datetime

class WatchProgress(BaseModel):
    video_id: str
    timestamp_seconds: int
    completed: bool = False

class StreamRequest(BaseModel):
    video_id: str
