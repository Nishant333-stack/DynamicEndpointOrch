const loginScreen = document.querySelector("#loginScreen");
const loginForm = document.querySelector("#loginForm");
const loginEmail = document.querySelector("#loginEmail");
const loginProjectSelect = document.querySelector("#loginProjectSelect");
const loginState = document.querySelector("#loginState");
const appShell = document.querySelector("#appShell");
const logoutButton = document.querySelector("#logoutButton");
const userDisplay = document.querySelector("#userDisplay");
const sidebarProjectSelect = document.querySelector("#sidebarProjectSelect");
const topProjectSelect = document.querySelector("#topProjectSelect");
const apiBaseUrl = document.querySelector("#apiBaseUrl");
const backendStatus = document.querySelector("#backendStatus");
const backendStatusText = document.querySelector("#backendStatusText");
const uptimeMetric = document.querySelector("#uptimeMetric");
const requestMetric = document.querySelector("#requestMetric");
const avgResponseMetric = document.querySelector("#avgResponseMetric");
const errorMetric = document.querySelector("#errorMetric");
const topRefreshButton = document.querySelector("#topRefreshButton");
const navItems = document.querySelectorAll(".nav-item[data-view]");
const viewSections = document.querySelectorAll(".view-section");
const endpointRows = document.querySelector("#endpointRows");
const endpointCount = document.querySelector("#endpointCount");
const endpointFooter = document.querySelector("#endpointFooter");
const refreshButton = document.querySelector("#refreshButton");
const searchInput = document.querySelector("#searchInput");
const methodFilter = document.querySelector("#methodFilter");
const statusFilter = document.querySelector("#statusFilter");
const createForm = document.querySelector("#createForm");
const createState = document.querySelector("#createState");
const checkForm = document.querySelector("#checkForm");
const checkState = document.querySelector("#checkState");
const checkResult = document.querySelector("#checkResult");
const probeBody = document.querySelector("#probeBody");
const probeButton = document.querySelector("#probeButton");
const probeResult = document.querySelector("#probeResult");
const ruleRows = document.querySelector("#ruleRows");
const ruleCount = document.querySelector("#ruleCount");
const refreshRulesButton = document.querySelector("#refreshRulesButton");
const ruleForm = document.querySelector("#ruleForm");
const ruleState = document.querySelector("#ruleState");
const ruleEndpointSelect = document.querySelector("#ruleEndpointSelect");
const logRows = document.querySelector("#logRows");
const logCount = document.querySelector("#logCount");
const refreshLogsButton = document.querySelector("#refreshLogsButton");
const architectPanel = document.querySelector("#architectPanel");
const architectForm = document.querySelector("#architectForm");
const architectSpec = document.querySelector("#architectSpec");
const architectState = document.querySelector("#architectState");
const architectSampleButton = document.querySelector("#architectSampleButton");
const architectGenerateButton = document.querySelector("#architectGenerateButton");
const architectCommitButton = document.querySelector("#architectCommitButton");
const architectResult = document.querySelector("#architectResult");
const architectTaskMeta = document.querySelector("#architectTaskMeta");
const architectSummary = document.querySelector("#architectSummary");
const architectEndpointList = document.querySelector("#architectEndpointList");
const architectRuleList = document.querySelector("#architectRuleList");
const architectSandboxList = document.querySelector("#architectSandboxList");
const coverageMetric = document.querySelector("#coverageMetric");
const simulationMetric = document.querySelector("#simulationMetric");
const iterationMetric = document.querySelector("#iterationMetric");
const showPlanButton = document.querySelector("#showPlanButton");

const loginConnection = document.querySelector("#loginConnection");
const apiBaseInput = document.querySelector("#apiBaseInput");
const retryProjectsButton = document.querySelector("#retryProjectsButton");

const sessionStorageKey = "mockmeshDashboardSession";
const apiBaseStorageKey = "mockmeshApiBase";

// When the dashboard is served by the backend (http/https) the API lives at the
// same origin, so we use a relative base (""). When it is opened directly as a
// file:// document there is no origin to inherit, so we fall back to the
// documented local dev port. A saved override (set on the login screen) always
// wins, so the dashboard can also point at a remote/deployed API.
function defaultApiOrigin() {
  return window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";
}

function resolveApiOrigin() {
  const saved = (localStorage.getItem(apiBaseStorageKey) || "").trim();
  return saved ? saved.replace(/\/+$/, "") : defaultApiOrigin();
}

let apiOrigin = resolveApiOrigin();

function updateApiBaseDisplay() {
  const shown = apiOrigin || window.location.origin;
  apiBaseUrl.textContent = shown;
  if (apiBaseInput && document.activeElement !== apiBaseInput) {
    apiBaseInput.value = (localStorage.getItem(apiBaseStorageKey) || "").trim() || shown;
  }
}

