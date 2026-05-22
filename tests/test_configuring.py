"""Tests for the Configure facet — introspect / snapshot / validate Kimera config.

Uses a synthetic mini Kimera config tree (tmp_path) so the tests don't
depend on the real Kimera repo being present, plus assertions that mirror
the real env-var contract (app-level literals + domain f-string + ENV_PREFIX).
"""

from __future__ import annotations

import textwrap

import pytest

from ophamin.configuring import (
    config_snapshot,
    effective_config,
    extract_config_schema,
    is_valid,
    validate_config,
)


def _mini_kimera(tmp_path):
    """A tiny Kimera-shaped config tree: app-level + one domain config."""
    core = tmp_path / "kimera_swm" / "core"
    cfg = core / "configuration"
    cfg.mkdir(parents=True)
    (core / "configuration_predecessor.py").write_text(textwrap.dedent('''
        import os
        def get_app_config():
            host = os.getenv("KIMERA_DB_HOST", "localhost")
            port = int(os.getenv("KIMERA_DB_PORT", "5432"))
            pw = os.getenv("KIMERA_DB_PASSWORD", "")
            env = os.getenv("KIMERA_ENVIRONMENT", "development")
            debug = os.getenv("KIMERA_DEBUG", "false").lower() == "true"
            reload_ = os.getenv("KIMERA_API_RELOAD", "false").lower() == "true"
            return (host, port, pw, env, debug, reload_)
    '''), encoding="utf-8")
    (cfg / "__init__.py").write_text("", encoding="utf-8")
    (cfg / "geoid_config.py").write_text(textwrap.dedent('''
        import os
        from typing import ClassVar
        class GeoidConfiguration:
            ENV_PREFIX: ClassVar[str] = "GEOID_"
            @classmethod
            def from_env(cls):
                return (
                    float(os.getenv(f"{cls.ENV_PREFIX}ACTIVATION_THRESHOLD", "0.7")),
                    float(os.getenv(f"{cls.ENV_PREFIX}RESONANCE_DECAY_RATE", "0.1")),
                )
    '''), encoding="utf-8")
    (cfg / "test_config_direct.py").write_text(
        'import os\nos.getenv("SHOULD_BE_SKIPPED", "x")\n', encoding="utf-8")
    return tmp_path


class TestSchemaExtraction:
    def test_app_and_domain_knobs_extracted(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        by_var = {k.env_var: k for k in schema}
        # app-level literals
        assert "KIMERA_DB_HOST" in by_var
        assert by_var["KIMERA_DB_PORT"].value_type == "int"
        assert by_var["KIMERA_DEBUG"].value_type == "bool"
        # domain f-string + ENV_PREFIX resolved
        assert "GEOID_ACTIVATION_THRESHOLD" in by_var
        assert by_var["GEOID_ACTIVATION_THRESHOLD"].value_type == "float"
        assert by_var["GEOID_ACTIVATION_THRESHOLD"].group == "geoid"

    def test_secrets_flagged(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        by_var = {k.env_var: k for k in schema}
        assert by_var["KIMERA_DB_PASSWORD"].secret is True
        assert by_var["KIMERA_DB_HOST"].secret is False

    def test_test_files_skipped(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        assert "SHOULD_BE_SKIPPED" not in {k.env_var for k in schema}

    def test_groups(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        groups = {k.group for k in schema}
        assert {"database", "system", "api", "geoid"} <= groups

    def test_missing_repo_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_config_schema(tmp_path / "nope")


class TestEffectiveAndSnapshot:
    def test_effective_uses_env_override_and_redacts_secret(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        eff = effective_config(schema, env={"KIMERA_DB_HOST": "db.prod",
                                            "KIMERA_DB_PASSWORD": "hunter2"})
        by_var = {k.env_var: k for k in eff}
        assert by_var["KIMERA_DB_HOST"].current == "db.prod"
        assert by_var["KIMERA_DB_HOST"].is_default is False
        assert by_var["KIMERA_DB_PORT"].current == 5432   # default, typed int
        assert by_var["KIMERA_DB_PORT"].is_default is True
        # secret redacted to set/unset, never the value
        assert by_var["KIMERA_DB_PASSWORD"].current == "<set>"

    def test_snapshot_is_secret_safe_and_stable(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        env = {"KIMERA_DB_PASSWORD": "secret-value-1"}
        s1 = config_snapshot(effective_config(schema, env=env))
        # Different secret VALUE, same set/unset pattern → same snapshot id.
        s2 = config_snapshot(effective_config(
            schema, env={"KIMERA_DB_PASSWORD": "secret-value-2"}))
        assert s1.snapshot_id == s2.snapshot_id
        assert "secret-value-1" not in str(s1.payload)
        # A non-secret change → different snapshot id.
        s3 = config_snapshot(effective_config(
            schema, env={"KIMERA_DB_PASSWORD": "x", "KIMERA_DB_HOST": "other"}))
        assert s3.snapshot_id != s1.snapshot_id


class TestConfigGate:
    def test_dev_config_valid(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        eff = effective_config(schema, env={})
        assert is_valid(validate_config(eff))

    def test_production_empty_password_and_debug_flagged(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        eff = effective_config(schema, env={
            "KIMERA_ENVIRONMENT": "production",
            "KIMERA_DEBUG": "true",
            "KIMERA_DB_PASSWORD": "",
        })
        viol = validate_config(eff)
        codes = {v.code for v in viol}
        assert "empty_secret_in_production" in codes
        assert "debug_on_in_production" in codes
        assert not is_valid(viol)

    def test_production_with_password_and_no_debug_valid(self, tmp_path):
        schema = extract_config_schema(_mini_kimera(tmp_path))
        eff = effective_config(schema, env={
            "KIMERA_ENVIRONMENT": "production",
            "KIMERA_DEBUG": "false",
            "KIMERA_API_RELOAD": "false",
            "KIMERA_DB_PASSWORD": "a-real-secret",
        })
        assert is_valid(validate_config(eff))


class TestRealKimeraConfig:
    def test_real_repo_if_present(self):
        import pathlib
        repo = pathlib.Path(
            "/Users/idirbenslama/Desktop/DEV/Kimera_SWM (Spherical Word Memory)")
        if not (repo / "kimera_swm" / "core" / "configuration_predecessor.py").is_file():
            pytest.skip("real Kimera repo not present")
        schema = extract_config_schema(repo)
        groups = {k.group for k in schema}
        # The substrate-tuning domain knobs must be captured, not just app-level.
        assert {"geoid", "scar", "thermodynamic"} <= groups
        assert len(schema) > 50
