"use client";

import { useEffect, useMemo, useState } from "react";

import {
  clearCachedChatMessages,
  continueThesisPlan,
  createChatSession,
  downloadThesisPlanPdf,
  generateThesisPlanCompleteSection,
  listChatMessages,
  listChatSessions,
  setCachedChatMessages,
  startAutomaticThesisPlanJob,
  suggestThesisPlanProblems,
} from "../lib/api";

const PLAN_MODE = "thesis_plan";

const MANUAL_SECTIONS = [
  "Datos generales",
  "Problema de investigacion",
  "Marco teorico",
  "Marco metodologico",
  "Aspectos administrativos",
  "Referencias APA",
  "Anexos y matriz",
];

const COMPLETE_PLAN_STAGES = [
  { id: "datos_generales", title: "Datos generales" },
  { id: "problema_justificacion", title: "Problema y justificacion" },
  { id: "operacionalizacion", title: "Operacionalizacion" },
  { id: "marco_teorico", title: "Marco teorico" },
  { id: "metodologia", title: "Marco metodologico" },
  { id: "administrativos_referencias", title: "Aspectos y referencias" },
  { id: "anexos", title: "Anexos" },
];

function normalizeMessages(rows = []) {
  return (rows || []).map((row) => ({
    id: String(row.id),
    role: row.role,
    content: row.content,
  }));
}

function formatPhase(phase) {
  if (phase === "flujo_manual_faing") {
    return "Flujo del manual";
  }

  if (phase === "documento_completo") {
    return "Documento completo";
  }

  return "Entrevista";
}

function buildQuestionResponse(questions, answers, extraMessage) {
  const responseLines = questions
    .map((question, index) => {
      const answer = (answers[question.id] || "").trim();
      if (!answer) {
        return "";
      }
      return `${index + 1}. ${question.question}\nRespuesta: ${answer}`;
    })
    .filter(Boolean);

  const notes = (extraMessage || "").trim();
  if (notes) {
    responseLines.push(`Notas adicionales:\n${notes}`);
  }

  return responseLines.join("\n\n");
}

