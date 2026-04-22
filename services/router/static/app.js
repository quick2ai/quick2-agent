// Quick2 Router Console — pure vanilla JS against the router v2 endpoints.
const API = "";  // same-origin

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const state = {
  models: [],
  agents: [],
  taxonomy: null,
  benchmarks: null,
  verticals: [],
  vendors: new Set(),
  complianceAll: new Set(),
};

// ---- tabs ----------------------------------------------------------------
$$(".tab").forEach(btn => btn.addEventListener("click", () => {
  $$(".tab").forEach(b => b.classList.toggle("active", b === btn));
  const paneId = "pane-" + btn.dataset.pane;
  $$(".pane").forEach(p => p.classList.toggle("active", p.id === paneId));
  if (btn.dataset.pane === "leaderboards") renderLeaderboardsForm();
  if (btn.dataset.pane === "models") renderModels();
  if (btn.dataset.pane === "agents") renderAgents();
  if (btn.dataset.pane === "taxonomy") renderTaxonomy();
}));

// ---- fetch helpers -------------------------------------------------------
async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { "content-type": "application/json" },
    ...opts,
  });
  if (!r.ok) {
    let body = {};
    try { body = await r.json(); } catch {}
    throw new Error(body.detail || `${r.status} ${r.statusText}`);
  }
  return r.json();
}

// ---- initial load --------------------------------------------------------
async function boot() {
  try {
    const [models, agents, taxonomy, benchmarks] = await Promise.all([
      api("/v2/models"),
      api("/v2/agents"),
      api("/v2/taxonomy"),
      api("/v2/benchmarks"),
    ]);
    state.models = models.models;
    state.agents = agents.agents;
    state.taxonomy = taxonomy;
    state.benchmarks = benchmarks;
    state.verticals = Object.keys(taxonomy.by_vertical).sort();
    state.vendors = new Set(state.models.map(m => m.provider));
    state.models.forEach(m => (m.compliance || []).forEach(c => state.complianceAll.add(c)));
    $("#model-count").textContent = `${models.count} models (${models.curated_count} curated + ${models.openrouter_count} openrouter)`;
    renderConstraintChips();
  } catch (e) {
    $("#api-status").textContent = "offline";
    $("#api-status").classList.replace("pill-ok", "pill-err");
    console.error(e);
  }
}

function renderConstraintChips() {
  const vendors = $("#c-vendors");
  vendors.innerHTML = "";
  [...state.vendors].sort().forEach(v => {
    const c = document.createElement("span");
    c.className = "chip";
    c.textContent = v;
    c.addEventListener("click", () => c.classList.toggle("on"));
    vendors.appendChild(c);
  });
  const comp = $("#c-compliance");
  comp.innerHTML = "";
  [...state.complianceAll].sort().forEach(v => {
    const c = document.createElement("span");
    c.className = "chip";
    c.textContent = v;
    c.addEventListener("click", () => c.classList.toggle("on"));
    comp.appendChild(c);
  });
}

// ---- route pane ----------------------------------------------------------
function collectConstraints() {
  const readNumber = (id) => {
    const v = $(id).value.trim();
    return v ? Number(v) : undefined;
  };
  const chipValues = (id) => $$(`#${id} .chip.on`).map(el => el.textContent);
  const c = {};
  const lat = readNumber("#c-latency"); if (lat) c.max_latency_ms = lat;
  const cost = readNumber("#c-cost"); if (cost) c.max_cost_usd = cost;
  const ctx = readNumber("#c-ctx"); if (ctx) c.min_context_window = ctx;
  const region = $("#c-region").value; if (region) c.region = region;
  const vendors = chipValues("c-vendors"); if (vendors.length) c.vendor_allowlist = vendors;
  const comp = chipValues("c-compliance"); if (comp.length) c.compliance_required = comp;
  if ($("#c-open").checked) c.open_weights_only = true;
  if ($("#c-tools").checked) c.force_tools = true;
  if ($("#c-explore").checked) c.explore = true;
  return c;
}

