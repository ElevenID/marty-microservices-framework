"""
ML Adopt-a-Pet Advisor Sidecar Service

This service provides ML-powered pet recommendations that integrate with the MMF analytics
framework. It demonstrates how to plug ML services cleanly into the microservices architecture.

Features:
- Pet recommendation engine using customer preferences
- Integration with MMF analytics helpers
- A/B testing capabilities for recommendation algorithms
- Real-time model performance monitoring
- Fallback strategies for service resilience

Usage:
    uvicorn ml_pet_advisor:app --host 0.0.0.0 --port 8003
"""

import asyncio
import json
import logging
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="ML Adopt-a-Pet Advisor",
    description="AI-powered pet recommendation service for the MMF petstore domain",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class CustomerPreferences(BaseModel):
    """Customer preferences for ML recommendation"""
    pet_types: list[str] = Field(..., description="Preferred pet types")
    activity_level: str = Field(..., description="Desired activity level")
    living_situation: str = Field(..., description="Living environment")
    experience_with_pets: str = Field(..., description="Experience level")
    budget_range: tuple[float, float] = Field(..., description="Budget range")
    special_requirements: list[str] = Field(default_factory=list, description="Special requirements")


class RecommendationRequest(BaseModel):
    """Request for pet recommendations"""
    customer_id: str = Field(..., description="Customer identifier")
    preferences: CustomerPreferences = Field(..., description="Customer preferences")
    exclude_pets: list[str] = Field(default_factory=list, description="Pet IDs to exclude")
    max_recommendations: int = Field(default=5, description="Maximum recommendations to return")


class PetRecommendation(BaseModel):
    """Single pet recommendation"""
    pet_id: str = Field(..., description="Pet identifier")
    confidence_score: float = Field(..., description="Recommendation confidence (0-1)")
    reasoning: str = Field(..., description="Why this pet is recommended")
    match_factors: dict[str, float] = Field(..., description="Detailed matching factors")
    alternative_suggestions: list[str] = Field(default_factory=list, description="Alternative pets")
    price_optimization: dict[str, Any] | None = Field(None, description="Price optimization suggestions")


class RecommendationResponse(BaseModel):
    """Response containing pet recommendations"""
    recommendations: list[PetRecommendation] = Field(..., description="List of recommendations")
    model_version: str = Field(..., description="ML model version used")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    fallback_used: bool = Field(default=False, description="Whether fallback logic was used")
    a_b_test_variant: str = Field(..., description="A/B test variant used")


class ModelMetrics(BaseModel):
    """Model performance metrics"""
    total_requests: int
    successful_predictions: int
    average_confidence: float
    model_accuracy: float
    processing_time_p95: float
    fallback_rate: float
    last_updated: str


# In-memory analytics tracking
class MLAnalytics:
    """Analytics tracker for ML service performance"""

    def __init__(self):
        self.metrics = {
            "total_requests": 0,
            "successful_predictions": 0,
            "processing_times": [],
            "confidence_scores": [],
            "fallback_count": 0,
            "model_versions": {},
            "a_b_test_results": {"algorithm_v1": 0, "algorithm_v2": 0},
            "customer_segments": {},
            "prediction_accuracy": []
        }

    def track_prediction(self, processing_time: float, confidence: float,
                        model_version: str, fallback_used: bool = False,
                        a_b_variant: str = "algorithm_v1"):
        """Track prediction metrics"""
        self.metrics["total_requests"] += 1

        if not fallback_used:
            self.metrics["successful_predictions"] += 1
            self.metrics["confidence_scores"].append(confidence)
        else:
            self.metrics["fallback_count"] += 1

        self.metrics["processing_times"].append(processing_time)

        # Track model versions
        if model_version not in self.metrics["model_versions"]:
            self.metrics["model_versions"][model_version] = 0
        self.metrics["model_versions"][model_version] += 1

        # Track A/B test results
        self.metrics["a_b_test_results"][a_b_variant] += 1

    def get_current_metrics(self) -> ModelMetrics:
        """Get current model performance metrics"""
        processing_times = self.metrics["processing_times"]
        confidence_scores = self.metrics["confidence_scores"]

        return ModelMetrics(
            total_requests=self.metrics["total_requests"],
            successful_predictions=self.metrics["successful_predictions"],
            average_confidence=np.mean(confidence_scores) if confidence_scores else 0.0,
            model_accuracy=0.87,  # Simulated accuracy
            processing_time_p95=np.percentile(processing_times, 95) if processing_times else 0.0,
            fallback_rate=self.metrics["fallback_count"] / max(self.metrics["total_requests"], 1),
            last_updated=datetime.now().isoformat()
        )


