from fastapi import APIRouter, Depends, HTTPException

from app.core.academic_catalog import get_career_profile
from app.core.auth import get_current_user
from app.database.supabase_repository import SupabaseRepositoryError, supabase_repository
from app.models.schemas import AuthRequest, AuthResponse, RegisterRequest, UserPublic
from app.services.supabase_auth_service import AuthServiceError, supabase_auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


def _build_auth_response(payload: dict, fallback_message: str | None = None) -> AuthResponse:
    session = payload.get("session") or payload
    user_payload = payload.get("user") or session.get("user")

    user = None
    if user_payload and user_payload.get("id"):
        user = UserPublic(
            id=user_payload["id"],
            email=user_payload.get("email"),
        )

    return AuthResponse(
        access_token=session.get("access_token"),
        refresh_token=session.get("refresh_token"),
        expires_in=session.get("expires_in"),
        token_type=session.get("token_type") or "bearer",
        user=user,
        message=fallback_message,
    )


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest) -> AuthResponse:
    if not get_career_profile(payload.faculty_id, payload.career_id):
        raise HTTPException(
            status_code=400,
            detail="Selecciona una facultad y carrera validas para crear la cuenta.",
        )

    try:
        response = await supabase_auth_service.register(payload.email, payload.password)
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error

    auth_response = _build_auth_response(response)
    if not auth_response.access_token:
        raise HTTPException(
            status_code=502,
            detail="La cuenta fue creada, pero no se pudo iniciar sesion automaticamente.",
        )

    if auth_response.user:
        try:
            supabase_repository.upsert_user_academic_profile(
                user_id=auth_response.user.id,
                faculty_id=payload.faculty_id,
                career_id=payload.career_id,
            )
        except SupabaseRepositoryError as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    return auth_response


@router.post("/login", response_model=AuthResponse)
async def login(payload: AuthRequest) -> AuthResponse:
    try:
        response = await supabase_auth_service.login(payload.email, payload.password)
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error

    return _build_auth_response(response)


@router.get("/me", response_model=UserPublic)
async def me(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    return current_user
