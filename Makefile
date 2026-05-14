# Ophamin framework — automated execution commands.
# The framework is independent of Kimera-SWM; the SUT it tests is plugged in
# via an adapter (see src/ophamin/substrate/).

PY ?= python3
SRC := src

.PHONY: help install test demo lint clean sweep probe-kimera

help:
	@echo "Ophamin framework — make targets"
	@echo "  make install        editable install + dev extras"
	@echo "  make test           run the pytest suite (statistical core)"
	@echo "  make demo           run the end-to-end mock experiment (no Kimera needed)"
	@echo "  make sweep          run the example parameter sweep"
	@echo "  make probe-kimera   self-test the Kimera adapter (needs KIMERA_REPO set)"
	@echo "  make clean          remove caches and generated run artifacts"

install:
	$(PY) -m pip install -e ".[dev,viz]"

test:
	PYTHONPATH=$(SRC) $(PY) -m pytest -q

demo:
	PYTHONPATH=$(SRC) $(PY) examples/run_mock_experiment.py

sweep:
	PYTHONPATH=$(SRC) $(PY) -m ophamin.cli sweep config/experiment_vars.yaml

probe-kimera:
	PYTHONPATH=$(SRC) $(PY) -m ophamin.cli probe-kimera "$(KIMERA_REPO)"

lint:
	PYTHONPATH=$(SRC) $(PY) -m pyflakes $(SRC) || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	rm -rf runs/ mlruns/ build/ *.egg-info src/*.egg-info
