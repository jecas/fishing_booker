from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal


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


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=254)
    phone: str = Field(min_length=1, max_length=32)


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_id: int = Field(gt=0)
    trip_date: date
    group_size: int = Field(ge=1)
    customer: CustomerCreate


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    charter_id: int
    customer_id: int
    trip_date: date
    group_size: int
    total_price: Decimal
    currency: str
    status: str
    created_at: datetime
    expires_at: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    status: str
    created_at: datetime
    provider_reference: str | None


class PaymentResultResponse(BaseModel):
    booking: BookingResponse
    payment: PaymentResponse


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_token: Literal["tok_success", "tok_declined", "tok_timeout_after_charge"]