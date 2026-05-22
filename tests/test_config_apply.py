"""Tests for CR5 — owner-gated config write/apply.

Everything mutating in here is gated hard. The tests pin the gate, the
dry-run safety, validation-before-apply, secret refusal, reversibility, and
the signed audit — all against TMP env files (the real Kimera is never
touched). The boundary: a config change to the substrate is owner-gated by
construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ophamin.configuring.apply import (
    APPLY_GATE_ENV,
    ConfigApplyError,
    ConfigApplyNotAuthorized,
    apply_authorized,
    apply_config_change,
    plan_config_change,
)
from ophamin.configuring.schema import ConfigKnob

_KEY = b"test-config-audit-key"


def _knob(env_var, default, value_type, group="system", secret=False):
    return ConfigKnob(
        env_var=env_var, default=default, value_type=value_type,
        group=group, source_file="kimera/config.py", secret=secret,
    )


def _schema():
    return [
        _knob("KIMERA_DEBUG", "false", "bool"),
        _knob("KIMERA_MAX_WORKERS", "4", "int"),
        _knob("KIMERA_ENVIRONMENT", "development", "str"),
        _knob("KIMERA_DB_PASSWORD", "", "str", group="database", secret=True),
    ]


def _env_file(tmp_path, content="KIMERA_DEBUG=true\n"):
    p = tmp_path / "kimera.env"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestPlan:
    def test_current_is_read_from_file_not_environ(self, tmp_path, monkeypatch):
        # Even if os.environ disagrees, the plan's "current" comes from the
        # FILE the tool manages.
        monkeypatch.setenv("KIMERA_DEBUG", "false")
        ef = _env_file(tmp_path, "KIMERA_DEBUG=true\n")
        plan = plan_config_change(_schema(), {"KIMERA_DEBUG": "false"}, env_file=ef)
        e = {x.env_var: x for x in plan.entries}["KIMERA_DEBUG"]
        assert e.current == "true"      # from file, not environ
        assert e.status == "ok"         # true -> false is a real change
        assert plan.applicable is True

    def test_noop_when_proposed_equals_file(self, tmp_path):
        ef = _env_file(tmp_path, "KIMERA_DEBUG=true\n")
        plan = plan_config_change(_schema(), {"KIMERA_DEBUG": "true"}, env_file=ef)
        e = {x.env_var: x for x in plan.entries}["KIMERA_DEBUG"]
        assert e.status == "noop"
        assert plan.applicable is False  # no real change

    def test_unknown_knob_refused(self, tmp_path):
        ef = _env_file(tmp_path)
        plan = plan_config_change(_schema(), {"NOT_A_KNOB": "x"}, env_file=ef)
        assert {x.env_var: x.status for x in plan.entries}["NOT_A_KNOB"] == "unknown_knob"
        assert plan.applicable is False

    def test_type_error_refused(self, tmp_path):
        ef = _env_file(tmp_path)
        plan = plan_config_change(_schema(), {"KIMERA_MAX_WORKERS": "lots"}, env_file=ef)
        assert {x.env_var: x.status for x in plan.entries}["KIMERA_MAX_WORKERS"] == "type_error"
        assert plan.applicable is False

    def test_secret_knob_refused_and_value_hidden(self, tmp_path):
        ef = _env_file(tmp_path)
        plan = plan_config_change(_schema(), {"KIMERA_DB_PASSWORD": "hunter2"}, env_file=ef)
        e = {x.env_var: x for x in plan.entries}["KIMERA_DB_PASSWORD"]
        assert e.status == "secret_refused"
        assert plan.applicable is False
        # the secret value never appears anywhere in the serialized plan
        assert "hunter2" not in json.dumps(plan.to_dict())

    def test_validation_blocks_applicable(self, tmp_path):
        # Switching to production with debug on triggers a validate_config
        # ERROR, so the plan is not applicable even though the entries parse.
        ef = _env_file(tmp_path, "KIMERA_DEBUG=true\n")
        plan = plan_config_change(
            _schema(), {"KIMERA_ENVIRONMENT": "production"}, env_file=ef,
        )
        # KIMERA_DEBUG=true (from file) + production => debug_on_in_production ERROR
        codes = {v["code"] for v in plan.validation}
        assert "debug_on_in_production" in codes
        assert plan.applicable is False


class TestGate:
    def test_apply_authorized_requires_both(self, monkeypatch):
        monkeypatch.delenv(APPLY_GATE_ENV, raising=False)
        assert apply_authorized(True) is False              # no env gate
        assert apply_authorized(False, env={APPLY_GATE_ENV: "1"}) is False  # not authorized
        assert apply_authorized(True, env={APPLY_GATE_ENV: "1"}) is True
        assert apply_authorized(True, env={APPLY_GATE_ENV: "0"}) is False

    def test_apply_refused_without_env_gate(self, tmp_path):
        ef = _env_file(tmp_path)
        plan = plan_config_change(_schema(), {"KIMERA_DEBUG": "false"}, env_file=ef)
        with pytest.raises(ConfigApplyNotAuthorized):
            apply_config_change(
                plan, _schema(), authorized=True, sign_key=_KEY,
                audit_root=str(tmp_path / "a"), gate_env={},  # no gate
            )
        # file untouched
        assert Path(ef).read_text() == "KIMERA_DEBUG=true\n"

    def test_apply_refused_without_authorized(self, tmp_path):
        ef = _env_file(tmp_path)
        plan = plan_config_change(_schema(), {"KIMERA_DEBUG": "false"}, env_file=ef)
        with pytest.raises(ConfigApplyNotAuthorized):
            apply_config_change(
                plan, _schema(), authorized=False, sign_key=_KEY,
                audit_root=str(tmp_path / "a"), gate_env={APPLY_GATE_ENV: "1"},
            )

    def test_non_applicable_plan_refused(self, tmp_path):
        ef = _env_file(tmp_path)
        plan = plan_config_change(_schema(), {"KIMERA_MAX_WORKERS": "lots"}, env_file=ef)
        with pytest.raises(ConfigApplyError):
            apply_config_change(
                plan, _schema(), authorized=True, sign_key=_KEY,
                audit_root=str(tmp_path / "a"), gate_env={APPLY_GATE_ENV: "1"},
            )


class TestApply:
    def _apply(self, tmp_path, content="KIMERA_DEBUG=true\n", changes=None):
        ef = _env_file(tmp_path, content)
        plan = plan_config_change(
            _schema(), changes or {"KIMERA_DEBUG": "false", "KIMERA_MAX_WORKERS": "8"},
            env_file=ef,
        )
        audit = apply_config_change(
            plan, _schema(), authorized=True, sign_key=_KEY,
            audit_root=str(tmp_path / "audits"), gate_env={APPLY_GATE_ENV: "1"},
        )
        return ef, audit

    def test_apply_writes_changes(self, tmp_path):
        ef, audit = self._apply(tmp_path)
        text = Path(ef).read_text()
        assert "KIMERA_DEBUG=false" in text
        assert "KIMERA_MAX_WORKERS=8" in text

    def test_apply_is_reversible_via_backup(self, tmp_path):
        ef, audit = self._apply(tmp_path)
        assert audit.backup_file
        assert Path(audit.backup_file).exists()
        assert Path(audit.backup_file).read_text() == "KIMERA_DEBUG=true\n"

    def test_audit_signed_and_verifies(self, tmp_path):
        _, audit = self._apply(tmp_path)
        assert audit.signature
        assert audit.verify_signature(_KEY) is True
        assert audit.verify_signature(b"wrong-key") is False

    def test_audit_records_hashes_and_snapshots(self, tmp_path):
        _, audit = self._apply(tmp_path)
        assert len(audit.prior_content_hash) == 64
        assert len(audit.new_content_hash) == 64
        assert audit.prior_content_hash != audit.new_content_hash
        assert audit.before_snapshot_id != audit.after_snapshot_id

    def test_audit_persisted_to_root(self, tmp_path):
        _, audit = self._apply(tmp_path)
        files = list((tmp_path / "audits").glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["audit_id"] == audit.audit_id
        assert data["signature"] == audit.signature

    def test_audit_changes_are_secret_safe(self, tmp_path):
        # Apply only non-secret changes (secrets are refused at plan time), and
        # confirm no value that could be a secret leaks into the audit record.
        _, audit = self._apply(tmp_path)
        assert all(c["status"] == "ok" for c in audit.changes)
        assert all(c["env_var"] != "KIMERA_DB_PASSWORD" for c in audit.changes)

    def test_apply_to_missing_file_creates_it(self, tmp_path):
        ef = str(tmp_path / "new.env")  # does not exist yet
        plan = plan_config_change(_schema(), {"KIMERA_MAX_WORKERS": "8"}, env_file=ef)
        assert plan.applicable is True
        audit = apply_config_change(
            plan, _schema(), authorized=True, sign_key=_KEY,
            audit_root=str(tmp_path / "audits"), gate_env={APPLY_GATE_ENV: "1"},
        )
        assert "KIMERA_MAX_WORKERS=8" in Path(ef).read_text()
        assert audit.backup_file == ""  # nothing to back up
