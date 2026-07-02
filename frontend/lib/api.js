const configuredBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();

function resolveApiBaseUrl() {
  if (!configuredBackendUrl) {
    return "/backend";
  }

  const cleanUrl = configuredBackendUrl.replace(/\/$/, "");
  try {
    const parsedUrl = new URL(cleanUrl);
    const isLocalBackend = ["localhost", "127.0.0.1", "0.0.0.0"].includes(parsedUrl.hostname);
    if (isLocalBackend) {
      return "/backend";
    }
  } catch {
    return cleanUrl || "/backend";
  }

  return cleanUrl;
}

const API_BASE_URL = resolveApiBaseUrl();

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const chatSessionsCache = new Map();
const chatMessagesCache = new Map();

function formatApiErrorPayload(payload, fallback) {
  const detail = payload?.detail || payload?.message;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .filter(Boolean)
      .join(" ");
  }

  if (detail && typeof detail === "object") {
    return detail.message || detail.error || JSON.stringify(detail);
  }

  return fallback;
}

function clonePayload(payload) {
  if (payload == null) {
    return payload;
  }
  return JSON.parse(JSON.stringify(payload));
}

function buildTokenScope(token) {
  if (!token) {
    return "anon";
  }
  return token.slice(0, 16);
}

function buildSessionsCacheKey(token, { documentId = "", mode = "" } = {}) {
  return `${buildTokenScope(token)}::${documentId}::${mode}`;
}

function buildMessagesCacheKey(token, chatId) {
  return `${buildTokenScope(token)}::${chatId || ""}`;
}

function invalidateChatSessionsByDocument(token, documentId = "") {
  const tokenScope = buildTokenScope(token);
  const documentPrefix = `${tokenScope}::${documentId}::`;
  for (const cacheKey of chatSessionsCache.keys()) {
    if (cacheKey.startsWith(documentPrefix)) {
      chatSessionsCache.delete(cacheKey);
    }
  }
}

function invalidateChatSessionsByMode(token, mode = "") {
  if (!mode) {
    return;
  }

  const tokenScope = buildTokenScope(token);
  const modeSuffix = `::${mode}`;
  for (const cacheKey of chatSessionsCache.keys()) {
    if (cacheKey.startsWith(`${tokenScope}::`) && cacheKey.endsWith(modeSuffix)) {
      chatSessionsCache.delete(cacheKey);
    }
  }
}

function setCachedChatSessions(token, { documentId = "", mode = "" } = {}, sessions = []) {
  const cacheKey = buildSessionsCacheKey(token, { documentId, mode });
  chatSessionsCache.set(cacheKey, clonePayload(sessions || []));
}

function setCachedChatMessages(token, chatId, messages = []) {
  if (!chatId) {
    return;
  }
  const cacheKey = buildMessagesCacheKey(token, chatId);
  chatMessagesCache.set(cacheKey, clonePayload(messages || []));
}

function clearCachedChatMessages(token, chatId) {
  if (!chatId) {
    return;
  }
  const cacheKey = buildMessagesCacheKey(token, chatId);
  chatMessagesCache.delete(cacheKey);
}

