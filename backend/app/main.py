from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _ensure_schema() -> None:
    """create_all covers new tables; add new columns to pre-existing ones."""
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(
                text("ALTER TABLE seat_holds ADD COLUMN IF NOT EXISTS kind VARCHAR(20) NOT NULL DEFAULT 'normal'")
            )
        elif engine.dialect.name == "sqlite":
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(seat_holds)"))}
            if cols and "kind" not in cols:
                conn.execute(text("ALTER TABLE seat_holds ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'normal'"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="SeatBond", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
