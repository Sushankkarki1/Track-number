"""SQLAlchemy database models."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Owner(Base):
    """Vehicle owner table."""

    __tablename__ = "owners"

    owner_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    address = Column(String(150), nullable=False)

    vehicles = relationship("Vehicle", back_populates="owner")


class Vehicle(Base):
    """Vehicle table."""

    __tablename__ = "vehicles"

    vehicle_id = Column(Integer, primary_key=True, index=True)
    registration_number = Column(String(30), nullable=False, unique=True, index=True)
    vehicle_name = Column(String(100), nullable=False)
    model = Column(String(30), nullable=False)
    registered_year = Column(Integer, nullable=False)
    color = Column(String(50), nullable=False)
    owner_id = Column(Integer, ForeignKey("owners.owner_id"), nullable=False)

    owner = relationship("Owner", back_populates="vehicles")


class Admin(Base):
    """Simple admin table."""

    __tablename__ = "admins"

    admin_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password = Column(String(150), nullable=False)