async function apiRequest(path, options = {}) {
  const {
    method = "GET",
    token,
    body,
    isFormData = false,
    headers = {},
  } = options;

  const requestHeaders = {
    ...headers,
  };

  if (token) {
    requestHeaders.Authorization = `Bearer ${token}`;
  }

  if (!isFormData) {
    requestHeaders["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: requestHeaders,
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
  });

  if (!response.ok) {
    let message = `Error de API (${response.status})`;
    try {
      const payload = await response.json();
      message = formatApiErrorPayload(payload, message);
    } catch {
      try {
        const text = await response.text();
        message = text?.trim() || message;
      } catch {
        // Sin payload legible, se mantiene el mensaje por defecto.
      }
    }
    throw new ApiError(message, response.status);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  return response.json();
}

async function apiDownload(path, options = {}) {
  const {
    method = "GET",
    token,
    body,
    isFormData = false,
    headers = {},
    fallbackFilename = "plan_de_tesis.pdf",
  } = options;
  const requestHeaders = { ...headers };

  if (token) {
    requestHeaders.Authorization = `Bearer ${token}`;
  }

  if (body && !isFormData) {
    requestHeaders["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: requestHeaders,
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
  });

  if (!response.ok) {
    let message = `Error de API (${response.status})`;
    try {
      const payload = await response.json();
      message = formatApiErrorPayload(payload, message);
    } catch {
      try {
        const text = await response.text();
        message = text?.trim() || message;
      } catch {
        // Sin payload legible, se mantiene el mensaje por defecto.
      }
    }
    throw new ApiError(message, response.status);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="([^"]+)"/i);

  return {
    blob,
    filename: filenameMatch?.[1] || fallbackFilename,
    chatId: response.headers.get("x-chat-id") || "",
  };
}

function fetchAcademicCatalog() {
  return apiRequest("/api/academic/catalog", {
    method: "GET",
  });
}

function fetchAcademicProfile(token) {
  return apiRequest("/api/academic/profile", {
    method: "GET",
    token,
  });
}

function saveAcademicProfile(token, { facultyId, careerId }) {
  return apiRequest("/api/academic/profile", {
    method: "PUT",
    token,
    body: {
      faculty_id: facultyId,
      career_id: careerId,
    },
  });
}

function registerUser(email, password, academicProfile = {}) {
  return apiRequest("/api/auth/register", {
    method: "POST",
    body: {
      email,
      password,
      faculty_id: academicProfile.facultyId,
      career_id: academicProfile.careerId,
    },
  });
}

