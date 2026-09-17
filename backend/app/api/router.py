from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ConflictLog, Hall, SeatHold, Showtime, WheelchairPair
from app.schemas.schemas import (
    ConflictOut,
    HallOut,
    HoldOut,
    HoldRequest,
    SeatMapCell,
    SeatMapOut,
    ShowtimeOut,
    WheelchairPairIn,
    WheelchairPairOut,
)
from app.services.bond_engine import (
    HOLD_KIND_NORMAL,
    HOLD_KIND_WHEELCHAIR,
    WHEELCHAIR_COMBO_SIZE,
    HoldSpan,
    SeatCell,
    WheelchairPair as PairSpec,
    combo_conflict_reason,
    conflicts_with,
    find_bond_across_rows,
    find_contiguous_block,
    find_wheelchair_combo,
    protected_companion_cols,
    validate_wheelchair_pair,
    wheelchair_combo_blockers,
)

api_router = APIRouter()


def _aisles(hall: Hall) -> list[int]:
    if not hall.aisle_cols.strip():
        return []
    return [int(x) for x in hall.aisle_cols.split(",") if x.strip()]


def _pair_specs(hall: Hall) -> list[PairSpec]:
    return [PairSpec(row=p.row, col=p.col, companion_col=p.companion_col) for p in hall.wheelchair_pairs]


def _hall_out(h: Hall) -> HallOut:
    return HallOut(
        id=h.id,
        name=h.name,
        rows=h.rows,
        cols=h.cols,
        aisle_cols=_aisles(h),
        wheelchair_pairs=[WheelchairPairOut.model_validate(p) for p in h.wheelchair_pairs],
    )


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/halls", response_model=list[HallOut])
def list_halls(db: Session = Depends(get_db)):
    return [_hall_out(h) for h in db.scalars(select(Hall).order_by(Hall.id)).all()]


