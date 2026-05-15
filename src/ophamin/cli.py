"""Ophamin command-line interface.

    ophamin demo                          run the end-to-end mock experiment
    ophamin run <config.yaml>             run one experiment from a base config
    ophamin sweep <experiment.yaml>       run a parameter sweep (parent + children)
    ophamin probe-kimera <repo>           self-test the Kimera adapter
    ophamin lineage --list                list recorded runs
    ophamin lineage <run-id>              show a run's lineage chain
    ophamin discover <repo>               mine Kimera's field-schema (Layer A)
    ophamin discover-diff <a.json> <b.json>  structural diff between two schema docs
    ophamin drift-report                  cross-Kimera-commit drift over proof records (Layer C)
    ophamin watch <repo>                  many-small-eyes: continuously re-discover + diff
                                          + drift on every Kimera HEAD change
    ophamin audit <path>                  orchestrate static-analysis pillars; signed audit record
    ophamin inventory <kimera-repo>       enumerate observable surface across 9 strata (static)
    ophamin discover-fields <kimera-repo> diff one probe cycle's raw fields vs KIMERA_FIELD_CATALOG
    ophamin scrape <url>                  passive scrape of a Prometheus /metrics endpoint
    ophamin wiring <kimera-repo>          per-surface wired vs WIRE_CANDIDATE vs orphan report
    ophamin report <record.json>          render a proof or audit record as HTML / Markdown / LaTeX
    ophamin inspect <kimera-repo> <name>  per-primitive profile (static + optional dynamic)
    ophamin inspect-all <kimera-repo>     survey every catalogued Kimera primitive
    ophamin export <record.json>          export a record to SARIF (audit) / JUnit XML (proof)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ophamin import __version__
from ophamin.config.sweep import SweepSpec, get_in, load_config, load_sweep
from ophamin.seeing.discovery import (
    DEFAULT_POLL_INTERVAL_S,
    KimeraDiscoveryWatcher,
    KimeraInventory,
    SchemaDocument,
    SchemaMiner,
    STRATA_DISCOVERERS,
    WatchOutcome,
    diff_schemas,
    discover_all,
    write_schema_markdown,
)
from ophamin.auditing import AuditRunner
from ophamin.auditing.pillars import DEFAULT_PILLAR_CLASSES
from ophamin.inspecting import PrimitiveInspector
from ophamin.interop import (
    CycloneDXExporter,
    JUnitXMLExporter,
    MLflowExporter,
    SARIFExporter,
)
from ophamin.reporting import ReportFormat, ReportRunner
from ophamin.comparing.drift import ProofIndex, detect_drift
from ophamin.comparing.orchestration.experiment import ExperimentRunner
from ophamin.comparing.provenance.lineage import LineageStore
from ophamin.seeing.substrate.field_catalog import (
    KIMERA_FIELD_CATALOG,
    catalog_coverage,
)
from ophamin.seeing.telemetry import (
    DEFAULT_PROMETHEUS_URL,
    DEFAULT_SCRAPE_TIMEOUT_S,
    PROMETHEUS_AVAILABLE,
    PrometheusScrapeProbe,
    TelemetryDependencyMissing,
    TelemetryScrapeError,
)
from ophamin.seeing.wiring import WiringProbe
from ophamin.seeing.substrate.kimera_adapter import KimeraAdapter, KimeraAdapterError
from ophamin.seeing.substrate.mock import MockSubstrate

#: default probe stimuli — small balanced text set covering several modalities
#: of input that Kimera should be able to process. Deliberately kept short and
#: hand-picked so the schema-mining stays cheap.
DEFAULT_DISCOVERY_STIMULI = [
    "The quarterly earnings report shows steady revenue growth across segments.",
    "Photosynthesis converts sunlight, water and CO2 into glucose.",
    "Reminder: the Tuesday status meeting will be at 3pm in conference room B.",
    "I disagree with the proposed changes. The risk assessment is inadequate.",
    "mm/slub: fix race condition in kmalloc_slab when CPU hot-unplug occurs.",
    "The boy went to the store and bought an apple.",
    "Memory is the deformation of the manifold by accumulated experience.",
    "Le garçon est allé au magasin.",
    "El niño fue a la tienda.",
    "少年は店に行った。",
]
DEFAULT_DISCOVERY_TARGETS = ("entity", "rosetta", "gwf", "arachne", "walker")


def build_substrate(config: dict):
    """Construct the substrate under test from a config's ``substrate`` block."""
    kind = get_in(config, "substrate.kind", "mock")
    if kind == "mock":
        return MockSubstrate(
            seed=int(get_in(config, "experiment.seed", 0)),
            collapse_cells=list(get_in(config, "substrate.collapse_cells", []) or []),
        )
    if kind == "kimera":
        repo = get_in(config, "substrate.kimera_repo", "")
        if not repo:
            raise SystemExit(
                "substrate.kimera_repo must be set when substrate.kind == 'kimera'"
            )
        python_exe = get_in(config, "substrate.kimera_python", "") or None
        try:
            return KimeraAdapter(repo, python_exe=python_exe)
        except KimeraAdapterError as exc:
            raise SystemExit(f"Kimera adapter could not be constructed: {exc}")
    raise SystemExit(f"unknown substrate.kind: {kind!r} (expected 'mock' or 'kimera')")


