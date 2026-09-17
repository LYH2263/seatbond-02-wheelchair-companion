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
    # 轮椅位登记：轮椅位 + 同排相邻陪同位（不隔过道）。
    db.add_all(
        [
            WheelchairPair(hall_id=h1.id, row=8, col=11, companion_col=12),
            WheelchairPair(hall_id=h2.id, row=6, col=9, companion_col=10),
        ]
    )
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    s1 = Showtime(hall_id=h1.id, film_title="星际旅人", start_at=now + timedelta(hours=2))
    s2 = Showtime(hall_id=h1.id, film_title="雾都夜曲", start_at=now + timedelta(hours=5))
    s3 = Showtime(hall_id=h2.id, film_title="山海经异", start_at=now + timedelta(hours=3))
    db.add_all([s1, s2, s3])
    db.flush()
    db.add_all(
        [
            SeatHold(showtime_id=s1.id, order_code="SB-1001", row=3, start_col=2, end_col=4, party_size=3),
            SeatHold(showtime_id=s1.id, order_code="SB-1002", row=5, start_col=7, end_col=9, party_size=3),
            SeatHold(showtime_id=s3.id, order_code="SB-1003", row=2, start_col=1, end_col=2, party_size=2),
            # 冲突剧本：普通持座已占掉一号厅轮椅组合的陪同位（第8排12列），
            # 对 s1 的轮椅需求请求必须冲突失败，且原因指向陪同位被占。
            SeatHold(showtime_id=s1.id, order_code="SB-1004", row=8, start_col=12, end_col=12, party_size=1),
        ]
    )
    # 成功路径：s2（一号厅）与 s3（二号厅）的陪同位空闲，轮椅需求可锁完整组合。
    db.add(ConflictLog(showtime_id=s1.id, party_size=4, reason="与既有持座重叠：第3排 2-4"))
    db.commit()
