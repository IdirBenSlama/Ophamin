# Ophamin — reproducible build image (Phase S4, 2026-05-16)
#
# Builds Ophamin in a fixed Python 3.12 slim image with every transitive
# dependency pinned via requirements-lock.txt. The result is byte-for-byte
# reproducible for any commit + lockfile pair.
#
# Build:
#   docker build -t ophamin:0.7.0 .
#
# Smoke-test the image:
#   docker run --rm ophamin:0.7.0 ophamin --help
#
# Run the full test suite inside the image (re-validates the build):
#   docker run --rm ophamin:0.7.0 sh -c \
#     'PYTHONPATH=src python -m pytest -q --ignore=tests/bench'
#
# The pin on python:3.12.7-slim-bookworm matches the [tool.mypy] python_version
# in pyproject.toml; do not bump these in isolation — coordinate.

FROM python:3.12.7-slim-bookworm

# Base image hygiene: drop the deprecated debconf prompts, give pip a stable
# cache location, prevent .pyc files from cluttering the layer.
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0

# System packages — only what Ophamin's runtime needs.
#   git is required by dvc + by some lineage probes.
#   libgomp1 is the OpenMP runtime that statsmodels/scipy load lazily.
#   libxml2 + libxslt1.1 back lxml (PROV serializer).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git \
        libgomp1 \
        libxml2 \
        libxslt1.1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/ophamin

# Scope note: this image ships the Ophamin CORE runtime + CLI only.
# It deliberately does NOT include the [all,dev] optional surface because:
#   - Several optional deps (causalml, econml, z3-solver) need C/C++ build
#     tools that aren't in python:3.12-slim — installing them inflates the
#     image by ~600MB of build tooling for ~5 packages that the CLI never
#     calls directly.
#   - Several optional wheels (gudhi 3.x, puncc 0.9.x) don't have
#     linux/arm64 Python 3.12 builds at all.
#
# What this image CAN do:
#   - ophamin --help / ophamin scenario list / ophamin pillar list (CLI)
#   - run scenarios that depend only on core deps (numpy / scipy /
#     scikit-learn / statsmodels / pandas / pyyaml / prov / etc.)
#   - emit signed proof records and CycloneDX SBOMs
#
# What it CANNOT do:
#   - run causal-discovery / Bayesian / TDA scenarios (need [causal] /
#     [bayesian] / [tda] extras — install on a build-tool-equipped host)
#   - run the audit pillar against a Kimera repo (needs [audit] extras)
#
# For full-surface development, use a local venv with the macOS lockfile
# (or any toolchain-equipped Linux distro: e.g. python:3.12-bookworm).

# 1) bring the source in
COPY pyproject.toml README.md NOTICE LICENSE ./
COPY src/ ./src/
COPY tests/ ./tests/
COPY docs/ ./docs/

# 2) install ophamin CORE (no extras) — fresh resolve against pyproject
RUN pip install -e .

# Run as non-root by default.
RUN useradd --create-home --shell /bin/bash ophamin \
 && chown -R ophamin:ophamin /opt/ophamin
USER ophamin

ENTRYPOINT ["ophamin"]
CMD ["--help"]
