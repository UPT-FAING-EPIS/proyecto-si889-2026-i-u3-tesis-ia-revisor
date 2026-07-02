import re
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
import logging

from supabase import Client, create_client

from app.core.config import get_settings


LOGGER = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"[\w\-]+", re.UNICODE)
VECTOR_DIMENSION_PATTERN = re.compile(r"expected\s+(\d+)\s+dimensions?\s*,\s*not\s+(\d+)", re.IGNORECASE)


class SupabaseRepositoryError(Exception):
    """Error de operaciones en Supabase."""


class SupabaseRepository:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Client | None = None
        self._storage_bucket_ready = False
        self._vector_dimension_override: int | None = None

    def _get_client(self) -> Client:
        if self._client:
            return self._client

        if not self.settings.supabase_url:
            raise SupabaseRepositoryError(
                "Debes configurar SUPABASE_URL en las variables de entorno del backend."
            )

        if not self.settings.supabase_service_role_key:
            raise SupabaseRepositoryError(
                "Debes configurar SUPABASE_SERVICE_ROLE_KEY para operaciones backend con RLS."
            )

        self._client = create_client(
            self.settings.supabase_url,
            self.settings.supabase_service_role_key,
        )
        return self._client

    @staticmethod
    def _to_pgvector(embedding: Sequence[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"

    @staticmethod
    def _tokenize_for_search(text: str) -> list[str]:
        return [
            token
            for token in TOKEN_PATTERN.findall((text or "").lower())
            if len(token) >= 3
        ]

    @staticmethod
    def _is_vector_dimension_mismatch(error: Exception) -> bool:
        message = str(error).lower()
        return (
            "different vector dimensions" in message
            or ("vector" in message and "dimension" in message)
            or "expected" in message and "dimensions" in message and "not" in message
        )

    @staticmethod
    def _extract_expected_vector_dimension(error: Exception) -> int | None:
        message = str(error)
        match = VECTOR_DIMENSION_PATTERN.search(message)
        if match:
            try:
                expected = int(match.group(1))
                return expected if expected > 0 else None
            except ValueError:
                return None

        lower_message = message.lower()
        generic_match = re.search(r"vector\((\d+)\)", lower_message)
        if generic_match:
            try:
                expected = int(generic_match.group(1))
                return expected if expected > 0 else None
            except ValueError:
                return None

        return None

    @staticmethod
    def _coerce_embedding_dimension(embedding: Sequence[float], target_dimension: int) -> list[float]:
        values = [float(value) for value in embedding]
        if target_dimension <= 0:
            return values

        if len(values) == target_dimension:
            return values

        if len(values) > target_dimension:
            return values[:target_dimension]

        return values + [0.0] * (target_dimension - len(values))

    def _resolve_target_vector_dimension(self, current_dimension: int) -> int:
        if self._vector_dimension_override and self._vector_dimension_override > 0:
            return self._vector_dimension_override
        return current_dimension

    def _build_chunk_rows(
        self,
        document_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> list[dict]:
        return [
            {
                "document_id": document_id,
                "content": chunk,
                "embedding": self._to_pgvector(embedding),
            }
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

    def _insert_chunk_rows_in_batches(self, rows: list[dict], batch_size: int = 100) -> None:
        client = self._get_client()
        for index in range(0, len(rows), batch_size):
            batch = rows[index : index + batch_size]
            client.table("document_chunks").insert(batch).execute()

    @staticmethod
    def _is_missing_pdf_metadata_columns(error: Exception) -> bool:
        message = str(error).lower()
        if "column" not in message:
            return False

        return (
            "pdf_storage_path" in message
            or "pdf_filename" in message
            or "pdf_size_bytes" in message
            or "pdf_mime_type" in message
            or "pdf_generated_at" in message
        ) and ("does not exist" in message or "undefined" in message)

    @staticmethod
    def _is_missing_chat_session_mode_column(error: Exception) -> bool:
        message = str(error).lower()
        return (
            "chat_sessions" in message
            and "mode" in message
            and (
                "does not exist" in message
                or "schema cache" in message
                or "could not find" in message
                or "undefined" in message
            )
        )

    @staticmethod
    def _is_thesis_plan_session_schema_error(error: Exception) -> bool:
        message = str(error).lower()
        if "chat_sessions" not in message:
            return False

        document_id_is_required = (
            "document_id" in message
            and (
                "not-null" in message
                or "not null" in message
                or "null value" in message
                or "violates" in message
            )
        )
        mode_is_restricted = (
            "mode" in message
            and (
                "check constraint" in message
                or "chat_sessions_mode_check" in message
                or "violates" in message
                or "does not exist" in message
                or "schema cache" in message
                or "could not find" in message
                or "undefined" in message
            )
        )
        return document_id_is_required or mode_is_restricted

    @staticmethod
    def _is_missing_academic_profile_schema(error: Exception) -> bool:
        message = str(error).lower()
        return (
            "user_academic_profiles" in message
            or "faculty_id" in message
            or "career_id" in message
            or "source_chat_session_id" in message
        ) and (
            "does not exist" in message
            or "schema cache" in message
            or "could not find" in message
            or "undefined" in message
            or "column" in message
        )

    @staticmethod
    def _thesis_plan_schema_error_message() -> str:
        return (
            "La base de datos aun no esta preparada para que los flujos de tesis "
            "funcionen independiente del PDF. Ejecuta backend/sql/schema.sql en Supabase "
            "para permitir chat_sessions.document_id NULL y los modos academicos."
        )

    @staticmethod
    def _academic_profile_schema_error_message() -> str:
        return (
            "La base de datos aun no tiene el perfil academico. Ejecuta "
            "backend/sql/schema.sql en Supabase para crear user_academic_profiles "
            "y las columnas faculty_id/career_id."
        )

    def _fallback_match_document_chunks_text(
        self,
        document_id: str,
        query_text: str | None,
        match_count: int,
    ) -> list[dict]:
        client = self._get_client()

        response = (
            client.table("document_chunks")
            .select("id, document_id, content")
            .eq("document_id", document_id)
            .order("id")
            .limit(1000)
            .execute()
        )

        chunks = response.data or []
        if not chunks:
            return []

        query_tokens = self._tokenize_for_search(query_text or "")
        if not query_tokens:
            return [
                {
                    "id": chunk.get("id"),
                    "document_id": chunk.get("document_id"),
                    "content": chunk.get("content"),
                    "similarity": 0.0,
                }
                for chunk in chunks[:match_count]
            ]

        scored_chunks: list[tuple[float, dict]] = []
        for chunk in chunks:
            content = chunk.get("content") or ""
            content_tokens = self._tokenize_for_search(content)
            if not content_tokens:
                scored_chunks.append((0.0, chunk))
                continue

            frequency = Counter(content_tokens)
            score = 0.0
            for token in query_tokens:
                hits = frequency.get(token, 0)
                if hits:
                    score += 1.0 + min(hits, 4) * 0.25

            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        top_chunks = scored_chunks[:match_count]

        if top_chunks and top_chunks[0][0] == 0.0:
            top_chunks = [(0.0, chunk) for chunk in chunks[:match_count]]

        return [
            {
                "id": chunk.get("id"),
                "document_id": chunk.get("document_id"),
                "content": chunk.get("content"),
                "similarity": score,
            }
            for score, chunk in top_chunks
        ]

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9._-]+", "_", (filename or "").strip())
        if not clean:
            clean = "documento.pdf"
        if not clean.lower().endswith(".pdf"):
            clean = f"{clean}.pdf"
        return clean

    @staticmethod
    def _normalize_chat_title(title: str | None, default_title: str = "Nuevo chat") -> str:
        clean = " ".join((title or "").strip().split())
        if not clean:
            return default_title
        return clean[:120]

    def _build_pdf_storage_path(self, user_id: str, document_id: str, filename: str) -> str:
        normalized_filename = self._normalize_filename(filename)
        return f"{user_id}/{document_id}/{normalized_filename}"

    def _build_thesis_plan_pdf_storage_path(
        self,
        user_id: str,
        chat_session_id: str,
        filename: str,
    ) -> str:
        normalized_filename = self._normalize_filename(filename)
        return f"{user_id}/thesis-plans/{chat_session_id}/{normalized_filename}"

    def _build_thesis_pdf_storage_path(
        self,
        user_id: str,
        chat_session_id: str,
        filename: str,
    ) -> str:
        normalized_filename = self._normalize_filename(filename)
        return f"{user_id}/theses/{chat_session_id}/{normalized_filename}"

    def _resolve_pdf_storage_path(
        self,
        user_id: str,
        document_id: str,
        filename: str,
        pdf_storage_path: str | None = None,
    ) -> str:
        persisted_path = (pdf_storage_path or "").strip()
        if persisted_path:
            return persisted_path

        return self._build_pdf_storage_path(user_id, document_id, filename)

    def resolve_document_pdf_storage_path(
        self,
        user_id: str,
        document_id: str,
        filename: str,
        pdf_storage_path: str | None = None,
    ) -> str:
        return self._resolve_pdf_storage_path(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            pdf_storage_path=pdf_storage_path,
        )

    @staticmethod
    def _extract_signed_url(payload: object) -> str | None:
        if isinstance(payload, dict):
            url = (
                payload.get("signedURL")
                or payload.get("signedUrl")
                or payload.get("signed_url")
            )
            if isinstance(url, str) and url.strip():
                return url

        url_attr = getattr(payload, "signedURL", None) or getattr(payload, "signed_url", None)
        if isinstance(url_attr, str) and url_attr.strip():
            return url_attr

        return None

    def _ensure_storage_bucket(self) -> None:
        if self._storage_bucket_ready:
            return

        client = self._get_client()
        bucket_name = self.settings.supabase_storage_bucket

        bucket_exists = False
        try:
            buckets = client.storage.list_buckets() or []
            for bucket in buckets:
                name = bucket.get("name") if isinstance(bucket, dict) else getattr(bucket, "name", None)
                if name == bucket_name:
                    bucket_exists = True
                    break
        except Exception:
            bucket_exists = False

        if not bucket_exists:
            try:
                client.storage.create_bucket(bucket_name, options={"public": False})
            except TypeError:
                client.storage.create_bucket(bucket_name)
            except Exception as error:
                message = str(error).lower()
                if "exists" not in message and "duplicate" not in message and "already" not in message:
                    raise SupabaseRepositoryError(
                        f"No se pudo crear bucket de storage '{bucket_name}'."
                    ) from error

        self._storage_bucket_ready = True

    def _upload_pdf_to_storage(self, storage_path: str, file_bytes: bytes) -> None:
        if not file_bytes:
            raise SupabaseRepositoryError("No se puede subir un PDF vacio.")

        client = self._get_client()
        self._ensure_storage_bucket()

        bucket_name = self.settings.supabase_storage_bucket
        bucket = client.storage.from_(bucket_name)

        try:
            bucket.upload(
                path=storage_path,
                file=file_bytes,
                file_options={
                    "content-type": "application/pdf",
                    "upsert": "true",
                },
            )
        except TypeError:
            bucket.upload(
                storage_path,
                file_bytes,
                {"content-type": "application/pdf", "upsert": "true"},
            )
        except Exception as error:
            raise SupabaseRepositoryError("No se pudo almacenar el PDF en Supabase Storage.") from error

    def upload_document_pdf(
        self,
        user_id: str,
        document_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> str:
        storage_path = self._build_pdf_storage_path(user_id, document_id, filename)
        self._upload_pdf_to_storage(storage_path, file_bytes)
        return storage_path

    def upload_thesis_plan_pdf(
        self,
        user_id: str,
        chat_session_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> str:
        storage_path = self._build_thesis_plan_pdf_storage_path(
            user_id=user_id,
            chat_session_id=chat_session_id,
            filename=filename,
        )
        self._upload_pdf_to_storage(storage_path, file_bytes)
        return storage_path

    def upload_thesis_pdf(
        self,
        user_id: str,
        chat_session_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> str:
        storage_path = self._build_thesis_pdf_storage_path(
            user_id=user_id,
            chat_session_id=chat_session_id,
            filename=filename,
        )
        self._upload_pdf_to_storage(storage_path, file_bytes)
        return storage_path

    def get_document_pdf_url(
        self,
        user_id: str,
        document_id: str,
        filename: str,
        pdf_storage_path: str | None = None,
    ) -> str | None:
        client = self._get_client()
        self._ensure_storage_bucket()

        bucket_name = self.settings.supabase_storage_bucket
        storage_path = self._resolve_pdf_storage_path(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            pdf_storage_path=pdf_storage_path,
        )
        bucket = client.storage.from_(bucket_name)

        try:
            result = bucket.create_signed_url(
                storage_path,
                self.settings.supabase_storage_signed_url_expires_seconds,
            )
        except TypeError:
            result = bucket.create_signed_url(
                path=storage_path,
                expires_in=self.settings.supabase_storage_signed_url_expires_seconds,
            )
        except Exception:
            return None

        signed_url = self._extract_signed_url(result)
        if not signed_url:
            return None

        if signed_url.startswith("http"):
            return signed_url

        base_url = self.settings.supabase_url.rstrip("/")
        if signed_url.startswith("/"):
            return f"{base_url}{signed_url}"

        return f"{base_url}/{signed_url}"

    def create_document(self, user_id: str, filename: str) -> dict:
        client = self._get_client()
        response = (
            client.table("documents")
            .insert(
                {
                    "user_id": user_id,
                    "filename": filename,
                }
            )
            .execute()
        )

        if not response.data:
            raise SupabaseRepositoryError("No se pudo registrar el documento en Supabase.")

        return response.data[0]

    def update_document_pdf_metadata(
        self,
        document_id: str,
        pdf_storage_path: str,
        pdf_size_bytes: int,
        pdf_mime_type: str = "application/pdf",
    ) -> dict:
        clean_storage_path = (pdf_storage_path or "").strip()
        if not clean_storage_path:
            raise SupabaseRepositoryError(
                "La ruta de storage del PDF es obligatoria para actualizar metadatos."
            )

        safe_size_bytes = max(int(pdf_size_bytes), 0)
        safe_mime_type = (pdf_mime_type or "application/pdf").strip() or "application/pdf"

        client = self._get_client()
        try:
            response = (
                client.table("documents")
                .update(
                    {
                        "pdf_storage_path": clean_storage_path,
                        "pdf_size_bytes": safe_size_bytes,
                        "pdf_mime_type": safe_mime_type,
                    }
                )
                .eq("id", document_id)
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error):
                LOGGER.warning(
                    "No se pudieron guardar metadatos PDF por columnas faltantes en documents. "
                    "Ejecuta backend/sql/schema.sql para habilitar pdf_storage_path/pdf_size_bytes/pdf_mime_type."
                )
                return {
                    "id": document_id,
                    "pdf_storage_path": clean_storage_path,
                    "pdf_size_bytes": safe_size_bytes,
                    "pdf_mime_type": safe_mime_type,
                }

            raise SupabaseRepositoryError(
                "No se pudieron guardar los metadatos del PDF en Supabase."
            ) from error

        if not response.data:
            raise SupabaseRepositoryError(
                "No se pudieron guardar los metadatos del PDF en Supabase."
            )

        return response.data[0]

    def delete_document_pdf(self, pdf_storage_path: str) -> None:
        storage_path = (pdf_storage_path or "").strip()
        if not storage_path:
            return

        client = self._get_client()
        self._ensure_storage_bucket()

        bucket_name = self.settings.supabase_storage_bucket
        bucket = client.storage.from_(bucket_name)

        try:
            bucket.remove([storage_path])
        except Exception as error:
            message = str(error).lower()
            if "not found" in message or "no such" in message:
                return
            raise SupabaseRepositoryError(
                "No se pudo eliminar el PDF desde Supabase Storage."
            ) from error

    def delete_document(self, document_id: str) -> None:
        client = self._get_client()
        try:
            client.table("documents").delete().eq("id", document_id).execute()
        except Exception as error:
            raise SupabaseRepositoryError(
                "No se pudo eliminar el documento desde Supabase."
            ) from error

    def list_documents(self, user_id: str) -> list[dict]:
        client = self._get_client()
        try:
            response = (
                client.table("documents")
                .select("id, filename, created_at, pdf_storage_path")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error):
                response = (
                    client.table("documents")
                    .select("id, filename, created_at")
                    .eq("user_id", user_id)
                    .order("created_at", desc=True)
                    .execute()
                )
            else:
                raise SupabaseRepositoryError(
                    "No se pudo listar documentos desde Supabase."
                ) from error

        items = response.data or []
        for item in items:
            try:
                item["pdf_url"] = self.get_document_pdf_url(
                    user_id=user_id,
                    document_id=item["id"],
                    filename=item["filename"],
                    pdf_storage_path=item.get("pdf_storage_path"),
                )
            except SupabaseRepositoryError:
                item["pdf_url"] = None

        return items

    def get_document_by_id(self, document_id: str) -> dict | None:
        client = self._get_client()
        try:
            response = (
                client.table("documents")
                .select("id, user_id, filename, created_at, pdf_storage_path")
                .eq("id", document_id)
                .limit(1)
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error):
                response = (
                    client.table("documents")
                    .select("id, user_id, filename, created_at")
                    .eq("id", document_id)
                    .limit(1)
                    .execute()
                )
            else:
                raise SupabaseRepositoryError(
                    "No se pudo recuperar el documento solicitado desde Supabase."
                ) from error

        if not response.data:
            return None

        item = response.data[0]
        try:
            item["pdf_url"] = self.get_document_pdf_url(
                user_id=item["user_id"],
                document_id=item["id"],
                filename=item["filename"],
                pdf_storage_path=item.get("pdf_storage_path"),
            )
        except SupabaseRepositoryError:
            item["pdf_url"] = None
        return item

    def list_chat_sessions(
        self,
        user_id: str,
        document_id: str | None = None,
        mode: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        client = self._get_client()

        select_columns = (
            "id, document_id, mode, title, faculty_id, career_id, source_chat_session_id, "
            "created_at, updated_at, last_message_at"
        )
        query = client.table("chat_sessions").select(select_columns).eq("user_id", user_id)

        if document_id:
            query = query.eq("document_id", document_id)

        if mode:
            query = query.eq("mode", mode)

        try:
            response = (
                query
                .order("last_message_at", desc=True)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
        except Exception as error:
            if self._is_missing_academic_profile_schema(error):
                fallback_query = (
                    client.table("chat_sessions")
                    .select("id, document_id, mode, title, created_at, updated_at, last_message_at")
                    .eq("user_id", user_id)
                )
                if document_id:
                    fallback_query = fallback_query.eq("document_id", document_id)
                if mode:
                    fallback_query = fallback_query.eq("mode", mode)
                response = (
                    fallback_query
                    .order("last_message_at", desc=True)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                return response.data or []

            if mode == "thesis_plan" and (
                self._is_missing_chat_session_mode_column(error)
                or self._is_thesis_plan_session_schema_error(error)
            ):
                raise SupabaseRepositoryError(
                    self._thesis_plan_schema_error_message()
                ) from error
            if mode == "thesis" and (
                self._is_missing_chat_session_mode_column(error)
                or self._is_thesis_plan_session_schema_error(error)
            ):
                raise SupabaseRepositoryError(
                    self._thesis_plan_schema_error_message()
                ) from error

            raise SupabaseRepositoryError(
                "No se pudieron listar las sesiones de chat desde Supabase."
            ) from error

        return response.data or []

    def create_chat_session(
        self,
        user_id: str,
        document_id: str | None,
        mode: str,
        title: str | None = None,
        faculty_id: str | None = None,
        career_id: str | None = None,
        source_chat_session_id: str | None = None,
    ) -> dict:
        default_titles = {
            "pdf_chat": "Nuevo chat PDF",
            "thesis_review": "Nueva revision",
            "thesis_plan": "Nuevo plan de tesis",
            "thesis": "Nueva tesis",
        }
        default_title = default_titles.get(mode, "Nuevo chat")
        safe_title = self._normalize_chat_title(title, default_title=default_title)

        client = self._get_client()
        payload = {
            "user_id": user_id,
            "document_id": document_id,
            "mode": mode,
            "title": safe_title,
        }
        if faculty_id and career_id:
            payload["faculty_id"] = faculty_id
            payload["career_id"] = career_id
        if source_chat_session_id:
            payload["source_chat_session_id"] = source_chat_session_id

        try:
            response = (
                client.table("chat_sessions")
                .insert(payload)
                .execute()
            )
        except Exception as error:
            if mode in {"thesis_plan", "thesis"} and self._is_thesis_plan_session_schema_error(error):
                raise SupabaseRepositoryError(
                    self._thesis_plan_schema_error_message()
                ) from error

            if self._is_missing_academic_profile_schema(error):
                raise SupabaseRepositoryError(
                    self._academic_profile_schema_error_message()
                ) from error

            raise SupabaseRepositoryError("No se pudo crear la sesion de chat en Supabase.") from error

        if not response.data:
            raise SupabaseRepositoryError(
                "No se pudo crear la sesion de chat en Supabase."
            )

        return response.data[0]

    def get_chat_session_by_id(self, chat_session_id: str) -> dict | None:
        client = self._get_client()

        try:
            response = (
                client.table("chat_sessions")
                .select(
                    "id, user_id, document_id, mode, title, faculty_id, career_id, "
                    "source_chat_session_id, created_at, updated_at, last_message_at"
                )
                .eq("id", chat_session_id)
                .limit(1)
                .execute()
            )
        except Exception as error:
            if self._is_missing_academic_profile_schema(error):
                response = (
                    client.table("chat_sessions")
                    .select("id, user_id, document_id, mode, title, created_at, updated_at, last_message_at")
                    .eq("id", chat_session_id)
                    .limit(1)
                    .execute()
                )
                if not response.data:
                    return None
                return response.data[0]

            if self._is_missing_chat_session_mode_column(error):
                raise SupabaseRepositoryError(
                    "La tabla chat_sessions no tiene la columna mode requerida. "
                    "Ejecuta backend/sql/schema.sql en Supabase antes de usar chats y planes."
                ) from error

            raise SupabaseRepositoryError(
                "No se pudo recuperar la sesion de chat desde Supabase."
            ) from error

        if not response.data:
            return None

        return response.data[0]

    def update_chat_session_title_from_user_message(
        self,
        chat_session_id: str,
        user_message: str,
    ) -> None:
        candidate_title = self._normalize_chat_title(user_message, default_title="")
        if not candidate_title:
            return

        client = self._get_client()

        try:
            current = (
                client.table("chat_sessions")
                .select("title")
                .eq("id", chat_session_id)
                .limit(1)
                .execute()
            )
        except Exception:
            return

        if not current.data:
            return

        current_title = (current.data[0].get("title") or "").strip().lower()
        generic_titles = {
            "",
            "nuevo chat",
            "nuevo chat pdf",
            "nueva revision",
            "nuevo plan de tesis",
            "plan de tesis",
        }
        if current_title not in generic_titles:
            return

        try:
            client.table("chat_sessions").update({"title": candidate_title}).eq("id", chat_session_id).execute()
        except Exception:
            return

    def list_chat_messages(self, chat_session_id: str, limit: int = 300) -> list[dict]:
        client = self._get_client()

        try:
            response = (
                client.table("chat_messages")
                .select("id, chat_session_id, role, content, created_at")
                .eq("chat_session_id", chat_session_id)
                .order("id")
                .limit(limit)
                .execute()
            )
        except Exception as error:
            raise SupabaseRepositoryError(
                "No se pudieron recuperar los mensajes del chat desde Supabase."
            ) from error

        return response.data or []

    def create_chat_message(
        self,
        chat_session_id: str,
        role: str,
        content: str,
    ) -> dict:
        clean_content = (content or "").strip()
        if not clean_content:
            raise SupabaseRepositoryError("No se puede guardar un mensaje vacio en el chat.")

        client = self._get_client()

        try:
            response = (
                client.table("chat_messages")
                .insert(
                    {
                        "chat_session_id": chat_session_id,
                        "role": role,
                        "content": clean_content,
                    }
                )
                .execute()
            )
        except Exception as error:
            raise SupabaseRepositoryError(
                "No se pudo guardar el mensaje del chat en Supabase."
            ) from error

        if not response.data:
            raise SupabaseRepositoryError(
                "No se pudo guardar el mensaje del chat en Supabase."
            )

        if role == "user":
            self.update_chat_session_title_from_user_message(chat_session_id, clean_content)

        return response.data[0]

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(UTC).isoformat()

    def create_thesis_plan_auto_job(
        self,
        user_id: str,
        chat_session_id: str,
        selected_problem: dict,
        ai_provider: str,
        ai_model: str | None,
        faculty_id: str | None = None,
        career_id: str | None = None,
    ) -> dict:
        title = " ".join(str((selected_problem or {}).get("title") or "").split())
        problem = " ".join(str((selected_problem or {}).get("problem") or title).split())
        if not problem:
            problem = "Plan automatico de tesis"

        client = self._get_client()
        payload = {
            "user_id": user_id,
            "chat_session_id": chat_session_id,
            "problem": problem[:1200],
            "search_query": title[:500] if title else problem[:500],
            "status": "pending",
            "total_sources": 7,
            "found_sources": 0,
            "progress_percent": 0,
            "progress_label": "En cola para generar el plan",
            "job_type": "auto_thesis_plan",
            "selected_problem": selected_problem or {},
            "ai_provider": ai_provider,
            "ai_model": ai_model,
            "faculty_id": faculty_id,
            "career_id": career_id,
            "error_message": None,
        }

        try:
            response = client.table("thesis_problem_jobs").insert(payload).execute()
        except Exception as error:
            if self._is_missing_academic_profile_schema(error):
                raise SupabaseRepositoryError(
                    self._academic_profile_schema_error_message()
                ) from error
            raise SupabaseRepositoryError(
                "No se pudo crear el trabajo automatico de plan de tesis en Supabase."
            ) from error

        if not response.data:
            raise SupabaseRepositoryError(
                "No se pudo crear el trabajo automatico de plan de tesis en Supabase."
            )

        return response.data[0]

    def list_thesis_plan_auto_jobs(self, user_id: str, limit: int = 10) -> list[dict]:
        client = self._get_client()
        safe_limit = min(max(int(limit or 10), 1), 50)
        select_columns = (
            "id, chat_session_id, status, progress_percent, progress_label, "
            "error_message, selected_problem, ai_provider, ai_model, faculty_id, career_id, created_at, "
            "updated_at, started_at, completed_at, notified_at, pdf_storage_path, "
            "pdf_filename, pdf_size_bytes, pdf_mime_type, pdf_generated_at"
        )
        try:
            response = (
                client.table("thesis_problem_jobs")
                .select(select_columns)
                .eq("user_id", user_id)
                .eq("job_type", "auto_thesis_plan")
                .order("created_at", desc=True)
                .limit(safe_limit)
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error) or self._is_missing_academic_profile_schema(error):
                response = (
                    client.table("thesis_problem_jobs")
                    .select(
                        "id, chat_session_id, status, progress_percent, progress_label, "
                        "error_message, selected_problem, ai_provider, ai_model, created_at, "
                        "updated_at, started_at, completed_at, notified_at"
                    )
                    .eq("user_id", user_id)
                    .eq("job_type", "auto_thesis_plan")
                    .order("created_at", desc=True)
                    .limit(safe_limit)
                    .execute()
                )
            else:
                raise SupabaseRepositoryError(
                    "No se pudieron listar los trabajos automaticos de plan de tesis."
                ) from error

        return response.data or []

    def get_thesis_plan_auto_job(self, job_id: str, user_id: str) -> dict | None:
        client = self._get_client()
        select_columns = (
            "id, user_id, chat_session_id, status, progress_percent, progress_label, "
            "error_message, selected_problem, ai_provider, ai_model, faculty_id, career_id, created_at, "
            "updated_at, started_at, completed_at, notified_at, pdf_storage_path, "
            "pdf_filename, pdf_size_bytes, pdf_mime_type, pdf_generated_at"
        )
        try:
            response = (
                client.table("thesis_problem_jobs")
                .select(select_columns)
                .eq("id", job_id)
                .eq("user_id", user_id)
                .eq("job_type", "auto_thesis_plan")
                .limit(1)
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error) or self._is_missing_academic_profile_schema(error):
                response = (
                    client.table("thesis_problem_jobs")
                    .select(
                        "id, user_id, chat_session_id, status, progress_percent, progress_label, "
                        "error_message, selected_problem, ai_provider, ai_model, created_at, "
                        "updated_at, started_at, completed_at, notified_at"
                    )
                    .eq("id", job_id)
                    .eq("user_id", user_id)
                    .eq("job_type", "auto_thesis_plan")
                    .limit(1)
                    .execute()
                )
            else:
                raise SupabaseRepositoryError(
                    "No se pudo recuperar el trabajo automatico de plan de tesis."
                ) from error

        if not response.data:
            return None

        return response.data[0]

    def update_thesis_plan_auto_job_pdf_metadata(
        self,
        job_id: str,
        *,
        pdf_storage_path: str,
        pdf_filename: str,
        pdf_size_bytes: int,
        pdf_mime_type: str = "application/pdf",
    ) -> dict | None:
        clean_storage_path = (pdf_storage_path or "").strip()
        clean_filename = (pdf_filename or "").strip()
        if not clean_storage_path:
            raise SupabaseRepositoryError(
                "La ruta de storage del PDF del plan es obligatoria."
            )
        if not clean_filename:
            clean_filename = self._normalize_filename("plan_de_tesis.pdf")

        payload = {
            "pdf_storage_path": clean_storage_path,
            "pdf_filename": self._normalize_filename(clean_filename),
            "pdf_size_bytes": max(int(pdf_size_bytes), 0),
            "pdf_mime_type": (pdf_mime_type or "application/pdf").strip() or "application/pdf",
            "pdf_generated_at": self._utc_now_iso(),
            "updated_at": self._utc_now_iso(),
        }

        client = self._get_client()
        try:
            response = (
                client.table("thesis_problem_jobs")
                .update(payload)
                .eq("id", job_id)
                .eq("job_type", "auto_thesis_plan")
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error):
                LOGGER.warning(
                    "El PDF del plan se subio a Storage, pero no se pudieron guardar "
                    "metadatos en thesis_problem_jobs. Ejecuta backend/sql/schema.sql."
                )
                return {"id": job_id, **payload}

            raise SupabaseRepositoryError(
                "No se pudieron guardar los metadatos del PDF del plan de tesis."
            ) from error

        if not response.data:
            return None

        return response.data[0]

    def update_thesis_plan_auto_job_pdf_metadata_for_chat(
        self,
        *,
        chat_session_id: str,
        user_id: str,
        pdf_storage_path: str,
        pdf_filename: str,
        pdf_size_bytes: int,
        pdf_mime_type: str = "application/pdf",
    ) -> dict | None:
        clean_storage_path = (pdf_storage_path or "").strip()
        clean_filename = (pdf_filename or "").strip()
        if not clean_storage_path:
            raise SupabaseRepositoryError(
                "La ruta de storage del PDF del plan es obligatoria."
            )
        if not clean_filename:
            clean_filename = self._normalize_filename("plan_de_tesis.pdf")

        payload = {
            "pdf_storage_path": clean_storage_path,
            "pdf_filename": self._normalize_filename(clean_filename),
            "pdf_size_bytes": max(int(pdf_size_bytes), 0),
            "pdf_mime_type": (pdf_mime_type or "application/pdf").strip() or "application/pdf",
            "pdf_generated_at": self._utc_now_iso(),
            "updated_at": self._utc_now_iso(),
        }

        client = self._get_client()
        try:
            response = (
                client.table("thesis_problem_jobs")
                .update(payload)
                .eq("chat_session_id", chat_session_id)
                .eq("user_id", user_id)
                .eq("job_type", "auto_thesis_plan")
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error):
                LOGGER.warning(
                    "El PDF del plan se subio a Storage, pero no se pudieron guardar "
                    "metadatos en thesis_problem_jobs. Ejecuta backend/sql/schema.sql."
                )
                return {"chat_session_id": chat_session_id, **payload}

            raise SupabaseRepositoryError(
                "No se pudieron guardar los metadatos del PDF del plan de tesis."
            ) from error

        if not response.data:
            return None

        return response.data[0]

    def update_thesis_plan_auto_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        found_sources: int | None = None,
        progress_percent: int | None = None,
        progress_label: str | None = None,
        error_message: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict | None:
        payload: dict[str, object] = {
            "updated_at": self._utc_now_iso(),
        }
        if status is not None:
            payload["status"] = status
        if found_sources is not None:
            payload["found_sources"] = max(int(found_sources), 0)
        if progress_percent is not None:
            payload["progress_percent"] = min(max(int(progress_percent), 0), 100)
        if progress_label is not None:
            payload["progress_label"] = progress_label
        if error_message is not None:
            payload["error_message"] = error_message
        if started_at is not None:
            payload["started_at"] = started_at
        if completed_at is not None:
            payload["completed_at"] = completed_at

        client = self._get_client()
        try:
            response = (
                client.table("thesis_problem_jobs")
                .update(payload)
                .eq("id", job_id)
                .eq("job_type", "auto_thesis_plan")
                .execute()
            )
        except Exception as error:
            raise SupabaseRepositoryError(
                "No se pudo actualizar el trabajo automatico de plan de tesis."
            ) from error

        if not response.data:
            return None

        return response.data[0]

    def mark_thesis_plan_auto_job_notified(self, job_id: str, user_id: str) -> dict | None:
        client = self._get_client()
        try:
            response = (
                client.table("thesis_problem_jobs")
                .update(
                    {
                        "notified_at": self._utc_now_iso(),
                        "updated_at": self._utc_now_iso(),
                    }
                )
                .eq("id", job_id)
                .eq("user_id", user_id)
                .eq("job_type", "auto_thesis_plan")
                .execute()
            )
        except Exception as error:
            raise SupabaseRepositoryError(
                "No se pudo marcar como notificado el plan automatico."
            ) from error

        if not response.data:
            return None

        return response.data[0]

    def create_thesis_auto_job(
        self,
        user_id: str,
        chat_session_id: str,
        source_plan_chat_id: str,
        source_plan_title: str,
        formal_data: dict,
        ai_provider: str,
        ai_model: str | None,
        faculty_id: str | None = None,
        career_id: str | None = None,
    ) -> dict:
        clean_title = " ".join((source_plan_title or "Tesis desde plan").split())
        selected_payload = {
            "source_plan_chat_id": source_plan_chat_id,
            "source_plan_title": clean_title,
            "formal_data": formal_data or {},
        }

        client = self._get_client()
        payload = {
            "user_id": user_id,
            "chat_session_id": chat_session_id,
            "problem": f"Tesis automatica desde plan: {clean_title}"[:1200],
            "search_query": clean_title[:500],
            "status": "pending",
            "total_sources": 8,
            "found_sources": 0,
            "progress_percent": 0,
            "progress_label": "En cola para generar la tesis",
            "job_type": "auto_thesis",
            "selected_problem": selected_payload,
            "ai_provider": ai_provider,
            "ai_model": ai_model,
            "faculty_id": faculty_id,
            "career_id": career_id,
            "error_message": None,
        }

        try:
            response = client.table("thesis_problem_jobs").insert(payload).execute()
        except Exception as error:
            if self._is_missing_academic_profile_schema(error):
                raise SupabaseRepositoryError(
                    self._academic_profile_schema_error_message()
                ) from error
            raise SupabaseRepositoryError(
                "No se pudo crear el trabajo automatico de tesis en Supabase."
            ) from error

        if not response.data:
            raise SupabaseRepositoryError(
                "No se pudo crear el trabajo automatico de tesis en Supabase."
            )

        return response.data[0]

    def list_thesis_auto_jobs(self, user_id: str, limit: int = 10) -> list[dict]:
        client = self._get_client()
        safe_limit = min(max(int(limit or 10), 1), 50)
        select_columns = (
            "id, chat_session_id, status, progress_percent, progress_label, "
            "error_message, selected_problem, ai_provider, ai_model, faculty_id, career_id, created_at, "
            "updated_at, started_at, completed_at, notified_at, pdf_storage_path, "
            "pdf_filename, pdf_size_bytes, pdf_mime_type, pdf_generated_at"
        )
        try:
            response = (
                client.table("thesis_problem_jobs")
                .select(select_columns)
                .eq("user_id", user_id)
                .eq("job_type", "auto_thesis")
                .order("created_at", desc=True)
                .limit(safe_limit)
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error) or self._is_missing_academic_profile_schema(error):
                response = (
                    client.table("thesis_problem_jobs")
                    .select(
                        "id, chat_session_id, status, progress_percent, progress_label, "
                        "error_message, selected_problem, ai_provider, ai_model, created_at, "
                        "updated_at, started_at, completed_at, notified_at"
                    )
                    .eq("user_id", user_id)
                    .eq("job_type", "auto_thesis")
                    .order("created_at", desc=True)
                    .limit(safe_limit)
                    .execute()
                )
            else:
                raise SupabaseRepositoryError(
                    "No se pudieron listar los trabajos automaticos de tesis."
                ) from error

        return response.data or []

    def update_thesis_auto_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        found_sources: int | None = None,
        progress_percent: int | None = None,
        progress_label: str | None = None,
        error_message: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict | None:
        payload: dict[str, object] = {
            "updated_at": self._utc_now_iso(),
        }
        if status is not None:
            payload["status"] = status
        if found_sources is not None:
            payload["found_sources"] = max(int(found_sources), 0)
        if progress_percent is not None:
            payload["progress_percent"] = min(max(int(progress_percent), 0), 100)
        if progress_label is not None:
            payload["progress_label"] = progress_label
        if error_message is not None:
            payload["error_message"] = error_message
        if started_at is not None:
            payload["started_at"] = started_at
        if completed_at is not None:
            payload["completed_at"] = completed_at

        client = self._get_client()
        try:
            response = (
                client.table("thesis_problem_jobs")
                .update(payload)
                .eq("id", job_id)
                .eq("job_type", "auto_thesis")
                .execute()
            )
        except Exception as error:
            raise SupabaseRepositoryError(
                "No se pudo actualizar el trabajo automatico de tesis."
            ) from error

        if not response.data:
            return None

        return response.data[0]

    def update_thesis_auto_job_pdf_metadata(
        self,
        job_id: str,
        *,
        pdf_storage_path: str,
        pdf_filename: str,
        pdf_size_bytes: int,
        pdf_mime_type: str = "application/pdf",
    ) -> dict | None:
        clean_storage_path = (pdf_storage_path or "").strip()
        clean_filename = (pdf_filename or "").strip()
        if not clean_storage_path:
            raise SupabaseRepositoryError(
                "La ruta de storage del PDF de la tesis es obligatoria."
            )
        if not clean_filename:
            clean_filename = self._normalize_filename("tesis.pdf")

        payload = {
            "pdf_storage_path": clean_storage_path,
            "pdf_filename": self._normalize_filename(clean_filename),
            "pdf_size_bytes": max(int(pdf_size_bytes), 0),
            "pdf_mime_type": (pdf_mime_type or "application/pdf").strip() or "application/pdf",
            "pdf_generated_at": self._utc_now_iso(),
            "updated_at": self._utc_now_iso(),
        }

        client = self._get_client()
        try:
            response = (
                client.table("thesis_problem_jobs")
                .update(payload)
                .eq("id", job_id)
                .eq("job_type", "auto_thesis")
                .execute()
            )
        except Exception as error:
            if self._is_missing_pdf_metadata_columns(error):
                LOGGER.warning(
                    "El PDF de la tesis se subio a Storage, pero no se pudieron guardar "
                    "metadatos en thesis_problem_jobs. Ejecuta backend/sql/schema.sql."
                )
                return {"id": job_id, **payload}

            raise SupabaseRepositoryError(
                "No se pudieron guardar los metadatos del PDF de la tesis."
            ) from error

        if not response.data:
            return None

        return response.data[0]

    def mark_thesis_auto_job_notified(self, job_id: str, user_id: str) -> dict | None:
        client = self._get_client()
        try:
            response = (
                client.table("thesis_problem_jobs")
                .update(
                    {
                        "notified_at": self._utc_now_iso(),
                        "updated_at": self._utc_now_iso(),
                    }
                )
                .eq("id", job_id)
                .eq("user_id", user_id)
                .eq("job_type", "auto_thesis")
                .execute()
            )
        except Exception as error:
            raise SupabaseRepositoryError(
                "No se pudo marcar como notificada la tesis automatica."
            ) from error

        if not response.data:
            return None

        return response.data[0]

    def get_user_academic_profile(self, user_id: str) -> dict | None:
        client = self._get_client()
        try:
            response = (
                client.table("user_academic_profiles")
                .select("user_id, faculty_id, career_id, created_at, updated_at")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        except Exception as error:
            if self._is_missing_academic_profile_schema(error):
                raise SupabaseRepositoryError(
                    self._academic_profile_schema_error_message()
                ) from error
            raise SupabaseRepositoryError(
                "No se pudo recuperar el perfil academico desde Supabase."
            ) from error

        if not response.data:
            return None
        return response.data[0]

    def upsert_user_academic_profile(
        self,
        user_id: str,
        faculty_id: str,
        career_id: str,
    ) -> dict:
        payload = {
            "user_id": user_id,
            "faculty_id": faculty_id,
            "career_id": career_id,
            "updated_at": self._utc_now_iso(),
        }

        client = self._get_client()
        try:
            response = (
                client.table("user_academic_profiles")
                .upsert(payload, on_conflict="user_id")
                .execute()
            )
        except TypeError:
            try:
                response = (
                    client.table("user_academic_profiles")
                    .upsert(payload)
                    .execute()
                )
            except Exception as error:
                if self._is_missing_academic_profile_schema(error):
                    raise SupabaseRepositoryError(
                        self._academic_profile_schema_error_message()
                    ) from error
                raise SupabaseRepositoryError(
                    "No se pudo guardar el perfil academico en Supabase."
                ) from error
        except Exception as error:
            if self._is_missing_academic_profile_schema(error):
                raise SupabaseRepositoryError(
                    self._academic_profile_schema_error_message()
                ) from error
            raise SupabaseRepositoryError(
                "No se pudo guardar el perfil academico en Supabase."
            ) from error

        if not response.data:
            raise SupabaseRepositoryError(
                "No se pudo guardar el perfil academico en Supabase."
            )

        return response.data[0]

    def insert_document_chunks(
        self,
        document_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise SupabaseRepositoryError(
                "La cantidad de chunks no coincide con la cantidad de embeddings."
            )

        if not chunks:
            return 0

        current_dimension = len(embeddings[0]) if embeddings else 0
        target_dimension = self._resolve_target_vector_dimension(current_dimension)
        normalized_embeddings = [
            self._coerce_embedding_dimension(embedding, target_dimension)
            for embedding in embeddings
        ]
        rows = self._build_chunk_rows(document_id, chunks, normalized_embeddings)

        try:
            self._insert_chunk_rows_in_batches(rows)
            return len(rows)
        except Exception as error:
            if not self._is_vector_dimension_mismatch(error):
                raise SupabaseRepositoryError(
                    "No se pudieron guardar los fragmentos del documento en Supabase."
                ) from error

            expected_dimension = self._extract_expected_vector_dimension(error)
            if not expected_dimension:
                raise SupabaseRepositoryError(
                    "No se pudieron guardar los fragmentos por incompatibilidad de dimensiones vectoriales."
                ) from error

            self._vector_dimension_override = expected_dimension
            LOGGER.warning(
                "Dimension vectorial incompatible al insertar chunks. Reintentando con %s dimensiones.",
                expected_dimension,
            )
            adjusted_embeddings = [
                self._coerce_embedding_dimension(embedding, expected_dimension)
                for embedding in embeddings
            ]
            adjusted_rows = self._build_chunk_rows(document_id, chunks, adjusted_embeddings)

            try:
                self._insert_chunk_rows_in_batches(adjusted_rows)
                return len(adjusted_rows)
            except Exception as retry_error:
                raise SupabaseRepositoryError(
                    "No se pudieron guardar los fragmentos del documento en Supabase."
                ) from retry_error

    def list_document_chunks(self, document_id: str, limit: int = 3000) -> list[str]:
        client = self._get_client()

        response = (
            client.table("document_chunks")
            .select("content")
            .eq("document_id", document_id)
            .order("id")
            .limit(limit)
            .execute()
        )

        rows = response.data or []
        return [
            content
            for row in rows
            for content in [(row.get("content") or "").strip()]
            if content
        ]

    def match_document_chunks(
        self,
        document_id: str,
        query_embedding: list[float],
        match_count: int = 5,
        query_text: str | None = None,
    ) -> list[dict]:
        client = self._get_client()

        working_embedding = self._coerce_embedding_dimension(
            query_embedding,
            self._resolve_target_vector_dimension(len(query_embedding)),
        )

        def _run_match(embedding_values: list[float]) -> list[dict]:
            response = client.rpc(
                "match_document_chunks",
                {
                    "match_document_id": document_id,
                    "query_embedding": self._to_pgvector(embedding_values),
                    "match_count": match_count,
                },
            ).execute()
            return response.data or []

        try:
            return _run_match(working_embedding)
        except Exception as error:
            if self._is_vector_dimension_mismatch(error):
                expected_dimension = self._extract_expected_vector_dimension(error)
                if expected_dimension:
                    self._vector_dimension_override = expected_dimension
                    adjusted_embedding = self._coerce_embedding_dimension(
                        query_embedding,
                        expected_dimension,
                    )
                    if adjusted_embedding != working_embedding:
                        try:
                            return _run_match(adjusted_embedding)
                        except Exception:
                            pass

                LOGGER.warning(
                    "Fallo match vectorial por dimensiones incompatibles. "
                    "Activando fallback por texto para document_id=%s",
                    document_id,
                )
                return self._fallback_match_document_chunks_text(
                    document_id=document_id,
                    query_text=query_text,
                    match_count=match_count,
                )

            raise SupabaseRepositoryError(
                "No se pudo recuperar contexto del documento desde Supabase."
            ) from error

    def match_document_chunks_by_text(
        self,
        document_id: str,
        query_text: str,
        match_count: int = 5,
    ) -> list[dict]:
        try:
            return self._fallback_match_document_chunks_text(
                document_id=document_id,
                query_text=query_text,
                match_count=match_count,
            )
        except Exception as error:
            raise SupabaseRepositoryError(
                "No se pudo recuperar contexto textual del documento desde Supabase."
            ) from error


supabase_repository = SupabaseRepository()