const sampleArchitectSpec =
  "Create a POST /cards endpoint that validates card details and returns success for valid test cards and 400 for invalid ones.";

let authToken = "";
let currentUser = null;
let currentProjectId = "demo";
let projects = [];
let endpointState = [];
let ruleStateData = [];
let logStateData = [];
let activeView = "endpoints";
let logRefreshTimer = null;
let architectPollTimer = null;
let activeArchitectTaskId = null;
let lastArchitectTask = null;
let sessionStartedAt = Date.now();
let serverStartClientMs = null;

updateApiBaseDisplay();

function apiUrl(path) {
  return `${apiOrigin}${path}`;
}

function endpointUrl(path) {
  return apiUrl(`/api/projects/${encodeURIComponent(currentProjectId)}${path}`);
}

function architectUrl(path) {
  return apiUrl(`/architect${path}`);
}

function mockUrl(path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return apiUrl(`/mock/${encodeURIComponent(currentProjectId)}${normalizedPath}`);
}

function authHeaders(extra = {}) {
  return authToken ? {...extra, authorization: `Bearer ${authToken}`} : extra;
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function percentage(value) {
  return Number.isFinite(value) ? `${Math.round(value * 100)}%` : "--";
}

function methodClass(method) {
  return `method-pill method-${String(method).toLowerCase()}`;
}

function setButtonLoading(button, isLoading) {
  if (!button) {
    return;
  }
  button.disabled = isLoading;
  button.dataset.loading = isLoading ? "true" : "false";
}

function setBackendStatus(isOnline) {
  backendStatus.classList.toggle("offline", !isOnline);
  backendStatusText.textContent = isOnline ? "Backend online" : "Backend offline";
}

async function errorMessage(response, fallback) {
  const payload = await response.json().catch(() => ({}));
  return payload.detail || payload.error || fallback;
}

function formatUptime() {
  if (serverStartClientMs === null) {
    uptimeMetric.textContent = "—";
    return;
  }
  const elapsedMs = Math.max(0, Date.now() - serverStartClientMs);
  const minutes = Math.floor(elapsedMs / 60000) % 60;
  const hours = Math.floor(elapsedMs / 3600000) % 24;
  const days = Math.floor(elapsedMs / 86400000);
  uptimeMetric.textContent = `${days}d ${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m`;
}

// Uptime reflects how long the backend process has been running. We fetch the
// server's reported uptime once, derive the server start time on the client
// clock, then tick locally; refreshDashboard re-syncs to correct any drift.
async function syncServerUptime() {
  try {
    const response = await fetch(apiUrl("/api/status"));
    if (response.ok) {
      const status = await response.json();
      if (Number.isFinite(status.uptime_seconds)) {
        serverStartClientMs = Date.now() - status.uptime_seconds * 1000;
      }
    }
  } catch {
    // Backend unreachable: leave uptime showing its placeholder.
  }
  formatUptime();
}

function updateMetrics() {
  requestMetric.textContent = String(logStateData.length);
  const responses = logStateData.map((entry) => Number(entry.response_time_ms)).filter(Number.isFinite);
  const avg = responses.length
    ? responses.reduce((total, value) => total + value, 0) / responses.length
    : 0;
  avgResponseMetric.textContent = `${avg.toFixed(avg >= 100 ? 0 : 1)} ms`;
  const errors = logStateData.filter((entry) => Number(entry.response_code) >= 400).length;
  errorMetric.textContent = errors ? `${errors} (${Math.round((errors / logStateData.length) * 100)}%)` : "0";
}

function fillProjectSelect(select, selectedProjectId = currentProjectId) {
  select.innerHTML = projects.map((project) => `
    <option value="${escapeHtml(project.id)}" ${project.id === selectedProjectId ? "selected" : ""}>
      ${escapeHtml(project.name || project.id)}
    </option>
  `).join("");
}

function syncProjectSelects() {
  [sidebarProjectSelect, topProjectSelect, loginProjectSelect].forEach((select) => {
    if (select) {
      fillProjectSelect(select, currentProjectId);
    }
  });
}

async function loadProjects() {
  const response = await fetch(apiUrl("/api/projects"));
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Unable to load projects."));
  }
  const payload = await response.json();
  projects = payload.projects ?? [];
  if (!projects.length) {
    throw new Error("No projects are configured.");
  }
  if (!projects.some((project) => project.id === currentProjectId)) {
    currentProjectId = projects[0].id;
  }
  syncProjectSelects();
}

function applySession(session) {
  currentUser = {
    user_id: session.user_id,
    display_name: session.display_name,
  };
  authToken = session.token;
  projects = session.projects ?? projects;
  currentProjectId = session.default_project_id || currentProjectId;
  sessionStartedAt = Date.now();
  userDisplay.textContent = session.display_name;
  syncProjectSelects();
  loginScreen.classList.add("is-hidden");
  appShell.classList.remove("is-hidden");
  localStorage.setItem(
    sessionStorageKey,
    JSON.stringify({
      user_id: session.user_id,
      display_name: session.display_name,
      token: session.token,
      projects: session.projects,
      default_project_id: currentProjectId,
    }),
  );
}

