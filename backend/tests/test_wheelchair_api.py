"""API-level wheelchair flows: conflict points at the occupied companion, success books the combo."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Hall, SeatHold, Showtime, WheelchairPair


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    # 不进入 lifespan：不触 Postgres、不跑种子
    yield TestClient(app), TestingSessionLocal
    app.dependency_overrides.clear()


def _mk_showtime(db, rows=8, cols=12, aisles="5,6", name="测试厅"):
    hall = Hall(name=name, rows=rows, cols=cols, aisle_cols=aisles)
    db.add(hall)
    db.flush()
    st = Showtime(hall_id=hall.id, film_title="测试片", start_at=datetime(2026, 9, 17, 20, 0))
    db.add(st)
    db.flush()
    return hall, st


def test_wheelchair_conflict_points_to_companion(env):
    client, SessionLocal = env
    with SessionLocal() as db:
        hall, st = _mk_showtime(db)
        db.add(WheelchairPair(hall_id=hall.id, row=8, col=11, companion_col=12))
        # 普通持座已占掉陪同位（第8排12列）
        db.add(
            SeatHold(
                showtime_id=st.id, order_code="SB-X1", row=8, start_col=12, end_col=12, party_size=1
            )
        )
        db.commit()
        sid = st.id

    resp = client.post("/api/holds", json={"showtime_id": sid, "party_size": 2, "wheelchair_need": True})
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "陪同位" in detail
    assert "第8排" in detail and "12" in detail
    assert "无足够连续空座" not in detail

    conflicts = client.get("/api/conflicts").json()
    assert conflicts[0]["reason"] == detail
    assert conflicts[0]["party_size"] == 2  # 人数口径与组合座位数一致


def test_wheelchair_combo_success(env):
    client, SessionLocal = env
    with SessionLocal() as db:
        hall, st = _mk_showtime(db)
        db.add(WheelchairPair(hall_id=hall.id, row=8, col=11, companion_col=12))
        db.commit()
        sid = st.id

    resp = client.post("/api/holds", json={"showtime_id": sid, "party_size": 4, "wheelchair_need": True})
    assert resp.status_code == 200
    hold = resp.json()
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (8, 11, 12)
    assert hold["party_size"] == 2  # 组合座位数
    assert hold["kind"] == "wheelchair"

    cells = {(c["row"], c["col"]): c for c in client.get(f"/api/seatmap/{sid}").json()["cells"]}
    assert cells[(8, 11)]["kind"] == "wheelchair" and cells[(8, 11)]["occupied"]
    assert cells[(8, 12)]["kind"] == "companion" and cells[(8, 12)]["occupied"]
    assert cells[(8, 10)]["kind"] == "normal"

    holds = client.get("/api/holds").json()
    assert holds[0]["kind"] == "wheelchair"


def test_normal_search_cannot_eat_companion(env):
    client, SessionLocal = env
    with SessionLocal() as db:
        hall, st = _mk_showtime(db, rows=1, cols=2, aisles="")
        db.add(WheelchairPair(hall_id=hall.id, row=1, col=1, companion_col=2))
        db.commit()
        sid = st.id

    # 普通连座要 2 人：陪同位（第2列）受保护不可单独占用 → 凑不出连座必须失败
    resp = client.post("/api/holds", json={"showtime_id": sid, "party_size": 2})
    assert resp.status_code == 409
    assert "无足够连续空座" in resp.json()["detail"]
    assert client.get("/api/holds").json() == []  # 陪同位未被吃掉

    # 陪同位仍在 → 轮椅需求能锁到完整组合
    resp = client.post("/api/holds", json={"showtime_id": sid, "party_size": 2, "wheelchair_need": True})
    assert resp.status_code == 200
    hold = resp.json()
    assert (hold["row"], hold["start_col"], hold["end_col"]) == (1, 1, 2)
    assert hold["kind"] == "wheelchair"


def test_wheelchair_request_without_pairs(env):
    client, SessionLocal = env
    with SessionLocal() as db:
        _, st = _mk_showtime(db)
        db.commit()
        sid = st.id
    resp = client.post("/api/holds", json={"showtime_id": sid, "party_size": 2, "wheelchair_need": True})
    assert resp.status_code == 409
    assert "未登记轮椅位" in resp.json()["detail"]


def test_pair_crud_and_validation(env):
    client, SessionLocal = env
    with SessionLocal() as db:
        hall, st = _mk_showtime(db)
        db.commit()
        hid, sid = hall.id, st.id

    url = f"/api/halls/{hid}/wheelchair-pairs"
    assert client.post(url, json={"row": 2, "col": 3, "companion_col": 5}).status_code == 422  # 不相邻
    assert client.post(url, json={"row": 2, "col": 4, "companion_col": 5}).status_code == 422  # 过道列
    assert client.post(url, json={"row": 9, "col": 1, "companion_col": 2}).status_code == 422  # 超范围

    resp = client.post(url, json={"row": 2, "col": 7, "companion_col": 8})
    assert resp.status_code == 201
    pair_id = resp.json()["id"]
    # 与已登记组合重叠
    assert client.post(url, json={"row": 2, "col": 8, "companion_col": 9}).status_code == 422

    pairs = client.get(url).json()
    assert len(pairs) == 1 and pairs[0]["companion_col"] == 8

    cells = {(c["row"], c["col"]): c["kind"] for c in client.get(f"/api/seatmap/{sid}").json()["cells"]}
    assert cells[(2, 7)] == "wheelchair"
    assert cells[(2, 8)] == "companion"
    assert cells[(2, 9)] == "normal"

    assert client.delete(f"{url}/{pair_id}").status_code == 204
    assert client.get(url).json() == []
