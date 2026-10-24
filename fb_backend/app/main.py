from datetime import date
from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.models import Charter, Trip, Customer
from app.storage import generate_photo_url
from app.availability import get_unavailability_reasons
from app.schemas import HealthResponse, CharterResponse, CharterDetailsResponse, TripResponse, TripAvailabilityResponse, \
    BookingResponse, BookingCreate
from app.booking_service import create_booking as create_booking_service, get_booking as get_booking_service


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


@app.post("/bookings", response_model=BookingResponse, status_code=201)
def book_trip(payload: BookingCreate, session: Session = Depends(get_db)):
    try:
        with session.begin():
            customer = Customer(**payload.customer.model_dump())
            session.add(customer)
            session.flush()

            try:
                booking = create_booking_service(session, payload.trip_id, customer.id, payload.trip_date,
                                                 payload.group_size)
            except ValueError as e:
                if str(e) == "Trip not found.":
                    raise HTTPException(status_code=404, detail=str(e)) from e

                raise HTTPException(status_code=409, detail=str(e)) from e

        return BookingResponse.model_validate(booking)
    except IntegrityError as e:
        constraint_name = getattr(getattr(e.orig, "diag", None), "constraint_name", None)

        if constraint_name == "uq_booking_active_charter_date":
            raise HTTPException(status_code=409, detail="Charter is alredy booked for this date.") from e

        raise e


@app.get("/bookings/{booking_id}", response_model=BookingResponse,
         responses={404: {"description": "Booking not found"}})
def get_booking(booking_id: int, session: Session = Depends(get_db)):
    with session.begin():
        booking = get_booking_service(session=session, booking_id=booking_id)

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found.")

        response = BookingResponse.model_validate(booking)

    return response