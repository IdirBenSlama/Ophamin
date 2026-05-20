"""Make the package runnable as ``python -m ophamin``.

Mirrors the ``ophamin`` console-script entry point
(``[project.scripts] ophamin = "ophamin.cli:main"``) so that
``python -m ophamin <args>`` and ``ophamin <args>`` behave
identically. Tools that launch the package as a module — e.g.
``.claude/launch.json``'s ``runtimeArgs: ["-m", "ophamin", ...]`` —
depend on this entry point existing.
"""

from __future__ import annotations

import sys

from ophamin.cli import main

if __name__ == "__main__":
    sys.exit(main())
