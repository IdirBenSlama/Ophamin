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
    ophamin verify                        self-check the install (deps + binaries + CLI subcommands)
    ophamin drift-detect [--repo R]       online drift detection on a Kimera batch's Φ / walker stream
    ophamin report <record.json>          render a proof or audit record as HTML / Markdown / LaTeX
    ophamin inspect <kimera-repo> <name>  per-primitive profile (static + optional dynamic)
    ophamin inspect-all <kimera-repo>     survey every catalogued Kimera primitive
    ophamin export <record.json>          export a record to SARIF (audit) / JUnit XML (proof)
    ophamin audit-record show <path>      render an AuditRecord as Markdown
    ophamin audit-record verify <path>    HMAC-verify an AuditRecord
    ophamin audit-record validate <path>  structural + optional signature validation
    ophamin audit-record ingest <path>    full-validate pipeline (loud-fail on any layer)
    ophamin audit-record list <dir>       walk a directory; one row per audit JSON
    ophamin corpus list                   list every registered corpus + availability
    ophamin corpus show <name>            print one corpus's metadata + availability
    ophamin substrate list                list every registered SubstrateProbe class
    ophamin pillar list                   list every registered pillar (name + library + version)
    ophamin pillar show <name>            print the full metadata block for one pillar
    ophamin report-batch <records-dir>    render every signed record under a directory + INDEX.md
    ophamin run-all [--repo R]            run the 6-phase composite (seeing → measuring → comparing
                                          → instrumenting → auditing → reporting) and emit signed CampaignRecord
    ophamin summarize <directory>         walk a proof corpus; emit campaign-level summary
    ophamin diagnose <proof.json>         per-record diagnostic (verdict + siblings + claim)
    ophamin analyze <metric> --across D   walk a corpus; trajectory + summary for one metric
    ophamin scenario list                 list every registered scenario (name + tier + family + goal)
    ophamin scenario show <name>          print the full metadata block for one scenario
    ophamin proof show <path>             pretty-print a signed proof record to terminal
    ophamin proof verify <path>           HMAC-verify a signed proof under a key (default: built-in)
    ophamin proof validate <path>         JSON-Schema + structural + (optional) signature validation
    ophamin proof ingest <path>           full pipeline: raise loud on any validation failure
    ophamin proof list <directory>        walk a directory; emit one summary row per proof
    ophamin proof index <directory>       generate master INDEX.md manifest for the corpus
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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
from ophamin.auditing.pillars import (
    DEEP_PILLAR_CLASSES,
    DEFAULT_PILLAR_CLASSES,
    PROJECT_PILLAR_CLASSES,
)
from ophamin.inspecting import PrimitiveInspector
from ophamin.interop import (
    CycloneDXExporter,
    JUnitXMLExporter,
    MLflowExporter,
    SARIFExporter,
)
from ophamin.measuring.proof import codec as proof_codec
from ophamin.measuring.proof.codec import (
    ProofCodecError,
    ProofListEntry,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
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
from ophamin.comparing.drift_detection import (
    StreamDriftDetector,
    available_detectors,
    extract_phi_stream,
    extract_walker_halt_counts,
)
from ophamin.verify import (
    has_required_failure,
    render_report,
    render_text,
    run_all_checks,
)
from ophamin.seeing.substrate.base import SubstrateUnderTest
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


def build_substrate(config: dict[str, Any]) -> SubstrateUnderTest:
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
    sut = MockSubstrate(seed=int(base["experiment"]["seed"]))  # type: ignore[index]
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
        with_comparing=getattr(args, "with_comparing", False),
        with_instrumenting=getattr(args, "with_instrumenting", False),
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
        with_comparing=getattr(args, "with_comparing", False),
        with_instrumenting=getattr(args, "with_instrumenting", False),
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
    # filter pillars by --pillars list if given. Project-scope pillars
    # (deptry / fawltydeps) AND deep pillars (pylint) are NOT in
    # DEFAULT_PILLAR_CLASSES — include them in the lookup pool when named.
    available_classes = (
        list(DEFAULT_PILLAR_CLASSES) +
        list(DEEP_PILLAR_CLASSES) +
        list(PROJECT_PILLAR_CLASSES)
    )
    if args.pillars:
        wanted = {name.strip() for name in args.pillars.split(",") if name.strip()}
        pillar_classes = [cls for cls in available_classes if cls.name in wanted]
        if not pillar_classes:
            print(f"no pillars match --pillars={args.pillars}; available: "
                  f"{','.join(cls.name for cls in available_classes)}",
                  file=sys.stderr)
            return 2
    else:
        pillar_classes = list(DEFAULT_PILLAR_CLASSES)
    runner = AuditRunner(pillars=[cls() for cls in pillar_classes])  # type: ignore[abstract]
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


def cmd_drift_detect(args: argparse.Namespace) -> int:
    """Run an online drift detector over a Kimera batch's per-cycle stream.

    Pulls cycles via either KimeraAdapter (when ``--repo`` is given) or
    MockSubstrate, extracts the per-cycle Φ trajectory or the rolling
    amplitude_death fraction, and feeds the stream through the chosen
    River drift detector. Writes a signed DriftScan to ``--out-dir/``.
    """
    if args.repo:
        try:
            substrate: Any = KimeraAdapter(args.repo, target=args.target)
        except KimeraAdapterError as e:
            print(f"adapter error: {e}", file=sys.stderr)
            return 2
        substrate_label = f"kimera_repo={args.repo}, target={args.target}"
    else:
        substrate = MockSubstrate()
        substrate_label = "MockSubstrate"

    stimuli = [args.stimulus] * int(args.n_cycles)
    print(f"running         : {substrate_label}")
    print(f"cycles          : {args.n_cycles}")
    try:
        cycle_results = substrate.run_batch(stimuli)
    except Exception as e:
        print(f"batch failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if args.stream == "phi":
        stream = extract_phi_stream(cycle_results)
        stream_name = "phi_value"
    else:  # walker_halt
        stream = extract_walker_halt_counts(cycle_results, window=args.window)
        stream_name = f"walker_amplitude_death_rate_w{args.window}"

    if not stream:
        print(f"no stream samples extracted from {len(cycle_results)} cycles "
              f"(stream={args.stream}); cannot run drift detection",
              file=sys.stderr)
        return 1

    print(f"stream          : {stream_name} ({len(stream)} samples)")
    print(f"detector        : {args.detector}")

    detector = StreamDriftDetector(args.detector, stream_name=stream_name)
    scan = detector.scan(stream)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    short = scan.scan_id[:16]
    json_path = out_dir / f"drift_{short}.json"
    scan.to_json(str(json_path))

    print(f"\nresults:")
    print(f"  detector fired : {scan.fired}")
    print(f"  drift events   : {scan.n_events}")
    if scan.events:
        print(f"  event indices  : {scan.event_indices[:20]}"
              f"{' ...' if scan.n_events > 20 else ''}")
    print(f"\nwritten         : {json_path}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Self-check the install. Exit code 1 if any required check fails."""
    results = run_all_checks(
        kimera_repo=(args.kimera_repo if args.kimera_repo else None),
    )
    if args.markdown:
        print(render_report(results), end="")
    else:
        print(render_text(results))
    return 1 if has_required_failure(results) else 0


def cmd_mcp_serve(args: argparse.Namespace) -> int:
    """Start the Ophamin MCP server.

    Default transport is stdio (what Claude Code expects); SSE +
    streamable-http are available via ``--transport``. Returns
    exit code 0 on clean shutdown; the function blocks until the
    transport closes.
    """
    from ophamin.mcp import build_server

    server = build_server()
    transport = args.transport
    if transport == "stdio":
        # FastMCP.run signature is run(transport, mount_path=None)
        # mount_path is ignored for stdio
        server.run(transport="stdio")
    else:
        server.run(transport=transport, mount_path=args.mount_path)
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
    for stratum_s in report.per_stratum:
        print(f"{stratum_s.stratum:<16} {stratum_s.n_total:>6} {stratum_s.n_wired:>6} "
              f"{stratum_s.n_wire_candidate:>4} "
              f"{stratum_s.n_orphan:>7} {stratum_s.n_archived:>5} {stratum_s.n_parse_error:>5} "
              f"{stratum_s.wired_rate*100:>6.1f}% {stratum_s.orphan_rate*100:>6.1f}%")
    print()
    orphans = report.orphan_surfaces()
    wc = report.wire_candidate_surfaces()
    print(f"orphan surfaces         : {len(orphans)}")
    print(f"WIRE_CANDIDATE surfaces : {len(wc)}")
    if orphans:
        print(f"\norphan action list (first 10):")
        for orphan_s in orphans[:10]:
            print(f"  [{orphan_s.stratum:<14}] {orphan_s.file_path}")
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


def cmd_report_batch(args: argparse.Namespace) -> int:
    """Render every signed record under a directory; emit an INDEX.md."""
    from ophamin.reporting import ReportFormat, ReportRunner

    records_dir = Path(args.records_dir)
    if not records_dir.is_dir():
        sys.stderr.write(
            f"ophamin report-batch: {records_dir} is not a directory\n"
        )
        return 2
    fmt_map = {
        "html": ReportFormat.HTML,
        "markdown": ReportFormat.MARKDOWN,
        "latex": ReportFormat.LATEX,
    }
    fmt = fmt_map[args.format]
    runner = ReportRunner()
    summary = runner.run_batch(records_dir, Path(args.out_dir), fmt)
    print(
        f"OK: rendered {summary['n_rendered']} record(s) "
        f"({summary['n_skipped']} skipped) into {summary['out_dir']}"
    )
    print(f"  format:     {summary['format']}")
    print(f"  index:      {summary['index_path']}")
    if summary["n_skipped"] > 0:
        print(f"  skipped:")
        for path, reason in summary["skipped_paths"]:
            print(f"    - {path}: {reason}")
    return 0


def cmd_watch_proofs(args: argparse.Namespace) -> int:
    """Compare two proof-corpus snapshots; emit a signed RegressionAlertRecord.

    Exit codes:
      0 — no regressions detected (transitions may include recoveries or
          unchanged-pairs);
      1 — at least one regression detected (verdict went VALIDATED /
          INCONCLUSIVE → REFUTED);
      2 — CLI error (missing directory etc.).
    """
    from ophamin.comparing.regression_alert import (
        compute_regression_alert,
        dump_alert,
    )

    before = Path(args.before)
    after = Path(args.after)
    if not before.is_dir():
        sys.stderr.write(f"ophamin watch-proofs: --before {before} is not a directory\n")
        return 2
    if not after.is_dir():
        sys.stderr.write(f"ophamin watch-proofs: --after {after} is not a directory\n")
        return 2
    alert = compute_regression_alert(before, after)
    if args.key:
        alert.sign(_resolve_proof_key(args.key))
    elif not args.no_sign:
        alert.sign(DEFAULT_SIGN_KEY)
    if args.out:
        out_path = Path(args.out)
        dump_alert(alert, out_path)
        print(f"OK: regression-alert written to {out_path}")
    if args.json:
        print(json.dumps(alert.to_dict(), indent=2, default=str))
    else:
        print(alert.to_markdown())
    return 1 if alert.has_regressions else 0


def cmd_audit_record(args: argparse.Namespace) -> int:
    """Umbrella for the `ophamin audit-record <action>` subcommands.

    Mirrors `ophamin proof` but operates on AuditRecord JSON.
    """
    from ophamin.auditing import codec as audit_codec
    from ophamin.auditing.codec import AuditCodecError

    action = args.audit_action
    if action == "show":
        path = Path(args.path)
        try:
            record = audit_codec.load(path)
        except AuditCodecError as exc:
            sys.stderr.write(f"ophamin audit-record show: {exc}\n")
            return 2
        print(record.to_markdown())
        return 0
    if action == "verify":
        try:
            ok = audit_codec.verify_signature(
                Path(args.path), _resolve_proof_key(args.key)
            )
        except AuditCodecError as exc:
            sys.stderr.write(f"ophamin audit-record verify: {exc}\n")
            return 2
        if ok:
            print(f"OK: signature verifies for {args.path}")
            return 0
        print(f"FAIL: signature did NOT verify for {args.path}", file=sys.stderr)
        return 1
    if action == "validate":
        key = _resolve_proof_key(args.key) if args.key or args.with_signature else None
        try:
            report = audit_codec.validate(Path(args.path), key=key)
        except AuditCodecError as exc:
            sys.stderr.write(f"ophamin audit-record validate: {exc}\n")
            return 2
        print(f"path:           {args.path}")
        print(f"record_ok:      {report.record_ok}")
        if report.record_problems:
            print("record_problems:")
            for prob in report.record_problems:
                print(f"  - {prob}")
        print(f"signature_ok:   {report.signature_ok}")
        print(f"all_ok:         {report.all_ok}")
        return 0 if report.all_ok else 1
    if action == "ingest":
        key = (
            _resolve_proof_key(args.key) if args.key or args.strict_signature else None
        )
        try:
            record = audit_codec.ingest(
                Path(args.path),
                key=key,
                strict_signature=bool(args.strict_signature),
            )
        except AuditCodecError as exc:
            sys.stderr.write(f"ophamin audit-record ingest: {exc}\n")
            return 1
        print(f"OK: ingested {args.path}")
        print(f"  audit_id:        {record.audit_id}")
        print(f"  schema_version:  {record.schema_version}")
        print(f"  total_findings:  {record.summary.total_findings}")
        return 0
    if action == "list":
        directory = Path(args.directory)
        if not directory.is_dir():
            sys.stderr.write(f"ophamin audit-record list: {directory} is not a directory\n")
            return 2
        key = _resolve_proof_key(args.key) if args.key or args.with_signature else None
        entries = audit_codec.list_audits(directory, key=key)
        if args.json:
            payload = [
                {
                    "path": str(e.path),
                    "audit_id": e.audit_id,
                    "total_findings": e.total_findings,
                    "schema_version": e.schema_version,
                    "target_path": e.target_path,
                    "signature_ok": e.signature_ok,
                    "error": e.error,
                }
                for e in entries
            ]
            print(json.dumps(payload, indent=2))
            return 0
        if not entries:
            print(f"(no JSON files under {directory})")
            return 0
        print(f"{'findings':>10}  {'schema':<10}  path")
        print("-" * 80)
        for e in entries:
            if e.error:
                print(f"{'ERROR':>10}  {'?':<10}  {e.path}  ({e.error})")
                continue
            print(
                f"{e.total_findings:>10}  {e.schema_version or '?':<10}  {e.path}"
            )
        return 0
    sys.stderr.write(f"ophamin audit-record: unknown action {action!r}\n")
    return 2


def cmd_corpus(args: argparse.Namespace) -> int:
    """Umbrella for `ophamin corpus <action>` subcommands.

    Two actions:
    - ``list`` — print every registered corpus name + availability.
    - ``show <name>`` — print the corpus's source / kind / n_records
      and whether its data is downloaded.
    """
    from ophamin.seeing.corpus import (
        CORPUS_FACTORIES,
        available_corpora,
        get_corpus,
    )

    action = args.corpus_action
    if action == "list":
        avail = available_corpora()
        entries = [
            {"name": name, "available": bool(avail.get(name, False))}
            for name in sorted(CORPUS_FACTORIES)
        ]
        if args.json:
            print(json.dumps(entries, indent=2))
            return 0
        print(f"{'name':<20}  available")
        print("-" * 40)
        for e in entries:
            print(f"{e['name']:<20}  {'yes' if e['available'] else 'no'}")
        print()
        print(f"({len(entries)} corpus/corpora registered)")
        return 0
    if action == "show":
        if args.name not in CORPUS_FACTORIES:
            sys.stderr.write(
                f"ophamin corpus show: unknown corpus {args.name!r}\n"
                f"  available: {', '.join(sorted(CORPUS_FACTORIES))}\n"
            )
            return 2
        corpus = get_corpus(args.name)
        print(f"name:        {args.name}")
        print(f"kind:        {getattr(corpus, 'kind', '?')}")
        print(f"source:      {getattr(corpus, 'source', '?')}")
        print(f"available:   {corpus.is_available()}")
        if corpus.is_available():
            try:
                print(f"n_records:   {corpus.count()}")
            except Exception as exc:  # noqa: BLE001
                print(f"n_records:   (unable to count: {exc})")
        return 0
    sys.stderr.write(f"ophamin corpus: unknown action {action!r}\n")
    return 2


def cmd_substrate(args: argparse.Namespace) -> int:
    """Umbrella for `ophamin substrate <action>` — list registered probes."""
    from ophamin.registry import SUBSTRATE_FACTORIES

    action = args.substrate_action
    if action == "list":
        entries = [
            {
                "name": name,
                "class": f"{SUBSTRATE_FACTORIES[name].__module__}."
                         f"{SUBSTRATE_FACTORIES[name].__qualname__}",
            }
            for name in sorted(SUBSTRATE_FACTORIES)
        ]
        if args.json:
            print(json.dumps(entries, indent=2))
            return 0
        print(f"{'name':<20}  class")
        print("-" * 80)
        for e in entries:
            print(f"{e['name']:<20}  {e['class']}")
        print()
        print(f"({len(entries)} substrate(s) registered)")
        return 0
    sys.stderr.write(f"ophamin substrate: unknown action {action!r}\n")
    return 2


def cmd_pillar(args: argparse.Namespace) -> int:
    """Umbrella for `ophamin pillar <action>` subcommands.

    Two actions:
    - ``list`` — print every registered pillar (name + library +
      version) as a table, or as JSON via ``--json``.
    - ``show <name>`` — print the full metadata block for one pillar
      (name + library + version + class + module + docstring summary).
    """
    # Import the pillars package to fire registration of every shipped
    # adapter; the registry is otherwise empty on a fresh interpreter.
    from ophamin.measuring import pillars  # noqa: F401
    from ophamin.registry import PILLARS

    action = args.pillar_action
    if action == "list":
        return _pillar_list(PILLARS, as_json=bool(args.json))
    if action == "show":
        return _pillar_show(PILLARS, args.name)
    sys.stderr.write(f"ophamin pillar: unknown action {action!r}\n")
    return 2


def _pillar_list(pillars_dict: dict[str, Any], *, as_json: bool) -> int:
    entries = [
        {
            "name": p.pillar_name,
            "library": p.library,
            "library_version": p.library_version,
            "class": f"{type(p).__module__}.{type(p).__qualname__}",
        }
        for p in (pillars_dict[k] for k in sorted(pillars_dict))
    ]
    if as_json:
        print(json.dumps(entries, indent=2))
        return 0
    if not entries:
        print("(no pillars registered)")
        return 0
    name_w = max(len(e["name"]) for e in entries)
    lib_w = max(len(e["library"]) for e in entries)
    print(f"{'pillar_name':<{name_w}}  {'library':<{lib_w}}  version")
    print("-" * (name_w + lib_w + 20))
    for e in entries:
        print(
            f"{e['name']:<{name_w}}  {e['library']:<{lib_w}}  "
            f"{e['library_version']}"
        )
    print()
    print(f"({len(entries)} pillar(s) registered)")
    return 0


def _pillar_show(pillars_dict: dict[str, Any], name: str) -> int:
    pillar = pillars_dict.get(name)
    if pillar is None:
        sys.stderr.write(
            f"ophamin pillar show: unknown pillar {name!r}\n"
            f"  available: {', '.join(sorted(pillars_dict))}\n"
        )
        return 2
    cls = type(pillar)
    doc = (cls.__doc__ or "").strip().split("\n\n")[0].replace("\n", " ")
    print(f"pillar_name:       {pillar.pillar_name}")
    print(f"library:           {pillar.library}")
    print(f"library_version:   {pillar.library_version}")
    print(f"class:             {cls.__module__}.{cls.__qualname__}")
    print(f"protocol_check:    isinstance(pillar, Pillar) = True")
    print()
    print("summary:")
    for line in _wrap_paragraph(doc, width=76):
        print(f"  {line}")
    return 0


def cmd_run_all(args: argparse.Namespace) -> int:
    """Run the 6-phase composite-run orchestrator against MockSubstrate
    (or a Kimera adapter when ``--repo`` is provided) and emit a signed
    CampaignRecord."""
    from ophamin.campaign import (
        CANONICAL_PHASE_ORDER,
        dump_campaign,
        run_campaign,
    )
    from ophamin.measuring.scenarios import SCENARIOS
    from ophamin.seeing.substrate import MockSubstrate

    substrate: SubstrateUnderTest
    if args.repo:
        try:
            from ophamin.seeing.substrate.kimera_adapter import KimeraAdapter
            substrate = KimeraAdapter(
                kimera_repo=args.repo,
                target=args.target,
                mode="batch",
            )
        except Exception as exc:
            sys.stderr.write(f"ophamin run-all: could not construct KimeraAdapter: {exc}\n")
            return 2
    else:
        substrate = MockSubstrate(seed=1)

    if args.scenarios:
        names = [s.strip() for s in args.scenarios.split(",") if s.strip()]
        unknown = [n for n in names if n not in SCENARIOS]
        if unknown:
            sys.stderr.write(
                f"ophamin run-all: unknown scenario(s): {unknown}\n"
                f"  available: {', '.join(sorted(SCENARIOS))}\n"
            )
            return 2
        scenarios = [SCENARIOS[n] for n in names]
    else:
        scenarios = None  # let run_campaign pick default-instantiable

    if args.skip:
        skip = {s.strip() for s in args.skip.split(",") if s.strip()}
        unknown_phases = skip - set(CANONICAL_PHASE_ORDER)
        if unknown_phases:
            sys.stderr.write(
                f"ophamin run-all: unknown phase(s): {sorted(unknown_phases)}\n"
                f"  canonical phases: {list(CANONICAL_PHASE_ORDER)}\n"
            )
            return 2
        enable_phases = set(CANONICAL_PHASE_ORDER) - skip
    else:
        enable_phases = set(CANONICAL_PHASE_ORDER)

    out_dir = Path(args.out_dir)
    record = run_campaign(
        substrate=substrate,
        scenarios=scenarios,
        enable_phases=enable_phases,
        out_dir=out_dir,
        fwer_method=getattr(args, "fwer_method", "holm"),
        fwer_alpha=getattr(args, "fwer_alpha", 0.05),
    )

    campaign_path = out_dir / "CAMPAIGN.json"
    dump_campaign(record, campaign_path)
    print(f"OK: campaign complete (id={record.campaign_id[:16]}...)")
    print(f"  target:     {record.target_name} @ {record.target_git_commit[:12]}")
    print(f"  phases:     {record.status_counts}")
    print(f"  campaign:   {campaign_path}")
    if not args.quiet:
        print()
        print(record.to_markdown())
    return 0 if not record.any_failed else 1


def cmd_summarize(args: argparse.Namespace) -> int:
    """Walk a proof directory; emit a campaign-level summary."""
    from ophamin.comparing.synthesis import summarize_directory

    directory = Path(args.directory)
    if not directory.is_dir():
        sys.stderr.write(
            f"ophamin summarize: {directory} is not a directory\n"
        )
        return 2
    summary = summarize_directory(directory)
    if args.json:
        payload = {
            "root": str(summary.root),
            "generated_at": summary.generated_at,
            "total": summary.total,
            "n_decode_errors": summary.n_decode_errors,
            "by_verdict": summary.by_verdict,
            "by_family": summary.by_family,
            "by_substrate_commit": summary.by_substrate_commit,
            "verdict_flips": [
                {
                    "family": f.family,
                    "commit_a": f.commit_a,
                    "commit_b": f.commit_b,
                    "verdict_a": f.verdict_a,
                    "verdict_b": f.verdict_b,
                    "proof_a": str(f.proof_a),
                    "proof_b": str(f.proof_b),
                }
                for f in summary.verdict_flips
            ],
        }
        text = json.dumps(payload, indent=2)
    else:
        text = summary.to_markdown()
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"OK: wrote {out} ({summary.total} entries)")
    else:
        print(text)
    return 0


def cmd_correct(args: argparse.Namespace) -> int:
    """Walk a proof directory; apply multiplicity correction.

    Reads every signed proof under ``args.directory``, projects each to
    its (claim_id, raw_verdict, min-p-value-across-pillars), and runs
    the chosen correction (Holm-Bonferroni for FWER, Benjamini-Hochberg
    for FDR, or no correction). Emits a per-record table + summary.

    Exit codes:
      0 — happy path (correction completed; some demotions are allowed)
      2 — input directory missing or invalid
    """
    from ophamin.campaign import correction_family_from_directory

    directory = Path(args.directory)
    if not directory.is_dir():
        sys.stderr.write(
            f"ophamin correct: {directory} is not a directory\n"
        )
        return 2
    family = correction_family_from_directory(
        directory, method=args.method, alpha=args.alpha
    )
    if args.json:
        payload = {
            "directory": str(directory),
            "method": family.method,
            "alpha": family.alpha,
            "family_size": family.family_size,
            "n_with_p_value": family.n_with_p_value,
            "n_rejections": family.n_rejections,
            "verdicts": family.verdicts(),
            "per_record": [
                {
                    "claim_id": r.claim_id,
                    "raw_verdict": r.raw_verdict,
                    "corrected_verdict": r.corrected_verdict,
                    "raw_p_value": r.raw_p_value,
                    "corrected_p_value": r.corrected_p_value,
                    "significant_after_correction": r.significant_after_correction,
                }
                for r in family.results
            ],
        }
        text = json.dumps(payload, indent=2)
    else:
        lines: list[str] = []
        lines.append(f"# Multiplicity correction — `{directory}`")
        lines.append("")
        lines.append(
            f"**Method:** `{family.method}` · **α:** {family.alpha} · "
            f"**Family size:** {family.family_size} · "
            f"**With p-value:** {family.n_with_p_value} · "
            f"**Rejections (significant after correction):** {family.n_rejections}"
        )
        lines.append("")
        lines.append("| Claim ID | Raw verdict | Corrected verdict | Raw p | Adj. p | Significant |")
        lines.append("|---|---|---|---|---|---|")
        for r in family.results:
            raw_p = f"{r.raw_p_value:.4g}" if r.raw_p_value is not None else "—"
            adj_p = (
                f"{r.corrected_p_value:.4g}"
                if r.corrected_p_value is not None
                else "—"
            )
            sig = "✓" if r.significant_after_correction else "✗"
            short_id = r.claim_id[:12] if len(r.claim_id) > 16 else r.claim_id
            lines.append(
                f"| `{short_id}` | {r.raw_verdict} | {r.corrected_verdict} | "
                f"{raw_p} | {adj_p} | {sig} |"
            )
        lines.append("")
        text = "\n".join(lines)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(
            f"OK: wrote {out} ({family.family_size} entries, "
            f"{family.n_rejections} rejections after correction)"
        )
    else:
        print(text)
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    """Build a per-record diagnostic and emit it."""
    from ophamin.comparing.synthesis import diagnose_proof
    from ophamin.measuring.proof.codec import ProofDecodeError

    path = Path(args.path)
    corpus_dir = Path(args.corpus_dir) if args.corpus_dir else None
    try:
        diag = diagnose_proof(path, corpus_dir=corpus_dir)
    except ProofDecodeError as exc:
        sys.stderr.write(f"ophamin diagnose: {exc}\n")
        return 2
    if args.json:
        payload = {
            "proof_path": str(diag.proof_path),
            "proof_id": diag.proof_id,
            "verdict_outcome": diag.verdict_outcome,
            "verdict_observed": diag.verdict_observed,
            "verdict_threshold": diag.verdict_threshold_describe,
            "claim": diag.claim_statement,
            "closest_family_siblings": [
                {"path": str(s.path), "verdict": s.verdict}
                for s in diag.closest_family_siblings
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(diag.to_markdown())
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Walk a corpus; extract every value of one metric; summarise."""
    from ophamin.comparing.synthesis import analyze_metric

    directory = Path(args.directory)
    if not directory.is_dir():
        sys.stderr.write(
            f"ophamin analyze: {directory} is not a directory\n"
        )
        return 2
    trajectory = analyze_metric(args.metric, directory)
    if args.json:
        payload = {
            "metric": trajectory.metric,
            "root": str(trajectory.root),
            "n_proofs_scanned": trajectory.n_proofs_scanned,
            "n_values": trajectory.n_values,
            "values": [
                {"path": str(p), "value": v} for p, v in trajectory.values
            ],
            "mean": trajectory.mean,
            "stdev": trajectory.stdev,
            "minimum": trajectory.minimum,
            "maximum": trajectory.maximum,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(trajectory.to_markdown())
    return 0


def cmd_api_stability(args: argparse.Namespace) -> int:
    """Audit the framework's public symbols against the stability policy.

    Two modes:

      ``ophamin api-stability list``
          Print every annotated symbol grouped by tier.

      ``ophamin api-stability check <directory>``
          Walk every Python file under ``<directory>`` and report any
          imports of ophamin symbols tagged ``@Deprecated`` or
          ``@Internal``. Exit code 0 = clean; 1 = at least one
          violation (suitable for CI gates).
    """
    import importlib
    import pkgutil

    from ophamin._stability import (
        StabilityInfo,
        get_stability,
        is_deprecated,
        is_internal,
    )

    def _walk_ophamin_symbols() -> dict[str, list[tuple[str, StabilityInfo]]]:
        """Group every annotated ophamin symbol by tier."""
        import ophamin as _ophamin

        groups: dict[str, list[tuple[str, StabilityInfo]]] = {
            "Stable": [],
            "Provisional": [],
            "Internal": [],
            "Deprecated": [],
        }
        seen: set[int] = set()

        def _scan(mod_name: str) -> None:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:  # noqa: BLE001 — broken submodule; skip
                return
            for attr in dir(mod):
                if attr.startswith("__") and attr.endswith("__"):
                    continue
                obj = getattr(mod, attr, None)
                if obj is None or id(obj) in seen:
                    continue
                info = get_stability(obj)
                if info is None:
                    continue
                # Filter to objects actually defined in ophamin (not
                # re-exports of third-party objects).
                obj_mod = getattr(obj, "__module__", "")
                if not obj_mod.startswith("ophamin"):
                    continue
                seen.add(id(obj))
                groups.setdefault(info.tier, []).append(
                    (f"{obj_mod}.{attr}", info)
                )

        # Walk every submodule under ophamin/
        prefix = _ophamin.__name__ + "."
        for _finder, mod_name, _is_pkg in pkgutil.walk_packages(
            _ophamin.__path__, prefix
        ):
            _scan(mod_name)
        return groups

    if args.subcommand == "list":
        groups = _walk_ophamin_symbols()
        if args.json:
            payload: dict[str, list[dict[str, str]]] = {
                tier: [
                    {
                        "name": name,
                        "since": info.since,
                        "removal_version": info.removal_version,
                        "replacement": info.replacement,
                        "notes": info.notes,
                    }
                    for name, info in sorted(entries)
                ]
                for tier, entries in groups.items()
            }
            print(json.dumps(payload, indent=2))
        else:
            for tier in ("Stable", "Provisional", "Deprecated", "Internal"):
                entries = sorted(groups.get(tier, []))
                if not entries:
                    continue
                print(f"\n## {tier} ({len(entries)} symbol(s))\n")
                for name, info in entries:
                    suffix = ""
                    if info.since:
                        suffix += f" since {info.since}"
                    if info.removal_version:
                        suffix += f"; removal at {info.removal_version}"
                    if info.replacement:
                        suffix += f"; use {info.replacement}"
                    print(f"  {name}{suffix}")
        return 0

    if args.subcommand == "check":
        target_dir = Path(args.directory)
        if not target_dir.is_dir():
            sys.stderr.write(
                f"ophamin api-stability check: {target_dir} is not a directory\n"
            )
            return 2
        import ast

        violations: list[tuple[Path, int, str, str]] = []
        # Build the deprecated + internal symbol set up front.
        groups = _walk_ophamin_symbols()
        deprecated_names: dict[str, StabilityInfo] = {
            name: info
            for name, info in groups.get("Deprecated", [])
        }
        internal_names: dict[str, StabilityInfo] = {
            name: info
            for name, info in groups.get("Internal", [])
        }

        def _check_imports(py_path: Path) -> None:
            try:
                source = py_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_path))
            except (OSError, SyntaxError):
                return
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if not mod.startswith("ophamin"):
                        continue
                    for alias in node.names:
                        full = f"{mod}.{alias.name}"
                        if full in deprecated_names:
                            info = deprecated_names[full]
                            violations.append(
                                (py_path, node.lineno, "Deprecated", full
                                 + f" (removal: {info.removal_version}"
                                 + (f", use: {info.replacement}" if info.replacement else "")
                                 + ")")
                            )
                        elif full in internal_names:
                            violations.append(
                                (py_path, node.lineno, "Internal", full)
                            )

        for py_path in sorted(target_dir.rglob("*.py")):
            _check_imports(py_path)

        if args.json:
            payload2: list[dict[str, str | int]] = [
                {
                    "path": str(p),
                    "line": ln,
                    "tier": tier,
                    "symbol": detail,
                }
                for (p, ln, tier, detail) in violations
            ]
            print(json.dumps(payload2, indent=2))
        else:
            if not violations:
                print(f"OK: 0 deprecated / internal Ophamin imports under {target_dir}")
            else:
                for p, ln, tier, detail in violations:
                    print(f"{p}:{ln}: [{tier}] {detail}")
                print(
                    f"\n{len(violations)} violation(s) found.",
                    file=sys.stderr,
                )
        return 0 if not violations else 1

    sys.stderr.write(
        f"ophamin api-stability: unknown subcommand {args.subcommand!r}\n"
        f"  expected: list | check\n"
    )
    return 64


def cmd_schema(args: argparse.Namespace) -> int:
    """Umbrella for `ophamin schema <action>` subcommands (Phase L4).

    Three actions:

    - ``info <path>`` — detect the schema_version of a signed record,
      print the catalogue row from SCHEMAS.md, exit 0.
    - ``validate <path>`` — load the record via the appropriate codec
      (structural validation), optionally verify the signature when
      ``--key`` is provided. Exit 0 on success, 2 on any failure.
    - ``list`` — print every documented schema name + current version.

    The action runs against any of the framework's signed record types:
    EmpiricalProofRecord (proof.json), AuditRecord (audit.json),
    CampaignRecord, RegressionAlertRecord, DriftScan. Detection is by
    inspecting top-level keys: ``proof_id`` → proof, ``audit_id`` →
    audit, ``campaign_id`` → campaign, ``alert_id`` → regression-alert,
    ``events`` + ``metric_name`` → drift-scan.

    See SCHEMAS.md for the full versioning policy.
    """
    action = args.schema_action
    if action == "list":
        return _schema_list()
    if action == "info":
        return _schema_info(args.path)
    if action == "validate":
        sign_key = (
            args.key.encode("utf-8") if getattr(args, "key", None) else None
        )
        return _schema_validate(
            args.path, sign_key=sign_key,
            allow_any_version=bool(getattr(args, "allow_any_schema_version", False)),
            recursive=bool(getattr(args, "recursive", False)),
        )
    sys.stderr.write(f"ophamin schema: unknown action {action!r}\n")
    return 2


def _schema_list() -> int:
    rows = [
        ("EmpiricalProofRecord", "1.0", "measuring/proof/codec.py"),
        ("AuditRecord",          "audit/1.1", "auditing/codec.py"),
        ("CampaignRecord",       "1.0", "campaign.py"),
        ("RegressionAlertRecord", "regression-alert/1.0", "comparing/regression_alert.py"),
        ("DriftScan",            "2", "comparing/drift_detection/river_detector.py"),
    ]
    print(f"{'schema':<28} {'version':<24} module")
    print("-" * 86)
    for name, ver, mod in rows:
        print(f"{name:<28} {ver:<24} {mod}")
    print()
    print("See SCHEMAS.md for the full versioning policy + migration story.")
    return 0


def _detect_schema_kind(payload: dict[str, Any]) -> str | None:
    """Return one of: 'proof', 'audit', 'campaign', 'regression-alert',
    'drift-scan', or None if unrecognised."""
    if "proof_id" in payload:
        return "proof"
    if "audit_id" in payload:
        return "audit"
    if "campaign_id" in payload:
        return "campaign"
    if "alert_id" in payload:
        return "regression-alert"
    if "events" in payload and "metric_name" in payload:
        return "drift-scan"
    return None


def _schema_info(path: str | Path) -> int:
    p = Path(path)
    if not p.is_file():
        sys.stderr.write(f"ophamin schema info: not a file: {p}\n")
        return 2
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ophamin schema info: cannot read {p}: {exc}\n")
        return 2
    if not isinstance(payload, dict):
        sys.stderr.write(f"ophamin schema info: top level must be an object, got {type(payload).__name__}\n")
        return 2
    kind = _detect_schema_kind(payload)
    version = payload.get("schema_version", "<missing>")
    print(f"path:           {p}")
    print(f"detected kind:  {kind or '<unrecognised>'}")
    print(f"schema_version: {version}")
    if "signature" in payload:
        sig = payload.get("signature") or ""
        print(f"signature:      {sig[:20]}{'…' if len(sig) > 20 else ''} ({'present' if sig else '<empty>'})")
    else:
        print("signature:      <not present in this schema>")
    return 0


def _schema_validate(
    path: str | Path,
    *,
    sign_key: bytes | None,
    allow_any_version: bool,
    recursive: bool,
) -> int:
    p = Path(path)
    if recursive and p.is_dir():
        targets = sorted(p.rglob("*.json"))
        if not targets:
            sys.stderr.write(f"ophamin schema validate: no .json files under {p}\n")
            return 2
    elif p.is_file():
        targets = [p]
    elif p.is_dir() and not recursive:
        sys.stderr.write(
            f"ophamin schema validate: {p} is a directory; pass --recursive to scan it\n"
        )
        return 2
    else:
        sys.stderr.write(f"ophamin schema validate: not found: {p}\n")
        return 2

    n_ok = 0
    n_failed = 0
    for target in targets:
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL  {target}: cannot read: {exc}")
            n_failed += 1
            continue
        if not isinstance(payload, dict):
            print(f"FAIL  {target}: top-level must be a JSON object")
            n_failed += 1
            continue
        kind = _detect_schema_kind(payload)
        if kind is None:
            print(f"FAIL  {target}: unrecognised schema (no recognised id field)")
            n_failed += 1
            continue
        try:
            _validate_one(target, kind, payload, sign_key, allow_any_version)
        except Exception as exc:  # noqa: BLE001 — surface per-file failures
            print(f"FAIL  {target}: {type(exc).__name__}: {exc}")
            n_failed += 1
            continue
        sig_note = " (signature verified)" if sign_key else ""
        print(f"OK    {target}: {kind}@{payload.get('schema_version', '?')}{sig_note}")
        n_ok += 1

    print()
    print(f"summary: {n_ok} ok, {n_failed} failed")
    return 0 if n_failed == 0 else 2


def _validate_one(
    target: Path,
    kind: str,
    payload: dict[str, Any],
    sign_key: bytes | None,
    allow_any_version: bool,
) -> None:
    """Dispatch validation to the appropriate codec; raises on failure."""
    if kind == "proof":
        from ophamin.measuring.proof.codec import (
            SCHEMA_VERSION as PROOF_VERSION,
            load as proof_load,
            verify_signature as proof_verify,
        )
        version = payload.get("schema_version")
        if not allow_any_version and version != PROOF_VERSION:
            raise ValueError(
                f"schema_version mismatch: file is {version!r}, codec expects {PROOF_VERSION!r}"
            )
        proof_load(target)  # structural validation; raises on shape errors
        if sign_key is not None:
            if not proof_verify(target, sign_key):
                raise ValueError("signature verification failed")
        return

    if kind == "audit":
        from ophamin.auditing.codec import (
            SCHEMA_VERSION as AUDIT_VERSION,
            load as audit_load,
            verify_signature as audit_verify,
        )
        version = payload.get("schema_version")
        # AuditRecord v1.1 codec accepts v1.0 cleanly; only block on a
        # different major. allow_any_version skips even that.
        if not allow_any_version and version not in {AUDIT_VERSION, "audit/1.0"}:
            raise ValueError(
                f"schema_version mismatch: file is {version!r}, codec accepts {AUDIT_VERSION!r} or audit/1.0"
            )
        audit_load(target)
        if sign_key is not None:
            if not audit_verify(target, sign_key):
                raise ValueError("signature verification failed")
        return

    if kind == "campaign":
        from ophamin.campaign import (
            CAMPAIGN_SCHEMA_VERSION,
            load_campaign,
        )
        version = payload.get("schema_version")
        if not allow_any_version and version != CAMPAIGN_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version mismatch: file is {version!r}, codec expects {CAMPAIGN_SCHEMA_VERSION!r}"
            )
        campaign_record = load_campaign(target)
        if sign_key is not None and not campaign_record.verify_signature(sign_key):
            raise ValueError("signature verification failed")
        return

    if kind == "regression-alert":
        from ophamin.comparing.regression_alert import (
            REGRESSION_ALERT_SCHEMA_VERSION,
            RegressionAlertRecord,
        )
        version = payload.get("schema_version")
        if not allow_any_version and version != REGRESSION_ALERT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version mismatch: file is {version!r}, codec expects {REGRESSION_ALERT_SCHEMA_VERSION!r}"
            )
        alert_record = RegressionAlertRecord.from_dict(payload)
        if sign_key is not None and not alert_record.verify_signature(sign_key):
            raise ValueError("signature verification failed")
        return

    if kind == "drift-scan":
        from ophamin.comparing.drift_detection.river_detector import (
            DRIFT_SCHEMA_VERSION,
        )
        version = payload.get("schema_version")
        if not allow_any_version and version not in {DRIFT_SCHEMA_VERSION, 1}:
            raise ValueError(
                f"schema_version mismatch: file is {version!r}, codec accepts {DRIFT_SCHEMA_VERSION} or 1"
            )
        # drift-scan has no codec-level signing yet; structural-only
        for required in ("events", "metric_name", "n_observations"):
            if required not in payload:
                raise ValueError(f"missing required field {required!r}")
        return

    raise ValueError(f"no dispatcher for kind {kind!r}")


def cmd_scenario(args: argparse.Namespace) -> int:
    """Umbrella for `ophamin scenario <action>` subcommands.

    Three actions:
    - ``list`` — print every registered scenario (name + tier + family +
      goal) as a table, or as JSON via ``--json``;
    - ``show <name>`` — print the full metadata block for one scenario
      (tier + family + goal + explanation + method +
      falsification_consequence + corpus + target + n_cycles);
    - ``info <name>`` — same as ``show`` (alias).

    Per Move E's design, scenario execution itself is wired via the
    existing ``ophamin run / sweep`` entry points; ``cmd_scenario`` is
    the **discovery surface** that surfaces what's available + their
    metadata. The CLI does not duplicate the runner machinery.
    """
    from ophamin.measuring.scenarios import SCENARIOS

    action = args.scenario_action
    if action == "list":
        return _scenario_list(SCENARIOS, as_json=bool(args.json), tier_filter=args.tier or None)
    if action in ("show", "info"):
        return _scenario_show(SCENARIOS, args.name)
    sys.stderr.write(f"ophamin scenario: unknown action {action!r}\n")
    return 2


def _scenario_list(scenarios_dict: dict[str, Any], *, as_json: bool, tier_filter: str | None) -> int:
    entries = []
    for name, cls in sorted(scenarios_dict.items()):
        tier_value = cls.tier.value if hasattr(cls.tier, "value") else str(cls.tier)
        if tier_filter and tier_value != tier_filter:
            continue
        entries.append({
            "name": name,
            "tier": tier_value,
            "family": cls.family,
            "goal": cls.goal,
            "method": cls.method or None,
            "corpus": cls.corpus_name,
            "target": cls.target,
        })
    if as_json:
        print(json.dumps(entries, indent=2))
        return 0
    if not entries:
        suffix = f" matching tier={tier_filter!r}" if tier_filter else ""
        print(f"(no scenarios registered{suffix})")
        return 0
    name_w = max(len(e["name"]) for e in entries)
    tier_w = max(len(e["tier"]) for e in entries)
    family_w = max(len(e["family"]) for e in entries)
    print(
        f"{'name':<{name_w}}  {'tier':<{tier_w}}  "
        f"{'family':<{family_w}}  goal"
    )
    print("-" * (name_w + tier_w + family_w + 60))
    for e in entries:
        goal = e["goal"]
        if len(goal) > 80:
            goal = goal[:77] + "..."
        print(
            f"{e['name']:<{name_w}}  {e['tier']:<{tier_w}}  "
            f"{e['family']:<{family_w}}  {goal}"
        )
    print()
    print(f"({len(entries)} scenario(s) registered)")
    return 0


def _scenario_show(scenarios_dict: dict[str, Any], name: str) -> int:
    cls = scenarios_dict.get(name)
    if cls is None:
        sys.stderr.write(
            f"ophamin scenario show: unknown scenario {name!r}\n"
            f"  available: {', '.join(sorted(scenarios_dict))}\n"
        )
        return 2
    tier_value = cls.tier.value if hasattr(cls.tier, "value") else str(cls.tier)
    print(f"name:                        {cls.name}")
    print(f"tier:                        {tier_value}")
    print(f"family:                      {cls.family}")
    print(f"corpus_name:                 {cls.corpus_name}")
    print(f"target:                      {cls.target}")
    print(f"n_cycles (default):          {cls.n_cycles}")
    if cls.method:
        print(f"method:                      {cls.method}")
    print()
    print(f"goal:")
    print(f"  {cls.goal}")
    print()
    print(f"explanation:")
    for line in _wrap_paragraph(cls.explanation, width=76):
        print(f"  {line}")
    print()
    if cls.falsification_consequence:
        print(f"falsification consequence:")
        for line in _wrap_paragraph(cls.falsification_consequence, width=76):
            print(f"  {line}")
        print()
    print(f"qualified class:             {cls.__module__}.{cls.__qualname__}")
    return 0


def _wrap_paragraph(text: str, *, width: int) -> list[str]:
    """Word-wrap a paragraph into lines no longer than ``width``."""
    import textwrap
    return textwrap.wrap(text, width=width) or [""]


def _resolve_proof_key(arg_value: str) -> bytes:
    """Resolve the ``--key`` CLI argument into HMAC key bytes.

    Special value ``"default"`` (or empty) maps to
    :data:`DEFAULT_SIGN_KEY`. Otherwise the argument is interpreted as
    a UTF-8 string of the key.
    """
    if not arg_value or arg_value == "default":
        return DEFAULT_SIGN_KEY
    return arg_value.encode("utf-8")


def cmd_proof(args: argparse.Namespace) -> int:
    """Umbrella for the `ophamin proof <action>` subcommands.

    Dispatches to one of: show / verify / validate / ingest / list.
    Returns an exit code suitable for shells (0 on success, non-zero on
    any failure surfaced by the codec layer).
    """
    action = args.proof_action
    if action == "show":
        return _proof_show(Path(args.path))
    if action == "verify":
        return _proof_verify(Path(args.path), _resolve_proof_key(args.key))
    if action == "validate":
        key: bytes | None = (
            _resolve_proof_key(args.key) if args.key or args.with_signature else None
        )
        return _proof_validate(Path(args.path), key)
    if action == "ingest":
        key_opt: bytes | None = (
            _resolve_proof_key(args.key) if args.key or args.strict_signature else None
        )
        if args.allow_any_schema_version:
            require_version: str | None = None
        elif args.require_schema_version:
            require_version = args.require_schema_version
        else:
            require_version = proof_codec.SCHEMA_VERSION
        return _proof_ingest(
            Path(args.path),
            key=key_opt,
            strict_signature=bool(args.strict_signature),
            require_schema_version=require_version,
        )
    if action == "list":
        key_or_none: bytes | None = (
            _resolve_proof_key(args.key) if args.key or args.with_signature else None
        )
        return _proof_list(
            Path(args.directory),
            key=key_or_none,
            as_json=bool(args.json),
        )
    if action == "index":
        out_path: Path | None = Path(args.out) if args.out else None
        return _proof_index(Path(args.directory), out=out_path)
    sys.stderr.write(f"ophamin proof: unknown action {action!r}\n")
    return 2


def _proof_show(path: Path) -> int:
    try:
        record = proof_codec.load(path)
    except ProofCodecError as exc:
        sys.stderr.write(f"ophamin proof show: {exc}\n")
        return 2
    print(record.to_markdown())
    return 0


def _proof_verify(path: Path, key: bytes) -> int:
    try:
        ok = proof_codec.verify_signature(path, key)
    except ProofCodecError as exc:
        sys.stderr.write(f"ophamin proof verify: {exc}\n")
        return 2
    if ok:
        print(f"OK: signature verifies for {path}")
        return 0
    print(f"FAIL: signature did NOT verify for {path}", file=sys.stderr)
    return 1


def _proof_validate(path: Path, key: bytes | None) -> int:
    try:
        report = proof_codec.validate(path, key=key)
    except ProofCodecError as exc:
        sys.stderr.write(f"ophamin proof validate: {exc}\n")
        return 2
    print(f"path:           {path}")
    print(f"schema_ok:      {report.schema_ok}")
    if report.schema_errors:
        print("schema_errors:")
        for err in report.schema_errors:
            print(f"  - {err}")
    print(f"record_ok:      {report.record_ok}")
    if report.record_problems:
        print("record_problems:")
        for prob in report.record_problems:
            print(f"  - {prob}")
    print(f"signature_ok:   {report.signature_ok}")
    print(f"all_ok:         {report.all_ok}")
    return 0 if report.all_ok else 1


def _proof_ingest(
    path: Path,
    *,
    key: bytes | None,
    strict_signature: bool,
    require_schema_version: str | None,
) -> int:
    try:
        record = proof_codec.ingest(
            path,
            key=key,
            strict_signature=strict_signature,
            require_schema_version=require_schema_version,
        )
    except ProofCodecError as exc:
        sys.stderr.write(f"ophamin proof ingest: {exc}\n")
        return 1
    print(f"OK: ingested {path}")
    print(f"  proof_id:        {record.proof_id}")
    print(f"  verdict:         {record.verdict.outcome}")
    print(f"  schema_version:  {record.schema_version}")
    print(f"  signature:       {'verified' if strict_signature else '(not strictly checked)'}")
    return 0


def _proof_index(directory: Path, *, out: Path | None) -> int:
    if not directory.is_dir():
        sys.stderr.write(f"ophamin proof index: {directory} is not a directory\n")
        return 2
    index = proof_codec.build_index(directory)
    markdown = index.to_markdown()
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        print(f"OK: wrote {out} ({index.total} entries, {index.n_decode_errors} errors)")
    else:
        print(markdown)
    return 0


def _proof_list(directory: Path, *, key: bytes | None, as_json: bool) -> int:
    if not directory.is_dir():
        sys.stderr.write(f"ophamin proof list: {directory} is not a directory\n")
        return 2
    entries = proof_codec.list_proofs(directory, key=key)
    if as_json:
        payload = [
            {
                "path": str(e.path),
                "proof_id": e.proof_id,
                "verdict": e.verdict,
                "schema_version": e.schema_version,
                "claim_statement": e.claim_statement,
                "signature_ok": e.signature_ok,
                "error": e.error,
            }
            for e in entries
        ]
        print(json.dumps(payload, indent=2))
        return 0
    if not entries:
        print(f"(no JSON files under {directory})")
        return 0
    sig_column = "  sig" if key is not None else ""
    print(f"{'verdict':<12} {'schema':<6}{sig_column}  path")
    print("-" * 80)
    for e in entries:
        if e.error:
            print(f"{'ERROR':<12} {'?':<6}{'    ?' if key is not None else ''}  {e.path}  ({e.error})")
            continue
        sig_cell = ""
        if key is not None:
            sig_cell = f"  {'ok' if e.signature_ok else 'NO':<3}"
        print(
            f"{e.verdict or '?':<12} {e.schema_version or '?':<6}{sig_cell}  {e.path}"
        )
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

    p_verify = sub.add_parser(
        "verify",
        help="self-check the install — required deps, optional extras, "
             "audit-pillar binaries, CLI subcommands",
    )
    p_verify.add_argument(
        "--kimera-repo", default="",
        help="optional path to a Kimera repo — runs a discovery probe to "
             "verify the adapter works end-to-end",
    )
    p_verify.add_argument(
        "--markdown", action="store_true",
        help="emit Markdown report instead of compact text",
    )
    p_verify.set_defaults(func=cmd_verify)

    p_mcp = sub.add_parser(
        "mcp",
        help="run the Ophamin Model Context Protocol server "
             "(exposes scenarios + signature operations to any MCP "
             "client — Claude Code, Claude Desktop, Cursor, custom agents)",
    )
    p_mcp_sub = p_mcp.add_subparsers(dest="mcp_cmd", required=True)
    p_mcp_serve = p_mcp_sub.add_parser(
        "serve",
        help="start the MCP server (stdio by default)",
    )
    p_mcp_serve.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable-http"],
        help="transport (default: stdio — what Claude Code expects)",
    )
    p_mcp_serve.add_argument(
        "--mount-path",
        default=None,
        help="optional mount path for sse / streamable-http transports",
    )
    p_mcp_serve.set_defaults(func=cmd_mcp_serve)

    p_drift = sub.add_parser(
        "drift-detect",
        help="run a per-stream online drift detector (River-backed) over a "
             "Kimera batch — extracts phi_value or walker_halt_amplitude_death "
             "rolling-fraction stream + emits a signed DriftScan",
    )
    p_drift.add_argument(
        "--repo", default="",
        help="path to Kimera repo (omit to use MockSubstrate)",
    )
    p_drift.add_argument(
        "--target", default="entity",
        help="adapter target (default: entity — full Takwin)",
    )
    p_drift.add_argument(
        "--n-cycles", type=int, default=100,
        help="number of cycles to run (default: 100)",
    )
    p_drift.add_argument(
        "--stimulus", default="A simple stimulus for the substrate to process.",
        help="stimulus text (replicated across all cycles)",
    )
    p_drift.add_argument(
        "--stream", default="phi",
        choices=["phi", "walker_halt"],
        help="which stream to extract: 'phi' (per-cycle Φ) or "
             "'walker_halt' (rolling fraction of amplitude_death halts)",
    )
    p_drift.add_argument(
        "--detector", default="adwin",
        choices=list(available_detectors()) or ["adwin"],
        help="drift detector backend (default: adwin)",
    )
    p_drift.add_argument(
        "--window", type=int, default=20,
        help="rolling window size for walker_halt stream (default: 20)",
    )
    p_drift.add_argument(
        "--out-dir", default="drift",
        help="directory to write the signed DriftScan JSON (default: drift/)",
    )
    p_drift.set_defaults(func=cmd_drift_detect)

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
        "--with-comparing", action="store_true",
        help="run a brief drift-detection probe on the primitive's phi stream "
             "(Move K)",
    )
    p_insp.add_argument(
        "--with-instrumenting", action="store_true",
        help="wrap the primitive's adapter in InstrumentedSubstrate to harvest "
             "per-cycle resource profile (Move K)",
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
        "--with-comparing", action="store_true",
        help="run a brief drift-detection probe per primitive (Move K)",
    )
    p_insp_all.add_argument(
        "--with-instrumenting", action="store_true",
        help="wrap each primitive's adapter in InstrumentedSubstrate (Move K)",
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

    # ophamin run-all — six-phase composite-run orchestrator
    p_runall = sub.add_parser(
        "run-all",
        help="run the 6-phase composite-run orchestrator (seeing / "
             "measuring / comparing / instrumenting / auditing / reporting) "
             "and emit a signed CampaignRecord",
    )
    p_runall.add_argument(
        "--repo",
        default="",
        help="path to a Kimera repo (default: MockSubstrate — no Kimera needed)",
    )
    p_runall.add_argument(
        "--target",
        default="entity",
        help="adapter target when --repo is set (default: entity = full Takwin)",
    )
    p_runall.add_argument(
        "--scenarios",
        default="",
        help="comma-separated list of scenario names to run in the measuring "
             "phase (default: every default-instantiable registered scenario)",
    )
    p_runall.add_argument(
        "--skip",
        default="",
        help="comma-separated list of phases to skip "
             "(seeing,measuring,comparing,instrumenting,auditing,reporting)",
    )
    p_runall.add_argument(
        "--out-dir",
        default="campaigns/latest",
        help="directory for per-phase artifacts + final CAMPAIGN.json "
             "(default: campaigns/latest)",
    )
    p_runall.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the per-phase Markdown summary on stdout (still "
             "writes CAMPAIGN.json + REPORT.md to --out-dir)",
    )
    p_runall.add_argument(
        "--fwer-method",
        default="holm",
        choices=["holm", "bh", "none"],
        help="multiplicity-correction method applied during the comparing "
             "phase (default: holm = strict family-wise error rate control). "
             "Set to 'none' to disable (raw verdicts only). New in 0.9.0.",
    )
    p_runall.add_argument(
        "--fwer-alpha",
        type=float,
        default=0.05,
        help="family-wise / FDR threshold (default: 0.05)",
    )
    p_runall.set_defaults(func=cmd_run_all)

    # ophamin summarize — campaign-level synthesis over a proof corpus
    p_sum = sub.add_parser(
        "summarize",
        help="walk a proof directory; emit a campaign-level summary "
             "(by-verdict + by-family + per-substrate-commit + verdict-flips)",
    )
    p_sum.add_argument("directory", help="directory to walk recursively")
    p_sum.add_argument(
        "--out",
        default="",
        help="optional output path (default: print to stdout)",
    )
    p_sum.add_argument(
        "--json", action="store_true",
        help="emit JSON instead of the human-readable Markdown",
    )
    p_sum.set_defaults(func=cmd_summarize)

    # ophamin correct — ad-hoc multiplicity correction over a proofs dir
    p_correct = sub.add_parser(
        "correct",
        help="apply multiplicity correction (Holm / BH) to every signed "
             "proof under a directory; emit a corrected-verdicts report",
    )
    p_correct.add_argument("directory", help="directory to walk recursively")
    p_correct.add_argument(
        "--method",
        default="holm",
        choices=["holm", "bh", "none"],
        help="correction method (default: holm)",
    )
    p_correct.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="family-wise / FDR threshold (default: 0.05)",
    )
    p_correct.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of Markdown",
    )
    p_correct.add_argument(
        "--out",
        default="",
        help="optional output path (default: print to stdout)",
    )
    p_correct.set_defaults(func=cmd_correct)

    # ophamin diagnose — per-record diagnostic
    p_diag = sub.add_parser(
        "diagnose",
        help="per-record diagnostic — verdict + siblings + comparison",
    )
    p_diag.add_argument("path", help="path to one proof JSON")
    p_diag.add_argument(
        "--corpus-dir",
        default="",
        help="optional broader corpus directory for sibling detection "
             "(default: the proof's containing directory)",
    )
    p_diag.add_argument(
        "--json", action="store_true",
        help="emit JSON instead of the human-readable Markdown",
    )
    p_diag.set_defaults(func=cmd_diagnose)

    # ophamin analyze — per-metric trajectory across a corpus
    p_anl = sub.add_parser(
        "analyze",
        help="walk a corpus; extract every PillarEvidence value for one "
             "metric; emit trajectory + summary statistics",
    )
    p_anl.add_argument("metric", help="statistic name to extract (e.g. gwf_false_positive_rate)")
    p_anl.add_argument(
        "--across",
        dest="directory",
        required=True,
        help="directory to walk for proof records",
    )
    p_anl.add_argument(
        "--json", action="store_true",
        help="emit JSON instead of the human-readable Markdown",
    )
    p_anl.set_defaults(func=cmd_analyze)

    # ophamin api-stability — Phase E8 stability-tier listing + audit
    p_api = sub.add_parser(
        "api-stability",
        help="list every annotated public symbol by tier, or check a user "
             "codebase for imports of @Deprecated / @Internal Ophamin symbols",
    )
    api_sub = p_api.add_subparsers(dest="subcommand", required=True)

    p_api_list = api_sub.add_parser(
        "list",
        help="print every annotated symbol grouped by stability tier",
    )
    p_api_list.add_argument(
        "--json", action="store_true",
        help="emit JSON instead of the human-readable Markdown",
    )
    p_api_list.set_defaults(func=cmd_api_stability)

    p_api_check = api_sub.add_parser(
        "check",
        help="audit a directory of Python files for imports of "
             "@Deprecated / @Internal Ophamin symbols; exit 1 if any found",
    )
    p_api_check.add_argument(
        "directory",
        help="root directory of the user codebase to audit",
    )
    p_api_check.add_argument(
        "--json", action="store_true",
        help="emit JSON instead of human-readable rows",
    )
    p_api_check.set_defaults(func=cmd_api_stability)

    # ophamin report-batch — campaign-level rendering across a directory
    p_rb = sub.add_parser(
        "report-batch",
        help="render every signed record under a directory + emit an "
             "INDEX.md (Move M — campaign-level reporting surface)",
    )
    p_rb.add_argument("records_dir", help="directory of proof / audit JSON files")
    p_rb.add_argument(
        "--format", default="markdown",
        choices=["html", "markdown", "latex"],
        help="output format (default: markdown)",
    )
    p_rb.add_argument(
        "--out-dir", default="reports/batch",
        help="directory to write the rendered outputs (default: reports/batch/)",
    )
    p_rb.set_defaults(func=cmd_report_batch)

    # ophamin watch-proofs — before/after regression alert
    p_wp = sub.add_parser(
        "watch-proofs",
        help="compare two proof-corpus snapshots; emit a signed "
             "RegressionAlertRecord (exit 1 if any regression detected)",
    )
    p_wp.add_argument("--before", required=True, help="proof corpus snapshot at the prior commit")
    p_wp.add_argument("--after", required=True, help="proof corpus snapshot at the new commit")
    p_wp.add_argument("--out", default="", help="optional output path for the signed alert JSON")
    p_wp.add_argument("--key", default="", help="HMAC sign key (default: built-in DEFAULT_SIGN_KEY)")
    p_wp.add_argument("--no-sign", action="store_true", help="emit the alert unsigned")
    p_wp.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    p_wp.set_defaults(func=cmd_watch_proofs)

    # ophamin audit-record — umbrella for the AuditRecord codec surface
    p_ar = sub.add_parser(
        "audit-record",
        help="audit-record codec — show / verify / validate / ingest / list "
             "(Move H — parallel to `ophamin proof`)",
    )
    ar_sub = p_ar.add_subparsers(
        dest="audit_action",
        metavar="action",
        required=True,
    )
    p_ar_show = ar_sub.add_parser("show", help="render an AuditRecord as Markdown")
    p_ar_show.add_argument("path")
    p_ar_show.set_defaults(func=cmd_audit_record)

    p_ar_verify = ar_sub.add_parser("verify", help="HMAC-verify an AuditRecord")
    p_ar_verify.add_argument("path")
    p_ar_verify.add_argument("--key", default="default")
    p_ar_verify.set_defaults(func=cmd_audit_record)

    p_ar_validate = ar_sub.add_parser("validate", help="structural + optional signature check")
    p_ar_validate.add_argument("path")
    p_ar_validate.add_argument("--with-signature", action="store_true")
    p_ar_validate.add_argument("--key", default="")
    p_ar_validate.set_defaults(func=cmd_audit_record)

    p_ar_ingest = ar_sub.add_parser("ingest", help="full-validate pipeline; loud-fail")
    p_ar_ingest.add_argument("path")
    p_ar_ingest.add_argument("--strict-signature", action="store_true")
    p_ar_ingest.add_argument("--key", default="")
    p_ar_ingest.set_defaults(func=cmd_audit_record)

    p_ar_list = ar_sub.add_parser("list", help="walk a directory; one row per audit JSON")
    p_ar_list.add_argument("directory")
    p_ar_list.add_argument("--with-signature", action="store_true")
    p_ar_list.add_argument("--key", default="")
    p_ar_list.add_argument("--json", action="store_true")
    p_ar_list.set_defaults(func=cmd_audit_record)

    # ophamin corpus — umbrella for the corpus-registry discovery surface
    p_cor = sub.add_parser(
        "corpus",
        help="corpus registry — list / show registered corpora (Move N)",
    )
    cor_sub = p_cor.add_subparsers(
        dest="corpus_action", metavar="action", required=True,
    )
    p_cor_list = cor_sub.add_parser("list", help="print every registered corpus + availability")
    p_cor_list.add_argument("--json", action="store_true")
    p_cor_list.set_defaults(func=cmd_corpus)
    p_cor_show = cor_sub.add_parser("show", help="print one corpus's metadata + availability")
    p_cor_show.add_argument("name")
    p_cor_show.set_defaults(func=cmd_corpus)

    # ophamin substrate — umbrella for the SubstrateProbe registry
    p_sub_s = sub.add_parser(
        "substrate",
        help="substrate registry — list registered SubstrateProbe classes (Move N)",
    )
    sub_s_sub = p_sub_s.add_subparsers(
        dest="substrate_action", metavar="action", required=True,
    )
    p_sub_list = sub_s_sub.add_parser("list", help="print every registered substrate class")
    p_sub_list.add_argument("--json", action="store_true")
    p_sub_list.set_defaults(func=cmd_substrate)

    # ophamin pillar — umbrella for the pillar-registry discovery surface
    p_pil = sub.add_parser(
        "pillar",
        help="pillar registry — list / show metadata for every registered pillar",
    )
    pil_sub = p_pil.add_subparsers(
        dest="pillar_action",
        metavar="action",
        required=True,
    )
    p_pil_list = pil_sub.add_parser(
        "list",
        help="print every registered pillar (name + library + version)",
    )
    p_pil_list.add_argument(
        "--json", action="store_true",
        help="emit JSON instead of the human-readable table",
    )
    p_pil_list.set_defaults(func=cmd_pillar)

    p_pil_show = pil_sub.add_parser(
        "show",
        help="print the full metadata block for one pillar",
    )
    p_pil_show.add_argument("name", help="pillar name (e.g. O.spc, M.mixed_effects)")
    p_pil_show.set_defaults(func=cmd_pillar)

    # ophamin scenario — umbrella for the scenario-registry discovery surface
    p_scen = sub.add_parser(
        "scenario",
        help="scenario registry — list / show metadata for every registered scenario",
    )
    scen_sub = p_scen.add_subparsers(
        dest="scenario_action",
        metavar="action",
        required=True,
    )

    p_scen_list = scen_sub.add_parser(
        "list",
        help="print every registered scenario (name + tier + family + goal)",
    )
    p_scen_list.add_argument(
        "--tier",
        default="",
        help="filter to one tier (scientific / engineering / philosophical "
             "/ empirical_deep / measurement_machinery)",
    )
    p_scen_list.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of the human-readable table",
    )
    p_scen_list.set_defaults(func=cmd_scenario)

    p_scen_show = scen_sub.add_parser(
        "show",
        help="print the full metadata block for one scenario",
    )
    p_scen_show.add_argument("name", help="scenario name (e.g. memory-as-deformation)")
    p_scen_show.set_defaults(func=cmd_scenario)

    p_scen_info = scen_sub.add_parser(
        "info",
        help="alias for `show`",
    )
    p_scen_info.add_argument("name", help="scenario name")
    p_scen_info.set_defaults(func=cmd_scenario)

    # ophamin schema — umbrella for the cross-record schema surface (Phase L4)
    p_schema = sub.add_parser(
        "schema",
        help="signed-record schema policy — list / info / validate across every codec",
    )
    schema_sub = p_schema.add_subparsers(
        dest="schema_action",
        metavar="action",
        required=True,
    )
    p_schema_list = schema_sub.add_parser(
        "list",
        help="print every documented schema name + current version",
    )
    p_schema_list.set_defaults(func=cmd_schema)

    p_schema_info = schema_sub.add_parser(
        "info",
        help="detect the schema kind + version of one record file",
    )
    p_schema_info.add_argument("path", help="path to record JSON file")
    p_schema_info.set_defaults(func=cmd_schema)

    p_schema_validate = schema_sub.add_parser(
        "validate",
        help="validate one file or a directory tree of signed records",
    )
    p_schema_validate.add_argument(
        "path",
        help="path to record JSON file or directory (with --recursive)",
    )
    p_schema_validate.add_argument(
        "--key",
        default="",
        help="HMAC key for signature verification (omit to skip)",
    )
    p_schema_validate.add_argument(
        "--allow-any-schema-version",
        action="store_true",
        help="allow major-version mismatch — forensic use only",
    )
    p_schema_validate.add_argument(
        "--recursive",
        action="store_true",
        help="when path is a directory, scan all *.json files under it",
    )
    p_schema_validate.set_defaults(func=cmd_schema)

    # ophamin proof — umbrella for the proof-record codec surface
    p_proof = sub.add_parser(
        "proof",
        help="proof-record codec — show / verify / validate / ingest / list",
    )
    proof_sub = p_proof.add_subparsers(
        dest="proof_action",
        metavar="action",
        required=True,
    )

    p_proof_show = proof_sub.add_parser(
        "show",
        help="pretty-print a signed proof record (renders to Markdown)",
    )
    p_proof_show.add_argument("path", help="path to the proof JSON")
    p_proof_show.set_defaults(func=cmd_proof)

    p_proof_verify = proof_sub.add_parser(
        "verify",
        help="HMAC-verify a signed proof under a key",
    )
    p_proof_verify.add_argument("path", help="path to the proof JSON")
    p_proof_verify.add_argument(
        "--key",
        default="default",
        help="HMAC key (UTF-8 string; default: framework's DEFAULT_SIGN_KEY)",
    )
    p_proof_verify.set_defaults(func=cmd_proof)

    p_proof_validate = proof_sub.add_parser(
        "validate",
        help="JSON-Schema + structural + (optional) signature validation",
    )
    p_proof_validate.add_argument("path", help="path to the proof JSON")
    p_proof_validate.add_argument(
        "--with-signature",
        action="store_true",
        help="also verify the HMAC signature under --key (or DEFAULT_SIGN_KEY)",
    )
    p_proof_validate.add_argument(
        "--key",
        default="",
        help="HMAC key for the signature check (default: built-in)",
    )
    p_proof_validate.set_defaults(func=cmd_proof)

    p_proof_ingest = proof_sub.add_parser(
        "ingest",
        help="full pipeline (load + schema + structural + optional signature); "
             "loud failure on any problem",
    )
    p_proof_ingest.add_argument("path", help="path to the proof JSON")
    p_proof_ingest.add_argument(
        "--strict-signature",
        action="store_true",
        help="require the signature to verify under --key (or DEFAULT_SIGN_KEY) "
             "or raise loud",
    )
    p_proof_ingest.add_argument(
        "--key",
        default="",
        help="HMAC key for signature check (default: framework's DEFAULT_SIGN_KEY)",
    )
    p_proof_ingest.add_argument(
        "--require-schema-version",
        default="",
        help=(
            "required proof-record schema version "
            f"(default: current = {proof_codec.SCHEMA_VERSION}); pass "
            "--allow-any-schema-version to opt out of the version gate"
        ),
    )
    p_proof_ingest.add_argument(
        "--allow-any-schema-version",
        action="store_true",
        help="accept proofs of any schema version (e.g. for migration tooling)",
    )
    p_proof_ingest.set_defaults(func=cmd_proof)

    p_proof_index = proof_sub.add_parser(
        "index",
        help="generate INDEX.md master manifest from a proof directory",
    )
    p_proof_index.add_argument(
        "directory", help="directory to index recursively"
    )
    p_proof_index.add_argument(
        "--out",
        default="",
        help="optional output path for the rendered Markdown (default: print "
             "to stdout; conventional location: <directory>/INDEX.md)",
    )
    p_proof_index.set_defaults(func=cmd_proof)

    p_proof_list = proof_sub.add_parser(
        "list",
        help="walk a directory; emit one summary row per proof JSON found",
    )
    p_proof_list.add_argument(
        "directory", help="directory to walk recursively for *.json files"
    )
    p_proof_list.add_argument(
        "--with-signature",
        action="store_true",
        help="also report signature verification under --key (or DEFAULT_SIGN_KEY)",
    )
    p_proof_list.add_argument(
        "--key",
        default="",
        help="HMAC key for signature check (default: built-in)",
    )
    p_proof_list.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of the human-readable table",
    )
    p_proof_list.set_defaults(func=cmd_proof)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    rc: int = args.func(args)
    return rc


if __name__ == "__main__":
    sys.exit(main())
