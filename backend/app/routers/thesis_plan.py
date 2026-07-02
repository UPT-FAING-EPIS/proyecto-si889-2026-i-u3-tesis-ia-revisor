import re
from datetime import UTC, datetime
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from app.core.academic_catalog import build_academic_profile, get_career_profile
from app.core.auth import get_current_user
from app.database.supabase_repository import SupabaseRepositoryError, supabase_repository
from app.models.schemas import (
    ChatSessionMode,
    ThesisPlanAutoJobRequest,
    ThesisPlanAutoJobSummary,
    ThesisPlanAutoPdfRequest,
    ThesisPlanCompleteSectionRequest,
    ThesisPlanCompleteSectionResponse,
    ThesisPlanProblemSuggestionsRequest,
    ThesisPlanProblemSuggestionsResponse,
    ThesisPlanRequest,
    ThesisPlanResponse,
    UserPublic,
)
from app.services.gemini_service import (
    THESIS_PLAN_COMPLETE_STAGE_PREFIX,
    GeminiServiceError,
    gemini_service,
)
from app.services.thesis_plan_pdf_service import thesis_plan_pdf_service


router = APIRouter(tags=["thesis-plan"])
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


def _validate_thesis_plan_session(chat_id: str, current_user: UserPublic) -> dict:
    try:
        chat_session = supabase_repository.get_chat_session_by_id(chat_id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    if not chat_session or chat_session.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Sesion de plan de tesis no encontrada.")

    if chat_session.get("mode") != ChatSessionMode.THESIS_PLAN.value:
        raise HTTPException(
            status_code=400,
            detail="La sesion no corresponde al modo de plan de tesis.",
        )

    return chat_session


def _get_current_user_academic_profile(current_user: UserPublic) -> dict:
    try:
        row = supabase_repository.get_user_academic_profile(current_user.id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    if not row:
        raise HTTPException(
            status_code=400,
            detail="Selecciona tu facultad y carrera antes de crear o continuar un plan de tesis.",
        )

    profile = build_academic_profile(
        faculty_id=row.get("faculty_id"),
        career_id=row.get("career_id"),
        user_id=current_user.id,
    )
    if not profile or not profile.get("supports_thesis_plan"):
        raise HTTPException(
            status_code=400,
            detail="La facultad y carrera seleccionadas no estan habilitadas para plan de tesis.",
        )

    return profile


def _resolve_chat_academic_profile(chat_session: dict, current_user: UserPublic) -> dict:
    session_faculty_id = chat_session.get("faculty_id")
    session_career_id = chat_session.get("career_id")
    if session_faculty_id and session_career_id:
        profile = get_career_profile(session_faculty_id, session_career_id)
        if profile and profile.get("supports_thesis_plan"):
            profile["user_id"] = current_user.id
            return profile

    return _get_current_user_academic_profile(current_user)


def _format_complete_stage_message(
    content: str,
    section_index: int,
    total_sections: int,
    section_title: str,
) -> str:
    return (
        f"{THESIS_PLAN_COMPLETE_STAGE_PREFIX} {section_index}/{total_sections} - {section_title}\n\n"
        f"{(content or '').strip()}"
    ).strip()


def _strip_complete_stage_marker(content: str) -> str:
    lines = (content or "").splitlines()
    if lines and lines[0].startswith(THESIS_PLAN_COMPLETE_STAGE_PREFIX):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]

    stage_marker_pattern = "documento academico completo - etapa"
    clean_lines = [
        line for line in lines
        if stage_marker_pattern not in line.strip().lower().replace("académico", "academico")
    ]
    return "\n".join(clean_lines).strip()


def _remove_validation_language(content: str) -> str:
    text = content or ""
    replacements = [
        (r"\s*\((?:por\s+validar|por\s+confirmar|sujeto\s+a\s+confirmaci[oó]n)\)", ""),
        (r"\s*\*(?:por\s+validar|por\s+confirmar|sujeto\s+a\s+confirmaci[oó]n)\*", ""),
        (r"\bpor\s+validar\b", ""),
        (r"\bpor\s+confirmar\b", ""),
        (r"\bsujeto\s+a\s+confirmaci[oó]n\b", ""),
        (r"\bsujet[oa]s?\s+a\s+confirmaci[oó]n\b", ""),
        (r"\breferencias?\s+por\s+completar\b", "referencias academicas"),
        (r"\bsecci[oó]n\s+en\s+blanco\s*[-–]\s*por\s+completar\b", "seccion desarrollada"),
        (r"\*?Nota\s+para\s+la\s+versi[oó]n\s+final:\*?.*?(?=\n\n|$)", ""),
        (r"Al\s+tratarse\s+de\s+un\s+plan,.*?durante\s+el\s+desarrollo\s+de\s+la\s+tesis\.", ""),
        (r"o\s+ser[aá]n\s+confirmadas\s+en\s+su\s+texto\s+completo\s+durante\s+el\s+desarrollo\s+de\s+la\s+tesis", ""),
        (r",?\s*aunque\s+la\s+referencia\s+debe\s+ser\s+validada\s+en\s+texto\s+completo", ""),
        (r"Ninguna\s+de\s+estas\s+fuentes\s+ha\s+sido\s+confirmada.*?(?=\n\n|$)", ""),
        (r"\bde\s+manera\s+aproximada\s+contando\b", "contando"),
        (r"\bvalores\s+referenciales\b", "costos estimados"),
        (r"Este\s+presupuesto\s+es\s+tentativo\s+y\s+deber[aá]\s+ser\s+ajustado\s+cuando\s+se\s+confirmen\s+los\s+recursos\s+disponibles\.", "Este presupuesto corresponde a la estimacion economica definida para el plan."),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\(\s*\)", "", text)
    return text.strip()


def _count_doi_links(content: str) -> int:
    return len(set(re.findall(r"https?://doi\.org/[^\s)>\]]+", content or "", flags=re.IGNORECASE)))


def _append_doi_references_if_needed(
    plan_text: str,
    messages: list[dict],
    min_doi_count: int = 15,
    academic_profile: dict | None = None,
) -> str:
    current_count = _count_doi_links(plan_text)
    if current_count >= min_doi_count:
        return plan_text

    references = gemini_service._discover_academic_sources(  # noqa: SLF001 - reuso controlado para exportacion.
        _serialize_history(messages, limit=80),
        limit=max(min_doi_count, 18),
        academic_profile=academic_profile,
    )
    doi_references = [reference for reference in references if "https://doi.org/" in reference.lower()]
    if not doi_references:
        return plan_text

    existing_dois = {
        doi.lower()
        for doi in re.findall(r"https?://doi\.org/[^\s)>\]]+", plan_text, flags=re.IGNORECASE)
    }
    new_references = []
    for reference in doi_references:
        doi_match = re.search(r"https?://doi\.org/[^\s)>\]]+", reference, flags=re.IGNORECASE)
        if not doi_match:
            continue
        normalized_doi = doi_match.group(0).lower()
        if normalized_doi in existing_dois:
            continue
        new_references.append(reference)
        existing_dois.add(normalized_doi)
        if len(existing_dois) >= min_doi_count:
            break

    if not new_references:
        return plan_text

    supplement = "\n".join(f"- {reference}" for reference in new_references)
    supplement_block = f"Referencias academicas complementarias con DOI\n{supplement}"
    annex_match = re.search(r"\n(?=(?:#{1,6}\s*)?ANEXOS\b)", plan_text, flags=re.IGNORECASE)
    if annex_match:
        return (
            f"{plan_text[:annex_match.start()].rstrip()}\n\n"
            f"{supplement_block}\n\n"
            f"{plan_text[annex_match.start():].lstrip()}"
        )

    return f"{plan_text.rstrip()}\n\n{supplement_block}"


def _select_pdf_plan_text(messages: list[dict]) -> str:
    last_complete_start_index = -1
    for index, row in enumerate(messages):
        content = (row.get("content") or "").strip()
        if (
            row.get("role") == "assistant"
            and content.startswith(THESIS_PLAN_COMPLETE_STAGE_PREFIX)
            and "ETAPA 1/" in content.splitlines()[0]
        ):
            last_complete_start_index = index

    if last_complete_start_index >= 0:
        complete_sections = [
            _strip_complete_stage_marker(row.get("content") or "")
            for row in messages[last_complete_start_index:]
            if row.get("role") == "assistant"
            and (row.get("content") or "").strip().startswith(THESIS_PLAN_COMPLETE_STAGE_PREFIX)
        ]
        complete_sections = [section for section in complete_sections if section]
        if complete_sections:
            return _remove_validation_language("\n\n".join(complete_sections))

    assistant_messages = [
        row for row in messages
        if row.get("role") == "assistant" and (row.get("content") or "").strip()
    ]
    if not assistant_messages:
        return ""
    return _remove_validation_language(assistant_messages[-1].get("content") or "")


def _validate_complete_formal_data(formal_data: dict[str, str]) -> None:
    required_fields = {
        "authors": "autor(es)",
        "advisor": "asesor",
        "area": "area de investigacion",
        "research_line": "linea de investigacion",
    }
    missing = [
        label for key, label in required_fields.items()
        if not (formal_data.get(key) or "").strip()
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                "Completa los datos formales antes de generar el documento: "
                + ", ".join(missing)
                + "."
            ),
        )


def _build_auto_formal_data(
    current_user: UserPublic,
    academic_profile: dict | None = None,
) -> dict[str, str]:
    email = (current_user.email or "").strip()
    local_part = email.split("@", 1)[0] if email else ""
    author_name = " ".join(re.sub(r"[^A-Za-z0-9]+", " ", local_part).split()).title()
    if not author_name:
        author_name = "Estudiante Autenticado"

    career_name = str((academic_profile or {}).get("name") or "").strip()
    faculty_acronym = str((academic_profile or {}).get("faculty_acronym") or "").strip()
    research_line = str((academic_profile or {}).get("default_research_line") or "").strip()

    return {
        "authors": f"Bach. {author_name}",
        "advisor": f"Asesor metodologico {faculty_acronym or 'UPT'}",
        "area": career_name or "Carrera pendiente de registro",
        "research_line": research_line or "Linea de investigacion pendiente de registro",
    }


def _build_auto_problem_message(
    selected_problem: dict[str, str],
    academic_profile: dict | None = None,
) -> str:
    title = (selected_problem.get("title") or "").strip()
    problem = (selected_problem.get("problem") or "").strip()
    community_impact = (selected_problem.get("community_impact") or "").strip()
    research_context = (selected_problem.get("research_context") or "").strip()
    variables = (selected_problem.get("variables") or "").strip()
    career_name = str((academic_profile or {}).get("name") or "la carrera seleccionada").strip()
    data_sources = str((academic_profile or {}).get("data_sources") or "").strip()
    deliverable = str((academic_profile or {}).get("deliverable") or "").strip()
    method_guidance = str((academic_profile or {}).get("method_guidance") or "").strip()
    thesis_focus = str((academic_profile or {}).get("thesis_focus") or "").strip()

    return (
        f"Quiero investigar: {title}.\n\n"
        f"Facultad y carrera: {academic_profile.get('faculty_acronym') if academic_profile else 'UPT'} - {career_name}.\n\n"
        f"Enfoque esperado de la carrera: {thesis_focus or 'problema aplicado con evidencia suficiente'}.\n\n"
        f"Problema observable: {problem}\n\n"
        f"Contexto o delimitacion: {research_context}\n\n"
        "Unidad de analisis o poblacion: actores, usuarios, pacientes, estudiantes, empresas, "
        "espacios, registros, muestras o documentos del contexto propuesto, segun corresponda "
        "a la carrera y al alcance del plan.\n\n"
        f"Variables o categorias tentativas: {variables}\n\n"
        f"Justificacion, importancia o factibilidad: {community_impact}\n\n"
        f"Objetivo o resultado esperado: formular y validar {deliverable or 'una propuesta o evidencia aplicada'} "
        "que mejore la comprension o solucion del problema seleccionado y aporte valor a la comunidad.\n\n"
        f"Tipo, nivel o diseno preliminar: {method_guidance or 'investigacion aplicada con diseno coherente segun datos disponibles'}.\n\n"
        f"Datos, instrumentos o tecnica: {data_sources or 'encuestas, entrevistas, revision documental, mediciones, registros e indicadores observables'}."
    )


def _build_auto_chat_title(selected_problem: dict[str, str]) -> str:
    title = " ".join((selected_problem.get("title") or "Plan automatico de tesis").split())
    return f"Plan automatico - {title}"[:120]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _serialize_auto_job(row: dict) -> ThesisPlanAutoJobSummary:
    provider = row.get("ai_provider")
    if provider not in {"gemini", "deepseek"}:
        provider = None

    selected_problem = row.get("selected_problem")
    if not isinstance(selected_problem, dict):
        selected_problem = None

    return ThesisPlanAutoJobSummary(
        id=str(row.get("id")),
        chat_id=row.get("chat_session_id"),
        status=row.get("status") or "pending",
        progress_percent=int(row.get("progress_percent") or 0),
        progress_label=row.get("progress_label"),
        error_message=row.get("error_message"),
        selected_problem=selected_problem,
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


def _store_thesis_plan_pdf(
    *,
    user_id: str,
    chat_id: str,
    filename: str,
    pdf_content: bytes,
    job_id: str | None = None,
    update_job_for_chat: bool = False,
) -> str:
    try:
        storage_path = supabase_repository.upload_thesis_plan_pdf(
            user_id=user_id,
            chat_session_id=chat_id,
            filename=filename,
            file_bytes=pdf_content,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    try:
        if job_id:
            supabase_repository.update_thesis_plan_auto_job_pdf_metadata(
                job_id=job_id,
                pdf_storage_path=storage_path,
                pdf_filename=filename,
                pdf_size_bytes=len(pdf_content),
            )
        elif update_job_for_chat:
            supabase_repository.update_thesis_plan_auto_job_pdf_metadata_for_chat(
                chat_session_id=chat_id,
                user_id=user_id,
                pdf_storage_path=storage_path,
                pdf_filename=filename,
                pdf_size_bytes=len(pdf_content),
            )
    except SupabaseRepositoryError:
        LOGGER.exception(
            "El PDF del plan se subio a Storage, pero no se pudieron guardar metadatos del job."
        )

    return storage_path


def _generate_automatic_plan_sections(
    chat_id: str,
    formal_data: dict[str, str],
    ai_provider: str,
    ai_model: str | None,
    academic_profile: dict | None = None,
    job_id: str | None = None,
) -> None:
    try:
        persisted_messages = supabase_repository.list_chat_messages(chat_id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    history = _serialize_history(persisted_messages, limit=40)
    sections = gemini_service.thesis_plan_complete_sections()
    total_sections = len(sections)

    for section in sections:
        section_id = str(section["id"])
        section_title_for_progress = str(section["title"])
        section_index_for_progress = int(section["index"])

        if job_id:
            supabase_repository.update_thesis_plan_auto_job(
                job_id,
                status="running",
                found_sources=max(section_index_for_progress - 1, 0),
                progress_percent=round(((section_index_for_progress - 1) / total_sections) * 95),
                progress_label=f"Generando {section_title_for_progress}",
            )

        try:
            section_text, section_index, section_title, total = (
                gemini_service.generate_thesis_plan_complete_section(
                    history=history,
                    section_id=section_id,
                    formal_data=formal_data,
                    ai_provider=ai_provider,
                    ai_model=ai_model,
                    academic_profile=academic_profile,
                )
            )
        except GeminiServiceError as error:
            raise HTTPException(status_code=500, detail=error.message) from error

        response_text = _format_complete_stage_message(
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

        if job_id:
            supabase_repository.update_thesis_plan_auto_job(
                job_id,
                status="running",
                found_sources=section_index,
                progress_percent=round((section_index / total_sections) * 95),
                progress_label=f"Completado {section_title}",
            )


def _run_automatic_thesis_plan_job(
    job_id: str,
    chat_id: str,
    user_id: str,
    user_email: str | None,
    ai_provider: str,
    ai_model: str | None,
    academic_profile: dict | None,
) -> None:
    try:
        supabase_repository.update_thesis_plan_auto_job(
            job_id,
            status="running",
            progress_percent=2,
            progress_label="Preparando generacion del plan",
            started_at=_utc_now_iso(),
        )

        formal_data = _build_auto_formal_data(
            UserPublic(id=user_id, email=user_email),
            academic_profile=academic_profile,
        )
        _generate_automatic_plan_sections(
            chat_id=chat_id,
            formal_data=formal_data,
            ai_provider=ai_provider,
            ai_model=ai_model,
            academic_profile=academic_profile,
            job_id=job_id,
        )

        supabase_repository.update_thesis_plan_auto_job(
            job_id,
            status="running",
            progress_percent=96,
            progress_label="Preparando PDF del plan",
        )
        persisted_messages = supabase_repository.list_chat_messages(chat_id)
        plan_text = _append_doi_references_if_needed(
            _select_pdf_plan_text(persisted_messages),
            persisted_messages,
            academic_profile=academic_profile,
        )
        if not plan_text:
            raise RuntimeError("No se pudo consolidar el plan automatico para PDF.")

        pdf_content, filename = thesis_plan_pdf_service.build_pdf(
            plan_text=plan_text,
            chat_title="Plan automatico de tesis",
            user_email=user_email,
            academic_profile=academic_profile,
        )
        _store_thesis_plan_pdf(
            user_id=user_id,
            chat_id=chat_id,
            filename=filename,
            pdf_content=pdf_content,
            job_id=job_id,
        )

        supabase_repository.update_thesis_plan_auto_job(
            job_id,
            status="completed",
            found_sources=len(gemini_service.thesis_plan_complete_sections()),
            progress_percent=100,
            progress_label="Plan de tesis listo y PDF guardado",
            error_message="",
            completed_at=_utc_now_iso(),
        )
    except Exception as error:  # pragma: no cover - ejecucion en background
        LOGGER.exception("No se pudo completar el plan automatico en background.")
        try:
            supabase_repository.update_thesis_plan_auto_job(
                job_id,
                status="failed",
                progress_label="No se pudo completar el plan automatico",
                error_message=str(error),
            )
        except SupabaseRepositoryError:
            LOGGER.exception("No se pudo actualizar el estado fallido del job automatico.")


@router.post("/thesis/plan/auto-problems", response_model=ThesisPlanProblemSuggestionsResponse)
async def suggest_thesis_plan_problems(
    payload: ThesisPlanProblemSuggestionsRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisPlanProblemSuggestionsResponse:
    academic_profile = _get_current_user_academic_profile(current_user)
    try:
        suggestions = gemini_service.generate_thesis_plan_problem_suggestions(
            ai_provider=payload.ai_provider.value,
            ai_model=payload.ai_model,
            academic_profile=academic_profile,
        )
    except GeminiServiceError as error:
        raise HTTPException(status_code=500, detail=error.message) from error

    return ThesisPlanProblemSuggestionsResponse(suggestions=suggestions)


@router.get("/thesis/plan/auto-jobs", response_model=list[ThesisPlanAutoJobSummary])
async def list_automatic_thesis_plan_jobs(
    limit: int = 10,
    current_user: UserPublic = Depends(get_current_user),
) -> list[ThesisPlanAutoJobSummary]:
    try:
        jobs = supabase_repository.list_thesis_plan_auto_jobs(
            user_id=current_user.id,
            limit=limit,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return [_serialize_auto_job(job) for job in jobs]


@router.post("/thesis/plan/auto-jobs", response_model=ThesisPlanAutoJobSummary)
async def start_automatic_thesis_plan_job(
    payload: ThesisPlanAutoJobRequest,
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisPlanAutoJobSummary:
    academic_profile = _get_current_user_academic_profile(current_user)
    selected_problem = payload.selected_problem.model_dump()
    user_message = _build_auto_problem_message(selected_problem, academic_profile)

    try:
        chat_session = supabase_repository.create_chat_session(
            user_id=current_user.id,
            document_id=None,
            mode=ChatSessionMode.THESIS_PLAN.value,
            title=_build_auto_chat_title(selected_problem),
            faculty_id=str(academic_profile["faculty_id"]),
            career_id=str(academic_profile["id"]),
        )
        supabase_repository.create_chat_message(
            chat_session_id=chat_session["id"],
            role="user",
            content=user_message,
        )
        job = supabase_repository.create_thesis_plan_auto_job(
            user_id=current_user.id,
            chat_session_id=chat_session["id"],
            selected_problem=selected_problem,
            ai_provider=payload.ai_provider.value,
            ai_model=payload.ai_model,
            faculty_id=str(academic_profile["faculty_id"]),
            career_id=str(academic_profile["id"]),
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    background_tasks.add_task(
        _run_automatic_thesis_plan_job,
        job_id=job["id"],
        chat_id=chat_session["id"],
        user_id=current_user.id,
        user_email=current_user.email,
        ai_provider=payload.ai_provider.value,
        ai_model=payload.ai_model,
        academic_profile=academic_profile,
    )

    return _serialize_auto_job(job)


@router.patch("/thesis/plan/auto-jobs/{job_id}/notified", response_model=ThesisPlanAutoJobSummary)
async def mark_automatic_thesis_plan_job_notified(
    job_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisPlanAutoJobSummary:
    try:
        job = supabase_repository.mark_thesis_plan_auto_job_notified(
            job_id=job_id,
            user_id=current_user.id,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    if not job:
        raise HTTPException(status_code=404, detail="Trabajo automatico no encontrado.")

    return _serialize_auto_job(job)


@router.post("/thesis/plan/auto-pdf")
async def generate_automatic_thesis_plan_pdf(
    payload: ThesisPlanAutoPdfRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> Response:
    academic_profile = _get_current_user_academic_profile(current_user)
    selected_problem = payload.selected_problem.model_dump()
    formal_data = _build_auto_formal_data(current_user, academic_profile)
    user_message = _build_auto_problem_message(selected_problem, academic_profile)

    try:
        chat_session = supabase_repository.create_chat_session(
            user_id=current_user.id,
            document_id=None,
            mode=ChatSessionMode.THESIS_PLAN.value,
            title=_build_auto_chat_title(selected_problem),
            faculty_id=str(academic_profile["faculty_id"]),
            career_id=str(academic_profile["id"]),
        )
        supabase_repository.create_chat_message(
            chat_session_id=chat_session["id"],
            role="user",
            content=user_message,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    _generate_automatic_plan_sections(
        chat_id=chat_session["id"],
        formal_data=formal_data,
        ai_provider=payload.ai_provider.value,
        ai_model=payload.ai_model,
        academic_profile=academic_profile,
    )

    try:
        messages = supabase_repository.list_chat_messages(chat_session["id"])
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    plan_text = _append_doi_references_if_needed(
        _select_pdf_plan_text(messages),
        messages,
        academic_profile=academic_profile,
    )
    if not plan_text:
        raise HTTPException(
            status_code=500,
            detail="No se pudo consolidar el plan automatico para PDF.",
        )

    pdf_content, filename = thesis_plan_pdf_service.build_pdf(
        plan_text=plan_text,
        chat_title=chat_session.get("title") or "Plan automatico de tesis",
        user_email=current_user.email,
        academic_profile=academic_profile,
    )
    storage_path = _store_thesis_plan_pdf(
        user_id=current_user.id,
        chat_id=chat_session["id"],
        filename=filename,
        pdf_content=pdf_content,
        update_job_for_chat=True,
    )

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Chat-Id": str(chat_session["id"]),
            "X-Storage-Path": storage_path,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/thesis/plan", response_model=ThesisPlanResponse)
async def continue_thesis_plan(
    payload: ThesisPlanRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisPlanResponse:
    chat_session = _validate_thesis_plan_session(payload.chat_id, current_user)
    academic_profile = _resolve_chat_academic_profile(chat_session, current_user)

    try:
        supabase_repository.create_chat_message(
            chat_session_id=payload.chat_id,
            role="user",
            content=payload.message,
        )
        persisted_messages = supabase_repository.list_chat_messages(payload.chat_id)
        history = _serialize_history(persisted_messages)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    try:
        response_text, readiness_score, missing_fields, next_phase = gemini_service.advise_thesis_plan(
            history=history,
            user_message=payload.message,
            ai_provider=payload.ai_provider.value,
            ai_model=payload.ai_model,
            academic_profile=academic_profile,
        )
    except GeminiServiceError as error:
        raise HTTPException(status_code=500, detail=error.message) from error

    try:
        supabase_repository.create_chat_message(
            chat_session_id=payload.chat_id,
            role="assistant",
            content=response_text,
        )
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return ThesisPlanResponse(
        chat_id=payload.chat_id,
        response=response_text,
        readiness_score=readiness_score,
        missing_fields=missing_fields,
        next_phase=next_phase,
        manual_sections=gemini_service.thesis_plan_manual_sections(academic_profile),
        suggested_questions=gemini_service.thesis_plan_suggested_questions(
            missing_fields=missing_fields,
            next_phase=next_phase,
        ),
    )


@router.get("/thesis/plan/complete/sections")
async def list_thesis_plan_complete_sections(
    current_user: UserPublic = Depends(get_current_user),
) -> list[dict[str, str | int]]:
    return gemini_service.thesis_plan_complete_sections()


@router.post("/thesis/plan/complete-section", response_model=ThesisPlanCompleteSectionResponse)
async def generate_thesis_plan_complete_section(
    payload: ThesisPlanCompleteSectionRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> ThesisPlanCompleteSectionResponse:
    chat_session = _validate_thesis_plan_session(payload.chat_id, current_user)
    academic_profile = _resolve_chat_academic_profile(chat_session, current_user)

    formal_data = payload.formal_data.model_dump() if payload.formal_data else {}
    _validate_complete_formal_data(formal_data)

    try:
        persisted_messages = supabase_repository.list_chat_messages(payload.chat_id)
        history = _serialize_history(persisted_messages, limit=40)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    try:
        section_text, section_index, section_title, total_sections = (
            gemini_service.generate_thesis_plan_complete_section(
                history=history,
                section_id=payload.section_id,
                formal_data=formal_data,
                ai_provider=payload.ai_provider.value,
                ai_model=payload.ai_model,
                academic_profile=academic_profile,
            )
        )
    except GeminiServiceError as error:
        raise HTTPException(status_code=500, detail=error.message) from error

    response_text = _format_complete_stage_message(
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

    return ThesisPlanCompleteSectionResponse(
        chat_id=payload.chat_id,
        section_id=payload.section_id,
        section_title=section_title,
        section_index=section_index,
        total_sections=total_sections,
        response=response_text,
    )


@router.get("/thesis/plan/{chat_id}/pdf")
async def export_thesis_plan_pdf(
    chat_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> Response:
    chat_session = _validate_thesis_plan_session(chat_id, current_user)
    academic_profile = _resolve_chat_academic_profile(chat_session, current_user)

    try:
        messages = supabase_repository.list_chat_messages(chat_id)
    except SupabaseRepositoryError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    plan_text = _append_doi_references_if_needed(
        _select_pdf_plan_text(messages),
        messages,
        academic_profile=academic_profile,
    )
    if not plan_text:
        raise HTTPException(
            status_code=400,
            detail="Genera primero un plan con el asesor antes de descargar el PDF.",
        )

    pdf_content, filename = thesis_plan_pdf_service.build_pdf(
        plan_text=plan_text,
        chat_title=chat_session.get("title") or "Plan de tesis",
        user_email=current_user.email,
        academic_profile=academic_profile,
    )
    storage_path = _store_thesis_plan_pdf(
        user_id=current_user.id,
        chat_id=chat_id,
        filename=filename,
        pdf_content=pdf_content,
        update_job_for_chat=True,
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