function loginUser(email, password) {
  return apiRequest("/api/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

function fetchCurrentUser(token) {
  return apiRequest("/api/auth/me", {
    method: "GET",
    token,
  });
}

function listDocuments(token) {
  return apiRequest("/api/documents", {
    method: "GET",
    token,
  });
}

function listChatSessions(token, { documentId, mode } = {}) {
  const cacheKey = buildSessionsCacheKey(token, { documentId, mode });
  const cached = chatSessionsCache.get(cacheKey);
  if (cached) {
    return Promise.resolve(clonePayload(cached));
  }

  const query = new URLSearchParams();
  if (documentId) {
    query.set("document_id", documentId);
  }
  if (mode) {
    query.set("mode", mode);
  }

  const queryString = query.toString();
  const path = queryString ? `/api/chats?${queryString}` : "/api/chats";

  return apiRequest(path, {
    method: "GET",
    token,
  }).then((rows) => {
    const normalized = rows || [];
    setCachedChatSessions(token, { documentId, mode }, normalized);
    return clonePayload(normalized);
  });
}

function createChatSession(token, { documentId, mode, title, facultyId, careerId, sourceChatSessionId }) {
  const body = {
    mode,
    title,
  };

  if (documentId) {
    body.document_id = documentId;
  }

  if (facultyId && careerId) {
    body.faculty_id = facultyId;
    body.career_id = careerId;
  }

  if (sourceChatSessionId) {
    body.source_chat_session_id = sourceChatSessionId;
  }

  return apiRequest("/api/chats", {
    method: "POST",
    token,
    body,
  }).then((created) => {
    if (created) {
      const cacheKey = buildSessionsCacheKey(token, { documentId, mode });
      const current = chatSessionsCache.get(cacheKey) || [];
      const deduped = [created, ...current.filter((session) => session.id !== created.id)];
      chatSessionsCache.set(cacheKey, clonePayload(deduped));
      clearCachedChatMessages(token, created.id);
    }
    return created;
  });
}

function listChatMessages(token, chatId) {
  const cacheKey = buildMessagesCacheKey(token, chatId);
  const cached = chatMessagesCache.get(cacheKey);
  if (cached) {
    return Promise.resolve(clonePayload(cached));
  }

  return apiRequest(`/api/chats/${encodeURIComponent(chatId)}/messages`, {
    method: "GET",
    token,
  }).then((rows) => {
    const normalized = rows || [];
    setCachedChatMessages(token, chatId, normalized);
    return clonePayload(normalized);
  });
}

function deleteDocument(token, documentId) {
  return apiRequest(`/api/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
    token,
  }).then((response) => {
    invalidateChatSessionsByDocument(token, documentId);
    return response;
  });
}

function uploadDocument(token, file, replaceDocumentId = "") {
  const formData = new FormData();
  formData.append("file", file);
  if (replaceDocumentId) {
    formData.append("replace_document_id", replaceDocumentId);
  }

  return apiRequest("/api/upload", {
    method: "POST",
    token,
    body: formData,
    isFormData: true,
  }).then((response) => {
    if (replaceDocumentId) {
      invalidateChatSessionsByDocument(token, replaceDocumentId);
    }
    return response;
  });
}

function evaluateThesis(token, documentId, chatId, message, aiConfig = {}) {
  return apiRequest("/api/thesis/review", {
    method: "POST",
    token,
    body: {
      document_id: documentId,
      chat_id: chatId,
      message,
      ai_provider: aiConfig.provider,
      ai_model: aiConfig.model,
    },
  });
}

function continueThesisPlan(token, chatId, message, aiConfig = {}) {
  return apiRequest("/api/thesis/plan", {
    method: "POST",
    token,
    body: {
      chat_id: chatId,
      message,
      ai_provider: aiConfig.provider,
      ai_model: aiConfig.model,
    },
  });
}

function suggestThesisPlanProblems(token, aiConfig = {}) {
  return apiRequest("/api/thesis/plan/auto-problems", {
    method: "POST",
    token,
    body: {
      ai_provider: aiConfig.provider,
      ai_model: aiConfig.model,
    },
  });
}

function listAutomaticThesisPlanJobs(token, { limit = 10 } = {}) {
  const query = new URLSearchParams();
  if (limit) {
    query.set("limit", String(limit));
  }

  const queryString = query.toString();
  const path = queryString
    ? `/api/thesis/plan/auto-jobs?${queryString}`
    : "/api/thesis/plan/auto-jobs";

  return apiRequest(path, {
    method: "GET",
    token,
  });
}

function startAutomaticThesisPlanJob(token, selectedProblem, aiConfig = {}) {
  return apiRequest("/api/thesis/plan/auto-jobs", {
    method: "POST",
    token,
    body: {
      selected_problem: selectedProblem,
      ai_provider: aiConfig.provider,
      ai_model: aiConfig.model,
    },
  }).then((job) => {
    invalidateChatSessionsByMode(token, "thesis_plan");
    if (job?.chat_id) {
      clearCachedChatMessages(token, job.chat_id);
    }
    return job;
  });
}

function markAutomaticThesisPlanJobNotified(token, jobId) {
  return apiRequest(`/api/thesis/plan/auto-jobs/${encodeURIComponent(jobId)}/notified`, {
    method: "PATCH",
    token,
  });
}

function generateAutomaticThesisPlanPdf(token, selectedProblem, aiConfig = {}) {
  return apiDownload("/api/thesis/plan/auto-pdf", {
    method: "POST",
    token,
    body: {
      selected_problem: selectedProblem,
      ai_provider: aiConfig.provider,
      ai_model: aiConfig.model,
    },
  }).then((response) => {
    invalidateChatSessionsByMode(token, "thesis_plan");
    if (response?.chatId) {
      clearCachedChatMessages(token, response.chatId);
    }
    return response;
  });
}

function generateThesisPlanCompleteSection(token, chatId, sectionId, formalData = {}, aiConfig = {}) {
  return apiRequest("/api/thesis/plan/complete-section", {
    method: "POST",
    token,
    body: {
      chat_id: chatId,
      section_id: sectionId,
      formal_data: formalData,
      ai_provider: aiConfig.provider,
      ai_model: aiConfig.model,
    },
  });
}

function downloadThesisPlanPdf(token, chatId) {
  return apiDownload(`/api/thesis/plan/${encodeURIComponent(chatId)}/pdf`, {
    token,
  });
}

function createThesisFromPlan(token, sourcePlanChatId, title = "") {
  return apiRequest("/api/thesis/from-plan", {
    method: "POST",
    token,
    body: {
      source_plan_chat_id: sourcePlanChatId,
      title: title || undefined,
    },
  }).then((created) => {
    invalidateChatSessionsByMode(token, "thesis");
    if (created?.chat_id) {
      clearCachedChatMessages(token, created.chat_id);
    }
    return created;
  });
}

function generateThesisCompleteSection(
  token,
  chatId,
  sourcePlanChatId,
  sectionId,
  formalData = {},
  aiConfig = {}
) {
  return apiRequest("/api/thesis/complete-section", {
    method: "POST",
    token,
    body: {
      chat_id: chatId,
      source_plan_chat_id: sourcePlanChatId,
      section_id: sectionId,
      formal_data: formalData,
      ai_provider: aiConfig.provider,
      ai_model: aiConfig.model,
    },
  });
}

function downloadThesisPdf(token, chatId) {
  return apiDownload(`/api/thesis/${encodeURIComponent(chatId)}/pdf`, {
    token,
    fallbackFilename: "tesis.pdf",
  });
}

function listAutomaticThesisJobs(token, { limit = 10 } = {}) {
  const query = new URLSearchParams();
  if (limit) {
    query.set("limit", String(limit));
  }

  const queryString = query.toString();
  const path = queryString
    ? `/api/thesis/auto-jobs?${queryString}`
    : "/api/thesis/auto-jobs";

  return apiRequest(path, {
    method: "GET",
    token,
  });
}

function startAutomaticThesisJob(token, sourcePlanChatId, formalData = {}, aiConfig = {}) {
  return apiRequest("/api/thesis/auto-jobs", {
    method: "POST",
    token,
    body: {
      source_plan_chat_id: sourcePlanChatId,
      formal_data: formalData,
      ai_provider: aiConfig.provider,
      ai_model: aiConfig.model,
    },
  }).then((job) => {
    invalidateChatSessionsByMode(token, "thesis");
    if (job?.chat_id) {
      clearCachedChatMessages(token, job.chat_id);
    }
    return job;
  });
}

function markAutomaticThesisJobNotified(token, jobId) {
  return apiRequest(`/api/thesis/auto-jobs/${encodeURIComponent(jobId)}/notified`, {
    method: "PATCH",
    token,
  });
}

export {
  API_BASE_URL,
  ApiError,
  clearCachedChatMessages,
  continueThesisPlan,
  createChatSession,
  createThesisFromPlan,
  deleteDocument,
  downloadThesisPdf,
  downloadThesisPlanPdf,
  evaluateThesis,
  fetchAcademicCatalog,
  fetchAcademicProfile,
  fetchCurrentUser,
  generateAutomaticThesisPlanPdf,
  generateThesisCompleteSection,
  generateThesisPlanCompleteSection,
  listAutomaticThesisJobs,
  listAutomaticThesisPlanJobs,
  listChatMessages,
  listChatSessions,
  listDocuments,
  loginUser,
  markAutomaticThesisPlanJobNotified,
  markAutomaticThesisJobNotified,
  registerUser,
  saveAcademicProfile,
  setCachedChatMessages,
  setCachedChatSessions,
  startAutomaticThesisJob,
  startAutomaticThesisPlanJob,
  suggestThesisPlanProblems,
  uploadDocument,
};
