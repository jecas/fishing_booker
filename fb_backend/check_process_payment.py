from datetime import date
from uuid import uuid4
from sqlalchemy import delete

from app.booking_service import create_booking
from app.db import SessionLocal
from app.models import Booking, Customer, Payment
from app.payment_service import process_payment


with SessionLocal.begin() as session:
    customer = Customer(first_name="Full Payment", last_name="Test", email="full-payment@example.com",
                        phone="+381641111111")

    session.add(customer)
    session.flush()

    booking = create_booking(session=session, trip_id=1, customer_id=customer.id,
                             trip_date=date(2027, 6, 19), group_size=4)

    customer_id = customer.id
    booking_id = booking.id

key = str(uuid4())

try:
    with SessionLocal() as session:
        first = process_payment(session=session, booking_id=booking_id, idempotency_key=key,
                                payment_token="tok_success")

        assert first.booking.status == "CONFIRMED"
        assert first.payment.status == "SUCCEEDED"
        assert first.payment.provider_reference is not None
        assert not session.in_transaction()
        print("PASS: HTTP payment succeeded and booking confirmed")

        repeated = process_payment(session=session, booking_id=booking_id, idempotency_key=key,
                                   payment_token="tok_success")

        assert repeated == first
        assert not session.in_transaction()
        print("PASS: Replay returns the same payment and booking")

    with SessionLocal() as session:
        saved_booking = session.get(Booking, booking_id)
        saved_payment = session.get(Payment, first.payment.id)
        assert saved_booking.status == "CONFIRMED"
        assert saved_payment.status == "SUCCEEDED"
        print("PASS: Results persisted in PostgreSQL")

finally:
    with SessionLocal.begin() as session:
        session.execute(delete(Payment).where(Payment.booking_id == booking_id))
        session.execute(delete(Booking).where(Booking.id == booking_id))
        session.execute(delete(Customer).where(Customer.id == customer_id))
    print("Temporary booking data removed.")