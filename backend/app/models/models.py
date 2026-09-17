from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Hall(Base):
    __tablename__ = "halls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    rows: Mapped[int] = mapped_column(Integer)
    cols: Mapped[int] = mapped_column(Integer)
    aisle_cols: Mapped[str] = mapped_column(String(80), default="")  # comma-separated
    showtimes: Mapped[list["Showtime"]] = relationship(back_populates="hall")
    wheelchair_pairs: Mapped[list["WheelchairPair"]] = relationship(
        back_populates="hall", cascade="all, delete-orphan"
    )


class WheelchairPair(Base):
    """A wheelchair seat plus its mandatory same-row adjacent companion seat."""

    __tablename__ = "wheelchair_pairs"
    __table_args__ = (UniqueConstraint("hall_id", "row", "col", name="uq_wheelchair_seat"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    row: Mapped[int] = mapped_column(Integer)
    col: Mapped[int] = mapped_column(Integer)  # wheelchair seat
    companion_col: Mapped[int] = mapped_column(Integer)  # adjacent companion seat
    hall: Mapped[Hall] = relationship(back_populates="wheelchair_pairs")


class Showtime(Base):
    __tablename__ = "showtimes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    film_title: Mapped[str] = mapped_column(String(120))
    start_at: Mapped[datetime] = mapped_column(DateTime)
    hall: Mapped[Hall] = relationship(back_populates="showtimes")
    holds: Mapped[list["SeatHold"]] = relationship(back_populates="showtime")


class SeatHold(Base):
    __tablename__ = "seat_holds"
    __table_args__ = (UniqueConstraint("showtime_id", "row", "start_col", "end_col", name="uq_hold_span"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    showtime_id: Mapped[int] = mapped_column(ForeignKey("showtimes.id"))
    order_code: Mapped[str] = mapped_column(String(40))
    row: Mapped[int] = mapped_column(Integer)
    start_col: Mapped[int] = mapped_column(Integer)
    end_col: Mapped[int] = mapped_column(Integer)
    party_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="held")
    kind: Mapped[str] = mapped_column(String(20), default="normal")  # normal | wheelchair
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    showtime: Mapped[Showtime] = relationship(back_populates="holds")


class ConflictLog(Base):
    __tablename__ = "conflict_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    showtime_id: Mapped[int] = mapped_column(ForeignKey("showtimes.id"))
    party_size: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
