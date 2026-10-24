import json
import hashlib
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from payment_service_mock.payment_store import initialize_database, get_or_create_charge


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Mock Payment Provider", lifespan=lifespan)


class HealthResponse(BaseModel):
    status: str


class ChargeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    payment_token: Literal["tok_success", "tok_declined", "tok_timeout_after_charge"]


class ChargeResponse(BaseModel):
    id: str
    status: Literal["SUCCEEDED", "DECLINED"]
    created_at: datetime


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.post("/charges", response_model=ChargeResponse,
    responses={
        409: {"description": "Idempotency key conflict"},
        504: {"description": "Simulated lost payment response"},
    }
)
def create_charge(payload: ChargeRequest, idempotency_key: UUID = Header(alias="Idempotency-Key")):
    request_data = {
        "amount": format(payload.amount, ".2f"),
        "currency": payload.currency,
        "payment_token": payload.payment_token
    }

    request_hash = hashlib.sha256(json.dumps(request_data, sort_keys=True).encode("utf-8")).hexdigest()

    status = "DECLINED" if payload.payment_token == "tok_declined" else "SUCCEEDED"

    try:
        charge, created = get_or_create_charge(idempotency_key=str(idempotency_key), request_hash=request_hash,
                                               status=status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if created and payload.payment_token == "tok_timeout_after_charge":
        raise HTTPException(status_code=504, detail="Simulated lost response after a successful charge.")

    return ChargeResponse(id=charge["id"], status=charge["status"], created_at=charge["created_at"])
