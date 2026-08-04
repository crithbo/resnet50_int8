from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


try:
    import node0004_assumed_hardware_server_runtime_v5_base as observer_base
except ImportError:
    from tools import node0004_assumed_hardware_server_runtime_v5 as observer_base


numeric_base = observer_base.base
PASS_STATUS = "CONV_NATIVE_FOUR_LANE_DF23E4D_SERVER_PASS"
EXPECTED_LEAVES = {
    "SA_PE_Float_CSA.v": (
        "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3"
    ),
    "SA_PE_Float_Control.v": (
        "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb"
    ),
    "SA_PE_Mul_Array.v": (
        "135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a"
    ),
    "SA_ALU.v": (
        "c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06"
    ),
}
PARSING_RE = re.compile(r"Parsing design file ['\"]([^'\"]+)['\"]")
NATURAL_MARKER = "$finish at simulation time"
OBSERVER_MARKER = "[RETURN_OBSERVER] enabled"
FEATURE_MARKER = (
    "N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1"
)
CANONICAL_MARKER = "N4PERF_CANONICAL_DECISION_V1"
COMPLETE_DECISION = "decision=EXPECTED_STAGE_PREFIX_COMPLETE"


class RuntimeErrorContract(numeric_base.RuntimeErrorContract):
    pass


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def preflight(package_root: Path) -> dict[str, Any]:
    value = numeric_base.preflight(package_root)
    manifest = numeric_base.load_json(package_root / "package_manifest.json")
    if (
        manifest.get("status") != "PACKAGE_READY_NOT_RUN"
        or manifest.get("candidate_release") is not False
        or manifest.get("candidate_class")
        != "PERFORMANCE_DIAGNOSTIC_CANDIDATE"
        or manifest.get("expected_production_rtl_identity", {}).get("leaves")
        != EXPECTED_LEAVES
        or manifest.get("formal_readback_count") != 320
    ):
        raise RuntimeErrorContract("native-four-lane package identity differs")
    return {
        **value,
        "schema": "conv-native-four-lane-df23e4d-package-preflight-v1",
        "candidate_release": False,
        "formal_readback_count": 320,
    }


def collect_compile_identity(
    compile_log: Path, output: Path
) -> dict[str, Any]:
    text = compile_log.read_text(encoding="utf-8", errors="replace")
    parsed = [Path(match.group(1)) for match in PARSING_RE.finditer(text)]
    records: dict[str, Any] = {}
    errors: list[str] = []
    for basename, expected in EXPECTED_LEAVES.items():
        matches = [path for path in parsed if path.name == basename]
        unique = {str(path) for path in matches}
        if len(unique) != 1:
            errors.append(
                f"{basename}: expected one compiled path, found {len(unique)}"
            )
            continue
        path = Path(next(iter(unique)))
        if not path.is_file():
            errors.append(f"{basename}: compiled source path is unreadable")
            continue
        observed = numeric_base.sha256(path)
        records[basename] = {
            "compiled_path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": observed,
            "expected_sha256": expected,
            "match": observed == expected,
        }
        if observed != expected:
            errors.append(f"{basename}: production source SHA differs")
    receipt = {
        "schema": "conv-native-four-lane-production-rtl-identity-v1",
        "valid": not errors,
        "errors": errors,
        "compile_log": str(compile_log),
        "compile_log_sha256": numeric_base.sha256(compile_log),
        "leaves": records,
        "expected_commit": "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727",
        "identity_source": (
            "actual VCS parsing receipts followed by post-compile leaf hashing"
        ),
        "precompile_server_source_preflight": False,
    }
    _write(output, receipt)
    if errors:
        raise RuntimeErrorContract("; ".join(errors))
    return receipt


