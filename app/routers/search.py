"""Public vehicle search routes."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.utils.logger.central_logger import logger

router = APIRouter()
templates = Jinja2Templates(directory="templates")

REGISTRATION_PATTERN = re.compile(r"^[A-Z]{2}\d[A-Z]{2,3}\d{4}$")


def is_valid_registration_number(registration_number: str) -> bool:
    """Check the simple registration number format used in this project."""
    clean_number = crud.normalize_registration_number(registration_number)
    return bool(REGISTRATION_PATTERN.fullmatch(clean_number))


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@router.get("/result", response_class=HTMLResponse)
def show_result(
    request: Request,
    registration_number: str = Query(default=""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    clean_number = crud.normalize_registration_number(registration_number)

    if not clean_number or not is_valid_registration_number(clean_number):
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "message": "Please enter a valid registration number.",
                "registration_number": registration_number,
            },
        )

    try:
        vehicle = crud.get_vehicle_by_registration(db, clean_number)
    except SQLAlchemyError as exc:
        logger.error("Vehicle search page failed for %s: %s", clean_number, exc)
        return templates.TemplateResponse(
            request,
            "result.html",
            {
                "error": "Database connection failed. Please check your setup.",
            },
            status_code=500,
        )

    if vehicle is None:
        return templates.TemplateResponse(
            request,
            "result.html",
            {
                "message": "No vehicle record found.",
                "registration_number": clean_number,
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "result.html",
        {"vehicle": vehicle},
    )


@router.get("/search/{registration_number}", response_model=schemas.VehicleSearchResult)
def search_vehicle(
    registration_number: str, db: Session = Depends(get_db)
) -> schemas.VehicleSearchResult:
    clean_number = crud.normalize_registration_number(registration_number)
    if not clean_number or not is_valid_registration_number(clean_number):
        raise HTTPException(
            status_code=400, detail="Please enter a valid registration number."
        )

    try:
        vehicle = crud.get_vehicle_by_registration(db, clean_number)
    except SQLAlchemyError as exc:
        logger.error("Vehicle search API failed for %s: %s", clean_number, exc)
        raise HTTPException(
            status_code=500, detail="Database connection failed. Please check setup."
        ) from exc

    if vehicle is None:
        raise HTTPException(status_code=404, detail="No vehicle record found.")

    return schemas.VehicleSearchResult(
        registration_number=vehicle.registration_number,
        vehicle_name=vehicle.vehicle_name,
        model=vehicle.model,
        owner_name=vehicle.owner.full_name,
        registered_year=vehicle.registered_year,
        color=vehicle.color,
    )
