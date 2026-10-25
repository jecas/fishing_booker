from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.models import Booking, Captains, Charter, Customer, Trip
from tests.base import DatabaseTestCase


class BookingApiTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()

        captain = Captains(first_name="Test", last_name="Captain", email="captain@example.com", phone="+381641111111")
        charter = Charter(captain=captain, title="Test charter", description="Test charter description.")
        trip = Trip(charter=charter, title="Test trip", description="Test trip description.", price=Decimal("50.00"),
                    currency="USD", pricing_model="per_person", min_group_size=2, max_group_size=6, trip_type="regular")
        self.session.add_all([captain, charter, trip])
        self.session.flush()
        self.trip_id = trip.id
        self.charter_id = charter.id
        self.session.commit()
        self.now = datetime(2030, 6, 1, tzinfo=timezone.utc)
        self.payload = {
            "trip_id": self.trip_id,
            "trip_date": date(2030, 6, 16).isoformat(),
            "group_size": 4,
            "customer": {
                "first_name": "Ana",
                "last_name": "Petrovic",
                "email": "ana@example.com",
                "phone": "+381642222222"
            }
        }

        self.client = self.enterContext(TestClient(app))

    @patch("app.booking_service.datetime")
    def test_create_and_read_booking(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        response = self.client.post("/bookings", json=self.payload)
        data = response.json()
        read_response = self.client.get(f"/bookings/{data['id']}")

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(data["trip_id"], self.trip_id)
        self.assertEqual(data["charter_id"], self.charter_id)
        self.assertEqual(data["total_price"], "200.00")
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["status"], "PENDING")
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.json(), data)

    @patch("app.booking_service.datetime")
    def test_duplicate_booking_rolls_back_new_customer(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        first = self.client.post("/bookings", json=self.payload)
        second = self.client.post("/bookings", json=self.payload)

        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 409)
        self.assertIn("CHARTER_ALREADY_BOOKED", second.json()["detail"])

        with SessionLocal() as verification:
            customer_count = verification.scalar(select(func.count()).select_from(Customer))
            booking_count = verification.scalar(select(func.count()).select_from(Booking))

            self.assertEqual(customer_count, 1)
            self.assertEqual(booking_count, 1)

    @patch("app.booking_service.datetime")
    def test_missing_trip_returns_404_without_creating_customer(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        missing_trip_id = self.trip_id + 1
        response = self.client.post("/bookings", json={**self.payload, "trip_id": missing_trip_id})

        self.assertEqual(response.status_code, 404, response.text)

        with SessionLocal() as verification:
            customer_count = verification.scalar(select(func.count()).select_from(Customer))
            booking_count = verification.scalar(select(func.count()).select_from(Booking))

            self.assertEqual(customer_count, 0)
            self.assertEqual(booking_count, 0)

    def test_invalid_booking_request_returns_422(self):
        examples = [{**self.payload, "group_size": 0}, {**self.payload, "trip_date": "invalid-date"},
                    {**self.payload, "total_price": "1.00"}]

        for payload in examples:
            with self.subTest(payload=payload):
                response = self.client.post("/bookings", json=payload)

                self.assertEqual(response.status_code, 422)

        with SessionLocal() as verification:
            customer_count = verification.scalar(select(func.count()).select_from(Customer))

            self.assertEqual(customer_count, 0)