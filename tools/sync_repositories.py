from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


LOCK_VERSION = "0.2"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_FIELDS = {
    "name",
    "path",
    "upstream",
    "private_mirror",
    "branch",
    "commit",
    "dirty",
    "dirty_paths",
}


class RepositoryLockError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepositoryState:
    name: str
    path: Path
    head: str
    dirty_paths: tuple[str, ...]
    remotes: tuple[str, ...]


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={cwd.resolve()}", *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check and completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RepositoryLockError(f"git {' '.join(args)} failed in {cwd}: {detail}")
    return completed


def _target_path(root: Path, value: str) -> Path:
    relative = Path(value)
    if (
        not value
        or relative.is_absolute()
        or len(relative.parts) != 1
        or relative.parts[0] in {".", ".."}
    ):
        raise RepositoryLockError(f"repository path must be one direct child of root: {value}")
    return root.resolve() / relative


def _source_checkout_root(root: Path) -> Path:
    common = _git(
        root,
        "rev-parse",
        "--path-format=absolute",
        "--git-common-dir",
        check=False,
    )
    if common.returncode or not common.stdout.strip():
        raise RepositoryLockError("cannot locate the local checkout for a linked repository")
    common_path = Path(common.stdout.strip())
    if not common_path.is_absolute():
        common_path = root / common_path
    source_root = common_path.resolve().parent
    reported = _git(source_root, "rev-parse", "--show-toplevel", check=False)
    if (
        reported.returncode
        or not reported.stdout.strip()
        or Path(reported.stdout.strip()).resolve() != source_root
    ):
        raise RepositoryLockError("Git common directory does not identify a local checkout")
    return source_root


def _verification_target_path(root: Path, value: str) -> Path:
    lexical_target = _target_path(root, value)
    resolved_target = lexical_target.resolve()
    resolved_root = root.resolve()
    if resolved_target.parent == resolved_root:
        return resolved_target

    source_root = _source_checkout_root(resolved_root)
    expected_target = _target_path(source_root, value).resolve()
    if source_root == resolved_root or resolved_target != expected_target:
        raise RepositoryLockError(
            f"linked repository path does not match the local checkout: {value}"
        )
    return resolved_target


def load_lock(path: Path) -> list[dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RepositoryLockError(f"cannot read repository lock {path}: {error}") from error
    if document.get("schema_version") != LOCK_VERSION:
        raise RepositoryLockError(
            f"unsupported repository lock version: {document.get('schema_version')!r}"
        )
    repositories = document.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise RepositoryLockError("repositories must be a non-empty list")
    names: set[str] = set()
    paths: set[str] = set()
    for index, repository in enumerate(repositories):
        if not isinstance(repository, dict) or set(repository) != REQUIRED_FIELDS:
            raise RepositoryLockError(f"repository[{index}] fields do not match schema 0.2")
        name = repository["name"]
        relative_path = repository["path"]
        if not isinstance(name, str) or not name:
            raise RepositoryLockError(f"repository[{index}] has invalid name")
        if name in names or relative_path in paths:
            raise RepositoryLockError(f"duplicate repository name/path: {name}/{relative_path}")
        names.add(name)
        paths.add(relative_path)
        _target_path(path.parent, relative_path)
        for field in ("upstream", "branch"):
            if not isinstance(repository[field], str) or not repository[field]:
                raise RepositoryLockError(f"{name}.{field} must be a non-empty string")
        mirror = repository["private_mirror"]
        if mirror is not None and (not isinstance(mirror, str) or not mirror):
            raise RepositoryLockError(f"{name}.private_mirror must be null or non-empty")
        if not isinstance(repository["commit"], str) or not COMMIT_RE.fullmatch(
            repository["commit"]
        ):
            raise RepositoryLockError(f"{name}.commit must be a full lowercase SHA-1")
        dirty_paths = repository["dirty_paths"]
        if not isinstance(repository["dirty"], bool) or not isinstance(dirty_paths, list):
            raise RepositoryLockError(f"{name} dirty state is invalid")
        if any(not isinstance(item, str) or not item for item in dirty_paths):
            raise RepositoryLockError(f"{name}.dirty_paths contains an invalid path")
        if repository["dirty"] != bool(dirty_paths):
            raise RepositoryLockError(f"{name} dirty flag and dirty_paths disagree")
    return repositories


def _dirty_paths(path: Path) -> tuple[str, ...]:
    output = _git(path, "-c", "core.quotepath=false", "status", "--porcelain=v1").stdout
    paths: list[str] = []
    for line in output.splitlines():
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value.replace("\\", "/"))
    return tuple(sorted(paths))