@api_router.get("/halls/{hall_id}/wheelchair-pairs", response_model=list[WheelchairPairOut])
def list_wheelchair_pairs(hall_id: int, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")
    return sorted(hall.wheelchair_pairs, key=lambda p: (p.row, p.col))


@api_router.post(
    "/halls/{hall_id}/wheelchair-pairs",
    response_model=WheelchairPairOut,
    status_code=201,
)
def create_wheelchair_pair(hall_id: int, body: WheelchairPairIn, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")
    spec = PairSpec(row=body.row, col=body.col, companion_col=body.companion_col)
    error = validate_wheelchair_pair(hall.rows, hall.cols, set(_aisles(hall)), spec, _pair_specs(hall))
    if error:
        raise HTTPException(422, error)
    pair = WheelchairPair(hall_id=hall.id, row=body.row, col=body.col, companion_col=body.companion_col)
    db.add(pair)
    db.commit()
    db.refresh(pair)
    return pair


@api_router.delete("/halls/{hall_id}/wheelchair-pairs/{pair_id}", status_code=204)
def delete_wheelchair_pair(hall_id: int, pair_id: int, db: Session = Depends(get_db)):
    pair = db.get(WheelchairPair, pair_id)
    if not pair or pair.hall_id != hall_id:
        raise HTTPException(404, "轮椅组合不存在")
    db.delete(pair)
    db.commit()


@api_router.get("/showtimes", response_model=list[ShowtimeOut])
def list_showtimes(db: Session = Depends(get_db)):
    rows = db.scalars(select(Showtime).order_by(Showtime.start_at)).all()
    out = []
    for s in rows:
        hall = db.get(Hall, s.hall_id)
        out.append(
            ShowtimeOut(
                id=s.id,
                hall_id=s.hall_id,
                film_title=s.film_title,
                start_at=s.start_at,
                hall_name=hall.name if hall else None,
            )
        )
    return out


@api_router.get("/seatmap/{showtime_id}", response_model=SeatMapOut)
def seatmap(showtime_id: int, db: Session = Depends(get_db)):
    st = db.get(Showtime, showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    holds = db.scalars(select(SeatHold).where(SeatHold.showtime_id == showtime_id)).all()
    occupied: set[tuple[int, int]] = set()
    for h in holds:
        for c in range(h.start_col, h.end_col + 1):
            occupied.add((h.row, c))
    wheelchair_seats: set[tuple[int, int]] = set()
    companion_seats: set[tuple[int, int]] = set()
    for p in hall.wheelchair_pairs:
        wheelchair_seats.add((p.row, p.col))
        companion_seats.add((p.row, p.companion_col))
    cells: list[SeatMapCell] = []
    total = hall.rows * hall.cols
    for r in range(1, hall.rows + 1):
        for c in range(1, hall.cols + 1):
            occ = (r, c) in occupied
            kind = "normal"
            if (r, c) in wheelchair_seats:
                kind = "wheelchair"
            elif (r, c) in companion_seats:
                kind = "companion"
            cells.append(
                SeatMapCell(
                    row=r,
                    col=c,
                    is_aisle=c in aisles,
                    occupied=occ,
                    heat=1.0 if occ else (0.15 if c in aisles else 0.0),
                    kind=kind,
                )
            )
    return SeatMapOut(
        showtime_id=showtime_id,
        hall_name=hall.name,
        rows=hall.rows,
        cols=hall.cols,
        cells=cells,
    )


@api_router.get("/holds", response_model=list[HoldOut])
def list_holds(db: Session = Depends(get_db)):
    return db.scalars(select(SeatHold).order_by(SeatHold.id.desc())).all()


@api_router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(db: Session = Depends(get_db)):
    return db.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).all()


@api_router.post("/holds", response_model=HoldOut)
def create_hold(body: HoldRequest, db: Session = Depends(get_db)):
    st = db.get(Showtime, body.showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    pairs = _pair_specs(hall)
    existing = db.scalars(select(SeatHold).where(SeatHold.showtime_id == body.showtime_id)).all()
    holds = [HoldSpan(row=h.row, start_col=h.start_col, end_col=h.end_col) for h in existing]
    seats_by_row: dict[int, list[SeatCell]] = {}
    for r in range(1, hall.rows + 1):
        seats_by_row[r] = [
            SeatCell(row=r, col=c, is_aisle=c in aisles) for c in range(1, hall.cols + 1)
        ]

    party_size = body.party_size
    kind = HOLD_KIND_NORMAL
    block = None
    if body.wheelchair_need:
        # 轮椅需求：只锁完整轮椅组合（轮椅位+陪同位），人数口径与组合座位数一致。
        party_size = WHEELCHAIR_COMBO_SIZE
        kind = HOLD_KIND_WHEELCHAIR
        combo = find_wheelchair_combo(pairs, holds)
        if combo is None:
            if not pairs:
                reason = "该影厅未登记轮椅位"
            else:
                reason = combo_conflict_reason(wheelchair_combo_blockers(pairs, holds))
            db.add(
                ConflictLog(showtime_id=body.showtime_id, party_size=party_size, reason=reason)
            )
            db.commit()
            raise HTTPException(409, reason)
        block = combo.span()
    else:
        # 普通连座：受保护陪同位视同不可用，只能由轮椅组合整体占用。
        reserved = protected_companion_cols(pairs)
        if body.preferred_row:
            block = find_contiguous_block(
                seats_by_row.get(body.preferred_row, []),
                holds,
                body.preferred_row,
                party_size,
                reserved_cols=reserved.get(body.preferred_row),
            )
        if block is None:
            block = find_bond_across_rows(seats_by_row, holds, party_size, reserved_by_row=reserved)
        if block is None:
            db.add(
                ConflictLog(
                    showtime_id=body.showtime_id,
                    party_size=party_size,
                    reason=f"无足够连续空座（人数 {party_size}）",
                )
            )
            db.commit()
            raise HTTPException(409, "无足够连续空座")

    hits = conflicts_with(holds, block)
    if hits:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=party_size,
                reason=f"与既有持座重叠：第{hits[0].row}排 {hits[0].start_col}-{hits[0].end_col}",
            )
        )
        db.commit()
        raise HTTPException(409, "与既有持座冲突")

    code = f"SB-{int(datetime.utcnow().timestamp()) % 100000:05d}"
    hold = SeatHold(
        showtime_id=body.showtime_id,
        order_code=code,
        row=block.row,
        start_col=block.start_col,
        end_col=block.end_col,
        party_size=party_size,
        kind=kind,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)
    return hold