function ThesisPlanPanel({
  token,
  academicProfile = null,
  aiProvider = "gemini",
  aiModel = "gemini-2.0-flash",
  aiModelLabel = "Gemini (gemini-2.0-flash)",
  aiModelOptions = null,
  selectedAiModelId = "",
  onAutoJobStarted,
}) {
  const [planSessions, setPlanSessions] = useState([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState("");
  const [advisorQuestions, setAdvisorQuestions] = useState([]);
  const [questionAnswers, setQuestionAnswers] = useState({});
  const [readiness, setReadiness] = useState({
    score: 0,
    phase: "entrevista_diagnostica",
    missingFields: [],
  });
  const [isInitializing, setIsInitializing] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isCreatingPlan, setIsCreatingPlan] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [isCompletingPlan, setIsCompletingPlan] = useState(false);
  const [isAutoModalOpen, setIsAutoModalOpen] = useState(false);
  const [isLoadingAutoProblems, setIsLoadingAutoProblems] = useState(false);
  const [isGeneratingAutoPlan, setIsGeneratingAutoPlan] = useState(false);
  const [autoSuggestions, setAutoSuggestions] = useState([]);
  const [selectedAutoProblemId, setSelectedAutoProblemId] = useState("");
  const [selectedAutoModelId, setSelectedAutoModelId] = useState("");
  const [autoError, setAutoError] = useState("");
  const [info, setInfo] = useState("");
  const [completionProgress, setCompletionProgress] = useState({
    current: 0,
    total: COMPLETE_PLAN_STAGES.length,
    label: "",
  });
  const [formalData, setFormalData] = useState({
    authors: "",
    advisor: "",
    area: academicProfile?.career_name || "",
    research_line: academicProfile?.default_research_line || "",
  });
  const [error, setError] = useState("");

  const currentModelId = `${aiProvider}:${aiModel}`;
  const manualSections = useMemo(
    () => (
      Array.isArray(academicProfile?.plan_sections) && academicProfile.plan_sections.length
        ? academicProfile.plan_sections
        : MANUAL_SECTIONS
    ),
    [academicProfile]
  );
  const initialAdvisorPrompt = useMemo(() => {
    if (!academicProfile) {
      return "Selecciona tu facultad y carrera para iniciar el plan de tesis.";
    }

    return [
      `Carrera seleccionada: ${academicProfile.faculty_acronym} - ${academicProfile.career_name}.`,
      "Describe la idea que tienes en mente.",
      "Incluye el problema observable, el contexto, la poblacion o unidad de analisis, las posibles variables o categorias y los datos que podrias obtener.",
      "Con eso decidire si seguimos preguntando o si ya iniciamos el esquema normativo de tu facultad.",
    ].join("\n");
  }, [academicProfile]);
  const resolvedAutoModelOptions = useMemo(() => {
    if (Array.isArray(aiModelOptions) && aiModelOptions.length) {
      return aiModelOptions;
    }

    return [
      {
        id: currentModelId,
        provider: aiProvider,
        model: aiModel,
        label: aiModelLabel,
        detail: aiModel,
      },
    ];
  }, [aiModel, aiModelLabel, aiModelOptions, aiProvider, currentModelId]);
  const defaultAutoModelId = useMemo(() => {
    const selectedExists = selectedAiModelId
      && resolvedAutoModelOptions.some((option) => option.id === selectedAiModelId);
    if (selectedExists) {
      return selectedAiModelId;
    }

    const currentExists = resolvedAutoModelOptions.some((option) => option.id === currentModelId);
    if (currentExists) {
      return currentModelId;
    }

    return resolvedAutoModelOptions[0]?.id || "";
  }, [currentModelId, resolvedAutoModelOptions, selectedAiModelId]);
  const selectedAutoModel = useMemo(
    () => (
      resolvedAutoModelOptions.find((option) => option.id === selectedAutoModelId)
      || resolvedAutoModelOptions[0]
      || null
    ),
    [resolvedAutoModelOptions, selectedAutoModelId]
  );
  const selectedAutoProblem = useMemo(
    () => autoSuggestions.find((item) => item.id === selectedAutoProblemId) || autoSuggestions[0] || null,
    [autoSuggestions, selectedAutoProblemId]
  );

  const isBusy = isInitializing
    || isLoadingMessages
    || isCreatingPlan
    || isSending
    || isExportingPdf
    || isCompletingPlan
    || isGeneratingAutoPlan;
  const hasAssistantPlan = messages.some((item) =>
    item.role === "assistant" && Boolean((item.content || "").trim())
  );
  const hasUserIdea = messages.some((item) =>
    item.role === "user" && Boolean((item.content || "").trim())
  );
  const missingFormalFields = [
    ["authors", "autor(es)"],
    ["advisor", "asesor"],
    ["area", "area de investigacion"],
    ["research_line", "linea de investigacion"],
  ]
    .filter(([key]) => !String(formalData[key] || "").trim())
    .map(([, label]) => label);
  const hasAnsweredQuestions = advisorQuestions.some((question) =>
    Boolean((questionAnswers[question.id] || "").trim())
  );
  const canSend = Boolean(
    token
    && academicProfile
    && !isBusy
    && (message.trim() || hasAnsweredQuestions)
  );

  const progressStyle = useMemo(
    () => ({ width: `${Math.min(Math.max(readiness.score, 0), 100)}%` }),
    [readiness.score]
  );

  useEffect(() => {
    if (!token || !activeChatId) {
      return;
    }

    setCachedChatMessages(token, activeChatId, messages);
  }, [activeChatId, messages, token]);

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
    if (!isAutoModalOpen || !token || !academicProfile || !selectedAutoModel || isGeneratingAutoPlan) {
      return;
    }

    let cancelled = false;

    const loadAutomaticProblems = async () => {
      setIsLoadingAutoProblems(true);
      setAutoError("");
      setAutoSuggestions([]);
      setSelectedAutoProblemId("");

      try {
        const response = await suggestThesisPlanProblems(token, {
          provider: selectedAutoModel.provider,
          model: selectedAutoModel.model,
        });
        const suggestions = response?.suggestions || [];

        if (!cancelled) {
          setAutoSuggestions(suggestions);
          setSelectedAutoProblemId(suggestions[0]?.id || "");
        }
      } catch (requestError) {
        if (!cancelled) {
          setAutoError(
            requestError instanceof Error
              ? requestError.message
              : "No se pudieron cargar problemas sugeridos."
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingAutoProblems(false);
        }
      }
    };

    void loadAutomaticProblems();
    return () => {
      cancelled = true;
    };
  }, [
    isAutoModalOpen,
    isGeneratingAutoPlan,
    academicProfile,
    selectedAutoModel,
    token,
  ]);

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
      setAdvisorQuestions([]);
      setQuestionAnswers({});
    } catch (requestError) {
      setMessages([]);
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo cargar el historial del plan."
      );
    } finally {
      setIsLoadingMessages(false);
    }
  };

  const syncSessions = async (preferredChatId = "") => {
    if (!token) {
      setPlanSessions([]);
      setActiveChatId("");
      setMessages([]);
      return "";
    }

    const sessions = (await listChatSessions(token, { mode: PLAN_MODE })) || [];
    setPlanSessions(sessions);

    const hasPreferred = preferredChatId && sessions.some((session) => session.id === preferredChatId);
    const nextChatId = hasPreferred ? preferredChatId : sessions[0]?.id || "";
    setActiveChatId(nextChatId);
    return nextChatId;
  };

  const downloadPdfBlob = (blob, filename) => {
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename || "plan_de_tesis.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
  };

  const handleOpenAutoModal = () => {
    if (!token || !academicProfile || isBusy) {
      return;
    }

    setSelectedAutoModelId(defaultAutoModelId);
    setSelectedAutoProblemId("");
    setAutoSuggestions([]);
    setAutoError("");
    setIsAutoModalOpen(true);
  };

  const handleCloseAutoModal = () => {
    if (isGeneratingAutoPlan) {
      return;
    }

    setIsAutoModalOpen(false);
    setAutoError("");
  };

  const handleGenerateAutomaticPlan = async () => {
    if (
      !token
      || !academicProfile
      || !selectedAutoProblem
      || !selectedAutoModel
      || isLoadingAutoProblems
      || isGeneratingAutoPlan
    ) {
      return;
    }

    setIsGeneratingAutoPlan(true);
    setAutoError("");
    setError("");
    setInfo("");
    setAdvisorQuestions([]);
    setQuestionAnswers({});

    try {
      const job = await startAutomaticThesisPlanJob(
        token,
        selectedAutoProblem,
        {
          provider: selectedAutoModel.provider,
          model: selectedAutoModel.model,
        }
      );

      const nextChatId = await syncSessions(job?.chat_id || "");
      if (nextChatId) {
        await loadMessagesByChatId(nextChatId);
      }

      setReadiness({
        score: 15,
        phase: "entrevista_diagnostica",
        missingFields: [],
      });
      setMessage("");
      setIsAutoModalOpen(false);
      setInfo(
        "El backend esta generando tu plan automatico. Puedes cerrar la pestaña; al volver se avisara cuando este listo."
      );
      if (typeof onAutoJobStarted === "function") {
        onAutoJobStarted(job);
      }
    } catch (requestError) {
      setAutoError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo iniciar la generacion automatica del plan de tesis."
      );
    } finally {
      setIsGeneratingAutoPlan(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const bootstrapSessions = async () => {
      if (!token) {
        return;
      }

      setIsInitializing(true);
      setError("");

      try {
        let nextChatId = await syncSessions();

        if (!cancelled && nextChatId) {
          await loadMessagesByChatId(nextChatId);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "No se pudieron inicializar los planes de tesis."
          );
        }
      } finally {
        if (!cancelled) {
          setIsInitializing(false);
        }
      }
    };

    void bootstrapSessions();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const createPlanSession = async () => {
    const created = await createChatSession(token, {
      mode: PLAN_MODE,
      title: "Plan de tesis",
      facultyId: academicProfile?.faculty_id,
      careerId: academicProfile?.career_id,
    });

    setPlanSessions((previous) => [
      created,
      ...previous.filter((session) => session.id !== created.id),
    ]);
    setActiveChatId(created.id);
    clearCachedChatMessages(token, created.id);
    return created;
  };

  const handleCreatePlan = async () => {
    if (!token || !academicProfile || isCreatingPlan) {
      return;
    }

    setIsCreatingPlan(true);
    setError("");
    setInfo("");

    try {
      await createPlanSession();
      setMessages([]);
      setMessage("");
      setAdvisorQuestions([]);
      setQuestionAnswers({});
      setReadiness({
        score: 0,
        phase: "entrevista_diagnostica",
        missingFields: [],
      });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo crear un nuevo plan de tesis."
      );
    } finally {
      setIsCreatingPlan(false);
    }
  };

  const handleSelectPlan = async (event) => {
    const nextChatId = event.target.value;
    setActiveChatId(nextChatId);
    setMessage("");
    setAdvisorQuestions([]);
    setQuestionAnswers({});
    setError("");
    setReadiness({
      score: 0,
      phase: "entrevista_diagnostica",
      missingFields: [],
    });
    await loadMessagesByChatId(nextChatId);
  };

  const handleSend = async () => {
    if (!canSend) {
      return;
    }

    const cleanMessage = advisorQuestions.length
      ? buildQuestionResponse(advisorQuestions, questionAnswers, message)
      : message.trim();

    if (!cleanMessage) {
      return;
    }

    setIsSending(true);
    setError("");
    setInfo("");

    let chatId = activeChatId;
    if (!chatId) {
      try {
        const created = await createPlanSession();
        chatId = created.id;
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "No se pudo crear un nuevo plan de tesis."
        );
        setIsSending(false);
        return;
      }
    }

    const localUserMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: cleanMessage,
    };

    setMessages((previous) => [...previous, localUserMessage]);
    setMessage("");

    try {
      const response = await continueThesisPlan(token, chatId, cleanMessage, {
        provider: aiProvider,
        model: aiModel,
      });
      const assistantMessage = {
        id: `local-assistant-${Date.now() + 1}`,
        role: "assistant",
        content: response?.response || "No se obtuvo respuesta del asesor.",
      };

      setReadiness({
        score: response?.readiness_score || 0,
        phase: response?.next_phase || "entrevista_diagnostica",
        missingFields: response?.missing_fields || [],
      });
      setAdvisorQuestions(response?.suggested_questions || []);
      setQuestionAnswers({});

      setMessages((previous) => {
        const nextMessages = [...previous, assistantMessage];
        setCachedChatMessages(token, chatId, nextMessages);
        return nextMessages;
      });
    } catch (requestError) {
      setMessages((previous) => previous.filter((item) => item.id !== localUserMessage.id));
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo continuar el plan de tesis."
      );
    } finally {
      setIsSending(false);
    }
  };

  const handleQuestionAnswerChange = (questionId, value) => {
    setQuestionAnswers((previous) => ({
      ...previous,
      [questionId]: value,
    }));
  };

  const handleFormalDataChange = (field, value) => {
    setFormalData((previous) => ({
      ...previous,
      [field]: value,
    }));
  };

  const handleCompleteDocument = async () => {
    if (!token || !academicProfile || !activeChatId || !hasUserIdea || isCompletingPlan) {
      setError("Primero envia la idea del proyecto al asesor y luego genera el documento completo.");
      return;
    }

    if (missingFormalFields.length) {
      setError(`Completa antes estos datos formales: ${missingFormalFields.join(", ")}.`);
      return;
    }

    setIsCompletingPlan(true);
    setError("");
    setInfo("");
    setAdvisorQuestions([]);
    setQuestionAnswers({});

    try {
      for (const [index, stage] of COMPLETE_PLAN_STAGES.entries()) {
        setCompletionProgress({
          current: index + 1,
          total: COMPLETE_PLAN_STAGES.length,
          label: stage.title,
        });

        const response = await generateThesisPlanCompleteSection(
          token,
          activeChatId,
          stage.id,
          formalData,
          {
            provider: aiProvider,
            model: aiModel,
          }
        );

        const assistantMessage = {
          id: `complete-${stage.id}-${Date.now()}`,
          role: "assistant",
          content: response?.response || "No se obtuvo contenido para esta etapa.",
        };

        setMessages((previous) => {
          const nextMessages = [...previous, assistantMessage];
          setCachedChatMessages(token, activeChatId, nextMessages);
          return nextMessages;
        });
      }

      setReadiness({
        score: 100,
        phase: "documento_completo",
        missingFields: [],
      });
      await syncSessions(activeChatId);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo completar el documento por etapas."
      );
    } finally {
      setCompletionProgress({
        current: 0,
        total: COMPLETE_PLAN_STAGES.length,
        label: "",
      });
      setIsCompletingPlan(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!token || !academicProfile || !activeChatId || !hasAssistantPlan || isExportingPdf) {
      return;
    }

    setIsExportingPdf(true);
    setError("");
    setInfo("");

    try {
      const { blob, filename } = await downloadThesisPlanPdf(token, activeChatId);
      downloadPdfBlob(blob, filename);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "No se pudo descargar el PDF del plan de tesis."
      );
    } finally {
      setIsExportingPdf(false);
    }
  };

  if (!academicProfile) {
    return (
      <div className="thesis-plan-shell is-blocked">
        <section className="thesis-plan-main">
          <article className="message-bubble assistant">
            <p className="message-role">Asesor IA</p>
            <pre className="review-content">{initialAdvisorPrompt}</pre>
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
            <p className="dashboard-eyebrow">Plan de tesis</p>
            <h2>Asesor metodologico {academicProfile.faculty_acronym}</h2>
            <span className="model-label">{academicProfile.career_name}</span>
            <span className="model-label">{aiModelLabel}</span>
          </div>
          <div className="plan-header-actions">
            <button
              type="button"
              className="button button-special"
              onClick={handleOpenAutoModal}
              disabled={!token || !academicProfile || isBusy}
            >
              Plan automatico
            </button>
            <button
              type="button"
              className="button button-primary"
              onClick={handleCompleteDocument}
              disabled={!token || !academicProfile || !activeChatId || !hasUserIdea || isBusy}
            >
              {isCompletingPlan ? "Generando..." : "Completar documento"}
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={handleDownloadPdf}
              disabled={!token || !academicProfile || !activeChatId || !hasAssistantPlan || isBusy}
            >
              {isExportingPdf ? "Preparando PDF..." : "Descargar PDF"}
            </button>
            <div className="plan-status" aria-label="Estado de suficiencia">
              <span>{readiness.score}/100</span>
              <strong>{formatPhase(readiness.phase)}</strong>
            </div>
          </div>
        </div>

        <div className="plan-progress" aria-hidden="true">
          <span style={progressStyle} />
        </div>

        <div className={`chat-controls-stack ${isBusy ? "is-busy" : ""}`}>
          <div className="chat-session-controls">
            <label className="field-label" htmlFor="plan-session-select">
              Planes guardados
            </label>
            <div className="chat-session-row">
              <select
                id="plan-session-select"
                className="field-select"
                value={activeChatId}
                onChange={handleSelectPlan}
                disabled={!academicProfile || isInitializing || isCreatingPlan || isSending}
              >
                <option value="">Nuevo plan al enviar</option>
                {planSessions.map((session) => (
                  <option key={session.id} value={session.id}>
                    {session.title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="button button-secondary"
                onClick={handleCreatePlan}
                disabled={!token || !academicProfile || isInitializing || isCreatingPlan || isSending}
              >
                {isCreatingPlan ? "Creando..." : "Nuevo plan"}
              </button>
            </div>
          </div>

          {isBusy ? (
            <div className="chat-controls-overlay" aria-live="polite" aria-busy="true">
              <span className="spinner" aria-hidden="true" />
              <span>
                {isGeneratingAutoPlan
                  ? "Iniciando generacion en backend..."
                  : isCompletingPlan && completionProgress.current
                    ? `Etapa ${completionProgress.current}/${completionProgress.total}: ${completionProgress.label}`
                    : "Procesando..."}
              </span>
            </div>
          ) : null}
        </div>

        {!messages.length && !isLoadingMessages ? (
          <article className="message-bubble assistant">
            <p className="message-role">Asesor IA</p>
            <pre className="review-content">{initialAdvisorPrompt}</pre>
          </article>
        ) : null}

        <div className="chat-messages plan-chat-messages">
          {isLoadingMessages ? <p className="chat-placeholder">Cargando historial...</p> : null}
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

        <div className="chat-form plan-input-form">
          {advisorQuestions.length ? (
            <section className="plan-question-form" aria-label="Preguntas del asesor">
              <div className="plan-question-form-header">
                <h3>Responde para avanzar</h3>
                <p>Completa lo que sepas. Puedes dejar vacios los campos que aun quieras que el asesor proponga.</p>
              </div>
              {advisorQuestions.map((question) => (
                <label className="plan-question-field" key={question.id}>
                  <span>{question.label}</span>
                  <small>{question.question}</small>
                  <textarea
                    value={questionAnswers[question.id] || ""}
                    onChange={(event) => handleQuestionAnswerChange(question.id, event.target.value)}
                    rows={3}
                    placeholder={question.placeholder || "Escribe tu respuesta..."}
                    disabled={isBusy}
                  />
                </label>
              ))}
            </section>
          ) : null}

          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={5}
            placeholder={
              advisorQuestions.length
                ? "Agrega una nota adicional si quieres corregir o ampliar algo..."
                : "Escribe tu idea inicial o responde las preguntas del asesor..."
            }
            disabled={!token || isBusy}
          />
          <div className="chat-actions">
            <button
              type="button"
              className="button button-primary"
              disabled={!canSend}
              onClick={handleSend}
            >
              {isSending
                ? "Analizando..."
                : advisorQuestions.length
                  ? "Enviar respuestas y avanzar"
                  : "Enviar al asesor"}
            </button>
          </div>
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
          <h3>Ruta del manual</h3>
          <ol className="manual-section-list">
            {manualSections.map((section) => (
              <li key={section}>{section}</li>
            ))}
          </ol>
        </div>

        <div className="plan-sidebar-section">
          <h3>Faltantes detectados</h3>
          {readiness.missingFields.length ? (
            <ul className="missing-field-list">
              {readiness.missingFields.slice(0, 8).map((field) => (
                <li key={field}>{field}</li>
              ))}
            </ul>
          ) : (
            <p className="plan-muted">Aun no hay diagnostico o ya puedes entrar al flujo del manual.</p>
          )}
        </div>
      </aside>

      {isAutoModalOpen ? (
        <div className="auto-plan-backdrop">
          <section
            className="auto-plan-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="auto-plan-title"
          >
            <div className="auto-plan-modal-header">
              <div>
                <p className="dashboard-eyebrow">Plan automatico</p>
                <h3 id="auto-plan-title">Problema de investigacion</h3>
              </div>
              <button
                type="button"
                className="button button-ghost auto-plan-close"
                onClick={handleCloseAutoModal}
                disabled={isGeneratingAutoPlan}
              >
                Cerrar
              </button>
            </div>

            <div className="auto-plan-problem-list" aria-live="polite">
              {isLoadingAutoProblems ? (
                <div className="auto-plan-loading">
                  <span className="spinner" aria-hidden="true" />
                  <span>Cargando problemas sugeridos...</span>
                </div>
              ) : null}

              {!isLoadingAutoProblems && autoSuggestions.map((item) => (
                <label
                  className={`auto-problem-option ${selectedAutoProblem?.id === item.id ? "is-selected" : ""}`}
                  key={`${item.id}-${item.title}`}
                >
                  <input
                    type="radio"
                    name="auto-plan-problem"
                    value={item.id}
                    checked={selectedAutoProblem?.id === item.id}
                    onChange={() => setSelectedAutoProblemId(item.id)}
                    disabled={isGeneratingAutoPlan}
                  />
                  <span className="auto-problem-option-body">
                    <strong>{item.title}</strong>
                    <span>{item.problem}</span>
                    <small>{item.community_impact}</small>
                    <small>Contexto: {item.research_context}</small>
                  </span>
                </label>
              ))}

              {!isLoadingAutoProblems && !autoSuggestions.length ? (
                <p className="plan-muted">No se cargaron problemas sugeridos.</p>
              ) : null}
            </div>

            <label className="auto-plan-model-picker" htmlFor="auto-plan-model-select">
              <span>Modelo a utilizar</span>
              <select
                id="auto-plan-model-select"
                className="field-select"
                value={selectedAutoModelId}
                onChange={(event) => setSelectedAutoModelId(event.target.value)}
                disabled={isLoadingAutoProblems || isGeneratingAutoPlan}
              >
                {resolvedAutoModelOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label} - {option.detail}
                  </option>
                ))}
              </select>
            </label>

            {autoError ? <p className="inline-error">{autoError}</p> : null}

            <div className="auto-plan-modal-actions">
              <button
                type="button"
                className="button button-secondary"
                onClick={handleCloseAutoModal}
                disabled={isGeneratingAutoPlan}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="button button-special"
                onClick={handleGenerateAutomaticPlan}
                disabled={
                  !selectedAutoProblem
                  || !selectedAutoModel
                  || isLoadingAutoProblems
                  || isGeneratingAutoPlan
                }
              >
                {isGeneratingAutoPlan ? "Iniciando..." : "Iniciar generacion automatica"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

export default ThesisPlanPanel;
