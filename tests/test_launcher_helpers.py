"""Launcher helpers for ``ophamin http serve --open`` — version-aware idempotency.

These lock down the pure primitives the launcher uses to decide between opening a
*current* server, restarting a *stale* one, and leaving a *foreign* process
alone. The full branch binds a real port (exercised manually); these guard the
primitives so a regression can't silently reintroduce the stale-server trap that
once showed an upgraded user the old UI.
"""

import socket

from ophamin.cli import (
    _pids_listening_on,
    _running_framework_version,
    _stop_port_listeners,
)


def _free_port() -> int:
    """Grab (and release) an ephemeral port number that is currently closed."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def test_version_probe_is_none_when_nothing_listening() -> None:
    # Foreign/none case: no Ophamin answering → None (launcher must NOT kill).
    assert _running_framework_version("127.0.0.1", _free_port()) is None


def test_no_pids_when_nothing_listening() -> None:
    assert _pids_listening_on(_free_port()) == []


def test_stop_listeners_is_true_when_nothing_to_stop() -> None:
    # Nothing on the port → already free → True (no-op, no exception).
    assert _stop_port_listeners("127.0.0.1", _free_port()) is True
