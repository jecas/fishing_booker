from decimal import Decimal

from app.db import SessionLocal
from app.models import Trip, Charter


with SessionLocal() as session:
    with session.begin():
        charter = session.get(Charter, 2)

        if not charter:
            raise ValueError("Charter not found")

        trip = Trip(
            charter=charter,
            title="Two-hour excursion",
            description="Private two-hour boat trip.",
            price=Decimal("50.00"),
            currency="USD",
            pricing_model="per_person",
            min_group_size=2,
            max_group_size=6,
            trip_type="regular",
            season_start=None,
            season_end=None
        )
        session.add(trip)
        session.flush()

        print(f"Trip ID: {trip.id}")
        print(f"Charter ID: {trip.charter_id}")
        print(f"Price: {trip.price} {trip.currency}")
        print(f"Method of calculation: {trip.pricing_model}")

    print("Transaction committed.")