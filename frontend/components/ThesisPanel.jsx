"use client";

import { useEffect, useMemo, useState } from "react";

import {
  clearCachedChatMessages,
  createThesisFromPlan,
  downloadThesisPdf,
  listAutomaticThesisJobs,
  listChatMessages,
  listChatSessions,
  markAutomaticThesisJobNotified,
  setCachedChatMessages,
  startAutomaticThesisJob,
} from "../lib/api";

const PLAN_MODE = "thesis_plan";
const THESIS_MODE = "thesis";

const THESIS_STAGES = [
  { id: "preliminares_resumen", title: "Preliminares, resumen e introduccion" },
  { id: "capitulo_i_problema", title: "Capitulo I: problema" },
  { id: "capitulo_ii_marco_teorico", title: "Capitulo II: marco teorico" },
  { id: "capitulo_iii_metodologia", title: "Capitulo III: metodologia" },
  { id: "capitulo_iv_resultados_propuesta", title: "Capitulo IV: resultados o propuesta" },
  { id: "capitulo_v_discusion", title: "Capitulo V: discusion" },
  { id: "conclusiones_recomendaciones", title: "Conclusiones y recomendaciones" },
  { id: "referencias_anexos", title: "Referencias y anexos" },
];

function normalizeMessages(rows = []) {
  return (rows || [])
    .filter((row) => row.role !== "system")
    .map((row) => ({
      id: String(row.id),
      role: row.role,
      content: row.content,
    }));
}

