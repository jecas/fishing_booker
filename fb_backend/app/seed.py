import os
from decimal import Decimal
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from pathlib import Path
from botocore.exceptions import ClientError

from app.db import SessionLocal
from app.models import Captains, Charter, Trip, CaptainDayOff, CharterPhoto
from app.storage import get_s3_client


DEMO_CAPTAIN_EMAIL = "demo-camptain@example.com"
DEMO_CHARTER_TITLE = "Demo fishing charter"


def ensure_demo_photo(charter_id: int):
    file_path = Path(__file__).resolve().parent.parent / "sample_files/boat.jpg"

    if not file_path.is_file():
        raise FileNotFoundError(f"Demo photo not found: {file_path}")

    bucket_name = os.environ.get("S3_BUCKET_NAME", "charter-photos")
    object_key = f"demo/charter/{charter_id}/boat.jpg"

    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        if error_code not in {"404", "NoSuchBucket"}:
            raise

        s3.create_bucket(Bucket=bucket_name)

    s3.upload_file(str(file_path), bucket_name, object_key, ExtraArgs={"ContentType": "image/jpeg"})

    with SessionLocal.begin() as session:
        photo = session.execute(select(CharterPhoto).where(CharterPhoto.object_key == object_key)).scalar_one_or_none()
        if not photo:
            session.add(CharterPhoto(object_key=object_key, charter_id=charter_id))

    print(f"Demo photo ready: {object_key}")


def seed_database():
    with SessionLocal.begin() as session:
        captain = session.execute(select(Captains).where(Captains.email == DEMO_CAPTAIN_EMAIL)).scalar_one_or_none()

        if not captain:
            captain = Captains(first_name="Demo", last_name="Campain", email=DEMO_CAPTAIN_EMAIL, phone="+381641111111")
            session.add(captain)
            session.flush()

        charter = session.execute(select(Charter).where(Charter.captain_id == captain.id,
                                                        Charter.title == DEMO_CHARTER_TITLE)).scalar_one_or_none()

        if not charter:
            charter = Charter(captain=captain, title=DEMO_CHARTER_TITLE, description="Demo charter description",
                              review_business_id="demo-charter")
            session.add(charter)
            session.flush()

        today = datetime.now(timezone.utc).date()
        trip_definitions = [
            {
                "title": "Demo two-hour excursion",
                "description": "Private two-hour boat trip.",
                "price": Decimal("50.00"),
                "currency": "USD",
                "pricing_model": "per_person",
                "min_group_size": 2,
                "max_group_size": 6,
                "trip_type": "regular",
                "season_start": None,
                "season_end": None
            },
            {
                "title": "Demo seasonal sunset trip",
                "description": "Private sunset boat trip.",
                "price": Decimal("300.00"),
                "currency": "USD",
                "pricing_model": "per_trip",
                "min_group_size": 2,
                "max_group_size": 6,
                "trip_type": "seasonal",
                "season_start": today + timedelta(days=7),
                "season_end": today + timedelta(days=37)
            }
        ]

        trip_summeries = []
        for definition in trip_definitions:
            trip = session.execute(select(Trip).where(Trip.charter_id == charter.id,
                                                      Trip.title == definition["title"])).scalar_one_or_none()

            if not trip:
                trip = Trip(charter=charter, **definition)
                session.add(trip)
                session.flush()

            trip_summeries.append((trip.id, trip.title, trip.season_start, trip.season_end))

        seasonal_trip = session.execute(select(Trip).where(Trip.charter_id == charter.id,
                                                           Trip.title == "Demo seasonal sunset trip")).scalar_one()
        demo_day_off = seasonal_trip.season_start + timedelta(days=1)
        existing_day_off = session.get(CaptainDayOff, (captain.id, demo_day_off))

        if not existing_day_off:
            session.add(CaptainDayOff(captain_id=captain.id, day=demo_day_off))

        captain_id = captain.id
        charter_id = charter.id

    ensure_demo_photo(charter_id)
    print("Database seed completed.")
    print(f"Demo captain ID: {captain_id}")
    print(f"Demo charter ID: {charter_id}")
    for trip_id, trip_title, season_start, season_end in trip_summeries:
        print(f"Demo trip ID: {trip_id}, title: {trip_title}")

        if season_start:
            print(f"Season: {season_start} - {season_end}")

    print(f"Demo captain day off: {demo_day_off}")


if __name__ == "__main__":
    seed_database()