# Global analytics instance
ml_analytics = MLAnalytics()


# ML Models and Logic
class PetRecommendationEngine:
    """Main recommendation engine with multiple algorithms"""

    def __init__(self):
        self.model_version = "recommendation_engine_v2.1.0"
        self.pet_database = self._initialize_pet_database()

    def _initialize_pet_database(self) -> dict[str, dict[str, Any]]:
        """Initialize the pet database for recommendations"""
        return {
            "golden-retriever-001": {
                "id": "golden-retriever-001",
                "name": "Buddy",
                "category": "dog",
                "breed": "Golden Retriever",
                "age_months": 8,
                "price": 1200.00,
                "activity_level": "high",
                "living_space_requirement": "house_with_yard",
                "experience_required": "intermediate",
                "care_difficulty": 0.6,
                "social_needs": 0.9,
                "grooming_needs": 0.7,
                "training_difficulty": 0.4,
                "allergenic": False
            },
            "persian-cat-002": {
                "id": "persian-cat-002",
                "name": "Princess",
                "category": "cat",
                "breed": "Persian",
                "age_months": 12,
                "price": 800.00,
                "activity_level": "low",
                "living_space_requirement": "apartment",
                "experience_required": "beginner",
                "care_difficulty": 0.8,
                "social_needs": 0.4,
                "grooming_needs": 0.9,
                "training_difficulty": 0.2,
                "allergenic": True
            },
            "rabbit-fluffy-003": {
                "id": "rabbit-fluffy-003",
                "name": "Fluffy",
                "category": "small_animal",
                "breed": "Holland Lop",
                "age_months": 6,
                "price": 150.00,
                "activity_level": "medium",
                "living_space_requirement": "apartment",
                "experience_required": "beginner",
                "care_difficulty": 0.3,
                "social_needs": 0.6,
                "grooming_needs": 0.4,
                "training_difficulty": 0.1,
                "allergenic": False
            },
            "bearded-dragon-004": {
                "id": "bearded-dragon-004",
                "name": "Spike",
                "category": "reptile",
                "breed": "Bearded Dragon",
                "age_months": 18,
                "price": 300.00,
                "activity_level": "low",
                "living_space_requirement": "apartment",
                "experience_required": "intermediate",
                "care_difficulty": 0.7,
                "social_needs": 0.2,
                "grooming_needs": 0.1,
                "training_difficulty": 0.0,
                "allergenic": False
            },
            "canary-sunny-005": {
                "id": "canary-sunny-005",
                "name": "Sunny",
                "category": "bird",
                "breed": "Canary",
                "age_months": 10,
                "price": 75.00,
                "activity_level": "medium",
                "living_space_requirement": "apartment",
                "experience_required": "beginner",
                "care_difficulty": 0.4,
                "social_needs": 0.5,
                "grooming_needs": 0.2,
                "training_difficulty": 0.3,
                "allergenic": False
            }
        }

    async def generate_recommendations(self, request: RecommendationRequest) -> RecommendationResponse:
        """Generate ML-powered pet recommendations"""
        start_time = time.time()

        try:
            # Select A/B test variant
            a_b_variant = "algorithm_v2" if random.random() < 0.5 else "algorithm_v1"

            # Apply the selected algorithm
            if a_b_variant == "algorithm_v2":
                recommendations = await self._advanced_recommendation_algorithm(request)
            else:
                recommendations = await self._basic_recommendation_algorithm(request)

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Track analytics
            avg_confidence = np.mean([r.confidence_score for r in recommendations]) if recommendations else 0.0
            ml_analytics.track_prediction(
                processing_time_ms, avg_confidence, self.model_version,
                fallback_used=False, a_b_variant=a_b_variant
            )

            return RecommendationResponse(
                recommendations=recommendations,
                model_version=self.model_version,
                processing_time_ms=processing_time_ms,
                fallback_used=False,
                a_b_test_variant=a_b_variant
            )

        except Exception as e:
            logger.error(f"ML recommendation failed: {e}")
            # Fallback to basic recommendations
            return await self._fallback_recommendations(request, start_time)

    async def _advanced_recommendation_algorithm(self, request: RecommendationRequest) -> list[PetRecommendation]:
        """Advanced ML algorithm with multiple factors"""
        recommendations = []
        preferences = request.preferences

        for pet_id, pet_data in self.pet_database.items():
            if pet_id in request.exclude_pets:
                continue

            # Calculate match score using weighted factors
            match_factors = await self._calculate_match_factors(pet_data, preferences)
            overall_score = self._calculate_weighted_score(match_factors)

            if overall_score > 0.3:  # Minimum threshold
                recommendation = PetRecommendation(
                    pet_id=pet_id,
                    confidence_score=overall_score,
                    reasoning=self._generate_reasoning(match_factors, pet_data),
                    match_factors=match_factors,
                    alternative_suggestions=self._get_alternatives(pet_data),
                    price_optimization=self._calculate_price_optimization(pet_data, preferences)
                )
                recommendations.append(recommendation)

        # Sort by confidence score and limit results
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        return recommendations[:request.max_recommendations]

    async def _basic_recommendation_algorithm(self, request: RecommendationRequest) -> list[PetRecommendation]:
        """Basic recommendation algorithm"""
        recommendations = []
        preferences = request.preferences

        for pet_id, pet_data in self.pet_database.items():
            if pet_id in request.exclude_pets:
                continue

            # Simple category and budget matching
            category_match = pet_data["category"] in preferences.pet_types
            price_match = preferences.budget_range[0] <= pet_data["price"] <= preferences.budget_range[1]

            if category_match and price_match:
                confidence = random.uniform(0.6, 0.9)
                recommendation = PetRecommendation(
                    pet_id=pet_id,
                    confidence_score=confidence,
                    reasoning=f"Good match for {pet_data['category']} preference and budget",
                    match_factors={"category": 1.0, "price": 1.0},
                    alternative_suggestions=[]
                )
                recommendations.append(recommendation)

        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        return recommendations[:request.max_recommendations]

    async def _calculate_match_factors(self, pet_data: dict[str, Any],
                                     preferences: CustomerPreferences) -> dict[str, float]:
        """Calculate detailed matching factors"""
        factors = {}

        # Category preference matching
        factors["category_match"] = 1.0 if pet_data["category"] in preferences.pet_types else 0.0

        # Activity level matching
        activity_mapping = {"low": 0.2, "medium": 0.5, "high": 0.8}
        pet_activity = activity_mapping.get(pet_data["activity_level"], 0.5)
        pref_activity = activity_mapping.get(preferences.activity_level, 0.5)
        factors["activity_match"] = 1.0 - abs(pet_activity - pref_activity)

        # Living situation compatibility
        living_compatibility = {
            ("apartment", "apartment"): 1.0,
            ("apartment", "house"): 0.8,
            ("house_with_yard", "house"): 1.0,
            ("house_with_yard", "apartment"): 0.3
        }
        factors["living_match"] = living_compatibility.get(
            (pet_data["living_space_requirement"], preferences.living_situation), 0.5
        )

        # Experience level matching
        experience_mapping = {"beginner": 0.2, "intermediate": 0.5, "expert": 0.8}
        pet_exp = experience_mapping.get(pet_data["experience_required"], 0.5)
        user_exp = experience_mapping.get(preferences.experience_with_pets, 0.5)
        factors["experience_match"] = 1.0 if user_exp >= pet_exp else user_exp / pet_exp

        # Price compatibility
        min_budget, max_budget = preferences.budget_range
        if min_budget <= pet_data["price"] <= max_budget:
            factors["price_match"] = 1.0
        elif pet_data["price"] < min_budget:
            factors["price_match"] = 0.8  # Cheaper is often good
        else:
            factors["price_match"] = max(0.0, 1.0 - (pet_data["price"] - max_budget) / max_budget)

        # Care requirements
        factors["care_difficulty"] = 1.0 - pet_data["care_difficulty"]

        return factors

    def _calculate_weighted_score(self, match_factors: dict[str, float]) -> float:
        """Calculate weighted overall match score"""
        weights = {
            "category_match": 0.25,
            "activity_match": 0.20,
            "living_match": 0.20,
            "experience_match": 0.15,
            "price_match": 0.15,
            "care_difficulty": 0.05
        }

        score = sum(match_factors.get(factor, 0) * weight
                   for factor, weight in weights.items())

        # Add some randomness for diversity
        score += random.uniform(-0.05, 0.05)
        return max(0.0, min(1.0, score))

    def _generate_reasoning(self, match_factors: dict[str, float], pet_data: dict[str, Any]) -> str:
        """Generate human-readable reasoning"""
        strong_points = [factor for factor, score in match_factors.items() if score > 0.8]

        reasons = []
        if "category_match" in strong_points:
            reasons.append(f"Perfect match for your {pet_data['category']} preference")
        if "activity_match" in strong_points:
            reasons.append(f"Activity level aligns with your lifestyle")
        if "living_match" in strong_points:
            reasons.append(f"Well-suited for your living situation")
        if "experience_match" in strong_points:
            reasons.append(f"Appropriate for your experience level")
        if "price_match" in strong_points:
            reasons.append(f"Within your budget range")

        if not reasons:
            reasons.append("Good overall compatibility based on your preferences")

        return ". ".join(reasons)

    def _get_alternatives(self, pet_data: dict[str, Any]) -> list[str]:
        """Get alternative pet suggestions"""
        alternatives = []
        same_category = [pid for pid, pdata in self.pet_database.items()
                        if pdata["category"] == pet_data["category"] and pid != pet_data["id"]]
        alternatives.extend(same_category[:2])
        return alternatives

    def _calculate_price_optimization(self, pet_data: dict[str, Any],
                                    preferences: CustomerPreferences) -> dict[str, Any] | None:
        """Calculate price optimization suggestions"""
        min_budget, max_budget = preferences.budget_range
        price = pet_data["price"]

        if price > max_budget * 0.8:  # If near budget limit
            return {
                "suggested_payment_plan": True,
                "monthly_payment": round(price / 12, 2),
                "savings_tip": "Consider pet insurance to reduce long-term costs"
            }

        return None

    async def _fallback_recommendations(self, request: RecommendationRequest,
                                      start_time: float) -> RecommendationResponse:
        """Fallback recommendations when ML fails"""
        logger.info("Using fallback recommendation logic")

        # Simple category-based fallback
        fallback_recs = []
        for pet_type in request.preferences.pet_types:
            for pet_id, pet_data in self.pet_database.items():
                if pet_data["category"] == pet_type:
                    rec = PetRecommendation(
                        pet_id=pet_id,
                        confidence_score=0.6,
                        reasoning=f"Fallback recommendation for {pet_type}",
                        match_factors={"category": 1.0},
                        alternative_suggestions=[]
                    )
                    fallback_recs.append(rec)
                    break

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Track fallback usage
        ml_analytics.track_prediction(processing_time_ms, 0.6, self.model_version, fallback_used=True)

        return RecommendationResponse(
            recommendations=fallback_recs[:request.max_recommendations],
            model_version=f"{self.model_version}-fallback",
            processing_time_ms=processing_time_ms,
            fallback_used=True,
            a_b_test_variant="fallback"
        )