$("#route-btn").addEventListener("click", async () => {
  const btn = $("#route-btn");
  const text = $("#prompt").value.trim();
  if (!text) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="loading"></span> Routing…';
  try {
    const decision = await api("/v2/route", {
      method: "POST",
      body: JSON.stringify({ text, constraints: collectConstraints() }),
    });
    renderDecision(decision);
  } catch (e) {
    $("#decision").innerHTML = `<div class="error">${e.message}</div>`;
    $("#decision").classList.remove("empty");
  } finally {
    btn.disabled = false;
    btn.textContent = "Route";
  }
});

function renderDecision(d) {
  const el = $("#decision");
  el.classList.remove("empty");
  el.innerHTML = "";

  // Features
  const feat = d.features;
  const featSec = document.createElement("section");
  featSec.innerHTML = `<h3>Features</h3>
    <div class="kv">
      <span>lang: <b>${feat.language}</b></span>
      <span>modalities: <b>${feat.modalities.join(", ")}</b></span>
      <span>reasoning: <b>${feat.estimated_reasoning}/5</b></span>
      <span>ctx tokens: <b>${feat.estimated_context_tokens.toLocaleString()}</b></span>
      <span>PII: <b>${feat.pii_hits}</b></span>
      <span>regulated: <b>${feat.regulated}</b></span>
    </div>`;
  el.appendChild(featSec);

  // Intents
  const intSec = document.createElement("section");
  intSec.innerHTML = `<h3>Top intents (confidence ${d.intent_confidence})</h3>`;
  d.top_intents.forEach((m, i) => {
    const row = document.createElement("div");
    row.className = "intent" + (i === 0 ? " primary" : "");
    row.innerHTML = `
      <div class="label">
        <b>${m.label}</b>
        <div class="id">${m.intent_id} · ${m.domain}/${m.vertical}</div>
      </div>
      <div class="score-bar"><span style="width:${Math.round(Math.min(1, m.score * 2) * 100)}%"></span></div>
      <div class="muted">${m.score.toFixed(3)}</div>`;
    intSec.appendChild(row);
  });
  el.appendChild(intSec);

  // Tools + skills
  const tsSec = document.createElement("section");
  tsSec.innerHTML = `<h3>Inferred</h3>
    <div class="kv"><span><b>tools</b>: ${d.tools.join(", ") || "—"}</span>
                    <span><b>skills</b>: ${d.skills.join(", ") || "—"}</span></div>`;
  el.appendChild(tsSec);

  // Model primary + fallbacks
  const mSec = document.createElement("section");
  mSec.innerHTML = `<h3>Model</h3>`;
  mSec.appendChild(renderModelRow(d.model.primary, true));
  d.model.fallbacks.forEach(m => mSec.appendChild(renderModelRow(m, false)));
  el.appendChild(mSec);

  // Agent primary + fallbacks
  if (d.agent.primary) {
    const aSec = document.createElement("section");
    aSec.innerHTML = `<h3>Agent</h3>`;
    aSec.appendChild(renderAgentRow(d.agent.primary, true));
    d.agent.fallbacks.forEach(a => aSec.appendChild(renderAgentRow(a, false)));
    el.appendChild(aSec);
  }

  // Safety gate
  const s = d.safety_gate;
  const sSec = document.createElement("section");
  const ok = !s.requires_approval;
  sSec.innerHTML = `<h3>Safety gate</h3>
    <div class="safety ${ok ? "ok" : "warn"}">
      <b>${ok ? "No approval required" : "Approval required"}</b>
      ${s.flags.length ? ` — ${s.flags.join(", ")}` : ""}
      <div class="muted" style="margin-top:6px">
        recommended autonomy: <b style="color:var(--text)">${s.recommended_autonomy}</b>
        · redaction: <b style="color:var(--text)">${s.redaction_required}</b>
        · audit: <b style="color:var(--text)">${s.audit_required}</b>
      </div>
    </div>`;
  el.appendChild(sSec);

  // Trace
  const tSec = document.createElement("section");
  tSec.innerHTML = `<h3>Trace</h3><div class="trace"></div>`;
  const trace = $(".trace", tSec);
  d.trace.forEach(t => {
    const s = document.createElement("div");
    s.className = "step";
    s.innerHTML = `<b>${t.stage}</b> @ ${t.at_ms}ms — <span>${JSON.stringify(t.detail)}</span>`;
    trace.appendChild(s);
  });
  el.appendChild(tSec);
}

