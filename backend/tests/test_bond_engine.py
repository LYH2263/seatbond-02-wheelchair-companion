from app.services.bond_engine import (
    HoldSpan,
    SeatCell,
    WheelchairBinding,
    conflicts_with,
    contiguous_runs,
    find_bond_across_rows,
    find_contiguous_block,
    find_wheelchair_combo,
    protected_cells,
    validate_wheelchair_pair,
    wheelchair_pair_conflict,
)


def _row(cols, aisles=()):
    return [SeatCell(row=1, col=c, is_aisle=(c in aisles)) for c in cols]


def _binding(pair_id=1, row=4, wheel=4, companion=3):
    return WheelchairBinding(pair_id=pair_id, row=row, wheel_col=wheel, companion_col=companion)


def test_aisle_breaks_runs():
    cells = _row(range(1, 11), aisles={5, 6})
    assert contiguous_runs(cells) == [(1, 4), (7, 10)]


def test_find_contiguous_skips_occupied():
    cells = _row(range(1, 9))
    holds = [HoldSpan(row=1, start_col=2, end_col=3)]
    block = find_contiguous_block(cells, holds, 1, 3)
    assert block == HoldSpan(row=1, start_col=4, end_col=6)


def test_party_too_large_returns_none():
    cells = _row(range(1, 5), aisles={3})
    assert find_contiguous_block(cells, [], 1, 3) is None


def test_conflict_overlap():
    existing = [HoldSpan(row=2, start_col=4, end_col=6)]
    cand = HoldSpan(row=2, start_col=6, end_col=8)
    assert conflicts_with(existing, cand) == existing


def test_find_across_rows():
    seats = {
        1: _row(range(1, 5)),
        2: [SeatCell(row=2, col=c) for c in range(1, 9)],
    }
    holds = [HoldSpan(row=1, start_col=1, end_col=4)]
    block = find_bond_across_rows(seats, holds, 4)
    assert block == HoldSpan(row=2, start_col=1, end_col=4)


def test_validate_requires_adjacent_same_row():
    # same row but two columns apart — illegal
    assert validate_wheelchair_pair(4, 4, 6, 8, 12, set()) is not None
    # seat sitting on an aisle column — illegal
    assert validate_wheelchair_pair(4, 4, 5, 8, 12, {5}) is not None
    # immediate neighbours, no aisle — legal
    assert validate_wheelchair_pair(4, 4, 3, 8, 12, set()) is None


def test_protected_cells_block_ordinary_search():
    """Ordinary contiguous search must not eat an idle companion seat."""
    b = _binding(row=1, wheel=4, companion=3)
    blocked = protected_cells([b])
    cells = _row(range(1, 7))
    # a party of 3 cannot use cols 3/4, and cols 1-2 are only two wide
    assert find_contiguous_block(cells, [], 1, 3, blocked.get(1)) is None
    # a party of 2 still fits before the protected pair
    two = find_contiguous_block(cells, [], 1, 2, blocked.get(1))
    assert two == HoldSpan(row=1, start_col=1, end_col=2)
    assert two.end_col < 3


def test_protection_does_not_apply_after_wheelchair_hold():
    """Once the combo is taken by a wheelchair hold, its cells leave protection."""
    assert protected_cells([]) == {}
    hold = HoldSpan(row=1, start_col=3, end_col=4, hold_type="wheelchair", pair_id=1)
    cells = _row(range(1, 7))
    block = find_contiguous_block(cells, [hold], 1, 2)
    assert block == HoldSpan(row=1, start_col=1, end_col=2)


def test_wheelchair_combo_success_when_free():
    b = _binding()
    found = find_wheelchair_combo({4: [b]}, [])
    assert found is not None
    binding, span = found
    assert binding is b
    assert span == HoldSpan(row=4, start_col=3, end_col=4, pair_id=1)


def test_wheelchair_combo_fails_when_companion_held():
    b = _binding(row=4, wheel=4, companion=3)
    regular = HoldSpan(row=4, start_col=1, end_col=3, order_code="SB-1004")
    assert find_wheelchair_combo({4: [b]}, [regular]) is None
    hit = wheelchair_pair_conflict(b, [regular])
    assert hit is regular


def test_wheelchair_combo_prefers_free_pair():
    b1 = _binding(pair_id=1, row=4, wheel=4, companion=3)
    b2 = _binding(pair_id=2, row=7, wheel=10, companion=11)
    # SB-1004 occupies the first pair's companion seat (row 4 cols 1-3)
    regular = HoldSpan(row=4, start_col=1, end_col=3, order_code="SB-1004")
    found = find_wheelchair_combo({4: [b1], 7: [b2]}, [regular])
    assert found is not None
    binding, span = found
    assert binding.pair_id == 2
    assert span.row == 7


def test_conflict_points_at_companion_not_wheelchair():
    b = _binding(row=4, wheel=4, companion=3)
    companion_hold = HoldSpan(row=4, start_col=2, end_col=3, order_code="SB-2001")
    hit = wheelchair_pair_conflict(b, [companion_hold])
    assert hit is companion_hold
    assert hit.start_col <= b.companion_col <= hit.end_col