# Initialize recommendation engine
recommendation_engine = PetRecommendationEngine()


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ml-pet-advisor",
        "version": "1.0.0",
        "model_version": recommendation_engine.model_version,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/recommendations", response_model=RecommendationResponse)
async def get_pet_recommendations(request: RecommendationRequest):
    """Get ML-powered pet recommendations"""
    try:
        logger.info(f"Generating recommendations for customer {request.customer_id}")
        response = await recommendation_engine.generate_recommendations(request)
        logger.info(f"Generated {len(response.recommendations)} recommendations in {response.processing_time_ms}ms")
        return response
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")


@app.get("/metrics", response_model=ModelMetrics)
async def get_model_metrics():
    """Get current model performance metrics"""
    return ml_analytics.get_current_metrics()


@app.get("/analytics/summary")
async def get_analytics_summary():
    """Get detailed analytics summary for observability"""
    metrics = ml_analytics.get_current_metrics()

    return {
        "model_performance": {
            "total_requests": metrics.total_requests,
            "success_rate": (metrics.successful_predictions / max(metrics.total_requests, 1)) * 100,
            "average_confidence": metrics.average_confidence,
            "fallback_rate": metrics.fallback_rate * 100,
            "processing_time_p95": metrics.processing_time_p95
        },
        "a_b_testing": ml_analytics.metrics["a_b_test_results"],
        "model_versions": ml_analytics.metrics["model_versions"],
        "recommendation_trends": {
            "confidence_distribution": {
                "high": len([s for s in ml_analytics.metrics["confidence_scores"] if s > 0.8]),
                "medium": len([s for s in ml_analytics.metrics["confidence_scores"] if 0.5 < s <= 0.8]),
                "low": len([s for s in ml_analytics.metrics["confidence_scores"] if s <= 0.5])
            }
        }
    }


