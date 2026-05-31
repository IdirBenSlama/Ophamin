/** @jsxRuntime classic */ /** @jsx React.createElement */
/* global React, ReactDOM, OPHAMIN, AppShell, OverviewScreen, ProofsScreen, ScenariosScreen, RunScreen, TelemetryScreen, TweaksPanel, useTweaks, TweakSection, TweakRadio, TweakColor */

const { useState: useAppState, useEffect: useAppEffect } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "dark",
  "density": "comfortable",
  "accent": "#2c8df7"
}/*EDITMODE-END*/;

// Accent options (UniFi blue default; Ophamin teal + a couple instrument hues)
const ACCENT_OPTIONS = ['#2c8df7', '#2dd4bf', '#a3e635', '#f5b948'];
// HSL conversions for --accent-h/s/l
const ACCENT_HSL = {
  '#2c8df7': '212 92% 57%',   // UniFi blue — default
  '#2dd4bf': '172 66% 51%',   // Ophamin teal
  '#a3e635': '83 76% 56%',    // lime
  '#f5b948': '38 89% 62%',    // instrument amber
};

function App() {
  // SCREEN BINDINGS — resolve via window so strict-mode bare-identifier
  // lookups can never throw, regardless of script load order.
  const AppShell          = window.AppShell;
  const OverviewScreen    = window.OverviewScreen;
  const ProofsScreen      = window.ProofsScreen;
  const ScenariosScreen   = window.ScenariosScreen;
  const RunScreen         = window.RunScreen;
  const TelemetryScreen   = window.TelemetryScreen;
  const AgentsScreen      = window.AgentsScreen;
  const LabScreen         = window.LabScreen;
  const AuditScreen       = window.AuditScreen;
  const ChatScreen        = window.ChatScreen;
  const RoadmapScreen     = window.RoadmapScreen;
  const DiscoveryScreen   = window.DiscoveryScreen;
  const InspectorScreen   = window.InspectorScreen;
  const ControlRoomScreen = window.ControlRoomScreen;
  const InteropScreen     = window.InteropScreen;
  const IntegrationsScreen = window.IntegrationsScreen;
  const SubstrateScreen   = window.SubstrateScreen;
  const CockpitScreen     = window.CockpitScreen;
  const FlowScreen        = window.FlowScreen;
  const ConfigScreen      = window.ConfigScreen;
  const ModelsScreen      = window.ModelsScreen;
  const ToolkitsScreen    = window.ToolkitsScreen;
  const ComposeScreen     = window.ComposeScreen;
  const VerifyScreen      = window.VerifyScreen;
  const CommandPalette    = window.CommandPalette;
  const TweaksPanel       = window.TweaksPanel;
  const TweakSection      = window.TweakSection;
  const TweakRadio        = window.TweakRadio;
  const TweakColor        = window.TweakColor;
  const ShortcutsModal    = window.ShortcutsModal;
  const KeyboardNav       = window.KeyboardNav;
  const IntroOverlay      = window.IntroOverlay;

  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [screen, setScreen] = useAppState('overview');
  const [proofFilter, setProofFilter] = useAppState(null);
  const [proofBundle, setProofBundle] = useAppState(null);
  const [runScenario, setRunScenario] = useAppState(null);
  // Bumped when the substrate selector scopes the corpus (data-layer
  // filter on OPHAMIN.bundles/totals) so the screens re-read it.
  const [, setSubstrateScope] = useAppState(0);

  // Apply tweaks to root
  useAppEffect(() => {
    document.documentElement.setAttribute('data-theme', t.theme);
    document.documentElement.setAttribute('data-density', t.density);
    const hsl = ACCENT_HSL[t.accent] || ACCENT_HSL['#2dd4bf'];
    const [h, s, l] = hsl.split(' ');
    document.documentElement.style.setProperty('--accent-h', h);
    document.documentElement.style.setProperty('--accent-s', s);
    document.documentElement.style.setProperty('--accent-l', l);
  }, [t.theme, t.density, t.accent]);

  useAppEffect(() => {
    const fn = (e) => nav(e.detail);
    window.addEventListener('ophamin:nav', fn);
    return () => window.removeEventListener('ophamin:nav', fn);
  }, []);

  const nav = (id) => {
    setScreen(id);
    if (id !== 'proofs') { setProofFilter(null); setProofBundle(null); }
    if (id !== 'run') setRunScenario(null);
  };

  const onNavToProofs = (filter, bundle) => {
    setProofFilter(filter || null);
    setProofBundle(bundle || null);
    setScreen('proofs');
  };

  const onRun = (scn) => { setRunScenario(scn); setScreen('run'); };

  const onJumpToProof = (bundle) => {
    setProofBundle(bundle);
    setScreen('proofs');
  };

  return (
    <>
      <AppShell
        active={screen}
        onNav={nav}
        onSubstrateChange={() => { setProofBundle(null); setSubstrateScope(n => n + 1); }}
        totals={OPHAMIN.totals}
        theme={t.theme}
        density={t.density}
        onToggleTheme={() => setTweak('theme', t.theme === 'dark' ? 'light' : 'dark')}
      >
        {screen === 'overview'  && <OverviewScreen onNavToProofs={onNavToProofs}/>}
        {screen === 'drift'     && <DriftScreen onNavToProofs={onNavToProofs}/>}
        {screen === 'topology'  && <TopologyScreen onNavToProofs={onNavToProofs}/>}
        {screen === 'proofs'    && <ProofsScreen initialFilter={proofFilter} initialBundle={proofBundle}/>}
        {screen === 'scenarios' && <ScenariosScreen onRun={onRun}/>}
        {screen === 'run'       && <RunScreen initialScenario={runScenario} onJumpToProof={onJumpToProof}/>}
        {screen === 'telemetry' && <TelemetryScreen/>}
        {screen === 'agents'    && <AgentsScreen/>}
        {screen === 'lab'       && <LabScreen/>}
        {screen === 'audit'     && <AuditScreen/>}
        {screen === 'chat'      && <ChatScreen onNavToProofs={onNavToProofs} onNavToDrift={() => setScreen('drift')} onNavToAgents={() => setScreen('agents')}/>}
        {screen === 'roadmap'   && <RoadmapScreen onNavToProofs={onNavToProofs}/>}
        {screen === 'discovery' && <DiscoveryScreen/>}
        {screen === 'inspector' && <InspectorScreen/>}
        {screen === 'control'   && <ControlRoomScreen/>}
        {screen === 'interop'   && <InteropScreen/>}
        {screen === 'integrations' && <IntegrationsScreen/>}
        {screen === 'substrate' && <SubstrateScreen/>}
        {screen === 'cockpit'   && <CockpitScreen/>}
        {screen === 'flow'      && <FlowScreen/>}
        {screen === 'config'    && <ConfigScreen/>}
        {screen === 'models'    && <ModelsScreen/>}
        {screen === 'toolkits'  && <ToolkitsScreen/>}
        {screen === 'compose'   && <ComposeScreen/>}
        {screen === 'verify'    && <VerifyScreen/>}
        {screen === 'settings'  && <SettingsScreen tweak={t} setTweak={setTweak}/>}
      </AppShell>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Appearance">
          <TweakRadio label="Theme" value={t.theme} onChange={v => setTweak('theme', v)}
            options={[{ value: 'dark', label: 'Dark' }, { value: 'light', label: 'Light' }]}/>
          <TweakRadio label="Density" value={t.density} onChange={v => setTweak('density', v)}
            options={[{ value: 'comfortable', label: 'Comfort' }, { value: 'compact', label: 'Compact' }]}/>
          <TweakColor label="Accent" value={t.accent} onChange={v => setTweak('accent', v)}
            options={ACCENT_OPTIONS}/>
        </TweakSection>
        <TweakSection label="Hints">
          <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.55, padding: '6px 0' }}>
            Click the wheels mark in the topbar to <b>collapse the rail</b>. Click any donut segment on Overview to <b>filter Proofs</b>. Run a scenario from the Scenarios catalog to land on the Run console pre-filled.
          </div>
        </TweakSection>
      </TweaksPanel>

      <ShortcutsModal/>
      <KeyboardNav/>
      <IntroOverlay/>

      <CommandPalette onAction={(a) => {
        if (a.kind === 'theme') { setTweak('theme', t.theme === 'dark' ? 'light' : 'dark'); return; }
        if (a.kind === 'reindex') { window.toast && window.toast({ kind: 'success', title: 'Bundles reindexed', msg: 'POST /proofs/index · 33 bundles' }); return; }
        if (a.nav === 'proofs') { onNavToProofs(a.filter || null, a.bundle || null); return; }
        if (a.nav === 'run' && a.scenario) { onRun(a.scenario); return; }
        if (a.nav) setScreen(a.nav);
      }}/>
    </>
  );
}

