from datetime import datetime, date, timedelta, timezone
from sqlalchemy import update, select
from sqlalchemy.orm import Session

from app.models import Booking, Captains, Customer, Trip
from app.availability import get_unavailability_reasons


def expire_pending_bookings(session: Session, charter_id: int, now: datetime) -> int:
    statement = (update(Booking)
                 .where(Booking.charter_id == charter_id,
                        Booking.status == "PENDING",
                        Booking.expires_at <= now).values(status="EXPIRED"))

    result = session.execute(statement)

    return result.rowcount


def create_booking(session: Session, trip_id: int, customer_id: int, trip_date: date, group_size: int) -> Booking:
    trip = session.get(Trip, trip_id)
    if not trip:
        raise ValueError("Trip not found")

    customer = session.get(Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    session.execute(select(Captains.id).where(Captains.id == trip.charter.captain_id).with_for_update()).scalar_one()

    now = datetime.now(timezone.utc)
    if trip_date < now.date():
        raise ValueError("Trip date cannot be in the past")

    expire_pending_bookings(session, trip.charter_id, now)

    reasons = get_unavailability_reasons(session, trip, trip_date, group_size, now)
    if reasons:
        raise ValueError(f"Trip is unavailable: {reasons}")

    if trip.pricing_model == "per_person":
        total_price = trip.price * group_size
    elif trip.pricing_model == "per_trip":
        total_price = trip.price
    else:
        raise ValueError(f"Unsupported pricing model: {trip.pricing_model}")

    booking = Booking(trip=trip, charter_id=trip.charter_id, customer=customer, trip_date=trip_date,
                      group_size=group_size, total_price=total_price, currency=trip.currency, status="PENDING",
                      created_at=now, expires_at=now + timedelta(minutes=15))
    session.add(booking)
    session.flush()

    return booking


def get_booking(session: Session, booking_id: int) -> Booking | None:
    booking = session.get(Booking, booking_id)

    if not booking:
        return None

    session.execute(
        select(Captains.id)
        .where(Captains.id == booking.charter.captain_id)
        .with_for_update()
    ).scalar_one()

    session.refresh(booking)

    expire_pending_bookings(session=session, charter_id=booking.charter_id, now=datetime.now(timezone.utc))

    session.refresh(booking)

    return booking