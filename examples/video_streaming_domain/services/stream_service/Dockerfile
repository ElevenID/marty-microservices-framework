FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install fastapi uvicorn pydantic httpx

COPY examples/video_streaming_domain/services/stream_service/ /app/stream_service/

ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "stream_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
