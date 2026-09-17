from datetime import datetime
from pydantic import BaseModel, Field


class WheelchairPairIn(BaseModel):
    row: int = Field(ge=1)
    col: int = Field(ge=1, description="轮椅位列")
    companion_col: int = Field(ge=1, description="陪同位列，须与轮椅位同排左右相邻")


class WheelchairPairOut(BaseModel):
    id: int
    hall_id: int
    row: int
    col: int
    companion_col: int
    model_config = {"from_attributes": True}


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
    kind: str  # normal | wheelchair
    model_config = {"from_attributes": True}


class HoldRequest(BaseModel):
    showtime_id: int
    party_size: int = Field(ge=1, le=12)
    preferred_row: int | None = None
    wheelchair_need: bool = Field(
        default=False,
        description="为 true 时锁定完整轮椅组合（轮椅位+陪同位），人数按组合座位数记为 2",
    )


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
    kind: str = "normal"  # normal | wheelchair | companion


class SeatMapOut(BaseModel):
    showtime_id: int
    hall_name: str
    rows: int
    cols: int
    cells: list[SeatMapCell]
