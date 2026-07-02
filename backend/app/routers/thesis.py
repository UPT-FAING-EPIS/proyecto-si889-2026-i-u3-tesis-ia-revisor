from datetime import UTC, datetime
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from app.core.academic_catalog import get_career_profile
from app.core.auth import get_current_user
from app.database.supabase_repository import SupabaseRepositoryError, supabase_repository
from app.models.schemas import (
    ChatSessionMode,
    ThesisAutoJobRequest,
    ThesisAutoJobSummary,
    ThesisCompleteSectionRequest,
    ThesisCompleteSectionResponse,
    ThesisFromPlanRequest,
    ThesisFromPlanResponse,
    UserPublic,
)
from app.routers.thesis_plan import _select_pdf_plan_text
from app.services.gemini_service import (
    THESIS_COMPLETE_STAGE_PREFIX,
    GeminiServiceError,
    gemini_service,
)
from app.services.thesis_plan_pdf_service import thesis_plan_pdf_service


router = APIRouter(tags=["thesis"])
LOGGER = logging.getLogger(__name__)


def _serialize_history(rows: list[dict], limit: int = 30) -> list[dict]:
    history_rows = rows[-limit:]
    return [
        {
            "role": row.get("role") or "user",
            "content": row.get("content") or "",
        }
        for row in history_rows
    ]


