"""Simple administrator routes for vehicle records."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import auth, crud, schemas
from app.database import get_db
from app.routers.search import is_valid_registration_number
from app.utils.logger.central_logger import logger

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="templates")


def _admin_login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/admin/login", status_code=303)


def _require_admin_api(request: Request) -> None:
    if not auth.is_admin_request(request):
        raise HTTPException(status_code=401, detail="Admin login required.")


def _vehicle_schema_from_form(form: dict) -> schemas.VehicleCreate:
    registration_number = str(form.get("registration_number", "")).strip()
    if not is_valid_registration_number(registration_number):
        raise ValueError("Please enter a valid registration number.")

    try:
        registered_year = int(str(form.get("registered_year", "0")))
        owner_id = int(str(form.get("owner_id", "0")))
    except ValueError as exc:
        raise ValueError("Registered year and owner must be valid numbers.") from exc

    return schemas.VehicleCreate(
        registration_number=registration_number,
        vehicle_name=str(form.get("vehicle_name", "")).strip(),
        model=str(form.get("model", "")).strip(),
        registered_year=registered_year,
        color=str(form.get("color", "")).strip(),
        owner_id=owner_id,
    )


@router.get("/login", response_class=HTMLResponse, response_model=None)
def admin_login_page(request: Request) -> HTMLResponse | RedirectResponse:
    if auth.is_admin_request(request):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(request, "admin_login.html")


@router.post("/login", response_model=None)
async def admin_login(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse | RedirectResponse:
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))

    try:
        admin_user = crud.get_admin_by_username(db, username)
    except SQLAlchemyError as exc:
        logger.error("Admin login database failed: %s", exc)
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "Database connection failed. Please check your setup."},
            status_code=500,
        )

    if admin_user is None or not auth.verify_password(password, admin_user.password):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "Invalid username or password."},
            status_code=401,
        )

    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(
        key=auth.ADMIN_COOKIE_NAME,
        value=auth.create_admin_cookie(admin_user.username),
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout", response_model=None)
def admin_logout() -> RedirectResponse:
    response = RedirectResponse(url="/admin/login?message=Logged out", status_code=303)
    response.delete_cookie(auth.ADMIN_COOKIE_NAME)
    return response


@router.get("", response_class=HTMLResponse, response_model=None)
def admin_page(
    request: Request, db: Session = Depends(get_db)
) -> HTMLResponse | RedirectResponse:
    if not auth.is_admin_request(request):
        return _admin_login_redirect()

    try:
        vehicles = crud.get_vehicles(db)
        owners = crud.get_owners(db)
    except SQLAlchemyError as exc:
        logger.error("Admin page database load failed: %s", exc)
        vehicles = []
        owners = []
        error = "Database connection failed. Please check your setup."
    else:
        error = None

    return templates.TemplateResponse(
        request,
        "admin.html",
        {"vehicles": vehicles, "owners": owners, "error": error},
    )


@router.get("/vehicles", response_model=list[schemas.VehicleRead])
def list_vehicles(
    request: Request, db: Session = Depends(get_db)
) -> list[schemas.VehicleRead]:
    _require_admin_api(request)
    return crud.get_vehicles(db)


@router.post("/vehicles", response_model=schemas.VehicleRead, status_code=201)
def add_vehicle(
    vehicle: schemas.VehicleCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> object:
    _require_admin_api(request)
    if not is_valid_registration_number(vehicle.registration_number):
        raise HTTPException(
            status_code=400, detail="Please enter a valid registration number."
        )
    try:
        return crud.create_vehicle(db, vehicle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Create vehicle API failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Database operation failed."
        ) from exc


@router.put("/vehicles/{vehicle_id}", response_model=schemas.VehicleRead)
def edit_vehicle(
    vehicle_id: int,
    vehicle: schemas.VehicleUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> object:
    _require_admin_api(request)
    if not is_valid_registration_number(vehicle.registration_number):
        raise HTTPException(
            status_code=400, detail="Please enter a valid registration number."
        )
    try:
        updated_vehicle = crud.update_vehicle(db, vehicle_id, vehicle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Update vehicle API failed for id %s: %s", vehicle_id, exc)
        raise HTTPException(
            status_code=500, detail="Database operation failed."
        ) from exc

    if updated_vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found.")
    return updated_vehicle


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_vehicle(
    vehicle_id: int, request: Request, db: Session = Depends(get_db)
) -> None:
    _require_admin_api(request)
    try:
        deleted = crud.delete_vehicle(db, vehicle_id)
    except SQLAlchemyError as exc:
        logger.error("Delete vehicle API failed for id %s: %s", vehicle_id, exc)
        raise HTTPException(
            status_code=500, detail="Database operation failed."
        ) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Vehicle not found.")


@router.post("/vehicles/form", response_model=None)
async def add_vehicle_from_form(
    request: Request, db: Session = Depends(get_db)
) -> RedirectResponse | HTMLResponse:
    if not auth.is_admin_request(request):
        return _admin_login_redirect()

    form = await request.form()
    try:
        vehicle = _vehicle_schema_from_form(dict(form))
        crud.create_vehicle(db, vehicle)
    except (ValueError, ValidationError) as exc:
        return _admin_error_response(request, db, str(exc))
    except SQLAlchemyError as exc:
        logger.error("Create vehicle form failed: %s", exc)
        return _admin_error_response(request, db, "Database operation failed.")

    return RedirectResponse(url="/admin?message=Vehicle added", status_code=303)


@router.post("/vehicles/{vehicle_id}/edit", response_model=None)
async def edit_vehicle_from_form(
    vehicle_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse | HTMLResponse:
    if not auth.is_admin_request(request):
        return _admin_login_redirect()

    form = await request.form()
    try:
        form_vehicle = _vehicle_schema_from_form(dict(form))
        vehicle = schemas.VehicleUpdate(**form_vehicle.model_dump())
        updated_vehicle = crud.update_vehicle(db, vehicle_id, vehicle)
    except (ValueError, ValidationError) as exc:
        return _admin_error_response(request, db, str(exc))
    except SQLAlchemyError as exc:
        logger.error("Update vehicle form failed for id %s: %s", vehicle_id, exc)
        return _admin_error_response(request, db, "Database operation failed.")

    if updated_vehicle is None:
        return _admin_error_response(request, db, "Vehicle not found.")
    return RedirectResponse(url="/admin?message=Vehicle updated", status_code=303)


@router.post("/vehicles/{vehicle_id}/delete", response_model=None)
def delete_vehicle_from_form(
    vehicle_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    if not auth.is_admin_request(request):
        return _admin_login_redirect()

    try:
        deleted = crud.delete_vehicle(db, vehicle_id)
    except SQLAlchemyError as exc:
        logger.error("Delete vehicle form failed for id %s: %s", vehicle_id, exc)
        return RedirectResponse(
            url="/admin?error=Database operation failed", status_code=303
        )

    if not deleted:
        return RedirectResponse(url="/admin?error=Vehicle not found", status_code=303)
    return RedirectResponse(url="/admin?message=Vehicle deleted", status_code=303)


def _admin_error_response(request: Request, db: Session, error: str) -> HTMLResponse:
    try:
        vehicles = crud.get_vehicles(db)
        owners = crud.get_owners(db)
    except SQLAlchemyError as exc:
        logger.error("Admin error response load failed: %s", exc)
        vehicles = []
        owners = []

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "vehicles": vehicles,
            "owners": owners,
            "error": error,
        },
        status_code=400,
    )
