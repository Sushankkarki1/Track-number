"""Main FastAPI app for the Track Number project."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app import crud, models
from app.database import SessionLocal, engine
from app.routers import admin, search
from app.utils.logger.central_logger import logger

app = FastAPI(
    title="Track Number",
    description="A simple vehicle registration lookup system for BCA project work.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(search.router)
app.include_router(admin.router)


@app.on_event("startup")
def startup() -> None:
    """Create missing tables and insert sample data only when the database is empty."""
    try:
        models.Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            crud.seed_sample_data(db)
        finally:
            db.close()
    except SQLAlchemyError as exc:
        logger.error("Database setup failed: %s", exc)
