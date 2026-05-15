"""Massive-dataset corpus connectors — the four real open-source datasets.

Each connector locates its downloaded raw data, streams it as ``CorpusRecord``
objects, and content-addresses it. None of them load the whole corpus into
memory — Enron is ~500k emails, the Linux kernel ~1.4M commits.
"""

from __future__ import annotations

import csv
import email
import hashlib
import io
import json
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ophamin.seeing.corpus.base import Corpus, CorpusRecord, CorpusUnavailableError


class EnronCorpus(Corpus):
    """The Enron email corpus — ~500k real executive emails (CMU release).

    Streamed directly from the ``.tar.gz`` — no 500k-file extraction needed.
    """

    name = "enron-email-corpus"
    kind = "email_corpus"
    source = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"

    @property
    def _archive(self) -> Path:
        return self.root / "enron_mail_20150507.tar.gz"

    def is_available(self) -> bool:
        return self._archive.is_file()

    def _compute_content_hash(self) -> str:
        return self._hash_file(self._archive)

    def _compute_count(self) -> int:
        n = 0
        with tarfile.open(self._archive, "r:gz") as tf:
            for member in tf:
                if member.isfile():
                    n += 1
        return n

    @staticmethod
    def _body(message: email.message.Message) -> str:
        if message.is_multipart():
            parts = [
                p.get_payload(decode=True)
                for p in message.walk()
                if p.get_content_type() == "text/plain"
            ]
            raw = b"\n".join(p for p in parts if p)
        else:
            payload = message.get_payload(decode=True)
            raw = payload if isinstance(payload, bytes) else b""
        return raw.decode("utf-8", errors="replace")

    def records(self) -> Iterator[CorpusRecord]:
        self.require_available()
        with tarfile.open(self._archive, "r:gz") as tf:
            for member in tf:
                if not member.isfile():
                    continue
                handle = tf.extractfile(member)
                if handle is None:
                    continue
                try:
                    message = email.message_from_bytes(handle.read())
                except Exception:
                    continue
                yield CorpusRecord(
                    id=member.name,
                    text=self._body(message),
                    metadata={
                        "from": message.get("From", ""),
                        "to": message.get("To", ""),
                        "date": message.get("Date", ""),
                        "subject": message.get("Subject", ""),
                    },
                )


