"""Wheelchair pair engine: companion protection, combo search, registration validation."""

from app.services.bond_engine import (
    ComboBlocker,
    HoldSpan,
    SeatCell,
    WheelchairPair,
    combo_conflict_reason,
    find_bond_across_rows,
    find_contiguous_block,
    find_wheelchair_combo,
    protected_companion_cols,
    validate_wheelchair_pair,
    wheelchair_combo_blockers,
)


def _row(row, cols, aisles=()):
    return [SeatCell(row=row, col=c, is_aisle=(c in aisles)) for c in cols]


# —— 陪同位保护：普通连座搜索不得单独吃掉受保护陪同位 ——


def test_normal_search_skips_reserved_companion():
    cells = _row(1, range(1, 7))
    # 第3列是受保护陪同位：人数3的普通搜索不能吃掉它，只能去右侧段
    block = find_contiguous_block(cells, [], 1, 3, reserved_cols={3})
    assert block == HoldSpan(row=1, start_col=4, end_col=6)
    assert not (block.start_col <= 3 <= block.end_col)


def test_reserved_companion_is_only_free_seat_returns_none():
    cells = _row(1, range(1, 4))
    holds = [HoldSpan(row=1, start_col=1, end_col=1), HoldSpan(row=1, start_col=3, end_col=3)]
    # 唯一空座是陪同位（第2列）→ 普通搜索必须空手而归
    assert find_contiguous_block(cells, holds, 1, 1, reserved_cols={2}) is None


def test_across_rows_respects_reserved_cols():
    seats = {1: _row(1, range(1, 3)), 2: _row(2, range(1, 3))}
    reserved = {1: {1}}
    block = find_bond_across_rows(seats, [], 2, reserved_by_row=reserved)
    assert block == HoldSpan(row=2, start_col=1, end_col=2)


def test_protected_companion_cols_mapping():
    pairs = [WheelchairPair(row=8, col=11, companion_col=12), WheelchairPair(row=6, col=9, companion_col=10)]
    assert protected_companion_cols(pairs) == {8: {12}, 6: {10}}


# —— 轮椅组合搜索 ——


def test_combo_success_when_both_seats_free():
    pair = WheelchairPair(row=8, col=11, companion_col=12)
    assert find_wheelchair_combo([pair], []) == pair
    assert pair.span() == HoldSpan(row=8, start_col=11, end_col=12)


def test_combo_span_normalizes_companion_on_left():
    pair = WheelchairPair(row=8, col=12, companion_col=11)
    assert pair.span() == HoldSpan(row=8, start_col=11, end_col=12)


def test_combo_blocked_by_companion_occupied():
    pair = WheelchairPair(row=8, col=11, companion_col=12)
    holds = [HoldSpan(row=8, start_col=12, end_col=12)]
    assert find_wheelchair_combo([pair], holds) is None
    blockers = wheelchair_combo_blockers([pair], holds)
    assert blockers == [ComboBlocker(pair=pair, occupied=(("陪同位", 12),))]
    reason = combo_conflict_reason(blockers)
    assert "陪同位" in reason
    assert "第8排" in reason and "12" in reason
    assert "无足够连续空座" not in reason


def test_combo_blocked_by_wheelchair_seat_occupied():
    pair = WheelchairPair(row=8, col=11, companion_col=12)
    holds = [HoldSpan(row=8, start_col=11, end_col=11)]
    blockers = wheelchair_combo_blockers([pair], holds)
    assert blockers == [ComboBlocker(pair=pair, occupied=(("轮椅位", 11),))]
    assert "轮椅位" in combo_conflict_reason(blockers)


def test_combo_falls_through_to_next_free_pair():
    blocked = WheelchairPair(row=7, col=1, companion_col=2)
    free = WheelchairPair(row=8, col=11, companion_col=12)
    holds = [HoldSpan(row=7, start_col=2, end_col=2)]
    assert find_wheelchair_combo([blocked, free], holds) == free


# —— 登记校验：同排左右相邻、不隔过道、不重叠 ——


def test_validate_ok():
    pair = WheelchairPair(row=8, col=11, companion_col=12)
    assert validate_wheelchair_pair(8, 12, {5, 6}, pair, []) is None


def test_validate_rejects_non_adjacent():
    pair = WheelchairPair(row=8, col=10, companion_col=12)
    assert validate_wheelchair_pair(8, 12, set(), pair, []) == "轮椅位与陪同位必须同排左右相邻"


def test_validate_rejects_aisle_between_seats():
    # 轮椅位/陪同位本身落在过道列 → 拒绝
    pair = WheelchairPair(row=8, col=4, companion_col=5)
    assert validate_wheelchair_pair(8, 12, {5, 6}, pair, []) == "陪同位不能位于过道列（第5列）"
    pair = WheelchairPair(row=8, col=5, companion_col=4)
    assert validate_wheelchair_pair(8, 12, {5, 6}, pair, []) == "轮椅位不能位于过道列（第5列）"
    # 过道列4隔在第3列与第5列之间：两位均非过道但被过道断开 → 相邻性拒绝
    pair = WheelchairPair(row=8, col=3, companion_col=5)
    assert validate_wheelchair_pair(8, 12, {4}, pair, []) == "轮椅位与陪同位必须同排左右相邻"


def test_validate_rejects_out_of_bounds():
    assert validate_wheelchair_pair(8, 12, set(), WheelchairPair(row=9, col=1, companion_col=2), [])
    assert validate_wheelchair_pair(8, 12, set(), WheelchairPair(row=8, col=12, companion_col=13), [])


def test_validate_rejects_overlap_with_existing():
    existing = [WheelchairPair(row=8, col=11, companion_col=12)]
    assert validate_wheelchair_pair(8, 12, set(), WheelchairPair(row=8, col=11, companion_col=12), existing)
    assert validate_wheelchair_pair(8, 12, set(), WheelchairPair(row=8, col=10, companion_col=11), existing)
    assert validate_wheelchair_pair(8, 12, set(), WheelchairPair(row=8, col=12, companion_col=11), existing)
