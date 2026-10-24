from app.reviews_client import ReviewsProviderUnavailable, get_reviews


reviews = get_reviews("demo-charter")
assert len(reviews) == 2
assert reviews[0].rating == 5
print("PASS: Reviews retrieved and validated")


assert get_reviews("empty") == []
print("PASS: Empty reviews list supported")

try:
    get_reviews("unavailable")
except ReviewsProviderUnavailable:
    print("PASS: Provider outage handled")
else:
    raise AssertionError("Expected provider unavailability.")