function renderModelRow(m, primary) {
  const row = document.createElement("div");
  row.className = "model-row" + (primary ? " primary" : "");
  const subs = m.sub_scores;
  const subHtml = Object.keys(subs).map(k => `
    <div class="sub ${k}">
      <div class="name">${k.slice(0, 3)}</div>
      <div class="val">${subs[k].toFixed(2)}</div>
      <div class="bar"><span style="width:${Math.round(subs[k] * 100)}%"></span></div>
    </div>`).join("");
  const bench = m.benchmark_score != null
    ? `<div class="bench-bar"><span style="width:${Math.round(m.benchmark_score * 100)}%"></span></div>
       <div class="contribs">bench: ${m.benchmark_score.toFixed(3)}${
         m.benchmark_contributions ? " · " + Object.entries(m.benchmark_contributions)
           .map(([k,v]) => `${k}:${v}`).join(" · ") : ""
       }</div>`
    : "";
  row.innerHTML = `
    <div class="model-row-head">
      <b>${m.model_id}</b>
      <span class="id">${m.provider}</span>
      <span class="score">${m.score.toFixed(3)}</span>
    </div>
    <div class="sub-scores">${subHtml}</div>
    ${bench}
    <div class="model-meta">
      <span>${m.projected_latency_ms}ms p50</span>
      <span>$${m.projected_cost_usd.toFixed(6)} projected</span>
      <span>${m.reasons.join(" · ")}</span>
    </div>`;
  return row;
}

function renderAgentRow(a, primary) {
  const row = document.createElement("div");
  row.className = "agent-row" + (primary ? " primary" : "");
  row.innerHTML = `
    <div class="head">
      <b>${a.agent_id}</b>
      <span class="muted">${a.runtime}</span>
      <span class="score">${a.score.toFixed(3)}</span>
    </div>
    <div class="muted" style="margin-top:4px">default model: ${a.default_model} · ${a.reasons.join(" · ")}</div>`;
  return row;
}

// ---- leaderboards --------------------------------------------------------
function renderLeaderboardsForm() {
  const sel = $("#lb-vertical");
  if (sel.childElementCount) return;  // already built
  state.verticals.forEach(v => {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    sel.appendChild(o);
  });
  sel.value = "engineering";
  $("#lb-weights").textContent = JSON.stringify(state.benchmarks.vertical_weights, null, 2);
}

$("#lb-go").addEventListener("click", async () => {
  const vertical = $("#lb-vertical").value;
  const k = Number($("#lb-k").value);
  const box = $("#lb-results");
  box.innerHTML = '<div class="muted"><span class="loading"></span> Ranking…</div>';
  try {
    const data = await api(`/v2/benchmarks/top?vertical=${encodeURIComponent(vertical)}&k=${k}`);
    box.innerHTML = "";
    data.ranked.forEach((r, i) => {
      const el = document.createElement("div");
      el.className = "lb-row";
      const contribs = Object.entries(r.contributions).map(([k, v]) => `${k}:${v}`).join(" · ");
      el.innerHTML = `
        <div><div class="rank">#${i + 1}</div><b>${r.model_id}</b></div>
        <div class="score">${r.score.toFixed(3)}</div>
        <div class="contribs">${contribs}</div>`;
      box.appendChild(el);
    });
  } catch (e) {
    box.innerHTML = `<div class="error">${e.message}</div>`;
  }
});

