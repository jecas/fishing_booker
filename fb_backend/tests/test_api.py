from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import Captains, Charter
from app.schemas import ReviewResponse
from app.reviews_client import ReviewsProviderUnavailable
from tests.base import DatabaseTestCase


class CharterApiTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()

        captain = Captains(first_name="Test", last_name="Captain", email="captain@example.com", phone="+381641111111")
        first_charter = Charter(captain=captain, title="First test charter", description="First charter description.")
        second_charter = Charter(captain=captain, title="Second test charter", description="Second charter description.")
        self.session.add_all([captain, first_charter, second_charter])
        self.session.flush()
        self.charter_ids = sorted([first_charter.id, second_charter.id])
        self.session.commit()
        self.client = self.enterContext(TestClient(app))

    def _link_reviews(self):
        charter = self.session.get(Charter, self.charter_ids[0])
        charter.review_business_id = "test-business"
        self.session.commit()

    def test_list_charters(self):
        response = self.client.get("/charters")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual([item["id"] for item in data], self.charter_ids)
        self.assertTrue(all("title" in item for item in data))

    def test_charter_pagination(self):
        for offset, expected_id in enumerate(self.charter_ids):
            with self.subTest(offset=offset):
                response = self.client.get("/charters", params={"offset": offset, "limit": 1})

                self.assertEqual(response.status_code, 200)

                data = response.json()

                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["id"], expected_id)

        response = self.client.get("/charters", params={"offset": 2, "limit": 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_invalid_pagination_is_rejected(self):
        examples = [{"limit": 0}, {"limit": 101}, {"offset": -1}]

        for params in examples:
            with self.subTest(params=params):
                response = self.client.get("/charters", params=params)

                self.assertEqual(response.status_code, 422)

    def test_missing_charter_returns_404(self):
        response = self.client.get("/charters/0")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(),{"detail": "Charter not found"})

    def test_invalid_charter_id_returns_422(self):
        response = self.client.get("/charters/not-an-integer")

        self.assertEqual(response.status_code, 422)

    @patch("app.main.get_reviews")
    def test_charter_detail_without_review_link(self, mocked_reviews):
        response = self.client.get(f"/charters/{self.charter_ids[0]}")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["id"], self.charter_ids[0])
        self.assertEqual(data["captain"]["first_name"], "Test")
        self.assertEqual(data["photos"], [])
        self.assertEqual(data["reviews"], [])
        self.assertEqual(data["reviews_status"], "not_linked")
        mocked_reviews.assert_not_called()

    @patch("app.main.get_reviews")
    def test_charter_detail_includes_reviews(self, mocked_reviews):
        self._link_reviews()
        mocked_reviews.return_value = [ReviewResponse(id="test-review", author="Ana", rating=5, text="Great trip.")]
        response = self.client.get(f"/charters/{self.charter_ids[0]}")
        data = response.json()

        expected_reviews = [{"id": "test-review", "author": "Ana", "rating": 5, "text": "Great trip."}]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["reviews_status"], "available")
        self.assertEqual(data["reviews"], expected_reviews)

        mocked_reviews.assert_called_once_with("test-business")

    @patch("app.main.get_reviews")
    def test_empty_reviews_are_available(self, mocked_reviews):
        self._link_reviews()
        mocked_reviews.return_value = []
        response = self.client.get(f"/charters/{self.charter_ids[0]}")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["reviews"], [])
        self.assertEqual(data["reviews_status"], "available")

    @patch("app.main.get_reviews")
    def test_reviews_outage_does_not_hide_charter(self, mocked_reviews):
        self._link_reviews()
        mocked_reviews.side_effect = ReviewsProviderUnavailable("Simulated outage")
        response = self.client.get(f"/charters/{self.charter_ids[0]}")
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["id"], self.charter_ids[0])
        self.assertEqual(data["captain"]["first_name"], "Test")
        self.assertEqual(data["reviews"], [])
        self.assertEqual(data["reviews_status"], "unavailable")
