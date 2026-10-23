from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.booking_service import create_booking
from app.db import SessionLocal
from app.models import Customer


with SessionLocal() as session:
    try:
        customer = Customer(
            first_name="Test",
            last_name="Customer",
            email="expiration-test@example.com",
            phone="+381641111111",
        )

        session.add(customer)
        session.flush()

        old_booking = create_booking(
            session=session,
            trip_id=1,
            customer_id=customer.id,
            trip_date=date(2027, 6, 16),
            group_size=4,
        )

        now = datetime.now(timezone.utc)

        old_booking.created_at = now - timedelta(minutes=30)
        old_booking.expires_at = now - timedelta(minutes=1)

        session.flush()

        assert old_booking.status == "PENDING"

        new_booking = create_booking(
            session=session,
            trip_id=3,
            customer_id=customer.id,
            trip_date=date(2027, 6, 16),
            group_size=4,
        )

        session.refresh(old_booking)

        assert old_booking.status == "EXPIRED"
        print("PASS: Old pending booking marked as expired")

        assert new_booking.id != old_booking.id
        assert new_booking.status == "PENDING"
        print("PASS: New booking created for the same charter and date")

        assert new_booking.total_price == Decimal("300.00")
        print("PASS: Per-trip price is fixed at 300 USD")

    finally:
        session.rollback()

print("Checks passed. Temporary data rolled back.")