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
    """A wheelchair spot bound to one mandatory companion seat in the same row.

    The companion must be the immediate left/right neighbour and may not sit
    across an aisle. Until a wheelchair hold takes the whole pair, the
    companion is protected: ordinary contiguous search treats it as blocked.
    """

    __tablename__ = "wheelchair_pairs"
    __table_args__ = (
        UniqueConstraint("hall_id", "wheel_row", "wheel_col", name="uq_wheelchair_cell"),
        UniqueConstraint("hall_id", "companion_row", "companion_col", name="uq_companion_cell"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    wheel_row: Mapped[int] = mapped_column(Integer)
    wheel_col: Mapped[int] = mapped_column(Integer)
    companion_row: Mapped[int] = mapped_column(Integer)
    companion_col: Mapped[int] = mapped_column(Integer)
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
    hold_type: Mapped[str] = mapped_column(String(20), default="regular")
    pair_id: Mapped[int | None] = mapped_column(ForeignKey("wheelchair_pairs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    showtime: Mapped[Showtime] = relationship(back_populates="holds")


class ConflictLog(Base):
    __tablename__ = "conflict_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    showtime_id: Mapped[int] = mapped_column(ForeignKey("showtimes.id"))
    party_size: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