@app.post("/simulate/recommendation-load")
async def simulate_recommendation_load(requests_count: int = 100):
    """Simulate recommendation load for testing/demo purposes"""
    logger.info(f"Simulating {requests_count} recommendation requests")

    # Sample customer profiles for simulation
    sample_preferences = [
        CustomerPreferences(
            pet_types=["dog"],
            activity_level="high",
            living_situation="house",
            experience_with_pets="intermediate",
            budget_range=(800, 2000)
        ),
        CustomerPreferences(
            pet_types=["cat"],
            activity_level="low",
            living_situation="apartment",
            experience_with_pets="beginner",
            budget_range=(200, 800)
        ),
        CustomerPreferences(
            pet_types=["small_animal", "bird"],
            activity_level="medium",
            living_situation="apartment",
            experience_with_pets="beginner",
            budget_range=(50, 300)
        )
    ]

    results = []
    for i in range(requests_count):
        customer_prefs = random.choice(sample_preferences)
        request = RecommendationRequest(
            customer_id=f"sim-customer-{i}",
            preferences=customer_prefs,
            max_recommendations=3
        )

        try:
            response = await recommendation_engine.generate_recommendations(request)
            results.append({
                "success": True,
                "recommendations_count": len(response.recommendations),
                "processing_time_ms": response.processing_time_ms,
                "confidence_avg": np.mean([r.confidence_score for r in response.recommendations]) if response.recommendations else 0
            })
        except Exception as e:
            results.append({"success": False, "error": str(e)})

        # Small delay to simulate realistic load
        await asyncio.sleep(0.01)

    success_count = len([r for r in results if r.get("success")])
    avg_processing_time = np.mean([r.get("processing_time_ms", 0) for r in results if r.get("success")])

    return {
        "simulation_summary": {
            "total_requests": requests_count,
            "successful_requests": success_count,
            "success_rate": (success_count / requests_count) * 100,
            "average_processing_time_ms": avg_processing_time,
            "current_metrics": ml_analytics.get_current_metrics()
        },
        "detailed_results": results[:10]  # Return first 10 for brevity
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
