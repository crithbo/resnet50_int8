from __future__ import annotations

import subprocess
from pathlib import Path


OFFICIAL_CONFIG_COMMIT = "e299b2804448242d1589b3e58ed7c5a9a5eca09f"
OFFICIAL_EXECPLAN_COMMIT = "d4ffc32c9b29a858d83e13706cd837c5549521a4"


class SourceVersionError(ValueError):
    """The ndp-sim-ref checkout is not the locked config+execplan source."""


def _git(source_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    resolved = source_root.resolve()
    return subprocess.run(
        ["git", "-c", f"safe.directory={resolved.as_posix()}", *args],
        cwd=resolved,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def verify_ndp_source_checkout(source_root: Path, *, require_clean: bool = True) -> str:
    """Verify the newer execplan commit still contains the frozen config baseline."""

    head = _git(source_root, "rev-parse", "HEAD")
    if head.returncode or head.stdout.strip() != OFFICIAL_EXECPLAN_COMMIT:
        raise SourceVersionError("ndp-sim-ref checkout does not match locked execplan commit")
    ancestor = _git(
        source_root,
        "merge-base",
        "--is-ancestor",
        OFFICIAL_CONFIG_COMMIT,
        OFFICIAL_EXECPLAN_COMMIT,
    )
    if ancestor.returncode:
        raise SourceVersionError("locked DeepSeek config baseline is not an execplan ancestor")
    if require_clean:
        status = _git(source_root, "status", "--short")
        if status.returncode or status.stdout.strip():
            raise SourceVersionError("ndp-sim-ref checkout must be clean")
    return OFFICIAL_EXECPLAN_COMMIT


__all__ = [
    "OFFICIAL_CONFIG_COMMIT",
    "OFFICIAL_EXECPLAN_COMMIT",
    "SourceVersionError",
    "verify_ndp_source_checkout",
]
