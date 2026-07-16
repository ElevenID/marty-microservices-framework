# Video Streaming Domain Example

This example demonstrates a microservices-based video streaming platform (like Netflix) built with the Marty Microservices Framework (MMF).

## Architecture

The domain consists of three microservices:

1.  **Catalog Service** (`port 8001`):
    *   Manages video metadata (title, description, category).
    *   Stores user watch history.
    *   Serves public domain video URLs (Blender Foundation).

2.  **Stream Service** (`port 8002`):
    *   Handles video streaming sessions.
    *   Validates user access.
    *   Tracks watch progress and syncs it to the Catalog Service.

3.  **Recommendation Service** (`port 8003`):
    *   Provides personalized video recommendations.
    *   Analyzes user watch history from the Catalog Service.

## Prerequisites

*   Python 3.9+
*   `uvicorn`
*   `httpx`
*   `fastapi`

## Running the Services

You will need three terminal windows to run the services simultaneously.

### 1. Start Catalog Service
```bash
uvicorn examples.video_streaming_domain.services.catalog_service.main:app --port 8001 --reload
```

### 2. Start Stream Service
```bash
export CATALOG_SERVICE_URL=http://localhost:8001
uvicorn examples.video_streaming_domain.services.stream_service.main:app --port 8002 --reload
```

### 3. Start Recommendation Service
```bash
export CATALOG_SERVICE_URL=http://localhost:8001
uvicorn examples.video_streaming_domain.services.recommendation_service.main:app --port 8003 --reload
```

## Usage Example

You can interact with the services using `curl` or the Swagger UI (e.g., `http://localhost:8001/docs`).

### 1. List Videos
```bash
curl http://localhost:8001/videos
```

### 2. Start a Stream (Simulated)
```bash
# Returns a session object
curl -X POST "http://localhost:8002/stream/big_buck_bunny" \
     -H "Authorization: Bearer user123"
```

### 3. Update Progress
```bash
curl -X POST "http://localhost:8002/progress" \
     -H "Authorization: Bearer user123" \
     -H "Content-Type: application/json" \
     -d '{"video_id": "big_buck_bunny", "timestamp_seconds": 120, "completed": false}'
```

### 4. Get Recommendations
```bash
curl "http://localhost:8003/recommendations" \
     -H "Authorization: Bearer user123"
```

## Authentication

This example uses a simplified session/token mechanism. Pass a `session_id` cookie or `Authorization: Bearer <user_id>` header to identify the user.