function AgentsPlaceholder() {
  return (
    <div className="content-inner page" style={{ display: 'grid', placeItems: 'center', minHeight: 'calc(100vh - 56px)' }}>
      <div style={{ textAlign: 'center', maxWidth: 480 }}>
        <div className="micro" style={{ color: 'var(--accent)', marginBottom: 12 }}>PHASE 2 · LOCAL-LLM AGENTIC LAYER</div>
        <h2 style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', margin: '0 0 12px' }}>Agents</h2>
        <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6, fontSize: 14 }}>
          The 0.63.x agentic layer runs via <span className="mono" style={{ color: 'var(--text-primary)' }}>ophamin agent …</span> CLI today —
          HTTP routes for prereg-validator, confound-enumerator, scenario-gen, proof-brief,
          refuted-triage, and bundle-query are flagged for the next milestone.
        </p>
        <div style={{ marginTop: 24, display: 'inline-flex', gap: 6 }}>
          {['prereg-validator', 'confound-enumerator', 'scenario-gen', 'proof-brief', 'refuted-triage', 'bundle-query'].map(a => (
            <span key={a} className="chip">{a}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function DDSnapshotCard() {
  const D = window.OPHAMIN;
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Snapshot for investors and auditors</div>
          <div className="micro" style={{ marginTop: 2 }}>SIGNED, CONTENT-ADDRESSED, REPRODUCIBLE</div>
        </div>
        <span className="chip">interop</span>
      </div>
      <div style={{ padding: 16 }}>
        <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55, margin: '0 0 12px' }}>
          A signed, content-addressed bundle of the current empirical record. Latest proof per scenario plus journal entries since the last snapshot, with a manifest hash. The artifact a Kimera investor or auditor receives.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 12 }}>
          <div className="dd-stat"><span className="micro">SCENARIOS</span><span className="mono tnum">{D.totals.scenarios}</span></div>
          <div className="dd-stat"><span className="micro">SIGNED PROOFS</span><span className="mono tnum">{D.totals.bundles}</span></div>
          <div className="dd-stat"><span className="micro">SUBSTRATE STAMPS</span><span className="mono tnum">{D.substrateStamps.length}</span></div>
          <div className="dd-stat"><span className="micro">HARDENING TESTS</span><span className="mono tnum">2,944</span></div>
        </div>
        <div className="mono" style={{ fontSize: 11, padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', color: 'var(--text-secondary)' }}>
          manifest_hash = sha256(canonical(latest-proof[per-scenario] ∪ journal[since-last]))<br/>
          signature     = HMAC-SHA256(publication_key, manifest_hash)<br/>
          format        = ophamin-dd-snapshot/1.0
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
          <button className="btn primary" style={{ fontSize: 12 }}><Icon name="download" size={12}/> Export snapshot</button>
          <button className="btn" style={{ fontSize: 12 }}><Icon name="copy" size={12}/> Copy manifest hash</button>
          <span style={{ flex: 1 }}/>
          <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', alignSelf: 'center' }}>
            last exported: 2026-05-18 · b3525b62...
          </span>
        </div>
      </div>
    </div>
  );
}

