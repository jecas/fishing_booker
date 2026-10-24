from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Text, Numeric, Date, DateTime, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Captains(Base):
    __tablename__ = "captains"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(32))
    charters: Mapped[list["Charter"]] = relationship("Charter", back_populates="captain")
    days_off: Mapped[list["CaptainDayOff"]] = relationship("CaptainDayOff", back_populates="captain",
                                                           cascade="all, delete-orphan")


class CaptainDayOff(Base):
    __tablename__ = "captain_days_off"

    captain_id: Mapped[int] = mapped_column(ForeignKey("captains.id"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    captain: Mapped["Captains"] = relationship("Captains", back_populates="days_off")


class Charter(Base):
    __tablename__ = "charters"

    id: Mapped[int] = mapped_column(primary_key=True)
    captain_id: Mapped[int] = mapped_column(ForeignKey("captains.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    captain: Mapped["Captains"] = relationship("Captains", back_populates="charters")
    photos: Mapped[list["CharterPhoto"]] = relationship("CharterPhoto", back_populates="charter",
                                                        cascade="all, delete-orphan")
    trips: Mapped[list["Trip"]] = relationship("Trip", back_populates="charter")


class CharterPhoto(Base):
    __tablename__ = "charter_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    charter_id: Mapped[int] = mapped_column(ForeignKey("charters.id"), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    charter: Mapped["Charter"] = relationship("Charter", back_populates="photos")


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_trip_price_positive"),
        CheckConstraint("min_group_size >= 1 AND min_group_size <= max_group_size", name="ck_trip_group_size"),
        CheckConstraint("pricing_model IN ('per_person', 'per_trip')", name="ck_trip_pricing_mode"),
        CheckConstraint(
            """
            (trip_type = 'regular' AND season_start IS NULL AND season_end IS NULL) OR 
            (trip_type = 'seasonal' AND season_start IS NOT NULL AND season_end IS NOT NULL AND season_start <= season_end)
            """, name="ck_trip_season"
        )
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    charter_id: Mapped[int] = mapped_column(ForeignKey("charters.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2))
    currency: Mapped[str] = mapped_column(String(3))
    pricing_model: Mapped[str] = mapped_column(String(20))
    min_group_size: Mapped[int]
    max_group_size: Mapped[int]
    trip_type: Mapped[str] = mapped_column(String(20))
    season_start: Mapped[date | None] = mapped_column(Date)
    season_end: Mapped[date | None] = mapped_column(Date)
    charter: Mapped["Charter"] = relationship("Charter", back_populates="trips")
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="trip")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(32))
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="customer")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("group_size >= 1", name="ck_booking_group_size"),
        CheckConstraint("total_price > 0", name="ck_booking_total_price"),
        CheckConstraint(
            """
            status IN ('PENDING', 'PROCESSING', 'CONFIRMED', 'FAILED', 'EXPIRED')
            """, name="ck_booking_status"
        ),
        CheckConstraint("expires_at > created_at", name="ck_booking_expiration"),
        Index("uq_booking_active_charter_date", "charter_id", "trip_date", unique=True,
              postgresql_where=text("status IN ('PENDING', 'PROCESSING', 'CONFIRMED')"))
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False)
    charter_id: Mapped[int] = mapped_column(ForeignKey("charters.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    trip_date: Mapped[date] = mapped_column(Date)
    group_size: Mapped[int]
    total_price: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trip: Mapped["Trip"] = relationship("Trip", back_populates="bookings")
    charter: Mapped["Charter"] = relationship("Charter")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="bookings")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("status IN ('PROCESSING', 'SUCCEEDED', 'DECLINED')", name="ck_payment_status"),
        Index("uq_payment_active_booking", "booking_id", unique=True,
              postgresql_where=text("status IN ('PROCESSING', 'SUCCEEDED')"))
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(36), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booking: Mapped["Booking"] = relationship("Booking")
