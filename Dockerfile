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

# 1) install pinned transitive deps FIRST (heavy layer, cache-friendly)
COPY requirements-lock.txt ./
RUN pip install -r requirements-lock.txt

# 2) bring the source in (light layer, invalidated on every code change)
COPY pyproject.toml README.md NOTICE LICENSE ./
COPY src/ ./src/
COPY tests/ ./tests/
COPY docs/ ./docs/

# 3) install ophamin itself without re-resolving its declared deps —
#    the lockfile is the source of truth for what's actually installed.
RUN pip install -e . --no-deps

# Run as non-root by default.
RUN useradd --create-home --shell /bin/bash ophamin \
 && chown -R ophamin:ophamin /opt/ophamin
USER ophamin

ENTRYPOINT ["ophamin"]
CMD ["--help"]