// ---- models --------------------------------------------------------------
function renderModels() {
  const tbody = $("#models-table tbody");
  const filter = $("#m-filter").value.toLowerCase();
  tbody.innerHTML = "";
  state.models
    .filter(m => {
      if (!filter) return true;
      return [m.model_id, m.provider, m.family].some(
        v => (v || "").toLowerCase().includes(filter));
    })
    .forEach(m => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${m.model_id}</td>
        <td>${m.provider}</td>
        <td>${m.family}</td>
        <td>${m.tier}</td>
        <td>${m.context_window.toLocaleString()}</td>
        <td>$${m.cost_in_per_mtok.toFixed(2)}</td>
        <td>$${m.cost_out_per_mtok.toFixed(2)}</td>
        <td>${m.latency_p50_ms}</td>
        <td>${(m.modalities || []).join(", ")}</td>
        <td>${(m.compliance || []).join(", ") || "—"}</td>`;
      tbody.appendChild(tr);
    });
}

$("#m-filter").addEventListener("input", renderModels);

// ---- agents --------------------------------------------------------------
function renderAgents() {
  const box = $("#agent-list");
  box.innerHTML = "";
  state.agents.forEach(a => {
    const card = document.createElement("div");
    card.className = "agent-card";
    card.innerHTML = `
      <h4>${a.agent_id}</h4>
      <div class="muted">${a.description}</div>
      <div class="meta" style="margin-top:8px">
        <div>runtime: <b>${a.runtime}</b></div>
        <div>default: <b>${a.default_model}</b></div>
        <div>fallbacks: ${a.fallback_models.join(", ") || "—"}</div>
        <div>strengths: ${a.strengths.join(", ")}</div>
        <div>tools: ${a.supported_tools.join(", ") || "—"}</div>
        <div>autonomy: ${a.autonomy_default} · max parallel: ${a.max_parallel}</div>
      </div>`;
    box.appendChild(card);
  });
}

// ---- taxonomy ------------------------------------------------------------
function renderTaxonomy() {
  const filter = $("#t-filter").value.toLowerCase();
  const box = $("#taxonomy-groups");
  box.innerHTML = "";
  const grouped = {};
  state.taxonomy.intents.forEach(i => {
    if (filter && !`${i.intent_id} ${i.label} ${i.vertical}`.toLowerCase().includes(filter)) return;
    (grouped[i.vertical] ||= []).push(i);
  });
  Object.keys(grouped).sort().forEach(vertical => {
    const g = document.createElement("div");
    g.className = "tax-group";
    g.innerHTML = `<h3>${vertical} · ${grouped[vertical].length}</h3><div class="tax-intents"></div>`;
    const ints = $(".tax-intents", g);
    grouped[vertical].forEach(i => {
      const el = document.createElement("div");
      el.className = "tax-intent";
      const flags = [
        i.regulated && "regulated",
        i.agentic && "agentic",
        i.long_context && "long-ctx",
      ].filter(Boolean).join(" · ");
      el.innerHTML = `<b>${i.label}</b>
        <div class="id">${i.intent_id}</div>
        <div class="muted" style="margin-top:4px">
          depth ${i.reasoning_depth}/5 · complexity ${i.complexity}/5 ${flags ? "· " + flags : ""}
        </div>`;
      ints.appendChild(el);
    });
    box.appendChild(g);
  });
}

$("#t-filter").addEventListener("input", renderTaxonomy);

// ---- openrouter sync -----------------------------------------------------
$("#or-sync").addEventListener("click", async () => {
  const btn = $("#or-sync");
  const res = $("#or-result");
  btn.disabled = true;
  res.innerHTML = '<span class="loading"></span> Syncing…';
  try {
    const body = {
      use_sample: $("#or-sample").checked,
      fallback_to_sample: $("#or-fallback").checked,
    };
    const key = $("#or-key").value.trim();
    if (key) body.api_key = key;
    const out = await api("/v2/openrouter/sync", {
      method: "POST",
      body: JSON.stringify(body),
    });
    res.innerHTML = `fetched <b>${out.fetched}</b>, added <b>${out.added}</b>, active now <b>${out.active_total}</b>`;
    // refresh model cache
    const models = await api("/v2/models");
    state.models = models.models;
    state.vendors = new Set(state.models.map(m => m.provider));
    renderConstraintChips();
    $("#model-count").textContent =
      `${models.count} models (${models.curated_count} curated + ${models.openrouter_count} openrouter)`;
  } catch (e) {
    res.innerHTML = `<span class="error">${e.message}</span>`;
  } finally {
    btn.disabled = false;
  }
});

boot();
