from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Booking, Captains, Charter, Customer, Payment, Trip
from app.payment_service import prepare_payment, apply_payment_result, process_payment
from app.payment_client import ProviderChargeResponse, PaymentProviderUnavailable
from app.exceptions import PaymentConflictError
from tests.base import DatabaseTestCase


class PaymentServiceTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()

        self.now = datetime(2030, 6, 1, tzinfo=timezone.utc)
        self.key = str(uuid4())

        captain = Captains(first_name="Test", last_name="Captain", email="captain@example.com", phone="+381641111111")
        charter = Charter(captain=captain, title="Test charter", description="Charter created by the test.")
        trip = Trip(charter=charter, title="Test trip", description="Trip created by the test.", price=Decimal("50.00"),
                    currency="USD", pricing_model="per_person", min_group_size=2, max_group_size=6, trip_type="regular")
        customer = Customer(first_name="Test", last_name="Customer", email="customer@example.com", phone="+381642222222")
        self.booking = Booking(trip=trip, charter=charter, customer=customer, trip_date=date(2030, 6, 16),
                               group_size=4, total_price=Decimal("200.00"), currency="USD", status="PENDING",
                               created_at=self.now, expires_at=self.now + timedelta(minutes=15))

        self.session.add_all([captain, charter, trip, customer, self.booking])
        self.session.flush()

    def _prepare_attempt(self, token="tok_success", key=None):
        _, payment = prepare_payment(session=self.session, booking_id=self.booking.id,
                                     idempotency_key=key if key is not None else self.key, payment_token=token)
        return payment

    def _provider_result(self, status):
        return ProviderChargeResponse(id=uuid4(), status=status, created_at=self.now)

    def _commit_booking(self):
        booking_id = self.booking.id
        self.session.commit()
        return booking_id

    @patch("app.payment_service.datetime")
    def test_prepare_payment_marks_booking_as_processing(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        booking, payment = prepare_payment(session=self.session, booking_id=self.booking.id, idempotency_key=self.key,
                                           payment_token="tok_success")

        self.assertEqual(booking.status, "PROCESSING")
        self.assertEqual(payment.status, "PROCESSING")
        self.assertEqual(payment.booking_id, booking.id)
        self.assertEqual(payment.idempotency_key, self.key)
        self.assertIsNone(payment.provider_reference)

    @patch("app.payment_service.datetime")
    def test_same_request_reuses_payment(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        _, first = prepare_payment(session=self.session, booking_id=self.booking.id, idempotency_key=self.key,
                                   payment_token="tok_success")
        _, repeated = prepare_payment(session=self.session, booking_id=self.booking.id, idempotency_key=self.key,
                                      payment_token="tok_success")
        count = self.session.scalar(select(func.count()).select_from(Payment).where(Payment.booking_id == self.booking.id))

        self.assertEqual(first.id, repeated.id)
        self.assertEqual(count, 1)

    @patch("app.payment_service.datetime")
    def test_same_key_with_different_token_is_rejected(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        prepare_payment(session=self.session, booking_id=self.booking.id, idempotency_key=self.key,
                        payment_token="tok_success")

        with self.assertRaisesRegex(PaymentConflictError,"Idempotency key was used with a different request"):
            prepare_payment(session=self.session, booking_id=self.booking.id, idempotency_key=self.key,
                            payment_token="tok_declined")

    @patch("app.payment_service.datetime")
    def test_new_attempt_is_blocked_while_processing(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        prepare_payment(session=self.session, booking_id=self.booking.id, idempotency_key=self.key,
                        payment_token="tok_success")

        with self.assertRaisesRegex(PaymentConflictError,"Booking is not awaiting a new payment attempt"):
            prepare_payment(session=self.session, booking_id=self.booking.id, idempotency_key=str(uuid4()),
                            payment_token="tok_success")

    @patch("app.payment_service.datetime")
    def test_success_confirms_booking_and_can_be_reapplied(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        payment = self._prepare_attempt()
        result = self._provider_result("SUCCEEDED")

        apply_payment_result(self.session, payment.id, result)

        self.assertEqual(payment.status, "SUCCEEDED")
        self.assertEqual(payment.provider_reference, str(result.id))
        self.assertEqual(self.booking.status, "CONFIRMED")

        apply_payment_result(self.session, payment.id, result)

        self.assertEqual(payment.status, "SUCCEEDED")
        self.assertEqual(self.booking.status, "CONFIRMED")

    @patch("app.payment_service.datetime")
    def test_decline_allows_retry_and_cannot_undo_later_success(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        first_payment = self._prepare_attempt(token="tok_declined")
        declined_result = self._provider_result("DECLINED")

        apply_payment_result(self.session, first_payment.id, declined_result)

        self.assertEqual(first_payment.status, "DECLINED")
        self.assertEqual(self.booking.status, "PENDING")

        second_payment = self._prepare_attempt(key=str(uuid4()))
        success_result = self._provider_result("SUCCEEDED")

        apply_payment_result(self.session, second_payment.id, success_result)

        self.assertNotEqual(first_payment.id, second_payment.id)
        self.assertEqual(self.booking.status, "CONFIRMED")

        apply_payment_result(self.session, first_payment.id, declined_result)

        self.assertEqual(first_payment.status, "DECLINED")
        self.assertEqual(second_payment.status, "SUCCEEDED")
        self.assertEqual(self.booking.status, "CONFIRMED")

    @patch("app.payment_service.datetime")
    def test_decline_at_deadline_expires_booking(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        payment = self._prepare_attempt()
        mocked_datetime.now.return_value = self.booking.expires_at

        apply_payment_result(self.session, payment.id, self._provider_result("DECLINED"))

        self.assertEqual(payment.status, "DECLINED")
        self.assertEqual(self.booking.status, "EXPIRED")

    @patch("app.payment_service.datetime")
    def test_success_after_deadline_still_confirms_booking(self, mocked_datetime):
        mocked_datetime.now.return_value = self.now
        payment = self._prepare_attempt()
        mocked_datetime.now.return_value = self.booking.expires_at + timedelta(minutes=1)

        apply_payment_result(self.session, payment.id, self._provider_result("SUCCEEDED"))

        self.assertEqual(payment.status, "SUCCEEDED")
        self.assertEqual(self.booking.status, "CONFIRMED")

    @patch("app.payment_service.charge_payment")
    @patch("app.payment_service.datetime")
    def test_process_payment_success_and_replay(self, mocked_datetime, mocked_charge):
        mocked_datetime.now.return_value = self.now
        mocked_charge.return_value = self._provider_result("SUCCEEDED")
        booking_id = self._commit_booking()
        first = process_payment(session=self.session, booking_id=booking_id, idempotency_key=self.key,
                                payment_token="tok_success")

        self.assertEqual(first.booking.status, "CONFIRMED")
        self.assertEqual(first.payment.status, "SUCCEEDED")
        self.assertFalse(self.session.in_transaction())

        repeated = process_payment(session=self.session, booking_id=booking_id, idempotency_key=self.key,
                                   payment_token="tok_success")

        self.assertEqual(repeated, first)

        mocked_charge.assert_called_once_with(idempotency_key=self.key, payment_token="tok_success",
                                              amount=Decimal("200.00"), currency="USD")

        with SessionLocal() as verification:
            saved_booking = verification.get(Booking, booking_id)
            saved_payment = verification.get(Payment, first.payment.id)

            self.assertEqual(saved_booking.status, "CONFIRMED")
            self.assertEqual(saved_payment.status, "SUCCEEDED")

    @patch("app.payment_service.charge_payment")
    @patch("app.payment_service.datetime")
    def test_unknown_outcome_is_persisted_and_recoverable(self, mocked_datetime, mocked_charge):
        mocked_datetime.now.return_value = self.now
        mocked_charge.side_effect = [PaymentProviderUnavailable("Simulated timeout"),
                                     self._provider_result("SUCCEEDED")]
        booking_id = self._commit_booking()

        with self.assertRaises(PaymentProviderUnavailable):
            process_payment(session=self.session, booking_id=booking_id, idempotency_key=self.key,
                            payment_token="tok_timeout_after_charge")

        self.assertFalse(self.session.in_transaction())

        with SessionLocal() as verification:
            saved_booking = verification.get(Booking, booking_id)
            saved_payment = verification.scalar(select(Payment).where(Payment.idempotency_key == self.key))

            self.assertEqual(saved_booking.status, "PROCESSING")
            self.assertIsNotNone(saved_payment)
            self.assertEqual(saved_payment.status, "PROCESSING")

            payment_id = saved_payment.id

        recovered = process_payment(session=self.session, booking_id=booking_id, idempotency_key=self.key,
                                    payment_token="tok_timeout_after_charge")

        self.assertEqual(recovered.payment.id, payment_id)
        self.assertEqual(recovered.payment.status, "SUCCEEDED")
        self.assertEqual(recovered.booking.status, "CONFIRMED")
        self.assertFalse(self.session.in_transaction())

        self.assertEqual(mocked_charge.call_count, 2)

        first_call, second_call = mocked_charge.call_args_list
        self.assertEqual(first_call, second_call)