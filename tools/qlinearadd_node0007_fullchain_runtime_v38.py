#!/usr/bin/env python3
"""Install-subtree runtime adapter for the node0007 six-stage full chain."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
import qlinearadd_node0007_split_server_runtime_v25 as base


RuntimeGateError = base.RuntimeGateError


def _output_prefix(manifest: dict[str, Any]) -> str:
    return (
        f"install/codex_runs/{manifest['install_name']}/"
        "{attempt}/"
    )


def preflight(package_root: Path) -> dict[str, Any]:
    root = package_root.resolve()
    manifest = base.load_json(root / base.MANIFEST)
    observed = base.file_records(root)
    if manifest.get("files") != observed:
        raise RuntimeGateError("package exact-set differs")
    split = manifest.get("split_segment_contract")
    if not isinstance(split, dict):
        raise RuntimeGateError("full-chain contract absent")
    stages = list(split.get("stage_names", []))
    if (
        stages
        != [
            "op_a_dequant",
            "op_b_dequant",
            "op_relocation_pad",
            "op_fp32_add",
            "op_tail_mul",
            "op_tail_round",
        ]
        or split.get("final_stage") != "op_tail_round"
        or split.get("result_mode") != "FULL_NUMERIC_28D"
        or int(split.get("expected_output_count", -1)) != 28
    ):
        raise RuntimeGateError("six-stage/full-28D contract differs")
    sca = base.load_json(root / "workload/runtime/sca_cfg.json")
    sca_d = base.load_json(root / "workload/runtime/sca_cfg_D.json")
    if int(sca.get("Repeat_Num", -1)) != 6:
        raise RuntimeGateError("SCA six-stage repeat differs")
    input_prefix = f"install/cfg_pkg/{manifest['install_name']}/"
    preload_paths = [
        str(value["path"])
        for value in sca.values()
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    ]
    if (
        not preload_paths
        or len(preload_paths) != int(split["expected_preload_count"])
        or any(not path.startswith(input_prefix) for path in preload_paths)
    ):
        raise RuntimeGateError("SCA input namespace/count differs")
    for path in preload_paths:
        relative = path.removeprefix(input_prefix)
        if not base.safe_child(root / "workload/runtime", relative).is_file():
            raise RuntimeGateError(f"SCA preload absent: {relative}")
    checks = list(split["output_checks"])
    expected_keys = {str(item["sca_key"]) for item in checks}
    if len(checks) != 28 or set(sca_d) != expected_keys:
        raise RuntimeGateError("formal D exact-set differs")
    output_prefix = _output_prefix(manifest)
    for item in checks:
        record = sca_d[str(item["sca_key"])]
        expected = output_prefix + str(item["runtime_path"])
        if record.get("path") != expected:
            raise RuntimeGateError("SCA-D install-subtree path differs")
        if int(record["length"]) * 16 != int(item["decoded_bytes"]):
            raise RuntimeGateError("SCA-D length differs")
        golden = base.safe_child(root, str(item["golden_path"]))
        if len(base.decode_128bit(golden)) != int(item["decoded_bytes"]):
            raise RuntimeGateError("formal golden length differs")
    actual_stage_dirs = {
        path.name
        for path in (root / "workload/runtime/install").iterdir()
        if path.is_dir() and path.name.startswith("op_")
    }
    if actual_stage_dirs != {
        "op_a_dequant",
        "op_b_dequant",
        "op_relocation_pad",
    }:
        raise RuntimeGateError("packaged external-input stage set differs")
    return {
        "schema": "qlinearadd-node0007-fullchain-preflight-v38",
        "valid": True,
        "stage_count": 6,
        "preload_count": len(preload_paths),
        "formal_D_count": len(checks),
        "formal_D_initially_absent_by_contract": True,
    }


def preflight_installed(
    package_root: Path, cfg_root: Path, run_root: Path
) -> dict[str, Any]:
    report = preflight(package_root)
    for relative in ("sca_cfg.json", "sca_cfg_D.json", "install/execplan.txt"):
        if not base.safe_child(cfg_root, relative).is_file():
            raise RuntimeGateError(f"installed payload absent: {relative}")
    manifest = base.load_json(package_root / base.MANIFEST)
    for item in manifest["split_segment_contract"]["output_checks"]:
        if base.safe_child(run_root, str(item["runtime_path"])).exists():
            raise RuntimeGateError("formal D target was preseeded")
    return {
        "schema": "qlinearadd-node0007-fullchain-installed-preflight-v38",
        "valid": True,
        "package_preflight": report,
        "formal_D_initially_absent": True,
    }


def analyze_full(
    package_root: Path,
    evidence_root: Path,
    run_root: Path,
    compile_status: int,
    simulation_status: int,
) -> dict[str, Any]:
    manifest = base.load_json(package_root / base.MANIFEST)
    split = manifest["split_segment_contract"]
    sim_log = run_root / "sim.log"
    text = (
        sim_log.read_text(encoding="utf-8", errors="replace")
        if sim_log.is_file()
        else ""
    )
    starts = len(re.findall(r"INFO: slice start", text))
    finishes = len(
        re.findall(r"INFO: slice completed after \d+ cycles", text)
    )
    identity = re.escape(str(manifest["install_name"]))
    loader = {
        "sca_cfg_echo_exact": bool(
            re.search(
                rf"Using SCA cfg file:\s+\S*install/cfg_pkg/{identity}/sca_cfg\.json",
                text.replace("\\", "/"),
            )
        ),
        "sca_cfg_d_echo_exact": bool(
            re.search(
                rf"Using SCA cfg D file:\s+\S*install/cfg_pkg/{identity}/sca_cfg_D\.json",
                text.replace("\\", "/"),
            )
        ),
        "preload_count_exact": bool(
            re.search(
                rf"JSON config:\s*{int(split['expected_preload_count'])}\s+matrices loaded",
                text,
            )
        ),
        "dump_count_exact": bool(
            re.search(r"JSON_D config:\s*28\s+matrices dumped", text)
        ),
        "natural_completion_exact": (
            text.count("Simulation completed successfully!") == 1
        ),
        "ordered_stage_count_exact": starts == 6 and finishes == 6,
        "no_critical_markers": not any(
            marker in text
            for marker in ("Cannot open", "skip matrix readback", "$fatal", "Fatal:")
        ),
    }
    expected_paths = {
        str(item["runtime_path"]) for item in split["output_checks"]
    }
    observed_paths = {
        path.relative_to(run_root).as_posix()
        for path in run_root.rglob("matrix_D_linearized_128bit.txt")
        if path.is_file()
    }
    checks: list[dict[str, Any]] = []
    missing = invalid = mismatch_bytes = 0
    for item in split["output_checks"]:
        actual = base.safe_child(run_root, str(item["runtime_path"]))
        if not actual.is_file():
            missing += 1
            checks.append({**item, "status": "missing"})
            continue
        try:
            payload = base.decode_128bit(actual)
            golden = base.decode_128bit(
                base.safe_child(package_root, str(item["golden_path"]))
            )
        except RuntimeGateError as error:
            invalid += 1
            checks.append({**item, "status": "invalid", "error": str(error)})
            continue
        if len(payload) != int(item["decoded_bytes"]):
            invalid += 1
            checks.append({**item, "status": "invalid_length"})
            continue
        mismatch = sum(
            left != right for left, right in zip(payload, golden, strict=False)
        ) + abs(len(payload) - len(golden))
        mismatch_bytes += mismatch
        checks.append(
            {
                **item,
                "status": "pass" if mismatch == 0 else "mismatch",
                "actual_sha256": base.sha256(actual),
                "mismatch_bytes": mismatch,
            }
        )
    exact_set = observed_paths == expected_paths
    passed = (
        compile_status == 0
        and simulation_status == 0
        and all(loader.values())
        and exact_set
        and missing == 0
        and invalid == 0
        and mismatch_bytes == 0
    )
    result = {
        "schema": "qlinearadd-node0007-fullchain-server-result-v38",
        "status": (
            "QLINEARADD_NODE0007_SERVER_PASS"
            if passed
            else "QLINEARADD_NODE0007_SERVER_FAILURE"
        ),
        "claim_boundary": (
            "Full six-stage natural terminal plus final UINT8 28D exact "
            "golden comparison; E4/E5 requires returned production identity "
            "and mainline acceptance."
        ),
        "result_gate_conjunction": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "loader_checks": loader,
            "output_exact_set_complete": exact_set,
            "missing_count_zero": missing == 0,
            "invalid_count_zero": invalid == 0,
            "mismatch_count_zero": mismatch_bytes == 0,
            "all_terms_true": passed,
        },
        "expected_readback_count": 28,
        "observed_readback_count": len(observed_paths),
        "missing_count": missing,
        "invalid_count": invalid,
        "mismatch_byte_count": mismatch_bytes,
        "mismatch_evaluable": missing == 0 and invalid == 0,
        "checks": checks,
    }
    base.write_json(evidence_root / "SERVER_RESULT_GATE.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    value = sub.add_parser("manifest-value")
    value.add_argument("--package-root", type=Path, required=True)
    value.add_argument("--key", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-root", type=Path, required=True)
    installed = sub.add_parser("preflight-installed")
    installed.add_argument("--package-root", type=Path, required=True)
    installed.add_argument("--cfg-root", type=Path, required=True)
    installed.add_argument("--run-root", type=Path, required=True)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--package-root", type=Path, required=True)
    analyze.add_argument("--evidence-root", type=Path, required=True)
    analyze.add_argument("--run-root", type=Path, required=True)
    analyze.add_argument("--compile-status", type=int, required=True)
    analyze.add_argument("--simulation-status", type=int, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--server-root", type=Path, required=True)
    collect.add_argument("--install-name", required=True)
    collect.add_argument("--package-root", type=Path, required=True)
    collect.add_argument("--evidence-root", type=Path, required=True)
    collect.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "manifest-value":
            print(base.manifest_value(args.package_root, args.key))
        elif args.command == "preflight":
            print(json.dumps(preflight(args.package_root)))
        elif args.command == "preflight-installed":
            print(
                json.dumps(
                    preflight_installed(
                        args.package_root, args.cfg_root, args.run_root
                    )
                )
            )
        elif args.command == "analyze":
            result = analyze_full(
                args.package_root,
                args.evidence_root,
                args.run_root,
                args.compile_status,
                args.simulation_status,
            )
            print(json.dumps(result))
            return (
                0
                if result["result_gate_conjunction"]["all_terms_true"]
                else 1
            )
        else:
            print(
                json.dumps(
                    base.collect(
                        args.server_root,
                        args.install_name,
                        args.package_root,
                        args.evidence_root,
                        args.run_root,
                        args.run_root,
                    )
                )
            )
    except Exception as error:
        print(f"full-chain runtime failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
