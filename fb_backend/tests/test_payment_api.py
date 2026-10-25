from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.models import Booking, Captains, Charter, Customer, Trip
from app.payment_client import PaymentProviderUnavailable, ProviderChargeResponse
from tests.base import DatabaseTestCase


class PaymentApiTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()

        self.now = datetime(2030, 6, 1, tzinfo=timezone.utc)
        self.key = str(uuid4())
        captain = Captains(first_name="Test", last_name="Captain", email="captain@example.com", phone="+381641111111")
        charter = Charter(captain=captain, title="Test charter", description="Test charter description.")
        trip = Trip(charter=charter, title="Test trip", description="Test trip description.", price=Decimal("50.00"),
                    currency="USD", pricing_model="per_person", min_group_size=2, max_group_size=6, trip_type="regular")
        customer = Customer(first_name="Ana", last_name="Petrovic", email="ana@example.com", phone="+381642222222")
        booking = Booking(trip=trip, charter=charter, customer=customer, trip_date=date(2030, 6, 16),
                          group_size=4, total_price=Decimal("200.00"), currency="USD", status="PENDING",
                          created_at=self.now, expires_at=self.now + timedelta(minutes=15))
        self.session.add_all([captain, charter, trip, customer, booking])
        self.session.flush()
        self.booking_id = booking.id
        self.session.commit()
        self.url = f"/bookings/{self.booking_id}/payments"
        self.client = self.enterContext(TestClient(app))

    def _provider_result(self, status):
        return ProviderChargeResponse(id=uuid4(), status=status, created_at=self.now)

    def _pay(self, token, key):
        return self.client.post(self.url, headers={"Idempotency-Key": key}, json={"payment_token": token})

    @patch("app.payment_service.charge_payment")
    @patch("app.payment_service.datetime")
    def test_success_replay_and_duplicate_payment_protection(self, mocked_datetime, mocked_charge):
        mocked_datetime.now.return_value = self.now
        mocked_charge.return_value = self._provider_result("SUCCEEDED")
        first = self._pay("tok_success", self.key)

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["booking"]["status"], "CONFIRMED")
        self.assertEqual(first.json()["payment"]["status"], "SUCCEEDED")

        repeated = self._pay("tok_success", self.key)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json(), first.json())

        new_attempt = self._pay("tok_success", str(uuid4()))
        self.assertEqual(new_attempt.status_code, 409)
        mocked_charge.assert_called_once()

    @patch("app.payment_service.charge_payment")
    @patch("app.payment_service.datetime")
    def test_decline_allows_a_new_attempt(self, mocked_datetime, mocked_charge):
        mocked_datetime.now.return_value = self.now
        mocked_charge.side_effect = [self._provider_result("DECLINED"), self._provider_result("SUCCEEDED")]

        declined = self._pay("tok_declined", self.key)
        self.assertEqual(declined.status_code, 200, declined.text)
        self.assertEqual(declined.json()["payment"]["status"], "DECLINED")
        self.assertEqual(declined.json()["booking"]["status"], "PENDING")

        succeeded = self._pay("tok_success", str(uuid4()))
        self.assertEqual(succeeded.status_code, 200, succeeded.text)
        self.assertEqual(succeeded.json()["booking"]["status"], "CONFIRMED")
        self.assertNotEqual(declined.json()["payment"]["id"], succeeded.json()["payment"]["id"])

    @patch("app.payment_service.charge_payment")
    @patch("app.payment_service.datetime")
    def test_unknown_outcome_returns_503_and_can_be_recovered(self, mocked_datetime, mocked_charge):
        mocked_datetime.now.return_value = self.now
        mocked_charge.side_effect = [PaymentProviderUnavailable("Simulated timeout"),
                                     self._provider_result("SUCCEEDED")]

        first = self._pay("tok_timeout_after_charge", self.key)
        self.assertEqual(first.status_code, 503)
        self.assertIn("same Idempotency-Key", first.json()["detail"])

        read_response = self.client.get(f"/bookings/{self.booking_id}")
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.json()["status"],"PROCESSING")

        recovered = self._pay("tok_timeout_after_charge", self.key)
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()["booking"]["status"], "CONFIRMED")
        self.assertEqual(recovered.json()["payment"]["status"], "SUCCEEDED")
        self.assertEqual(mocked_charge.call_count, 2)
        first_call, second_call = mocked_charge.call_args_list
        self.assertEqual(first_call, second_call)

    @patch("app.payment_service.charge_payment")
    def test_invalid_payment_requests_return_422(self, mocked_charge):
        examples = [
            (
                {},
                {"payment_token": "tok_success"}
            ),
            (
                {"Idempotency-Key": "invalid-uuid"},
                {"payment_token": "tok_success"}
            ),
            (
                {"Idempotency-Key": self.key},
                {"payment_token": "unknown-token"}
            ),
            (
                {"Idempotency-Key": self.key},
                {"payment_token": "tok_success", "amount": "1.00"}
            )
        ]

        for headers, payload in examples:
            with self.subTest(headers=headers, payload=payload):
                response = self.client.post(self.url, headers=headers, json=payload)

                self.assertEqual(response.status_code, 422)

        mocked_charge.assert_not_called()