async function login(event) {
  event.preventDefault();
  loginState.textContent = "Signing in";
  let response;
  try {
    response = await fetch(apiUrl("/api/auth/login"), {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({
        email: loginEmail.value.trim(),
        project_id: loginProjectSelect.value || currentProjectId,
      }),
    });
  } catch {
    loginState.textContent = `Could not reach the API at ${apiOrigin || window.location.origin}. Check the API URL below and reconnect.`;
    loginConnection.classList.remove("is-hidden");
    setBackendStatus(false);
    return;
  }

  if (!response.ok) {
    loginState.textContent = await errorMessage(response, "Login failed.");
    return;
  }

  const session = await response.json();
  applySession(session);
  await refreshDashboard();
}

function logout() {
  localStorage.removeItem(sessionStorageKey);
  authToken = "";
  currentUser = null;
  appShell.classList.add("is-hidden");
  loginScreen.classList.remove("is-hidden");
  loginState.textContent = "Signed out";
}

async function selectProject(projectId) {
  if (!projectId || projectId === currentProjectId) {
    syncProjectSelects();
    return;
  }
  currentProjectId = projectId;
  clearArchitectState();
  syncProjectSelects();
  if (currentUser) {
    localStorage.setItem(
      sessionStorageKey,
      JSON.stringify({
        user_id: currentUser.user_id,
        display_name: currentUser.display_name,
        token: authToken,
        projects,
        default_project_id: currentProjectId,
      }),
    );
  }
  await refreshDashboard();
}

function startLogAutoRefresh() {
  stopLogAutoRefresh();
  logRefreshTimer = window.setInterval(() => {
    if (activeView === "logs") {
      loadLogs({silent: true});
    }
  }, 3000);
}

function stopLogAutoRefresh() {
  if (logRefreshTimer !== null) {
    window.clearInterval(logRefreshTimer);
    logRefreshTimer = null;
  }
}

function switchView(viewName) {
  activeView = viewName;
  navItems.forEach((item) => {
    item.classList.toggle("active", item.dataset.view === viewName);
  });
  viewSections.forEach((section) => {
    section.classList.toggle("active", section.id === viewName);
  });

  if (viewName === "rules") {
    loadRules();
  }
  if (viewName === "logs") {
    loadLogs();
    startLogAutoRefresh();
  } else {
    stopLogAutoRefresh();
  }
}

async function refreshDashboard() {
  setBackendStatus(true);
  syncServerUptime();
  await Promise.all([
    loadEndpoints(),
    loadRules(),
    loadLogs({silent: true}),
  ]);
}

async function loadEndpoints() {
  setButtonLoading(refreshButton, true);
  try {
    const response = await fetch(endpointUrl("/endpoints"), {
      headers: authHeaders(),
    });
    if (!response.ok) {
      setBackendStatus(false);
      endpointCount.textContent = "0";
      endpointFooter.textContent = "Unable to load endpoints";
      return;
    }

    setBackendStatus(true);
    const data = await response.json();
    endpointState = data.endpoints ?? [];
    renderEndpoints();
    renderRuleEndpointOptions();
  } catch {
    setBackendStatus(false);
    endpointRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="6">Start the FastAPI app to load live endpoints.</td>
      </tr>
    `;
    endpointCount.textContent = "0";
    endpointFooter.textContent = "API unavailable";
  } finally {
    setButtonLoading(refreshButton, false);
  }
}

function filteredEndpoints() {
  const query = searchInput.value.trim().toLowerCase();
  const method = methodFilter.value;
  const status = statusFilter.value;
  return endpointState.filter((endpoint) => {
    const searchable = `${endpoint.method} ${endpoint.path} ${endpoint.name}`.toLowerCase();
    const matchesQuery = !query || searchable.includes(query);
    const matchesMethod = !method || endpoint.method === method;
    const matchesStatus =
      !status ||
      (status === "active" && endpoint.is_active) ||
      (status === "inactive" && !endpoint.is_active);
    return matchesQuery && matchesMethod && matchesStatus;
  });
}

function renderEndpoints() {
  const endpoints = filteredEndpoints();
  endpointCount.textContent = String(endpointState.length);
  endpointFooter.textContent = endpointState.length
    ? `Showing 1 to ${endpoints.length} of ${endpointState.length} endpoints`
    : "Showing 0 endpoints";

  if (!endpoints.length) {
    endpointRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="6">No endpoints match the current filters.</td>
      </tr>
    `;
    return;
  }

  endpointRows.innerHTML = endpoints.map((endpoint) => {
    const delay = endpoint.delay_ms ? `${endpoint.delay_ms} ms ${endpoint.delay_mode}` : "None";
    return `
      <tr>
        <td><span class="${methodClass(endpoint.method)}">${escapeHtml(endpoint.method)}</span></td>
        <td><span class="path-code">${escapeHtml(endpoint.path)}</span></td>
        <td>${escapeHtml(endpoint.name)}</td>
        <td>
          <span class="${endpoint.is_active ? "active-state" : "inactive-state"}">
            ${endpoint.is_active ? "Active" : "Inactive"}
          </span>
        </td>
        <td><span class="status-badge ${endpoint.default_status_code >= 300 ? "info" : ""}">${escapeHtml(endpoint.default_status_code ?? "None")}</span></td>
        <td class="${endpoint.delay_ms ? "delay-warning" : "muted"}">${escapeHtml(delay)}</td>
      </tr>
    `;
  }).join("");
}

