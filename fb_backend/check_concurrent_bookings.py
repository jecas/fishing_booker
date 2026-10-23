from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

from sqlalchemy import delete, select

from app.booking_service import create_booking
from app.db import SessionLocal
from app.models import Booking, Captains, Charter, Customer, Trip


with SessionLocal.begin() as session:
    captain = session.get(Captains, 1)

    if captain is None:
        raise ValueError("Captain 1 must exist.")

    customer = Customer(
        first_name="Concurrency",
        last_name="Test",
        email="concurrency@example.com",
        phone="+381641111111",
    )

    charter = Charter(
        captain_id=captain.id,
        title="Temporary concurrency test",
        description="Temporary test charter.",
    )

    session.add_all([customer, charter])
    session.flush()

    trips = [
        Trip(
            charter=charter,
            title=f"Temporary trip {number}",
            description="Temporary test trip.",
            price=Decimal("50.00"),
            currency="USD",
            pricing_model="per_person",
            min_group_size=2,
            max_group_size=6,
            trip_type="regular",
        )
        for number in (1, 2)
    ]

    session.add_all(trips)
    session.flush()

    customer_id = customer.id
    charter_id = charter.id
    trip_ids = [trip.id for trip in trips]


barrier = Barrier(2)


def attempt_booking(trip_id: int) -> str:
    with SessionLocal() as session:
        try:
            with session.begin():
                barrier.wait(timeout=10)

                create_booking(
                    session=session,
                    trip_id=trip_id,
                    customer_id=customer_id,
                    trip_date=date(2027, 6, 16),
                    group_size=4,
                )

            return "CREATED"

        except ValueError as exc:
            if "CHARTER_ALREADY_BOOKED" not in str(exc):
                raise

            return "REJECTED"


try:
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt_booking, trip_ids))

    assert sorted(results) == ["CREATED", "REJECTED"], results
    print("PASS: One booking created, the other rejected")

    with SessionLocal() as session:
        bookings = session.scalars(
            select(Booking).where(
                Booking.charter_id == charter_id,
            )
        ).all()

        assert len(bookings) == 1
        assert bookings[0].status == "PENDING"

        print("PASS: Exactly one pending booking exists in the database")

finally:
    with SessionLocal.begin() as session:
        session.execute(
            delete(Booking).where(Booking.charter_id == charter_id)
        )
        session.execute(
            delete(Trip).where(Trip.charter_id == charter_id)
        )
        session.execute(
            delete(Charter).where(Charter.id == charter_id)
        )
        session.execute(
            delete(Customer).where(Customer.id == customer_id)
        )

    print("Temporary test data removed.")