from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session
from datetime import date, datetime, timezone

from app.models import CaptainDayOff, Trip, Booking


def get_unavailability_reasons(session, trip, trip_date, group_size, now=None) -> list[str]:
    reasons = []

    if not trip.min_group_size <= group_size <= trip.max_group_size:
        reasons.append("GROUP_SIZE_OUT_OF_RANGE")

    if trip.trip_type == "seasonal":
        if not trip.season_start <= trip_date <= trip.season_end:
            reasons.append("OUTSIDE_SEASON")

    captain_id = trip.charter.captain_id
    day_off = session.get(CaptainDayOff, (captain_id, trip_date))
    if day_off:
        reasons.append("CAPTAIN_DAY_OFF")

    if not now:
        now = datetime.now(timezone.utc)

    blocking_booking_id = session.scalar(
        select(Booking)
        .where(
            Booking.charter_id == trip.charter_id,
            Booking.trip_date == trip_date,
            or_(
                Booking.status.in_(['PROCESSING', 'CONFIRMED']),
                and_(Booking.status == 'PENDING', now < Booking.expires_at)
            )
        ).limit(1)
    )
    if blocking_booking_id:
        reasons.append("CHARTER_ALREADY_BOOKED")

    return reasons