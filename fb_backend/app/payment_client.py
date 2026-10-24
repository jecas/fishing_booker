import os
import httpx
from uuid import UUID
from typing import Literal
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel


class PaymentProviderUnavailable(Exception):
    pass


class ProviderChargeResponse(BaseModel):
    id: UUID
    status: Literal["SUCCEEDED", "DECLINED"]
    created_at: datetime


def charge_payment(idempotency_key: str, payment_token: str, amount: Decimal, currency: str) -> ProviderChargeResponse:
    url = os.environ["PAYMENT_PROVIDER_URL"].rstrip("/") + "/charges"

    try:
        response = httpx.post(
            url,
            headers={"Idempotency-Key": idempotency_key},
            json={
                "amount": format(amount, ".2f"),
                "currency": currency,
                "payment_token": payment_token
            },
            timeout=httpx.Timeout(5.0, connect=2.0)
        )

        response.raise_for_status()
        return ProviderChargeResponse.model_validate(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise PaymentProviderUnavailable("Payment outcome could not be determined.") from exc