def _remote_urls(path: Path) -> tuple[str, ...]:
    names = _git(path, "remote").stdout.split()
    urls: set[str] = set()
    for name in names:
        result = _git(path, "remote", "get-url", "--all", name, check=False)
        if result.returncode == 0:
            urls.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return tuple(sorted(urls))


def verify_repository(root: Path, repository: dict[str, Any]) -> RepositoryState:
    target = _verification_target_path(root, repository["path"])
    if not target.is_dir():
        raise RepositoryLockError(f"{repository['name']} is missing: {target}")
    inside = _git(target, "rev-parse", "--is-inside-work-tree", check=False)
    if inside.returncode or inside.stdout.strip() != "true":
        raise RepositoryLockError(f"{repository['name']} is not a Git worktree: {target}")
    head = _git(target, "rev-parse", "HEAD").stdout.strip()
    if head != repository["commit"]:
        raise RepositoryLockError(
            f"{repository['name']} HEAD mismatch: {head} != {repository['commit']}"
        )
    actual_dirty = _dirty_paths(target)
    expected_dirty = tuple(sorted(repository["dirty_paths"]))
    if actual_dirty != expected_dirty:
        raise RepositoryLockError(
            f"{repository['name']} dirty paths mismatch: {actual_dirty} != {expected_dirty}"
        )
    remotes = _remote_urls(target)
    expected_urls = [repository["upstream"]]
    if repository["private_mirror"]:
        expected_urls.append(repository["private_mirror"])
    missing_urls = [url for url in expected_urls if url not in remotes]
    if missing_urls:
        raise RepositoryLockError(
            f"{repository['name']} is missing configured remote URL(s): {missing_urls}"
        )
    return RepositoryState(repository["name"], target, head, actual_dirty, remotes)


def _set_remote(path: Path, name: str, url: str) -> None:
    exists = _git(path, "remote", "get-url", name, check=False).returncode == 0
    if exists:
        _git(path, "remote", "set-url", name, url)
    else:
        _git(path, "remote", "add", name, url)


def sync_repository(root: Path, repository: dict[str, Any]) -> RepositoryState:
    target = _target_path(root, repository["path"])
    if target.exists() and target.resolve() != target:
        raise RepositoryLockError(
            f"refusing to sync shared linked repository: {repository['name']}"
        )
    mirror = repository["private_mirror"]
    preferred_url = mirror or repository["upstream"]
    preferred_name = "private" if mirror else "origin"
    created = not target.exists()
    if created:
        _git(
            root,
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            "--origin",
            preferred_name,
            preferred_url,
            str(target),
        )
    elif not target.is_dir():
        raise RepositoryLockError(f"repository target exists but is not a directory: {target}")
    inside = _git(target, "rev-parse", "--is-inside-work-tree", check=False)
    if inside.returncode or inside.stdout.strip() != "true":
        raise RepositoryLockError(f"refusing non-Git repository target: {target}")
    if not created and _dirty_paths(target):
        raise RepositoryLockError(f"refusing to sync dirty repository: {repository['name']}")

    _set_remote(target, "origin", repository["upstream"])
    if mirror:
        _set_remote(target, "private", mirror)
    object_check = _git(
        target, "cat-file", "-e", f"{repository['commit']}^{{commit}}", check=False
    )
    if object_check.returncode:
        _git(target, "fetch", "--no-tags", preferred_name, repository["branch"])
    _git(target, "cat-file", "-e", f"{repository['commit']}^{{commit}}")
    head = _git(target, "rev-parse", "HEAD", check=False)
    if created or head.returncode or head.stdout.strip() != repository["commit"]:
        _git(target, "checkout", "--detach", "--force", repository["commit"])
    return verify_repository(root, repository)


def _select(
    repositories: list[dict[str, Any]], requested: Sequence[str]
) -> list[dict[str, Any]]:
    if not requested:
        return repositories
    by_name = {repository["name"]: repository for repository in repositories}
    unknown = sorted(set(requested) - set(by_name))
    if unknown:
        raise RepositoryLockError(f"unknown repository name(s): {unknown}")
    return [by_name[name] for name in requested]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify or restore repositories pinned by repos.lock.json"
    )
    parser.add_argument("command", choices=("verify", "sync"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--repo", action="append", default=[], help="repository name")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        repositories = _select(load_lock(root / "repos.lock.json"), args.repo)
        for repository in repositories:
            state = (
                verify_repository(root, repository)
                if args.command == "verify"
                else sync_repository(root, repository)
            )
            print(f"[ok] {state.name} {state.head} {state.path}")
    except RepositoryLockError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
