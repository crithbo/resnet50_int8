from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as zipped:
        names = [item.filename for item in zipped.infolist()]
        roots = {name.split("/", 1)[0] for name in names if name}
        if len(names) != len(set(names)) or len(roots) != 1:
            raise RuntimeError(f"unsafe archive topology: {archive}")
        for item in zipped.infolist():
            parts = Path(item.filename.replace("/", "\\")).parts
            if item.filename.startswith(("/", "\\")) or ".." in parts:
                raise RuntimeError(f"unsafe member: {item.filename}")
        zipped.extractall(destination)
    return destination / next(iter(roots))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def parser_run(parser: Path, log: Path, output: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(parser), "--log", str(log), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    value = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return result.returncode, value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--v75-source", type=Path, required=True)
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="node0004_v76_bound_") as raw:
        temp = Path(raw)
        package = safe_extract(args.zip, temp / "v76")
        old_package = safe_extract(args.v75_source, temp / "v75")
        returned = safe_extract(args.return_zip, temp / "return")
        source_log = returned / "runs/c0/sim.log"
        checks["formal_return_sim_log_present"] = source_log.is_file()

        old_run = temp / "old_run"
        (old_run / "c0").mkdir(parents=True)
        shutil.copy2(source_log, old_run / "c0/sim.log")
        old_runtime = load_module(
            old_package / "package_tools/node0004_hang_localization_runtime_v7.py",
            "node0004_v75_runtime_negative",
        )
        old_error = None
        try:
            old_runtime._prepare_source_bound_products(old_run)
        except Exception as exc:  # exact historical escape is the negative control
            old_error = f"{type(exc).__name__}: {exc}"
        checks["negative_historical_unbounded_collector_fails_closed"] = (
            old_error is not None and "exceeds 7 MiB" in old_error
        )

        new_run = temp / "new_run"
        (new_run / "c0").mkdir(parents=True)
        shutil.copy2(source_log, new_run / "c0/sim.log")
        new_runtime = load_module(
            package / "package_tools/node0004_hang_localization_runtime_v7.py",
            "node0004_v76_runtime_positive",
        )
        receipt = new_runtime._prepare_source_bound_products(new_run)
        decision = json.loads(
            (new_run / "c0/source_bound_causal_decision.json").read_text(encoding="utf-8")
        )
        checks["positive_bounded_collector_under_limit"] = (
            receipt["bounded_log_bytes"] <= receipt["bounded_log_limit_bytes"]
        )
        checks["positive_parser_exit_zero"] = receipt["parser_exit_status"] == 0
        checks["positive_decision_preserved"] = (
            receipt["parser_decision"] == "POST_TERMINAL_TEMPORAL_OWNERSHIP_REQUIRES_RING"
            and decision.get("decision") == receipt["parser_decision"]
        )
        checks["positive_both_terminal_classes_preserved"] = (
            receipt["retained_kind_counts"].get("CLASS", 0) > 0
            and receipt["retained_kind_counts"].get("RING_POST", 0) > 0
        )
        checks["positive_reduction_is_material"] = (
            receipt["bounded_log_bytes"] < receipt["original_sim_log_bytes"]
            and receipt["source_bound_dropped_ring_record_count"] > 0
        )

        compact = (new_run / "c0/source_bound_causal.log").read_text(
            encoding="utf-8", errors="replace"
        )
        missing_records = temp / "negative_missing_all_probe_records.log"
        missing_records.write_text("non-probe simulator text\n", encoding="utf-8")
        missing_records_exit, missing_records_decision = parser_run(
            package / "package_tools/source_bound_causal_parser.py",
            missing_records,
            temp / "negative_missing_all_probe_records.json",
        )
        checks["negative_missing_probe_records_fails_closed"] = (
            missing_records_exit != 0
            or missing_records_decision.get("decision") == "EVIDENCE_INCOMPLETE"
        )

        details.update(
            {
                "v76_zip": {
                    "path": str(args.zip.resolve()),
                    "bytes": args.zip.stat().st_size,
                    "sha256": sha256(args.zip),
                },
                "v75_source_zip_sha256": sha256(args.v75_source),
                "formal_return_zip_sha256": sha256(args.return_zip),
                "historical_negative_error": old_error,
                "positive_receipt": receipt,
                "positive_decision": decision,
                "negative_missing_probe_records": {
                    "exit": missing_records_exit,
                    "decision": missing_records_decision.get("decision"),
                },
            }
        )

    errors.extend(name for name, value in checks.items() if not value)
    report = {
        "schema": "conv-node0004-v76-bounded-collector-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "details": details,
        "claim_boundary": (
            "Exact v75 receipted simulator log replay through the final v76 package-local "
            "collector/parser only; no DUT rerun, numeric, natural-terminal, formal-D, E4 or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
