from datetime import date
from decimal import Decimal

from app.db import SessionLocal
from app.models import Charter, Trip


with SessionLocal() as session:
    with session.begin():
        charter = session.get(Charter, 2)

        if not charter:
            raise ValueError("Charter not found")

        trip = Trip(
            charter=charter,
            title="Summer sunset trip",
            description="Private summer boat trip.",
            price=Decimal("300.00"),
            currency="USD",
            pricing_model="per_trip",
            min_group_size=2,
            max_group_size=6,
            trip_type="seasonal",
            season_start=date(2027, 6, 1),
            season_end=date(2027, 8, 31),
        )

        session.add(trip)
        session.flush()

        print(f"Trip ID: {trip.id}")
        print(f"Season: {trip.season_start} - {trip.season_end}")

    print("Transaction committed.")