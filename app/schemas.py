"""Pydantic schemas for request and response validation."""

from pydantic import BaseModel, Field


class OwnerCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=7, max_length=20)
    address: str = Field(..., min_length=2, max_length=150)


class OwnerRead(OwnerCreate):
    owner_id: int

    model_config = {"from_attributes": True}


class VehicleBase(BaseModel):
    registration_number: str = Field(..., min_length=5, max_length=30)
    vehicle_name: str = Field(..., min_length=2, max_length=100)
    model: str = Field(..., min_length=1, max_length=30)
    registered_year: int = Field(..., ge=1900, le=2100)
    color: str = Field(..., min_length=2, max_length=50)
    owner_id: int = Field(..., gt=0)


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(VehicleBase):
    pass


class VehicleRead(VehicleBase):
    vehicle_id: int
    owner: OwnerRead

    model_config = {"from_attributes": True}


class VehicleSearchResult(BaseModel):
    registration_number: str
    vehicle_name: str
    model: str
    owner_name: str
    registered_year: int
    color: str
