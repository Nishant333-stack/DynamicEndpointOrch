const endpointRows = document.querySelector("#endpointRows");
const endpointCount = document.querySelector("#endpointCount");
const pageTitle = document.querySelector("#pageTitle");
const pageSubtitle = document.querySelector("#pageSubtitle");
const navItems = document.querySelectorAll(".nav-item[data-view]");
const viewSections = document.querySelectorAll(".view-section");
const projectIdInput = document.querySelector("#projectId");
const backendStatus = document.querySelector("#backendStatus");
const backendStatusText = document.querySelector("#backendStatusText");
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
let endpointState = [];
let ruleStateData = [];
let logStateData = [];
let activeView = "endpoints";
let logRefreshTimer = null;
const apiOrigin = window.location.protocol === "file:" ? "http://127.0.0.1:8765" : "";
const viewCopy = {
  endpoints: {
    title: "Endpoints",
    subtitle: "Configure dynamic mock routes for the demo project.",
  },
  rules: {
    title: "Rules",
    subtitle: "Create ordered conditions that select alternate mock responses.",
  },
  logs: {
    title: "Logs",
    subtitle: "Inspect requests resolved by the Dynamic Endpoint Orchestrator.",
  },
};

function projectId() {
  return projectIdInput.value.trim() || "demo";
}

function endpointUrl(path) {
  return `${apiOrigin}/api/projects/${encodeURIComponent(projectId())}${path}`;
}

function mockUrl(path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${apiOrigin}/mock/${encodeURIComponent(projectId())}${normalizedPath}`;
}

function methodClass(method) {
  return `method-pill method-${method.toLowerCase()}`;
}

function setBackendStatus(isOnline) {
  backendStatus.classList.toggle("offline", !isOnline);
  backendStatusText.textContent = isOnline ? "Backend online" : "Backend offline";
}

function setButtonLoading(button, isLoading) {
  if (!button) {
    return;
  }
  button.disabled = isLoading;
  button.dataset.loading = isLoading ? "true" : "false";
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
  const copy = viewCopy[viewName] || viewCopy.endpoints;
  pageTitle.textContent = copy.title;
  pageSubtitle.textContent = copy.subtitle;
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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadEndpoints() {
  setButtonLoading(refreshButton, true);
  endpointCount.textContent = "Loading endpoints";
  let response;
  try {
    response = await fetch(endpointUrl("/endpoints"));
  } catch {
    setButtonLoading(refreshButton, false);
    setBackendStatus(false);
    endpointRows.innerHTML = "";
    endpointCount.textContent = "API unavailable";
    endpointRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="5">
          Start the FastAPI app and open http://127.0.0.1:8765/dashboard to load live endpoints.
        </td>
      </tr>
    `;
    return;
  }

  if (!response.ok) {
    setButtonLoading(refreshButton, false);
    setBackendStatus(false);
    endpointRows.innerHTML = "";
    endpointCount.textContent = "Unable to load endpoints";
    return;
  }

  setBackendStatus(true);
  const data = await response.json();
  endpointState = data.endpoints ?? [];
  renderEndpoints();
  renderRuleEndpointOptions();
  setButtonLoading(refreshButton, false);
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
  const countText = `${endpoints.length} of ${endpointState.length} configured endpoint${endpointState.length === 1 ? "" : "s"}`;
  endpointCount.textContent = countText;
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
          <span class="muted"> · ${endpoint.default_status_code ?? "No response"}</span>
        </td>
        <td class="muted">${escapeHtml(delay)}</td>
      </tr>
    `;
  }).join("");
}

function renderRuleEndpointOptions() {
  ruleEndpointSelect.innerHTML = endpointState.map((endpoint) => `
    <option value="${escapeHtml(endpoint.id)}">
      ${escapeHtml(endpoint.method)} ${escapeHtml(endpoint.path)}
    </option>
  `).join("");
}

async function loadRules() {
  setButtonLoading(refreshRulesButton, true);
  ruleCount.textContent = "Loading rules";
  let response;
  try {
    response = await fetch(endpointUrl("/rules"));
  } catch {
    setButtonLoading(refreshRulesButton, false);
    setBackendStatus(false);
    ruleCount.textContent = "API unavailable";
    ruleRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="5">
          Start the FastAPI app to load configured rules.
        </td>
      </tr>
    `;
    return;
  }
  if (!response.ok) {
    setButtonLoading(refreshRulesButton, false);
    setBackendStatus(false);
    ruleCount.textContent = "Unable to load rules";
    return;
  }

  setBackendStatus(true);
  const data = await response.json();
  ruleStateData = data.rules ?? [];
  renderRules();
  setButtonLoading(refreshRulesButton, false);
}