def cmd_demo(args: argparse.Namespace) -> int:
    """Run a small mock sweep end-to-end — no external system required."""
    base = {
        "experiment": {"cycles_per_run": 120, "warmup_cycles": 2, "seed": 20260514},
        "substrate": {"kind": "mock", "params": {}},
        "observability": {"spc": {"sigma_limit": 3.0}},
        "adaptive": {"msprt_mixing_variance": 1.0, "msprt_alpha": 0.05},
        "robustness": {"n_iterations": 150, "train_fraction": 0.7},
        "provenance": {"lineage_root": args.root},
    }
    sweep = SweepSpec(
        base_config=base,
        parent_name="ophamin-demo",
        parent_description="End-to-end mock experiment exercising all six pillars.",
        grid={
            "substrate.params.injection_rate": [0.1, 0.4, 0.7, 0.95],
            "substrate.params.immune_threshold": [0.45, 0.9],
        },
        stimuli=["alpha stimulus", "beta stimulus", "gamma stimulus"],
        diagnostics={"anticipatory_failure": True, "cognitive_inertia": True},
    )
    sut = MockSubstrate(seed=base["experiment"]["seed"])
    runner = ExperimentRunner(LineageStore(args.root))
    experiment = runner.run_sweep(sut, sweep)
    print(experiment.summary())
    print(f"\nlineage written to: {args.root}/")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    sut = build_substrate(config)
    lineage = LineageStore(get_in(config, "provenance.lineage_root", args.root))
    runner = ExperimentRunner(lineage)
    stimuli = args.stimuli.split(",") if args.stimuli else [None]
    result = runner.run_single(sut, config, stimuli=stimuli)
    print(f"run {result.run_id}  ({result.n_cycles} cycles)")
    for pillar in result.pillars:
        print(f"  {pillar.pillar:<18} [{pillar.status}] {pillar.summary}")
    print(f"\nlineage written to: {lineage.root}/{result.run_id}/")
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    sweep = load_sweep(args.config)
    sut = build_substrate(sweep.base_config)
    lineage = LineageStore(
        get_in(sweep.base_config, "provenance.lineage_root", args.root)
    )
    runner = ExperimentRunner(lineage)
    experiment = runner.run_sweep(sut, sweep)
    print(experiment.summary())
    print(f"\nlineage written to: {lineage.root}/")
    return 0


def cmd_probe_kimera(args: argparse.Namespace) -> int:
    try:
        adapter = KimeraAdapter(args.repo, python_exe=args.python or None)
    except KimeraAdapterError as exc:
        print(f"adapter misconfigured: {exc}", file=sys.stderr)
        return 2
    report = adapter.probe()
    print(json.dumps(report, indent=2))
    return 0 if report.get("runner_ok") and report.get("takwin_construct_ok") else 1


