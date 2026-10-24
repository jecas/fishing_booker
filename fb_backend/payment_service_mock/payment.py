from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Mock Payment Provider")


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}