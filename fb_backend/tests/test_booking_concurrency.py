from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier
from sqlalchemy import select

from app.booking_service import create_booking
from app.db import SessionLocal
from app.exceptions import BookingConflictError
from app.models import Booking, Captains, Charter, Customer, Trip
from tests.base import DatabaseTestCase


class BookingConcurrencyTests(DatabaseTestCase):
    def test_only_one_booking_can_reserve_the_same_charter_and_date(self):
        captain = Captains(first_name="Test", last_name="Captain", email="captain@example.com", phone="+381641111111")
        customer = Customer(first_name="Test", last_name="Customer", email="customer@example.com", phone="+381642222222")
        charter = Charter(captain=captain, title="Concurrency test charter", description="Charter created by the test.")
        trips = [Trip(charter=charter, title=f"Test trip {number}", description="Trip created by the test.",
                      price=Decimal("50.00"), currency="USD", pricing_model="per_person", min_group_size=2,
                      max_group_size=6, trip_type="regular") for number in (1, 2)]

        self.session.add_all([captain, customer, charter, *trips])
        self.session.flush()

        customer_id = customer.id
        charter_id = charter.id
        trip_ids = [trip.id for trip in trips]
        self.session.commit()
        trip_date = datetime.now(timezone.utc).date() + timedelta(days=30)
        barrier = Barrier(2)

        def attempt_booking(trip_id):
            with SessionLocal() as session:
                try:
                    with session.begin():
                        session.execute(select(Trip.id).where(Trip.id == trip_id)).scalar_one()

                        barrier.wait(timeout=10)

                        create_booking(session=session, trip_id=trip_id, customer_id=customer_id, trip_date=trip_date,
                                       group_size=4)

                    return "CREATED"
                except BookingConflictError:
                    return "REJECTED"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt_booking, trip_ids))

        self.assertCountEqual(results, ["CREATED", "REJECTED"])

        bookings = self.session.scalars(select(Booking).where(Booking.charter_id == charter_id,
                                                              Booking.trip_date == trip_date)).all()

        self.assertEqual(len(bookings), 1)
        self.assertEqual(bookings[0].status, "PENDING")
        self.assertIn(bookings[0].trip_id, trip_ids)