"""Restore and verify every external repository pinned by repos.lock.json."""

from __future__ import annotations

from pathlib import Path

from tools.sync_repositories import main as repository_sync_main


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    print("[bootstrap] restoring repositories pinned by repos.lock.json")
    result = repository_sync_main(["sync", "--root", str(PROJECT_ROOT)])
    if result:
        return result
    print("[bootstrap] running final lock and hash verification")
    return repository_sync_main(["verify", "--root", str(PROJECT_ROOT)])


if __name__ == "__main__":
    raise SystemExit(main())
