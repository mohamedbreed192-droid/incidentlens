"use strict";
const $ = (s, root = document) => root.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let auth = null,
  csrf = "",
  docs = [],
  noticeTimer,
  routeCounter = 0;
const labels = {
  database: "Database connection",
  credentials: "Credential validity",
  service: "Service availability",
  unknown: "Unclassified",
};
const date = (s) =>
  new Date(s).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
const pill = (state) =>
  `<span class="pill ${esc(state)}">${esc(state.replaceAll("_", " "))}</span>`;
const button = (text, href, secondary = false) =>
  `<a class="button${secondary ? " secondary" : ""}" href="${esc(href)}">${text}</a>`;
function notify(text) {
  clearTimeout(noticeTimer);
  $("#notice").textContent = text;
  noticeTimer = setTimeout(() => ($("#notice").textContent = ""), 6500);
}
async function api(path, options = {}) {
  const headers = { ...options.headers };
  if (options.body && !(options.body instanceof FormData))
    headers["Content-Type"] = "application/json";
  if (options.method && options.method !== "GET")
    headers["X-CSRF-Token"] = csrf;
  const response = await fetch(`/api${path}`, { ...options, headers });
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error("The server returned an unreadable response. Retry shortly.");
  }
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") {
      auth = null;
      showLogin();
    }
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "Check the submitted fields and input limits.",
    );
  }
  return data;
}
function brand() {
  return '<a href="#dashboard" class="brand"><img src="/static/lens.svg" alt="">IncidentLens</a>';
}
function showLogin() {
  $("#app").innerHTML =
    `<div class="login-page"><section class="login-story">${brand()}<div><p class="eyebrow">A clearer path through the noise</p><h1>From incident.<br>To evidence.<br>To a next step.</h1><p>Bring your logs and investigate with cited runbooks. Keep the evidence visible and the decision human.</p><div class="lens-art" aria-hidden="true"></div></div><footer>Northstar Labs · Fictional organization<br>Student portfolio prototype by Mohamed Said</footer></section><main id="main" class="login-panel"><div class="login-box"><p class="eyebrow">Investigation workspace</p><h1>Welcome back.</h1><p class="muted">Sign in to your incident workspace.</p><form id="login-form"><label>Username<input name="username" autocomplete="username" required maxlength="80" placeholder="engineer"></label><label>Password<input name="password" type="password" autocomplete="current-password" required maxlength="128"></label><p class="form-error" id="login-error" role="alert"></p><button class="button" type="submit">Sign in <span aria-hidden="true">↗</span></button></form><div class="login-footer"><strong>Running the demo?</strong><p>Use an account created by the explicit development seed command. Passwords are set by the person starting this instance.</p>Baseline mode needs no external AI credentials. All example incidents and runbooks are synthetic.</div></div></main></div>`;
  $("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget,
      submit = $("button", form);
    submit.disabled = true;
    submit.textContent = "Signing in…";
    $("#login-error").textContent = "";
    try {
      const result = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      auth = result.user;
      csrf = result.csrf_token;
      location.hash = "#dashboard";
      await route();
    } catch (err) {
      $("#login-error").textContent = err.message;
    } finally {
      if (submit.isConnected) {
        submit.disabled = false;
        submit.textContent = "Sign in ↗";
      }
    }
  });
}
function shell(active) {
  $("#app").innerHTML =
    `<div class="shell"><aside class="sidebar">${brand()}<p class="brand-sub">INVESTIGATION WORKSPACE</p><nav class="nav" aria-label="Main navigation">${[
      ["dashboard", "◫", "Overview"],
      ["new", "＋", "New incident"],
      ["library", "▤", "Knowledge library"],
    ]
      .map(
        ([key, icon, label]) =>
          `<a href="#${key}" class="${active === key ? "active" : ""}" ${active === key ? 'aria-current="page"' : ""}><span class="nav-icon" aria-hidden="true">${icon}</span>${label}</a>`,
      )
      .join(
        "",
      )}</nav><div class="sidebar-foot"><strong>Evidence informs. You decide.</strong>Recommendations require human review. IncidentLens never executes commands.<p class="spaced">Northstar Labs<br>Synthetic portfolio prototype</p></div></aside><div class="workspace"><header class="topbar"><span class="breadcrumb">Workspace / ${active === "library" ? "Knowledge library" : active === "new" ? "New incident" : "Incidents"}</span><div class="account"><span class="avatar" aria-hidden="true">${esc(auth.username[0].toUpperCase())}</span><span>${esc(auth.username)} · ${esc(auth.role)}</span><button class="text-button" id="logout">Sign out</button></div></header><main id="main" class="main" tabindex="-1"><div class="loading" role="status">Loading workspace…</div></main></div></div>`;
  $("#logout").addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST" });
      auth = null;
      csrf = "";
      showLogin();
      notify("You have signed out.");
    } catch (err) {
      notify(err.message);
    }
  });
}
const heading = (eyebrow, title, subtitle, action = "") =>
  `<div class="page-head"><div><p class="eyebrow">${eyebrow}</p><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>${action}</div>`;
