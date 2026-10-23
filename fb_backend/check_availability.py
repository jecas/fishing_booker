from datetime import date

from app.models import Trip
from app.db import SessionLocal
from app.availability import get_unavailability_reasons


examples = [
    ("Regulat trip is available", 1, date(2027, 6, 16), 4, []),
    ("Group below minimum", 1, date(2027, 6, 16), 1, ["GROUP_SIZE_OUT_OF_RANGE"]),
    ("Minimum group size is allowed", 1, date(2027, 6, 16), 2, []),
    ("Maximum group size is allowed", 1, date(2027, 6, 16), 6, []),
    ("Group above maximum", 1, date(2027, 6, 16), 7, ["GROUP_SIZE_OUT_OF_RANGE"]),
    ("Day before season", 3, date(2027, 5, 31), 4, ["OUTSIDE_SEASON"]),
    ("First day of season is allowed", 3, date(2027, 6, 1), 4, []),
    ("Last day of season is allowed", 3, date(2027, 8, 31), 4, []),
    ("Day after season", 3, date(2027, 9, 1), 4, ["OUTSIDE_SEASON"]),
    ("Captain's day off", 1, date(2027, 6, 15), 4, ["CAPTAIN_DAY_OFF"]),
    ("Multiple unavailability reasons", 3, date(2027, 6, 15), 8, ["GROUP_SIZE_OUT_OF_RANGE", "CAPTAIN_DAY_OFF"]),
]

with SessionLocal() as session:
    for name, trip_id, trip_date, group_size, expected in examples:
        trip = session.get(Trip, trip_id)

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        actual = get_unavailability_reasons(session=session, trip=trip, trip_date=trip_date, group_size=group_size)

        assert set(actual) == set(expected), f"{name}: Expected {expected}, got {actual}"

        print(f"{name}: Passed")

print(f"\nAll {len(examples)} examples passed.")