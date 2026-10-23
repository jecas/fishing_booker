from pydantic import BaseModel, ConfigDict, Field
from datetime import date
from decimal import Decimal


class HealthResponse(BaseModel):
    status: str


class CharterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    captain_id: int
    title: str
    description: str


class CaptainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone: str


class CharterPhotoResponse(BaseModel):
    id: int
    url: str


class CharterDetailsResponse(CharterResponse):
    captain: CaptainResponse
    photos: list[CharterPhotoResponse]


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    charter_id: int
    title: str
    description: str

    price: Decimal
    currency: str
    pricing_model: str

    min_group_size: int
    max_group_size: int

    trip_type: str
    season_start: date | None
    season_end: date | None


class TripAvailabilityResponse(TripResponse):
    available: bool | None = None
    unavailability_reasons: list[str] = Field(default_factory=list)