import hashlib
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.booking_service import expire_pending_bookings
from app.models import Booking, Captains, Payment
from app.payment_client import ProviderChargeResponse, charge_payment
from app.schemas import BookingResponse, PaymentResponse, PaymentResultResponse


def prepare_payment(session: Session, booking_id: int, idempotency_key: str, payment_token: str) -> tuple[Booking, Payment]:
    booking = session.get(Booking, booking_id)

    if not booking:
        raise ValueError("Booking not found.")

    session.execute(select(Captains.id).where(Captains.id == booking.charter.captain_id).with_for_update()).scalar_one()
    session.refresh(booking)

    now = datetime.now(timezone.utc)

    expire_pending_bookings(session=session, charter_id=booking.charter_id, now=now)

    token_hash = hashlib.sha256(payment_token.encode("utf-8")).hexdigest()
    existing = session.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
    if existing:
        if existing.booking_id != booking.id or existing.token_hash != token_hash:
            raise ValueError("Idempotency key was used with a different request.")

        return booking, existing

    if booking.status != "PENDING":
        raise ValueError("Booking is not awaiting a new payment attempt.")

    if booking.trip_date < now.date():
        raise ValueError("Trip date cannot be in the past.")

    payment = Payment(booking_id=booking.id, idempotency_key=idempotency_key, token_hash=token_hash,
                      status="PROCESSING", created_at=now)

    booking.status = "PROCESSING"

    session.add(payment)
    session.flush()

    return booking, payment


def apply_payment_result(session: Session, payment_id: int, result: ProviderChargeResponse) -> tuple[Booking, Payment]:
    payment = session.get(Payment, payment_id)
    if not payment:
        raise ValueError("Payment not found.")

    booking = session.get(Booking, payment.booking_id)
    if not booking:
        raise ValueError("Booking not found.")

    session.execute(select(Captains.id).where(Captains.id == booking.charter.captain_id).with_for_update()).scalar_one()

    session.refresh(booking)
    session.refresh(payment)

    provider_reference = str(result.id)

    if payment.status != "PROCESSING":
        if payment.status != result.status or payment.provider_reference != provider_reference:
            raise ValueError("Provider result conflicts with the saved payment result.")

        return booking, payment

    if booking.status != "PROCESSING":
        raise ValueError("Booking is not processing this payment.")

    payment.status = result.status
    payment.provider_reference = provider_reference

    if result.status == "SUCCEEDED":
        booking.status = "CONFIRMED"
    else:
        now = datetime.now(timezone.utc)
        if booking.expires_at > now and booking.trip_date >= now.date():
            booking.status = "PENDING"
        else:
            booking.status = "EXPIRED"

    session.flush()

    return booking, payment


def process_payment(session: Session, booking_id: int, idempotency_key: str, payment_token: str) -> PaymentResultResponse:
    with session.begin():
        booking, payment = prepare_payment(session=session, booking_id=booking_id, idempotency_key=idempotency_key,
                                           payment_token=payment_token)

        if payment.status != "PROCESSING":
            return PaymentResultResponse(booking=BookingResponse.model_validate(booking),
                                         payment=PaymentResponse.model_validate(payment))

        payment_id = payment.id
        provider_key = payment.idempotency_key
        amount = booking.total_price
        currency = booking.currency

    result = charge_payment(idempotency_key=provider_key, payment_token=payment_token, amount=amount, currency=currency)

    with session.begin():
        booking, payment = apply_payment_result(session=session, payment_id=payment_id, result=result)
        response = PaymentResultResponse(booking=BookingResponse.model_validate(booking),
                                         payment=PaymentResponse.model_validate(payment))
        return response
