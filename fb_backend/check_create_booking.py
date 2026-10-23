from datetime import date
from decimal import Decimal

from app.booking_service import create_booking
from app.db import SessionLocal
from app.models import Customer


with SessionLocal() as session:
    try:
        customer = Customer(
            first_name="Test",
            last_name="Customer",
            email="booking-test@example.com",
            phone="+381641111111",
        )

        session.add(customer)
        session.flush()

        booking = create_booking(
            session=session,
            trip_id=1,
            customer_id=customer.id,
            trip_date=date(2027, 6, 16),
            group_size=4,
        )

        assert booking.id is not None
        assert booking.charter_id == 2
        assert booking.customer_id == customer.id
        assert booking.total_price == Decimal("200.00")
        assert booking.currency == "USD"
        assert booking.status == "PENDING"
        assert (booking.expires_at - booking.created_at).total_seconds() == 900

        print("PASS: Booking created with correct price and expiration")

        try:
            create_booking(
                session=session,
                trip_id=3,
                customer_id=customer.id,
                trip_date=date(2027, 6, 16),
                group_size=4,
            )
        except ValueError as exc:
            assert "CHARTER_ALREADY_BOOKED" in str(exc), "Unexpected error: {exc}"
            print("PASS: Another trip on the same charter is blocked")
        else:
            raise AssertionError("Duplicate booking was allowed.")

    finally:
        session.rollback()

print("Checks passed. Temporary data rolled back.")