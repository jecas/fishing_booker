from app.models import Charter
from app.db import SessionLocal


with SessionLocal() as session:
    charter = session.get(Charter, 2)

    if not charter:
        raise ValueError("Charter not found")

    print(f"Charter: {charter.title}")

    for trip in sorted(charter.trips, key=lambda t: t.id):
        print(f"Trip: {trip.id}: {trip.title}")
        print(f"Price: {trip.price} {trip.currency}")
        print(f"Method of calculation: {trip.pricing_model}")
        print(f"Group: {trip.min_group_size} - {trip.max_group_size}")

        if trip.trip_type == "seasonal":
            print(f"Season: {trip.season_start} - {trip.season_end}")
        else:
            print("Regular trip")