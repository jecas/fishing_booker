from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from app.availability import get_unavailability_reasons
from app.models import Captains, Charter, Trip, CaptainDayOff, Booking, Customer
from tests.base import DatabaseTestCase


class AvailabilityTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()

        captain = Captains(first_name="Test", last_name="Captain", email="captain@example.com", phone="+381641111111")
        charter = Charter(captain=captain, title="Test charter", description="Charter created by the test.")
        self.trip = Trip(charter=charter, title="Regular trip", description="Trip created by the test.",
                        price=Decimal("50.00"), currency="USD", pricing_model="per_person", min_group_size=2,
                        max_group_size=6, trip_type="regular")

        self.session.add_all([captain, charter, self.trip])
        self.session.flush()
        self.now = datetime(2030, 6, 1, tzinfo=timezone.utc)
        self.trip_date = date(2030, 6, 16)

    def _create_booking(self, status, expires_at):
        customer = Customer(first_name="Test", last_name="Customer", email="customer@example.com", phone="+381641111111")

        booking = Booking(trip=self.trip, charter_id=self.trip.charter_id, customer=customer, trip_date=self.trip_date,
                          group_size=4, total_price=Decimal("200.00"), currency="USD", status=status,
                          created_at=self.now - timedelta(hours=1), expires_at=expires_at)

        self.session.add_all([customer, booking])
        self.session.flush()

        return booking

    def test_regular_trip_is_available(self):
        reasons = get_unavailability_reasons(session=self.session, trip=self.trip, trip_date=self.trip_date,
                                             group_size=4, now=self.now)

        self.assertEqual(reasons, [])

    def test_group_size_boundaries(self):
        examples = [(1, ["GROUP_SIZE_OUT_OF_RANGE"]), (2, []), (6, []), (7, ["GROUP_SIZE_OUT_OF_RANGE"])]

        for group_size, expected in examples:
            with self.subTest(group_size=group_size):
                reasons = get_unavailability_reasons(session=self.session, trip=self.trip, trip_date=self.trip_date,
                                                     group_size=group_size, now=self.now)
                self.assertCountEqual(reasons, expected)

    def test_season_boundaries(self):
        self.trip.trip_type = "seasonal"
        self.trip.season_start = date(2030, 6, 10)
        self.trip.season_end = date(2030, 6, 20)

        self.session.flush()

        examples = [(date(2030, 6, 9), ["OUTSIDE_SEASON"]),
                    (date(2030, 6, 10), []),
                    (date(2030, 6, 20), []),
                    (date(2030, 6, 21), ["OUTSIDE_SEASON"])]

        for trip_date, expected in examples:
            with self.subTest(trip_date=trip_date):
                reasons = get_unavailability_reasons(session=self.session, trip=self.trip, trip_date=trip_date,
                                                     group_size=4, now=self.now)
                self.assertCountEqual(reasons, expected)

    def test_past_date_is_unavailable(self):
        reasons = get_unavailability_reasons(session=self.session, trip=self.trip, trip_date=date(2030, 5, 31),
                                             group_size=4, now=self.now)
        self.assertEqual(reasons, ["TRIP_DATE_IN_PAST"])

    def test_today_is_allowed(self):
        reasons = get_unavailability_reasons(session=self.session, trip=self.trip, trip_date=self.now.date(),
                                             group_size=4, now=self.now)
        self.assertEqual(reasons, [])

    def test_captain_day_off(self):
        self.session.add(CaptainDayOff(captain_id=self.trip.charter.captain_id, day=self.trip_date))
        self.session.flush()

        reasons = get_unavailability_reasons(session=self.session, trip=self.trip, trip_date=self.trip_date,
                                             group_size=4, now=self.now)
        self.assertEqual(reasons, ["CAPTAIN_DAY_OFF"])

    def test_all_applicable_reasons_are_returned(self):
        self.trip.trip_type = "seasonal"
        self.trip.season_start = date(2030, 7, 1)
        self.trip.season_end = date(2030, 7, 31)

        self.session.add(CaptainDayOff(captain_id=self.trip.charter.captain_id, day=self.trip_date))
        self.session.flush()

        reasons = get_unavailability_reasons(session=self.session, trip=self.trip, trip_date=self.trip_date,
                                             group_size=8, now=self.now)

        self.assertCountEqual(reasons,["GROUP_SIZE_OUT_OF_RANGE", "OUTSIDE_SEASON", "CAPTAIN_DAY_OFF"])

    def test_booking_statuses_and_expiration(self):
        future = self.now + timedelta(minutes=15)
        past = self.now - timedelta(minutes=1)

        examples = [("PENDING", future, True), ("PENDING", self.now, False), ("PENDING", past, False),
                    ("PROCESSING", past, True), ("CONFIRMED", past, True), ("FAILED", future, False),
                    ("EXPIRED", past, False)]

        for status, expires_at, should_block in examples:
            with self.subTest(status=status, expires_at=expires_at):
                booking = self._create_booking(status=status, expires_at=expires_at)

                reasons = get_unavailability_reasons(session=self.session, trip=self.trip, trip_date=self.trip_date,
                                                     group_size=4, now=self.now)

                expected = ["CHARTER_ALREADY_BOOKED"] if should_block else []

                self.assertCountEqual(reasons, expected)
                self.session.delete(booking)
                self.session.flush()

    def test_booking_blocks_other_trip_of_same_charter(self):
        self._create_booking(status="CONFIRMED", expires_at=self.now + timedelta(minutes=15))

        other_trip = Trip(charter=self.trip.charter, title="Another trip",
                          description="Another trip on the same charter.", price=Decimal("300.00"), currency="USD",
                          pricing_model="per_trip", min_group_size=2, max_group_size=6, trip_type="regular")

        self.session.add(other_trip)
        self.session.flush()

        reasons = get_unavailability_reasons(session=self.session, trip=other_trip, trip_date=self.trip_date,
                                             group_size=4, now=self.now)
        self.assertEqual(reasons, ["CHARTER_ALREADY_BOOKED"])

    def test_booking_does_not_block_another_date(self):
        self._create_booking(status="CONFIRMED", expires_at=self.now + timedelta(minutes=15))

        reasons = get_unavailability_reasons(session=self.session, trip=self.trip,
                                             trip_date=self.trip_date + timedelta(days=1), group_size=4, now=self.now)
        self.assertEqual(reasons, [])
