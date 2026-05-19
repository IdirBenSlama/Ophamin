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

    // ---------------------- tabs ----------------------

    function activateTab(name) {
        $$(".tab").forEach((b) =>
            b.classList.toggle("active", b.dataset.tab === name),
        );
        $$(".tab-panel").forEach((p) =>
            p.classList.toggle("active", p.id === `tab-${name}`),
        );
    }

    $$(".tab").forEach((b) =>
        b.addEventListener("click", () => activateTab(b.dataset.tab)),
    );

    // ---------------------- header stats ----------------------

    async function refreshHeaderStats() {
        try {
            const [version, scenarios, tree] = await Promise.all([
                fetchJSON("/version"),
                fetchJSON("/scenarios"),
                fetchJSON("/proofs/bundles/tree"),
            ]);
            $("#stat-version").textContent = `v${version.framework_version}`;
            $("#stat-scenarios").textContent = `${scenarios.count} scenarios`;
            const t = tree.totals || {};
            $("#stat-bundles").textContent = `${t.bundles || 0} bundles`;
            const v = t.verdicts || {};
            $("#stat-validated").textContent = `${v.validated || 0} validated`;
            $("#stat-refuted").textContent = `${v.refuted || 0} refuted`;
            $("#stat-inconclusive").textContent =
                `${v.inconclusive || 0} inconclusive`;
        } catch (e) {
            console.error("header stats failed:", e);
        }
    }

    // ---------------------- proofs tab (tree) ----------------------

    let selectedBundle = null; // { tier, scenario, bundle, files }

    async function refreshTree() {
        const root = $("#bundle-tree");
        root.innerHTML = '<div class="muted" style="padding:14px">Loading…</div>';
        try {
            const tree = await fetchJSON("/proofs/bundles/tree");
            renderTree(tree);
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
                    div.innerHTML = `
                        <span class="bundle-date">${escapeHtml(b.date)}</span>
                        <span class="verdict-tag ${b.verdict}">${escapeHtml(b.verdict)}</span>
                        <span class="bundle-hash">${escapeHtml(b.short_hash)}</span>
                    `;
                    div.addEventListener("click", () => selectBundle(div));
                    scDetails.appendChild(div);
                }
                tierDetails.appendChild(scDetails);
            }
            root.appendChild(tierDetails);
        }
    }

    function selectBundle(el) {
        $$(".tree-bundle.active").forEach((n) =>
            n.classList.remove("active"),
        );
        el.classList.add("active");
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
    }

    function renderFormatTabs(files) {
        const nav = $("#format-tabs");
        nav.innerHTML = "";
        for (const f of files) {
            const b = document.createElement("button");
            b.className = "format-tab";
            b.textContent = f.replace(/^proof\./, "").toUpperCase();
            b.dataset.file = f;
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
        $$(".format-tab").forEach((b) =>
            b.classList.toggle("active", b.dataset.file === filename),
        );
        const view = $("#detail-view");
        view.innerHTML = '<div class="empty-state">Loading…</div>';

        const url = fileURL(filename);
        try {
            if (filename === "proof.html") {
                view.innerHTML = `<iframe src="${url}"></iframe>`;
            } else if (filename === "proof.pdf") {
                view.innerHTML = `<iframe src="${url}#view=FitH" type="application/pdf"></iframe>`;
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
        // escape first, then re-introduce <strong> + <code> markup.
        let escaped = escapeHtml(s);
        escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");
        escaped = escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        return escaped;
    }

    // ---------------------- scenarios tab ----------------------

    async function refreshScenarios() {
        const grid = $("#scenarios-grid");
        grid.innerHTML = '<div class="muted">Loading…</div>';
        try {
            const data = await fetchJSON("/scenarios");
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
            // Populate the run-form scenario selector too.
            const sel = $("#run-scenario");
            sel.innerHTML = data.scenarios
                .map((s) => `<option value="${escapeHtml(s.name)}">${escapeHtml(s.name)}</option>`)
                .join("");
        } catch (e) {
            grid.innerHTML = `<div class="error-text">Failed: ${escapeHtml(e.message)}</div>`;
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
                // Refresh bundle tree so the new proof shows up.
                refreshTree();
                refreshHeaderStats();
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

    // ---------------------- wire up refresh buttons ----------------------

    $("#refresh-tree").addEventListener("click", refreshTree);
    $("#refresh-metrics").addEventListener("click", refreshMetrics);

    // ---------------------- boot ----------------------

    refreshHeaderStats();
    refreshTree();
    refreshScenarios();
    refreshMetrics();
})();