function renderRuleEndpointOptions() {
  if (!endpointState.length) {
    ruleEndpointSelect.innerHTML = '<option value="" disabled>No endpoints available</option>';
    return;
  }
  ruleEndpointSelect.innerHTML = endpointState.map((endpoint) => `
    <option value="${escapeHtml(endpoint.id)}">
      ${escapeHtml(endpoint.method)} ${escapeHtml(endpoint.path)}
    </option>
  `).join("");
}

async function loadRules() {
  setButtonLoading(refreshRulesButton, true);
  try {
    const response = await fetch(endpointUrl("/rules"), {
      headers: authHeaders(),
    });
    if (!response.ok) {
      setBackendStatus(false);
      ruleCount.textContent = "0";
      return;
    }

    setBackendStatus(true);
    const data = await response.json();
    ruleStateData = data.rules ?? [];
    renderRules();
  } catch {
    setBackendStatus(false);
    ruleRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="5">Start the FastAPI app to load configured rules.</td>
      </tr>
    `;
    ruleCount.textContent = "0";
  } finally {
    setButtonLoading(refreshRulesButton, false);
  }
}

function renderRules() {
  ruleCount.textContent = String(ruleStateData.length);
  if (!ruleStateData.length) {
    ruleRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="5">No rules configured for this project.</td>
      </tr>
    `;
    return;
  }

  ruleRows.innerHTML = ruleStateData.map((rule) => {
    const value = rule.value === null || rule.value === undefined ? "-" : rule.value;
    return `
      <tr>
        <td>
          <span class="${methodClass(rule.endpoint_method)}">${escapeHtml(rule.endpoint_method)}</span>
          <span class="path-code">${escapeHtml(rule.endpoint_path)}</span>
        </td>
        <td>${escapeHtml(rule.condition_type)}.${escapeHtml(rule.field)}</td>
        <td>${escapeHtml(rule.operator)}</td>
        <td>${escapeHtml(value)}</td>
        <td class="${rule.action_status_code >= 400 ? "code-error" : "code-ok"}">
          ${rule.action_status_code ?? "response"}
        </td>
      </tr>
    `;
  }).join("");
}

async function loadLogs(options = {}) {
  const silent = Boolean(options.silent);
  setButtonLoading(refreshLogsButton, true);
  if (!silent) {
    logCount.textContent = "Loading";
  }
  try {
    const response = await fetch(endpointUrl("/logs?limit=50"), {
      headers: authHeaders(),
    });
    if (!response.ok) {
      setBackendStatus(false);
      logCount.textContent = "0";
      return;
    }

    setBackendStatus(true);
    const data = await response.json();
    logStateData = data.logs ?? [];
    renderLogs();
    updateMetrics();
  } catch {
    setBackendStatus(false);
    logRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="6">Start the FastAPI app to load request logs.</td>
      </tr>
    `;
    logCount.textContent = "0";
    logStateData = [];
    updateMetrics();
  } finally {
    setButtonLoading(refreshLogsButton, false);
  }
}

function renderLogs() {
  logCount.textContent = String(logStateData.length);
  if (!logStateData.length) {
    logRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="6">No requests have been logged for this project yet.</td>
      </tr>
    `;
    return;
  }

  logRows.innerHTML = logStateData.map((entry) => {
    const createdAt = new Date(entry.created_at).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    const codeClass = entry.response_code >= 400 ? "code-error" : "code-ok";
    return `
      <tr>
        <td>${escapeHtml(createdAt)}</td>
        <td><span class="${methodClass(entry.method)}">${escapeHtml(entry.method)}</span></td>
        <td><span class="path-code">${escapeHtml(entry.path)}</span></td>
        <td>${escapeHtml(entry.endpoint_name || "Unmatched")}</td>
        <td class="${codeClass}">${escapeHtml(entry.response_code)}</td>
        <td class="muted">${Number(entry.response_time_ms).toFixed(1)} ms</td>
      </tr>
    `;
  }).join("");
}