function ThesisPanel({
  token,
  academicProfile = null,
  aiProvider = "gemini",
  aiModel = "gemini-2.0-flash",
  aiModelLabel = "Gemini (gemini-2.0-flash)",
}) {
  const [sourcePlans, setSourcePlans] = useState([]);
  const [thesisSessions, setThesisSessions] = useState([]);
  const [selectedSourcePlanId, setSelectedSourcePlanId] = useState("");
  const [activeThesisId, setActiveThesisId] = useState("");
  const [messages, setMessages] = useState([]);
  const [isInitializing, setIsInitializing] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isCreatingThesis, setIsCreatingThesis] = useState(false);
  const [isGeneratingThesis, setIsGeneratingThesis] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [isCheckingAutoJobs, setIsCheckingAutoJobs] = useState(false);
  const [isDismissingAutoJob, setIsDismissingAutoJob] = useState(false);
  const [autoJobs, setAutoJobs] = useState([]);
  const [formalData, setFormalData] = useState({
    authors: "",
    advisor: "",
    area: academicProfile?.career_name || "",
    research_line: academicProfile?.default_research_line || "",
  });
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const selectedSourcePlan = useMemo(
    () => sourcePlans.find((plan) => plan.id === selectedSourcePlanId) || sourcePlans[0] || null,
    [sourcePlans, selectedSourcePlanId]
  );
  const hasGeneratedContent = messages.some((item) =>
    item.role === "assistant" && Boolean((item.content || "").trim())
  );
  const isBusy = isInitializing
    || isLoadingMessages
    || isCreatingThesis
    || isGeneratingThesis
    || isExportingPdf
    || isDismissingAutoJob;
  const completedAutoJob = autoJobs.find((job) =>
    job.status === "completed" && !job.notified_at && job.chat_id
  );
  const runningAutoJob = autoJobs.find((job) =>
    (job.status === "pending" || job.status === "running") && job.chat_id
  );
  const missingFormalFields = [
    ["authors", "autor(es)"],
    ["advisor", "asesor"],
    ["area", "area de investigacion"],
    ["research_line", "linea de investigacion"],
  ]
    .filter(([key]) => !String(formalData[key] || "").trim())
    .map(([, label]) => label);

  useEffect(() => {
    if (!academicProfile) {
      return;
    }

    setFormalData((previous) => ({
      ...previous,
      area: academicProfile.career_name || previous.area,
      research_line: academicProfile.default_research_line || previous.research_line,
    }));
  }, [academicProfile]);

  useEffect(() => {
    if (!token || !activeThesisId) {
      return;
    }

    setCachedChatMessages(token, activeThesisId, messages);
  }, [activeThesisId, messages, token]);

  const syncSourcePlans = async () => {
    if (!token) {
      setSourcePlans([]);
      setSelectedSourcePlanId("");
      return [];
    }

    const sessions = (await listChatSessions(token, { mode: PLAN_MODE })) || [];
    setSourcePlans(sessions);
    setSelectedSourcePlanId((previous) => {
      if (previous && sessions.some((session) => session.id === previous)) {
        return previous;
      }
      return sessions[0]?.id || "";
    });
    return sessions;
  };

  const syncThesisSessions = async (preferredChatId = "") => {
    if (!token) {
      setThesisSessions([]);
      setActiveThesisId("");
      return { sessions: [], nextChatId: "" };
    }

    const sessions = (await listChatSessions(token, { mode: THESIS_MODE })) || [];
    setThesisSessions(sessions);

    const hasPreferred = preferredChatId && sessions.some((session) => session.id === preferredChatId);
    const nextChatId = hasPreferred ? preferredChatId : sessions[0]?.id || "";
    setActiveThesisId(nextChatId);
    return { sessions, nextChatId };
  };

  const refreshAutoJobs = async () => {
    if (!token) {
      setAutoJobs([]);
      return [];
    }

    setIsCheckingAutoJobs(true);
    try {
      const jobs = (await listAutomaticThesisJobs(token, { limit: 12 })) || [];
      setAutoJobs(jobs);

      const completed = jobs.find((job) => job.status === "completed" && job.chat_id);
      if (completed?.chat_id && completed.chat_id === activeThesisId) {
        clearCachedChatMessages(token, completed.chat_id);
        await loadMessagesByChatId(completed.chat_id);
      }

      return jobs;
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudieron revisar los trabajos automaticos de tesis."
      );
      return [];
    } finally {
      setIsCheckingAutoJobs(false);
    }
  };

  const loadMessagesByChatId = async (chatId) => {
    if (!token || !chatId) {
      setMessages([]);
      return;
    }

    setIsLoadingMessages(true);
    setError("");

    try {
      const rows = await listChatMessages(token, chatId);
      setMessages(normalizeMessages(rows));
    } catch (requestError) {
      setMessages([]);
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo cargar el historial de la tesis."
      );
    } finally {
      setIsLoadingMessages(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      if (!token) {
        return;
      }

      setIsInitializing(true);
      setError("");

      try {
        const [plans, thesisResult] = await Promise.all([
          syncSourcePlans(),
          syncThesisSessions(),
        ]);
        if (cancelled) {
          return;
        }

        const nextThesisId = thesisResult.nextChatId;
        const nextThesis = nextThesisId
          ? thesisResult.sessions.find((session) => session.id === nextThesisId)
          : null;
        if (nextThesis?.source_chat_session_id) {
          setSelectedSourcePlanId(nextThesis.source_chat_session_id);
        } else if (plans?.[0]?.id) {
          setSelectedSourcePlanId(plans[0].id);
        }
        if (nextThesisId) {
          await loadMessagesByChatId(nextThesisId);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "No se pudo inicializar la seccion de tesis."
          );
        }
      } finally {
        if (!cancelled) {
          setIsInitializing(false);
        }
      }
    };

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token) {
      return undefined;
    }

    void refreshAutoJobs();
    const intervalId = window.setInterval(() => {
      void refreshAutoJobs();
    }, 12000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [token, activeThesisId]);

  const createThesisSession = async () => {
    if (!token || !selectedSourcePlan) {
      throw new Error("Selecciona primero un plan de tesis generado.");
    }

    const created = await createThesisFromPlan(token, selectedSourcePlan.id);
    const { nextChatId } = await syncThesisSessions(created?.chat_id || "");
    if (nextChatId) {
      clearCachedChatMessages(token, nextChatId);
      await loadMessagesByChatId(nextChatId);
    }
    return created;
  };

  const handleCreateThesis = async () => {
    if (!token || !academicProfile || !selectedSourcePlan || isCreatingThesis) {
      return;
    }

    setIsCreatingThesis(true);
    setError("");
    setInfo("");

    try {
      const created = await createThesisSession();
      setInfo(`Tesis creada desde el plan: ${selectedSourcePlan.title}.`);
      return created;
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo crear la tesis desde el plan seleccionado."
      );
      return null;
    } finally {
      setIsCreatingThesis(false);
    }
  };

  const handleSelectSourcePlan = (event) => {
    const nextPlanId = event.target.value;
    setSelectedSourcePlanId(nextPlanId);
    const linkedThesis = thesisSessions.find((session) => session.source_chat_session_id === nextPlanId);
    if (linkedThesis) {
      setActiveThesisId(linkedThesis.id);
      void loadMessagesByChatId(linkedThesis.id);
    }
  };

  const handleSelectThesis = async (event) => {
    const nextChatId = event.target.value;
    setActiveThesisId(nextChatId);
    setError("");
    setInfo("");

    const selected = thesisSessions.find((session) => session.id === nextChatId);
    if (selected?.source_chat_session_id) {
      setSelectedSourcePlanId(selected.source_chat_session_id);
    }
    await loadMessagesByChatId(nextChatId);
  };

  const handleFormalDataChange = (field, value) => {
    setFormalData((previous) => ({
      ...previous,
      [field]: value,
    }));
  };

  const handleGenerateThesis = async () => {
    if (!token || !academicProfile || !selectedSourcePlan || isGeneratingThesis) {
      setError("Selecciona un plan de tesis generado antes de crear la tesis.");
      return;
    }

    if (missingFormalFields.length) {
      setError(`Completa antes estos datos formales: ${missingFormalFields.join(", ")}.`);
      return;
    }

    setIsGeneratingThesis(true);
    setError("");
    setInfo("");

    try {
      const job = await startAutomaticThesisJob(
        token,
        selectedSourcePlan.id,
        formalData,
        {
          provider: aiProvider,
          model: aiModel,
        }
      );

      const { nextChatId } = await syncThesisSessions(job?.chat_id || "");
      if (nextChatId) {
        await loadMessagesByChatId(nextChatId);
      }

      setAutoJobs((previous) => [
        job,
        ...previous.filter((item) => item.id !== job?.id),
      ]);
      setInfo(
        "El backend esta generando tu tesis. Puedes cerrar la pestaña; al volver se avisara cuando este lista."
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo iniciar la generacion automatica de la tesis."
      );
    } finally {
      setIsGeneratingThesis(false);
    }
  };

  const downloadPdfBlob = (blob, filename) => {
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename || "tesis.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
  };

  const handleDownloadPdf = async () => {
    if (!token || !activeThesisId || !hasGeneratedContent || isExportingPdf) {
      return;
    }

    setIsExportingPdf(true);
    setError("");
    setInfo("");

    try {
      const { blob, filename } = await downloadThesisPdf(token, activeThesisId);
      downloadPdfBlob(blob, filename);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo descargar el PDF de la tesis."
      );
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleDownloadAutoJobPdf = async (job) => {
    if (!token || !job?.chat_id || isExportingPdf) {
      return;
    }

    setIsExportingPdf(true);
    setError("");
    setInfo("");

    try {
      const { blob, filename } = await downloadThesisPdf(token, job.chat_id);
      downloadPdfBlob(blob, filename);
      const updatedJob = await markAutomaticThesisJobNotified(token, job.id);
      setAutoJobs((previous) =>
        previous.map((item) => (item.id === updatedJob.id ? updatedJob : item))
      );
      await syncThesisSessions(job.chat_id);
      await loadMessagesByChatId(job.chat_id);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo descargar el PDF de la tesis automatica."
      );
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleDismissAutoJob = async (job) => {
    if (!token || !job?.id || isDismissingAutoJob) {
      return;
    }

    setIsDismissingAutoJob(true);
    setError("");

    try {
      const updatedJob = await markAutomaticThesisJobNotified(token, job.id);
      setAutoJobs((previous) =>
        previous.map((item) => (item.id === updatedJob.id ? updatedJob : item))
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo cerrar el aviso de la tesis automatica."
      );
    } finally {
      setIsDismissingAutoJob(false);
    }
  };

  if (!academicProfile) {
    return (
      <div className="thesis-plan-shell is-blocked">
        <section className="thesis-plan-main">
          <article className="message-bubble assistant">
            <p className="message-role">Asesor IA</p>
            <pre className="review-content">
              Selecciona tu facultad y carrera para generar una tesis desde un plan.
            </pre>
          </article>
        </section>
      </div>
    );
  }

  return (
    <div className="thesis-plan-shell">
      <section className="thesis-plan-main">
        <div className="plan-header">
          <div>
            <p className="dashboard-eyebrow">Tesis</p>
            <h2>Generador de tesis {academicProfile.faculty_acronym}</h2>
            <span className="model-label">{academicProfile.career_name}</span>
            <span className="model-label">{aiModelLabel}</span>
          </div>
          <div className="plan-header-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={handleCreateThesis}
              disabled={!token || !selectedSourcePlan || isBusy}
            >
              {isCreatingThesis ? "Creando..." : "Nueva tesis desde plan"}
            </button>
            <button
              type="button"
              className="button button-primary"
              onClick={handleGenerateThesis}
              disabled={!token || !selectedSourcePlan || isBusy}
            >
              {isGeneratingThesis ? "Generando..." : "Generar tesis completa"}
            </button>
            <button
              type="button"
              className="button button-special"
              onClick={handleDownloadPdf}
              disabled={!token || !activeThesisId || !hasGeneratedContent || isBusy}
            >
              {isExportingPdf ? "Preparando PDF..." : "Descargar PDF"}
            </button>
          </div>
        </div>

        {completedAutoJob ? (
          <section className="auto-plan-notice" aria-live="polite">
            <div>
              <p className="dashboard-eyebrow">Tesis automatica lista</p>
              <h2>Tu tesis ya fue creada</h2>
              <p>{completedAutoJob.source_plan_title || "El backend termino de generar la tesis."}</p>
            </div>
            <div className="auto-plan-notice-actions">
              <button
                type="button"
                className="button button-primary"
                onClick={async () => {
                  setActiveThesisId(completedAutoJob.chat_id || "");
                  await syncThesisSessions(completedAutoJob.chat_id || "");
                  await loadMessagesByChatId(completedAutoJob.chat_id || "");
                }}
              >
                Ver tesis
              </button>
              <button
                type="button"
                className="button button-special"
                onClick={() => handleDownloadAutoJobPdf(completedAutoJob)}
                disabled={isExportingPdf}
              >
                {isExportingPdf ? "Descargando..." : "Descargar PDF"}
              </button>
              <button
                type="button"
                className="button button-ghost"
                onClick={() => handleDismissAutoJob(completedAutoJob)}
                disabled={isDismissingAutoJob}
              >
                Cerrar aviso
              </button>
            </div>
          </section>
        ) : runningAutoJob ? (
          <section className="auto-plan-notice is-running" aria-live="polite">
            <div>
              <p className="dashboard-eyebrow">Tesis automatica en proceso</p>
              <h2>El backend sigue generando tu tesis</h2>
              <p>
                {runningAutoJob.progress_label || "Puedes cerrar la pestaña y volver mas tarde."}
                {" "}
                {Number.isFinite(runningAutoJob.progress_percent)
                  ? `${runningAutoJob.progress_percent}%`
                  : ""}
              </p>
            </div>
            {isCheckingAutoJobs ? <span className="spinner" aria-hidden="true" /> : null}
          </section>
        ) : null}

        <div className={`chat-controls-stack ${isBusy ? "is-busy" : ""}`}>
          <div className="chat-session-controls">
            <label className="field-label" htmlFor="source-plan-select">
              Plan de tesis fuente
            </label>
            <select
              id="source-plan-select"
              className="field-select"
              value={selectedSourcePlanId}
              onChange={handleSelectSourcePlan}
              disabled={isBusy || !sourcePlans.length}
            >
              {!sourcePlans.length ? <option value="">No hay planes generados</option> : null}
              {sourcePlans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.title}
                </option>
              ))}
            </select>
          </div>

          <div className="chat-session-controls">
            <label className="field-label" htmlFor="thesis-session-select">
              Tesis guardadas
            </label>
            <select
              id="thesis-session-select"
              className="field-select"
              value={activeThesisId}
              onChange={handleSelectThesis}
              disabled={isBusy || !thesisSessions.length}
            >
              <option value="">Nueva tesis al generar</option>
              {thesisSessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.title}
                </option>
              ))}
            </select>
          </div>

          {isBusy ? (
            <div className="chat-controls-overlay" aria-live="polite" aria-busy="true">
              <span className="spinner" aria-hidden="true" />
              <span>
                {isGeneratingThesis
                  ? "Iniciando generacion en backend..."
                  : "Procesando..."}
              </span>
            </div>
          ) : null}
        </div>

        {!sourcePlans.length && !isInitializing ? (
          <article className="message-bubble assistant">
            <p className="message-role">Asesor IA</p>
            <pre className="review-content">
              Primero genera o completa un plan de tesis. Luego vuelve a esta seccion para convertirlo en tesis.
            </pre>
          </article>
        ) : null}

        {!messages.length && sourcePlans.length && !isLoadingMessages ? (
          <article className="message-bubble assistant">
            <p className="message-role">Asesor IA</p>
            <pre className="review-content">
              Selecciona el plan fuente y genera la tesis completa. La estructura se adaptara a tu facultad y carrera.
            </pre>
          </article>
        ) : null}

        <div className="chat-messages plan-chat-messages">
          {isLoadingMessages ? <p className="chat-placeholder">Cargando tesis...</p> : null}
          {!isLoadingMessages && messages.map((item) => (
            <article
              key={item.id}
              className={`message-bubble ${item.role === "user" ? "user" : "assistant"}`}
            >
              <p className="message-role">
                {item.role === "user" ? "Estudiante" : "Asesor IA"}
              </p>
              {item.role === "assistant" ? (
                <pre className="review-content">{item.content}</pre>
              ) : (
                <p className="message-content">{item.content}</p>
              )}
            </article>
          ))}
        </div>

        {error ? <p className="inline-error">{error}</p> : null}
        {info ? <p className="inline-info">{info}</p> : null}
      </section>

      <aside className="plan-sidebar">
        <div className="plan-sidebar-section">
          <h3>Datos formales</h3>
          <div className="formal-data-grid">
            <label>
              <span>Autor(es)</span>
              <input
                type="text"
                value={formalData.authors}
                onChange={(event) => handleFormalDataChange("authors", event.target.value)}
                placeholder="Bach. Nombre Apellido"
                disabled={isBusy}
              />
            </label>
            <label>
              <span>Asesor</span>
              <input
                type="text"
                value={formalData.advisor}
                onChange={(event) => handleFormalDataChange("advisor", event.target.value)}
                placeholder="Dr./Mg. Nombre Apellido"
                disabled={isBusy}
              />
            </label>
            <label>
              <span>Area</span>
              <input
                type="text"
                value={formalData.area}
                onChange={(event) => handleFormalDataChange("area", event.target.value)}
                disabled={isBusy}
              />
            </label>
            <label>
              <span>Linea</span>
              <input
                type="text"
                value={formalData.research_line}
                onChange={(event) => handleFormalDataChange("research_line", event.target.value)}
                disabled={isBusy}
              />
            </label>
          </div>
        </div>

        <div className="plan-sidebar-section">
          <h3>Plan fuente</h3>
          <p className="plan-muted">
            {selectedSourcePlan?.title || "Aun no hay un plan seleccionado."}
          </p>
        </div>

        <div className="plan-sidebar-section">
          <h3>Etapas de tesis</h3>
          <ol className="manual-section-list">
            {THESIS_STAGES.map((stage) => (
              <li key={stage.id}>{stage.title}</li>
            ))}
          </ol>
        </div>
      </aside>
    </div>
  );
}

export default ThesisPanel;
