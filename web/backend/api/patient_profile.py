from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.database.models import PatientProfile, User
from web.backend.models.patient_profile import (
    ModuleDefaults,
    PatientProfileCreate,
    PatientProfileResponse,
    PatientProfileUpdate,
)
from web.backend.services.auth import get_current_user

router = APIRouter()

ALLOWED_RELATIONSHIPS = {"本人", "父母", "孩子", "伴侣", "朋友", "其他"}


def _normalize_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_relationship(relationship: str) -> str:
    normalized = relationship.strip()
    if normalized not in ALLOWED_RELATIONSHIPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="relationship 必须是 本人/父母/孩子/伴侣/朋友/其他 之一",
        )
    return normalized


def _validate_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name 不能为空",
        )
    return normalized


def _ensure_single_self_profile(
    db: Session, user_id: int, excluded_profile_id: Optional[int] = None
) -> None:
    query = db.query(PatientProfile).filter(
        PatientProfile.user_id == user_id,
        PatientProfile.relationship == "本人",
    )
    if excluded_profile_id is not None:
        query = query.filter(PatientProfile.id != excluded_profile_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="每个用户只能有一个“本人”档案",
        )


def _build_module_defaults_response(current_user: User) -> ModuleDefaults:
    return ModuleDefaults(
        tracker_profile_id=cast(
            Optional[int], cast(object, current_user.default_tracker_profile_id)
        ),
        report_profile_id=cast(
            Optional[int], cast(object, current_user.default_report_profile_id)
        ),
        diary_profile_id=cast(
            Optional[int], cast(object, current_user.default_diary_profile_id)
        ),
    )


def _auto_create_self_profile(db: Session, current_user: User) -> PatientProfile:
    profile = PatientProfile(
        user_id=cast(int, cast(object, current_user.id)),
        name=cast(str, cast(object, current_user.username)),
        relationship="本人",
        is_self=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _get_owned_profile(db: Session, profile_id: int, user_id: int) -> PatientProfile:
    profile = (
        db.query(PatientProfile)
        .filter(PatientProfile.id == profile_id, PatientProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="档案不存在")
    return cast(PatientProfile, profile)


@router.get("/patient-profiles/", response_model=list[PatientProfileResponse])
async def list_patient_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profiles = (
        db.query(PatientProfile)
        .filter(PatientProfile.user_id == cast(int, cast(object, current_user.id)))
        .order_by(PatientProfile.created_at.asc(), PatientProfile.id.asc())
        .all()
    )
    if not profiles:
        profiles = [_auto_create_self_profile(db, current_user)]
    return profiles


@router.post("/patient-profiles/", response_model=PatientProfileResponse)
async def create_patient_profile(
    payload: PatientProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    relationship = _validate_relationship(payload.relationship)
    if relationship == "本人":
        _ensure_single_self_profile(db, cast(int, cast(object, current_user.id)))

    profile = PatientProfile(
        user_id=cast(int, cast(object, current_user.id)),
        name=_validate_name(payload.name),
        relationship=relationship,
        gender=_normalize_optional_string(payload.gender),
        birth_date=payload.birth_date,
        diagnosis_date=payload.diagnosis_date,
        vitiligo_type=_normalize_optional_string(payload.vitiligo_type),
        notes=_normalize_optional_string(payload.notes),
        is_self=relationship == "本人",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/patient-profiles/{profile_id}", response_model=PatientProfileResponse)
async def update_patient_profile(
    profile_id: int,
    payload: PatientProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = _get_owned_profile(
        db, profile_id, cast(int, cast(object, current_user.id))
    )
    updates = cast(dict[str, Any], payload.model_dump(exclude_unset=True))

    if "relationship" in updates:
        new_relationship_raw = cast(Optional[str], updates["relationship"])
        if new_relationship_raw is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="relationship 不能为空",
            )
        new_relationship = _validate_relationship(new_relationship_raw)
        if cast(bool, cast(object, profile.is_self)) and new_relationship != "本人":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="本人档案不能修改为其他关系",
            )
        if new_relationship == "本人":
            _ensure_single_self_profile(
                db,
                cast(int, cast(object, current_user.id)),
                excluded_profile_id=cast(int, cast(object, profile.id)),
            )
        setattr(profile, "relationship", new_relationship)
        setattr(profile, "is_self", new_relationship == "本人")

    if "name" in updates and updates["name"] is not None:
        setattr(profile, "name", _validate_name(cast(str, updates["name"])))

    if "gender" in updates:
        setattr(
            profile,
            "gender",
            _normalize_optional_string(cast(Optional[str], updates["gender"])),
        )

    if "birth_date" in updates:
        setattr(profile, "birth_date", updates["birth_date"])

    if "diagnosis_date" in updates:
        setattr(profile, "diagnosis_date", updates["diagnosis_date"])

    if "vitiligo_type" in updates:
        setattr(
            profile,
            "vitiligo_type",
            _normalize_optional_string(cast(Optional[str], updates["vitiligo_type"])),
        )

    if "notes" in updates:
        setattr(
            profile,
            "notes",
            _normalize_optional_string(cast(Optional[str], updates["notes"])),
        )

    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/patient-profiles/{profile_id}")
async def delete_patient_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = _get_owned_profile(
        db, profile_id, cast(int, cast(object, current_user.id))
    )
    if (
        cast(bool, cast(object, profile.is_self))
        or cast(str, cast(object, profile.relationship)) == "本人"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="本人档案不可删除",
        )

    profile_db_id = cast(int, cast(object, profile.id))
    if (
        cast(Optional[int], cast(object, current_user.default_tracker_profile_id))
        == profile_db_id
    ):
        setattr(current_user, "default_tracker_profile_id", None)
    if (
        cast(Optional[int], cast(object, current_user.default_report_profile_id))
        == profile_db_id
    ):
        setattr(current_user, "default_report_profile_id", None)
    if (
        cast(Optional[int], cast(object, current_user.default_diary_profile_id))
        == profile_db_id
    ):
        setattr(current_user, "default_diary_profile_id", None)

    db.delete(profile)
    db.commit()
    return {"detail": "删除成功"}


@router.get("/user/module-defaults", response_model=ModuleDefaults)
async def get_module_defaults(current_user: User = Depends(get_current_user)):
    return _build_module_defaults_response(current_user)


@router.put("/user/module-defaults", response_model=ModuleDefaults)
async def update_module_defaults(
    payload: ModuleDefaults,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updates = payload.model_dump()
    requested_ids = {
        profile_id for profile_id in updates.values() if profile_id is not None
    }

    if requested_ids:
        owned_ids = {
            cast(int, cast(object, profile.id))
            for profile in cast(
                list[PatientProfile],
                db.query(PatientProfile)
                .filter(
                    PatientProfile.user_id == cast(int, cast(object, current_user.id)),
                    PatientProfile.id.in_(requested_ids),
                )
                .all(),
            )
        }
        missing_ids = requested_ids - owned_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="默认档案必须属于当前用户",
            )

    setattr(current_user, "default_tracker_profile_id", updates["tracker_profile_id"])
    setattr(current_user, "default_report_profile_id", updates["report_profile_id"])
    setattr(current_user, "default_diary_profile_id", updates["diary_profile_id"])
    db.commit()
    db.refresh(current_user)

    return _build_module_defaults_response(current_user)
