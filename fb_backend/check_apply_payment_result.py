from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.booking_service import create_booking
from app.db import SessionLocal
from app.models import Customer
from app.payment_client import ProviderChargeResponse
from app.payment_service import apply_payment_result, prepare_payment


def provider_result(status: str) -> ProviderChargeResponse:
    return ProviderChargeResponse(id=uuid4(), status=status, created_at=datetime.now(timezone.utc))


with SessionLocal() as session:
    try:
        customer = Customer(first_name="Payment", last_name="Result Test", email="payment-result@example.com",
                            phone="+381641111111")
        session.add(customer)
        session.flush()

        booking = create_booking(session=session, trip_id=1, customer_id=customer.id,
                                 trip_date=date(2027, 6, 18), group_size=4)

        _, first_payment = prepare_payment(session=session, booking_id=booking.id, idempotency_key=str(uuid4()),
                                           payment_token="tok_declined")
        declined_result = provider_result("DECLINED")
        apply_payment_result(session=session, payment_id=first_payment.id, result=declined_result)
        assert first_payment.status == "DECLINED"
        assert booking.status == "PENDING"
        print("PASS: Decline allows retry while the booking hold is valid")

        _, second_payment = prepare_payment(session=session, booking_id=booking.id, idempotency_key=str(uuid4()),
                                            payment_token="tok_success")
        assert second_payment.id != first_payment.id
        assert booking.status == "PROCESSING"
        print("PASS: New payment attempt created for the same booking")

        now = datetime.now(timezone.utc)
        booking.created_at = now - timedelta(minutes=30)
        booking.expires_at = now - timedelta(minutes=1)
        session.flush()
        success_result = provider_result("SUCCEEDED")
        apply_payment_result(session=session, payment_id=second_payment.id, result=success_result)
        assert second_payment.status == "SUCCEEDED"
        assert booking.status == "CONFIRMED"
        print("PASS: Success confirms booking even after hold expiration")

        apply_payment_result(session=session, payment_id=second_payment.id, result=success_result)
        assert booking.status == "CONFIRMED"
        print("PASS: Repeated result leaves booking confirmed")

        apply_payment_result(session=session, payment_id=first_payment.id, result=declined_result)
        assert booking.status == "CONFIRMED"
        print("PASS: Old declined result cannot undo confirmation")
    finally:
        session.rollback()

print("Checks passed. Temporary data rolled back.")