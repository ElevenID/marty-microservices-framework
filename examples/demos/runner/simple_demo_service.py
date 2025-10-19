import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Demo Service", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "Demo service is running!"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
