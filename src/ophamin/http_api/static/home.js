/* =====================================================================
   Ophamin — the spherical home.  Kimera at the centre; six wheels around
   it.  Click a wheel, it opens.  The shape is the navigation.

   Everything shown is REAL, fetched live from this server:
     /version  /scenarios  /proofs/bundles/tree  /proofs/bundles/file
     /substrate  /toolkits  /reporting/standards  /managing/status  /metrics
   plus POST /scenarios/{name}/run and POST /verify.
   No framework, no build step, no fabricated data.
   ===================================================================== */
(function () {
  "use strict";

  // ----------------------------------------------------------- utilities
  const $ = (s, r = document) => r.querySelector(s);
  const SVGNS = "http://www.w3.org/2000/svg";

  function esc(s) {
    return String(s == null ? "" : s)
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
  }
  function humanize(name) {
    return String(name || "").replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  function shortVerdict(v) {
    v = String(v || "").toLowerCase();
    if (v.startsWith("valid")) return "validated";
    if (v.startsWith("refut")) return "refuted";
    if (v.startsWith("incon")) return "inconclusive";
    return "unknown";
  }
  function verdictPlain(v) {
    const k = shortVerdict(v);
    return { validated: "held up", refuted: "did not hold", inconclusive: "inconclusive", unknown: "—" }[k];
  }
  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status} ${url}`);
    return r.json();
  }
  async function getText(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status} ${url}`);
    return r.text();
  }
  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const txt = await r.text();
    let data; try { data = JSON.parse(txt); } catch { data = { _raw: txt }; }
    if (!r.ok) throw new Error(data.detail || `${r.status} ${url}`);
    return data;
  }

  // ------------------------------------------------------------- the data
  const DATA = {
    version: null, scenarios: null, tree: null, substrate: null,
    toolkits: null, standards: null, status: null, metrics: null,
  };

  // ------------------------------------------------------------ the wheels
  // Order matters: index 0 sits at the top, then clockwise.
  const WHEELS = [
    { id: "seeing", name: "Seeing", hue: 180,
      blurb: "what it senses about Kimera",
      lead: "How Ophamin senses Kimera right now — the living organs of the substrate and the last thing each one was caught doing.",
      count: () => DATA.substrate ? `${DATA.substrate.count} organs` : "",
      render: renderSeeing },
    { id: "measuring", name: "Measuring", hue: 145,
      blurb: "the proofs — what held",
      lead: "The heart of the observatory: pre-registered checks run against real data, each producing a signed proof you can open, read, and verify.",
      count: () => DATA.tree ? `${DATA.tree.totals.bundles} proofs · ${DATA.tree.totals.verdicts.validated || 0} held` : "",
      render: renderMeasuring },
    { id: "comparing", name: "Comparing", hue: 270,
      blurb: "how Kimera changed",
      lead: "Looking back across Kimera versions — which commits have been measured, and how results drift as the substrate evolves.",
      count: () => `${uniqueCommits().length} versions seen`,
      render: renderComparing },
    { id: "instrumenting", name: "Instrumenting", hue: 35,
      blurb: "what it costs to run",
      lead: "The engineering wheel: what each run costs in time and memory, sampled per cycle, plus the live counters this server keeps about itself.",
      count: () => DATA.metrics ? `${DATA.metrics.series} signals` : "",
      render: renderInstrumenting },
    { id: "auditing", name: "Auditing", hue: 355,
      blurb: "tools that keep it honest",
      lead: "The static-analysis and statistics tools Ophamin leans on to keep its own measurements trustworthy — and whether each is installed here.",
      count: () => DATA.toolkits ? `${DATA.toolkits.toolkits.length} tools` : "",
      render: renderAuditing },
    { id: "reporting", name: "Reporting", hue: 210,
      blurb: "how results get written up",
      lead: "How a result becomes something you can share: the formats every proof is rendered into, and the public standards each one is held to.",
      count: () => DATA.standards ? `${DATA.standards.standards.length} standards` : "",
      render: renderReporting },
  ];
  const byId = (id) => WHEELS.find((w) => w.id === id);

  function uniqueCommits() {
    const set = new Set();
    const organs = (DATA.substrate && DATA.substrate.organs) || [];
    for (const o of organs) {
      const c = o.latest && o.latest.substrate_commit;
      if (c) set.add(c);
    }
    return [...set];
  }

  // --------------------------------------------------------------- boot
  async function boot() {
    buildWheels();
    layout();
    // Fetch every wheel's data independently so one slow/empty endpoint
    // never blanks the home.
    const jobs = [
      ["version", "/version"], ["scenarios", "/scenarios"],
      ["tree", "/proofs/bundles/tree"], ["substrate", "/substrate"],
      ["toolkits", "/toolkits"], ["standards", "/reporting/standards"],
      ["status", "/managing/status"],
    ];
    await Promise.all(jobs.map(async ([key, url]) => {
      try { DATA[key] = await getJSON(url); } catch (e) { console.warn("skip", url, e.message); }
      paintCounts();
    }));
    try {
      const txt = await getText("/metrics");
      const series = txt.split("\n").filter((l) => l && !l.startsWith("#")).length;
      DATA.metrics = { series, text: txt };
    } catch (e) { console.warn("skip /metrics", e.message); }
    paintHeader();
    paintCounts();
  }

  function paintHeader() {
    if (DATA.version) $("#brand-version").textContent = "v" + DATA.version.framework_version;
    const commit = uniqueCommits()[0];
    const name = DATA.substrate && DATA.substrate.organs && DATA.substrate.organs[0]
      && DATA.substrate.organs[0].latest && DATA.substrate.organs[0].latest.substrate_name;
    if (name || commit) {
      $("#core-sub").textContent = (name || "kimera") + (commit ? " · " + commit.slice(0, 8) : "");
    }
  }

  function paintCounts() {
    for (const w of WHEELS) {
      const el = $(`#wheel-${w.id} .wheel-count`);
      if (el) el.textContent = w.count() || "";
    }
  }

  // ------------------------------------------------------ build + layout
  function buildWheels() {
    const host = $("#wheels");
    host.innerHTML = "";
    for (const w of WHEELS) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "wheel";
      b.id = `wheel-${w.id}`;
      b.style.setProperty("--hue", w.hue);
      b.setAttribute("aria-label", `${w.name} — ${w.blurb}`);
      b.innerHTML =
        `<span class="wheel-name">${esc(w.name)}</span>` +
        `<span class="wheel-count"></span>` +
        `<span class="wheel-blurb">${esc(w.blurb)}</span>`;
      b.addEventListener("click", () => openWheel(w.id));
      host.appendChild(b);
    }
  }

  function layout() {
    const cosmos = $("#cosmos");
    const svg = $("#cosmos-svg");
    const w = cosmos.clientWidth, h = cosmos.clientHeight;
    const cx = w / 2, cy = h / 2;
    const wheelHalf = w <= 720 ? 66 : 84;
    const coreHalf = w <= 720 ? 66 : 94;
    const margin = 14;
    const Rx = Math.max(120, Math.min(w * 0.42, w / 2 - wheelHalf - margin));
    const Ry = Math.max(120, Math.min(h * 0.42, h / 2 - wheelHalf - margin));

    // draw svg decoration
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    // faint concentric rings (wheels within wheels)
    for (const f of [1.0, 0.74, 0.48]) {
      const e = document.createElementNS(SVGNS, "ellipse");
      e.setAttribute("cx", cx); e.setAttribute("cy", cy);
      e.setAttribute("rx", Rx * f); e.setAttribute("ry", Ry * f);
      e.setAttribute("fill", "none");
      e.setAttribute("stroke", "rgba(255,255,255,0.05)");
      e.setAttribute("stroke-width", "1");
      svg.appendChild(e);
    }

    WHEELS.forEach((wheel, i) => {
      const theta = (-90 + i * 60) * Math.PI / 180;
      const x = cx + Rx * Math.cos(theta);
      const y = cy + Ry * Math.sin(theta);
      // spoke from core edge to wheel
      const dx = x - cx, dy = y - cy, len = Math.hypot(dx, dy) || 1;
      const ux = dx / len, uy = dy / len;
      const line = document.createElementNS(SVGNS, "line");
      line.setAttribute("x1", cx + ux * coreHalf); line.setAttribute("y1", cy + uy * coreHalf);
      line.setAttribute("x2", x - ux * wheelHalf); line.setAttribute("y2", y - uy * wheelHalf);
      line.setAttribute("stroke", `hsl(${wheel.hue} 60% 55% / 0.22)`);
      line.setAttribute("stroke-width", "1.2");
      svg.appendChild(line);
      // place the wheel button
      const el = $(`#wheel-${wheel.id}`);
      if (el) { el.style.left = `${x}px`; el.style.top = `${y}px`; }
    });
  }
  let resizeT;
  window.addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(layout, 120); });

  // ------------------------------------------------------------- panel
  const panelLayer = $("#panel-layer");
  function openWheel(id) {
    const w = byId(id);
    if (!w) return;
    panelLayer.style.setProperty("--hue", w.hue);
    $("#panel-title").textContent = w.name;
    $("#panel-blurb").textContent = w.lead;
    const body = $("#panel-body");
    body.innerHTML = '<div class="spinner">Loading…</div>';
    panelLayer.hidden = false;
    document.body.style.overflow = "hidden";
    try { w.render(body); } catch (e) { body.innerHTML = `<div class="err">Couldn’t render this wheel: ${esc(e.message)}</div>`; }
    $("#panel-back").focus();
  }
  function closePanel() {
    panelLayer.hidden = true;
    document.body.style.overflow = "";
  }
  $("#panel-back").addEventListener("click", closePanel);
  $("#core").addEventListener("click", closePanel);
  panelLayer.addEventListener("click", (e) => { if (e.target === panelLayer) closePanel(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panelLayer.hidden) closePanel(); });

  // ============================================================ RENDERERS

  // ---- Seeing: the organs of Kimera (from /substrate) ------------------
  function renderSeeing(body) {
    const s = DATA.substrate;
    if (!s || !s.organs) { body.innerHTML = miss("the substrate probe"); return; }
    const cards = s.organs.map((o) => {
      const st = shortVerdict(o.status || (o.latest && o.latest.outcome));
      const latest = o.latest;
      let line = '<p class="muted">not yet measured</p>';
      if (latest) {
        line = `<p>last seen: <span class="verdict-word ${st}">${esc(verdictPlain(latest.outcome))}</span>` +
          ` — ${esc(latest.metric)} ${esc(latest.comparator)} ${esc(latest.threshold)} (observed ${esc(round(latest.observed))})</p>`;
      }
      return `<div class="card"><h3><span class="dot ${st}"></span>${esc(o.name)}</h3>` +
        `<p>${esc(o.role)}</p>${line}` +
        `<div class="meta">${esc(o.proof_count || 0)} proof(s)</div></div>`;
    }).join("");
    body.innerHTML =
      `<p class="lead">${esc(byId("seeing").lead)} <b>${s.count} organs</b> are wired into the observatory.</p>` +
      `<div class="cards">${cards}</div>`;
  }

  // ---- Measuring: scenarios + proofs (the core) ------------------------
  function renderMeasuring(body) {
    const tree = DATA.tree, scen = DATA.scenarios;
    const v = (tree && tree.totals && tree.totals.verdicts) || {};
    const tot = (tree && tree.totals) || {};
    const tally =
      `<div class="tally">` +
      `<div class="stat"><div class="num">${tot.bundles || 0}</div><div class="lbl">proofs on disk</div></div>` +
      `<div class="stat"><div class="num good">${v.validated || 0}</div><div class="lbl">held up</div></div>` +
      `<div class="stat"><div class="num bad">${v.refuted || 0}</div><div class="lbl">did not hold</div></div>` +
      `<div class="stat"><div class="num meh">${v.inconclusive || 0}</div><div class="lbl">inconclusive</div></div>` +
      `</div>`;

    // proof rows, grouped by tier
    let rows = "";
    if (tree && tree.tiers && tree.tiers.length) {
      for (const tier of tree.tiers) {
        rows += `<div class="section-label">${esc(humanize(tier.tier))}</div><div class="rows">`;
        for (const sc of tier.scenarios) {
          for (const b of sc.bundles) {
            const bundle = `${b.date}_${b.verdict}_${b.short_hash}`;
            const st = shortVerdict(b.verdict);
            rows += `<div class="row" tabindex="0" role="button" ` +
              `data-tier="${esc(tier.tier)}" data-scenario="${esc(sc.scenario)}" data-bundle="${esc(bundle)}" data-files="${esc((b.files || []).join(","))}">` +
              `<span class="dot ${st}"></span>` +
              `<span class="row-name">${esc(humanize(sc.scenario))}</span>` +
              `<span class="verdict-word ${st}">${esc(verdictPlain(b.verdict))}</span>` +
              `<span class="row-date">${esc(b.date)}</span></div>`;
          }
        }
        rows += `</div>`;
      }
    } else {
      rows = `<p class="muted">No proofs on disk yet. Run a check below to make the first one.</p>`;
    }

    // run a check
    const opts = ((scen && scen.scenarios) || []).slice().sort((a, b) => a.name.localeCompare(b.name))
      .map((s) => `<option value="${esc(s.name)}">${esc(humanize(s.name))}</option>`).join("");
    const runBlock =
      `<div class="section-label">Run a check</div>` +
      `<p class="muted" style="margin:0 0 12px">Pick a check and run it against the substrate. A real run can take a while — it produces a fresh signed proof when it finishes.</p>` +
      `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">` +
      `<select id="run-pick" style="flex:1;min-width:220px;background:#0b1019;color:var(--ink);border:1px solid var(--line);border-radius:9px;padding:9px 12px;font-family:inherit;font-size:13px">${opts}</select>` +
      `<button class="btn" id="run-go">Run it</button></div>` +
      `<div id="run-out"></div>`;

    body.innerHTML =
      `<p class="lead">${esc(byId("measuring").lead)}</p>` + tally +
      `<div id="proof-list"><div class="section-label">The proofs (${(scen && scen.count) || 0} checks wired)</div>${rows}</div>` +
      runBlock;

    body.querySelectorAll(".row").forEach((r) => {
      const open = () => openProof(r.dataset.tier, r.dataset.scenario, r.dataset.bundle, (r.dataset.files || "").split(",").filter(Boolean));
      r.addEventListener("click", open);
      r.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    });
    const go = $("#run-go", body);
    if (go) go.addEventListener("click", () => runScenario($("#run-pick", body).value, go));
  }

  async function openProof(tier, scenario, bundle, files) {
    const body = $("#panel-body");
    body.innerHTML = `<button class="back" id="proof-back" style="margin-bottom:18px">← all proofs</button><div class="spinner">Opening the proof…</div>`;
    $("#proof-back", body).addEventListener("click", () => openWheel("measuring"));
    const q = new URLSearchParams({ tier, scenario, bundle, filename: "proof.json" });
    let d;
    try { d = await getJSON(`/proofs/bundles/file?${q}`); }
    catch (e) { body.innerHTML += `<div class="err">Couldn’t open this proof: ${esc(e.message)}</div>`; return; }

    const ver = d.verdict || {}, claim = d.claim || {};
    const th = ver.threshold || claim.threshold || {};
    const st = shortVerdict(ver.outcome);
    const hasHtml = files.includes("proof.html");
    const fileUrl = (fn) => `/proofs/bundles/file?${new URLSearchParams({ tier, scenario, bundle, filename: fn })}`;

    body.innerHTML =
      `<button class="back" id="proof-back" style="margin-bottom:18px">← all proofs</button>` +
      `<p class="proof-claim">${esc(claim.statement || humanize(scenario))}</p>` +
      `<p style="font-size:15px;margin:0 0 4px"><span class="dot ${st}"></span> ` +
      `<span class="verdict-word ${st}" style="font-size:15px">It ${esc(verdictPlain(ver.outcome))}.</span></p>` +
      (ver.reasoning ? `<p class="note" style="font-size:13.5px;color:var(--ink-soft);margin-top:6px">${esc(ver.reasoning)}</p>` : "") +
      `<dl class="kv">` +
      (th.metric ? `<dt>what we measured</dt><dd>${esc(th.metric)}</dd>` : "") +
      (th.value != null ? `<dt>the bar</dt><dd>${esc(th.comparator)} ${esc(th.value)} ${esc(th.units || "")}</dd>` : "") +
      (ver.observed_value != null ? `<dt>what we saw</dt><dd>${esc(round(ver.observed_value))}</dd>` : "") +
      (claim.operationalization ? `<dt>how</dt><dd style="font-family:inherit;color:var(--ink-soft)">${esc(claim.operationalization)}</dd>` : "") +
      `</dl>` +
      `<div class="actions">` +
      (hasHtml ? `<button class="btn" id="p-report">Open the written report</button>` : "") +
      `<button class="btn ghost" id="p-json">See the signed record</button>` +
      `<button class="btn ghost" id="p-verify">Verify this proof</button>` +
      `</div><div id="p-out"></div>`;

    $("#proof-back", body).addEventListener("click", () => openWheel("measuring"));
    const out = $("#p-out", body);
    const rep = $("#p-report", body);
    if (rep) rep.addEventListener("click", () => {
      out.innerHTML = `<div class="viewer"><iframe title="proof report" src="${esc(fileUrl("proof.html"))}"></iframe></div>`;
    });
    $("#p-json", body).addEventListener("click", () => {
      out.innerHTML = `<pre class="json-view">${esc(JSON.stringify(d, null, 2))}</pre>`;
    });
    $("#p-verify", body).addEventListener("click", async (e) => {
      e.target.disabled = true; e.target.textContent = "Checking…";
      try {
        const raw = await getText(fileUrl("proof.json"));
        const res = await postJSON("/verify", { proof_json: raw, sign_key_b64: "" });
        // Two independent guarantees, reported honestly:
        //   1. Content integrity — the recomputed fingerprint (proof_id)
        //      matches the one stored in the file. This is the anti-tamper
        //      anchor: if it matches, the proof has NOT been altered.
        //   2. Cryptographic seal — the HMAC verifies under the framework's
        //      default key. Most proofs do; a few are sealed with a project
        //      key, which can't be confirmed here — that is NOT tampering.
        const intact = res.proof_id && d.proof_id && res.proof_id === d.proof_id;
        const sealed = res.verified;
        const who = res.attestation_verified && res.attestation_author
          ? ` Attributed to ${esc(res.attestation_author)}.` : "";
        if (!intact) {
          out.innerHTML = `<div class="banner no">✗ Altered — the contents no longer match this proof's fingerprint. Don't trust it.</div>`;
        } else if (sealed) {
          out.innerHTML = `<div class="banner ok">✓ Verified — the contents match the fingerprint (nothing altered) and the cryptographic seal checks out under the framework key.${who}</div>`;
        } else {
          out.innerHTML = `<div class="banner ok">✓ Intact — the contents still match this proof's fingerprint, so nothing has been altered. Its seal was made with a different signing key, so the seal itself can't be confirmed here.</div>`;
        }
      } catch (err) {
        out.innerHTML = `<div class="err">Couldn’t verify: ${esc(err.message)}</div>`;
      } finally { e.target.disabled = false; e.target.textContent = "Verify this proof"; }
    });
  }

  async function runScenario(name, btn) {
    const out = $("#run-out");
    if (!confirm(`Run the “${humanize(name)}” check now?\n\nThis runs against the real substrate and can take a while.`)) return;
    btn.disabled = true; btn.textContent = "Running…";
    out.innerHTML = `<p class="note">Running ${esc(humanize(name))}… you can keep this open.</p>`;
    try {
      const res = await postJSON(`/scenarios/${encodeURIComponent(name)}/run`, { kwargs_json: "{}" });
      const ver = res.verdict || {};
      const st = shortVerdict(ver.outcome);
      out.innerHTML = `<div class="banner ${st === "validated" ? "ok" : st === "refuted" ? "no" : ""}" style="margin-top:14px">` +
        `Done — it <b>${esc(verdictPlain(ver.outcome))}</b>.` +
        (ver.reasoning ? ` ${esc(ver.reasoning)}` : "") +
        `</div><p class="note">A fresh signed proof was written. Re-open the Measuring wheel to see it in the list.</p>`;
    } catch (e) {
      out.innerHTML = `<div class="err">The run failed: ${esc(e.message)}</div>`;
    } finally { btn.disabled = false; btn.textContent = "Run it"; }
  }

  // ---- Comparing: versions seen (honest; deep work is CLI) -------------
  function renderComparing(body) {
    const commits = uniqueCommits();
    const list = commits.length
      ? `<div class="cards">${commits.map((c) =>
          `<div class="card"><h3>kimera-swm</h3><div class="meta">${esc(c)}</div></div>`).join("")}</div>`
      : `<p class="muted">No measured Kimera versions on record yet.</p>`;
    body.innerHTML =
      `<p class="lead">${esc(byId("comparing").lead)}</p>` +
      `<div class="section-label">Kimera versions Ophamin has measured</div>` + list +
      `<p class="note">Side-by-side drift between two versions runs from the command line today — ` +
      `<code>ophamin discover-diff</code> and the drift wheel — and isn’t wired into this page yet. ` +
      `What you see above are the substrate commits the proofs on this machine were measured against.</p>`;
  }

  // ---- Instrumenting: cost + live counters ----------------------------
  function renderInstrumenting(body) {
    const m = DATA.metrics;
    let counters = "";
    if (m && m.text) {
      const pick = (needle) => {
        let sum = 0, found = false;
        for (const line of m.text.split("\n")) {
          if (line.startsWith("#") || !line.includes(needle)) continue;
          const val = parseFloat(line.trim().split(/\s+/).pop());
          if (!isNaN(val)) { sum += val; found = true; }
        }
        return found ? sum : null;
      };
      const reqs = pick("ophamin_http_requests_total");
      const verified = pick("ophamin_proofs_verified_total");
      counters =
        `<div class="tally">` +
        `<div class="stat"><div class="num">${m.series}</div><div class="lbl">live signals tracked</div></div>` +
        (reqs != null ? `<div class="stat"><div class="num">${Math.round(reqs)}</div><div class="lbl">requests served</div></div>` : "") +
        (verified != null ? `<div class="stat"><div class="num">${Math.round(verified)}</div><div class="lbl">signatures checked</div></div>` : "") +
        `</div>`;
    }
    body.innerHTML =
      `<p class="lead">${esc(byId("instrumenting").lead)}</p>` + counters +
      `<p class="note">During a run, Ophamin samples CPU, memory (RSS) and page-faults per cycle so a result carries its own cost. ` +
      `At rest, the live counters above are what this server has tracked about itself since it started.</p>`;
  }

  // ---- Auditing: the tools (from /toolkits) ----------------------------
  function renderAuditing(body) {
    const t = DATA.toolkits;
    if (!t || !t.toolkits) { body.innerHTML = miss("the toolkit index"); return; }
    const cards = t.toolkits.map((k) => {
      const ok = k.installed;
      return `<div class="card"><h3><span class="dot ${ok ? "validated" : ""}"></span>${esc(k.id)}</h3>` +
        `<p>${esc(k.role || k.category)}</p>` +
        `<div class="meta">${ok ? "installed " + esc(k.version || "") : "not installed"} · ${esc(k.category || "")}</div></div>`;
    }).join("");
    body.innerHTML =
      `<p class="lead">${esc(byId("auditing").lead)}</p>` +
      `<div class="cards">${cards}</div>`;
  }

  // ---- Reporting: formats + standards (from /reporting/standards) ------
  function renderReporting(body) {
    const s = DATA.standards;
    if (!s) { body.innerHTML = miss("the reporting standards"); return; }
    const fmts = (s.output_formats || []).map((f) => `<code>${esc(f)}</code>`).join("  ");
    const cards = (s.standards || []).map((st) =>
      `<div class="card"><h3>${esc(st.id)}</h3><p>${esc(st.covers)}</p>` +
      `<div class="meta" style="font-family:inherit;white-space:normal">${esc(st.requires)}</div></div>`).join("");
    body.innerHTML =
      `<p class="lead">${esc(byId("reporting").lead)}</p>` +
      (fmts ? `<p style="font-size:14px;margin:0 0 22px">Every proof is rendered into: ${fmts}</p>` : "") +
      `<div class="section-label">Held to these public standards</div>` +
      `<div class="cards">${cards}</div>`;
  }

  // -------------------------------------------------------------- helpers
  function miss(what) {
    return `<div class="err">Couldn’t load ${esc(what)} from the server.</div>`;
  }
  function round(x) {
    const n = Number(x);
    if (!isFinite(n)) return x;
    if (n === 0) return "0";
    const a = Math.abs(n);
    if (a >= 100) return n.toFixed(1);
    if (a >= 1) return n.toFixed(3);
    return n.toPrecision(3);
  }

  boot();
})();
