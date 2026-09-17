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
    WheelchairPairCreate,
    WheelchairPairOut,
)
from app.services.bond_engine import (
    HoldSpan,
    SeatCell,
    WheelchairBinding,
    conflicts_with,
    find_bond_across_rows,
    find_contiguous_block,
    find_wheelchair_combo,
    protected_cells,
    validate_wheelchair_pair,
    wheelchair_pair_conflict,
)

api_router = APIRouter()


def _aisles(hall: Hall) -> list[int]:
    if not hall.aisle_cols.strip():
        return []
    return [int(x) for x in hall.aisle_cols.split(",") if x.strip()]


def _pair_out(p: WheelchairPair, occupied: bool = False) -> WheelchairPairOut:
    return WheelchairPairOut(
        id=p.id,
        wheel_row=p.wheel_row,
        wheel_col=p.wheel_col,
        companion_row=p.companion_row,
        companion_col=p.companion_col,
        occupied=occupied,
    )


def _hall_out(h: Hall) -> HallOut:
    return HallOut(
        id=h.id,
        name=h.name,
        rows=h.rows,
        cols=h.cols,
        aisle_cols=_aisles(h),
        wheelchair_pairs=[_pair_out(p) for p in h.wheelchair_pairs],
    )


def _to_span(h: SeatHold) -> HoldSpan:
    return HoldSpan(
        row=h.row,
        start_col=h.start_col,
        end_col=h.end_col,
        hold_type=h.hold_type,
        pair_id=h.pair_id,
        order_code=h.order_code,
    )


def _bindings(pairs: list[WheelchairPair]) -> list[WheelchairBinding]:
    return [
        WheelchairBinding(
            pair_id=p.id, row=p.wheel_row, wheel_col=p.wheel_col, companion_col=p.companion_col
        )
        for p in pairs
    ]


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
    return [_pair_out(p) for p in hall.wheelchair_pairs]


@api_router.post("/halls/{hall_id}/wheelchair-pairs", response_model=WheelchairPairOut)
def create_wheelchair_pair(hall_id: int, body: WheelchairPairCreate, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "影厅不存在")
    if body.companion_row != body.wheel_row:
        raise HTTPException(400, "陪同位必须与轮椅位在同一排")
    aisles = set(_aisles(hall))
    err = validate_wheelchair_pair(
        body.wheel_row, body.wheel_col, body.companion_col, hall.rows, hall.cols, aisles
    )
    if err:
        raise HTTPException(400, err)

    used: set[tuple[int, int]] = set()
    for p in hall.wheelchair_pairs:
        used.add((p.wheel_row, p.wheel_col))
        used.add((p.companion_row, p.companion_col))
    for cell in ((body.wheel_row, body.wheel_col), (body.companion_row, body.companion_col)):
        if cell in used:
            raise HTTPException(409, f"第{cell[0]}排第{cell[1]}列已登记为轮椅位或陪同位")

    pair = WheelchairPair(
        hall_id=hall_id,
        wheel_row=body.wheel_row,
        wheel_col=body.wheel_col,
        companion_row=body.companion_row,
        companion_col=body.companion_col,
    )
    db.add(pair)
    db.commit()
    db.refresh(pair)
    return _pair_out(pair)


@api_router.delete("/halls/{hall_id}/wheelchair-pairs/{pair_id}", status_code=204)
def delete_wheelchair_pair(hall_id: int, pair_id: int, db: Session = Depends(get_db)):
    pair = db.get(WheelchairPair, pair_id)
    if not pair or pair.hall_id != hall_id:
        raise HTTPException(404, "轮椅组合不存在")
    held = (
        db.scalars(
            select(SeatHold).where(
                SeatHold.pair_id == pair_id, SeatHold.hold_type == "wheelchair"
            )
        )
        .first()
    )
    if held:
        raise HTTPException(409, f"该组合已被订单 {held.order_code} 占用，无法删除")
    db.delete(pair)
    db.commit()
    return None


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
    occupied: dict[tuple[int, int], SeatHold] = {}
    for h in holds:
        for c in range(h.start_col, h.end_col + 1):
            occupied[(h.row, c)] = h

    pairs = db.scalars(
        select(WheelchairPair).where(WheelchairPair.hall_id == st.hall_id)
    ).all()
    kind_by_cell: dict[tuple[int, int], tuple[str, int]] = {}
    occupied_pair_ids = {
        h.pair_id for h in holds if h.hold_type == "wheelchair" and h.pair_id is not None
    }
    for p in pairs:
        kind_by_cell[(p.wheel_row, p.wheel_col)] = ("wheelchair", p.id)
        kind_by_cell[(p.companion_row, p.companion_col)] = ("companion", p.id)

    cells: list[SeatMapCell] = []
    for r in range(1, hall.rows + 1):
        for c in range(1, hall.cols + 1):
            hold = occupied.get((r, c))
            occ = hold is not None
            kind, pair_id = kind_by_cell.get((r, c), ("normal", None))
            cells.append(
                SeatMapCell(
                    row=r,
                    col=c,
                    is_aisle=c in aisles,
                    occupied=occ,
                    heat=1.0 if occ else (0.15 if c in aisles else 0.0),
                    seat_kind=kind,
                    held_kind=hold.hold_type if hold else None,
                    pair_id=pair_id,
                )
            )
    return SeatMapOut(
        showtime_id=showtime_id,
        hall_name=hall.name,
        rows=hall.rows,
        cols=hall.cols,
        cells=cells,
        wheelchair_pairs=[_pair_out(p, p.id in occupied_pair_ids) for p in pairs],
    )