function renderRules() {
  ruleCount.textContent = `${ruleStateData.length} configured rule${ruleStateData.length === 1 ? "" : "s"}`;
  if (!ruleStateData.length) {
    ruleRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="5">No rules configured for this project.</td>
      </tr>
    `;
    return;
  }

  ruleRows.innerHTML = ruleStateData.map((rule) => {
    const value = rule.value === null || rule.value === undefined ? "—" : rule.value;
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
    logCount.textContent = "Loading logs";
  }
  let response;
  try {
    response = await fetch(endpointUrl("/logs?limit=50"));
  } catch {
    setButtonLoading(refreshLogsButton, false);
    setBackendStatus(false);
    logCount.textContent = "API unavailable";
    logRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="6">
          Start the FastAPI app to load request logs.
        </td>
      </tr>
    `;
    return;
  }
  if (!response.ok) {
    setButtonLoading(refreshLogsButton, false);
    setBackendStatus(false);
    logCount.textContent = "Unable to load logs";
    return;
  }

  setBackendStatus(true);
  const data = await response.json();
  logStateData = data.logs ?? [];
  renderLogs();
  setButtonLoading(refreshLogsButton, false);
}

function renderLogs() {
  logCount.textContent = `${logStateData.length} recent request${logStateData.length === 1 ? "" : "s"}`;
  if (!logStateData.length) {
    logRows.innerHTML = `
      <tr>
        <td class="empty-row" colspan="6">
          No requests have been logged yet. Call a /mock route, then refresh logs.
        </td>
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
  const headers = {"content-type": "application/json"};
  const delayValue = formData.get("delay_ms");
  return {
    method: formData.get("method"),
    path: formData.get("path"),
    name: formData.get("name"),
    is_active: formData.get("is_active") === "on",
    status_code: Number(formData.get("status_code") || 200),
    body_template: formData.get("body_template"),
    headers,
    delay_ms: delayValue ? Number(delayValue) : null,
    delay_mode: formData.get("delay_mode") || "fixed",
  };
}

createForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  createState.textContent = "Creating";
  const payload = formJson(createForm);
  const response = await fetch(endpointUrl("/endpoints"), {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    createState.textContent = error.detail || "Create failed";
    return;
  }

  const created = await response.json();
  createState.textContent = `Created ${created.endpoint.method} ${created.endpoint.path}`;
  createForm.reset();
  createForm.elements.status_code.value = 200;
  createForm.elements.body_template.value = '{"ok":true,"id":"{{refund_id}}","trace_id":"{{uuid}}"}';
  createForm.elements.is_active.checked = true;
  await loadEndpoints();
  await loadRules();
});

ruleForm.addEventListener("submit", async (event) => {
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
    headers: {"content-type": "application/json"},
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    ruleState.textContent = error.detail || "Create failed";
    return;
  }

  const created = await response.json();
  ruleState.textContent = `Created ${created.rule.condition_type}.${created.rule.field}`;
  await loadRules();
});

checkForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  checkState.textContent = "Checking";
  checkResult.className = "result-card";
  const formData = new FormData(checkForm);
  const payload = {
    method: formData.get("method"),
    path: formData.get("path"),
  };
  const response = await fetch(endpointUrl("/endpoints/check"), {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    checkState.textContent = "Error";
    checkResult.className = "result-card error";
    checkResult.textContent = "Unable to check this endpoint.";
    return;
  }

  const result = await response.json();
  if (!result.exists) {
    checkState.textContent = "No match";
    checkResult.className = "result-card error";
    checkResult.textContent = `${payload.method} ${payload.path} does not match an active endpoint.`;
    return;
  }

  checkState.textContent = "Matched";
  checkResult.className = "result-card success";
  const pathParams = Object.keys(result.path_params || {}).length
    ? ` Path params: ${JSON.stringify(result.path_params)}.`
    : "";
  const delay = result.delay_ms
    ? ` Configured delay: ${result.delay_ms} ms ${result.delay_mode}.`
    : " No delay configured.";
  checkResult.textContent = `${payload.method} ${payload.path} resolves to ${result.endpoint.name} (${result.endpoint.path}).${pathParams}${delay}`;
});

probeButton.addEventListener("click", async () => {
  probeResult.className = "result-card";
  probeResult.textContent = "Running mock request";
  const formData = new FormData(checkForm);
  const method = String(formData.get("method") || "GET");
  const path = String(formData.get("path") || "/");
  const init = {method, headers: {}};

  if (!["GET", "DELETE"].includes(method)) {
    init.headers = {"content-type": "application/json"};
    init.body = probeBody.value || "{}";
  }

  const startedAt = performance.now();
  try {
    const response = await fetch(mockUrl(path), init);
    const elapsedMs = performance.now() - startedAt;
    const bodyText = await response.text();
    probeResult.className = response.ok ? "result-card success" : "result-card error";
    probeResult.textContent = `${method} ${path} returned ${response.status} in ${elapsedMs.toFixed(1)} ms. Body: ${bodyText}`;
    await loadLogs();
  } catch {
    probeResult.className = "result-card error";
    probeResult.textContent = "Unable to run the mock request.";
  }
});

refreshButton.addEventListener("click", loadEndpoints);
refreshRulesButton.addEventListener("click", loadRules);
refreshLogsButton.addEventListener("click", loadLogs);
projectIdInput.addEventListener("change", async () => {
  await loadEndpoints();
  await loadRules();
  await loadLogs({silent: activeView !== "logs"});
});
searchInput.addEventListener("input", renderEndpoints);
methodFilter.addEventListener("change", renderEndpoints);
statusFilter.addEventListener("change", renderEndpoints);
navItems.forEach((item) => {
  item.addEventListener("click", (event) => {
    event.preventDefault();
    switchView(item.dataset.view);
  });
});

loadEndpoints();
loadRules();
loadLogs();
