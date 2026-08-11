"""Small database helper functions used by the routers."""

import hashlib
import secrets

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.utils.logger.central_logger import logger


def normalize_registration_number(registration_number: str) -> str:
    """Convert user input to a consistent registration format."""
    return registration_number.strip().upper()


def normalize_owner_name(owner_name: str) -> str:
    """Clean and normalize an owner name."""
    return " ".join(owner_name.strip().split())


def hash_password(password: str) -> str:
    """Hash a password with a random salt."""
    salt = secrets.token_hex(16)

    password_hash = hashlib.sha256(
        f"{salt}{password}".encode("utf-8")
    ).hexdigest()

    return f"{salt}${password_hash}"


# ============================================================
# VEHICLE FUNCTIONS
# ============================================================

def get_vehicle_by_registration(
    db: Session,
    registration_number: str,
) -> models.Vehicle | None:

    clean_number = normalize_registration_number(
        registration_number
    )

    return (
        db.query(models.Vehicle)
        .options(joinedload(models.Vehicle.owner))
        .filter(
            models.Vehicle.registration_number == clean_number
        )
        .first()
    )


def get_vehicle(
    db: Session,
    vehicle_id: int,
) -> models.Vehicle | None:

    return (
        db.query(models.Vehicle)
        .options(joinedload(models.Vehicle.owner))
        .filter(
            models.Vehicle.vehicle_id == vehicle_id
        )
        .first()
    )


def get_vehicles(
    db: Session,
) -> list[models.Vehicle]:

    return (
        db.query(models.Vehicle)
        .options(joinedload(models.Vehicle.owner))
        .order_by(models.Vehicle.vehicle_id)
        .all()
    )


# ============================================================
# OWNER FUNCTIONS
# ============================================================

def get_owners(
    db: Session,
) -> list[models.Owner]:

    return (
        db.query(models.Owner)
        .order_by(models.Owner.full_name)
        .all()
    )


def get_owner_by_name(
    db: Session,
    owner_name: str,
) -> models.Owner | None:

    clean_name = normalize_owner_name(owner_name)

    if not clean_name:
        return None

    return (
        db.query(models.Owner)
        .filter(
            func.lower(models.Owner.full_name)
            == clean_name.lower()
        )
        .first()
    )


def get_or_create_owner(
    db: Session,
    owner_name: str,
    phone: str = "N/A",
    address: str = "N/A",
) -> models.Owner:

    clean_name = normalize_owner_name(owner_name)

    if not clean_name:
        raise ValueError(
            "Owner name is required."
        )

    # Check whether the owner already exists.
    existing_owner = get_owner_by_name(
        db,
        clean_name,
    )

    if existing_owner:
        return existing_owner

    # Create new owner.
    new_owner = models.Owner(
        full_name=clean_name,
        phone=phone.strip() if phone else "N/A",
        address=address.strip() if address else "N/A",
    )

    db.add(new_owner)
    db.flush()

    logger.info(
        "Created new owner: %s",
        clean_name,
    )

    return new_owner


# ============================================================
# ADMIN FUNCTIONS
# ============================================================

def get_admin_by_username(
    db: Session,
    username: str,
) -> models.Admin | None:

    return (
        db.query(models.Admin)
        .filter(
            models.Admin.username == username
        )
        .first()
    )


def update_admin_password(
    db: Session,
    username: str,
    new_password: str,
) -> bool:

    admin = get_admin_by_username(
        db,
        username,
    )

    if admin is None:
        return False

    admin.password = hash_password(
        new_password
    )

    db.commit()

    return True


# ============================================================
# CREATE VEHICLE
# ============================================================

def create_vehicle(
    db: Session,
    vehicle: schemas.VehicleCreate,
) -> models.Vehicle:

    new_vehicle = models.Vehicle(
        registration_number=normalize_registration_number(
            vehicle.registration_number
        ),
        vehicle_name=vehicle.vehicle_name.strip(),
        model=vehicle.model.strip(),
        registered_year=vehicle.registered_year,
        color=vehicle.color.strip(),
        owner_id=vehicle.owner_id,
    )

    db.add(new_vehicle)

    try:

        db.commit()

    except IntegrityError as exc:

        db.rollback()

        logger.warning(
            "Could not create vehicle: %s",
            exc,
        )

        raise ValueError(
            "Registration number already exists "
            "or owner is invalid."
        ) from exc

    db.refresh(new_vehicle)

    return new_vehicle


# ============================================================
# UPDATE VEHICLE
# ============================================================

def update_vehicle(
    db: Session,
    vehicle_id: int,
    vehicle: schemas.VehicleUpdate,
) -> models.Vehicle | None:

    existing_vehicle = get_vehicle(
        db,
        vehicle_id,
    )

    if existing_vehicle is None:
        return None

    existing_vehicle.registration_number = (
        normalize_registration_number(
            vehicle.registration_number
        )
    )

    existing_vehicle.vehicle_name = (
        vehicle.vehicle_name.strip()
    )

    existing_vehicle.model = (
        vehicle.model.strip()
    )

    existing_vehicle.registered_year = (
        vehicle.registered_year
    )

    existing_vehicle.color = (
        vehicle.color.strip()
    )

    existing_vehicle.owner_id = (
        vehicle.owner_id
    )

    try:

        db.commit()

    except IntegrityError as exc:

        db.rollback()

        logger.warning(
            "Could not update vehicle: %s",
            exc,
        )

        raise ValueError(
            "Registration number already exists "
            "or owner is invalid."
        ) from exc

    db.refresh(existing_vehicle)

    return existing_vehicle


# ============================================================
# DELETE VEHICLE
# ============================================================

def delete_vehicle(
    db: Session,
    vehicle_id: int,
) -> bool:

    vehicle = get_vehicle(
        db,
        vehicle_id,
    )

    if vehicle is None:
        return False

    db.delete(vehicle)
    db.commit()

    return True


# ============================================================
# SAMPLE DATA
# ============================================================

def seed_sample_data(
    db: Session,
) -> None:
    """Add sample data only when the database is empty."""

    if db.query(models.Owner).first() is not None:
        return

    owner_one = models.Owner(
        full_name="Sushank Karki",
        phone="9812345678",
        address="Kathmandu",
    )

    owner_two = models.Owner(
        full_name="Ram Sharma",
        phone="9801111111",
        address="Pokhara",
    )

    db.add_all(
        [
            owner_one,
            owner_two,
        ]
    )

    db.flush()

    db.add_all(
        [
            models.Vehicle(
                registration_number="BA2PA1234",
                vehicle_name="Hayabusa",
                model="2026",
                registered_year=2021,
                color="Black",
                owner_id=owner_one.owner_id,
            ),

            models.Vehicle(
                registration_number="BA1CHA5678",
                vehicle_name="Royal Enfield Hunter 350",
                model="2024",
                registered_year=2023,
                color="Red",
                owner_id=owner_two.owner_id,
            ),
        ]
    )

    db.add(
        models.Admin(
            username="admin",
            password=hash_password(
                "admin123"
            ),
        )
    )

    db.commit()