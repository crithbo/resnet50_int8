#!/usr/bin/env python3
"""Audit the one exact p31 ZIP and its candidate-decomposed parser surface."""

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
PACKAGE = "r5_n4_0cc_p31_postclear"
SOURCE = "r5_n4_0cc_p30_bankvalid"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p30_bankvalid.zip"
SOURCE_SHA = "8229b380c9b33f99c8bd27d3eb21ce2ce17aae1b5eb0278926f27307887cbf34"
BOUNDARIES = (
    "row2_block_bank_ready_00", "row2_block_bank_ready_0f", "row2_block_bank_ready_f0",
    "row2_block_bank_ready_ff", "row2_block_bank_ready_other", "final_same_row2_block",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def parse_case(parser: Path, root: Path, case: str, seen: set[str], enabled: bool = True, noise_bytes: int = 0) -> dict:
    instance = "tb_NDP_Top_new_phy.U.U_Slice[0].u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
    lines = [f"CODEX_PROBE_V1 kind=ENABLED boundary={name} instance={instance}" for name in BOUNDARIES] if enabled else []
    lines += [f"CODEX_PROBE_V1 kind=TRIGGER boundary={name} instance={instance} mask=1 payload=0" for name in sorted(seen)]
    log = root / f"{case}.log"
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        if noise_bytes:
            chunk = "NON_TARGET_MULTI_INSTANCE_NOISE %m tb_NDP_Top_new_phy.U.U_Slice[7] " + "x" * 960 + "\n"
            for _ in range((noise_bytes // len(chunk)) + 1):
                stream.write(chunk)
        stream.write("\n".join(lines) + "\n")
    output = root / f"{case}.json"
    process = run([sys.executable, str(parser), "--log", str(log), "--output", str(output)])
    decision = json.loads(output.read_text(encoding="utf-8"))
    return {"exit_code": process.returncode, "log_bytes": log.stat().st_size, "decision": decision}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        raise RuntimeError("refusing to overwrite p31 family audit")
    zip_path = args.zip.resolve()
    errors: list[str] = []
    checks: dict[str, bool] = {}
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise RuntimeError("p30 exact source differs")
    with tempfile.TemporaryDirectory(prefix="p31_family_") as temp_name:
        temp = Path(temp_name)
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            checks["zip_crc"] = archive.testzip() is None
            checks["zip_duplicate_free"] = len(names) == len(set(names))
            checks["zip_single_root"] = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
            checks["zip_safe_members"] = all(
                not PurePosixPath(item.filename).is_absolute()
                and ".." not in PurePosixPath(item.filename).parts
                and "\\" not in item.filename
                and not stat.S_ISLNK(item.external_attr >> 16)
                for item in infos
            )
            archive.extractall(temp)
        package = temp / PACKAGE
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        actual = {
            item.relative_to(package).as_posix(): {"sha256": sha(item), "size_bytes": item.stat().st_size}
            for item in sorted(package.rglob("*"))
            if item.is_file() and item.name != "package_manifest.json"
        }
        checks["manifest_exact_set"] = manifest.get("files") == actual
        checks["epoch_bound"] = (
            manifest.get("rule_change_epoch", {}).get("epoch_id") == "20260810-first-fresh-extra-audit-v1"
            and manifest.get("rule_change_epoch", {}).get("package_id") == PACKAGE
            and manifest.get("rule_change_epoch", {}).get("first_fresh_after_change") is True
        )
        checks["diagnostic_claim_only"] = manifest.get("candidate_release") is False and manifest.get("formal_readback_count") == 0
        preflight = run([sys.executable, str(package / "package_tools/node0004_assumed_hardware_server_runtime.py"), "preflight", "--package-root", str(package)])
        guard = run([sys.executable, str(package / "package_tools/node0004_package_observer_guard.py"), "--package-root", str(package)])
        syntax = run([sys.executable, "-W", "error", "-m", "py_compile", *map(str, sorted(package.rglob("*.py")))])
        checks["package_preflight"] = preflight.returncode == 0
        checks["observer_guard"] = guard.returncode == 0
        checks["python_syntax"] = syntax.returncode == 0
        with zipfile.ZipFile(SOURCE_ZIP) as source_archive:
            prefix = SOURCE + "/"
            frozen = sorted(name[len(prefix):] for name in source_archive.namelist() if name.startswith(prefix + "workload/runtime/runs/c0/install/") and not name.endswith("/"))
            checks["frozen_87_payload"] = len(frozen) == 87 and all((package / name).read_bytes() == source_archive.read(prefix + name) for name in frozen)
            checks["sca_normalized_equal"] = all(
                (package / name).read_text(encoding="utf-8").replace(PACKAGE, SOURCE) == source_archive.read(prefix + name).decode()
                for name in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json")
            )
        parser = package / "package_tools/source_bound_causal_parser.py"
        cases = {
            "not_reached": ({"row2_block_bank_ready_0f"}, "TARGET_FINAL_SAME_ROW2_BLOCK_NOT_REACHED"),
            "final_0f": ({"row2_block_bank_ready_0f", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_0F"),
            "final_00": ({"row2_block_bank_ready_0f", "row2_block_bank_ready_00", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_00"),
            "final_f0": ({"row2_block_bank_ready_0f", "row2_block_bank_ready_f0", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_F0"),
            "final_ff": ({"row2_block_bank_ready_0f", "row2_block_bank_ready_ff", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_FF"),
            "final_other": ({"row2_block_bank_ready_0f", "row2_block_bank_ready_other", "final_same_row2_block"}, "FINAL_POSTCLEAR_BANK_READY_OTHER"),
        }
        case_reports = {name: parse_case(parser, temp, name, seen, noise_bytes=(17 * 1024 * 1024 if name == "final_ff" else 0)) for name, (seen, _) in cases.items()}
        checks["six_candidate_positive_controls"] = all(
            case_reports[name]["exit_code"] == 0 and case_reports[name]["decision"]["decision"] == expected
            and len(case_reports[name]["decision"]["matching_candidate_ids"]) == 1
            for name, (_, expected) in cases.items()
        )
        checks["overbudget_multi_instance_parser"] = case_reports["final_ff"]["log_bytes"] > 16 * 1024 * 1024 and case_reports["final_ff"]["decision"]["decision"] == "FINAL_POSTCLEAR_BANK_READY_FF"
        missing = parse_case(parser, temp, "missing_enable", {"row2_block_bank_ready_0f"}, enabled=False)
        conflict = parse_case(parser, temp, "conflict", {"row2_block_bank_ready_0f", "row2_block_bank_ready_ff", "row2_block_bank_ready_f0", "final_same_row2_block"})
        checks["negative_missing_enable_fail_closed"] = missing["exit_code"] != 0 and missing["decision"]["decision"] == "EVIDENCE_INCOMPLETE"
        checks["negative_undeclared_signature_fail_closed"] = conflict["exit_code"] != 0 and conflict["decision"]["decision"] == "EVIDENCE_INCOMPLETE"
    errors.extend(name for name, passed in checks.items() if not passed)
    report = {
        "schema": "conv-native-four-lane-p31-postclear-family-audit-v1",
        "valid": not errors,
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "candidate_ids": [expected for _, expected in cases.values()],
        "candidate_case_results": case_reports,
        "positive_control_count": 6,
        "negative_control_count": 2,
        "pairwise_distinguishable": checks.get("six_candidate_positive_controls", False),
        "zip": {"path": zip_path.relative_to(ROOT).as_posix(), "bytes": zip_path.stat().st_size, "sha256": sha(zip_path)},
        "claim_boundary": "Static/package-local diagnostic audit only; no production natural terminal, formal D or E3-E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