def _validate_source_plan_session(chat_id: str, current_user: UserPublic) -> dict:
    try:
        chat_session = supabase_repository.get_chat_session_by_id(chat_id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    if not chat_session or chat_session.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Plan de tesis fuente no encontrado.")

    if chat_session.get("mode") != ChatSessionMode.THESIS_PLAN.value:
        raise HTTPException(
            status_code=400,
            detail="La sesion seleccionada no corresponde a un plan de tesis.",
        )

    return chat_session


def _validate_thesis_session(chat_id: str, current_user: UserPublic) -> dict:
    try:
        chat_session = supabase_repository.get_chat_session_by_id(chat_id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    if not chat_session or chat_session.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Tesis no encontrada.")

    if chat_session.get("mode") != ChatSessionMode.THESIS.value:
        raise HTTPException(
            status_code=400,
            detail="La sesion no corresponde al modo de tesis.",
        )

    return chat_session


def _resolve_session_academic_profile(chat_session: dict, current_user: UserPublic) -> dict:
    profile = get_career_profile(chat_session.get("faculty_id"), chat_session.get("career_id"))
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="La sesion no tiene una facultad y carrera validas.",
        )

    profile["user_id"] = current_user.id
    return profile


def _read_source_plan_text(source_plan_chat_id: str) -> str:
    try:
        source_messages = supabase_repository.list_chat_messages(source_plan_chat_id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    plan_text = _select_pdf_plan_text(source_messages)
    if not plan_text:
        raise HTTPException(
            status_code=400,
            detail="El plan seleccionado aun no tiene contenido suficiente para generar una tesis.",
        )
    return plan_text


def _format_thesis_stage_message(
    content: str,
    section_index: int,
    total_sections: int,
    section_title: str,
) -> str:
    return (
        f"{THESIS_COMPLETE_STAGE_PREFIX} {section_index}/{total_sections} - {section_title}\n\n"
        f"{(content or '').strip()}"
    ).strip()


def _strip_thesis_stage_marker(content: str) -> str:
    lines = (content or "").splitlines()
    if lines and lines[0].startswith(THESIS_COMPLETE_STAGE_PREFIX):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines).strip()


def _select_pdf_thesis_text(messages: list[dict]) -> str:
    last_complete_start_index = -1
    for index, row in enumerate(messages):
        content = (row.get("content") or "").strip()
        if (
            row.get("role") == "assistant"
            and content.startswith(THESIS_COMPLETE_STAGE_PREFIX)
            and "ETAPA 1/" in content.splitlines()[0]
        ):
            last_complete_start_index = index

    if last_complete_start_index >= 0:
        complete_sections = [
            _strip_thesis_stage_marker(row.get("content") or "")
            for row in messages[last_complete_start_index:]
            if row.get("role") == "assistant"
            and (row.get("content") or "").strip().startswith(THESIS_COMPLETE_STAGE_PREFIX)
        ]
        complete_sections = [section for section in complete_sections if section]
        if complete_sections:
            return "\n\n".join(complete_sections).strip()

    assistant_messages = [
        row for row in messages
        if row.get("role") == "assistant" and (row.get("content") or "").strip()
    ]
    if not assistant_messages:
        return ""
    return assistant_messages[-1].get("content") or ""


def _store_thesis_pdf(
    *,
    user_id: str,
    chat_id: str,
    filename: str,
    pdf_content: bytes,
    job_id: str | None = None,
) -> str:
    try:
        storage_path = supabase_repository.upload_thesis_pdf(
            user_id=user_id,
            chat_session_id=chat_id,
            filename=filename,
            file_bytes=pdf_content,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    try:
        if job_id:
            supabase_repository.update_thesis_auto_job_pdf_metadata(
                job_id=job_id,
                pdf_storage_path=storage_path,
                pdf_filename=filename,
                pdf_size_bytes=len(pdf_content),
            )
    except SupabaseRepositoryError:
        LOGGER.exception(
            "El PDF de tesis se subio a Storage, pero no se pudieron guardar metadatos del job."
        )

    return storage_path


def _build_thesis_title(source_plan: dict, requested_title: str | None = None) -> str:
    clean_requested = " ".join((requested_title or "").split())
    if clean_requested:
        return clean_requested[:120]

    source_title = " ".join((source_plan.get("title") or "Plan de tesis").split())
    if source_title.lower().startswith("tesis -"):
        return source_title[:120]
    return f"Tesis - {source_title}"[:120]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _serialize_auto_thesis_job(row: dict) -> ThesisAutoJobSummary:
    provider = row.get("ai_provider")
    if provider not in {"gemini", "deepseek"}:
        provider = None

    selected_payload = row.get("selected_problem")
    if not isinstance(selected_payload, dict):
        selected_payload = {}

    return ThesisAutoJobSummary(
        id=str(row.get("id")),
        chat_id=row.get("chat_session_id"),
        source_plan_chat_id=selected_payload.get("source_plan_chat_id"),
        source_plan_title=selected_payload.get("source_plan_title"),
        status=row.get("status") or "pending",
        progress_percent=int(row.get("progress_percent") or 0),
        progress_label=row.get("progress_label"),
        error_message=row.get("error_message"),
        ai_provider=provider,
        ai_model=row.get("ai_model"),
        faculty_id=row.get("faculty_id"),
        career_id=row.get("career_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        notified_at=row.get("notified_at"),
        pdf_storage_path=row.get("pdf_storage_path"),
        pdf_filename=row.get("pdf_filename"),
        pdf_size_bytes=row.get("pdf_size_bytes"),
        pdf_mime_type=row.get("pdf_mime_type"),
        pdf_generated_at=row.get("pdf_generated_at"),
    )


def _generate_automatic_thesis_sections(
    *,
    job_id: str,
    chat_id: str,
    source_plan_chat_id: str,
    formal_data: dict[str, str],
    ai_provider: str,
    ai_model: str | None,
    academic_profile: dict | None,
) -> None:
    plan_text = _read_source_plan_text(source_plan_chat_id)

    try:
        persisted_messages = supabase_repository.list_chat_messages(chat_id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    history = _serialize_history(persisted_messages, limit=40)
    sections = gemini_service.thesis_complete_sections()
    total_sections = len(sections)

    for section in sections:
        section_id = str(section["id"])
        section_title_for_progress = str(section["title"])
        section_index_for_progress = int(section["index"])

        supabase_repository.update_thesis_auto_job(
            job_id,
            status="running",
            found_sources=max(section_index_for_progress - 1, 0),
            progress_percent=round(((section_index_for_progress - 1) / total_sections) * 95),
            progress_label=f"Generando {section_title_for_progress}",
        )

        try:
            section_text, section_index, section_title, total = (
                gemini_service.generate_thesis_complete_section(
                    source_plan_text=plan_text,
                    thesis_history=history,
                    section_id=section_id,
                    formal_data=formal_data,
                    ai_provider=ai_provider,
                    ai_model=ai_model,
                    academic_profile=academic_profile,
                )
            )
        except GeminiServiceError as error:
            raise HTTPException(status_code=500, detail=error.message) from error

        response_text = _format_thesis_stage_message(
            content=section_text,
            section_index=section_index,
            total_sections=total,
            section_title=section_title,
        )

        try:
            supabase_repository.create_chat_message(
                chat_session_id=chat_id,
                role="assistant",
                content=response_text,
            )
        except SupabaseRepositoryError as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

        history.append({"role": "assistant", "content": response_text})
        supabase_repository.update_thesis_auto_job(
            job_id,
            status="running",
            found_sources=section_index,
            progress_percent=round((section_index / total_sections) * 95),
            progress_label=f"Completado {section_title}",
        )


def _run_automatic_thesis_job(
    *,
    job_id: str,
    chat_id: str,
    source_plan_chat_id: str,
    user_id: str,
    user_email: str | None,
    formal_data: dict[str, str],
    ai_provider: str,
    ai_model: str | None,
    academic_profile: dict | None,
) -> None:
    try:
        supabase_repository.update_thesis_auto_job(
            job_id,
            status="running",
            progress_percent=2,
            progress_label="Preparando generacion de la tesis",
            started_at=_utc_now_iso(),
        )

        _generate_automatic_thesis_sections(
            job_id=job_id,
            chat_id=chat_id,
            source_plan_chat_id=source_plan_chat_id,
            formal_data=formal_data,
            ai_provider=ai_provider,
            ai_model=ai_model,
            academic_profile=academic_profile,
        )

        supabase_repository.update_thesis_auto_job(
            job_id,
            status="running",
            progress_percent=96,
            progress_label="Preparando PDF de la tesis",
        )

        persisted_messages = supabase_repository.list_chat_messages(chat_id)
        thesis_text = _select_pdf_thesis_text(persisted_messages)
        if not thesis_text:
            raise RuntimeError("No se pudo consolidar la tesis automatica para PDF.")

        pdf_content, filename = thesis_plan_pdf_service.build_pdf(
            plan_text=thesis_text,
            chat_title="Tesis automatica",
            user_email=user_email,
            document_label="TESIS",
            filename_prefix="tesis",
            academic_profile=academic_profile,
        )
        _store_thesis_pdf(
            user_id=user_id,
            chat_id=chat_id,
            filename=filename,
            pdf_content=pdf_content,
            job_id=job_id,
        )

        supabase_repository.update_thesis_auto_job(
            job_id,
            status="completed",
            found_sources=len(gemini_service.thesis_complete_sections()),
            progress_percent=100,
            progress_label="Tesis lista y PDF guardado",
            error_message="",
            completed_at=_utc_now_iso(),
        )
    except Exception as error:  # pragma: no cover - ejecucion en background
        LOGGER.exception("No se pudo completar la tesis automatica en background.")
        try:
            supabase_repository.update_thesis_auto_job(
                job_id,
                status="failed",
                progress_label="No se pudo completar la tesis automatica",
                error_message=str(error),
            )
        except SupabaseRepositoryError:
            LOGGER.exception("No se pudo actualizar el estado fallido del job de tesis.")


@router.get("/thesis/auto-jobs", response_model=list[ThesisAutoJobSummary])
async def list_automatic_thesis_jobs(
    limit: int = 10,
    current_user: UserPublic = Depends(get_current_user),
) -> list[ThesisAutoJobSummary]:
    try:
        jobs = supabase_repository.list_thesis_auto_jobs(
            user_id=current_user.id,
            limit=limit,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return [_serialize_auto_thesis_job(job) for job in jobs]


@router.post("/thesis/auto-jobs", response_model=ThesisAutoJobSummary)
async def start_automatic_thesis_job(
    payload: ThesisAutoJobRequest,
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisAutoJobSummary:
    source_plan = _validate_source_plan_session(payload.source_plan_chat_id, current_user)
    academic_profile = _resolve_session_academic_profile(source_plan, current_user)
    _read_source_plan_text(source_plan["id"])

    formal_data = payload.formal_data.model_dump() if payload.formal_data else {}
    title = _build_thesis_title(source_plan)

    try:
        thesis_session = supabase_repository.create_chat_session(
            user_id=current_user.id,
            document_id=None,
            mode=ChatSessionMode.THESIS.value,
            title=title,
            faculty_id=str(academic_profile["faculty_id"]),
            career_id=str(academic_profile["id"]),
            source_chat_session_id=str(source_plan["id"]),
        )
        supabase_repository.create_chat_message(
            chat_session_id=thesis_session["id"],
            role="user",
            content=(
                "Generar tesis automatica desde el plan seleccionado.\n"
                f"Plan fuente: {source_plan.get('title') or source_plan['id']}.\n"
                f"Facultad y carrera: {academic_profile['faculty_acronym']} - {academic_profile['name']}."
            ),
        )
        job = supabase_repository.create_thesis_auto_job(
            user_id=current_user.id,
            chat_session_id=thesis_session["id"],
            source_plan_chat_id=str(source_plan["id"]),
            source_plan_title=source_plan.get("title") or "Plan de tesis",
            formal_data=formal_data,
            ai_provider=payload.ai_provider.value,
            ai_model=payload.ai_model,
            faculty_id=str(academic_profile["faculty_id"]),
            career_id=str(academic_profile["id"]),
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    background_tasks.add_task(
        _run_automatic_thesis_job,
        job_id=job["id"],
        chat_id=thesis_session["id"],
        source_plan_chat_id=str(source_plan["id"]),
        user_id=current_user.id,
        user_email=current_user.email,
        formal_data=formal_data,
        ai_provider=payload.ai_provider.value,
        ai_model=payload.ai_model,
        academic_profile=academic_profile,
    )

    return _serialize_auto_thesis_job(job)


@router.patch("/thesis/auto-jobs/{job_id}/notified", response_model=ThesisAutoJobSummary)
async def mark_automatic_thesis_job_notified(
    job_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisAutoJobSummary:
    try:
        job = supabase_repository.mark_thesis_auto_job_notified(
            job_id=job_id,
            user_id=current_user.id,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    if not job:
        raise HTTPException(status_code=404, detail="Trabajo automatico de tesis no encontrado.")

    return _serialize_auto_thesis_job(job)


@router.post("/thesis/from-plan", response_model=ThesisFromPlanResponse)
async def create_thesis_from_plan(
    payload: ThesisFromPlanRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisFromPlanResponse:
    source_plan = _validate_source_plan_session(payload.source_plan_chat_id, current_user)
    academic_profile = _resolve_session_academic_profile(source_plan, current_user)
    _read_source_plan_text(source_plan["id"])

    title = _build_thesis_title(source_plan, payload.title)
    try:
        thesis_session = supabase_repository.create_chat_session(
            user_id=current_user.id,
            document_id=None,
            mode=ChatSessionMode.THESIS.value,
            title=title,
            faculty_id=str(academic_profile["faculty_id"]),
            career_id=str(academic_profile["id"]),
            source_chat_session_id=str(source_plan["id"]),
        )
        supabase_repository.create_chat_message(
            chat_session_id=thesis_session["id"],
            role="user",
            content=(
                "Generar tesis desde el plan seleccionado.\n"
                f"Plan fuente: {source_plan.get('title') or source_plan['id']}.\n"
                f"Facultad y carrera: {academic_profile['faculty_acronym']} - {academic_profile['name']}."
            ),
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return ThesisFromPlanResponse(
        chat_id=str(thesis_session["id"]),
        source_plan_chat_id=str(source_plan["id"]),
        title=thesis_session.get("title") or title,
    )


@router.get("/thesis/complete/sections")
async def list_thesis_complete_sections(
    current_user: UserPublic = Depends(get_current_user),
) -> list[dict[str, str | int]]:
    return gemini_service.thesis_complete_sections()


@router.post("/thesis/complete-section", response_model=ThesisCompleteSectionResponse)
async def generate_thesis_complete_section(
    payload: ThesisCompleteSectionRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisCompleteSectionResponse:
    thesis_session = _validate_thesis_session(payload.chat_id, current_user)
    source_plan = _validate_source_plan_session(payload.source_plan_chat_id, current_user)

    persisted_source_id = thesis_session.get("source_chat_session_id")
    if persisted_source_id and persisted_source_id != source_plan["id"]:
        raise HTTPException(
            status_code=400,
            detail="La tesis seleccionada fue creada desde otro plan de tesis.",
        )

    academic_profile = _resolve_session_academic_profile(source_plan, current_user)
    plan_text = _read_source_plan_text(source_plan["id"])
    formal_data = payload.formal_data.model_dump() if payload.formal_data else {}

    try:
        persisted_messages = supabase_repository.list_chat_messages(payload.chat_id)
        history = _serialize_history(persisted_messages, limit=40)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    try:
        section_text, section_index, section_title, total_sections = (
            gemini_service.generate_thesis_complete_section(
                source_plan_text=plan_text,
                thesis_history=history,
                section_id=payload.section_id,
                formal_data=formal_data,
                ai_provider=payload.ai_provider.value,
                ai_model=payload.ai_model,
                academic_profile=academic_profile,
            )
        )
    except GeminiServiceError as error:
        raise HTTPException(status_code=500, detail=error.message) from error

    response_text = _format_thesis_stage_message(
        content=section_text,
        section_index=section_index,
        total_sections=total_sections,
        section_title=section_title,
    )

    try:
        supabase_repository.create_chat_message(
            chat_session_id=payload.chat_id,
            role="assistant",
            content=response_text,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return ThesisCompleteSectionResponse(
        chat_id=payload.chat_id,
        source_plan_chat_id=payload.source_plan_chat_id,
        section_id=payload.section_id,
        section_title=section_title,
        section_index=section_index,
        total_sections=total_sections,
        response=response_text,
    )


@router.get("/thesis/{chat_id}/pdf")
async def export_thesis_pdf(
    chat_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> Response:
    thesis_session = _validate_thesis_session(chat_id, current_user)
    academic_profile = _resolve_session_academic_profile(thesis_session, current_user)

    try:
        messages = supabase_repository.list_chat_messages(chat_id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    thesis_text = _select_pdf_thesis_text(messages)
    if not thesis_text:
        raise HTTPException(
            status_code=400,
            detail="Genera primero la tesis por etapas antes de descargar el PDF.",
        )

    pdf_content, filename = thesis_plan_pdf_service.build_pdf(
        plan_text=thesis_text,
        chat_title=thesis_session.get("title") or "Tesis",
        user_email=current_user.email,
        document_label="TESIS",
        filename_prefix="tesis",
        academic_profile=academic_profile,
    )
    storage_path = _store_thesis_pdf(
        user_id=current_user.id,
        chat_id=chat_id,
        filename=filename,
        pdf_content=pdf_content,
    )

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Storage-Path": storage_path,
            "X-Content-Type-Options": "nosniff",
        },
    )
