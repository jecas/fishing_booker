from datetime import date
from uuid import uuid4
from sqlalchemy import delete, select

from app.booking_service import create_booking
from app.db import SessionLocal
from app.models import Booking, Customer, Payment
from app.payment_client import PaymentProviderUnavailable
from app.payment_service import process_payment


with SessionLocal.begin() as session:
    customer = Customer(first_name="Payment Recovery", last_name="Test", email="payment-recovery@example.com",
                        phone="+381641111111")

    session.add(customer)
    session.flush()

    booking = create_booking(session=session, trip_id=1, customer_id=customer.id,
                             trip_date=date(2027, 6, 20), group_size=4)

    customer_id = customer.id
    booking_id = booking.id

key = str(uuid4())

try:
    with SessionLocal() as session:
        try:
            process_payment(session=session, booking_id=booking_id, idempotency_key=key,
                            payment_token="tok_timeout_after_charge")
        except PaymentProviderUnavailable:
            assert not session.in_transaction()
            print("PASS: Lost response reported as unknown outcome")
        else:
            raise AssertionError("Expected an unknown payment outcome.")

    with SessionLocal() as session:
        booking = session.get(Booking, booking_id)

        payments = session.scalars(select(Payment).where(Payment.booking_id == booking_id)).all()

        assert booking.status == "PROCESSING"
        assert len(payments) == 1
        assert payments[0].status == "PROCESSING"

        payment_id = payments[0].id
        print("PASS: Processing state persisted after the error")

    with SessionLocal() as session:
        recovered = process_payment(session=session, booking_id=booking_id, idempotency_key=key,
                                    payment_token="tok_timeout_after_charge")

        assert recovered.booking.status == "CONFIRMED"
        assert recovered.payment.status == "SUCCEEDED"
        assert recovered.payment.id == payment_id
        print("PASS: Original payment recovered and booking confirmed")

    with SessionLocal() as session:
        payments = session.scalars(select(Payment).where(Payment.booking_id == booking_id)).all()

        assert len(payments) == 1
        assert payments[0].id == payment_id
        assert payments[0].provider_reference is not None
        print("PASS: No additional payment attempt created")
finally:
    with SessionLocal.begin() as session:
        session.execute(delete(Payment).where(Payment.booking_id == booking_id))
        session.execute(delete(Booking).where(Booking.id == booking_id))
        session.execute(delete(Customer).where(Customer.id == customer_id))

    print("Temporary booking data removed.")