function formJson(form) {
  const formData = new FormData(form);
  const delayValue = Number(formData.get("delay_ms") || 0);
  return {
    method: formData.get("method"),
    path: formData.get("path"),
    name: formData.get("name"),
    is_active: formData.get("is_active") === "on",
    status_code: Number(formData.get("status_code") || 200),
    body_template: formData.get("body_template"),
    headers: {"content-type": "application/json"},
    delay_ms: delayValue > 0 ? delayValue : null,
    delay_mode: formData.get("delay_mode") || "fixed",
  };
}

async function createEndpoint(event) {
  event.preventDefault();
  createState.textContent = "Creating";
  const response = await fetch(endpointUrl("/endpoints"), {
    method: "POST",
    headers: authHeaders({"content-type": "application/json"}),
    body: JSON.stringify(formJson(createForm)),
  });

  if (!response.ok) {
    createState.textContent = await errorMessage(response, "Create failed");
    return;
  }

  const created = await response.json();
  createState.textContent = `Created ${created.endpoint.method} ${created.endpoint.path}`;
  createForm.reset();
  createForm.elements.status_code.value = 200;
  createForm.elements.delay_ms.value = 0;
  createForm.elements.body_template.value = '{\n  "ok": true,\n  "id": "{{id}}",\n  "trace_id": "{{uuid}}"\n}';
  createForm.elements.is_active.checked = true;
  await loadEndpoints();
  await loadRules();
}

