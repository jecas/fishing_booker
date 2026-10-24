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
                             trip_date=date(2027, 6, 21), group_size=4)

    customer_id = customer.id
    booking_id = booking.id

declined_key = str(uuid4())
success_key = str(uuid4())

try:
    with SessionLocal() as session:
        declined = process_payment(session=session, booking_id=booking_id, idempotency_key=declined_key,
                                   payment_token="tok_declined")

        assert declined.payment.status == "DECLINED"
        assert declined.booking.status == "PENDING"
        print("PASS: Decline keeps booking available for another attempt")

        repeated_decline = process_payment(session=session, booking_id=booking_id, idempotency_key=declined_key,
                                           payment_token="tok_declined")

        assert repeated_decline == declined
        print("PASS: Declined attempt can be replayed safely")

        succeeded = process_payment(session=session, booking_id=booking_id, idempotency_key=success_key,
                                    payment_token="tok_success")

        assert succeeded.booking.id == declined.booking.id
        assert succeeded.payment.id != declined.payment.id
        assert succeeded.payment.status == "SUCCEEDED"
        assert succeeded.booking.status == "CONFIRMED"
        print("PASS: New attempt confirms the same booking")

        old_attempt = process_payment(session=session, booking_id=booking_id, idempotency_key=declined_key,
                                      payment_token="tok_declined")

        assert old_attempt.payment.id == declined.payment.id
        assert old_attempt.payment.status == "DECLINED"
        assert old_attempt.booking.status == "CONFIRMED"
        print("PASS: Replaying an old decline cannot undo confirmation")

    with SessionLocal() as session:
        saved_booking = session.get(Booking, booking_id)
        first_payment = session.get(Payment, declined.payment.id)
        second_payment = session.get(Payment, succeeded.payment.id)

        assert saved_booking.status == "CONFIRMED"
        assert first_payment.status == "DECLINED"
        assert second_payment.status == "SUCCEEDED"
        print("PASS: Both attempt outcomes persisted")
finally:
    with SessionLocal.begin() as session:
        session.execute(delete(Payment).where(Payment.booking_id == booking_id))
        session.execute(delete(Booking).where(Booking.id == booking_id))
        session.execute(delete(Customer).where(Customer.id == customer_id))
    print("Temporary booking data removed.")