async function dashboard(main, token) {
  const offset = Math.max(
    0,
    Number(
      new URLSearchParams(location.hash.split("?")[1] || "").get("offset"),
    ) || 0,
  );
  const [stats, incidents] = await Promise.all([
    api("/dashboard"),
    api(`/incidents?offset=${offset}&limit=20`),
  ]);
  if (token !== routeCounter) return;
  main.innerHTML =
    heading(
      "YOUR INVESTIGATION DESK",
      "Make sense of the incident.",
      "Evidence, guidance, and a review trail — in one workspace.",
      button("＋ New investigation", "#new"),
    ) +
    `<section class="stats" aria-label="Your incident statistics">${[
      ["Total incidents", stats.total, "Visible in your workspace"],
      ["Awaiting review", stats.pending, "Human judgment required"],
      ["Accepted", stats.accepted, "Recommendations accepted"],
      ["Rejected", stats.rejected, "Recommendations rejected"],
    ]
      .map(
        ([label, n, hint]) =>
          `<div class="stat"><span class="muted">${label}</span><span class="number">${n}</span><small>${hint}</small></div>`,
      )
      .join(
        "",
      )}</section><section class="card"><div class="card-head"><h2>Incident history</h2><span class="pill neutral">${stats.total} total</span></div>${incidents.length ? `<div class="table-wrap"><table><thead><tr><th>Incident</th><th>Review state</th><th>Submitted</th></tr></thead><tbody>${incidents.map((i) => `<tr><td><a href="#incident/${i.id}">${esc(i.title)}</a><span class="id">IL-${i.id.slice(0, 8).toUpperCase()}</span></td><td>${pill(i.review_state)}</td><td>${esc(date(i.created_at))}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty"><span class="empty-symbol" aria-hidden="true">◎</span><h3>Your next investigation starts here.</h3><p>Submit a log excerpt to collect observed evidence and retrieve the runbooks you can access.</p>${button("Investigate an incident", "#new")}</div>`}<div class="pagination"><span>Showing ${incidents.length ? offset + 1 : 0}–${offset + incidents.length} of ${stats.total}</span><span>${offset ? `<a href="#dashboard?offset=${Math.max(0, offset - 20)}">Previous</a> · ` : ""}${offset + incidents.length < stats.total ? `<a href="#dashboard?offset=${offset + 20}">Next page →</a>` : ""}</span></div></section><div class="callout"><strong>A deliberate baseline.</strong> Reports identify database, credential, and unavailable-service signals. Unfamiliar or conflicting evidence stays unresolved. Each report displays its actual analysis mode.</div><p class="footer-note">Counts are computed from incidents you are permitted to view. No live infrastructure is connected.</p>`;
}
function newIncident(main) {
  main.innerHTML =
    heading(
      "START WITH THE EVIDENCE",
      "Open an investigation.",
      "Paste an excerpt or upload a UTF-8 log. Your original line numbers are preserved.",
    ) +
    `<div class="two-col"><section class="card"><form id="incident-form"><label>Incident title<input name="title" required minlength="3" maxlength="160" placeholder="Checkout cannot connect to its database"></label><label>Log excerpt<textarea name="log_text" rows="12" maxlength="65536" placeholder="2026-06-04T10:04:12Z ERROR checkout postgres connection refused at db:5432"></textarea><span class="hint">Up to 64 KiB and 1,200 lines. Include timestamps and relevant surrounding context.</span></label><label>Or upload a log file<input type="file" name="file" accept=".log,.txt,text/plain"><span class="hint">If a file is selected, its contents are used instead of the pasted excerpt.</span></label><div class="callout warn">Use synthetic data for this prototype. Common secret patterns are redacted, but detection is incomplete. In model mode, redacted evidence and accessible runbooks are sent to the configured provider.</div><p class="form-error" id="incident-error" role="alert"></p><button class="button" type="submit">Investigate incident <span aria-hidden="true">↗</span></button></form></section><aside><section class="card"><p class="eyebrow">HOW IT WORKS</p><ol class="steps"><li><div><strong>Observe the signal</strong>Extract specific log lines and identify supported failure patterns.</div></li><li><div><strong>Retrieve permitted guidance</strong>Search the runbook library with PostgreSQL full-text search.</div></li><li><div><strong>Keep judgment human</strong>Inspect the sources, then accept or reject the suggested explanation.</div></li></ol></section><p class="muted">No command execution. No infrastructure changes. No automatic remediation.</p></aside></div>`;
  $("#incident-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget,
      submit = $("button[type=submit]", form);
    submit.disabled = true;
    submit.textContent = "Investigating…";
    $("#incident-error").textContent = "";
    try {
      const f = new FormData(form);
      const file = f.get("file");
      let result;
      if (file && file.size) {
        if (file.size > 65536) throw Error("Log exceeds the 64 KiB limit");
        f.delete("log_text");
        result = await api("/incidents/upload", { method: "POST", body: f });
      } else {
        result = await api("/incidents", {
          method: "POST",
          body: JSON.stringify({
            title: f.get("title"),
            log_text: f.get("log_text"),
          }),
        });
      }
      location.hash = `#incident/${result.id}`;
      notify("Investigation saved. Review its evidence and sources.");
    } catch (err) {
      $("#incident-error").textContent = err.message;
    } finally {
      if (submit.isConnected) {
        submit.disabled = false;
        submit.textContent = "Investigate incident ↗";
      }
    }
  });
}
function sources(items, citations) {
  return `<div class="sources">${items
    .map((id) => {
      const c = citations.find((x) => x.id === id);
      return c
        ? `<button class="source-button" data-source="${esc(id)}">▤ ${esc(c.key)} · § ${esc(c.section)} · v${c.version}</button>`
        : "";
    })
    .join("")}</div>`;
}
async function incidentDetail(main, id, token) {
  const [i, audit] = await Promise.all([
    api(`/incidents/${id}`),
    api(`/incidents/${id}/audit`),
  ]);
  if (token !== routeCounter) return;
  const r = i.report;
  main.innerHTML =
    heading(
      `INVESTIGATION · IL-${i.id.slice(0, 8).toUpperCase()}`,
      i.title,
      `Submitted ${date(i.created_at)}`,
      button("← All incidents", "#dashboard", true),
    ) +
    `<div class="two-col"><div><section class="card"><div class="card-head"><h2>Investigation report</h2>${pill(r.status)}</div><div class="callout${r.status !== "supported" ? " warn" : ""}"><strong>${esc(labels[r.category])}</strong><p>${r.status === "supported" ? "A supported failure pattern was found. The explanations below are suggestions for human review, not confirmed root causes." : esc(r.reason)}</p></div><div class="report-block"><p class="report-label">01 / OBSERVED LOG EVIDENCE</p>${r.observed.length ? r.observed.map((o) => `<div class="evidence"><span class="line-tag">L${o.line}</span>${esc(o.text)}</div>`).join("") : '<p class="muted">No specific supported signal was identified.</p>'}</div>${r.status === "supported" ? `<div class="report-block"><p class="report-label">02 / SUGGESTED EXPLANATION</p>${r.explanations.map((x) => `<p>${esc(x.text)}</p><small>Observed lines ${x.log_lines.map((n) => "L" + n).join(", ")}</small>${sources(x.source_ids, r.citations)}`).join("")}</div><div class="report-block"><p class="report-label">03 / SUGGESTED DIAGNOSTIC CHECKS</p><ol class="check-list">${r.checks.map((c) => `<li>${esc(c.text)}${sources(c.source_ids, r.citations)}</li>`).join("")}</ol></div>` : ""}<div class="report-block"><p class="report-label">ANALYSIS PROVENANCE</p><p class="muted">${r.mode === "model_assisted" ? `${esc(r.provider)} · ${esc(r.model)} · model assisted` : r.mode === "withheld" ? "Report withheld · source access or version changed" : "Deterministic baseline · rules + PostgreSQL retrieval"}</p>${r.fallback_reason ? `<p class="callout warn">Provider attempt unavailable (${esc(r.fallback_reason)}). This report uses the deterministic baseline.</p>` : ""}<small>${r.latency_ms !== undefined ? `${r.latency_ms} ms analysis time · ` : ""}Citation validity does not establish factual support. Inspect each source.</small></div></section><section class="card"><h2>Submitted log · redacted</h2><ol class="log-lines">${i.log_text
      .split("\n")
      .map((line) => `<li>${esc(line) || " "}</li>`)
      .join(
        "",
      )}</ol></section></div><aside><section class="card"><p class="eyebrow">HUMAN REVIEW</p><h2>Your judgment matters.</h2><p class="muted">Accept the suggested direction or record why you disagree.</p><dl class="meta-list"><div><dt>Review state</dt><dd>${pill(i.review_state)}</dd></div>${i.reviewed_at ? `<div><dt>Last reviewed</dt><dd>${esc(date(i.reviewed_at))}</dd></div>` : ""}</dl>${r.status === "supported" ? `<form id="review-form"><label>Review note<textarea name="note" rows="4" maxlength="2000" placeholder="What did you verify?">${esc(i.review_note)}</textarea></label><p class="form-error" id="review-error" role="alert"></p><div class="review-actions"><button class="button" type="submit" value="accepted">Accept</button><button class="button danger" type="submit" value="rejected">Reject</button></div></form>` : '<p class="callout warn">A supported recommendation is required before it can be accepted or rejected. Gather more evidence and submit again.</p>'}</section><section class="card"><h2>Activity history</h2><p class="muted">Application audit records; not tamper-proof.</p>${audit.map((a) => `<div class="audit-item"><strong>${esc(a.action.replaceAll("_", " "))}</strong><span>${esc(a.actor)}${a.details.decision ? " · " + esc(a.details.decision) : ""}</span><small>${esc(date(a.created_at))}</small></div>`).join("")}</section></aside></div>`;
  if ($("#review-form"))
    $("#review-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const decision = event.submitter.value;
      const buttons = form.querySelectorAll("button");
      buttons.forEach((b) => (b.disabled = true));
      try {
        await api(`/incidents/${id}/review`, {
          method: "POST",
          body: JSON.stringify({
            decision,
            note: new FormData(form).get("note"),
          }),
        });
        await route();
        notify(`Recommendation ${decision}.`);
      } catch (err) {
        $("#review-error").textContent = err.message;
        buttons.forEach((b) => (b.disabled = false));
      }
    });
}
async function library(main, token) {
  docs = await api("/documents");
  if (token !== routeCounter) return;
  main.innerHTML =
    heading(
      "THE KNOWLEDGE BEHIND THE REPORT",
      "Runbooks, with context.",
      "Versioned troubleshooting sections from a fictional organization.",
      auth.role === "admin"
        ? '<button class="button" id="add-document">＋ Add runbook</button>'
        : "",
    ) +
    `<div class="callout">${auth.role === "admin" ? "Administrator view includes archived sections." : "Only documents available to your account appear here or enter retrieval."} Content is displayed as text to keep embedded instructions and markup inert.</div><div class="doc-grid">${docs.length ? docs.map((d) => `<article class="card"><div class="card-head"><span class="pill neutral">${esc(d.key)} · v${d.version}</span>${pill(d.active ? d.access : "archived")}</div><h2>${esc(d.title)}</h2><p>§ ${esc(d.section)}</p><p>${esc(d.content.slice(0, 160))}…</p><div class="doc-actions">${d.active ? `<button class="button secondary" data-source="${d.id}">Inspect source ↗</button>` : ""}${auth.role === "admin" ? `<button class="button secondary" data-edit="${d.id}">Edit / archive</button>` : ""}</div></article>`).join("") : '<section class="card empty"><h2>No available runbooks</h2><p>An administrator can add a troubleshooting section.</p></section>'}</div>${auth.role === "admin" ? '<section class="card spaced"><div class="card-head"><h2>Administrative activity</h2><button class="text-button" id="load-audit">Load recent audit records</button></div><div id="admin-audit" class="muted">Load the last 100 application actions.</div></section>' : ""}`;
  if ($("#add-document"))
    $("#add-document").addEventListener("click", () => editDocument());
  if ($("#load-audit"))
    $("#load-audit").addEventListener("click", async () => {
      try {
        const rows = await api("/admin/audit");
        $("#admin-audit").innerHTML =
          rows
            .map(
              (a) =>
                `<div class="audit-item"><strong>${esc(a.action.replaceAll("_", " "))}</strong>${esc(a.actor)}<small>${esc(date(a.created_at))}</small></div>`,
            )
            .join("") || "No activity recorded.";
      } catch (err) {
        notify(err.message);
      }
    });
}
function editDocument(id) {
  const form = $("#document-form");
  form.reset();
  $("#editor-error").textContent = "";
  const doc = docs.find((d) => d.id === id);
  if (doc)
    for (const [key, value] of Object.entries(doc)) {
      const field = form.elements.namedItem(key);
      if (field) {
        if (field.type === "checkbox") field.checked = value;
        else field.value = value;
      }
    }
  $("#editor-dialog").showModal();
}
$("#document-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget,
    f = new FormData(form),
    id = f.get("id"),
    data = Object.fromEntries(f);
  delete data.id;
  data.active = f.has("active");
  const b = $("button[type=submit]", form);
  b.disabled = true;
  try {
    await api(`/documents${id ? "/" + id : ""}`, {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(data),
    });
    $("#editor-dialog").close();
    await route();
    notify("Runbook saved. Its version is recorded.");
  } catch (err) {
    $("#editor-error").textContent = err.message;
  } finally {
    b.disabled = false;
  }
});
document.addEventListener("click", async (event) => {
  const close = event.target.closest("[data-close]");
  if (close) {
    $("#" + close.dataset.close).close();
    return;
  }
  const edit = event.target.closest("[data-edit]");
  if (edit) {
    editDocument(edit.dataset.edit);
    return;
  }
  const source = event.target.closest("[data-source]");
  if (source) {
    source.disabled = true;
    try {
      const d = await api("/documents/" + source.dataset.source);
      $("#source-title").textContent = d.title;
      $("#source-body").innerHTML =
        `<p class="muted">${esc(d.key)} · § ${esc(d.section)} · Version ${d.version} · ${esc(d.access)}</p><p class="callout">Synthetic runbook. Inspect whether this guidance supports the report.</p><pre class="source-text">${esc(d.content)}</pre>`;
      $("#source-dialog").showModal();
    } catch (err) {
      notify(err.message);
    } finally {
      source.disabled = false;
    }
  }
});
async function route() {
  if (!auth) return;
  const hash = location.hash.slice(1) || "dashboard",
    key = hash.split("/")[0].split("?")[0],
    token = ++routeCounter;
  shell(["new", "library"].includes(key) ? key : "dashboard");
  const main = $("#main");
  try {
    if (key === "new") newIncident(main);
    else if (key === "library") await library(main, token);
    else if (key === "incident")
      await incidentDetail(main, hash.split("/")[1], token);
    else await dashboard(main, token);
  } catch (err) {
    if (auth && token === routeCounter)
      main.innerHTML = heading(
        "WORKSPACE",
        "Unable to open this view.",
        err.message,
        button("Return to overview", "#dashboard", true),
      );
  }
  if (main.isConnected) main.focus({ preventScroll: true });
}
window.addEventListener("hashchange", route);
(async () => {
  try {
    const result = await api("/auth/me");
    auth = result.user;
    csrf = result.csrf_token;
    await route();
  } catch {
    showLogin();
  }
})();
