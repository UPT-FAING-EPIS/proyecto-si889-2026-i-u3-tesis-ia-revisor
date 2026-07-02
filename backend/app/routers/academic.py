from fastapi import APIRouter, Depends, HTTPException

from app.core.academic_catalog import (
    build_academic_profile,
    get_career_profile,
    list_academic_catalog,
)
from app.core.auth import get_current_user
from app.database.supabase_repository import SupabaseRepositoryError, supabase_repository
from app.models.schemas import (
    AcademicFacultySummary,
    AcademicProfile,
    AcademicProfileRequest,
    AcademicProfileStatus,
    UserPublic,
)


router = APIRouter(prefix="/academic", tags=["academic"])


def _profile_response(row: dict | None) -> AcademicProfile | None:
    if not row:
        return None

    profile = build_academic_profile(
        faculty_id=row.get("faculty_id"),
        career_id=row.get("career_id"),
        user_id=row.get("user_id"),
    )
    if not profile:
        return None

    profile["career_id"] = profile.pop("id")
    profile["career_name"] = profile.pop("name")
    profile["created_at"] = row.get("created_at")
    profile["updated_at"] = row.get("updated_at")
    return AcademicProfile(**profile)


@router.get("/catalog", response_model=list[AcademicFacultySummary])
async def catalog() -> list[AcademicFacultySummary]:
    return [AcademicFacultySummary(**faculty) for faculty in list_academic_catalog()]


@router.get("/profile", response_model=AcademicProfileStatus)
async def get_profile(
    current_user: UserPublic = Depends(get_current_user),
) -> AcademicProfileStatus:
    try:
        row = supabase_repository.get_user_academic_profile(current_user.id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    profile = _profile_response(row)
    return AcademicProfileStatus(
        profile=profile,
        requires_selection=profile is None,
    )


@router.put("/profile", response_model=AcademicProfile)
async def save_profile(
    payload: AcademicProfileRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> AcademicProfile:
    if not get_career_profile(payload.faculty_id, payload.career_id):
        raise HTTPException(
            status_code=400,
            detail="Selecciona una facultad y carrera validas para plan de tesis.",
        )

    try:
        row = supabase_repository.upsert_user_academic_profile(
            user_id=current_user.id,
            faculty_id=payload.faculty_id,
            career_id=payload.career_id,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    profile = _profile_response(row)
    if not profile:
        raise HTTPException(status_code=500, detail="No se pudo resolver el perfil academico guardado.")

    return profile
