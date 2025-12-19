FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install fastapi uvicorn pydantic httpx

COPY examples/video_streaming_domain/services/catalog_service/ /app/catalog_service/

ENV PYTHONPATH=/app

EXPOSE 8001

CMD ["uvicorn", "catalog_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