@api_router.get("/holds", response_model=list[HoldOut])
def list_holds(db: Session = Depends(get_db)):
    return db.scalars(select(SeatHold).order_by(SeatHold.id.desc())).all()


@api_router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(db: Session = Depends(get_db)):
    return db.scalars(select(ConflictLog).order_by(ConflictLog.id.desc())).all()


def _next_order_code(db: Session) -> str:
    codes = db.scalars(select(SeatHold.order_code)).all()
    nums = [int(c.split("-")[1]) for c in codes if c and c.startswith("SB-") and c.split("-")[1].isdigit()]
    return f"SB-{max(nums, default=1000) + 1:04d}"


def _wheelchair_failure_reason(
    all_pairs: list[WheelchairPair],
    free_pairs: list[WheelchairPair],
    bindings: list[WheelchairBinding],
    holds: list[HoldSpan],
) -> str:
    """Conflict wording must name the occupied companion, not a vague shortage."""
    if not all_pairs:
        return "轮椅需求冲突：该影厅未登记轮椅位与陪同位组合"
    if not free_pairs:
        return "轮椅需求冲突：所有轮椅组合均已被占用"
    for binding in bindings:
        hit = wheelchair_pair_conflict(binding, holds)
        if hit is None:
            continue
        covers_companion = (
            hit.row == binding.row
            and hit.start_col <= binding.companion_col <= hit.end_col
        )
        which = "陪同位" if covers_companion else "轮椅位"
        col = binding.companion_col if covers_companion else binding.wheel_col
        return (
            f"轮椅需求冲突：第{binding.row}排{which}（第{col}列）已被订单 "
            f"{hit.order_code or '既有持座'} 占用，轮椅组合不完整"
        )
    return "轮椅需求冲突：无可用的完整轮椅+陪同组合"


@api_router.post("/holds", response_model=HoldOut)
def create_hold(body: HoldRequest, db: Session = Depends(get_db)):
    st = db.get(Showtime, body.showtime_id)
    if not st:
        raise HTTPException(404, "场次不存在")
    hall = db.get(Hall, st.hall_id)
    assert hall
    aisles = set(_aisles(hall))
    existing = db.scalars(select(SeatHold).where(SeatHold.showtime_id == body.showtime_id)).all()
    holds = [_to_span(h) for h in existing]
    seats_by_row = {
        r: [SeatCell(row=r, col=c, is_aisle=c in aisles) for c in range(1, hall.cols + 1)]
        for r in range(1, hall.rows + 1)
    }

    all_pairs = hall.wheelchair_pairs
    taken_pair_ids = {
        h.pair_id for h in existing if h.hold_type == "wheelchair" and h.pair_id is not None
    }
    free_pairs = [p for p in all_pairs if p.id not in taken_pair_ids]
    bindings = _bindings(free_pairs)
    bindings_by_row: dict[int, list[WheelchairBinding]] = {}
    for b in bindings:
        bindings_by_row.setdefault(b.row, []).append(b)

    if body.wheelchair:
        found = find_wheelchair_combo(bindings_by_row, holds, body.preferred_row)
        if found is None:
            reason = _wheelchair_failure_reason(all_pairs, free_pairs, bindings, holds)
            db.add(
                ConflictLog(
                    showtime_id=body.showtime_id,
                    party_size=2,
                    reason=reason,
                )
            )
            db.commit()
            raise HTTPException(409, reason)
        binding, span = found
        code = _next_order_code(db)
        hold = SeatHold(
            showtime_id=body.showtime_id,
            order_code=code,
            row=span.row,
            start_col=span.start_col,
            end_col=span.end_col,
            party_size=2,
            hold_type="wheelchair",
            pair_id=binding.pair_id,
        )
        db.add(hold)
        db.commit()
        db.refresh(hold)
        return hold

    blocked_by_row = protected_cells(bindings)
    block = None
    if body.preferred_row:
        block = find_contiguous_block(
            seats_by_row.get(body.preferred_row, []),
            holds,
            body.preferred_row,
            body.party_size,
            blocked_by_row.get(body.preferred_row),
        )
    if block is None:
        block = find_bond_across_rows(
            seats_by_row, holds, body.party_size, blocked_by_row
        )
    if block is None:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=f"无足够连续空座（人数 {body.party_size}）",
            )
        )
        db.commit()
        raise HTTPException(409, "无足够连续空座")

    hits = conflicts_with(holds, block)
    if hits:
        db.add(
            ConflictLog(
                showtime_id=body.showtime_id,
                party_size=body.party_size,
                reason=f"与既有持座重叠：第{hits[0].row}排 {hits[0].start_col}-{hits[0].end_col}",
            )
        )
        db.commit()
        raise HTTPException(409, "与既有持座冲突")

    code = _next_order_code(db)
    hold = SeatHold(
        showtime_id=body.showtime_id,
        order_code=code,
        row=block.row,
        start_col=block.start_col,
        end_col=block.end_col,
        party_size=body.party_size,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)
    return hold
