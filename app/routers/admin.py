"""Simple administrator routes for vehicle records."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import auth, crud, schemas, models
from app.database import get_db
from app.routers.search import is_valid_registration_number
from app.utils.logger.central_logger import logger


router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="templates")


# ============================================================
# FORGOT PASSWORD SETTINGS
# ============================================================
#
# CHANGE THESE TO YOUR OWN QUESTION AND ANSWER.
#
# The answer is case-insensitive.
#
# Example:
#
# RESET_QUESTION = "What was my first bike?"
# RESET_ANSWER = "yamaha"
#
# ============================================================

RESET_QUESTION = "What is your favorite programming language?"
RESET_ANSWER = "python"


# ============================================================
# HELPERS
# ============================================================

def _admin_login_redirect() -> RedirectResponse:
    return RedirectResponse(
        url="/admin/login",
        status_code=303,
    )


def _require_admin_api(request: Request) -> None:
    if not auth.is_admin_request(request):
        raise HTTPException(
            status_code=401,
            detail="Admin login required.",
        )


def _normalize_reset_answer(answer: str) -> str:
    """Normalize security-answer input."""
    return " ".join(
        answer.strip().lower().split()
    )


def _vehicle_schema_from_form(
    form: dict,
    db: Session,
) -> schemas.VehicleCreate:

    registration_number = str(
        form.get("registration_number", "")
    ).strip()

    if not is_valid_registration_number(registration_number):
        raise ValueError(
            "Please enter a valid registration number."
        )

    # ---------------------------------------------
    # Basic vehicle information
    # ---------------------------------------------

    vehicle_name = str(
        form.get("vehicle_name", "")
    ).strip()

    model = str(
        form.get("model", "")
    ).strip()

    color = str(
        form.get("color", "")
    ).strip()

    try:
        registered_year = int(
            str(form.get("registered_year", "0"))
        )
    except ValueError as exc:
        raise ValueError(
            "Registered year must be a valid number."
        ) from exc

    # ---------------------------------------------
    # OWNER NAME
    # ---------------------------------------------
    #
    # The HTML form now sends owner_name instead
    # of owner_id.
    #
    # If the owner already exists:
    #     use the existing owner_id.
    #
    # If the owner does not exist:
    #     create a new owner automatically.
    # ---------------------------------------------

    owner_name = str(
        form.get("owner_name", "")
    ).strip()

    if not owner_name:
        raise ValueError(
            "Owner name is required."
        )

    # Look for an existing owner.
    owner = (
        db.query(models.Owner)
        .filter(
            models.Owner.full_name.ilike(owner_name)
        )
        .first()
    )

    # ---------------------------------------------
    # Existing owner
    # ---------------------------------------------

    if owner is None:

        owner_phone = str(
            form.get("owner_phone", "")
        ).strip()

        owner_address = str(
            form.get("owner_address", "")
        ).strip()

        # These columns are NOT nullable in your
        # database, so provide safe defaults when
        # phone/address are not entered.
        if not owner_phone:
            owner_phone = "Not provided"

        if not owner_address:
            owner_address = "Not provided"

        owner = models.Owner(
            full_name=owner_name,
            phone=owner_phone,
            address=owner_address,
        )

        db.add(owner)
        db.flush()

    # ---------------------------------------------
    # Create VehicleCreate schema
    # ---------------------------------------------

    return schemas.VehicleCreate(
        registration_number=registration_number,
        vehicle_name=vehicle_name,
        model=model,
        registered_year=registered_year,
        color=color,
        owner_id=owner.owner_id,
    )

# ============================================================
# ADMIN LOGIN
# ============================================================

@router.get(
    "/login",
    response_class=HTMLResponse,
    response_model=None,
)
def admin_login_page(
    request: Request,
) -> HTMLResponse | RedirectResponse:

    if auth.is_admin_request(request):

        return RedirectResponse(
            url="/admin",
            status_code=303,
        )

    return templates.TemplateResponse(
        request,
        "admin_login.html",
    )


@router.post(
    "/login",
    response_model=None,
)
async def admin_login(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:

    form = await request.form()

    username = str(
        form.get(
            "username",
            "",
        )
    ).strip()

    password = str(
        form.get(
            "password",
            "",
        )
    )

    try:

        admin_user = crud.get_admin_by_username(
            db,
            username,
        )

    except SQLAlchemyError as exc:

        logger.error(
            "Admin login database failed: %s",
            exc,
        )

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "error":
                    "Database connection failed. "
                    "Please check your setup."
            },
            status_code=500,
        )

    if (
        admin_user is None
        or not auth.verify_password(
            password,
            admin_user.password,
        )
    ):

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "error":
                    "Invalid username or password."
            },
            status_code=401,
        )

    response = RedirectResponse(
        url="/admin",
        status_code=303,
    )

    response.set_cookie(
        key=auth.ADMIN_COOKIE_NAME,
        value=auth.create_admin_cookie(
            admin_user.username
        ),
        httponly=True,
        samesite="lax",
    )

    return response


# ============================================================
# FORGOT PASSWORD PAGE
# ============================================================

@router.get(
    "/forgot-password",
    response_class=HTMLResponse,
    response_model=None,
)
def forgot_password_page(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {
            "forgot_password": True,
            "reset_question": RESET_QUESTION,
            "error": None,
            "message": None,
        },
    )


# ============================================================
# FORGOT PASSWORD / RESET PASSWORD
# ============================================================

@router.post(
    "/forgot-password",
    response_model=None,
)
async def forgot_password(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:

    form = await request.form()

    username = str(
        form.get(
            "username",
            "",
        )
    ).strip()

    answer = str(
        form.get(
            "answer",
            "",
        )
    )

    new_password = str(
        form.get(
            "new_password",
            "",
        )
    )

    confirm_password = str(
        form.get(
            "confirm_password",
            "",
        )
    )

    # --------------------------------------------------------
    # Validate username
    # --------------------------------------------------------

    if not username:

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error": "Username is required.",
                "message": None,
            },
            status_code=400,
        )


    # --------------------------------------------------------
    # Validate security answer
    # --------------------------------------------------------

    if not answer:

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error": "Security answer is required.",
                "message": None,
            },
            status_code=400,
        )


    correct_answer = _normalize_reset_answer(
        RESET_ANSWER
    )

    provided_answer = _normalize_reset_answer(
        answer
    )

    if provided_answer != correct_answer:

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error": "Incorrect security answer.",
                "message": None,
            },
            status_code=400,
        )


    # --------------------------------------------------------
    # Validate new password
    # --------------------------------------------------------

    if not new_password:

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error": "New password is required.",
                "message": None,
            },
            status_code=400,
        )


    if len(new_password) < 8:

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error":
                    "New password must be at least 8 characters.",
                "message": None,
            },
            status_code=400,
        )


    if new_password != confirm_password:

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error":
                    "New passwords do not match.",
                "message": None,
            },
            status_code=400,
        )


    # --------------------------------------------------------
    # Find admin account
    # --------------------------------------------------------

    try:

        admin_user = crud.get_admin_by_username(
            db,
            username,
        )

    except SQLAlchemyError as exc:

        logger.error(
            "Forgot password database lookup failed: %s",
            exc,
        )

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error":
                    "Database connection failed.",
                "message": None,
            },
            status_code=500,
        )


    if admin_user is None:

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error":
                    "Admin account was not found.",
                "message": None,
            },
            status_code=404,
        )


    # --------------------------------------------------------
    # Change password
    #
    # IMPORTANT:
    # We use the exact same hash_password()
    # function already present in your original crud.py.
    # --------------------------------------------------------

    try:

        admin_user.password = crud.hash_password(
            new_password
        )

        db.commit()

    except SQLAlchemyError as exc:

        db.rollback()

        logger.error(
            "Password reset failed: %s",
            exc,
        )

        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "forgot_password": True,
                "reset_question": RESET_QUESTION,
                "error":
                    "Could not reset password.",
                "message": None,
            },
            status_code=500,
        )


    # --------------------------------------------------------
    # Password successfully changed
    # --------------------------------------------------------

    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {
            "forgot_password": False,
            "reset_question": RESET_QUESTION,
            "error": None,
            "message":
                "Password reset successfully. "
                "You can now login with your new password.",
        },
    )


# ============================================================
# LOGOUT
# ============================================================

@router.get(
    "/logout",
    response_model=None,
)
def admin_logout() -> RedirectResponse:

    response = RedirectResponse(
        url="/admin/login?message=Logged out",
        status_code=303,
    )

    response.delete_cookie(
        auth.ADMIN_COOKIE_NAME
    )

    return response


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@router.get(
    "",
    response_class=HTMLResponse,
    response_model=None,
)
def admin_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:

    if not auth.is_admin_request(request):
        return _admin_login_redirect()

    try:

        vehicles = crud.get_vehicles(db)
        owners = crud.get_owners(db)

    except SQLAlchemyError as exc:

        logger.error(
            "Admin page database load failed: %s",
            exc,
        )

        vehicles = []
        owners = []

        error = (
            "Database connection failed. "
            "Please check your setup."
        )

    else:

        error = None

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "vehicles": vehicles,
            "owners": owners,
            "error": error,
        },
    )


# ============================================================
# LIST VEHICLES API
# ============================================================

@router.get(
    "/vehicles",
    response_model=list[schemas.VehicleRead],
)
def list_vehicles(
    request: Request,
    db: Session = Depends(get_db),
) -> list[schemas.VehicleRead]:

    _require_admin_api(request)

    return crud.get_vehicles(db)


# ============================================================
# ADD VEHICLE API
# ============================================================

@router.post(
    "/vehicles",
    response_model=schemas.VehicleRead,
    status_code=201,
)
def add_vehicle(
    vehicle: schemas.VehicleCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> object:

    _require_admin_api(request)

    if not is_valid_registration_number(
        vehicle.registration_number
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Please enter a valid "
                "registration number."
            ),
        )

    try:

        return crud.create_vehicle(
            db,
            vehicle,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError as exc:

        logger.error(
            "Create vehicle API failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Database operation failed.",
        ) from exc


# ============================================================
# UPDATE VEHICLE API
# ============================================================

@router.put(
    "/vehicles/{vehicle_id}",
    response_model=schemas.VehicleRead,
)
def edit_vehicle(
    vehicle_id: int,
    vehicle: schemas.VehicleUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> object:

    _require_admin_api(request)

    if not is_valid_registration_number(
        vehicle.registration_number
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Please enter a valid "
                "registration number."
            ),
        )

    try:

        updated_vehicle = crud.update_vehicle(
            db,
            vehicle_id,
            vehicle,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError as exc:

        logger.error(
            "Update vehicle API failed for id %s: %s",
            vehicle_id,
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Database operation failed.",
        ) from exc

    if updated_vehicle is None:

        raise HTTPException(
            status_code=404,
            detail="Vehicle not found.",
        )

    return updated_vehicle


# ============================================================
# DELETE VEHICLE API
# ============================================================

@router.delete(
    "/vehicles/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_vehicle(
    vehicle_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> None:

    _require_admin_api(request)

    try:

        deleted = crud.delete_vehicle(
            db,
            vehicle_id,
        )

    except SQLAlchemyError as exc:

        logger.error(
            "Delete vehicle API failed for id %s: %s",
            vehicle_id,
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Database operation failed.",
        ) from exc

    if not deleted:

        raise HTTPException(
            status_code=404,
            detail="Vehicle not found.")


# ============================================================
# ADD VEHICLE FROM HTML FORM
# ============================================================

@router.post(
    "/vehicles/form",
    response_model=None,
)
async def add_vehicle_from_form(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse | HTMLResponse:

    if not auth.is_admin_request(request):
        return _admin_login_redirect()

    form = await request.form()

    try:

        vehicle = _vehicle_schema_from_form(
            dict(form), db
        )

        crud.create_vehicle(
            db,
            vehicle,
        )

    except (
        ValueError,
        ValidationError,
    ) as exc:

        return _admin_error_response(
            request,
            db,
            str(exc),
        )

    except SQLAlchemyError as exc:

        logger.error(
            "Create vehicle form failed: %s",
            exc,
        )

        return _admin_error_response(
            request,
            db,
            "Database operation failed.",
        )

    return RedirectResponse(
        url="/admin?message=Vehicle added",
        status_code=303,
    )


# ============================================================
# EDIT VEHICLE FROM HTML FORM
# ============================================================

@router.post(
    "/vehicles/{vehicle_id}/edit",
    response_model=None,
)
async def edit_vehicle_from_form(
    vehicle_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse | HTMLResponse:

    if not auth.is_admin_request(request):
        return _admin_login_redirect()

    form = await request.form()

    try:

        form_vehicle = _vehicle_schema_from_form(
            dict(form), db
        )

        vehicle = schemas.VehicleUpdate(
            **form_vehicle.model_dump()
        )

        updated_vehicle = crud.update_vehicle(
            db,
            vehicle_id,
            vehicle,
        )

    except (
        ValueError,
        ValidationError,
    ) as exc:

        return _admin_error_response(
            request,
            db,
            str(exc),
        )

    except SQLAlchemyError as exc:

        logger.error(
            "Update vehicle form failed for id %s: %s",
            vehicle_id,
            exc,
        )

        return _admin_error_response(
            request,
            db,
            "Database operation failed.",
        )

    if updated_vehicle is None:

        return _admin_error_response(
            request,
            db,
            "Vehicle not found.",
        )

    return RedirectResponse(
        url="/admin?message=Vehicle updated",
        status_code=303,
    )


# ============================================================
# DELETE VEHICLE FROM HTML FORM
# ============================================================

@router.post(
    "/vehicles/{vehicle_id}/delete",
    response_model=None,
)
def delete_vehicle_from_form(
    vehicle_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:

    if not auth.is_admin_request(request):
        return _admin_login_redirect()

    try:

        deleted = crud.delete_vehicle(
            db,
            vehicle_id,
        )

    except SQLAlchemyError as exc:

        logger.error(
            "Delete vehicle form failed for id %s: %s",
            vehicle_id,
            exc,
        )

        return RedirectResponse(
            url="/admin?error=Database operation failed",
            status_code=303,
        )

    if not deleted:

        return RedirectResponse(
            url="/admin?error=Vehicle not found",
            status_code=303,
        )

    return RedirectResponse(
        url="/admin?message=Vehicle deleted",
        status_code=303,
    )


# ============================================================
# ADMIN ERROR RESPONSE
# ============================================================

def _admin_error_response(
    request: Request,
    db: Session,
    error: str,
) -> HTMLResponse:

    try:

        vehicles = crud.get_vehicles(db)
        owners = crud.get_owners(db)

    except SQLAlchemyError as exc:

        logger.error(
            "Admin error response load failed: %s",
            exc,
        )

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