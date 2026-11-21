const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const CLIENT_KEY = "behaviorsense_client_id";

/** Anonymous per-browser id. It scopes stored sessions to this browser; it is not a login. */
export function getClientId() {
  let id = null;
  try {
    id = localStorage.getItem(CLIENT_KEY);
  } catch (e) {
    id = null;
  }
  if (!id) {
    const random = (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2) + Date.now()).replace(/-/g, "");
    id = "client_" + random;
    try {
      localStorage.setItem(CLIENT_KEY, id);
    } catch (e) {
      /* storage blocked: id lives for this page load only */
    }
  }
  return id;
}

async function request(path, options = {}) {
  const response = await fetch(API_BASE + path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Client-Id": getClientId(), ...(options.headers || {}) },
  });
  if (response.status === 204) return null;
  let body = null;
  try {
    body = await response.json();
  } catch (e) {
    body = null;
  }
  if (!response.ok) {
    let detail = (body && body.detail) || "Request failed (" + response.status + ")";
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join("; ");
    throw new Error(detail);
  }
  return body;
}

export const api = {
  modelInfo: () => request("/api/model/info"),
  overview: () => request("/api/overview"),
  listSessions: () => request("/api/sessions"),
  startSession: (consentVersion) =>
    request("/api/sessions/start", { method: "POST", body: JSON.stringify({ consent: true, consent_version: consentVersion }) }),
  stopSession: (id) => request("/api/sessions/" + id + "/stop", { method: "POST" }),
  postMetrics: (id, minute) => request("/api/sessions/" + id + "/metrics", { method: "POST", body: JSON.stringify(minute) }),
  analytics: (id) => request("/api/sessions/" + id + "/analytics"),
  prediction: (id) => request("/api/sessions/" + id + "/prediction"),
  deleteSession: (id) => request("/api/sessions/" + id, { method: "DELETE" }),
  deleteAllData: () => request("/api/data", { method: "DELETE" }),
};

export function sessionSocketUrl(sessionId) {
  let base = API_BASE;
  if (!base) base = window.location.origin;
  base = base.replace(/^http/, "ws");
  return base + "/ws/sessions/" + sessionId + "?client_id=" + encodeURIComponent(getClientId());
}
