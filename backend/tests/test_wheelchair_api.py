"""End-to-end checks for wheelchair + companion protection via the API."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.models import ConflictLog, Hall, SeatHold, Showtime, WheelchairPair


@pytest.fixture
def db_session():
    settings.seed_on_empty = False
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.fixture
def client(db_session):
    return TestClient(app)


def _make_hall(db, rows=5, cols=8, aisle_cols=""):
    hall = Hall(name="测试厅", rows=rows, cols=cols, aisle_cols=aisle_cols)
    db.add(hall)
    db.flush()
    st = Showtime(hall_id=hall.id, film_title="测试片", start_at=datetime.utcnow())
    db.add(st)
    db.commit()
    return hall.id, st.id


def test_register_pair_enforces_adjacency(client, db_session):
    hall_id, _ = _make_hall(db_session)

    ok = client.post(
        f"/api/halls/{hall_id}/wheelchair-pairs",
        json={"wheel_row": 1, "wheel_col": 4, "companion_row": 1, "companion_col": 3},
    )
    assert ok.status_code == 200
    assert ok.json()["companion_col"] == 3

    gap = client.post(
        f"/api/halls/{hall_id}/wheelchair-pairs",
        json={"wheel_row": 2, "wheel_col": 4, "companion_row": 2, "companion_col": 6},
    )
    assert gap.status_code == 400

    listed = client.get(f"/api/halls/{hall_id}/wheelchair-pairs").json()
    assert len(listed) == 1


def test_ordinary_search_cannot_eat_companion(client, db_session):
    hall_id, st_id = _make_hall(db_session)
    client.post(
        f"/api/halls/{hall_id}/wheelchair-pairs",
        json={"wheel_row": 1, "wheel_col": 4, "companion_row": 1, "companion_col": 3},
    )

    r = client.post("/api/holds", json={"showtime_id": st_id, "party_size": 4})
    assert r.status_code == 200
    hold = r.json()
    # cols 3-4 are protected; the 4-block must land after them, not eat col 3
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (1, 5, 8)
    assert hold["hold_type"] == "regular"


def test_wheelchair_request_takes_full_combo(client, db_session):
    hall_id, st_id = _make_hall(db_session)
    p = client.post(
        f"/api/halls/{hall_id}/wheelchair-pairs",
        json={"wheel_row": 1, "wheel_col": 4, "companion_row": 1, "companion_col": 3},
    ).json()

    r = client.post(
        "/api/holds", json={"showtime_id": st_id, "party_size": 1, "wheelchair": True}
    )
    assert r.status_code == 200
    hold = r.json()
    assert hold["hold_type"] == "wheelchair"
    assert hold["pair_id"] == p["id"]
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (1, 3, 4)
    # headcount follows the two-seat combo, not the requested party size
    assert hold["party_size"] == 2


def test_wheelchair_conflict_when_companion_occupied(client, db_session):
    hall_id, st_id = _make_hall(db_session)
    pair = WheelchairPair(
        hall_id=hall_id, wheel_row=4, wheel_col=4, companion_row=4, companion_col=3
    )
    db_session.add(pair)
    db_session.flush()
    # Seed: an ordinary hold already covers the companion seat (row 4 col 3).
    db_session.add(
        SeatHold(
            showtime_id=st_id,
            order_code="SB-1004",
            row=4,
            start_col=1,
            end_col=3,
            party_size=3,
        )
    )
    db_session.commit()

    r = client.post(
        "/api/holds", json={"showtime_id": st_id, "party_size": 2, "wheelchair": True}
    )
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "陪同位" in detail
    assert "SB-1004" in detail

    log = db_session.scalars(
        select(ConflictLog).order_by(ConflictLog.id.desc())
    ).first()
    assert log is not None
    assert "陪同位" in log.reason
    assert "SB-1004" in log.reason

    wh = db_session.scalars(
        select(SeatHold).where(SeatHold.hold_type == "wheelchair")
    ).all()
    assert len(wh) == 0


def test_seatmap_marks_pair_cells(client, db_session):
    hall_id, st_id = _make_hall(db_session)
    client.post(
        f"/api/halls/{hall_id}/wheelchair-pairs",
        json={"wheel_row": 1, "wheel_col": 4, "companion_row": 1, "companion_col": 3},
    )

    cells = client.get(f"/api/seatmap/{st_id}").json()["cells"]
    kinds = {(c["row"], c["col"]): c["seat_kind"] for c in cells}
    assert kinds[(1, 4)] == "wheelchair"
    assert kinds[(1, 3)] == "companion"
    assert kinds[(1, 1)] == "normal"
