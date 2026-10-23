from datetime import date
from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import Charter, Trip
from app.storage import generate_photo_url
from app.availability import get_unavailability_reasons
from app.schemas import HealthResponse, CharterResponse, CharterDetailsResponse, TripResponse, TripAvailabilityResponse


app = FastAPI(title="Fishing Charter Booking API")


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.get("/charters", response_model=list[CharterResponse])
def list_charters(offset: int=Query(default=0, ge=0), limit: int=Query(default=20, ge=1, le=100),
                  session: Session = Depends(get_db)):
    statement = select(Charter).order_by(Charter.id).offset(offset).limit(limit)

    return session.scalars(statement).all()


@app.get("/charters/{charter_id}", response_model=CharterDetailsResponse)
def get_charter(charter_id: int, session: Session = Depends(get_db)):
    statement = (select(Charter)
                 .options(joinedload(Charter.captain), selectinload(Charter.photos))
                 .where(Charter.id == charter_id))
    charter = session.scalar(statement)

    if not charter:
        raise HTTPException(status_code=404, detail="Charter not found")

    return {
        **CharterResponse.model_validate(charter).model_dump(),
        "captain": charter.captain,
        "photos": [{"id": photo.id, "url": generate_photo_url(photo.object_key)}
                   for photo in sorted(charter.photos, key=lambda photo: photo.id)]
    }


@app.get("/charters/{charter_id}/trips", response_model=list[TripAvailabilityResponse])
def list_charter_trips(charter_id: int, trip_date: date | None = Query(default=None, alias="date"),
                       group_size: int | None = Query(default=None, ge=1), offset: int = Query(default=0, ge=0),
                       limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_db)):
    charter = session.get(Charter, charter_id)

    if not charter:
        raise HTTPException(status_code=404, detail="Charter not found")

    if (not trip_date) != (not group_size):
        raise HTTPException(status_code=422, detail="Provide both date and group_size or neither.")

    statement = (select(Trip)
                 .where(Trip.charter_id == charter_id)
                 .order_by(Trip.id)
                 .offset(offset)
                 .limit(limit))

    trips = session.scalars(statement).all()

    result = []

    for trip in trips:
        item = TripAvailabilityResponse.model_validate(trip)

        if trip_date:
            reasons = get_unavailability_reasons(session, trip, trip_date, group_size)

            item.available = not reasons
            item.unavailability_reasons = reasons

        result.append(item)

    return result


@app.get("/trips/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: int, session: Session = Depends(get_db)):
    trip = session.get(Trip, trip_id)

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return trip