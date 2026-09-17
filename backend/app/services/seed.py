from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import ConflictLog, Hall, SeatHold, Showtime, WheelchairPair


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(Hall.id).limit(1)):
        return
    h1 = Hall(name="一号厅", rows=8, cols=12, aisle_cols="5,6")
    h2 = Hall(name="二号厅", rows=6, cols=10, aisle_cols="4,5")
    db.add_all([h1, h2])
    db.flush()
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    s1 = Showtime(hall_id=h1.id, film_title="星际旅人", start_at=now + timedelta(hours=2))
    s2 = Showtime(hall_id=h1.id, film_title="雾都夜曲", start_at=now + timedelta(hours=5))
    s3 = Showtime(hall_id=h2.id, film_title="山海经异", start_at=now + timedelta(hours=3))
    db.add_all([s1, s2, s3])
    db.flush()

    pair_a = WheelchairPair(hall_id=h1.id, wheel_row=4, wheel_col=4, companion_row=4, companion_col=3)
    pair_b = WheelchairPair(hall_id=h1.id, wheel_row=7, wheel_col=10, companion_row=7, companion_col=11)
    pair_c = WheelchairPair(hall_id=h2.id, wheel_row=2, wheel_col=8, companion_row=2, companion_col=9)
    db.add_all([pair_a, pair_b, pair_c])
    db.flush()

    db.add_all(
        [
            SeatHold(showtime_id=s1.id, order_code="SB-1001", row=3, start_col=2, end_col=4, party_size=3),
            SeatHold(showtime_id=s1.id, order_code="SB-1002", row=5, start_col=7, end_col=9, party_size=3),
            # Ordinary hold already sitting on pair_a's companion seat (row 4 col 3):
            # a later wheelchair request must conflict, not false-succeed.
            SeatHold(showtime_id=s1.id, order_code="SB-1004", row=4, start_col=1, end_col=3, party_size=3),
            # pair_b already taken as a complete wheelchair combo.
            SeatHold(
                showtime_id=s1.id,
                order_code="SB-1005",
                row=7,
                start_col=10,
                end_col=11,
                party_size=2,
                hold_type="wheelchair",
                pair_id=pair_b.id,
            ),
            SeatHold(showtime_id=s3.id, order_code="SB-1003", row=2, start_col=1, end_col=2, party_size=2),
        ]
    )
    db.add(ConflictLog(showtime_id=s1.id, party_size=4, reason="与既有持座重叠：第3排 2-4"))
    db.add(
        ConflictLog(
            showtime_id=s1.id,
            party_size=2,
            reason="轮椅需求冲突：第4排陪同位（第3列）已被订单 SB-1004 占用，轮椅组合不完整",
        )
    )
    db.commit()