function MCPCard() {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">MCP server</div>
          <div className="micro" style={{ marginTop: 2 }}>MODEL CONTEXT PROTOCOL · AGENT-CALLABLE INTEROP LAYER</div>
        </div>
        <span className="live-pill ok"><span className="dot"></span>running</span>
      </div>
      <div style={{ padding: 16 }}>
        <p style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.55, margin: '0 0 12px' }}>
          MCP exposes Ophamin's read + run + verify surfaces to any agent that speaks the Model Context Protocol — Claude Code, Claude Desktop, Cursor, Cline, custom orchestrators. Same shared implementations as the HTTP API; behavioural drift is structurally impossible.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 12 }}>
          <div className="dd-stat"><span className="micro">TRANSPORT</span><span className="mono">stdio + sse</span></div>
          <div className="dd-stat"><span className="micro">CONNECTED CLIENTS</span><span className="mono tnum">3</span></div>
          <div className="dd-stat"><span className="micro">CALLS · 24H</span><span className="mono tnum">412</span></div>
          <div className="dd-stat"><span className="micro">P50 LATENCY</span><span className="mono tnum">8 ms</span></div>
        </div>
        <div className="micro" style={{ marginBottom: 6 }}>EXPOSED TOOLS</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 12 }}>
          {['list_scenarios','get_scenario_claim','list_bundles','read_bundle_file','run_scenario','verify_proof','canonicalize','reindex'].map(t =>
            <span key={t} className="chip" style={{ fontFamily: 'JetBrains Mono, monospace', textTransform: 'none', letterSpacing: 0, fontSize: 10.5 }}>{t}</span>
          )}
        </div>
        <div className="mono" style={{ fontSize: 11, padding: 10, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', color: 'var(--text-secondary)' }}>
          $ ophamin mcp serve --transport stdio<br/>
          $ ophamin mcp serve --transport sse --port 8002
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
          <button className="btn"><Icon name="copy" size={12}/> Copy MCP config</button>
          <button className="btn"><Icon name="external" size={12}/> View client list</button>
        </div>
      </div>
    </div>
  );
}

