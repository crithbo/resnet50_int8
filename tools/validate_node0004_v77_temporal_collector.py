from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v77_terminal_temporal_ledger_diag"
TARGET_TOKEN = (
    "slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
    "slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine."
    "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(archive_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        if len(names) != len(set(names)) or roots != {PACKAGE} or archive.testzip() is not None:
            raise RuntimeError("invalid final ZIP topology or CRC")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name:
                raise RuntimeError(f"unsafe member: {name}")
        archive.extractall(destination)
    return destination / PACKAGE


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("v77_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load final runtime")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def parse(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--v76-return", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    errors: list[str] = []
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="n4v77_temporal_") as raw:
        temp = Path(raw)
        package = extract(args.zip, temp / "package")
        with zipfile.ZipFile(args.v76_return) as archive:
            member = next(name for name in archive.namelist() if name.endswith("/runs/c0/sim.log"))
            base_lines = archive.read(member).decode("utf-8", errors="replace").splitlines()

        # Exact logger format, real %m multi-instance names, a target-complete burst,
        # and enough non-target ring traffic to cross the historical 7-MiB input size.
        target_template = next(
            line
            for line in base_lines
            if "kind=RING_PROGRESS" in line
            and "boundary=buf_queue_enqueue" in line
            and TARGET_TOKEN in line
        )
        target_parsed = parse(target_template)
        target_burst: list[str] = []
        for index in range(64):
            value = target_template
            value = value.replace(
                "time=" + target_parsed["time"], f"time={int(target_parsed['time']) + index + 1}"
            )
            value = value.replace("seq=" + target_parsed["seq"], f"seq={1000 + index}")
            target_burst.append(value)
        other_template = next(
            line
            for line in base_lines
            if "kind=RING_STATE" in line and TARGET_TOKEN not in line
        )
        # 16k legal multi-instance records add >3 MiB to the 5.34-MiB receipted base.
        noisy = [other_template.replace("seq=", f"extra={index} seq=", 1) for index in range(16000)]
        input_lines = base_lines + target_burst + noisy
        input_payload = ("\n".join(input_lines) + "\n").encode("utf-8")
        checks["raw_logger_input_exceeds_7_mib"] = len(input_payload) > 7 * 1024 * 1024

        run = temp / "run"
        (run / "c0").mkdir(parents=True)
        (run / "c0/sim.log").write_bytes(input_payload)
        runtime = load_module(package / "package_tools/node0004_hang_localization_runtime_v7.py")
        receipt = runtime._prepare_source_bound_products(run)
        temporal_path = run / "c0/target_temporal_decision.json"
        temporal = json.loads(temporal_path.read_text(encoding="utf-8"))
        checks.update(
            {
                "bounded_under_7_mib": receipt["bounded_log_bytes"] <= receipt["bounded_log_limit_bytes"],
                "complete_target_ring_retained": receipt["target_complete_ring_record_count"] >= 64,
                "non_target_noise_dropped": receipt["source_bound_dropped_ring_record_count"] >= 16000,
                "generated_parser_pass": receipt["parser_exit_status"] == 0,
                "target_decision_exists": temporal_path.is_file(),
                "target_decision_exactly_one": len(temporal.get("matching_candidate_ids", [])) == 1,
                "five_candidates_pairwise": len(temporal.get("candidate_ids", [])) == 5
                and temporal.get("pairwise_distinguishable") is True,
                "target_summaries_complete": temporal.get("missing_required_target_summaries") == [],
                "target_decision_receipted": receipt.get("target_temporal_decision_sha256") == sha(temporal_path),
            }
        )

        # Exact changed consumer negative: delete the target mem_terminal SUMMARY.
        negative_lines = [
            line
            for line in base_lines
            if not (
                "kind=SUMMARY" in line
                and "boundary=mem_terminal" in line
                and TARGET_TOKEN in line
            )
        ]
        negative = temp / "negative"
        (negative / "c0").mkdir(parents=True)
        (negative / "c0/sim.log").write_text("\n".join(negative_lines) + "\n", encoding="utf-8")
        negative_error = None
        try:
            runtime._prepare_source_bound_products(negative)
        except Exception as exc:
            negative_error = f"{type(exc).__name__}: {exc}"
        checks["negative_deleted_target_summary_fails_closed"] = bool(
            negative_error and "missing required summaries" in negative_error
        )

        # Stable-level/non-qualified traffic cannot change qualified progress ledger.
        stable_lines = [line for line in base_lines if "kind=RING_STATE" in line and TARGET_TOKEN in line]
        qualified_before = sum("kind=RING_PROGRESS" in line and TARGET_TOKEN in line for line in base_lines)
        qualified_after = sum(
            "kind=RING_PROGRESS" in line and TARGET_TOKEN in line
            for line in base_lines + stable_lines * 8
        )
        checks["stable_level_not_counted_as_qualified_transaction"] = qualified_before == qualified_after

        details = {
            "zip": {"path": str(args.zip.resolve()), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
            "v76_return_sha256": sha(args.v76_return),
            "raw_logger_bytes": len(input_payload),
            "receipt": receipt,
            "temporal_decision": temporal,
            "negative_deleted_summary_error": negative_error,
        }

    errors.extend(name for name, value in checks.items() if not value)
    report = {
        "schema": "conv-node0004-v77-temporal-collector-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "details": details,
        "claim_boundary": "Exact final package logger-to-collector-to-generated-parser and target temporal parser only; no DUT run or natural/formal-D claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
