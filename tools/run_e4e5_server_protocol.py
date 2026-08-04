from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.e4e5_handoff import (  # noqa: E402
    E4E5HandoffError,
    file_tree_receipt,
    validate_server_execution_protocol,
)
from resnet50_pipeline.hashing import sha256_file  # noqa: E402


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise E4E5HandoffError(f"JSON root must be an object: {path}")
    return value


def _substitute(token: str, values: Mapping[str, str]) -> str:
    result = token
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    if "{" in result or "}" in result:
        raise E4E5HandoffError(f"unknown server command placeholder: {token!r}")
    return result


def _copy_return(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise E4E5HandoffError(f"server return is a symlink: {source}")
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return
    if source.is_dir():
        for path in source.rglob("*"):
            if path.is_symlink():
                raise E4E5HandoffError(f"server return tree contains symlink: {path}")
            if path.is_file():
                relative = path.relative_to(source)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        return
    raise E4E5HandoffError(f"required server return is missing: {source}")


def run_server_protocol(
    protocol_path: Path,
    package_root: Path,
    output_root: Path,
    run_id: str,
) -> dict[str, Any]:
    if run_id not in {"run1", "run2"}:
        raise E4E5HandoffError("run_id must be run1 or run2")
    protocol_path = protocol_path.resolve()
    package_root = package_root.resolve()
    output_root = output_root.resolve()
    protocol = _load(protocol_path)
    validate_server_execution_protocol(protocol)
    if not package_root.is_dir():
        raise E4E5HandoffError(f"formal package directory is missing: {package_root}")
    if output_root == package_root or package_root in output_root.parents:
        raise E4E5HandoffError("output must not be inside the formal package")
    if output_root.exists():
        raise E4E5HandoffError(f"output must be a fresh path: {output_root}")
    output_root.mkdir(parents=True)
    logs_root = output_root / "logs"
    logs_root.mkdir()

    package_before = file_tree_receipt(package_root)
    substitutions = {
        "package_root": str(package_root),
        "output_root": str(output_root),
        "run_id": run_id,
    }
    phase_receipts: list[dict[str, Any]] = []
    status = "passed_commands_and_return_collection"
    failure: str | None = None
    try:
        for phase in protocol["phases"]:
            name = str(phase["name"])
            cwd = (package_root / str(phase["cwd"])).resolve()
            if cwd != package_root and package_root not in cwd.parents:
                raise E4E5HandoffError(f"phase cwd escapes package: {name}")
            if not cwd.is_dir():
                raise E4E5HandoffError(f"phase cwd is missing: {name}: {cwd}")
            argv = [_substitute(str(token), substitutions) for token in phase["argv"]]
            completed = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(phase["timeout_seconds"]),
                check=False,
                shell=False,
            )
            stdout_path = logs_root / f"{name}.stdout.log"
            stderr_path = logs_root / f"{name}.stderr.log"
            stdout_path.write_text(completed.stdout, encoding="utf-8", newline="\n")
            stderr_path.write_text(completed.stderr, encoding="utf-8", newline="\n")
            phase_receipts.append(
                {
                    "name": name,
                    "cwd": str(cwd),
                    "argv": argv,
                    "returncode": completed.returncode,
                    "stdout": {
                        "path": stdout_path.relative_to(output_root).as_posix(),
                        "sha256": sha256_file(stdout_path),
                    },
                    "stderr": {
                        "path": stderr_path.relative_to(output_root).as_posix(),
                        "sha256": sha256_file(stderr_path),
                    },
                }
            )
            if completed.returncode:
                raise E4E5HandoffError(
                    f"server phase failed: {name}: returncode={completed.returncode}"
                )

        raw_root = output_root / "raw_return"
        for item in protocol["return_paths"]:
            relative = Path(str(item["path"]))
            _copy_return(package_root / relative, raw_root / relative)
    except (E4E5HandoffError, subprocess.TimeoutExpired, OSError) as error:
        status = "failed"
        failure = str(error)

    package_after = file_tree_receipt(package_root)
    receipt: dict[str, Any] = {
        "schema": "resnet50-e4e5-server-run-receipt-v1",
        "status": status,
        "run_id": run_id,
        "server_id": protocol["server_id"],
        "rtl_identity": protocol["rtl_identity"],
        "protocol": {
            "path": str(protocol_path),
            "sha256": sha256_file(protocol_path),
        },
        "package_root": str(package_root),
        "package_tree_before": package_before,
        "package_tree_after": package_after,
        "phases": phase_receipts,
        "failure": failure,
    }
    receipt_path = output_root / "run_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if failure is not None:
        raise E4E5HandoffError(failure)
    receipt["return_tree"] = file_tree_receipt(output_root / "raw_return")
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute only an explicitly approved load/start/wait/readback server protocol "
            "and collect a hash-bound raw return."
        )
    )
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True, choices=("run1", "run2"))
    args = parser.parse_args()
    try:
        receipt = run_server_protocol(
            args.protocol, args.package, args.output, args.run_id
        )
    except Exception as error:
        print(f"E4/E5 server protocol failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "run_id": receipt["run_id"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
