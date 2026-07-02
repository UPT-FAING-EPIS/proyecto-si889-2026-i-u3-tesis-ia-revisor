from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            PROJECT_DIR / ".env",
            PROJECT_DIR / ".env.local",
            BACKEND_DIR / ".env",
            BACKEND_DIR / ".env.local",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Asesor IA de Tesis API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"

    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "API_GEMINI"),
    )
    gemini_api_version: str = Field(
        default="v1",
        validation_alias=AliasChoices("GEMINI_API_VERSION"),
    )
    gemini_chat_model: str = Field(default="gemini-2.0-flash")
    gemini_embedding_model: str = Field(default="models/text-embedding-004")
    gemini_embedding_output_dimensionality: int = Field(
        default=3072,
        validation_alias=AliasChoices("GEMINI_EMBEDDING_OUTPUT_DIMENSIONALITY"),
    )
    gemini_chat_max_output_tokens: int = Field(
        default=3072,
        validation_alias=AliasChoices("GEMINI_CHAT_MAX_OUTPUT_TOKENS"),
    )
    gemini_review_max_output_tokens: int = Field(
        default=6144,
        validation_alias=AliasChoices("GEMINI_REVIEW_MAX_OUTPUT_TOKENS"),
    )
    gemini_review_max_input_chars: int = Field(
        default=260000,
        validation_alias=AliasChoices("GEMINI_REVIEW_MAX_INPUT_CHARS"),
    )
    deepseek_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("DEEPSEEK_API_KEY"),
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias=AliasChoices("DEEPSEEK_BASE_URL"),
    )
    deepseek_chat_model: str = Field(
        default="deepseek-v4-pro",
        validation_alias=AliasChoices("DEEPSEEK_CHAT_MODEL"),
    )
    deepseek_chat_max_output_tokens: int = Field(
        default=8192,
        validation_alias=AliasChoices("DEEPSEEK_CHAT_MAX_OUTPUT_TOKENS"),
    )

    supabase_url: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
    )
    supabase_publishable_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_PUBLISHABLE_KEY",
            "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
        ),
    )
    supabase_service_role_key: str = Field(default="")
    supabase_storage_bucket: str = Field(
        default="thesis-documents",
        validation_alias=AliasChoices("SUPABASE_STORAGE_BUCKET"),
    )
    supabase_storage_signed_url_expires_seconds: int = Field(
        default=3600,
        validation_alias=AliasChoices("SUPABASE_STORAGE_SIGNED_URL_EXPIRES_SECONDS"),
    )

    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CORS_ORIGINS", "FRONTEND_ORIGINS"),
    )
    cors_origin_regex: str = Field(
        default=r"https://.*\\.app\\.github\\.dev",
        validation_alias=AliasChoices("CORS_ORIGIN_REGEX"),
    )

    @property
    def supabase_key(self) -> str:
        return self.supabase_service_role_key or self.supabase_publishable_key

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin and origin.strip()
        ]


@lru_cache

def get_settings() -> Settings:
    return Settings()
