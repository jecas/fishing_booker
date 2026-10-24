from datetime import date
from uuid import uuid4

from app.booking_service import create_booking
from app.db import SessionLocal
from app.models import Customer
from app.payment_service import prepare_payment


with SessionLocal() as session:
    try:
        customer = Customer(first_name="Payment", last_name="Test", email="payment-test@example.com",
                            phone="+381641111111")

        session.add(customer)
        session.flush()

        booking = create_booking(session=session, trip_id=1, customer_id=customer.id,
                                 trip_date=date(2027, 6, 17), group_size=4)

        key = str(uuid4())

        prepared_booking, payment = prepare_payment(session=session, booking_id=booking.id, idempotency_key=key,
                                                    payment_token="tok_success")
        assert prepared_booking.status == "PROCESSING"
        assert payment.status == "PROCESSING"
        assert payment.booking_id == booking.id
        assert payment.provider_reference is None
        print("PASS: Booking and payment marked as processing")

        _, repeated = prepare_payment(session=session, booking_id=booking.id, idempotency_key=key,
                                      payment_token="tok_success")
        assert repeated.id == payment.id
        print("PASS: Same key returns the same payment attempt")

        try:
            prepare_payment(session=session, booking_id=booking.id, idempotency_key=key, payment_token="tok_declined")
        except ValueError as exc:
            assert str(exc) == "Idempotency key was used with a different request."
            print("PASS: Same key with a different token rejected")
        else:
            raise AssertionError("Expected an idempotency conflict.")

        try:
            prepare_payment(session=session, booking_id=booking.id, idempotency_key=str(uuid4()),
                            payment_token="tok_success")
        except ValueError as exc:
            assert str(exc) == "Booking is not awaiting a new payment attempt."
            print("PASS: Another payment attempt blocked while processing")
        else:
            raise AssertionError("Expected the new attempt to be blocked.")
    finally:
        session.rollback()

print("Checks passed. Temporary data rolled back.")