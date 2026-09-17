"""Contiguous seat bonding: aisle columns break runs; holds conflict on overlap.

Wheelchair pairs: a wheelchair seat is registered together with one mandatory
companion seat (same row, left/right adjacent, never across an aisle). The
companion seat is protected — normal contiguous search must treat it as
unavailable so it can only ever be consumed as part of its wheelchair combo.
"""

from __future__ import annotations

from dataclasses import dataclass

HOLD_KIND_NORMAL = "normal"
HOLD_KIND_WHEELCHAIR = "wheelchair"

#: A wheelchair combo always seats the wheelchair user plus one companion.
WHEELCHAIR_COMBO_SIZE = 2


@dataclass(frozen=True)
class SeatCell:
    row: int
    col: int
    is_aisle: bool = False


@dataclass(frozen=True)
class HoldSpan:
    row: int
    start_col: int
    end_col: int  # inclusive


@dataclass(frozen=True)
class WheelchairPair:
    """A wheelchair seat and its mandatory adjacent companion seat (same row)."""

    row: int
    col: int  # wheelchair seat column
    companion_col: int  # companion seat column, must be col ± 1

    def span(self) -> HoldSpan:
        start = min(self.col, self.companion_col)
        return HoldSpan(row=self.row, start_col=start, end_col=max(self.col, self.companion_col))


@dataclass(frozen=True)
class ComboBlocker:
    """Why a wheelchair pair cannot be booked: which of its seats are occupied."""

    pair: WheelchairPair
    occupied: tuple[tuple[str, int], ...]  # (("轮椅位", col) | ("陪同位", col)), ...


def contiguous_runs(row_cells: list[SeatCell]) -> list[tuple[int, int]]:
    """Return inclusive (start_col, end_col) runs of non-aisle seats, broken by aisles."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    prev_col: int | None = None
    for cell in sorted(row_cells, key=lambda c: c.col):
        if cell.is_aisle:
            if start is not None and prev_col is not None:
                runs.append((start, prev_col))
            start = None
            prev_col = None
            continue
        if start is None:
            start = cell.col
        elif prev_col is not None and cell.col != prev_col + 1:
            runs.append((start, prev_col))
            start = cell.col
        prev_col = cell.col
    if start is not None and prev_col is not None:
        runs.append((start, prev_col))
    return runs


def occupied_cols(holds: list[HoldSpan], row: int) -> set[int]:
    cols: set[int] = set()
    for h in holds:
        if h.row != row:
            continue
        for c in range(h.start_col, h.end_col + 1):
            cols.add(c)
    return cols


def find_contiguous_block(
    row_cells: list[SeatCell],
    holds: list[HoldSpan],
    row: int,
    party_size: int,
    reserved_cols: set[int] | None = None,
) -> HoldSpan | None:
    """Find leftmost contiguous empty seats of party_size in a row.

    ``reserved_cols`` are treated as occupied even though no hold covers them
    (e.g. protected companion seats that only a wheelchair combo may take).
    """
    if party_size <= 0:
        return None
    taken = occupied_cols(holds, row) | (reserved_cols or set())
    for start, end in contiguous_runs(row_cells):
        free = [c for c in range(start, end + 1) if c not in taken]
        # free may have holes if holds punched middle — rebuild consecutive segments
        seg_start: int | None = None
        prev: int | None = None
        for col in free:
            if seg_start is None:
                seg_start = col
            elif prev is not None and col != prev + 1:
                if prev - seg_start + 1 >= party_size:
                    return HoldSpan(row=row, start_col=seg_start, end_col=seg_start + party_size - 1)
                seg_start = col
            prev = col
        if seg_start is not None and prev is not None and prev - seg_start + 1 >= party_size:
            return HoldSpan(row=row, start_col=seg_start, end_col=seg_start + party_size - 1)
    return None


def find_bond_across_rows(
    seats_by_row: dict[int, list[SeatCell]],
    holds: list[HoldSpan],
    party_size: int,
    reserved_by_row: dict[int, set[int]] | None = None,
) -> HoldSpan | None:
    for row in sorted(seats_by_row.keys()):
        block = find_contiguous_block(
            seats_by_row[row],
            holds,
            row,
            party_size,
            reserved_cols=(reserved_by_row or {}).get(row),
        )
        if block is not None:
            return block
    return None


def conflicts_with(existing: list[HoldSpan], candidate: HoldSpan) -> list[HoldSpan]:
    hits: list[HoldSpan] = []
    for h in existing:
        if h.row != candidate.row:
            continue
        if h.end_col < candidate.start_col or candidate.end_col < h.start_col:
            continue
        hits.append(h)
    return hits


def validate_wheelchair_pair(
    rows: int,
    cols: int,
    aisle_cols: set[int],
    pair: WheelchairPair,
    existing: list[WheelchairPair],
) -> str | None:
    """Validate a wheelchair/companion registration; return an error message or None.

    The companion must sit in the same row, exactly one column away, and neither
    seat may be an aisle column — since aisles are whole columns, adjacency plus
    non-aisle seats guarantees the pair is not split by an aisle.
    """
    if not 1 <= pair.row <= rows:
        return f"排号超出范围（1-{rows}）"
    for label, col in (("轮椅位", pair.col), ("陪同位", pair.companion_col)):
        if not 1 <= col <= cols:
            return f"{label}列号超出范围（1-{cols}）"
        if col in aisle_cols:
            return f"{label}不能位于过道列（第{col}列）"
    if abs(pair.col - pair.companion_col) != 1:
        return "轮椅位与陪同位必须同排左右相邻"
    new_seats = {pair.col, pair.companion_col}
    for p in existing:
        if p.row == pair.row and new_seats & {p.col, p.companion_col}:
            return f"与已登记组合座位重叠：第{p.row}排 第{p.col}/{p.companion_col}列"
    return None


def protected_companion_cols(pairs: list[WheelchairPair]) -> dict[int, set[int]]:
    """Companion seats reserved from normal search, keyed by row."""
    reserved: dict[int, set[int]] = {}
    for p in pairs:
        reserved.setdefault(p.row, set()).add(p.companion_col)
    return reserved


def find_wheelchair_combo(
    pairs: list[WheelchairPair],
    holds: list[HoldSpan],
) -> WheelchairPair | None:
    """First pair (row, then column order) whose wheelchair and companion seats are both free."""
    for pair in sorted(pairs, key=lambda p: (p.row, p.col)):
        taken = occupied_cols(holds, pair.row)
        if pair.col not in taken and pair.companion_col not in taken:
            return pair
    return None


def wheelchair_combo_blockers(
    pairs: list[WheelchairPair],
    holds: list[HoldSpan],
) -> list[ComboBlocker]:
    """For each unavailable pair, which of its seats are occupied and by which role."""
    blockers: list[ComboBlocker] = []
    for pair in sorted(pairs, key=lambda p: (p.row, p.col)):
        taken = occupied_cols(holds, pair.row)
        occupied: list[tuple[str, int]] = []
        if pair.col in taken:
            occupied.append(("轮椅位", pair.col))
        if pair.companion_col in taken:
            occupied.append(("陪同位", pair.companion_col))
        if occupied:
            blockers.append(ComboBlocker(pair=pair, occupied=tuple(occupied)))
    return blockers


def combo_conflict_reason(blockers: list[ComboBlocker]) -> str:
    """Specific conflict reason naming the occupied seats (never a generic 'no seats')."""
    parts = [
        f"第{b.pair.row}排{label}（第{col}列）已被占用"
        for b in blockers
        for label, col in b.occupied
    ]
    return "轮椅组合不可用：" + "；".join(parts)
