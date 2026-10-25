from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from app.booking_service import create_booking
from app.models import Captains, Charter, Customer, Trip
from app.exceptions import ResourceNotFoundError, BookingConflictError
from tests.base import DatabaseTestCase


class BookingServiceTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()

        captain = Captains(first_name="Test", last_name="Captain", email="captain@example.com", phone="+381641111111")
        charter = Charter(captain=captain, title="Test charter", description="Charter created by the test.")
        self.customer = Customer(first_name="Test", last_name="Customer", email="customer@example.com",
                                 phone="+381642222222")
        self.trip = Trip(charter=charter, title="Test trip", description="Trip created by the test.",
                         price=Decimal("50.00"), currency="USD", pricing_model="per_person", min_group_size=2,
                         max_group_size=6, trip_type="regular")
        self.session.add_all([captain, charter, self.customer, self.trip])
        self.session.flush()

        self.now = datetime(2030, 6, 1, tzinfo=timezone.utc)
        self.trip_date = date(2030, 6, 16)

    @patch("app.booking_service.datetime")
    def test_per_person_booking_price_and_initial_state(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        booking = create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                                 trip_date=self.trip_date, group_size=4)

        self.assertIsNotNone(booking.id)
        self.assertEqual(booking.trip_id, self.trip.id)
        self.assertEqual(booking.charter_id, self.trip.charter_id)
        self.assertEqual(booking.customer_id, self.customer.id)
        self.assertEqual(booking.total_price, Decimal("200.00"))
        self.assertEqual(booking.currency, "USD")
        self.assertEqual(booking.status, "PENDING")
        self.assertEqual(booking.created_at, self.now)
        self.assertEqual(booking.expires_at, self.now + timedelta(minutes=15))

    @patch("app.booking_service.datetime")
    def test_per_trip_price_is_not_multiplied_by_group_size(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        self.trip.pricing_model = "per_trip"
        self.trip.price = Decimal("300.00")
        self.session.flush()

        booking = create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                                 trip_date=self.trip_date, group_size=4)

        self.assertEqual(booking.total_price, Decimal("300.00"))

    @patch("app.booking_service.datetime")
    def test_booking_price_does_not_change_with_trip_price(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        booking = create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                                 trip_date=self.trip_date, group_size=4)

        self.trip.price = Decimal("100.00")
        self.session.flush()
        self.session.refresh(booking)

        self.assertEqual(booking.total_price, Decimal("200.00"))

    @patch("app.booking_service.datetime")
    def test_unavailable_group_size_is_rejected(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        with self.assertRaisesRegex(BookingConflictError,"GROUP_SIZE_OUT_OF_RANGE"):
            create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                           trip_date=self.trip_date, group_size=7)

    @patch("app.booking_service.datetime")
    def test_active_booking_blocks_another_booking(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                       trip_date=self.trip_date, group_size=4)

        with self.assertRaisesRegex(BookingConflictError,"CHARTER_ALREADY_BOOKED"):
            create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                           trip_date=self.trip_date, group_size=4)

    @patch("app.booking_service.datetime")
    def test_booking_can_be_replaced_at_expiration(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        old_booking = create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                                     trip_date=self.trip_date, group_size=4)

        deadline = old_booking.expires_at
        mocked_datetime.now.return_value = deadline

        new_booking = create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                                     trip_date=self.trip_date, group_size=4)

        self.session.refresh(old_booking)

        self.assertEqual(old_booking.status, "EXPIRED")
        self.assertEqual(new_booking.status, "PENDING")
        self.assertNotEqual(old_booking.id, new_booking.id)
        self.assertEqual(new_booking.created_at, deadline)

    @patch("app.booking_service.datetime")
    def test_missing_trip_is_rejected(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        with self.assertRaisesRegex(ResourceNotFoundError, "Trip not found"):
            create_booking(session=self.session, trip_id=0, customer_id=self.customer.id, trip_date=self.trip_date,
                           group_size=4)

    @patch("app.booking_service.datetime")
    def test_missing_customer_is_rejected(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        with self.assertRaisesRegex(ResourceNotFoundError, "Customer not found"):
            create_booking(session=self.session, trip_id=self.trip.id, customer_id=0, trip_date=self.trip_date,
                           group_size=4)

    @patch("app.booking_service.datetime")
    def test_past_date_is_rejected(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        with self.assertRaisesRegex(BookingConflictError,"Trip date cannot be in the past"):
            create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                           trip_date=self.now.date() - timedelta(days=1), group_size=4)

    @patch("app.booking_service.datetime")
    def test_processing_booking_is_not_expired(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        booking = create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                                 trip_date=self.trip_date, group_size=4)

        booking.status = "PROCESSING"
        self.session.flush()

        mocked_datetime.now.return_value = booking.expires_at + timedelta(minutes=1)

        with self.assertRaisesRegex(BookingConflictError,"CHARTER_ALREADY_BOOKED"):
            create_booking(session=self.session, trip_id=self.trip.id, customer_id=self.customer.id,
                           trip_date=self.trip_date, group_size=4)

        self.session.refresh(booking)

        self.assertEqual(booking.status, "PROCESSING")
