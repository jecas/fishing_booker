from datetime import datetime, timezone, timedelta, date
from decimal import Decimal

from app.db import SessionLocal
from app.models import Trip, Booking, Customer
from app.availability import get_unavailability_reasons


examples = [
    ("PENDING", False, True),
    ("PENDING", True, False),
    ("PROCESSING", False, True),
    ("PROCESSING", True, True),
    ("CONFIRMED", True, True),
    ("FAILED", False, False),
    ("EXPIRED", True, False)
]


with SessionLocal() as session:
    try:
        booked_trip = session.get(Trip, 1)
        other_trip = session.get(Trip, 3)

        if not booked_trip or not other_trip:
            raise ValueError("Trips 1 and 3 must exist")

        assert booked_trip.charter_id == other_trip.charter_id

        customer = Customer(first_name="Eric", last_name="Clapton", email="eacailability@example.com",
                            phone="+381641111111")
        session.add(customer)
        session.flush()

        now = datetime.now(timezone.utc)
        trip_date = date(2027, 6, 16)

        for status, expired, should_block in examples:
            booking = Booking(
                trip_id=booked_trip.id,
                charter_id=booked_trip.charter_id,
                customer=customer,
                trip_date=trip_date,
                group_size=4,
                total_price=Decimal("200.00"),
                currency="USD",
                status=status,
                created_at=now - timedelta(minutes=30),
                expires_at=now - timedelta(minutes=1) if expired else now + timedelta(minutes=15)
            )
            session.add(booking)
            session.flush()

            reasons = get_unavailability_reasons(session, trip=other_trip, trip_date=trip_date, group_size=4)

            expected = ["CHARTER_ALREADY_BOOKED"] if should_block else []

            assert set(reasons) == set(expected), f"{status}, expired={expired}: expected {expected}, got {reasons}"

            print(f"PASS: {status}, expired={expired}")

            session.delete(booking)
            session.flush()
    finally:
        session.rollback()

print(f"\nAll {len(examples)} tests passed.")