def cmd_lineage(args: argparse.Namespace) -> int:
    store = LineageStore(args.root)
    if args.list or not args.run_id:
        runs = store.list_runs()
        if not runs:
            print(f"(no runs recorded in {store.root})")
            return 0
        for run_id in runs:
            record = store.get_run(run_id)
            parent = record.parent_run_id or "-"
            print(f"{run_id}  parent={parent}  substrate={record.substrate_git_commit}")
        return 0
    chain = store.lineage_of(args.run_id)
    for depth, record in enumerate(chain):
        indent = "  " * depth
        print(f"{indent}{record.run_id}")
        print(f"{indent}  created   : {record.manifest.get('created_at')}")
        print(f"{indent}  substrate : {record.manifest.get('substrate', {}).get('name')} "
              f"@ {record.substrate_git_commit or '(no commit)'}")
        print(f"{indent}  config#   : {record.config_hash[:12]}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    """Mine Kimera's field-schema (Layer A of the co-evolution stack).

    Produces a SchemaDocument JSON + a human-readable Markdown reference
    pinned to the Kimera + Ophamin git commits and the stimulus-set content
    hash.
    """
    targets = (
        [t.strip() for t in args.targets.split(",") if t.strip()]
        if args.targets
        else list(DEFAULT_DISCOVERY_TARGETS)
    )
    stimuli = list(DEFAULT_DISCOVERY_STIMULI)
    if args.stimuli_file:
        stimuli = [
            line for line in Path(args.stimuli_file).read_text().splitlines() if line
        ]
    # we construct the adapter against the first target; SchemaMiner
    # re-constructs per-target so the targets list can be heterogeneous.
    try:
        substrate = KimeraAdapter(
            args.repo,
            target=targets[0],
            mode="batch",
            batch_timeout=float(args.batch_timeout),
        )
    except KimeraAdapterError as exc:
        print(f"adapter misconfigured: {exc}", file=sys.stderr)
        return 2
    miner = SchemaMiner(substrate)
    print(f"discovering Kimera field-schema: {len(targets)} targets × "
          f"{len(stimuli)} stimuli ...")
    doc = miner.mine(targets=targets, stimuli=stimuli)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    short_commit = (doc.kimera_git_commit or "unknown")[:12]
    json_path = out_dir / f"kimera_fields_{short_commit}.json"
    md_path = out_dir / f"kimera_fields_{short_commit}.md"
    doc.to_json(json_path)
    write_schema_markdown(doc, md_path)
    print(f"kimera commit  : {doc.kimera_git_commit}")
    print(f"targets probed : {', '.join(t.name for t in doc.targets)}")
    for t in doc.targets:
        print(f"  {t.name:<10} fields: {len(t.fields):>3}  cycles: {t.n_cycles}  "
              f"adapter_errors: {t.n_adapter_errors}")
    print(f"written        : {json_path}")
    print(f"                 {md_path}")
    return 0


def cmd_drift_report(args: argparse.Namespace) -> int:
    """Cross-Kimera-commit drift over signed Empirical Proof Records (Layer C).

    Loads every proof record under ``--proofs-dir`` (default ``proofs/``),
    groups by primary statistic name, and computes Wilson-CI-based drift
    between the oldest-commit and newest-commit measurement for each
    statistic. Statistics with only one Kimera commit are reported as
    ``status="single_commit"``.
    """
    proofs_dir = Path(args.proofs_dir)
    if not proofs_dir.is_dir():
        print(f"proofs directory not found: {proofs_dir}", file=sys.stderr)
        return 2
    index = ProofIndex.from_directory(proofs_dir)
    if not index.statistic_names():
        print(f"no signed proof records found under {proofs_dir}")
        return 0
    report = detect_drift(index)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0
    print(f"proofs indexed: {len(index)} from {proofs_dir}")
    print(f"distinct primary statistics: {len(report)}")
    print()
    significant_count = 0
    for stat, entry in report.items():
        if "status" in entry and entry["status"] == "single_commit":
            print(f"  {stat:<50} status: single_commit  "
                  f"(commit={entry['commit'][:12]}, n_records={entry['n_records']})")
            continue
        primary = entry["primary_delta"]
        sig = "⚠ DRIFT" if entry.get("has_significant_drift") else "ok"
        if entry.get("has_significant_drift"):
            significant_count += 1
        commit_before = entry["kimera_commit_before"][:12]
        commit_after = entry["kimera_commit_after"][:12]
        print(f"  {stat:<50} {sig}  "
              f"{primary['value_before']:.4f} → {primary['value_after']:.4f}  "
              f"(Δ={primary['delta']:+.4f})  "
              f"commits: {commit_before} → {commit_after}")
        if entry.get("verdict_changed"):
            print(f"      verdict flip: {entry['verdict_before']} → {entry['verdict_after']}")
    print()
    print(f"significant drift events: {significant_count}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Many-small-eyes mode — continuously re-discover + diff + drift on every
    Kimera HEAD change.

    Polls the Kimera repository's git HEAD at ``--poll-interval`` seconds. On
    a new commit, mines the field schema, writes the Markdown reference,
    diffs against the previous schema, and refreshes the drift report. The
    output is a dated artefact directory per commit.
    """
    targets = (
        [t.strip() for t in args.targets.split(",") if t.strip()]
        if args.targets
        else list(DEFAULT_DISCOVERY_TARGETS)
    )
    stimuli = list(DEFAULT_DISCOVERY_STIMULI)
    if args.stimuli_file:
        stimuli = [
            line for line in Path(args.stimuli_file).read_text().splitlines() if line
        ]
    watcher = KimeraDiscoveryWatcher(
        kimera_repo=args.repo,
        targets=targets,
        stimuli=stimuli,
        out_dir=args.out_dir,
        proofs_dir=args.proofs_dir,
        batch_timeout=float(args.batch_timeout),
    )

    def _report(outcome: WatchOutcome) -> None:
        if outcome.new_commit_discovered:
            print(
                f"[{outcome.kimera_commit[:12]}] {outcome.reason}; "
                f"schema={outcome.schema_md_path} "
                + (f"diff={outcome.diff_md_path} " if outcome.diff_md_path else "")
                + (f"drift={outcome.drift_path}" if outcome.drift_path else "")
            )
        else:
            print(f"[poll] {outcome.reason}")

    if args.once:
        outcome = watcher.run_once()
        _report(outcome)
        return 0 if outcome.kimera_commit else 1
    print(f"watching Kimera HEAD at {args.repo}; polling every {args.poll_interval}s...")
    watcher.run_forever(
        poll_interval_s=float(args.poll_interval),
        on_outcome=_report,
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Render a proof or audit record as HTML / Markdown / LaTeX.

    The record kind (proof vs audit) is auto-detected from the JSON shape.
    Output file extension is set by the chosen format. Charts go to an
    adjacent ``assets/`` dir for Markdown / LaTeX outputs.
    """
    record_path = Path(args.record)
    if not record_path.is_file():
        print(f"record not found: {record_path}", file=sys.stderr)
        return 2
    try:
        fmt = ReportFormat(args.format)
    except ValueError:
        print(
            f"unknown format {args.format!r}; choose from "
            f"{', '.join(f.value for f in ReportFormat)}",
            file=sys.stderr,
        )
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / record_path.stem  # extension chosen by renderer

    runner = ReportRunner()
    try:
        out_path = runner.render(record_path, out_stem, fmt)
    except ValueError as exc:
        print(f"render failed: {exc}", file=sys.stderr)
        return 1
    print(f"record  : {record_path}")
    print(f"format  : {fmt.value}")
    print(f"written : {out_path}")
    if fmt in (ReportFormat.MARKDOWN, ReportFormat.LATEX):
        assets = out_path.parent / "assets"
        if assets.is_dir():
            n = len(list(assets.glob("*.png")))
            print(f"         + {n} chart PNG(s) in {assets}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export a signed Ophamin record to a standard interop format.

    Audit records → SARIF 2.1.0 (consumed by VS Code Problems pane, GitHub
    code-scanning, GitLab CI security panel, any SARIF-aware tool).

    Proof records → JUnit XML (consumed by every CI's test-result aggregator
    — GitHub Actions, GitLab CI, CircleCI, Jenkins).
    """
    record_path = Path(args.record)
    if not record_path.is_file():
        print(f"record not found: {record_path}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(record_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"record is not valid JSON: {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.output) if args.output else None
    fmt = args.format.lower()

    if fmt == "sarif":
        if "audit_id" not in payload:
            print(
                "--format=sarif requires an Audit Record (got something without "
                "'audit_id'); use --format=junit-xml for proof records",
                file=sys.stderr,
            )
            return 2
        out = SARIFExporter().export(
            payload, out_path or record_path.with_suffix(".sarif")
        )
        print(f"record  : {record_path}")
        print(f"format  : {fmt}")
        print(f"written : {out}")
        return 0
    elif fmt in ("junit", "junit-xml"):
        if "claim" not in payload or "verdict" not in payload:
            print(
                "--format=junit-xml requires an Empirical Proof Record "
                "(missing 'claim' and/or 'verdict'); use --format=sarif for audit records",
                file=sys.stderr,
            )
            return 2
        out = JUnitXMLExporter().export(
            payload, out_path or record_path.with_suffix(".xml")
        )
        print(f"record  : {record_path}")
        print(f"format  : {fmt}")
        print(f"written : {out}")
        return 0
    elif fmt in ("cyclonedx", "sbom"):
        # CycloneDX SBOM — either from the record's reproduction.environment
        # (when it carries one) or from the current venv as a fallback.
        try:
            reproduction = (payload.get("reproduction") or {}) if isinstance(payload, dict) else {}
            if reproduction.get("environment"):
                out = CycloneDXExporter().export_record(
                    payload,
                    out_path or record_path.with_suffix(".cdx.json"),
                )
            else:
                # record has no environment lock; emit the current venv's SBOM
                out = CycloneDXExporter().export_env(
                    out_path or record_path.with_suffix(".cdx.json"),
                )
        except ValueError as exc:
            print(f"cyclonedx export failed: {exc}", file=sys.stderr)
            return 2
        print(f"record  : {record_path}")
        print(f"format  : cyclonedx")
        print(f"written : {out}")
        return 0
    elif fmt == "mlflow":
        # MLflow exporter writes to a tracking server (default file:./mlruns)
        # rather than a file — return the run_id instead of an output path.
        try:
            exporter = MLflowExporter(
                tracking_uri=args.tracking_uri or None,
                experiment_name=args.experiment_name or None,
            )
            run_id = exporter.export(payload)
        except ImportError as exc:
            print(f"mlflow not available: {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"mlflow export failed: {exc}", file=sys.stderr)
            return 2
        print(f"record       : {record_path}")
        print(f"format       : mlflow")
        print(f"run_id       : {run_id}")
        if args.tracking_uri:
            print(f"tracking uri : {args.tracking_uri}")
        return 0
    else:
        print(
            f"unknown format {args.format!r}; choose from: sarif, junit-xml, mlflow",
            file=sys.stderr,
        )
        return 2


def cmd_inspect(args: argparse.Namespace) -> int:
    """Per-primitive profile (static introspection + optional dynamic).

    Reads the Kimera source tree to extract the primitive's docstring,
    methods, parent classes, imports, and caller count. Optional flags
    add Layer A schema discovery (``--with-discovery``) and a single-file
    static audit (``--with-audit``).
    """
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"kimera repo not found: {repo}", file=sys.stderr)
        return 2
    try:
        inspector = PrimitiveInspector(repo)
    except NotADirectoryError as exc:
        print(f"inspector failed: {exc}", file=sys.stderr)
        return 2
    profile = inspector.inspect(
        args.primitive,
        with_discovery=args.with_discovery,
        with_audit=args.with_audit,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"primitive_{profile.canonical_class}"
    profile.to_json(str(base.with_suffix(".json")))
    profile.to_markdown(str(base.with_suffix(".md")))
    print(f"primitive       : {profile.name}")
    print(f"canonical class : {profile.canonical_class}")
    print(f"family          : {', '.join(profile.family_tags) or '(unclassified)'}")
    if profile.source_file:
        print(f"located         : {profile.source_file}:{profile.source_line}")
    else:
        print(f"located         : NOT FOUND in source tree")
    print(f"methods         : {len(profile.method_names)}")
    print(f"callers         : {profile.n_callers}")
    if profile.discovery_field_count is not None:
        print(f"discovery       : {profile.discovery_field_count} field paths")
    if profile.audit_finding_count is not None:
        print(f"audit findings  : {profile.audit_finding_count}")
    if profile.notes:
        print(f"notes           :")
        for n in profile.notes:
            print(f"  - {n}")
    print(f"written         : {base.with_suffix('.json')}")
    print(f"                  {base.with_suffix('.md')}")
    return 0


def cmd_inspect_all(args: argparse.Namespace) -> int:
    """Survey every catalogued primitive against the given Kimera repo.

    Produces a JSON array of profiles + a Markdown summary table. Optional
    flags add dynamic readings (slower).
    """
    repo = Path(args.repo)
    if not repo.is_dir():
        print(f"kimera repo not found: {repo}", file=sys.stderr)
        return 2
    inspector = PrimitiveInspector(repo)
    profiles = inspector.inspect_all(
        with_discovery=args.with_discovery,
        with_audit=args.with_audit,
        family_filter=args.family or None,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON array of profiles
    json_path = out_dir / "primitives_survey.json"
    json_path.write_text(
        json.dumps([p.to_dict() for p in profiles], indent=2, default=str),
        encoding="utf-8",
    )

    # Markdown summary table
    md_path = out_dir / "primitives_survey.md"
    lines = [
        "# Kimera primitives — survey\n",
        f"**Kimera repo:** `{repo.resolve()}`  ",
        f"**Kimera commit:** `{inspector.kimera_commit[:12]}`  ",
        f"**Primitives surveyed:** {len(profiles)}\n",
        "| name | class | family | located | methods | callers |",
        "|---|---|---|---|---|---|",
    ]
    for p in profiles:
        loc = (
            f"`{p.source_file}:{p.source_line}`" if p.source_file
            else "_not found_"
        )
        lines.append(
            f"| {p.name} | `{p.canonical_class}` | "
            f"{', '.join(p.family_tags)} | {loc} | "
            f"{len(p.method_names)} | {p.n_callers} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    n_located = sum(1 for p in profiles if p.source_file)
    print(f"primitives surveyed : {len(profiles)}")
    print(f"located in source    : {n_located} / {len(profiles)}")
    print(f"missing in source    : {len(profiles) - n_located}")
    print(f"written              : {json_path}")
    print(f"                       {md_path}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Orchestrate static-analysis pillars against a target path.

    Each pillar wraps one external tool (ruff, bandit, mypy, vulture, radon,
    pip-audit). Tools that aren't installed report ``status="unavailable"``;
    the rest run and contribute findings to a signed AuditRecord.
    """
    target = Path(args.target)
    if not target.exists():
        print(f"target does not exist: {target}", file=sys.stderr)
        return 2
    # filter pillars by --pillars list if given
    pillar_classes = list(DEFAULT_PILLAR_CLASSES)
    if args.pillars:
        wanted = {name.strip() for name in args.pillars.split(",") if name.strip()}
        pillar_classes = [cls for cls in pillar_classes if cls.name in wanted]
        if not pillar_classes:
            print(f"no pillars match --pillars={args.pillars}", file=sys.stderr)
            return 2
    runner = AuditRunner(pillars=[cls() for cls in pillar_classes])
    print(f"auditing: {target}")
    print(f"pillars : {', '.join(p.name for p in runner.pillars)}")
    print(f"          ({len(runner.available_pillars())} available locally)")
    record = runner.run(target, timeout_s=float(args.timeout))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    short = record.audit_id[:16]
    json_path = out_dir / f"audit_{short}.json"
    md_path = out_dir / f"audit_{short}.md"
    record.to_json(str(json_path))
    record.to_markdown(str(md_path))

    s = record.summary
    print(f"\nsummary:")
    print(f"  total findings  : {s.total_findings}")
    print(f"  pillars run     : {len(s.pillars_run)} "
          f"({', '.join(s.pillars_run) or '—'})")
    if s.pillars_unavailable:
        print(f"  pillars missing : {len(s.pillars_unavailable)} "
              f"({', '.join(s.pillars_unavailable)})")
    if s.pillars_errored:
        print(f"  pillars errored : {len(s.pillars_errored)} "
              f"({', '.join(s.pillars_errored)})")
    if s.severity_histogram:
        print(f"  severities      : ", end="")
        print(", ".join(f"{sev}={n}" for sev, n in sorted(
            s.severity_histogram.items(), key=lambda kv: -kv[1]
        )))
    if s.findings_per_pillar:
        print(f"  per pillar      : ", end="")
        print(", ".join(f"{p}={n}" for p, n in sorted(s.findings_per_pillar.items())))
    if s.top_files:
        print(f"  top hotspots    :")
        for path, n in s.top_files[:5]:
            print(f"    {n:>4}  {path}")
    print(f"\nwritten         : {json_path}")
    print(f"                  {md_path}")
    return 0


def cmd_inventory(args: argparse.Namespace) -> int:
    """Enumerate Kimera's observable surface across all 9 strata.

    Pure static analysis — does NOT execute Kimera. Reads the Kimera repo at
    the given path and emits a signed, content-addressed inventory JSON +
    Markdown. Each stratum's discoverer is independent; a stratum with zero
    surfaces is reported as ``dormant`` rather than as an error.
    """
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"kimera repo path is not a directory: {repo}", file=sys.stderr)
        return 2

    strata: tuple[str, ...] | None = None
    if args.strata:
        strata = tuple(s.strip() for s in args.strata.split(",") if s.strip())
        unknown = set(strata) - set(STRATA_DISCOVERERS)
        if unknown:
            print(f"unknown strata: {sorted(unknown)}", file=sys.stderr)
            print(f"valid strata  : {sorted(STRATA_DISCOVERERS)}", file=sys.stderr)
            return 2

    print(f"inventorying    : {repo}")
    inv = discover_all(repo, strata=strata)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    short = inv.inventory_id[:16]
    json_path = out_dir / f"inventory_{short}.json"
    md_path = out_dir / f"inventory_{short}.md"
    inv.to_json(str(json_path))
    inv.to_markdown(str(md_path))

    print(f"\nkimera commit   : {inv.kimera_git_commit or '(not a git repo)'}")
    print(f"total surfaces  : {inv.total_surfaces()}")
    print(f"live strata     : {len(inv.live_strata())}/{len(inv.strata)}")
    print(f"\nper-stratum coverage:")
    for s in inv.strata:
        status = "live" if s.is_live else "dormant"
        print(f"  {s.stratum:<16} {s.count:>4}  ({status}, expected ≥ {s.expected_count})")
    if inv.dormant_strata():
        print(f"\ndormant strata  : {', '.join(inv.dormant_strata())}")
    print(f"\nwritten         : {json_path}")
    print(f"                  {md_path}")
    return 0


def cmd_discover_fields(args: argparse.Namespace) -> int:
    """Probe Kimera one cycle, diff the resulting raw dict against the field catalog.

    Three buckets are reported:

    - **in_catalog**       — fields present in raw AND documented in the catalog
    - **uncataloged**      — fields present in raw but NOT in the catalog (Kimera
                              added them; consider extending the catalog)
    - **missing_from_raw** — catalog fields not present in this probe's raw (the
                              substrate may not surface them for this target /
                              stimulus, or Kimera renamed them)

    The third bucket is the load-bearing one — it surfaces Kimera-side drift
    that would silently break scenarios depending on those fields.
    """
    try:
        adapter = KimeraAdapter(args.repo, target=args.target)
    except KimeraAdapterError as e:
        print(f"adapter error: {e}", file=sys.stderr)
        return 2

    try:
        result = adapter.run_cycle(args.stimulus)
    except Exception as e:
        print(f"probe cycle failed: {e}", file=sys.stderr)
        return 1

    coverage = catalog_coverage(result.raw)
    if args.json:
        out = {
            "ophamin_version": __version__,
            "kimera_repo": str(args.repo),
            "target": args.target,
            "halt_mode": result.halt_mode,
            "success": result.success,
            "coverage": coverage,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(f"probing         : {args.repo}")
    print(f"target          : {args.target}")
    print(f"halt_mode       : {result.halt_mode}")
    print(f"catalog size    : {coverage['catalog_size']}")
    print(f"raw dict size   : {coverage['raw_size']}")
    print(f"")
    print(f"in catalog      : {coverage['in_catalog']} fields documented + present")
    print(f"uncataloged     : {coverage['uncataloged']} fields present but not in catalog")
    print(f"missing from raw: {coverage['missing_from_raw']} catalog fields absent this run")
    if coverage["missing_from_raw_names"]:
        print(f"\nmissing fields (catalog → raw drift):")
        for name in coverage["missing_from_raw_names"][:20]:
            print(f"  - {name}")
        if len(coverage["missing_from_raw_names"]) > 20:
            print(f"  ... and {len(coverage['missing_from_raw_names']) - 20} more")
    if coverage["uncataloged_names"]:
        print(f"\nuncataloged fields (raw → catalog drift):")
        for name in coverage["uncataloged_names"][:20]:
            print(f"  - {name}")
        if len(coverage["uncataloged_names"]) > 20:
            print(f"  ... and {len(coverage['uncataloged_names']) - 20} more")
    return 0


def cmd_wiring(args: argparse.Namespace) -> int:
    """Run the wiring probe against a Kimera repo, write a signed completeness report.

    The action list (per-stratum orphans + WIRE_CANDIDATEs) drives substrate-
    completion work. The report covers nine strata; only ``wired``,
    ``wire_candidate``, ``orphan``, ``archived``, and ``parse_error``
    classifications are reported (``config`` non-Python surfaces are
    excluded from the wiring contract).
    """
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"kimera repo path is not a directory: {repo}", file=sys.stderr)
        return 2

    if args.scan_all:
        print(f"scanning all    : {repo}/kimera_swm/")
        report = WiringProbe(repo).scan_all()
        print(f"classified      : {report.total_surfaces()} Python modules "
              f"(repo-wide scan, not inventory-only)")
    else:
        print(f"inventorying    : {repo}")
        inventory = discover_all(repo)
        print(f"building graph  : {inventory.total_surfaces()} surfaces")
        report = WiringProbe(repo).probe(inventory)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    short = report.report_id[:16]
    json_path = out_dir / f"wiring_{short}.json"
    md_path = out_dir / f"wiring_{short}.md"
    report.to_json(str(json_path))
    report.to_markdown(str(md_path))

    print()
    print(f"{'stratum':<16} {'total':>6} {'wired':>6} {'wc':>4} {'orphan':>7} "
          f"{'arch':>5} {'perr':>5} {'wired%':>7} {'orph%':>7}")
    for s in report.per_stratum:
        print(f"{s.stratum:<16} {s.n_total:>6} {s.n_wired:>6} {s.n_wire_candidate:>4} "
              f"{s.n_orphan:>7} {s.n_archived:>5} {s.n_parse_error:>5} "
              f"{s.wired_rate*100:>6.1f}% {s.orphan_rate*100:>6.1f}%")
    print()
    orphans = report.orphan_surfaces()
    wc = report.wire_candidate_surfaces()
    print(f"orphan surfaces         : {len(orphans)}")
    print(f"WIRE_CANDIDATE surfaces : {len(wc)}")
    if orphans:
        print(f"\norphan action list (first 10):")
        for s in orphans[:10]:
            print(f"  [{s.stratum:<14}] {s.file_path}")
        if len(orphans) > 10:
            print(f"  ... and {len(orphans) - 10} more in {md_path}")
    print(f"\nwritten         : {json_path}")
    print(f"                  {md_path}")
    return 0


def cmd_scrape(args: argparse.Namespace) -> int:
    """Passive scrape of a Prometheus /metrics endpoint, write a signed snapshot."""
    if not PROMETHEUS_AVAILABLE:
        print(
            "prometheus_client is not installed.\n"
            "Install with: pip install 'ophamin[telemetry]'",
            file=sys.stderr,
        )
        return 2
    try:
        probe = PrometheusScrapeProbe(
            url=args.url,
            timeout_s=args.timeout,
            ophamin_version=__version__,
        )
    except TelemetryDependencyMissing as e:
        print(f"telemetry dep missing: {e}", file=sys.stderr)
        return 2

    print(f"scraping        : {args.url}")
    try:
        snap = probe.scrape()
    except TelemetryScrapeError as e:
        print(f"scrape failed: {e}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    short = snap.snapshot_id[:16]
    json_path = out_dir / f"telemetry_{short}.json"
    snap.to_json(str(json_path))

    print(f"\nwall time       : {snap.wall_time_s:.3f}s")
    print(f"raw payload     : {snap.raw_bytes_len} bytes")
    print(f"families        : {len(snap.families)}")
    print(f"total samples   : {snap.total_samples()}")
    if snap.families and args.top > 0:
        ranked = sorted(
            snap.families, key=lambda f: -f.sample_count()
        )[: args.top]
        print(f"\ntop {len(ranked)} families by sample count:")
        for f in ranked:
            print(f"  {f.sample_count():>4}  {f.name:<40}  ({f.metric_type})")
    print(f"\nwritten         : {json_path}")
    return 0


def cmd_discover_diff(args: argparse.Namespace) -> int:
    """Structural diff between two SchemaDocuments (added/removed/type-changed)."""
    before = SchemaDocument.from_json(args.before)
    after = SchemaDocument.from_json(args.after)
    diff = diff_schemas(before, after)
    if args.json:
        print(json.dumps(diff.to_dict(), indent=2))
    else:
        print(f"before kimera commit : {before.kimera_git_commit}")
        print(f"after  kimera commit : {after.kimera_git_commit}")
        if diff.is_empty():
            print("no structural changes between the two schemas")
            return 0
        if diff.targets_added:
            print(f"targets added   : {', '.join(diff.targets_added)}")
        if diff.targets_removed:
            print(f"targets removed : {', '.join(diff.targets_removed)}")
        for change in diff.field_changes:
            if change.kind == "added":
                print(f"  + [{change.target}] {change.path} "
                      f"({', '.join(change.types_after)})")
            elif change.kind == "removed":
                print(f"  - [{change.target}] {change.path} "
                      f"({', '.join(change.types_before)})")
            elif change.kind == "type_changed":
                print(f"  ~ [{change.target}] {change.path} "
                      f"{', '.join(change.types_before)} -> "
                      f"{', '.join(change.types_after)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ophamin",
        description="Ophamin — empirical framework for iterative experimentation.",
    )
    parser.add_argument("--version", action="version", version=f"ophamin {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="run the end-to-end mock experiment")
    p_demo.add_argument("--root", default="runs", help="lineage store directory")
    p_demo.set_defaults(func=cmd_demo)

    p_run = sub.add_parser("run", help="run one experiment from a base config")
    p_run.add_argument("config", help="path to a base config YAML")
    p_run.add_argument("--root", default="runs", help="lineage store directory")
    p_run.add_argument("--stimuli", default="", help="comma-separated stimuli")
    p_run.set_defaults(func=cmd_run)

    p_sweep = sub.add_parser("sweep", help="run a parameter sweep")
    p_sweep.add_argument("config", help="path to a sweep YAML (experiment_vars.yaml)")
    p_sweep.add_argument("--root", default="runs", help="lineage store directory")
    p_sweep.set_defaults(func=cmd_sweep)

    p_probe = sub.add_parser("probe-kimera", help="self-test the Kimera adapter")
    p_probe.add_argument("repo", help="path to the Kimera-SWM repository")
    p_probe.add_argument("--python", default="", help="path to the Kimera venv python")
    p_probe.set_defaults(func=cmd_probe_kimera)

    p_lin = sub.add_parser("lineage", help="inspect the lineage store")
    p_lin.add_argument("run_id", nargs="?", default="", help="run id to trace")
    p_lin.add_argument("--list", action="store_true", help="list all recorded runs")
    p_lin.add_argument("--root", default="runs", help="lineage store directory")
    p_lin.set_defaults(func=cmd_lineage)

    p_disc = sub.add_parser(
        "discover",
        help="mine Kimera's field-schema (Layer A of the co-evolution stack)",
    )
    p_disc.add_argument("repo", help="path to the Kimera-SWM repository")
    p_disc.add_argument(
        "--targets",
        default="",
        help=(
            "comma-separated Kimera targets to probe "
            f"(default: {','.join(DEFAULT_DISCOVERY_TARGETS)})"
        ),
    )
    p_disc.add_argument(
        "--stimuli-file",
        default="",
        help="optional newline-separated file of probe stimuli "
        "(default: the built-in balanced text set)",
    )
    p_disc.add_argument(
        "--out-dir",
        default="discovery",
        help="directory to write the schema JSON + Markdown",
    )
    p_disc.add_argument(
        "--batch-timeout",
        default="600",
        help="adapter batch timeout in seconds (default: 600)",
    )
    p_disc.set_defaults(func=cmd_discover)

    p_dd = sub.add_parser(
        "discover-diff",
        help="structural diff between two schema documents (added/removed/type-changed)",
    )
    p_dd.add_argument("before", help="path to the older SchemaDocument JSON")
    p_dd.add_argument("after", help="path to the newer SchemaDocument JSON")
    p_dd.add_argument("--json", action="store_true", help="emit the diff as JSON")
    p_dd.set_defaults(func=cmd_discover_diff)

    p_drift = sub.add_parser(
        "drift-report",
        help="cross-Kimera-commit drift over signed proof records (Layer C)",
    )
    p_drift.add_argument(
        "--proofs-dir",
        default="proofs",
        help="directory containing signed Empirical Proof Records (default: proofs/)",
    )
    p_drift.add_argument("--json", action="store_true", help="emit the report as JSON")
    p_drift.set_defaults(func=cmd_drift_report)

    p_watch = sub.add_parser(
        "watch",
        help=(
            "many-small-eyes mode: continuously re-discover + diff + drift on "
            "every Kimera HEAD change"
        ),
    )
    p_watch.add_argument("repo", help="path to the Kimera-SWM repository")
    p_watch.add_argument(
        "--targets", default="",
        help=f"comma-separated Kimera targets to probe "
             f"(default: {','.join(DEFAULT_DISCOVERY_TARGETS)})",
    )
    p_watch.add_argument(
        "--stimuli-file", default="",
        help="optional newline-separated file of probe stimuli",
    )
    p_watch.add_argument(
        "--out-dir", default="discovery",
        help="directory to write schema + diff + drift artefacts",
    )
    p_watch.add_argument(
        "--proofs-dir", default="proofs",
        help="directory containing signed proof records (for drift refresh)",
    )
    p_watch.add_argument(
        "--batch-timeout", default="600",
        help="adapter batch timeout per discovery tick (default: 600s)",
    )
    p_watch.add_argument(
        "--poll-interval", default=str(DEFAULT_POLL_INTERVAL_S),
        help=f"seconds between HEAD checks (default: {DEFAULT_POLL_INTERVAL_S}s)",
    )
    p_watch.add_argument(
        "--once", action="store_true",
        help="run a single tick (mine if HEAD changed) and exit, instead of looping",
    )
    p_watch.set_defaults(func=cmd_watch)

    p_audit = sub.add_parser(
        "audit",
        help="orchestrate static-analysis pillars against a target path",
    )
    p_audit.add_argument("target", help="path to audit (directory or file)")
    p_audit.add_argument(
        "--pillars",
        default="",
        help=(
            "comma-separated subset of pillar names "
            f"(default: all; available: {','.join(cls.name for cls in DEFAULT_PILLAR_CLASSES)})"
        ),
    )
    p_audit.add_argument(
        "--out-dir",
        default="audits",
        help="directory to write the audit JSON + Markdown (default: audits/)",
    )
    p_audit.add_argument(
        "--timeout",
        default="600",
        help="per-pillar timeout in seconds (default: 600)",
    )
    p_audit.set_defaults(func=cmd_audit)

    p_inv = sub.add_parser(
        "inventory",
        help="enumerate Kimera's observable surface across all 9 strata "
             "(static analysis — no Kimera execution required)",
    )
    p_inv.add_argument("repo", help="path to the Kimera-SWM repository")
    p_inv.add_argument(
        "--strata", default="",
        help="comma-separated subset of strata to discover (default: all 9). "
             f"Valid: {','.join(sorted(STRATA_DISCOVERERS))}",
    )
    p_inv.add_argument(
        "--out-dir", default="inventory",
        help="directory to write the inventory JSON + Markdown (default: inventory/)",
    )
    p_inv.set_defaults(func=cmd_inventory)

    p_fields = sub.add_parser(
        "discover-fields",
        help="probe Kimera one cycle, diff the resulting OrchestratorResult "
             "field set against KIMERA_FIELD_CATALOG (surfaces field drift)",
    )
    p_fields.add_argument("repo", help="path to the Kimera-SWM repository")
    p_fields.add_argument(
        "--target", default="entity",
        help="adapter target to probe (default: entity)",
    )
    p_fields.add_argument(
        "--stimulus", default="Probe stimulus for catalog drift detection.",
        help="stimulus text for the probe cycle",
    )
    p_fields.add_argument(
        "--json", action="store_true",
        help="emit machine-readable JSON instead of the text summary",
    )
    p_fields.set_defaults(func=cmd_discover_fields)

    p_scrape = sub.add_parser(
        "scrape",
        help="passive scrape of a Prometheus /metrics endpoint (e.g. Kimera's "
             "exporter) → signed PrometheusSnapshot",
    )
    p_scrape.add_argument(
        "url", nargs="?", default=DEFAULT_PROMETHEUS_URL,
        help=f"endpoint to scrape (default: {DEFAULT_PROMETHEUS_URL})",
    )
    p_scrape.add_argument(
        "--timeout", type=float, default=DEFAULT_SCRAPE_TIMEOUT_S,
        help=f"scrape timeout in seconds (default: {DEFAULT_SCRAPE_TIMEOUT_S})",
    )
    p_scrape.add_argument(
        "--out-dir", default="telemetry",
        help="directory to write the snapshot JSON (default: telemetry/)",
    )
    p_scrape.add_argument(
        "--top", type=int, default=10,
        help="number of top metric families to print (by sample count, default: 10)",
    )
    p_scrape.set_defaults(func=cmd_scrape)

    p_wiring = sub.add_parser(
        "wiring",
        help="empirical wiring report — per-surface wired vs WIRE_CANDIDATE "
             "vs orphan classification (no Kimera execution required)",
    )
    p_wiring.add_argument("repo", help="path to the Kimera-SWM repository")
    p_wiring.add_argument(
        "--out-dir", default="wiring",
        help="directory to write the report JSON + Markdown (default: wiring/)",
    )
    p_wiring.add_argument(
        "--all", dest="scan_all", action="store_true",
        help="scan every .py file under kimera_swm/ — not just the ~336 "
             "named primitive surfaces in KimeraInventory (broader picture, "
             "slower run)",
    )
    p_wiring.set_defaults(func=cmd_wiring)

    p_report = sub.add_parser(
        "report",
        help="render a signed record (proof or audit) as HTML / Markdown / LaTeX",
    )
    p_report.add_argument("record", help="path to a signed record JSON")
    p_report.add_argument(
        "--format", default="html",
        choices=[f.value for f in ReportFormat
                 if f not in (ReportFormat.PDF, ReportFormat.JUPYTER)],
        help="output format (default: html)",
    )
    p_report.add_argument(
        "--out-dir", default="reports",
        help="directory to write the rendered output (default: reports/)",
    )
    p_report.set_defaults(func=cmd_report)

    p_insp = sub.add_parser(
        "inspect",
        help="per-primitive profile (static introspection + optional dynamic)",
    )
    p_insp.add_argument("repo", help="path to the Kimera-SWM repository")
    p_insp.add_argument("primitive", help="primitive name or class name")
    p_insp.add_argument(
        "--with-discovery", action="store_true",
        help="run Layer A schema mining if the primitive has a wired target",
    )
    p_insp.add_argument(
        "--with-audit", action="store_true",
        help="run a single-file static audit against the primitive's source",
    )
    p_insp.add_argument(
        "--out-dir", default="primitives",
        help="directory to write the profile JSON + Markdown (default: primitives/)",
    )
    p_insp.set_defaults(func=cmd_inspect)

    p_insp_all = sub.add_parser(
        "inspect-all",
        help="survey every catalogued Kimera primitive",
    )
    p_insp_all.add_argument("repo", help="path to the Kimera-SWM repository")
    p_insp_all.add_argument(
        "--family", default="",
        help="filter by biological-family tag (brain / nervous_system / sensory / …)",
    )
    p_insp_all.add_argument(
        "--with-discovery", action="store_true",
        help="run Layer A schema mining for every primitive with a wired target",
    )
    p_insp_all.add_argument(
        "--with-audit", action="store_true",
        help="run a single-file static audit per located primitive",
    )
    p_insp_all.add_argument(
        "--out-dir", default="primitives",
        help="directory to write the survey JSON + Markdown (default: primitives/)",
    )
    p_insp_all.set_defaults(func=cmd_inspect_all)

    p_export = sub.add_parser(
        "export",
        help="export a signed record to a standard interop format (SARIF / JUnit XML)",
    )
    p_export.add_argument("record", help="path to a signed Ophamin record JSON")
    p_export.add_argument(
        "--format", required=True,
        choices=["sarif", "junit-xml", "junit", "mlflow", "cyclonedx", "sbom"],
        help=(
            "target format: sarif (audit → SARIF 2.1.0); "
            "junit-xml (proof → JUnit XML); "
            "mlflow (proof/audit → MLflow tracking run); "
            "cyclonedx / sbom (proof → CycloneDX 1.5 SBOM)"
        ),
    )
    p_export.add_argument(
        "--output", default="",
        help="output path (default: record path with the target extension; "
             "ignored for --format=mlflow)",
    )
    p_export.add_argument(
        "--tracking-uri", default="",
        help="MLflow tracking URI (default: file:./mlruns); only for --format=mlflow",
    )
    p_export.add_argument(
        "--experiment-name", default="",
        help="MLflow experiment name (default: ophamin-proof / ophamin-audit); "
             "only for --format=mlflow",
    )
    p_export.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
