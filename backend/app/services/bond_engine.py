"""Contiguous seat bonding: aisle columns break runs; holds conflict on overlap.

Wheelchair spots are registered together with a mandatory companion seat
(immediate neighbour in the same row, never across an aisle). A wheelchair
hold occupies the whole pair; until that happens the pair's cells are
protected from ordinary contiguous search so a later wheelchair request can
never be reported as a false success.
"""

from __future__ import annotations

from dataclasses import dataclass


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
    hold_type: str = "regular"
    pair_id: int | None = None
    order_code: str | None = None


@dataclass(frozen=True)
class WheelchairBinding:
    """A registered wheelchair spot and its forced adjacent companion seat."""

    pair_id: int
    row: int
    wheel_col: int
    companion_col: int

    def span(self) -> HoldSpan:
        lo, hi = sorted((self.wheel_col, self.companion_col))
        return HoldSpan(row=self.row, start_col=lo, end_col=hi, pair_id=self.pair_id)


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
    blocked_cols: set[int] | None = None,
) -> HoldSpan | None:
    """Find leftmost contiguous empty seats of party_size in a row.

    ``blocked_cols`` are protected cells (wheelchair/companion seats of a pair
    not yet taken by a wheelchair combo); ordinary search must never sell them.
    """
    if party_size <= 0:
        return None
    taken = occupied_cols(holds, row) | (blocked_cols or set())
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
    blocked_by_row: dict[int, set[int]] | None = None,
) -> HoldSpan | None:
    blocked_by_row = blocked_by_row or {}
    for row in sorted(seats_by_row.keys()):
        block = find_contiguous_block(
            seats_by_row[row], holds, row, party_size, blocked_by_row.get(row)
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
    row: int,
    wheel_col: int,
    companion_col: int,
    rows: int,
    cols: int,
    aisle_cols: set[int],
) -> str | None:
    """Return a Chinese error message if the binding is illegal, else None."""
    if not (1 <= row <= rows):
        return f"行号超出影厅范围（1-{rows}）"
    for label, col in (("轮椅位", wheel_col), ("陪同位", companion_col)):
        if not (1 <= col <= cols):
            return f"{label}列号超出影厅范围（1-{cols}）"
        if col in aisle_cols:
            return f"{label}不能设在过道列（第{col}列）"
    if wheel_col == companion_col:
        return "轮椅位与陪同位不能为同一格"
    if abs(wheel_col - companion_col) != 1:
        return "陪同位必须与轮椅位同排左右相邻，不得隔座或隔过道"
    return None


def protected_cells(bindings: list[WheelchairBinding]) -> dict[int, set[int]]:
    """Cells reserved for every binding not yet taken by a wheelchair hold.

    Caller passes only the *available* bindings (those without an existing
    wheelchair hold). Both cells of such a binding are off-limits to ordinary
    contiguous search; otherwise an ordinary party could eat the companion
    seat and a later wheelchair request would false-succeed into an impossible
    layout.
    """
    blocked: dict[int, set[int]] = {}
    for b in bindings:
        blocked.setdefault(b.row, set()).update((b.wheel_col, b.companion_col))
    return blocked


def wheelchair_pair_conflict(binding: WheelchairBinding, holds: list[HoldSpan]) -> HoldSpan | None:
    """Return the hold occupying either cell of the pair, else None.

    Prefers a hit on the companion cell so the conflict reason points at the
    occupied companion seat rather than a generic shortage.
    """
    wheel_hit: HoldSpan | None = None
    for h in holds:
        if h.row != binding.row:
            continue
        covers_wheel = h.start_col <= binding.wheel_col <= h.end_col
        covers_companion = h.start_col <= binding.companion_col <= h.end_col
        if covers_companion:
            return h
        if covers_wheel and wheel_hit is None:
            wheel_hit = h
    return wheel_hit


def find_wheelchair_combo(
    bindings_by_row: dict[int, list[WheelchairBinding]],
    holds: list[HoldSpan],
    preferred_row: int | None = None,
) -> tuple[WheelchairBinding, HoldSpan] | None:
    """Find the first free complete wheelchair+companion combo.

    Tried before any ordinary contiguous search. Returns the binding and the
    two-cell span to hold; None when no complete pair is available. The
    preferred row is searched first, then every other row.
    """
    ordered_rows = sorted(bindings_by_row.keys())
    if preferred_row in bindings_by_row:
        ordered_rows = [preferred_row] + [r for r in ordered_rows if r != preferred_row]
    for row in ordered_rows:
        for binding in bindings_by_row.get(row, []):
            if wheelchair_pair_conflict(binding, holds) is None:
                return binding, binding.span()
    return None
