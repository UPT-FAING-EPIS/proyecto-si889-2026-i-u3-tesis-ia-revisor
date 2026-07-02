"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import ChatWindow from "../../components/ChatWindow";
import PDFViewer from "../../components/PDFViewer";
import ThesisPanel from "../../components/ThesisPanel";
import ThesisPlanPanel from "../../components/ThesisPlanPanel";
import UploadZone from "../../components/UploadZone";
import {
  deleteDocument,
  downloadThesisPlanPdf,
  fetchAcademicCatalog,
  fetchAcademicProfile,
  listAutomaticThesisPlanJobs,
  listDocuments,
  markAutomaticThesisPlanJobNotified,
  saveAcademicProfile,
  uploadDocument,
} from "../../lib/api";
import { useAuth } from "../../lib/providers/AuthProvider";

const AI_MODEL_OPTIONS = [
  {
    id: "gemini:gemini-2.0-flash",
    provider: "gemini",
    model: "gemini-2.0-flash",
    label: "Gemini",
    detail: "gemini-2.0-flash",
  },
  {
    id: "deepseek:deepseek-v4-pro",
    provider: "deepseek",
    model: "deepseek-v4-pro",
    label: "DeepSeek V4",
    detail: "deepseek-v4-pro",
  },
];

function AcademicProfileSelector({
  catalog,
  profile,
  isSaving,
  onSave,
  onCancel,
}) {
  const [facultyId, setFacultyId] = useState(profile?.faculty_id || catalog[0]?.id || "");
  const [careerId, setCareerId] = useState(profile?.career_id || catalog[0]?.careers?.[0]?.id || "");

  useEffect(() => {
    const nextFacultyId = profile?.faculty_id || catalog[0]?.id || "";
    const nextFaculty = catalog.find((faculty) => faculty.id === nextFacultyId) || catalog[0];
    setFacultyId(nextFaculty?.id || "");
    setCareerId(profile?.career_id || nextFaculty?.careers?.[0]?.id || "");
  }, [catalog, profile]);

  const selectedFaculty = catalog.find((faculty) => faculty.id === facultyId) || catalog[0];
  const careers = selectedFaculty?.careers || [];

  const handleFacultyChange = (event) => {
    const nextFacultyId = event.target.value;
    const nextFaculty = catalog.find((faculty) => faculty.id === nextFacultyId);
    setFacultyId(nextFacultyId);
    setCareerId(nextFaculty?.careers?.[0]?.id || "");
  };

  return (
    <section className="academic-profile-card">
      <div>
        <p className="dashboard-eyebrow">Perfil academico</p>
        <h2>Selecciona tu facultad y carrera</h2>
        <p>
          El plan de tesis se generara con la estructura y el enfoque metodologico de tu carrera.
        </p>
      </div>
      <div className="academic-profile-fields">
        <label>
          <span>Facultad</span>
          <select
            className="field-select"
            value={facultyId}
            onChange={handleFacultyChange}
            disabled={isSaving || !catalog.length}
          >
            {catalog.map((faculty) => (
              <option key={faculty.id} value={faculty.id}>
                {faculty.acronym} - {faculty.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Carrera</span>
          <select
            className="field-select"
            value={careerId}
            onChange={(event) => setCareerId(event.target.value)}
            disabled={isSaving || !careers.length}
          >
            {careers.map((career) => (
              <option key={career.id} value={career.id}>
                {career.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="academic-profile-actions">
        {onCancel ? (
          <button
            type="button"
            className="button button-ghost"
            onClick={onCancel}
            disabled={isSaving}
          >
            Cancelar
          </button>
        ) : null}
        <button
          type="button"
          className="button button-primary"
          disabled={isSaving || !facultyId || !careerId}
          onClick={() => onSave({ facultyId, careerId })}
        >
          {isSaving ? "Guardando..." : "Guardar perfil"}
        </button>
      </div>
    </section>
  );
}

function DashboardPage() {
  const router = useRouter();
  const { user, token, isLoading, logout } = useAuth();

  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedDocumentName, setSelectedDocumentName] = useState("");
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [activeSection, setActiveSection] = useState("chat");
  const [selectedAiModelId, setSelectedAiModelId] = useState(AI_MODEL_OPTIONS[0].id);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [autoPlanJobs, setAutoPlanJobs] = useState([]);
  const [academicCatalog, setAcademicCatalog] = useState([]);
  const [academicProfile, setAcademicProfile] = useState(null);
  const [isLoadingAcademicProfile, setIsLoadingAcademicProfile] = useState(false);
  const [isSavingAcademicProfile, setIsSavingAcademicProfile] = useState(false);
  const [isEditingAcademicProfile, setIsEditingAcademicProfile] = useState(false);
  const [academicProfileError, setAcademicProfileError] = useState("");
  const [isCheckingAutoPlanJobs, setIsCheckingAutoPlanJobs] = useState(false);
  const [isDownloadingAutoPlan, setIsDownloadingAutoPlan] = useState(false);
  const [isDismissingAutoPlan, setIsDismissingAutoPlan] = useState(false);
  const [autoPlanNoticeError, setAutoPlanNoticeError] = useState("");

  const previewUrlRef = useRef("");

  const cleanupPreviewUrl = () => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = "";
    }
  };

  const refreshAutoPlanJobs = async () => {
    if (!token) {
      setAutoPlanJobs([]);
      return;
    }

    setIsCheckingAutoPlanJobs(true);
    try {
      const jobs = await listAutomaticThesisPlanJobs(token, { limit: 12 });
      setAutoPlanJobs(jobs || []);
      setAutoPlanNoticeError("");
    } catch (requestError) {
      setAutoPlanNoticeError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudieron revisar los planes automaticos."
      );
    } finally {
      setIsCheckingAutoPlanJobs(false);
    }
  };

  const refreshDocuments = async ({ resetSelection = false } = {}) => {
    if (!token) {
      return;
    }

    const items = await listDocuments(token);
    const documentsList = items || [];
    setDocuments(documentsList);
    setError("");

    if (!documentsList.length) {
      setSelectedDocumentId("");
      setSelectedDocumentName("");
      cleanupPreviewUrl();
      setPdfPreviewUrl("");
      return;
    }

    const activeDocumentId = resetSelection ? "" : selectedDocumentId;
    if (!activeDocumentId) {
      setSelectedDocumentId("");
      setSelectedDocumentName("");
      cleanupPreviewUrl();
      setPdfPreviewUrl("");
      return;
    }

    const selected = documentsList.find((item) => item.id === activeDocumentId);
    if (!selected) {
      setSelectedDocumentId("");
      setSelectedDocumentName("");
      cleanupPreviewUrl();
      setPdfPreviewUrl("");
      return;
    }

    setSelectedDocumentId(selected.id);
    setSelectedDocumentName(selected.filename);

    if (selected?.pdf_url) {
      cleanupPreviewUrl();
      setPdfPreviewUrl(selected.pdf_url);
    } else {
      cleanupPreviewUrl();
      setPdfPreviewUrl("");
    }
  };

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (!user || !token) {
      router.replace("/login");
      return;
    }

    if (activeSection !== "chat") {
      return;
    }

    void refreshDocuments().catch((requestError) => {
      if (requestError instanceof Error) {
        setError(requestError.message);
      } else {
        setError("No se pudieron cargar tus documentos.");
      }
    });
  }, [activeSection, isLoading, router, token, user]);

  useEffect(() => {
    if (isLoading || !user || !token) {
      return undefined;
    }

    void refreshAutoPlanJobs();
    const intervalId = window.setInterval(() => {
      void refreshAutoPlanJobs();
    }, 12000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [isLoading, token, user]);

  useEffect(() => {
    let cancelled = false;

    const loadAcademicProfile = async () => {
      if (isLoading || !user || !token) {
        return;
      }

      setIsLoadingAcademicProfile(true);
      setAcademicProfileError("");

      try {
        const [catalogRows, profileStatus] = await Promise.all([
          fetchAcademicCatalog(),
          fetchAcademicProfile(token),
        ]);
        if (cancelled) {
          return;
        }
        setAcademicCatalog(catalogRows || []);
        setAcademicProfile(profileStatus?.profile || null);
        setIsEditingAcademicProfile(!profileStatus?.profile);
      } catch (requestError) {
        if (!cancelled) {
          setAcademicProfileError(
            requestError instanceof Error
              ? requestError.message
              : "No se pudo cargar el perfil academico."
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingAcademicProfile(false);
        }
      }
    };

    void loadAcademicProfile();
    return () => {
      cancelled = true;
    };
  }, [isLoading, token, user]);

  useEffect(
    () => () => {
      cleanupPreviewUrl();
    },
    []
  );

  const onUpload = async (file) => {
    if (!token) {
      setError("La sesion ha expirado. Inicia sesion nuevamente.");
      return;
    }

    setIsUploading(true);
    setError("");
    setInfo("");

    try {
      const replaceDocumentId = "";
      const replacingDocument = documents.find((item) => item.id === replaceDocumentId);
      const response = await uploadDocument(token, file, replaceDocumentId);
      await refreshDocuments();

      setSelectedDocumentId(response.document_id);
      setSelectedDocumentName(response.filename);

      cleanupPreviewUrl();
      if (response?.pdf_url) {
        setPdfPreviewUrl(response.pdf_url);
      } else {
        const localUrl = URL.createObjectURL(file);
        previewUrlRef.current = localUrl;
        setPdfPreviewUrl(localUrl);
      }

      const replacedLabel = response?.replaced_document_id
        ? ` Se reemplazo la tesis anterior (${replacingDocument?.filename || response.replaced_document_id}).`
        : "";
      const replaceWarning = response?.replace_warning
        ? ` Advertencia: ${response.replace_warning}`
        : "";

      setInfo(
        `Documento procesado: ${response.filename}. Fragmentos generados: ${response.chunk_count}.${replacedLabel}${replaceWarning}`
      );
    } catch (requestError) {
      if (requestError instanceof Error) {
        setError(requestError.message);
      } else {
        setError("No se pudo procesar el PDF.");
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteDocument = async () => {
    if (!token || !selectedDocumentId || isDeleting) {
      return;
    }

    const selected = documents.find((item) => item.id === selectedDocumentId);
    const selectedName = selected?.filename || "tesis seleccionada";
    const shouldDelete = window.confirm(
      `Se eliminara "${selectedName}" junto a sus chunks y el PDF en storage. ¿Deseas continuar?`
    );

    if (!shouldDelete) {
      return;
    }

    setIsDeleting(true);
    setError("");
    setInfo("");

    try {
      await deleteDocument(token, selectedDocumentId);
      setSelectedDocumentId("");
      setSelectedDocumentName("");
      cleanupPreviewUrl();
      setPdfPreviewUrl("");
      await refreshDocuments({ resetSelection: true });
      setInfo(`Tesis eliminada: ${selectedName}.`);
    } catch (requestError) {
      if (requestError instanceof Error) {
        setError(requestError.message);
      } else {
        setError("No se pudo eliminar la tesis seleccionada.");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDocumentSelect = (event) => {
    const nextDocumentId = event.target.value;
    setSelectedDocumentId(nextDocumentId);

    const selected = documents.find((item) => item.id === nextDocumentId);
    setSelectedDocumentName(selected?.filename || "");

    cleanupPreviewUrl();
    setPdfPreviewUrl(selected?.pdf_url || "");
  };

  const handleSectionChange = (section) => {
    setActiveSection(section);

    if (section === "plan" || section === "thesis") {
      setError("");
      setInfo("");
    }
  };

  const handleSaveAcademicProfile = async ({ facultyId, careerId }) => {
    if (!token || isSavingAcademicProfile) {
      return;
    }

    setIsSavingAcademicProfile(true);
    setAcademicProfileError("");

    try {
      const savedProfile = await saveAcademicProfile(token, { facultyId, careerId });
      setAcademicProfile(savedProfile);
      setIsEditingAcademicProfile(false);
    } catch (requestError) {
      setAcademicProfileError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo guardar el perfil academico."
      );
    } finally {
      setIsSavingAcademicProfile(false);
    }
  };

  const handleAutoJobStarted = (job) => {
    if (!job?.id) {
      void refreshAutoPlanJobs();
      return;
    }

    setAutoPlanJobs((previous) => [
      job,
      ...previous.filter((item) => item.id !== job.id),
    ]);
  };

  const downloadBlob = (blob, filename) => {
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename || "plan_de_tesis.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
  };

  const handleDownloadAutoPlan = async (job) => {
    if (!token || !job?.chat_id || isDownloadingAutoPlan) {
      return;
    }

    setIsDownloadingAutoPlan(true);
    setAutoPlanNoticeError("");

    try {
      const { blob, filename } = await downloadThesisPlanPdf(token, job.chat_id);
      downloadBlob(blob, filename);
      const updatedJob = await markAutomaticThesisPlanJobNotified(token, job.id);
      setAutoPlanJobs((previous) =>
        previous.map((item) => (item.id === updatedJob.id ? updatedJob : item))
      );
    } catch (requestError) {
      setAutoPlanNoticeError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo descargar el PDF del plan automatico."
      );
    } finally {
      setIsDownloadingAutoPlan(false);
    }
  };

  const handleDismissAutoPlanJob = async (job) => {
    if (!token || !job?.id || isDismissingAutoPlan) {
      return;
    }

    setIsDismissingAutoPlan(true);
    setAutoPlanNoticeError("");

    try {
      const updatedJob = await markAutomaticThesisPlanJobNotified(token, job.id);
      setAutoPlanJobs((previous) =>
        previous.map((item) => (item.id === updatedJob.id ? updatedJob : item))
      );
    } catch (requestError) {
      setAutoPlanNoticeError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo cerrar el aviso del plan automatico."
      );
    } finally {
      setIsDismissingAutoPlan(false);
    }
  };

  const isChatSection = activeSection === "chat";
  const isPlanSection = activeSection === "plan";
  const isThesisSection = activeSection === "thesis";
  const selectedAiModel = (
    AI_MODEL_OPTIONS.find((option) => option.id === selectedAiModelId)
    || AI_MODEL_OPTIONS[0]
  );
  const completedAutoPlanJob = autoPlanJobs.find((job) =>
    job.status === "completed" && !job.notified_at && job.chat_id
  );
  const runningAutoPlanJob = autoPlanJobs.find((job) =>
    (job.status === "pending" || job.status === "running") && job.chat_id
  );

  if (isLoading || !user) {
    return (
      <main className="center-screen">
        <div className="loading-card">Cargando panel de tesis...</div>
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-topbar">
        <div>
          <p className="dashboard-eyebrow">Asesor IA de tesis</p>
          <h1>Panel de tesis</h1>
        </div>
        <div className="dashboard-session">
          <label className="model-picker" htmlFor="ai-model-select">
            <span>Modelo IA</span>
            <select
              id="ai-model-select"
              className="field-select model-picker-select"
              value={selectedAiModelId}
              onChange={(event) => setSelectedAiModelId(event.target.value)}
            >
              {AI_MODEL_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label} - {option.detail}
                </option>
              ))}
            </select>
          </label>
          {academicProfile ? (
            <span className="academic-profile-chip">
              {academicProfile.faculty_acronym} - {academicProfile.career_name}
            </span>
          ) : null}
          <span>{user.email || "Usuario"}</span>
          <button
            className="button button-ghost"
            type="button"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
          >
            Cerrar sesion
          </button>
        </div>
      </header>

      <nav className="dashboard-tabs" aria-label="Apartados de trabajo">
        <button
          type="button"
          className={`dashboard-tab ${isChatSection ? "is-active" : ""}`}
          onClick={() => handleSectionChange("chat")}
        >
          Preguntas sobre PDF
        </button>
        <button
          type="button"
          className={`dashboard-tab ${isPlanSection ? "is-active" : ""}`}
          onClick={() => handleSectionChange("plan")}
        >
          Plan de tesis
        </button>
        <button
          type="button"
          className={`dashboard-tab ${isThesisSection ? "is-active" : ""}`}
          onClick={() => handleSectionChange("thesis")}
        >
          Tesis
        </button>
      </nav>

      {academicProfileError ? <p className="inline-error">{academicProfileError}</p> : null}

      {isLoadingAcademicProfile ? (
        <section className="academic-profile-card is-compact">
          <span className="spinner" aria-hidden="true" />
          <p>Cargando perfil academico...</p>
        </section>
      ) : isEditingAcademicProfile || !academicProfile ? (
        <AcademicProfileSelector
          catalog={academicCatalog}
          profile={academicProfile}
          isSaving={isSavingAcademicProfile}
          onSave={handleSaveAcademicProfile}
          onCancel={academicProfile ? () => setIsEditingAcademicProfile(false) : null}
        />
      ) : (
        <section className="academic-profile-strip">
          <div>
            <p className="dashboard-eyebrow">Perfil academico</p>
            <strong>{academicProfile.faculty_acronym} - {academicProfile.career_name}</strong>
            <span>{academicProfile.default_research_line}</span>
          </div>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => setIsEditingAcademicProfile(true)}
          >
            Cambiar
          </button>
        </section>
      )}

      {completedAutoPlanJob ? (
        <section className="auto-plan-notice" aria-live="polite">
          <div>
            <p className="dashboard-eyebrow">Plan automatico listo</p>
            <h2>Tu plan de tesis ya fue creado</h2>
            <p>
              {completedAutoPlanJob.selected_problem?.title
                || "El backend termino de generar el plan automatico."}
            </p>
          </div>
          <div className="auto-plan-notice-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={() => handleSectionChange("plan")}
            >
              Ver plan
            </button>
            <button
              type="button"
              className="button button-special"
              onClick={() => handleDownloadAutoPlan(completedAutoPlanJob)}
              disabled={isDownloadingAutoPlan}
            >
              {isDownloadingAutoPlan ? "Descargando..." : "Descargar PDF"}
            </button>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => handleDismissAutoPlanJob(completedAutoPlanJob)}
              disabled={isDismissingAutoPlan}
            >
              Cerrar aviso
            </button>
          </div>
        </section>
      ) : runningAutoPlanJob ? (
        <section className="auto-plan-notice is-running" aria-live="polite">
          <div>
            <p className="dashboard-eyebrow">Plan automatico en proceso</p>
            <h2>El backend sigue generando tu plan</h2>
            <p>
              {runningAutoPlanJob.progress_label || "Puedes cerrar la pestaña y volver mas tarde."}
              {" "}
              {Number.isFinite(runningAutoPlanJob.progress_percent)
                ? `${runningAutoPlanJob.progress_percent}%`
                : ""}
            </p>
          </div>
          {isCheckingAutoPlanJobs ? <span className="spinner" aria-hidden="true" /> : null}
        </section>
      ) : null}

      {autoPlanNoticeError ? <p className="inline-error">{autoPlanNoticeError}</p> : null}

      {isChatSection ? (
        <section className="dashboard-grid">
          <article className="panel">
            <div className="panel-header">
              <h2>Documento</h2>
              <p>Sube y visualiza tu tesis en paralelo al apartado de preguntas.</p>
            </div>

            <UploadZone onUpload={onUpload} isUploading={isUploading} />

            <label className="field-label" htmlFor="document-select">
              Tesis disponibles
            </label>
            <select
              id="document-select"
              className="field-select"
              value={selectedDocumentId}
              onChange={handleDocumentSelect}
            >
              <option value="">Selecciona una tesis</option>
              {documents.map((document) => (
                <option key={document.id} value={document.id}>
                  {document.filename}
                </option>
              ))}
            </select>

            <div className="document-actions">
              <button
                type="button"
                className="button button-secondary"
                onClick={() => {
                  void refreshDocuments({ resetSelection: !selectedDocumentId });
                }}
                disabled={!token || isUploading || isDeleting}
              >
                Actualizar lista
              </button>
              <button
                type="button"
                className="button button-danger"
                onClick={handleDeleteDocument}
                disabled={!selectedDocumentId || isUploading || isDeleting}
              >
                {isDeleting ? "Eliminando..." : "Eliminar tesis"}
              </button>
            </div>

            <PDFViewer pdfUrl={pdfPreviewUrl} filename={selectedDocumentName} />

            {error ? <p className="inline-error">{error}</p> : null}
            {info ? <p className="inline-info">{info}</p> : null}
          </article>

          <article className="panel">
            <ChatWindow
              token={token}
              documentId={selectedDocumentId}
              documentName={selectedDocumentName}
              aiProvider={selectedAiModel.provider}
              aiModel={selectedAiModel.model}
              aiModelLabel={`${selectedAiModel.label} (${selectedAiModel.detail})`}
            />
          </article>
        </section>
      ) : isPlanSection ? (
        <section className="plan-workspace">
          <ThesisPlanPanel
            token={token}
            academicProfile={academicProfile}
            aiProvider={selectedAiModel.provider}
            aiModel={selectedAiModel.model}
            aiModelLabel={`${selectedAiModel.label} (${selectedAiModel.detail})`}
            aiModelOptions={AI_MODEL_OPTIONS}
            selectedAiModelId={selectedAiModelId}
            onAutoJobStarted={handleAutoJobStarted}
          />
        </section>
      ) : (
        <section className="plan-workspace">
          <ThesisPanel
            token={token}
            academicProfile={academicProfile}
            aiProvider={selectedAiModel.provider}
            aiModel={selectedAiModel.model}
            aiModelLabel={`${selectedAiModel.label} (${selectedAiModel.detail})`}
          />
        </section>
      )}
    </main>
  );
}

export default DashboardPage;