async function createRule(event) {
  event.preventDefault();
  ruleState.textContent = "Creating";
  const formData = new FormData(ruleForm);
  const payload = {
    endpoint_id: formData.get("endpoint_id"),
    condition_type: formData.get("condition_type"),
    field: formData.get("field"),
    operator: formData.get("operator"),
    value: formData.get("value") || null,
    status_code: Number(formData.get("status_code") || 200),
    body_template: formData.get("body_template"),
    headers: {"content-type": "application/json"},
  };
  const response = await fetch(endpointUrl("/rules"), {
    method: "POST",
    headers: authHeaders({"content-type": "application/json"}),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    ruleState.textContent = await errorMessage(response, "Create failed");
    return;
  }

  const created = await response.json();
  ruleState.textContent = `Created ${created.rule.condition_type}.${created.rule.field}`;
  await loadRules();
}

function checkErrorCard(title, hintHtml) {
  checkResult.className = "result-card check-output is-error";
  checkResult.innerHTML = `
    <div class="co-head co-head-error"><span class="co-icon">✕</span> ${escapeHtml(title)}</div>
    <p class="co-hint">${hintHtml}</p>
  `;
}

function renderCheckResult(result, payload) {
  const requested = `<span class="${methodClass(payload.method)}">${escapeHtml(payload.method)}</span> <code>${escapeHtml(payload.path)}</code>`;

  if (!result.exists) {
    const hint = result.exact_signature_exists
      ? "An endpoint with this exact method and path exists but is <strong>inactive</strong>. Activate it to make it resolve."
      : `No active endpoint matches this path in <strong>${escapeHtml(currentProjectId)}</strong>. Create one to handle it.`;
    checkResult.className = "result-card check-output is-error";
    checkResult.innerHTML = `
      <div class="co-head co-head-error"><span class="co-icon">✕</span> No match</div>
      <dl>
        <dt>Requested</dt><dd>${requested}</dd>
      </dl>
      <p class="co-hint">${hint}</p>
    `;
    return;
  }

  const endpoint = result.endpoint;
  const params = Object.entries(result.path_params || {});
  const paramHtml = params.length
    ? `<div class="co-chips">${params
        .map(([key, value]) => `<span class="co-chip">${escapeHtml(key)} = ${escapeHtml(value)}</span>`)
        .join("")}</div>`
    : '<span class="muted">None</span>';
  const delay = result.delay_ms
    ? `${escapeHtml(result.delay_ms)} ms ${escapeHtml(result.delay_mode)}`
    : "No delay";
  const matchType = result.exact_signature_exists ? "Exact signature" : "Pattern match";
  const stateHtml = endpoint.is_active
    ? '<span class="active-state">Active</span>'
    : '<span class="inactive-state">Inactive</span>';

  checkResult.className = "result-card check-output is-success";
  checkResult.innerHTML = `
    <div class="co-head co-head-success"><span class="co-icon">✓</span> Match found</div>
    <dl>
      <dt>Endpoint</dt><dd><strong>${escapeHtml(endpoint.name)}</strong></dd>
      <dt>Resolves</dt><dd><span class="${methodClass(endpoint.method)}">${escapeHtml(endpoint.method)}</span> <code>${escapeHtml(endpoint.path)}</code></dd>
      <dt>Requested</dt><dd>${requested}</dd>
      <dt>Path params</dt><dd>${paramHtml}</dd>
      <dt>State</dt><dd>${stateHtml}</dd>
      <dt>Delay</dt><dd>${escapeHtml(delay)}</dd>
      <dt>Match</dt><dd>${escapeHtml(matchType)}</dd>
    </dl>
    <p class="co-hint">Use <strong>Run mock request</strong> below to see the actual response body.</p>
  `;
}

async function checkEndpoint(event) {
  event.preventDefault();
  checkResult.className = "result-card check-output";
  checkResult.textContent = "Checking…";
  const formData = new FormData(checkForm);
  const payload = {
    method: formData.get("method"),
    path: formData.get("path"),
  };

  let response;
  try {
    response = await fetch(endpointUrl("/endpoints/check"), {
      method: "POST",
      headers: authHeaders({"content-type": "application/json"}),
      body: JSON.stringify(payload),
    });
  } catch {
    checkErrorCard("Request failed", `Could not reach the API at ${escapeHtml(apiOrigin || window.location.origin)}.`);
    return;
  }

  if (!response.ok) {
    checkErrorCard("Error", escapeHtml(await errorMessage(response, "Unable to check this endpoint.")));
    return;
  }

  const result = await response.json();
  renderCheckResult(result, payload);
}

async function runMockProbe() {
  probeResult.className = "result-card";
  probeResult.textContent = "Running mock request";
  setButtonLoading(probeButton, true);
  const formData = new FormData(checkForm);
  const method = String(formData.get("method") || "GET");
  const path = String(formData.get("path") || "/");
  const init = {method, headers: authHeaders({})};

  if (!["GET", "DELETE"].includes(method)) {
    init.headers = authHeaders({"content-type": "application/json"});
    init.body = probeBody.value || "{}";
  }

  const startedAt = performance.now();
  try {
    const response = await fetch(mockUrl(path), init);
    const elapsedMs = performance.now() - startedAt;
    const bodyText = await response.text();
    probeResult.className = response.ok ? "result-card success" : "result-card error";
    probeResult.textContent = `${method} ${path} returned ${response.status} in ${elapsedMs.toFixed(1)} ms. Body: ${bodyText}`;
    await wait(700);
    await loadLogs({silent: true});
  } catch {
    probeResult.className = "result-card error";
    probeResult.textContent = "Unable to run the mock request.";
  } finally {
    setButtonLoading(probeButton, false);
  }
}

function clearArchitectPoll() {
  if (architectPollTimer !== null) {
    window.clearTimeout(architectPollTimer);
    architectPollTimer = null;
  }
}

function clearArchitectState() {
  clearArchitectPoll();
  activeArchitectTaskId = null;
  lastArchitectTask = null;
  architectState.textContent = "Ready";
  architectTaskMeta.textContent = "Generated plan";
  architectResult.className = "result-card";
  architectResult.textContent = "Ready to generate a sandboxed endpoint plan.";
  architectSummary.textContent = "No sandbox run yet.";
  coverageMetric.textContent = "--";
  simulationMetric.textContent = "--";
  iterationMetric.textContent = "--";
  architectCommitButton.disabled = true;
  renderMiniList(architectEndpointList, "No generated endpoints.", []);
  renderMiniList(architectRuleList, "No generated rules.", []);
  renderMiniList(architectSandboxList, "No sandbox cases.", []);
}

function renderMiniList(container, emptyText, items) {
  if (!items.length) {
    container.className = "mini-list empty";
    container.textContent = emptyText;
    return;
  }
  container.className = "mini-list";
  container.innerHTML = items.join("");
}

function renderArchitectTask(task) {
  lastArchitectTask = task;
  const result = task.result || {};
  const metrics = result.metrics || {};
  const config = result.generated_config || {};
  const plan = result.plan || {};
  const sandbox = result.sandbox_result || {};
  activeArchitectTaskId = task.task_id;

  const endpoints = config.endpoints || [];
  const rules = config.rules || [];
  const cases = sandbox.cases || [];
  architectTaskMeta.textContent = endpoints.length
    ? `Generated plan (${endpoints.length} endpoint${endpoints.length === 1 ? "" : "s"})`
    : `Task ${task.task_id.slice(0, 8)} · ${task.status}`;
  coverageMetric.textContent = percentage(metrics.specification_coverage);
  simulationMetric.textContent = percentage(metrics.simulation_pass_rate);
  iterationMetric.textContent = metrics.iterations ?? "--";

  const endpointItems = endpoints.map((entry) => {
    const endpoint = entry.endpoint;
    const delay = endpoint.delay_ms ? `${endpoint.delay_ms} ms ${endpoint.delay_mode}` : "No delay";
    return `
      <div class="mini-item">
        <div class="mini-item-header">
          <span class="${methodClass(endpoint.method)}">${escapeHtml(endpoint.method)}</span>
          <code>${escapeHtml(endpoint.path)}</code>
        </div>
        <strong>${escapeHtml(endpoint.name)}</strong>
        <span>Status ${escapeHtml(endpoint.status_code)} · ${escapeHtml(delay)}</span>
      </div>
    `;
  });
  const ruleItems = rules.map((entry) => {
    const rule = entry.rule;
    return `
      <div class="mini-item">
        <strong>${escapeHtml(entry.endpoint_key)}</strong>
        <code>${escapeHtml(rule.condition_type)}.${escapeHtml(rule.field)} ${escapeHtml(rule.operator)} ${escapeHtml(rule.value ?? "")}</code>
        <span>Returns ${escapeHtml(rule.status_code)}</span>
      </div>
    `;
  });
  const sandboxItems = cases.map((testCase) => {
    const className = testCase.passed ? "code-ok" : "code-error";
    return `
      <div class="mini-item">
        <strong class="${className}">${escapeHtml(testCase.scenario_name)}</strong>
        <span>Expected ${escapeHtml(testCase.expected_status_code)}, got ${escapeHtml(testCase.actual_status_code)} in ${Number(testCase.response_time_ms).toFixed(1)} ms</span>
      </div>
    `;
  });

  renderMiniList(architectEndpointList, "No generated endpoints.", endpointItems);
  renderMiniList(architectRuleList, "No generated rules.", ruleItems);
  renderMiniList(architectSandboxList, "No sandbox cases.", sandboxItems);

  const firstCase = cases[0];
  architectSummary.textContent = firstCase
    ? firstCase.response_body
    : result.error || plan.summary || "Architect task is running.";

  const succeeded = task.status === "succeeded";
  architectCommitButton.disabled = !succeeded;
  if (succeeded) {
    architectState.textContent = "Sandbox passed";
    architectResult.className = "result-card success";
    architectResult.textContent = "Generation succeeded. Review the plan, then commit it into the active repository.";
  } else if (task.status === "dead_lettered" || task.status === "failed") {
    architectState.textContent = "Needs review";
    architectResult.className = "result-card error";
    architectResult.textContent = result.error || task.error || "The architect workflow did not produce a valid config.";
  }
}

async function pollArchitectTask(taskId) {
  clearArchitectPoll();
  try {
    const response = await fetch(architectUrl(`/tasks/${encodeURIComponent(taskId)}`), {
      headers: authHeaders(),
    });
    if (!response.ok) {
      architectState.textContent = "Poll failed";
      architectResult.className = "result-card error";
      architectResult.textContent = await errorMessage(response, "Unable to poll architect task.");
      setButtonLoading(architectGenerateButton, false);
      return;
    }
    const task = await response.json();
    renderArchitectTask(task);
    if (task.status === "queued" || task.status === "running") {
      architectState.textContent = task.status === "queued" ? "Queued" : "Running";
      architectResult.className = "result-card";
      architectResult.textContent = "Planner, codegen, critic, and sandbox agents are evaluating the request.";
      architectPollTimer = window.setTimeout(() => pollArchitectTask(taskId), 500);
      return;
    }
  } catch {
    architectState.textContent = "API unavailable";
    architectResult.className = "result-card error";
    architectResult.textContent = "The Architect API is not available on this server.";
  } finally {
    setButtonLoading(architectGenerateButton, architectPollTimer !== null);
  }
}

async function generateArchitecture(event) {
  event.preventDefault();
  clearArchitectPoll();
  architectState.textContent = "Submitting";
  architectResult.className = "result-card";
  architectResult.textContent = "Submitting spec to the architect workflow.";
  architectCommitButton.disabled = true;
  setButtonLoading(architectGenerateButton, true);

  try {
    const response = await fetch(architectUrl("/generate"), {
      method: "POST",
      headers: authHeaders({"content-type": "application/json"}),
      body: JSON.stringify({
        project_id: currentProjectId,
        raw_spec: architectSpec.value.trim(),
      }),
    });
    if (!response.ok) {
      architectState.textContent = "Generate failed";
      architectResult.className = "result-card error";
      architectResult.textContent = await errorMessage(response, "Unable to generate architecture.");
      setButtonLoading(architectGenerateButton, false);
      return;
    }
    const payload = await response.json();
    activeArchitectTaskId = payload.task_id;
    architectTaskMeta.textContent = `Task ${payload.task_id.slice(0, 8)} · ${payload.status}`;
    await pollArchitectTask(payload.task_id);
  } catch {
    architectState.textContent = "API unavailable";
    architectResult.className = "result-card error";
    architectResult.textContent = "The Architect API is not available on this server.";
    setButtonLoading(architectGenerateButton, false);
  }
}

async function commitArchitecture() {
  if (!activeArchitectTaskId) {
    return;
  }
  architectState.textContent = "Committing";
  architectResult.className = "result-card";
  architectResult.textContent = "Committing generated endpoints to the active repository.";
  setButtonLoading(architectCommitButton, true);

  try {
    const response = await fetch(architectUrl("/commit"), {
      method: "POST",
      headers: authHeaders({"content-type": "application/json"}),
      body: JSON.stringify({
        task_id: activeArchitectTaskId,
        project_id: currentProjectId,
      }),
    });
    if (!response.ok) {
      architectState.textContent = "Commit failed";
      architectResult.className = "result-card error";
      architectResult.textContent = await errorMessage(response, "Unable to commit generated endpoints.");
      return;
    }
    const payload = await response.json();
    architectState.textContent = "Committed";
    architectResult.className = "result-card success";
    architectResult.textContent = payload.committed_endpoints
      ? `Committed ${payload.committed_endpoints} endpoint${payload.committed_endpoints === 1 ? "" : "s"} and ${payload.committed_rules} rule${payload.committed_rules === 1 ? "" : "s"} to ${currentProjectId}.`
      : "No new endpoints were committed because those method/path signatures already exist. Inventory refreshed.";
    await refreshDashboard();
  } catch {
    architectState.textContent = "Commit unavailable";
    architectResult.className = "result-card error";
    architectResult.textContent = "Unable to reach the Architect commit API.";
  } finally {
    architectCommitButton.disabled = false;
    setButtonLoading(architectCommitButton, false);
  }
}

function showPlanDetails() {
  if (!lastArchitectTask?.result?.generated_config) {
    architectResult.className = "result-card";
    architectResult.textContent = "Generate a plan first.";
    return;
  }
  architectResult.className = "result-card";
  architectResult.textContent = JSON.stringify(lastArchitectTask.result.generated_config, null, 2);
}

async function reconnectProjects() {
  const value = apiBaseInput.value.trim().replace(/\/+$/, "");
  if (value && value !== window.location.origin) {
    localStorage.setItem(apiBaseStorageKey, value);
  } else {
    localStorage.removeItem(apiBaseStorageKey);
  }
  apiOrigin = resolveApiOrigin();
  updateApiBaseDisplay();
  loginState.textContent = "Connecting";
  setButtonLoading(retryProjectsButton, true);
  try {
    await loadProjects();
    loginConnection.classList.add("is-hidden");
    loginState.textContent = "Ready";
    setBackendStatus(true);
  } catch (error) {
    const reachable = apiOrigin || window.location.origin;
    loginState.textContent = `${error.message} Still cannot reach the API at ${reachable}.`;
    loginConnection.classList.remove("is-hidden");
    setBackendStatus(false);
  } finally {
    setButtonLoading(retryProjectsButton, false);
  }
}

async function initialize() {
  formatUptime();
  window.setInterval(formatUptime, 15000);
  try {
    await loadProjects();
  } catch (error) {
    const reachable = apiOrigin || window.location.origin;
    loginState.textContent = `${error.message} Could not reach the API at ${reachable}.`;
    loginConnection.classList.remove("is-hidden");
    updateApiBaseDisplay();
    setBackendStatus(false);
    return;
  }

  syncServerUptime();

  const savedSession = localStorage.getItem(sessionStorageKey);
  if (savedSession) {
    try {
      const session = JSON.parse(savedSession);
      applySession(session);
      await refreshDashboard();
      return;
    } catch {
      localStorage.removeItem(sessionStorageKey);
    }
  }
  loginScreen.classList.remove("is-hidden");
  appShell.classList.add("is-hidden");
}

loginForm.addEventListener("submit", login);
logoutButton.addEventListener("click", logout);
retryProjectsButton.addEventListener("click", reconnectProjects);
sidebarProjectSelect.addEventListener("change", () => selectProject(sidebarProjectSelect.value));
topProjectSelect.addEventListener("change", () => selectProject(topProjectSelect.value));
loginProjectSelect.addEventListener("change", () => {
  currentProjectId = loginProjectSelect.value || currentProjectId;
  syncProjectSelects();
});
createForm.addEventListener("submit", createEndpoint);
ruleForm.addEventListener("submit", createRule);
checkForm.addEventListener("submit", checkEndpoint);
probeButton.addEventListener("click", runMockProbe);
refreshButton.addEventListener("click", loadEndpoints);
topRefreshButton.addEventListener("click", refreshDashboard);
refreshRulesButton.addEventListener("click", loadRules);
refreshLogsButton.addEventListener("click", () => loadLogs());
architectForm.addEventListener("submit", generateArchitecture);
architectSampleButton.addEventListener("click", () => {
  architectSpec.value = sampleArchitectSpec;
  architectState.textContent = "Sample loaded";
});
architectCommitButton.addEventListener("click", commitArchitecture);
showPlanButton.addEventListener("click", showPlanDetails);
searchInput.addEventListener("input", renderEndpoints);
methodFilter.addEventListener("change", renderEndpoints);
statusFilter.addEventListener("change", renderEndpoints);
navItems.forEach((item) => {
  item.addEventListener("click", (event) => {
    event.preventDefault();
    window.history.replaceState(null, "", `#${item.dataset.view}`);
    switchView(item.dataset.view);
  });
});

initialize();