def qualify_run(
    run_id: str, sim_log: Path, observer_log: Path, output: Path
) -> dict[str, Any]:
    sim_text = sim_log.read_text(encoding="utf-8", errors="replace")
    observer_text = observer_log.read_text(
        encoding="utf-8", errors="replace"
    )
    natural_count = sim_text.count(NATURAL_MARKER)
    observer_enabled_count = sim_text.count(OBSERVER_MARKER)
    observer_banner_count = observer_text.count(
        "Conv native four-lane progress observer v1"
    )
    feature_sim_count = sim_text.count(FEATURE_MARKER)
    feature_log_count = observer_text.count(FEATURE_MARKER)
    canonical_rows = [
        row
        for row in observer_text.splitlines()
        if row.startswith(CANONICAL_MARKER)
    ]
    complete_count = sum(COMPLETE_DECISION in row for row in canonical_rows)
    errors: list[str] = []
    if natural_count != 1:
        errors.append(f"natural terminal marker count={natural_count}")
    if observer_enabled_count < 1:
        errors.append("observer time-0 enable marker is missing")
    if observer_banner_count < 1:
        errors.append("observer progress log banner is missing")
    if feature_sim_count != 1 or feature_log_count != 1:
        errors.append(
            "feature time-0 binding marker count differs "
            f"(sim={feature_sim_count}, log={feature_log_count})"
        )
    if not canonical_rows or complete_count != 1:
        errors.append(
            "canonical expected-stage completion record is missing or ambiguous"
        )
    elif COMPLETE_DECISION not in canonical_rows[-1]:
        errors.append("last canonical decision is not stage-prefix completion")
    receipt = {
        "schema": "conv-native-four-lane-natural-terminal-v1",
        "run_id": run_id,
        "valid": not errors,
        "errors": errors,
        "natural_terminal": natural_count == 1,
        "natural_terminal_marker": NATURAL_MARKER,
        "natural_terminal_marker_count": natural_count,
        "observer_time0_enabled": observer_enabled_count >= 1,
        "observer_log_present": observer_banner_count >= 1,
        "feature_time0_binding": (
            feature_sim_count == 1 and feature_log_count == 1
        ),
        "canonical_record_count": len(canonical_rows),
        "expected_stage_completion_count": complete_count,
        "last_canonical_record": canonical_rows[-1] if canonical_rows else None,
        "sim_log_sha256": numeric_base.sha256(sim_log),
        "observer_log_sha256": numeric_base.sha256(observer_log),
    }
    _write(output, receipt)
    if errors:
        raise RuntimeErrorContract("; ".join(errors))
    return receipt


def analyze(
    package_root: Path, cfg_root: Path, evidence_root: Path
) -> dict[str, Any]:
    base_result = numeric_base.analyze(package_root, cfg_root, evidence_root)
    manifest = numeric_base.load_json(package_root / "package_manifest.json")
    identity_path = evidence_root / "production_rtl_identity.json"
    identity = (
        numeric_base.load_json(identity_path)
        if identity_path.is_file()
        else {
            "schema": "conv-native-four-lane-production-rtl-identity-v1",
            "valid": False,
            "missing": True,
            "errors": ["production RTL identity receipt is missing"],
        }
    )
    run_ids = [
        *manifest.get("conv_run_ids", []),
        *manifest.get("tail_run_ids", []),
    ]
    terminals = []
    for run_id in run_ids:
        path = evidence_root / "natural_terminal" / f"{run_id}.json"
        if path.is_file():
            terminals.append(numeric_base.load_json(path))
    natural_count = sum(
        item.get("natural_terminal") is True and item.get("valid") is True
        for item in terminals
    )
    signal_path = evidence_root / "signal_status.txt"
    signal_status = (
        signal_path.read_text(encoding="ascii").strip()
        if signal_path.is_file()
        else "MISSING"
    )
    passed = (
        base_result.get("status") == numeric_base.PASS_STATUS
        and identity.get("valid") is True
        and natural_count == 27
        and base_result.get("readback_count") == 320
        and base_result.get("missing_count") == 0
        and base_result.get("mismatch_byte_count") == 0
        and signal_status == "NONE"
    )
    result = {
        **base_result,
        "schema": "conv-native-four-lane-df23e4d-server-result-v1",
        "status": PASS_STATUS if passed else "CONV_NATIVE_FOUR_LANE_SERVER_FAILURE",
        "candidate_release": False,
        "execution_gate": {
            **base_result["execution_gate"],
            "natural_terminal_count": natural_count,
            "required_natural_terminal_count": 27,
            "all_natural_terminals": natural_count == 27,
            "production_rtl_identity_match": identity.get("valid") is True,
            "formal_readback_count": base_result.get("readback_count"),
            "missing_count": base_result.get("missing_count"),
            "mismatch_byte_count": base_result.get("mismatch_byte_count"),
            "signal_status": signal_status,
            "no_external_signal": signal_status == "NONE",
            "conjunction_pass": passed,
        },
        "production_rtl_identity": identity,
        "natural_terminal_receipts": terminals,
    }
    _write(evidence_root / "SERVER_RESULT_GATE.json", result)
    return result


def _copy_extra(
    source: Path,
    return_dir: Path,
    relative: str,
    records: list[dict[str, Any]],
    *,
    required: bool,
    max_bytes: int,
) -> None:
    if not source.is_file():
        if required:
            raise RuntimeErrorContract(f"required return file is missing: {source}")
        return
    if source.stat().st_size > max_bytes:
        raise RuntimeErrorContract(f"return file exceeds budget: {source}")
    target = return_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    records.append(
        {
            "path": relative,
            "size_bytes": target.stat().st_size,
            "sha256": numeric_base.sha256(target),
            "required": required,
            "max_bytes": max_bytes,
        }
    )


