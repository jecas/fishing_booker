import os
import httpx
from urllib.parse import quote

from app.schemas import ReviewResponse, ReviewsProviderResponse


class ReviewsProviderUnavailable(Exception):
    pass


def get_reviews(business_id: str) -> list[ReviewResponse]:
    base_url = os.environ["REVIEWS_PROVIDER_URL"].rstrip("/")
    encoded_id = quote(business_id, safe="")

    try:
        response = httpx.get(f"{base_url}/businesses/{encoded_id}/reviews", timeout=httpx.Timeout(2.0, connect=1.0))

        response.raise_for_status()

        result = ReviewsProviderResponse.model_validate(response.json())

        return result.reviews
    except (httpx.HTTPError, ValueError) as exc:
        raise ReviewsProviderUnavailable("Reviews could not be retrieved.") from exc
