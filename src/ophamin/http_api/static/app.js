/* Ophamin provisional GUI — vanilla JS, no framework, no build step.
 *
 * Talks to four read-only endpoints + one POST:
 *   GET  /version
 *   GET  /scenarios
 *   GET  /metrics                (Prometheus text exposition)
 *   GET  /proofs/bundles/tree    (nested tier → scenario → bundles)
 *   GET  /proofs/bundles/file    (single bundle file; safe-path-checked)
 *   POST /scenarios/{name}/run   (heavyweight; warn before invoking)
 */

(function () {
    "use strict";

    // ---------------------- shared utilities ----------------------

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => Array.from(document.querySelectorAll(sel));

    function escapeHtml(s) {
        return String(s)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    async function fetchJSON(url) {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${url}`);
        return r.json();
    }

    async function fetchText(url) {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${url}`);
        return r.text();
    }

    // ---------------------- shared state ----------------------
    // Cache the boot resources so tab switches + the run-select don't
    // re-fetch. `loaded` tracks which heavy tabs have rendered so they
    // load lazily on first activation rather than eagerly on boot.

    const state = {
        tree: null,         // /proofs/bundles/tree response
        scenarios: null,    // /scenarios response
        loaded: { metrics: false, scenarios: false },
        suppressHash: false, // guard against feedback loops on restore
    };

    // ---------------------- tabs ----------------------

    function activateTab(name, { updateHash = true } = {}) {
        $$(".tab").forEach((b) => {
            const on = b.dataset.tab === name;
            b.classList.toggle("active", on);
            b.setAttribute("aria-selected", on ? "true" : "false");
            b.tabIndex = on ? 0 : -1;
        });
        $$(".tab-panel").forEach((p) =>
            p.classList.toggle("active", p.id === `tab-${name}`),
        );
        // Lazy-load heavy tabs on first activation.
        if (name === "metrics" && !state.loaded.metrics) {
            state.loaded.metrics = true;
            refreshMetrics();
        }
        if (name === "scenarios" && !state.loaded.scenarios) {
            state.loaded.scenarios = true;
            renderScenarios();
        }
        if (updateHash) setHash({ tab: name });
    }

    $$(".tab").forEach((b) =>
        b.addEventListener("click", () => activateTab(b.dataset.tab)),
    );

    // Arrow-key navigation across the tablist (WAI-ARIA tabs pattern).
    const tablist = $(".tabs");
    if (tablist) {
        tablist.addEventListener("keydown", (e) => {
            const tabs = $$(".tab");
            const i = tabs.findIndex((t) => t.dataset.tab === currentTab());
            let j = null;
            if (e.key === "ArrowRight") j = (i + 1) % tabs.length;
            else if (e.key === "ArrowLeft") j = (i - 1 + tabs.length) % tabs.length;
            else if (e.key === "Home") j = 0;
            else if (e.key === "End") j = tabs.length - 1;
            if (j !== null) {
                e.preventDefault();
                activateTab(tabs[j].dataset.tab);
                tabs[j].focus();
            }
        });
    }

    function currentTab() {
        const active = $(".tab.active");
        return active ? active.dataset.tab : "proofs";
    }

    // ---------------------- boot (single deduped fetch) ----------------------
    // Fetch the three boot resources ONCE and share them: header stats,
    // the bundle tree, the scenario registry (+ the run-form select all
    // read from the same cached responses). Previously /scenarios and
    // /proofs/bundles/tree were each fetched twice on boot.

    async function boot() {
        try {
            const [version, scenarios, tree] = await Promise.all([
                fetchJSON("/version"),
                fetchJSON("/scenarios"),
                fetchJSON("/proofs/bundles/tree"),
            ]);
            state.scenarios = scenarios;
            state.tree = tree;
            paintHeaderStats(version, tree);
            renderTree(tree);
            populateRunSelect(scenarios);
        } catch (e) {
            console.error("boot failed:", e);
            $("#bundle-tree").innerHTML =
                `<div class="error-text" style="padding:14px">Failed to load: ${escapeHtml(e.message)}</div>`;
        }
        // Restore deep-link state once data is present.
        restoreFromHash();
    }

    function paintHeaderStats(version, tree) {
        $("#stat-version").textContent = `v${version.framework_version}`;
        const t = tree.totals || {};
        $("#stat-scenarios").textContent =
            `${(state.scenarios && state.scenarios.count) || 0} scenarios`;
        $("#stat-bundles").textContent = `${t.bundles || 0} bundles`;
        const v = t.verdicts || {};
        $("#stat-validated").textContent = `${v.validated || 0} validated`;
        $("#stat-refuted").textContent = `${v.refuted || 0} refuted`;
        $("#stat-inconclusive").textContent =
            `${v.inconclusive || 0} inconclusive`;
    }

    // ---------------------- proofs tab (tree) ----------------------

    let selectedBundle = null; // { tier, scenario, bundle, files }

    async function refreshTree() {
        const root = $("#bundle-tree");
        root.innerHTML = '<div class="muted" style="padding:14px">Loading…</div>';
        try {
            const tree = await fetchJSON("/proofs/bundles/tree");
            state.tree = tree;
            renderTree(tree);
            applyTreeFilter();
        } catch (e) {
            root.innerHTML = `<div class="error-text" style="padding:14px">Failed to load tree: ${escapeHtml(e.message)}</div>`;
        }
    }

    function renderTree(tree) {
        const root = $("#bundle-tree");
        root.innerHTML = "";
        if (!tree.tiers.length) {
            root.innerHTML =
                '<div class="muted" style="padding:14px">No bundles yet. Run a scenario to produce one.</div>';
            return;
        }
        for (const tier of tree.tiers) {
            const tierDetails = document.createElement("details");
            tierDetails.className = "tree-tier";
            tierDetails.open = true;
            const tierSummary = document.createElement("summary");
            tierSummary.innerHTML = `${escapeHtml(tier.tier)} <span class="bundle-count">${tier.scenarios.length}</span>`;
            tierDetails.appendChild(tierSummary);

            for (const sc of tier.scenarios) {
                const scDetails = document.createElement("details");
                scDetails.className = "tree-scenario";
                const scSummary = document.createElement("summary");
                scSummary.innerHTML = `${escapeHtml(sc.scenario)} <span class="bundle-count">${sc.bundles.length}</span>`;
                scDetails.appendChild(scSummary);

                for (const b of sc.bundles) {
                    const div = document.createElement("div");
                    div.className = "tree-bundle";
                    div.dataset.tier = tier.tier;
                    div.dataset.scenario = sc.scenario;
                    div.dataset.bundle = `${b.date}_${b.verdict}_${b.short_hash}`;
                    div.dataset.files = b.files.join(",");
                    div.dataset.verdict = b.verdict;
                    div.dataset.search =
                        `${sc.scenario} ${b.short_hash} ${b.verdict} ${b.date}`.toLowerCase();
                    // Keyboard-accessible: focusable + Enter/Space activate,
                    // so the proofs browser works without a mouse.
                    div.setAttribute("role", "treeitem");
                    div.tabIndex = 0;
                    div.setAttribute(
                        "aria-label",
                        `${sc.scenario}, ${b.verdict}, ${b.date}`,
                    );
                    div.innerHTML = `
                        <span class="bundle-date">${escapeHtml(b.date)}</span>
                        <span class="verdict-tag ${b.verdict}">${escapeHtml(b.verdict)}</span>
                        <span class="bundle-hash">${escapeHtml(b.short_hash)}</span>
                    `;
                    div.addEventListener("click", () => selectBundle(div));
                    div.addEventListener("keydown", (ev) => {
                        if (ev.key === "Enter" || ev.key === " ") {
                            ev.preventDefault();
                            selectBundle(div);
                        }
                    });
                    scDetails.appendChild(div);
                }
                tierDetails.appendChild(scDetails);
            }
            root.appendChild(tierDetails);
        }
    }

    // ---------------------- tree filter ----------------------

    function applyTreeFilter() {
        const q = ($("#tree-search").value || "").trim().toLowerCase();
        const verdict = state.filterVerdict || "all";
        let shown = 0;
        const total = $$(".tree-bundle").length;

        for (const el of $$(".tree-bundle")) {
            const matchText = !q || el.dataset.search.includes(q);
            const matchVerdict = verdict === "all" || el.dataset.verdict === verdict;
            const visible = matchText && matchVerdict;
            el.classList.toggle("filtered-out", !visible);
            if (visible) shown += 1;
        }

        // Hide scenarios/tiers with no visible bundles; auto-expand the
        // ones that still have matches when a filter is active.
        const filtering = q !== "" || verdict !== "all";
        for (const sc of $$(".tree-scenario")) {
            const anyVisible = sc.querySelector(".tree-bundle:not(.filtered-out)") !== null;
            sc.classList.toggle("filtered-out", !anyVisible);
            if (filtering && anyVisible) sc.open = true;
        }
        for (const tier of $$(".tree-tier")) {
            const anyVisible = tier.querySelector(".tree-bundle:not(.filtered-out)") !== null;
            tier.classList.toggle("filtered-out", !anyVisible);
        }

        const countEl = $("#tree-filter-count");
        if (countEl) {
            countEl.textContent = filtering ? `${shown} of ${total} bundles` : "";
        }
    }

    function wireTreeFilter() {
        const search = $("#tree-search");
        if (search) {
            search.addEventListener("input", applyTreeFilter);
        }
        for (const chip of $$(".verdict-chips .chip")) {
            chip.addEventListener("click", () => {
                state.filterVerdict = chip.dataset.verdict;
                $$(".verdict-chips .chip").forEach((c) =>
                    c.classList.toggle("active", c === chip),
                );
                applyTreeFilter();
            });
        }
    }

    function selectBundle(el, { updateHash = true } = {}) {
        $$(".tree-bundle.active").forEach((n) => {
            n.classList.remove("active");
            n.setAttribute("aria-selected", "false");
        });
        el.classList.add("active");
        el.setAttribute("aria-selected", "true");
        selectedBundle = {
            tier: el.dataset.tier,
            scenario: el.dataset.scenario,
            bundle: el.dataset.bundle,
            files: el.dataset.files.split(",").filter(Boolean),
        };
        $("#detail-path").textContent =
            `${selectedBundle.tier} / ${selectedBundle.scenario} / ${selectedBundle.bundle}`;
        renderFormatTabs(selectedBundle.files);
        // Default: render the HTML view if present, else markdown, else JSON.
        const preferred =
            selectedBundle.files.find((f) => f === "proof.html") ||
            selectedBundle.files.find((f) => f === "proof.md") ||
            selectedBundle.files.find((f) => f === "proof.json") ||
            selectedBundle.files[0];
        if (preferred) renderFormat(preferred);
        if (updateHash) {
            setHash({
                tab: "proofs",
                bundle: `${selectedBundle.tier}/${selectedBundle.scenario}/${selectedBundle.bundle}`,
            });
        }
    }

    function renderFormatTabs(files) {
        const nav = $("#format-tabs");
        nav.innerHTML = "";
        for (const f of files) {
            const b = document.createElement("button");
            b.className = "format-tab";
            b.textContent = f.replace(/^proof\./, "").toUpperCase();
            b.dataset.file = f;
            b.setAttribute("role", "tab");
            b.setAttribute("aria-selected", "false");
            b.addEventListener("click", () => renderFormat(f));
            nav.appendChild(b);
        }
    }

    function fileURL(filename) {
        const { tier, scenario, bundle } = selectedBundle;
        const params = new URLSearchParams({
            tier, scenario, bundle, filename,
        });
        return `/proofs/bundles/file?${params}`;
    }

    async function renderFormat(filename) {
        $$(".format-tab").forEach((b) => {
            const on = b.dataset.file === filename;
            b.classList.toggle("active", on);
            b.setAttribute("aria-selected", on ? "true" : "false");
        });
        const view = $("#detail-view");
        view.innerHTML = '<div class="empty-state">Loading…</div>';

        const url = fileURL(filename);
        try {
            if (filename === "proof.html" || filename === "proof.pdf") {
                // HTML/PDF render in an iframe. Always pair it with a
                // direct "open in new tab" link so a blank preview
                // (stale cache after an upgrade, a browser without a
                // built-in PDF viewer, etc.) is never a dead end.
                const hash = filename === "proof.pdf" ? "#view=FitH" : "";
                view.innerHTML = `<div class="embed-wrap">`
                    + `<div class="format-note">Preview blank? `
                    + `<a href="${url}" target="_blank" rel="noopener noreferrer">`
                    + `open ${escapeHtml(filename)} in a new tab ↗</a></div>`
                    + `<iframe src="${url}${hash}" title="${escapeHtml(filename)}"></iframe>`
                    + `</div>`;
            } else if (filename === "proof.md") {
                const md = await fetchText(url);
                view.innerHTML = `<div class="markdown-render">${markdownToHTML(md)}</div>`;
            } else if (filename === "proof.json") {
                const obj = await fetchJSON(url);
                view.innerHTML = `<pre>${escapeHtml(JSON.stringify(obj, null, 2))}</pre>`;
            } else if (filename === "proof.tex") {
                const tex = await fetchText(url);
                view.innerHTML = `<pre>${escapeHtml(tex)}</pre>`;
            } else {
                view.innerHTML = `<div class="empty-state">No renderer for ${escapeHtml(filename)}</div>`;
            }
        } catch (e) {
            view.innerHTML = `<div class="error-text" style="padding:20px">Failed: ${escapeHtml(e.message)}</div>`;
        }
    }

    // ---------------------- markdown renderer ----------------------
    // Minimal markdown → HTML for proof.md output. NOT a full GFM impl
    // — supports headings, paragraphs, fenced code blocks, blockquotes,
    // bullet lists, inline `code`, and **bold**. Sufficient for the
    // proof.md template's shape.
    function markdownToHTML(md) {
        // Split fenced code blocks first so we don't munge their contents.
        const parts = [];
        let i = 0;
        const fenceRe = /^```[ \t]*([a-zA-Z0-9_-]*)[ \t]*\n([\s\S]*?)```/gm;
        let match;
        while ((match = fenceRe.exec(md))) {
            parts.push({ type: "text", value: md.slice(i, match.index) });
            parts.push({ type: "code", lang: match[1] || "", value: match[2] });
            i = fenceRe.lastIndex;
        }
        parts.push({ type: "text", value: md.slice(i) });

        return parts.map((p) => {
            if (p.type === "code") {
                return `<pre><code class="lang-${escapeHtml(p.lang)}">${escapeHtml(p.value)}</code></pre>`;
            }
            return renderTextSegment(p.value);
        }).join("");
    }

    function renderTextSegment(text) {
        const lines = text.split("\n");
        let out = [];
        let inList = false;
        let inBlockquote = false;
        let paragraph = [];

        const flushPara = () => {
            if (paragraph.length) {
                out.push(`<p>${inline(paragraph.join(" "))}</p>`);
                paragraph = [];
            }
        };
        const flushList = () => {
            if (inList) { out.push("</ul>"); inList = false; }
        };
        const flushQuote = () => {
            if (inBlockquote) { out.push("</blockquote>"); inBlockquote = false; }
        };

        for (const raw of lines) {
            const line = raw.trimEnd();
            if (!line.trim()) {
                flushPara(); flushList(); flushQuote();
                continue;
            }
            const h = line.match(/^(#{1,6})\s+(.*)$/);
            if (h) {
                flushPara(); flushList(); flushQuote();
                const level = h[1].length;
                out.push(`<h${level}>${inline(h[2])}</h${level}>`);
                continue;
            }
            if (line.startsWith("> ")) {
                flushPara(); flushList();
                if (!inBlockquote) { out.push("<blockquote>"); inBlockquote = true; }
                out.push(`<p>${inline(line.slice(2))}</p>`);
                continue;
            }
            if (line.match(/^[-*]\s+/)) {
                flushPara(); flushQuote();
                if (!inList) { out.push("<ul>"); inList = true; }
                out.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`);
                continue;
            }
            paragraph.push(line);
        }
        flushPara(); flushList(); flushQuote();
        return out.join("\n");
    }

    function inline(s) {
        // escape first, then re-introduce markup. escapeHtml only
        // touches < > & " ' — the markdown delimiters ` * ! [ ] ( )
        // survive, so we can match them on the escaped string safely.
        let escaped = escapeHtml(s);
        escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");
        escaped = escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        // images: ![alt](src). Relative `assets/...` paths are rewritten
        // to the bundle-file endpoint so the MD view can show charts
        // (proof.html embeds them as data-URIs; proof.md references them
        // by relative path — without rewriting they 404 against /ui).
        escaped = escaped.replace(
            /!\[([^\]]*)\]\(([^)\s]+)\)/g,
            (_m, alt, src) =>
                `<img alt="${alt}" src="${rewriteAssetSrc(src)}" loading="lazy" />`,
        );
        // links: [text](href). Open in a new tab; noopener for safety.
        escaped = escaped.replace(
            /\[([^\]]+)\]\(([^)\s]+)\)/g,
            (_m, text, href) =>
                `<a href="${href}" target="_blank" rel="noopener noreferrer">${text}</a>`,
        );
        return escaped;
    }

    // Rewrite a markdown image/link target that points at a bundle
    // asset (relative `assets/<name>`) to the absolute bundle-file
    // endpoint URL for the currently-selected bundle. Absolute URLs
    // (http, data:, /...) are left untouched.
    function rewriteAssetSrc(src) {
        if (selectedBundle && /^assets\//.test(src)) {
            return fileURL(src);
        }
        return src;
    }

    // ---------------------- scenarios tab ----------------------
    // Renders from the cached boot response (state.scenarios) — no
    // refetch. If the cache is somehow empty, fetch once as a fallback.

    async function renderScenarios() {
        const grid = $("#scenarios-grid");
        if (!state.scenarios) {
            grid.innerHTML = '<div class="muted">Loading…</div>';
            try {
                state.scenarios = await fetchJSON("/scenarios");
            } catch (e) {
                grid.innerHTML = `<div class="error-text">Failed: ${escapeHtml(e.message)}</div>`;
                return;
            }
        }
        const data = state.scenarios;
        $("#scenarios-count").textContent = `(${data.count})`;
        grid.innerHTML = "";
        for (const s of data.scenarios) {
            const card = document.createElement("div");
            card.className = "scenario-card";
            card.innerHTML = `
                <div class="name">${escapeHtml(s.name)}</div>
                <div class="badges">
                    <span class="tier-tag">${escapeHtml(s.tier || "?")}</span>
                    <span class="family-tag">${escapeHtml(s.family || "?")}</span>
                </div>
                <div class="goal">${escapeHtml(s.goal || "")}</div>
            `;
            grid.appendChild(card);
        }
    }

    function populateRunSelect(data) {
        const sel = $("#run-scenario");
        sel.innerHTML = data.scenarios
            .map((s) => `<option value="${escapeHtml(s.name)}">${escapeHtml(s.name)}</option>`)
            .join("");
        // Show the selected scenario's claim so the operator knows what
        // it tests + what kwargs it needs, instead of guessing.
        sel.addEventListener("change", () => showRunClaim(sel.value));
        if (data.scenarios.length) showRunClaim(sel.value);
    }

    async function showRunClaim(name) {
        const box = $("#run-claim");
        if (!box || !name) return;
        box.innerHTML = '<span class="muted">Loading claim…</span>';
        try {
            const claim = await fetchJSON(`/scenarios/${encodeURIComponent(name)}/claim`);
            const t = claim.threshold || {};
            const thr = t.metric
                ? `${t.metric} ${t.comparator || ""} ${t.value}${t.units ? " " + t.units : ""}`
                : "—";
            box.innerHTML =
                `<div class="claim-statement">${escapeHtml(claim.statement || "")}</div>`
                + `<div class="claim-threshold"><strong>threshold:</strong> `
                + `<code>${escapeHtml(thr)}</code></div>`;
        } catch (e) {
            box.innerHTML = `<span class="muted">No claim preview (${escapeHtml(e.message)})</span>`;
        }
    }

    // ---------------------- metrics tab ----------------------

    async function refreshMetrics() {
        const tiles = $("#metrics-tiles");
        const raw = $("#metrics-raw");
        tiles.innerHTML = '<div class="muted">Loading…</div>';
        try {
            const text = await fetchText("/metrics");
            raw.textContent = text;
            tiles.innerHTML = "";
            const parsed = parseMetricsText(text);
            for (const m of parsed) {
                const tile = document.createElement("div");
                tile.className = `metric-tile ${m.kind === "info" ? "info" : ""}`;
                tile.innerHTML = `
                    <div class="metric-name">${escapeHtml(m.name)}</div>
                    <div class="metric-value">${escapeHtml(m.value)}</div>
                `;
                tiles.appendChild(tile);
            }
        } catch (e) {
            tiles.innerHTML = `<div class="error-text">Failed: ${escapeHtml(e.message)}</div>`;
        }
    }

    // Minimal Prometheus text-format parser — handles
    //   `# HELP name desc`
    //   `# TYPE name kind`
    //   `name{labels} value`
    function parseMetricsText(text) {
        const out = [];
        const lines = text.split("\n");
        const types = {};
        for (const line of lines) {
            if (line.startsWith("# TYPE ")) {
                const [, name, kind] = line.match(/^# TYPE (\S+)\s+(\S+)/) || [];
                if (name) types[name] = kind;
                continue;
            }
            if (line.startsWith("#") || !line.trim()) continue;
            const m = line.match(/^(\S+?)(\{[^}]*\})?\s+(.+)$/);
            if (!m) continue;
            const [, name, labels, value] = m;
            const kind = types[name] || "gauge";
            let displayName = name;
            if (labels) {
                // Strip `_info` from gauge names with labels for prettier display
                const inner = labels.slice(1, -1);
                displayName = `${name} ${inner}`;
            }
            // For Info-style gauges, value is always 1.0; show labels instead.
            let displayValue;
            if (kind === "info" || name.endsWith("_info")) {
                displayValue = labels ? labels.slice(1, -1) : value;
            } else {
                displayValue = value;
            }
            out.push({ name: displayName, value: displayValue, kind: kind === "info" || name.endsWith("_info") ? "info" : "gauge" });
        }
        return out;
    }

    // ---------------------- run tab ----------------------

    $("#run-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = $("#run-scenario").value;
        const kwargs = $("#run-kwargs").value || "{}";
        try {
            JSON.parse(kwargs);  // sanity check
        } catch (err) {
            return showRunStatus("error", `Invalid JSON in kwargs: ${err.message}`);
        }
        const btn = $("#run-form").querySelector("button");
        btn.disabled = true;
        showRunStatus("running", `Running ${name}…`);
        try {
            const res = await fetch(
                `/scenarios/${encodeURIComponent(name)}/run`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ kwargs_json: kwargs }),
                },
            );
            const data = await res.json();
            $("#run-result").textContent = JSON.stringify(data, null, 2);
            if (!res.ok) {
                showRunStatus("error", `${res.status}: ${data.detail || "failed"}`);
            } else {
                const verdict = (data.proof?.verdict?.outcome) || "DONE";
                showRunStatus("done", `${name} → ${verdict}`);
                // Refresh bundle tree so the new proof shows up + repaint
                // the header counts from the refreshed tree.
                await refreshTree();
                repaintHeaderCounts();
            }
        } catch (err) {
            showRunStatus("error", err.message);
        } finally {
            btn.disabled = false;
        }
    });

    function showRunStatus(kind, msg) {
        const el = $("#run-status");
        el.className = `run-status visible ${kind}`;
        el.textContent = msg;
    }

    function repaintHeaderCounts() {
        const t = (state.tree && state.tree.totals) || {};
        $("#stat-bundles").textContent = `${t.bundles || 0} bundles`;
        const v = t.verdicts || {};
        $("#stat-validated").textContent = `${v.validated || 0} validated`;
        $("#stat-refuted").textContent = `${v.refuted || 0} refuted`;
        $("#stat-inconclusive").textContent = `${v.inconclusive || 0} inconclusive`;
    }

    // ---------------------- deep-link hash routing ----------------------
    // Hash shapes:
    //   #tab=metrics
    //   #bundle=<tier>/<scenario>/<bundle>   (implies the proofs tab)
    // Shareable + reload-safe. setHash guards against feedback loops via
    // state.suppressHash while we programmatically restore.

    function setHash({ tab, bundle }) {
        if (state.suppressHash) return;
        let h = "";
        if (bundle) h = `bundle=${bundle}`;
        else if (tab) h = `tab=${tab}`;
        const next = h ? `#${h}` : "";
        if (next !== location.hash) {
            history.replaceState(null, "", next || location.pathname);
        }
    }

    function parseHash() {
        const h = location.hash.replace(/^#/, "");
        const out = {};
        for (const part of h.split("&")) {
            const eq = part.indexOf("=");
            if (eq > 0) out[part.slice(0, eq)] = decodeURIComponent(part.slice(eq + 1));
        }
        return out;
    }

    function restoreFromHash() {
        const { tab, bundle } = parseHash();
        state.suppressHash = true;
        try {
            if (bundle) {
                activateTab("proofs", { updateHash: false });
                const el = $$(".tree-bundle").find((d) => {
                    return `${d.dataset.tier}/${d.dataset.scenario}/${d.dataset.bundle}` === bundle;
                });
                if (el) {
                    selectBundle(el, { updateHash: false });
                    el.scrollIntoView({ block: "center" });
                }
            } else if (tab) {
                activateTab(tab, { updateHash: false });
            }
        } finally {
            state.suppressHash = false;
        }
    }

    // ---------------------- wire up refresh buttons ----------------------

    $("#refresh-tree").addEventListener("click", refreshTree);
    $("#refresh-metrics").addEventListener("click", refreshMetrics);
    wireTreeFilter();
    window.addEventListener("hashchange", restoreFromHash);

    // ---------------------- boot ----------------------
    // Single deduped fetch; Metrics + Scenarios load lazily on first
    // tab activation (boot() → restoreFromHash() handles deep links).

    boot();
})();
