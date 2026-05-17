FROM python:3.12.7-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git libgomp1 libxml2 libxslt1.1 build-essential && rm -rf /var/lib/apt/lists/*
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/ophamin
COPY pyproject.toml README.md NOTICE LICENSE ./
COPY src/ ./src/
RUN pip install --upgrade pip
RUN pip install -e ".[all,dev,property_test]" && pip freeze --exclude-editable > /lockfile.txt
