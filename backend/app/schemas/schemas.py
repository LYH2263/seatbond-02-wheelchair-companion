from datetime import datetime
from pydantic import BaseModel, Field


class WheelchairPairOut(BaseModel):
    id: int
    wheel_row: int
    wheel_col: int
    companion_row: int
    companion_col: int
    occupied: bool = False
    model_config = {"from_attributes": True}


class WheelchairPairCreate(BaseModel):
    wheel_row: int = Field(ge=1)
    wheel_col: int = Field(ge=1)
    companion_row: int = Field(ge=1)
    companion_col: int = Field(ge=1)


class HallOut(BaseModel):
    id: int
    name: str
    rows: int
    cols: int
    aisle_cols: list[int]
    wheelchair_pairs: list[WheelchairPairOut] = []
    model_config = {"from_attributes": True}


class ShowtimeOut(BaseModel):
    id: int
    hall_id: int
    film_title: str
    start_at: datetime
    hall_name: str | None = None
    model_config = {"from_attributes": True}


class HoldOut(BaseModel):
    id: int
    showtime_id: int
    order_code: str
    row: int
    start_col: int
    end_col: int
    party_size: int
    status: str
    hold_type: str = "regular"
    pair_id: int | None = None
    model_config = {"from_attributes": True}


class HoldRequest(BaseModel):
    showtime_id: int
    party_size: int = Field(ge=1, le=12)
    preferred_row: int | None = None
    wheelchair: bool = False


class ConflictOut(BaseModel):
    id: int
    showtime_id: int
    party_size: int
    reason: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SeatMapCell(BaseModel):
    row: int
    col: int
    is_aisle: bool
    occupied: bool
    heat: float
    seat_kind: str = "normal"  # normal | wheelchair | companion
    held_kind: str | None = None
    pair_id: int | None = None


class SeatMapOut(BaseModel):
    showtime_id: int
    hall_name: str
    rows: int
    cols: int
    cells: list[SeatMapCell]
    wheelchair_pairs: list[WheelchairPairOut] = []
