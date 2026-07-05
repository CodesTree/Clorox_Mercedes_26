from __future__ import annotations

from sqlalchemy.orm import Session

from app import orm
from app.schemas import VehicleProfileIn, VehicleProfileOut


class ProfileNotFound(RuntimeError):
    pass


DEFAULT_PROFILE = {
    "name": "Demo Mercedes SL-Class",
    "model": "SL CLASS",
    "year": 2016,
    "mileage": 42000,
    "transmission": "Automatic",
    "fuel_type": "Petrol",
    "engine_size": 5.5,
    "service_history_count": 6,
    "service_history_total": 7,
    "service_history_max": 7,
    "workshop": "Hap Seng Star KL",
    "glb_asset": "/models/amg-gt.glb",
}


def ensure_default_profile(session: Session) -> orm.VehicleProfile:
    profile = session.query(orm.VehicleProfile).order_by(orm.VehicleProfile.id).first()
    if profile is not None:
        return profile

    profile = orm.VehicleProfile(**DEFAULT_PROFILE)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def get_profile(session: Session, profile_id: int) -> orm.VehicleProfile:
    ensure_default_profile(session)
    profile = session.get(orm.VehicleProfile, profile_id)
    if profile is None:
        raise ProfileNotFound(f"vehicle profile {profile_id} not found")
    return profile


def update_default_profile(session: Session, data: VehicleProfileIn) -> orm.VehicleProfile:
    profile = ensure_default_profile(session)
    profile.model = data.model
    profile.year = data.year
    profile.mileage = data.mileage
    profile.transmission = data.transmission
    profile.fuel_type = data.fuel_type
    profile.engine_size = data.engine_size
    if data.service_history_count is not None:
        profile.service_history_count = data.service_history_count
    if data.service_history_total is not None:
        profile.service_history_total = data.service_history_total
        profile.service_history_max = data.service_history_total
    session.commit()
    session.refresh(profile)
    return profile


def to_schema(profile: orm.VehicleProfile) -> VehicleProfileOut:
    return VehicleProfileOut.model_validate(profile)
