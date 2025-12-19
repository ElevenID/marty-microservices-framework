from typing import List

from pydantic import BaseModel


class VideoRecommendation(BaseModel):
    video_id: str
    title: str
    reason: str
    score: float

class RecommendationResponse(BaseModel):
    user_id: str
    recommendations: List[VideoRecommendation]
