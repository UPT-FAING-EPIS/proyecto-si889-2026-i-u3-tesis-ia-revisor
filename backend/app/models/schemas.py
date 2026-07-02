from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AcademicCareerSummary(BaseModel):
    id: str
    name: str
    supports_thesis_plan: bool = True


class AcademicFacultySummary(BaseModel):
    id: str
    acronym: str
    name: str
    careers: list[AcademicCareerSummary] = Field(default_factory=list)


class AcademicProfileRequest(BaseModel):
    faculty_id: str = Field(min_length=2, max_length=80)
    career_id: str = Field(min_length=2, max_length=120)


class AcademicProfile(BaseModel):
    user_id: str | None = None
    faculty_id: str
    faculty_name: str
    faculty_acronym: str
    career_id: str
    career_name: str
    supports_thesis_plan: bool = True
    manual_name: str
    default_research_line: str | None = None
    thesis_focus: str | None = None
    plan_sections: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AcademicProfileStatus(BaseModel):
    profile: AcademicProfile | None = None
    requires_selection: bool = True


class UserPublic(BaseModel):
    id: str
    email: str | None = None


class AuthRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=6, max_length=128)


class RegisterRequest(AuthRequest):
    faculty_id: str = Field(min_length=2, max_length=80)
    career_id: str = Field(min_length=2, max_length=120)


class AuthResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str | None = "bearer"
    user: UserPublic | None = None
    message: str | None = None


class DocumentSummary(BaseModel):
    id: str
    filename: str
    pdf_url: str | None = None
    created_at: datetime | None = None


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    pdf_url: str | None = None
    chunk_count: int
    extracted_characters: int
    replaced_document_id: str | None = None
    replace_warning: str | None = None


class ChatMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSessionMode(str, Enum):
    PDF_CHAT = "pdf_chat"
    THESIS_REVIEW = "thesis_review"
    THESIS_PLAN = "thesis_plan"
    THESIS = "thesis"


class AIProvider(str, Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"


class ChatMessage(BaseModel):
    role: ChatMessageRole
    content: str = Field(min_length=1)


class ChatSessionSummary(BaseModel):
    id: str
    document_id: str | None = None
    mode: ChatSessionMode
    title: str
    faculty_id: str | None = None
    career_id: str | None = None
    source_chat_session_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_message_at: datetime | None = None


class ChatSessionCreateRequest(BaseModel):
    document_id: str | None = None
    mode: ChatSessionMode = ChatSessionMode.PDF_CHAT
    title: str | None = Field(default=None, min_length=1, max_length=120)
    faculty_id: str | None = Field(default=None, max_length=80)
    career_id: str | None = Field(default=None, max_length=120)
    source_chat_session_id: str | None = Field(default=None, max_length=80)


class ChatMessageSummary(BaseModel):
    id: int
    chat_session_id: str
    role: ChatMessageRole
    content: str
    created_at: datetime | None = None


class ChatRequest(BaseModel):
    chat_id: str
    message: str = Field(min_length=1, max_length=4000)
    match_count: int = Field(default=5, ge=1, le=20)
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisReviewRequest(BaseModel):
    document_id: str
    chat_id: str
    message: str = Field(
        default="Evalua integralmente esta tesis y prioriza las mejoras de mayor impacto.",
        min_length=1,
        max_length=4000,
    )
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisReviewResponse(BaseModel):
    chat_id: str
    document_id: str
    filename: str
    review: str
    total_chunks: int
    analyzed_chunks: int
    analyzed_characters: int


class ThesisPlanRequest(BaseModel):
    chat_id: str
    message: str = Field(min_length=1, max_length=6000)
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisPlanFormalData(BaseModel):
    authors: str | None = Field(default=None, max_length=240)
    advisor: str | None = Field(default=None, max_length=160)
    area: str | None = Field(default=None, max_length=160)
    research_line: str | None = Field(default=None, max_length=220)


class ThesisPlanCompleteSectionRequest(BaseModel):
    chat_id: str
    section_id: str = Field(min_length=3, max_length=80)
    formal_data: ThesisPlanFormalData | None = None
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisPlanProblemSuggestion(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=5, max_length=180)
    problem: str = Field(min_length=20, max_length=1200)
    community_impact: str = Field(min_length=10, max_length=700)
    research_context: str = Field(min_length=10, max_length=700)
    variables: str = Field(min_length=10, max_length=700)


class ThesisPlanProblemSuggestionsRequest(BaseModel):
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisPlanProblemSuggestionsResponse(BaseModel):
    suggestions: list[ThesisPlanProblemSuggestion] = Field(default_factory=list)


class ThesisPlanAutoPdfRequest(BaseModel):
    selected_problem: ThesisPlanProblemSuggestion
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisPlanAutoJobRequest(BaseModel):
    selected_problem: ThesisPlanProblemSuggestion
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisPlanAutoJobSummary(BaseModel):
    id: str
    chat_id: str | None = None
    status: str
    progress_percent: int = 0
    progress_label: str | None = None
    error_message: str | None = None
    selected_problem: ThesisPlanProblemSuggestion | None = None
    ai_provider: AIProvider | None = None
    ai_model: str | None = None
    faculty_id: str | None = None
    career_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notified_at: datetime | None = None
    pdf_storage_path: str | None = None
    pdf_filename: str | None = None
    pdf_size_bytes: int | None = None
    pdf_mime_type: str | None = None
    pdf_generated_at: datetime | None = None


class ThesisPlanQuestion(BaseModel):
    id: str
    label: str
    question: str
    placeholder: str | None = None


class ThesisPlanResponse(BaseModel):
    chat_id: str
    response: str
    readiness_score: int
    missing_fields: list[str]
    next_phase: str
    manual_sections: list[str]
    suggested_questions: list[ThesisPlanQuestion] = Field(default_factory=list)


class ThesisPlanCompleteSectionResponse(BaseModel):
    chat_id: str
    section_id: str
    section_title: str
    section_index: int
    total_sections: int
    response: str
    readiness_score: int = 100
    next_phase: str = "documento_completo"


class ThesisFromPlanRequest(BaseModel):
    source_plan_chat_id: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=120)


class ThesisFromPlanResponse(BaseModel):
    chat_id: str
    source_plan_chat_id: str
    title: str


class ThesisCompleteSectionRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=80)
    source_plan_chat_id: str = Field(min_length=1, max_length=80)
    section_id: str = Field(min_length=3, max_length=80)
    formal_data: ThesisPlanFormalData | None = None
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisCompleteSectionResponse(BaseModel):
    chat_id: str
    source_plan_chat_id: str
    section_id: str
    section_title: str
    section_index: int
    total_sections: int
    response: str


class ThesisAutoJobRequest(BaseModel):
    source_plan_chat_id: str = Field(min_length=1, max_length=80)
    formal_data: ThesisPlanFormalData | None = None
    ai_provider: AIProvider = AIProvider.GEMINI
    ai_model: str | None = Field(default=None, max_length=120)


class ThesisAutoJobSummary(BaseModel):
    id: str
    chat_id: str | None = None
    source_plan_chat_id: str | None = None
    source_plan_title: str | None = None
    status: str
    progress_percent: int = 0
    progress_label: str | None = None
    error_message: str | None = None
    ai_provider: AIProvider | None = None
    ai_model: str | None = None
    faculty_id: str | None = None
    career_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notified_at: datetime | None = None
    pdf_storage_path: str | None = None
    pdf_filename: str | None = None
    pdf_size_bytes: int | None = None
    pdf_mime_type: str | None = None
    pdf_generated_at: datetime | None = None