function PathTo10Card() {
  const GATES = [
    { id: 'E1', label: 'Cross-framework validation',         status: 'in-flight', detail: 'GWF↔Garak · Bayesian↔Stan · CRDT↔Yjs — each producing a signed measurement-machinery proof.' },
    { id: 'E2', label: 'Wire-format stability contract',     status: 'met',       detail: 'CampaignRecord 1.0 → 2.0 shipped in 0.9.0.' },
    { id: 'E3', label: 'Open data + benchmark corpus',       status: 'pending',   detail: 'Zenodo deposit of curated 100+ proof corpus with DOI. 6+ reproducer notebooks.' },
    { id: 'E4', label: 'Research-grade reproducibility',     status: 'in-flight', detail: 'Per-OS lockfiles · deterministic-seed audit · cosign container signing · third-party byte-equal rebuild.' },
    { id: 'E5', label: 'Methods paper · peer review',        status: 'pending',   detail: 'Submission to JOSS · SoftwareX · JMLR-OSS · external reviewer sign-off.' },
    { id: 'E8', label: 'Python-API stability contract',      status: 'met',       detail: '28 @Stable symbols · regression suite · ophamin api-stability CLI · shipped 0.10.0.' },
    { id: 'E9', label: 'Cross-language read APIs',           status: 'in-flight', detail: 'crates/ophamin-proof (Rust) + packages/ophamin-proof-js (TS) — byte-equal verifiers.' },
    { id: 'E10', label: 'Community infrastructure',          status: 'met',       detail: 'GOVERNANCE.md · ROADMAP.md · Discussions toggled in 0.10.x.' },
  ];
  const met = GATES.filter(g => g.status === 'met').length;
  const inFlight = GATES.filter(g => g.status === 'in-flight').length;
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Path to 1.0</div>
          <div className="micro" style={{ marginTop: 2 }}>RELEASE-READINESS GATES · RFC 0002</div>
        </div>
        <span className="live-pill" style={{ color: 'var(--text-secondary)', background: 'var(--bg-surface-2)', borderColor: 'var(--border-strong)' }}>
          <span className="dot" style={{ background: 'var(--accent)' }}></span>{met} met · {inFlight} in flight
        </span>
      </div>
      <div style={{ padding: 14 }}>
        {GATES.map(g => (
          <div key={g.id} className={'gate-row gate-' + g.status}>
            <span className={'gate-num gate-num-' + g.status}>{g.id}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{g.label}</span>
                <span className={'gate-status gate-status-' + g.status}>{g.status.replace('-', ' ')}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginTop: 3 }}>{g.detail}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProtocolsCard() {
  const PROTOCOLS = [
    { name: 'Pillar',            file: 'protocols.py:Pillar',            desc: 'Statistical primitive contract — backed by scipy/statsmodels/sklearn/MAPIE/river. Pillars compose; framework code orchestrates.' },
    { name: 'DatasetConnector',  file: 'protocols.py:DatasetConnector',  desc: 'Pluggable corpus adapter. Implementations: Enron, FLORES-200, Linux kernel, offensive-security, financial, The Well.' },
    { name: 'SubstrateProbe',    file: 'protocols.py:SubstrateProbe',    desc: 'Reads named-tuple of fields from the substrate-under-test. Field schema is mined by ophamin discover.' },
    { name: 'ScenarioProtocol',  file: 'protocols.py:ScenarioProtocol',  desc: 'A scenarios contract: name + tier + family + target + corpus_name + build_claim() + score().' },
    { name: 'SubstrateUnderTest',file: 'seeing/substrate/protocol.py',   desc: 'The one named boundary between Ophamin and the system being measured. MockSubstrate is the canonical reference implementation.' },
  ];
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Plugin protocols</div>
          <div className="micro" style={{ marginTop: 2 }}>NAMED ABSTRACTIONS · src/ophamin/protocols.py</div>
        </div>
        <span className="chip">{PROTOCOLS.length} contracts</span>
      </div>
      <div style={{ padding: 14 }}>
        {PROTOCOLS.map(p => (
          <div key={p.name} className="protocol-row">
            <div>
              <div className="mono" style={{ fontSize: 12.5, color: 'var(--accent)', fontWeight: 600 }}>{p.name}</div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{p.file}</div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{p.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CLICard() {
  const CLI_GROUPS = [
    { label: 'Core', cmds: [
      ['ophamin demo',                       'end-to-end mock experiment'],
      ['ophamin run <config.yaml>',          'run one experiment'],
      ['ophamin sweep <experiment.yaml>',    'parent + children parameter sweep'],
      ['ophamin lineage --list',             'list recorded runs'],
      ['ophamin verify',                     'install self-check + CI fast-fail'],
    ]},
    { label: 'Seeing', cmds: [
      ['ophamin discover <kimera-repo>',     'mine substrate field-schema'],
      ['ophamin discover-diff a.json b.json','structural diff between snapshots'],
      ['ophamin watch <kimera-repo>',        'continuous re-discover + diff'],
      ['ophamin inspect <repo> <primitive>', 'per-primitive composite profile'],
    ]},
    { label: 'Comparing', cmds: [
      ['ophamin drift-report',                       'cross-commit drift over signed proofs'],
      ['ophamin drift-detect --stream <s>',          'River streaming-drift on Φ / walker'],
    ]},
    { label: 'Auditing', cmds: [
      ['ophamin audit <path>',               'orchestrate 12 static-analysis tools'],
      ['ophamin self-test',                  'substrate-free dogfood scenarios'],
    ]},
    { label: 'Interop', cmds: [
      ['ophamin export <record> --format sarif',     'SARIF 2.1.0 for code-scanning tools'],
      ['ophamin export <record> --format junit-xml', 'JUnit XML for CI'],
      ['ophamin export <record> --format mlflow',    'MLflow Tracking Server'],
      ['ophamin export <record> --format cyclonedx', 'CycloneDX 1.5 SBOM'],
    ]},
    { label: 'Serving', cmds: [
      ['ophamin http serve',                  'FastAPI REST API + /ui'],
      ['ophamin mcp serve',                   'Model Context Protocol server'],
    ]},
    { label: 'Agents · default-off', cmds: [
      ['ophamin agent prereg <claim>',        'vet falsifiability before running'],
      ['ophamin agent scenario-gen',          'scaffold a Scenario subclass'],
      ['ophamin agent brief <proof>',         'plain-English brief'],
      ['ophamin agent triage <refuted-proof>','propose follow-up scenarios'],
      ['ophamin agent confounds <validated>', 'red-team alternative explanations'],
      ['ophamin agent query "<NL>"',          'natural-language proof-tree query'],
      ['ophamin agent adapt --name --desc',   'generate Foreign-Corpus adapter'],
    ]},
  ];
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">CLI surface</div>
          <div className="micro" style={{ marginTop: 2 }}>EVERYTHING THE FRAMEWORK CAN DO FROM THE TERMINAL</div>
        </div>
        <span className="chip">{CLI_GROUPS.reduce((s, g) => s + g.cmds.length, 0)} verbs</span>
      </div>
      <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {CLI_GROUPS.map(g => (
          <div key={g.label}>
            <div className="micro" style={{ marginBottom: 6 }}>{g.label.toUpperCase()}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {g.cmds.map(([cmd, desc]) => (
                <div key={cmd} className="cli-row">
                  <span className="mono" style={{ fontSize: 11.5, color: 'var(--accent)' }}>{cmd}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{desc}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SettingsScreen({ tweak, setTweak }) {
  return (
    <div className="content-inner page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <div className="page-subtitle mono">substrate config · sign-key · API stability · DD snapshot · console preferences</div>
        </div>
      </div>
      {/* Auth warning */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 12,
        padding: '12px 16px', margin: '0 0 16px',
        background: 'var(--inconclusive-bg)',
        border: '1px solid var(--inconclusive-line)',
        borderLeft: '3px solid var(--inconclusive)',
        borderRadius: 'var(--r-md)',
        color: 'var(--text-secondary)', fontSize: 12.5, lineHeight: 1.55,
      }}>
        <Icon name="rocket" size={16}/>
        <div>
          <b style={{ color: 'var(--inconclusive)' }}>Auth is delegated.</b> The Ophamin HTTP server has no built-in auth. Deploy behind a reverse proxy (nginx + OIDC, Traefik, API Gateway) and gate the heavyweight <span className="mono">POST /scenarios/{name}/run</span> endpoint — running scenarios costs compute proportional to caller demand. Console is currently bound to <span className="mono" style={{ color: 'var(--text-primary)' }}>localhost:8000</span> · no external exposure.
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-header"><div className="card-title">Substrate</div><span className="micro">UNDER TEST</span></div>
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <ConfigRow label="kimera_repo" v="/Users/work/Kimera-SWM-System" mono editable/>
            <ConfigRow label="substrate.kind" v="kimera" mono/>
            <ConfigRow label="substrate.target" v="entity" mono/>
            <ConfigRow label="default kwargs" v={'{}'} mono/>
            <ConfigRow label="probe self-test" v={<button className="btn" style={{ fontSize: 11 }}>ophamin probe-kimera</button>}/>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title">Sign key</div><span className="micro">HMAC PUBLICATION KEY</span></div>
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <ConfigRow label="source" v={<span className="mono">env: OPHAMIN_SIGN_KEY</span>}/>
            <ConfigRow label="loaded" v={<span style={{ color: 'var(--validated)' }}>● yes</span>}/>
            <ConfigRow label="key (b64)" v={<span className="mono faint">cGRy***************Y=</span>}/>
            <ConfigRow label="last rotation" v={<span className="mono">2026-04-22</span>}/>
            <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
              <button className="btn" style={{ fontSize: 11 }}>Reveal</button>
              <button className="btn" style={{ fontSize: 11 }}>Rotate key</button>
            </div>
          </div>
        </div>
      <DDSnapshotCard/>
      <div style={{ height: 16 }}/>
      <MCPCard/>
      <div style={{ height: 16 }}/>

      
      </div>

      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-header"><div className="card-title">API stability</div><span className="micro">@STABLE SYMBOLS</span></div>
          <div style={{ padding: 16 }}>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55, margin: '0 0 12px' }}>
              28 symbols carry the <span className="mono" style={{ color: 'var(--accent)' }}>@Stable</span> contract. Scenario scoring functions using only stable APIs survive across minor versions.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, fontSize: 11 }}>
              <ApiRow name="Pillar"            ok/>
              <ApiRow name="DatasetConnector"  ok/>
              <ApiRow name="SubstrateProbe"    ok/>
              <ApiRow name="ScenarioProtocol"  ok/>
              <ApiRow name="SubstrateUnderTest" ok/>
              <ApiRow name="Scenario.score"    ok/>
              <ApiRow name="Scenario.build_claim" ok/>
              <ApiRow name="Verdict.decide"    ok/>
              <ApiRow name="ProofRecord"       ok/>
              <ApiRow name="Claim"             ok/>
              <ApiRow name="Threshold"         ok/>
              <ApiRow name="PillarEvidence"    ok/>
              <ApiRow name="PreRegistration"   ok/>
              <ApiRow name="Reproduction"      ok/>
              <ApiRow name="DatasetRef"        ok/>
              <ApiRow name="LineageChain"      ok/>
              <ApiRow name="HMACVerify"        ok/>
              <ApiRow name="canonicalize"      ok/>
              <ApiRow name="verify_proof_bytes" ok/>
              <ApiRow name="sign_record"       ok/>
              <ApiRow name="MockSubstrate"     ok/>
              <ApiRow name="MetricRef"         ok/>
              <ApiRow name="CorpusRef"         ok/>
              <ApiRow name="MetricRegistry"    ok/>
              <ApiRow name="LLMCallRecord"     ok/>
              <ApiRow name="AuditRecord"       ok/>
              <ApiRow name="DriftDetector"     ok/>
              <ApiRow name="InteropExporter"   ok/>
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)' }}>
              Run <span className="mono">ophamin api-stability</span> to verify your code against the contract.
            </div>
            <div className="micro" style={{ marginTop: 16, marginBottom: 6 }}>SCHEMA VERSIONS</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
              <div className="schema-row"><span className="mono">CampaignRecord</span><span className="mono" style={{ color: 'var(--accent)' }}>1.0 → 2.0</span></div>
              <div className="schema-row"><span className="mono">EmpiricalProofRecord</span><span className="mono" style={{ color: 'var(--accent)' }}>1.0</span></div>
              <div className="schema-row"><span className="mono">AuditRecord</span><span className="mono" style={{ color: 'var(--accent)' }}>1.0</span></div>
              <div className="schema-row"><span className="mono">LLMCallRecord</span><span className="mono" style={{ color: 'var(--accent)' }}>1.0</span></div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title">Console</div><span className="micro">PREFS</span></div>
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <ConfigRow label="theme" v={tweak.theme}/>
            <ConfigRow label="density" v={tweak.density}/>
            <ConfigRow label="accent" v={
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 14, height: 14, borderRadius: 3, background: tweak.accent, border: '1px solid var(--border-strong)' }}/>
                <span className="mono">{tweak.accent}</span>
              </span>
            }/>
            <ConfigRow label="proofs root" v={<span className="mono">./proofs</span>}/>
            <ConfigRow label="LLM base URL" v={<span className="mono">http://localhost:11434/v1</span>}/>
            <ConfigRow label="MCP server" v={<span style={{ color: 'var(--text-muted)' }}>not running · ophamin mcp serve</span>}/>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><div className="card-title">Build · Runtime</div><span className="micro">INFO</span></div>
        <div style={{ padding: 16, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, fontSize: 12 }}>
          <ConfigRow label="ophamin" v={<span className="mono">{OPHAMIN.version}</span>}/>
          <ConfigRow label="commit" v={<span className="mono">{OPHAMIN.git_commit.slice(0,7)}</span>}/>
          <ConfigRow label="python" v={<span className="mono">3.14.3</span>}/>
          <ConfigRow label="platform" v={<span className="mono">macOS-26.3.1-arm64</span>}/>
        </div>
      </div>

      <div style={{ height: 16 }}/>
      <PathTo10Card/>
      <div style={{ height: 16 }}/>
      <ProtocolsCard/>
      <div style={{ height: 16 }}/>
      <CLICard/>
    </div>
  );
}

function ConfigRow({ label, v, mono, editable }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
      <span className="mono" style={{ color: 'var(--text-muted)', fontSize: 11, minWidth: 110 }}>{label}</span>
      <span style={{ flex: 1, color: 'var(--text-primary)' }}>{v}</span>
      {editable && <button className="btn ghost icon" title="Edit"><Icon name="copy" size={11}/></button>}
    </div>
  );
}

function ApiRow({ name, ok }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <Icon name={ok ? 'check' : 'x'} size={11}/>
      <span className="mono" style={{ color: ok ? 'var(--validated)' : 'var(--refuted)', fontSize: 11 }}>{name}</span>
    </div>
  );
}





class ErrorBoundary extends React.Component {
  constructor(p) {
    super(p);
    this.state = { err: null };
    window.__resetErrorBoundary = () => this.setState({ err: null });
  }
  static getDerivedStateFromError(e) { return { err: e }; }
  render() {
    if (this.state.err) {
      const msg = (this.state.err.message || '') + '\n\n' + (this.state.err.stack || this.state.err.toString());
      return React.createElement('div', { style: { padding: 24, background: 'var(--bg-base)', minHeight: '100vh', fontFamily: 'JetBrains Mono, monospace' } },
        React.createElement('h2', { style: { color: '#f87171', fontSize: 14, margin: '0 0 12px' } }, 'Render error caught'),
        React.createElement('pre', { style: { color: '#f87171', fontSize: 11, lineHeight: 1.5, whiteSpace: 'pre-wrap', maxHeight: 400, overflow: 'auto' } }, msg),
        React.createElement('button', {
          onClick: () => this.setState({ err: null }),
          style: { marginTop: 16, padding: '8px 16px', background: '#2c8df7', color: '#fff', border: 0, borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer' }
        }, 'Retry render')
      );
    }
    return this.props.children;
  }
}

const appRoot = ReactDOM.createRoot(document.getElementById('root'));
const REQUIRED = ['AppShell','OverviewScreen','ProofsScreen','ScenariosScreen','RunScreen','TelemetryScreen','AgentsScreen','LabScreen','AuditScreen','ChatScreen','RoadmapScreen','DiscoveryScreen','InspectorScreen','ControlRoomScreen','InteropScreen','IntegrationsScreen','SubstrateScreen','CockpitScreen','FlowScreen','ConfigScreen','ModelsScreen','ToolkitsScreen','VerifyScreen','CommandPalette','TweaksPanel'];
// FORCE_FETCH_FALLBACK — Babel-standalone occasionally silently skips a
// script-tag transform. Map every required component to the file it lives in,
// and if it's missing after polling, fetch+compile+eval that file directly.
const COMPONENT_TO_FILE = {
  AppShell: 'shell.jsx', TweaksPanel: 'tweaks-panel.jsx', TweakSection: 'tweaks-panel.jsx',
  TweakRadio: 'tweaks-panel.jsx', TweakColor: 'tweaks-panel.jsx',
  OverviewScreen: 'overview.jsx', ProofsScreen: 'proofs.jsx', ScenariosScreen: 'scenarios.jsx',
  RunScreen: 'run.jsx', TelemetryScreen: 'telemetry.jsx', AgentsScreen: 'agents.jsx',
  LabScreen: 'lab.jsx', AuditScreen: 'audit.jsx', ChatScreen: 'chat.jsx',
  RoadmapScreen: 'roadmap.jsx', DiscoveryScreen: 'discovery.jsx', InspectorScreen: 'inspector.jsx',
  ControlRoomScreen: 'control.jsx', InteropScreen: 'interop.jsx',
  IntegrationsScreen: 'integrations.jsx', SubstrateScreen: 'substrate.jsx',
  CockpitScreen: 'cockpit.jsx', FlowScreen: 'flow.jsx',
  ConfigScreen: 'config.jsx', ModelsScreen: 'models.jsx', ToolkitsScreen: 'toolkits.jsx',
  ComposeScreen: 'compose.jsx', VerifyScreen: 'verify.jsx',
  CommandPalette: 'palette.jsx', ShortcutsModal: 'shortcuts.jsx',
  KeyboardNav: 'keyboard.jsx', IntroOverlay: 'intro.jsx',
};

async function forceLoad(file) {
  try {
    // OPHAMIN_ASSET_BASE is injected by the FastAPI /app route so the
    // fallback fetch resolves under /app/static/app/. Falls back to the
    // relative 'app/' when opened straight off disk (the design bundle).
    const res = await fetch((window.OPHAMIN_ASSET_BASE || 'app/') + file + '?fb=' + Date.now());
    if (!res.ok) return false;
    const src = await res.text();
    const out = window.Babel.transform(src, { presets: ['react'] }).code;
    (0, eval)(out);
    return true;
  } catch (e) {
    console.error('[ophamin] forceLoad failed for', file, e);
    return false;
  }
}

function _doMount() {
  // Reference ErrorBoundary defensively: under Babel-standalone each
  // script is eval'd separately, so a top-level `class` may not be in
  // this function's lexical scope at call time even though `function`
  // declarations leak to window. Fall back to window, then to a bare
  // App render, and surface any render error loudly rather than leaving
  // a blank screen.
  const Boundary =
    (typeof ErrorBoundary === 'function' && ErrorBoundary) ||
    (typeof window.ErrorBoundary === 'function' && window.ErrorBoundary) ||
    null;
  const AppComp = (typeof App === 'function' && App) || window.App;
  try {
    const tree = Boundary
      ? React.createElement(Boundary, null, React.createElement(AppComp))
      : React.createElement(AppComp);
    appRoot.render(tree);
  } catch (e) {
    console.error('[ophamin] render with boundary failed — retrying bare:', e);
    try {
      appRoot.render(React.createElement(AppComp));
    } catch (e2) {
      console.error('[ophamin] bare render also failed:', e2);
    }
  }
}

// Mount once components are available. Rather than a long 30ms×N poll
// (which setTimeout-throttling stretches to tens of seconds in a
// backgrounded tab), give one short grace for in-flight Babel-standalone
// transforms, then force-load whatever is still missing IN PARALLEL and
// render. Bounded to ~1 timer regardless of tab visibility.
async function mountWhenReady() {
  let missing = REQUIRED.filter(n => typeof window[n] !== 'function');
  if (missing.length) {
    await new Promise(r => setTimeout(r, 80));
    missing = REQUIRED.filter(n => typeof window[n] !== 'function');
  }
  if (missing.length) {
    const filesToLoad = [...new Set(missing.map(n => COMPONENT_TO_FILE[n]).filter(Boolean))];
    console.warn('[ophamin] babel-standalone missed', missing, '— force-loading', filesToLoad);
    await Promise.all(filesToLoad.map(forceLoad));
    const stillMissing = REQUIRED.filter(n => typeof window[n] !== 'function');
    if (stillMissing.length) console.error('[ophamin] still missing after force-load:', stillMissing);
  }
  _doMount();
}

// Boot in two phases:
//   1. Render with the grounded mock as soon as components are ready, so a
//      slow / down backend can't blank the screen. While in this state the
//      data is NOT real — a banner says so (see _setDataBanner).
//   2. Overlay live REST data in the background, then re-render in place.
//      On success the banner clears; on failure it becomes a loud, persistent
//      "SAMPLE DATA — backend unreachable" warning. The mock is NEVER silently
//      shown as real (was: a console.warn only — a no-fake violation).
function _setDataBanner(state) {
  // state: 'pending' (loading, subtle) | 'mock' (hydrate failed, loud) | 'live' (clear)
  const ID = 'ophamin-data-banner';
  let el = document.getElementById(ID);
  if (state === 'live') { if (el) el.remove(); document.body.style.removeProperty('padding-top'); return; }
  if (!el) {
    el = document.createElement('div');
    el.id = ID;
    el.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:100000;'
      + 'font:600 12px/1.4 -apple-system,BlinkMacSystemFont,system-ui,sans-serif;'
      + 'padding:7px 16px;text-align:center;letter-spacing:0.02em;';
    document.body.appendChild(el);
  }
  if (state === 'mock') {
    el.textContent = '⚠  SAMPLE DATA — the live backend is unreachable. Nothing shown here is real — not the proofs, verdicts, metrics, or counts.';
    el.style.background = '#7a1f1f';
    el.style.color = '#ffe2e2';
    document.body.style.paddingTop = '30px';
  } else { // pending — brief, while hydrate is in flight
    el.textContent = 'Loading live data… (showing placeholder until the backend responds)';
    el.style.background = '#222834';
    el.style.color = '#9fb0c8';
    document.body.style.paddingTop = '28px';
  }
}

mountWhenReady();
_setDataBanner('pending');
(async () => {
  try {
    if (!(window.OPHAMIN && typeof window.OPHAMIN.hydrate === 'function')) {
      _setDataBanner('mock');
      console.warn('[ophamin] no hydrate() — SAMPLE DATA banner shown; mock data is NOT real');
      return;
    }
    const live = await window.OPHAMIN.hydrate(window.OPHAMIN_API_BASE || '');
    if (live && Object.values(live).some(Boolean)) {
      _setDataBanner('live');
      mountWhenReady();
    } else {
      _setDataBanner('mock');
      console.warn('[ophamin] hydrate returned no live data — SAMPLE DATA banner shown; mock is NOT real');
    }
  } catch (e) {
    _setDataBanner('mock');
    console.warn('[ophamin] hydrate failed — SAMPLE DATA banner shown; mock data is NOT real', e);
  }
})();
