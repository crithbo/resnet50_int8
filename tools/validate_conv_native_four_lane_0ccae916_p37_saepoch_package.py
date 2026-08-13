#!/usr/bin/env python3
"""Audit p37 package identity, frozen payload, and exact SA beat correlator."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p37_saepoch"
SOURCE = "r5_n4_0cc_p36b_semfp"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
SOURCE_SHA = "0111176e62fca03a023bbd83098067191113bdc4a91a7bf5c7e0e37c3d288e0e"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
PRIOR_PASS_SHA = "7e7cd5ea7e0ce3fbf0dcd6073dff27dbe0bd0b5abd619ccd67adfbacf02cfc3c"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def parser_case(parser: Path, contract: Path, text: str, root: Path, name: str) -> dict:
    log = root / f"{name}.log"
    output = root / f"{name}.json"
    log.write_text(text, encoding="utf-8", newline="\n")
    result = run([sys.executable, str(parser), "--log", str(log), "--contract", str(contract), "--output", str(output)])
    value = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {"decision": "PARSER_DID_NOT_PUBLISH"}
    return {"exit_code": result.returncode, "decision": value, "log_bytes": log.stat().st_size}


def mutate_fixture(text: str, contract: dict, mode: str) -> str:
    expected = contract["expected_instances"]
    near = contract["near_miss_instances"]
    output: list[str] = []
    for line in text.splitlines():
        if "boundary=sa_lane" not in line or "kind=EVENT" not in line:
            output.append(line)
            continue
        tokens = line.split()
        fields = dict(token.split("=", 1) for token in tokens[1:] if "=" in token)
        lane = next((index for index, value in enumerate(expected) if fields.get("instance") == value), -1)
        time = int(fields.get("time", "-1"))
        if mode == "missing_lane" and lane == 7 and time == 120:
            continue
        if mode == "wrong_instance" and lane == 0 and time == 120:
            line = line.replace(expected[0], near[0])
        elif mode == "unknown" and lane == 0 and time == 120:
            line = line.replace("payload=", "payload=Z", 1)
        elif mode == "width" and lane == 0 and time == 120:
            line = line.replace("payload_width=40", "payload_width=39")
        elif mode == "identical" and time == 120:
            data = lane + 1
            payload = (0x5F << 33) | (data << 1) | 1
            line = " ".join(f"payload={payload:x}" if token.startswith("payload=") else token for token in line.split())
        elif mode == "mixed_lane_same" and time == 120 and lane > 0:
            payload = int(fields["payload"], 16)
            payload = (0x4F << 33) | (payload & ((1 << 33) - 1))
            line = " ".join(f"payload={payload:x}" if token.startswith("payload=") else token for token in line.split())
        output.append(line)
    return "\n".join(output) + "\n"


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--zip", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    if args.output.exists():
        raise RuntimeError("refusing to overwrite p37 family audit")
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise RuntimeError("exact p36b source differs")
    checks: dict[str, bool] = {}
    cases: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="p37_family_") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(args.zip) as archive:
            infos = archive.infolist()
            names = [row.filename for row in infos]
            checks["zip_crc"] = archive.testzip() is None
            checks["zip_duplicate_free"] = len(names) == len(set(names))
            checks["zip_single_root"] = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
            checks["zip_safe_members"] = all(not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr >> 16) for row in infos)
            archive.extractall(root)
        package = root / PACKAGE
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        actual = {row.relative_to(package).as_posix(): {"sha256": sha(row), "size_bytes": row.stat().st_size} for row in sorted(package.rglob("*")) if row.is_file() and row.name != "package_manifest.json"}
        checks["manifest_exact_set"] = manifest.get("files") == actual
        epoch = manifest.get("rule_change_epoch", {})
        checks["same_epoch_prior_pass_bound"] = (
            epoch.get("epoch_id") == EPOCH and epoch.get("package_id") == PACKAGE
            and epoch.get("first_fresh_after_change") is False
            and epoch.get("prior_first_fresh_pass", {}).get("sha256") == PRIOR_PASS_SHA
        )
        checks["diagnostic_claim_only"] = manifest.get("candidate_release") is False and manifest.get("formal_readback_count") == 0
        checks["package_preflight"] = run([sys.executable, str(package / "package_tools/node0004_assumed_hardware_server_runtime.py"), "preflight", "--package-root", str(package)]).returncode == 0
        checks["observer_guard"] = run([sys.executable, str(package / "package_tools/node0004_package_observer_guard.py"), "--package-root", str(package)]).returncode == 0
        checks["python_syntax"] = run([sys.executable, "-W", "error", "-m", "py_compile", *map(str, sorted(package.rglob("*.py")))]).returncode == 0
        with zipfile.ZipFile(SOURCE_ZIP) as source_archive:
            prefix = SOURCE + "/"
            frozen = sorted(name[len(prefix):] for name in source_archive.namelist() if name.startswith(prefix + "workload/runtime/runs/c0/install/") and not name.endswith("/"))
            checks["frozen_87_payload"] = len(frozen) == 87 and all((package / name).read_bytes() == source_archive.read(prefix + name) for name in frozen)
            checks["sca_normalized_equal"] = all((package / name).read_text(encoding="utf-8").replace(PACKAGE, SOURCE) == source_archive.read(prefix + name).decode() for name in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json"))
        parser = package / "package_tools/sa_epoch_parser.py"
        contract_path = package / "diagnostics/sa_epoch_contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        fixture = (package / "diagnostics/live_fixtures/arm_known_event.log").read_text(encoding="utf-8")
        cases["distinct"] = parser_case(parser, contract_path, fixture, root, "distinct")
        cases["identical"] = parser_case(parser, contract_path, mutate_fixture(fixture, contract, "identical"), root, "identical")
        cases["mixed_lane_same"] = parser_case(parser, contract_path, mutate_fixture(fixture, contract, "mixed_lane_same"), root, "mixed_lane_same")
        checks["two_positive_decisions"] = (
            cases["distinct"]["exit_code"] == 0 and cases["distinct"]["decision"]["decision"] == "DISTINCT_SA_DATA_BEATS_SHARE_ARM_TAG"
            and cases["identical"]["exit_code"] == 0 and cases["identical"]["decision"]["decision"] == "IDENTICAL_SA_DATA_BEAT_REACCEPT_OR_VALUE_COLLISION"
            and cases["mixed_lane_same"]["exit_code"] == 0 and cases["mixed_lane_same"]["decision"]["decision"] == "DISTINCT_SA_DATA_BEATS_SHARE_ARM_TAG"
        )
        for mode in ("missing_lane", "wrong_instance", "unknown", "width"):
            cases[mode] = parser_case(parser, contract_path, mutate_fixture(fixture, contract, mode), root, mode)
        checks["four_negatives_fail_closed"] = all(cases[name]["exit_code"] != 0 and cases[name]["decision"]["decision"] == "EVIDENCE_INCOMPLETE" for name in ("missing_lane", "wrong_instance", "unknown", "width"))
        checks["exact_eight_instances_and_width"] = len(contract.get("expected_instances", [])) == 8 and contract.get("payload_width_bits") == 40 and contract.get("lane_count") == 8
        observer = (package / "tb_probe/source_bound_causal_observer.svh").read_text(encoding="utf-8")
        checks["generated_eight_sa_boundaries"] = all(f"boundary=sa_lane{lane}_output_accepted_data" in observer for lane in range(8)) and observer.count("wire [39:0] payload_now") == 8
        request = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
        core = json.loads((package / "contracts/server_post_sim_return_contract.json").read_text(encoding="utf-8"))
        required = {row["plugin_id"] for row in request["plugins"] if row.get("required_for_adjudication")}
        dispositions = {row["plugin_id"] for row in core["partial_exit_live_causal_record"]["plugin_dispositions"]}
        checks["required_plugin_exact_disposition"] = required == {"arm_known_parser", "sa_epoch_parser"} and dispositions == required
        checks["parser_source_bound"] = sha(parser) == contract.get("parser_source_sha256")
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "conv-native-four-lane-p37-saepoch-family-audit-v1",
        "valid": not errors, "pass": not errors, "errors": errors,
        "checks": checks, "case_results": cases,
        "positive_control_count": 3, "negative_control_count": 4,
        "zip": {"path": args.zip.resolve().relative_to(ROOT).as_posix(), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "claim_boundary": "Static/package-local exact eight-lane accepted-data diagnostic only; no natural terminal, formal D or E3-E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
