from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Mock Reviews Provider")


class ReviewResponse(BaseModel):
    id: str
    author: str
    rating: int = Field(ge=1, le=5)
    text: str


class ReviewsResponse(BaseModel):
    reviews: list[ReviewResponse]


@app.get("/businesses/{business_id}/reviews", response_model=ReviewsResponse)
def get_reviews(business_id: str):
    if business_id == "unavailable":
        raise HTTPException(status_code=503, detail="Reviews provider is unavailable.")

    if business_id == "demo-charter":
        return {
            "reviews": [
                {
                    "id": "review-1",
                    "author": "Ana",
                    "rating": 5,
                    "text": "Great trip and a helpful captain."
                },
                {
                    "id": "review-2",
                    "author": "Mark",
                    "rating": 4,
                    "text": "Enjoyable boat trip."
                }
            ]
        }

    return {"reviews": []}