class LinuxKernelCorpus(Corpus):
    """The Linux kernel commit history — ~1.4M commit messages (blobless bare clone)."""

    name = "linux-kernel-commits"
    kind = "commit_corpus"
    source = "https://github.com/torvalds/linux.git"

    @property
    def _repo(self) -> Path:
        return self.root / "linux.git"

    def is_available(self) -> bool:
        return (self._repo / "HEAD").is_file()

    def _git(self, *args: str, timeout: float = 600.0) -> str:
        result = subprocess.run(
            ["git", "-C", str(self._repo), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed in {self._repo}: {result.stderr.strip()}"
            )
        return result.stdout

    def _compute_content_hash(self) -> str:
        head = self._git("rev-parse", "HEAD").strip()
        count = self._git("rev-list", "--count", "HEAD").strip()
        return hashlib.sha256(f"{head}:{count}".encode("utf-8")).hexdigest()

    def _compute_count(self) -> int:
        return int(self._git("rev-list", "--count", "HEAD").strip())

    def records(self) -> Iterator[CorpusRecord]:
        self.require_available()
        # unit separator \x1f between fields, record separator \x1e between commits
        proc = subprocess.Popen(
            [
                "git",
                "-C",
                str(self._repo),
                "log",
                "--format=%H%x1f%an%x1f%aI%x1f%s%x1f%b%x1e",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None
        buffer = ""
        try:
            for line in proc.stdout:
                buffer += line
                while "\x1e" in buffer:
                    raw, buffer = buffer.split("\x1e", 1)
                    raw = raw.strip("\n")
                    if not raw:
                        continue
                    parts = raw.split("\x1f")
                    if len(parts) < 5:
                        continue
                    sha, author, date, subject, body = parts[:5]
                    yield CorpusRecord(
                        id=sha,
                        text=(subject + "\n\n" + body).strip(),
                        metadata={"author": author, "date": date, "subject": subject},
                    )
        finally:
            proc.stdout.close()
            proc.wait()


class FloresCorpus(Corpus):
    """FLORES-200 — sentence-aligned parallel text across ~200 languages.

    In ``aligned`` mode (the default) each record is one sentence with its
    translations into every language — the natural unit for the Rosetta
    scaling test. In flat mode each record is a single (language, sentence).
    """

    name = "flores-200"
    kind = "parallel_corpus"
    source = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"

    def __init__(self, root, split: str = "dev", aligned: bool = True) -> None:
        super().__init__(root)
        self.split = split
        self.aligned = aligned

    @property
    def _split_dir(self) -> Path:
        return self.root / "flores200_dataset" / self.split

    def is_available(self) -> bool:
        return self._split_dir.is_dir()

    def _lang_files(self) -> list[Path]:
        return sorted(self._split_dir.glob(f"*.{self.split}"))

    def _compute_content_hash(self) -> str:
        entries = [(f.name, self._hash_file(f)) for f in self._lang_files()]
        return hashlib.sha256(repr(entries).encode("utf-8")).hexdigest()

    def _compute_count(self) -> int:
        files = self._lang_files()
        if not files:
            return 0
        if self.aligned:
            with open(files[0], encoding="utf-8") as fh:
                return sum(1 for _ in fh)
        total = 0
        for f in files:
            with open(f, encoding="utf-8") as fh:
                total += sum(1 for _ in fh)
        return total

    def records(self) -> Iterator[CorpusRecord]:
        self.require_available()
        files = self._lang_files()
        if not files:
            return
        langs = [f.name.rsplit(".", 1)[0] for f in files]
        if not self.aligned:
            for lang, f in zip(langs, files):
                with open(f, encoding="utf-8") as fh:
                    for i, line in enumerate(fh):
                        yield CorpusRecord(
                            id=f"flores-{self.split}-{lang}-{i}",
                            text=line.rstrip("\n"),
                            metadata={"language": lang},
                        )
            return
        handles = [open(f, encoding="utf-8") for f in files]
        try:
            for i, lines in enumerate(zip(*handles)):
                translations = {
                    lang: line.rstrip("\n") for lang, line in zip(langs, lines)
                }
                anchor = translations.get("eng_Latn") or next(iter(translations.values()))
                yield CorpusRecord(
                    id=f"flores-{self.split}-{i}",
                    text=anchor,
                    metadata={"translations": translations, "n_languages": len(langs)},
                )
        finally:
            for handle in handles:
                handle.close()


@dataclass(frozen=True)
class _Source:
    """One sub-corpus within the offensive-security corpus."""

    name: str
    rel_path: str              # directory under data/raw
    globs: tuple[str, ...]
    mode: str                  # "file" | "line" | "tabular"


class OffensiveSecurityCorpus(Corpus):
    """State-of-the-art open-source offensive-security payloads, as an input corpus.

    Combines, as *text* records streamed through the substrate's threat
    detector (read, never executed):

        metasploit            Metasploit Framework modules (.rb)
        prompt_injection      deepset / jackhhao prompt-injection & jailbreak sets
        seclists-fuzzing      SecLists fuzzing strings        (one payload per line)
        seclists-payloads     SecLists attack payloads        (one payload per line)
        payloadsallthethings  PayloadsAllTheThings curated exploitation payloads
        nuclei-templates      ProjectDiscovery vulnerability-detection templates
        atomic-red-team       MITRE ATT&CK-mapped adversary-emulation tests
        exploitdb             the Exploit-DB exploit corpus
        garak                 NVIDIA garak LLM red-teaming probe data

    ``root`` is the shared ``data/raw`` directory. A source whose directory is
    absent is transparently excluded — never silently substituted;
    ``included_sources()`` reports exactly what is in the corpus, and the
    content hash and record count cover exactly those.
    """

    name = "offensive-security-corpus"
    kind = "adversarial_corpus"
    source = (
        "metasploit-framework + SecLists + PayloadsAllTheThings + nuclei-templates "
        "+ atomic-red-team + exploit-db + garak + prompt-injection / jailbreak sets"
    )

    _SOURCES = (
        _Source("metasploit", "metasploit/metasploit-framework/modules", ("**/*.rb",), "file"),
        _Source("prompt_injection", "prompt_injection", ("**/*.parquet", "**/*.csv"), "tabular"),
        _Source("seclists-fuzzing", "offensive_security/SecLists/Fuzzing", ("**/*.txt",), "line"),
        _Source("seclists-payloads", "offensive_security/SecLists/Payloads", ("**/*.txt",), "line"),
        _Source("payloadsallthethings", "offensive_security/PayloadsAllTheThings", ("**/*.md",), "file"),
        _Source("nuclei-templates", "offensive_security/nuclei-templates", ("**/*.yaml",), "file"),
        _Source("atomic-red-team", "offensive_security/atomic-red-team/atomics", ("**/*.yaml",), "file"),
        _Source("exploitdb", "offensive_security/exploitdb/exploits", ("**/*",), "file"),
        _Source("garak", "offensive_security/garak/garak/data", ("**/*",), "file"),
    )

    _TEXT_COLUMNS = ("text", "prompt", "Prompt", "sentence", "content")
    _LABEL_COLUMNS = ("label", "type", "Type", "class", "jailbreak")

    def _source_dir(self, src: _Source) -> Path:
        return self.root / src.rel_path

    def included_sources(self) -> list[str]:
        """The source names whose raw data is present — transparent, never silent."""
        return [
            s.name
            for s in self._SOURCES
            if self._source_dir(s).is_dir() and any(self._source_dir(s).iterdir())
        ]

    def is_available(self) -> bool:
        return len(self.included_sources()) > 0

    def _source_files(self, src: _Source) -> list[Path]:
        base = self._source_dir(src)
        files: set[Path] = set()
        for pattern in src.globs:
            files.update(p for p in base.glob(pattern) if p.is_file())
        return sorted(files)

    def _attack_class(self, src: _Source, path: Path) -> str:
        try:
            rel = path.relative_to(self._source_dir(src))
        except ValueError:
            return src.name
        return rel.parts[0].lower() if len(rel.parts) > 1 else src.name

    def _git_head(self, start: Path) -> str | None:
        """Walk up from ``start`` to a git repo; return its HEAD sha (a Merkle hash)."""
        cur = start
        for _ in range(8):
            if (cur / ".git").exists():
                try:
                    out = subprocess.run(
                        ["git", "-C", str(cur), "rev-parse", "HEAD"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    return None
                return out.stdout.strip() if out.returncode == 0 else None
            if cur.parent == cur:
                break
            cur = cur.parent
        return None

    def _source_identifier(self, src: _Source) -> str:
        """Content identifier for a source — the git HEAD sha if it is a repo,
        else a hash over its file list + per-file content hashes."""
        head = self._git_head(self._source_dir(src))
        if head:
            return f"git:{head}"
        entries = [
            (str(f.relative_to(self.root)), self._hash_file(f))
            for f in self._source_files(src)
        ]
        return "files:" + hashlib.sha256(repr(entries).encode("utf-8")).hexdigest()

    def _compute_content_hash(self) -> str:
        parts = sorted(
            (s.name, self._source_identifier(s))
            for s in self._SOURCES
            if self._source_dir(s).is_dir()
        )
        return hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()

    def _tabular_frames(self, src: _Source):
        import pandas as pd

        for f in self._source_files(src):
            try:
                df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
            except Exception:
                continue
            text_col = next((c for c in self._TEXT_COLUMNS if c in df.columns), None)
            if text_col is None:
                text_col = next((c for c in df.columns if df[c].dtype == object), None)
            if text_col is None:
                continue
            label_col = next((c for c in self._LABEL_COLUMNS if c in df.columns), None)
            yield f, df, text_col, label_col

    def _compute_count(self) -> int:
        total = 0
        for src in self._SOURCES:
            if not self._source_dir(src).is_dir():
                continue
            if src.mode == "file":
                total += len(self._source_files(src))
            elif src.mode == "line":
                for f in self._source_files(src):
                    try:
                        with open(f, encoding="utf-8", errors="replace") as fh:
                            total += sum(1 for line in fh if line.strip())
                    except OSError:
                        continue
            elif src.mode == "tabular":
                for _f, df, _t, _l in self._tabular_frames(src):
                    total += len(df)
        return total

    def _records_for_source(self, src: _Source) -> Iterator[CorpusRecord]:
        if not self._source_dir(src).is_dir():
            return
        if src.mode == "file":
            for f in self._source_files(src):
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if not text.strip():
                    continue
                rel = f.relative_to(self.root)
                yield CorpusRecord(
                    id=f"{src.name}:{rel}",
                    text=text,
                    metadata={
                        "origin": "offensive_security",
                        "source": src.name,
                        "attack_class": self._attack_class(src, f),
                        "file": str(rel),
                    },
                )
        elif src.mode == "line":
            for f in self._source_files(src):
                rel = f.relative_to(self.root)
                attack_class = self._attack_class(src, f)
                try:
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        for lineno, line in enumerate(fh):
                            payload = line.rstrip("\n")
                            if not payload.strip():
                                continue
                            yield CorpusRecord(
                                id=f"{src.name}:{rel}:{lineno}",
                                text=payload,
                                metadata={
                                    "origin": "offensive_security",
                                    "source": src.name,
                                    "attack_class": attack_class,
                                    "file": str(rel),
                                },
                            )
                except OSError:
                    continue
        elif src.mode == "tabular":
            for f, df, text_col, label_col in self._tabular_frames(src):
                rel = f.relative_to(self.root)
                for i, row in df.iterrows():
                    text = row[text_col]
                    if not isinstance(text, str) or not text.strip():
                        continue
                    meta = {
                        "origin": "offensive_security",
                        "source": src.name,
                        "file": str(rel),
                    }
                    if label_col is not None:
                        meta["label"] = str(row[label_col])
                    yield CorpusRecord(
                        id=f"{src.name}:{rel}:{i}", text=text, metadata=meta
                    )

    def records(self) -> Iterator[CorpusRecord]:
        self.require_available()
        for src in self._SOURCES:
            yield from self._records_for_source(src)

    def records_from(self, source_name: str) -> Iterator[CorpusRecord]:
        """Stream just one named sub-source (e.g. ``prompt_injection``).

        Efficient targeted access — does not iterate the whole corpus.
        """
        self.require_available()
        names = [s.name for s in self._SOURCES]
        if source_name not in names:
            raise ValueError(f"unknown source {source_name!r}; have {names}")
        for src in self._SOURCES:
            if src.name == source_name:
                yield from self._records_for_source(src)
                return


class FinancialCorpus(Corpus):
    """Open-source market & macroeconomic data, as an input corpus.

    Feeds Kimera's market Piovra arm. ``root`` is ``data/raw/financial``.
    Aggregates, transparently (``included_sources()`` reports what is present):

        fred         FRED macro-cycle series — GDP, CPI, yield curve, fed funds…
        worldbank    World Bank WDI development indicators (via the WB API)
        phrasebank   Financial PhraseBank — sentiment-labelled financial sentences
        sec_edgar    SEC EDGAR DERA Financial Statement Data Sets (submissions)
        uspto        USPTO / PatentsView bulk patent table (titles, dates, types)

    Records are heterogeneous: macro/market data points are streamed as ticks
    (text rendering + numeric value in metadata); PhraseBank / filings / patents
    are streamed as text.
    """

    name = "financial-corpus"
    kind = "financial_corpus"
    source = (
        "FRED (St. Louis Fed) + World Bank Open Data + Financial PhraseBank "
        "+ SEC EDGAR DERA datasets + USPTO PatentsView"
    )

    _SOURCES = (
        _Source("fred", "fred", ("*.csv",), "fred-series"),
        _Source("worldbank", "worldbank", ("*.json",), "worldbank-json"),
        _Source("phrasebank", "phrasebank/data", ("*.zip",), "phrasebank-zip"),
        _Source("sec_edgar", "sec_edgar", ("*.zip",), "edgar-submissions"),
        _Source("uspto", "uspto", ("g_patent.tsv.zip",), "patent-tsv"),
    )

    def _source_dir(self, src: _Source) -> Path:
        return self.root / src.rel_path

    def included_sources(self) -> list[str]:
        return [
            s.name
            for s in self._SOURCES
            if self._source_dir(s).is_dir() and any(self._source_dir(s).iterdir())
        ]

    def is_available(self) -> bool:
        return len(self.included_sources()) > 0

    def _source_files(self, src: _Source) -> list[Path]:
        base = self._source_dir(src)
        files: set[Path] = set()
        for pattern in src.globs:
            files.update(p for p in base.glob(pattern) if p.is_file())
        return sorted(files)

    def _compute_content_hash(self) -> str:
        parts = []
        for src in self._SOURCES:
            if not self._source_dir(src).is_dir():
                continue
            entries = [
                (str(f.relative_to(self.root)), self._hash_file(f))
                for f in self._source_files(src)
            ]
            parts.append((src.name, entries))
        return hashlib.sha256(repr(sorted(parts)).encode("utf-8")).hexdigest()

    def _compute_count(self) -> int:
        return sum(1 for _ in self.records())

    # -- per-source extractors ---------------------------------------------

    def _fred_records(self, src: _Source) -> Iterator[CorpusRecord]:
        for f in self._source_files(src):
            series = f.stem
            try:
                with open(f, encoding="utf-8", errors="replace", newline="") as fh:
                    reader = csv.reader(fh)
                    header = next(reader, None)
                    if not header or len(header) < 2:
                        continue
                    for row in reader:
                        if len(row) < 2 or not row[0]:
                            continue
                        date, raw = row[0], row[1]
                        try:
                            value = float(raw)
                        except ValueError:
                            continue
                        yield CorpusRecord(
                            id=f"fred:{series}:{date}",
                            text=f"{series} {date} {value}",
                            metadata={
                                "source": "fred",
                                "series": series,
                                "date": date,
                                "value": value,
                                "kind": "macro_series_tick",
                            },
                        )
            except OSError:
                continue

    def _worldbank_records(self, src: _Source) -> Iterator[CorpusRecord]:
        for f in self._source_files(src):
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            code = payload.get("indicator", f.stem)
            name = payload.get("name", code)
            for obs in payload.get("observations", []):
                value = obs.get("value")
                if value is None:
                    continue
                country = (obs.get("country") or {}).get("value", "")
                date = obs.get("date", "")
                yield CorpusRecord(
                    id=f"worldbank:{code}:{country}:{date}",
                    text=f"{name} {country} {date} {value}",
                    metadata={
                        "source": "worldbank",
                        "indicator": code,
                        "country": country,
                        "date": date,
                        "value": float(value),
                        "kind": "macro_series_tick",
                    },
                )

    def _phrasebank_records(self, src: _Source) -> Iterator[CorpusRecord]:
        for archive in self._source_files(src):
            try:
                zf = zipfile.ZipFile(archive)
            except (OSError, zipfile.BadZipFile):
                continue
            with zf:
                members = [m for m in zf.namelist() if m.endswith(".txt") and "Sentences_" in m]
                preferred = [m for m in members if "50Agree" in m] or members
                for member in preferred[:1]:
                    agreement = member.rsplit("/", 1)[-1].replace(".txt", "")
                    with zf.open(member) as raw:
                        for i, line in enumerate(
                            io.TextIOWrapper(raw, encoding="latin-1")
                        ):
                            line = line.rstrip("\n")
                            if "@" not in line:
                                continue
                            sentence, _, sentiment = line.rpartition("@")
                            if not sentence.strip():
                                continue
                            yield CorpusRecord(
                                id=f"phrasebank:{agreement}:{i}",
                                text=sentence.strip(),
                                metadata={
                                    "source": "phrasebank",
                                    "sentiment": sentiment.strip(),
                                    "agreement": agreement,
                                    "kind": "sentiment_sentence",
                                },
                            )

    def _edgar_records(self, src: _Source) -> Iterator[CorpusRecord]:
        for archive in self._source_files(src):
            try:
                zf = zipfile.ZipFile(archive)
            except (OSError, zipfile.BadZipFile):
                continue
            with zf:
                if "sub.txt" not in zf.namelist():
                    continue
                with zf.open("sub.txt") as raw:
                    reader = csv.DictReader(
                        io.TextIOWrapper(raw, encoding="utf-8", errors="replace"),
                        delimiter="\t",
                    )
                    for row in reader:
                        company = row.get("name", "")
                        form = row.get("form", "")
                        period = row.get("period", "")
                        adsh = row.get("adsh", "")
                        if not adsh:
                            continue
                        yield CorpusRecord(
                            id=f"edgar:{adsh}",
                            text=f"{company} filed {form} for period {period}",
                            metadata={
                                "source": "sec_edgar",
                                "cik": row.get("cik", ""),
                                "company": company,
                                "form": form,
                                "period": period,
                                "filed": row.get("filed", ""),
                                "quarter": archive.stem,
                                "kind": "filing_submission",
                            },
                        )

    def _patent_records(self, src: _Source) -> Iterator[CorpusRecord]:
        for archive in self._source_files(src):
            try:
                zf = zipfile.ZipFile(archive)
            except (OSError, zipfile.BadZipFile):
                continue
            with zf:
                tsv_members = [m for m in zf.namelist() if m.endswith(".tsv")]
                for member in tsv_members:
                    with zf.open(member) as raw:
                        reader = csv.DictReader(
                            io.TextIOWrapper(raw, encoding="utf-8", errors="replace"),
                            delimiter="\t",
                        )
                        title_col = "patent_title"
                        for row in reader:
                            title = row.get(title_col) or row.get("title") or ""
                            abstract = row.get("patent_abstract") or ""
                            text = (title + "\n" + abstract).strip()
                            pid = row.get("patent_id") or row.get("id") or ""
                            if not text or not pid:
                                continue
                            yield CorpusRecord(
                                id=f"uspto:{pid}",
                                text=text,
                                metadata={
                                    "source": "uspto",
                                    "patent_id": pid,
                                    "patent_date": row.get("patent_date", ""),
                                    "patent_type": row.get("patent_type", ""),
                                    "kind": "patent",
                                },
                            )

    _EXTRACTORS = {
        "fred-series": "_fred_records",
        "worldbank-json": "_worldbank_records",
        "phrasebank-zip": "_phrasebank_records",
        "edgar-submissions": "_edgar_records",
        "patent-tsv": "_patent_records",
    }

    def records(self) -> Iterator[CorpusRecord]:
        self.require_available()
        for src in self._SOURCES:
            if not self._source_dir(src).is_dir():
                continue
            extractor = getattr(self, self._EXTRACTORS[src.mode])
            yield from extractor(src)


# --------------------------------------------------------------------------
# The Well — physics-simulation datasets (foreign-signal corpus)
# --------------------------------------------------------------------------

def _require_h5py():
    """Import h5py loudly — it is an optional extra (``pip install ophamin[well]``)."""
    try:
        import h5py
    except ImportError as exc:  # never silent — the corpus simply cannot be read
        raise CorpusUnavailableError(
            "the-well corpus requires h5py — install with: pip install ophamin[well]"
        ) from exc
    return h5py


def _jsonable_attr(value):
    """Coerce an HDF5 attribute to a plain JSON-ish value for record metadata."""
    import numpy as np

    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


class TheWellCorpus(Corpus):
    """The Well (Polymathic AI) — HDF5 physics-simulation datasets as a foreign corpus.

    Each dataset under ``the_well/datasets/<name>/`` is a set of simulated
    physics fields on a spatial grid, evolving over time across several
    trajectories — The Well's standard ``t<rank>_fields/<name>`` layout, shape
    ``(n_trajectories, n_timesteps, *grid[, components])``.

    A *record* is one ``(trajectory, timestep)`` snapshot. The corpus is **lazy
    by construction**: ``records()`` streams cheap metadata specs — the HDF5
    path, the field groups, the indices, the grid shape — and never loads field
    arrays. ``load_snapshot(record)`` materialises the arrays on demand. Physics
    is foreign signal: it never passes through a text encoder. ``record.text``
    is a deterministic descriptor so text-centric tooling has a stable label;
    the metadata spec + ``load_snapshot`` are the real payload.

    A dataset directory that is absent (or carries no HDF5) is transparently
    excluded — never silently substituted. ``included_datasets()`` reports
    exactly what is in the corpus, and the content hash + record count cover
    exactly those.
    """

    name = "the-well"
    kind = "physics_simulation_corpus"
    source = "The Well (Polymathic AI) — HDF5 physics-simulation datasets"

    # The Well field-group naming: t0_fields = scalar, t1_fields = vector,
    # t2_fields = tensor. The first two shape axes are (trajectory, timestep).
    _FIELD_GROUP_PREFIX = "t"
    _FIELD_GROUP_SUFFIX = "_fields"

    def _datasets_dir(self) -> Path:
        return self.root / "datasets"

    def _hdf5_files(self, dataset_dir: Path) -> list[Path]:
        """The HDF5 files for one dataset — The Well's ``data/<split>/*.hdf5``."""
        files = sorted(dataset_dir.glob("data/**/*.hdf5"))
        if not files:  # tolerate a flat layout
            files = sorted(dataset_dir.glob("**/*.hdf5"))
        return files

    def included_datasets(self) -> list[str]:
        """Dataset names whose HDF5 data is present — transparent, never silent."""
        base = self._datasets_dir()
        if not base.is_dir():
            return []
        return [
            d.name
            for d in sorted(base.iterdir())
            if d.is_dir() and self._hdf5_files(d)
        ]

    def is_available(self) -> bool:
        return len(self.included_datasets()) > 0

    @classmethod
    def _field_groups(cls, handle) -> dict[str, list[str]]:
        """Map each ``t<rank>_fields`` group to its sorted field names."""
        groups: dict[str, list[str]] = {}
        for key in handle.keys():
            if key.startswith(cls._FIELD_GROUP_PREFIX) and key.endswith(
                cls._FIELD_GROUP_SUFFIX
            ):
                names = sorted(handle[key].keys())
                if names:
                    groups[key] = names
        return groups

    @classmethod
    def _file_dims(cls, handle, path: Path) -> tuple[int, int]:
        """``(n_trajectories, n_timesteps)`` from the first field's shape."""
        for grp, names in cls._field_groups(handle).items():
            shape = handle[grp][names[0]].shape
            if len(shape) >= 2:
                return int(shape[0]), int(shape[1])
        raise CorpusUnavailableError(
            f"the-well: {path} has no recognisable t*_fields groups"
        )

    def _file_record_count(self, path: Path) -> int:
        h5py = _require_h5py()
        with h5py.File(path, "r") as handle:
            n_traj, n_time = self._file_dims(handle, path)
        return n_traj * n_time

    def _compute_count(self) -> int:
        total = 0
        for dataset in self.included_datasets():
            for path in self._hdf5_files(self._datasets_dir() / dataset):
                total += self._file_record_count(path)
        return total

    def _compute_content_hash(self) -> str:
        # full content hash of every HDF5 file — cached to disk after the first
        # call by the base class; content-addressing done right, no size-or-mtime
        # shortcut
        entries = [
            (str(path.relative_to(self.root)), self._hash_file(path))
            for dataset in self.included_datasets()
            for path in self._hdf5_files(self._datasets_dir() / dataset)
        ]
        entries.sort()
        return hashlib.sha256(repr(entries).encode("utf-8")).hexdigest()

    def _records_for_dataset(self, dataset: str) -> Iterator[CorpusRecord]:
        h5py = _require_h5py()
        for path in self._hdf5_files(self._datasets_dir() / dataset):
            # read the file's structure into plain Python, then close the handle
            # *before* yielding — load_snapshot() reopens on demand
            with h5py.File(path, "r") as handle:
                groups = self._field_groups(handle)
                if not groups:
                    raise CorpusUnavailableError(
                        f"the-well: {path} has no t*_fields groups"
                    )
                n_traj, n_time = self._file_dims(handle, path)
                fields: dict[str, dict] = {}
                for grp, names in groups.items():
                    for fname in names:
                        full_shape = list(handle[grp][fname].shape)
                        fields[fname] = {
                            "group": grp,
                            "snapshot_shape": full_shape[2:],  # grid [+ components]
                        }
                attrs = {k: _jsonable_attr(v) for k, v in handle.attrs.items()}
            field_names = sorted(fields)
            grid_shape = fields[field_names[0]]["snapshot_shape"]
            stem = path.stem
            for traj in range(n_traj):
                for step in range(n_time):
                    yield CorpusRecord(
                        id=f"the-well/{dataset}/{stem}/traj{traj}/step{step}",
                        text=(
                            f"the-well dataset={dataset} trajectory={traj} "
                            f"timestep={step} fields={','.join(field_names)} "
                            f"grid={'x'.join(map(str, grid_shape))}"
                        ),
                        metadata={
                            "dataset": dataset,
                            "hdf5_path": str(path),
                            "trajectory": traj,
                            "timestep": step,
                            "fields": fields,
                            "grid_shape": grid_shape,
                            "dataset_attrs": attrs,
                        },
                    )

    def records(self) -> Iterator[CorpusRecord]:
        self.require_available()
        for dataset in self.included_datasets():
            yield from self._records_for_dataset(dataset)

    def records_from(self, dataset_name: str) -> Iterator[CorpusRecord]:
        """Stream records from one named dataset — raises loudly if absent."""
        available = self.included_datasets()
        if dataset_name not in available:
            raise CorpusUnavailableError(
                f"the-well dataset {dataset_name!r} is not available; "
                f"present datasets: {available}"
            )
        yield from self._records_for_dataset(dataset_name)

    @staticmethod
    def load_snapshot(record: CorpusRecord) -> dict:
        """Materialise the physics fields for one ``(trajectory, timestep)`` record.

        Lazy by design — ``records()`` streams metadata specs; the field arrays
        are read from HDF5 only here, only when a physics-aware consumer asks.
        Returns ``{field_name: numpy.ndarray}`` for that one snapshot.
        """
        h5py = _require_h5py()
        meta = record.metadata
        traj, step = meta["trajectory"], meta["timestep"]
        out: dict = {}
        with h5py.File(meta["hdf5_path"], "r") as handle:
            for name, spec in meta["fields"].items():
                out[name] = handle[spec["group"]][name][traj, step]
        return out