def _bound_return_file(path: Path, max_bytes: int) -> bool:
    if not path.is_file() or path.stat().st_size <= max_bytes:
        return False
    payload = path.read_bytes()
    half = max_bytes // 2
    marker = (
        b"\n--- RETURN LOG MIDDLE OMITTED BY DECLARED BYTE BUDGET ---\n"
    )
    bounded = payload[: half - len(marker)] + marker + payload[-half:]
    path.write_bytes(bounded)
    return True


def _source_for_return(
    relative: str,
    *,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
    package_root: Path,
) -> str:
    path = Path(relative)
    if path.parts and path.parts[0] == "evidence":
        return str(evidence_root / Path(*path.parts[1:]))
    if path.parts and path.parts[0] == "runs":
        return str(run_root / Path(*path.parts[1:]))
    if path.parts and path.parts[0] == "readbacks":
        return str(cfg_root / Path(*path.parts[1:]))
    if path.parts and path.parts[0] == "source_package":
        return str(package_root / Path(*path.parts[1:]))
    return "return-collector-generated"


def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
    package_root: Path,
) -> dict[str, Any]:
    observer_base.collect(
        server_root,
        install_name,
        evidence_root,
        run_root,
        cfg_root,
        package_root,
    )
    manifest = numeric_base.load_json(package_root / "package_manifest.json")
    return_dir = server_root / f"{install_name}_return"
    return_zip = return_dir.with_suffix(".zip")
    return_sha = Path(str(return_zip) + ".sha256")
    allowlist_path = return_dir / "RETURN_ALLOWLIST.json"
    allowlist = numeric_base.load_json(allowlist_path)
    records = allowlist.get("records")
    if not isinstance(records, list):
        raise RuntimeErrorContract("return allowlist records are missing")
    _copy_extra(
        evidence_root / "observer_precompile.json",
        return_dir,
        "evidence/observer_precompile.json",
        records,
        required=True,
        max_bytes=64 * 1024,
    )
    _copy_extra(
        evidence_root / "production_rtl_identity.json",
        return_dir,
        "evidence/production_rtl_identity.json",
        records,
        required=False,
        max_bytes=64 * 1024,
    )
    _copy_extra(
        evidence_root / "signal_status.txt",
        return_dir,
        "evidence/signal_status.txt",
        records,
        required=True,
        max_bytes=64 * 1024,
    )
    _copy_extra(
        package_root / "package_manifest.json",
        return_dir,
        "source_package/package_manifest.json",
        records,
        required=True,
        max_bytes=2 * 1024 * 1024,
    )
    _copy_extra(
        evidence_root / "compile_argv.txt",
        return_dir,
        "evidence/compile_argv.txt",
        records,
        required=False,
        max_bytes=64 * 1024,
    )
    run_ids = [
        *manifest.get("conv_run_ids", []),
        *manifest.get("tail_run_ids", []),
    ]
    for run_id in run_ids:
        _copy_extra(
            run_root / run_id / "return_observer.log",
            return_dir,
            f"runs/{run_id}/return_observer.log",
            records,
            required=False,
            max_bytes=8 * 1024 * 1024,
        )
        _copy_extra(
            evidence_root / "natural_terminal" / f"{run_id}.json",
            return_dir,
            f"evidence/natural_terminal/{run_id}.json",
            records,
            required=False,
            max_bytes=64 * 1024,
        )
        _copy_extra(
            run_root / run_id / "simulator_argv.txt",
            return_dir,
            f"runs/{run_id}/simulator_argv.txt",
            records,
            required=False,
            max_bytes=64 * 1024,
        )
        _copy_extra(
            run_root / run_id / "host_progress.log",
            return_dir,
            f"runs/{run_id}/host_progress.log",
            records,
            required=False,
            max_bytes=8 * 1024 * 1024,
        )
    bounded_paths: list[str] = []
    for record in records:
        relative = str(record.get("path"))
        target = return_dir / Path(*Path(relative).parts)
        maximum = (
            8 * 1024 * 1024
            if relative.endswith(".log")
            else 2 * 1024 * 1024
        )
        if _bound_return_file(target, maximum):
            bounded_paths.append(relative)
        if target.is_file():
            record.update(
                {
                    "source": _source_for_return(
                        relative,
                        evidence_root=evidence_root,
                        run_root=run_root,
                        cfg_root=cfg_root,
                        package_root=package_root,
                    ),
                    "size_bytes": target.stat().st_size,
                    "sha256": numeric_base.sha256(target),
                    "required": (
                        relative
                        in {
                            "evidence/package_preflight.json",
                            "evidence/install_preflight.json",
                            "evidence/compile_exit_status.txt",
                            "evidence/run_exit_status.txt",
                            "evidence/signal_status.txt",
                            "evidence/SERVER_RESULT_GATE.json",
                            "source_package/package_manifest.json",
                        }
                    ),
                    "max_bytes": maximum,
                    "missing_semantics": (
                        "required control evidence"
                        if relative.startswith("evidence/")
                        else "optional on an early failure; required by success gate"
                    ),
                }
            )
    return_manifest = {
        "schema": "conv-native-four-lane-df23e4d-return-manifest-v1",
        "install_name": install_name,
        "source_package_manifest_sha256": numeric_base.sha256(
            package_root / "package_manifest.json"
        ),
        "server_result_status": (
            numeric_base.load_json(
                evidence_root / "SERVER_RESULT_GATE.json"
            ).get("status")
            if (evidence_root / "SERVER_RESULT_GATE.json").is_file()
            else "MISSING"
        ),
        "records_excluding_this_manifest": sorted(
            records, key=lambda item: str(item["path"])
        ),
        "bounded_log_paths": bounded_paths,
        "return_exact_set_policy": (
            "records plus RETURN_MANIFEST.json and RETURN_ALLOWLIST.json only"
        ),
    }
    return_manifest_path = return_dir / "RETURN_MANIFEST.json"
    _write(return_manifest_path, return_manifest)
    records.append(
        {
            "path": "RETURN_MANIFEST.json",
            "source": "return-collector-generated",
            "size_bytes": return_manifest_path.stat().st_size,
            "sha256": numeric_base.sha256(return_manifest_path),
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
            "missing_semantics": "authoritative return identity is absent",
        }
    )
    allowlist_path.write_text(
        json.dumps(allowlist, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return observer_base._repack_return(
        return_dir=return_dir,
        return_zip=return_zip,
        return_sha=return_sha,
    )


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-root", type=Path, required=True)
    ins = sub.add_parser("verify-install")
    ins.add_argument("--package-root", type=Path, required=True)
    ins.add_argument("--cfg-root", type=Path, required=True)
    comp = sub.add_parser("compile-identity")
    comp.add_argument("--compile-log", type=Path, required=True)
    comp.add_argument("--output", type=Path, required=True)
    qual = sub.add_parser("qualify-run")
    qual.add_argument("--run-id", required=True)
    qual.add_argument("--sim-log", type=Path, required=True)
    qual.add_argument("--observer-log", type=Path, required=True)
    qual.add_argument("--output", type=Path, required=True)
    mat = sub.add_parser("materialize-tail")
    mat.add_argument("--package-root", type=Path, required=True)
    mat.add_argument("--cfg-root", type=Path, required=True)
    mat.add_argument("--output", type=Path, required=True)
    ana = sub.add_parser("analyze")
    ana.add_argument("--package-root", type=Path, required=True)
    ana.add_argument("--cfg-root", type=Path, required=True)
    ana.add_argument("--evidence-root", type=Path, required=True)
    col = sub.add_parser("collect")
    col.add_argument("--server-root", type=Path, required=True)
    col.add_argument("--install-name", required=True)
    col.add_argument("--evidence-root", type=Path, required=True)
    col.add_argument("--run-root", type=Path, required=True)
    col.add_argument("--cfg-root", type=Path, required=True)
    col.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        value = preflight(args.package_root)
    elif args.command == "verify-install":
        value = numeric_base.verify_install(args.package_root, args.cfg_root)
    elif args.command == "compile-identity":
        value = collect_compile_identity(args.compile_log, args.output)
    elif args.command == "qualify-run":
        value = qualify_run(
            args.run_id, args.sim_log, args.observer_log, args.output
        )
    elif args.command == "materialize-tail":
        value = numeric_base.materialize_tail_inputs(
            args.package_root, args.cfg_root
        )
        _write(args.output, value)
    elif args.command == "analyze":
        value = analyze(
            args.package_root, args.cfg_root, args.evidence_root
        )
    else:
        value = collect(
            args.server_root,
            args.install_name,
            args.evidence_root,
            args.run_root,
            args.cfg_root,
            args.package_root,
        )
    print(json.dumps(value, ensure_ascii=False))
    if args.command == "analyze" and value.get("status") != PASS_STATUS:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
