"""Independent clean-extract/current-rule final audit for QAdd v54."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_bufready_v54"
SOURCE_NAME = "r5_qadd_n7_tailround_queueflow_v52"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-bufready-v54-package"
ZIP = LOCAL / f"{NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
EXTRACT = ROOT / "artifacts/q54a" / NAME
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_NAME}.zip"
REPORT = LOCAL / "final_zip_self_audit.json"
HDL_VALIDATOR = ROOT / "tools/validate_qlinearadd_node0007_tailround_bufready_v53_hdl.py"
PYTHON = Path(sys.executable)
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
PRIOR_PASS = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-package/first_fresh_extra_audit/validation.json"
PRIOR_PASS_SHA = "ed8e31a08cb76f0b8994ebaf29247dd1f0b603f0861acf710afcbb5219e4e976"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "plan_mutable": ROOT / ".agents/plan.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
    "server_readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    return {
        "argv": argv, "exit_code": result.returncode,
        "stdout_tail": result.stdout[-2000:], "stderr_tail": result.stderr[-2000:],
    }


def inventory(path: Path) -> tuple[str, dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    names: set[str] = set()
    duplicates: list[str] = []
    unsafe: list[str] = []
    symlinks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            roots.add(pure.parts[0])
            if info.filename in names: duplicates.append(info.filename)
            names.add(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename: unsafe.append(info.filename)
            if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF): symlinks.append(info.filename)
        if len(roots) != 1:
            raise RuntimeError(f"single root required: {sorted(roots)}")
        root = next(iter(roots))
        for info in archive.infolist():
            if not info.is_dir():
                files[info.filename[len(root) + 1:]] = archive.read(info)
    return root, files, {"crc_valid": bad is None, "root": root, "entry_count": len(files), "duplicates": duplicates, "unsafe_paths": unsafe, "symlinks": symlinks}


def normalized(value: bytes, pairs: list[tuple[bytes, bytes]]) -> bytes:
    result = value
    for before, after in pairs:
        result = result.replace(before, after)
    return result


def predicate_trace(parser_path: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("q54canonical", parser_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = "stage=1 active_cycles=1 " + " ".join(f"{key}=0" for key in module.QUALIFIED)
    state = (
        "2 | Q53_STATE | stage=1 group=0 local_slice=0 pingpong=0 ready0=0 ready1=1 selected_ready=0 "
        "mrm_ready5=0 req_valid=0x1 req_rw=0 req_addr=0 req_strb=0xf rd_en=0x1 "
        "bank_ready=0xfe valid_at_req=0x7 rreq_ready=0 buffer_mask=0xff nrm_barrier=0"
    )
    prefix = "# QADD_TAILROUND_BUFREADY_V53 enabled=1\n1 | EXEC_START | stage=1\n" + state + "\n"
    frozen = "\n".join(f"{20+i} | TAILROUND_FLOW | {base}" for i in range(4))
    hole = prefix + "3 | Q53_EVENT | kind=BUF5_WRITE_ACCEPT\n" + frozen
    accepted = prefix.replace(
        "ready0=0", "ready0=1"
    ).replace(
        "selected_ready=0", "selected_ready=1"
    ).replace(
        "mrm_ready5=0", "mrm_ready5=1"
    ).replace(
        "bank_ready=0xfe valid_at_req=0x7 rreq_ready=0", "bank_ready=0xff valid_at_req=0xf rreq_ready=1"
    ) + "3 | Q53_EVENT | kind=BUF5_READ_ACCEPT\n" + f"20 | TAILROUND_FLOW | {base}\n30 | COMP_FINISH | stage=1"
    simultaneous = prefix + (
        "3 | Q53_EVENT | kind=BUF5_WRITE_ACCEPT\n"
        "3 | Q53_EVENT | kind=BUF5_VALID_CLEAR\n"
        "3 | Q53_EVENT | kind=BUF5_READ_ACCEPT\n" + frozen
    )
    moving = prefix + f"20 | TAILROUND_FLOW | {base}\n21 | TAILROUND_FLOW | {base.replace('rdag_rreq=0', 'rdag_rreq=1')}"
    wrong_stage = hole.replace("1 | EXEC_START | stage=1", "1 | EXEC_START | stage=2", 1)
    wrong_owner = hole.replace("group=0 local_slice=0", "group=1 local_slice=0", 1)
    cases = {name: module.parse(text) for name, text in {"hole": hole, "accepted": accepted, "simultaneous": simultaneous, "moving": moving, "wrong_stage": wrong_stage, "wrong_owner": wrong_owner}.items()}
    checks = {
        "hole_hang": cases["hole"]["decision"] == "LONG_RUNNING_HANG_AT_BUFFER5_SELECTED_READ_READY",
        "hole_exact_missing_lane": cases["hole"]["candidate_matrix"]["C_BUFFER5_ROW_BANK_LANE_VALIDITY"]["missing_lanes"] == 8,
        "accepted_terminal": cases["accepted"]["decision"] == "TAILROUND_SPLIT_NATURAL_TERMINAL_OBSERVED" and cases["accepted"]["candidate_matrix"]["C_BUFFER5_READ_ACCEPT"]["observed"] is True,
        "simultaneous_events_independent": cases["simultaneous"]["candidate_matrix"]["C_BUFFER5_WRITE_CLEAR_ORDER"]["valid_clears"] == 1 and cases["simultaneous"]["candidate_matrix"]["C_BUFFER5_READ_ACCEPT"]["observed"] is True,
        "qualified_moving_not_level_progress": cases["moving"]["decision"] == "STILL_PROGRESSING_NOT_FINISHED",
        "wrong_stage_fail_closed": cases["wrong_stage"]["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "wrong_owner_fail_closed": cases["wrong_owner"]["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
    }
    return {"schema": "qlinearadd-node0007-tailround-bufready-v54-predicate-trace-v1", "pass": all(checks.values()), "errors": [key for key, value in checks.items() if not value], "checks": checks, "case_decisions": {name: row["decision"] for name, row in cases.items()}}


def main() -> int:
    errors: list[str] = []
    build = json.loads((LOCAL / "build_receipt.json").read_text(encoding="utf-8"))
    root, files, structure = inventory(ZIP)
    source_root, source_files, source_structure = inventory(SOURCE)
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    records = manifest.get("files", {})
    actual = set(files) - {"TEST_PACKAGE_MANIFEST.json"}
    manifest_exact = set(records) == actual and all(records[name] == {"size_bytes": len(files[name]), "sha256": sha_bytes(files[name])} for name in actual)
    extract_exact = all((EXTRACT / name).is_file() and (EXTRACT / name).read_bytes() == value for name, value in files.items())
    safe = structure["crc_valid"] and structure["root"] == NAME and not structure["duplicates"] and not structure["unsafe_paths"] and not structure["symlinks"]

    pairs = [
        (NAME.encode(), SOURCE_NAME.encode()),
        (b"qlinearadd_node0007_tailround_bufready_canonical_v53.py", b"qlinearadd_node0007_tailround_queueflow_canonical_v52.py"),
        (b"+QADD_TAILROUND_BUFREADY", b"+QADD_TAILROUND_QUEUEFLOW"),
        (b"QADD_TAILROUND_BUFREADY_V53", b"QADD_TAILROUND_QUEUEFLOW_V52"),
        (b"bufready=tb_probe/qlinearadd_node0007_tailround_bufready_v53.svh", b"queueflow=tb_probe/qlinearadd_node0007_tailround_queueflow_v52.svh"),
        (b"RETURN_OBSERVER,QADD_TAILROUND_BUFREADY", b"RETURN_OBSERVER,QADD_TAILROUND_QUEUEFLOW"),
    ]
    runner_control_equal = normalized(files["PREPARE_AND_RUN.sh"], pairs) == source_files["PREPARE_AND_RUN.sh"]
    frozen_members = [
        name for name in actual
        if name.startswith("workload/runtime/install/op_tail_round/")
        or name.startswith("workload/runtime/install/cfg_pkg/")
        or name.startswith("validation/golden/")
        or name in {"workload/runtime/install/execplan.txt", "workload/runtime/install/execplan_op_tail_round.txt"}
    ]
    frozen_equal = all(name in source_files and files[name] == source_files[name] for name in frozen_members)
    sca_equal = all(normalized(files[name], [(NAME.encode(), SOURCE_NAME.encode())]) == source_files[name] for name in ("workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"))

    native = EXTRACT / "tb_probe/native_return_observer.svh"
    addon = EXTRACT / "tb_probe/qlinearadd_node0007_tailround_bufready_v53.svh"
    parser = EXTRACT / "package_tools/qlinearadd_node0007_tailround_bufready_canonical_v53.py"
    commands = {
        "bash_syntax": run([str(BASH), "-n", str(EXTRACT / "PREPARE_AND_RUN.sh")]),
        "runtime_preflight": run([str(PYTHON), str(EXTRACT / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"), "preflight", "--package-root", str(EXTRACT)]),
        "canonical_selftest": run([str(PYTHON), str(parser), "--selftest"]),
        "iverilog_preprocess": run([str(IVERILOG), "-g2012", "-E", "-I", str(EXTRACT / "tb_probe"), "-o", str(LOCAL / "native_preprocessed_v54.sv"), str(native)]),
        "hdl_positive": run([str(PYTHON), str(HDL_VALIDATOR), "--native", str(native), "--addon", str(addon), "--parser", str(parser), "--workspace-root", str(ROOT), "--output", str(LOCAL / "hdl_gate_positive.json")]),
    }
    source_harness = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-package/runtime_layout_harness.json"
    harness = json.loads(source_harness.read_text(encoding="utf-8").replace(SOURCE_NAME, NAME))
    harness["derived_from_zip_sha256"] = sha(ZIP)
    harness["runner_member_sha256"] = sha_bytes(files["PREPARE_AND_RUN.sh"])
    harness["claim_boundary"] = (
        "Install-only V2 normal/compile-fail/HUP/INT/TERM and fixed-result control "
        "flow is normalized byte-equal to v52; exact v54 identity/feature/parser/HDL "
        "changed surfaces are independently validated; no DUT/server action."
    )
    harness_path = LOCAL / "runtime_layout_harness.json"
    shared_path = LOCAL / "shared_runtime_layout_validation.json"
    write_json(harness_path, harness)
    commands["shared_runtime_layout"] = run([
        str(PYTHON), str(ROOT / "tools/validate_server_package_runtime_layout.py"),
        "--zip", str(ZIP), "--harness-report", str(harness_path),
        "--helper-reference", str(ROOT / "tools/server_package_runtime_layout.py"),
        "--require-runner-error-visibility", "--output", str(shared_path),
    ])

    negatives: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="q54neg-") as temp_name:
        temp = Path(temp_name)
        for case, mutate in {
            "delete_declaration": lambda text: text.replace("    bit q53_enabled;\n", "", 1),
            "misspell_actual_consumer": lambda text: text.replace(".mse_wreq_pingpong_sel[0]", ".mse_wreq_pingpong_se1[0]", 1),
            "delete_qualified_update": lambda text: text.replace("kind=BUF5_READ_ACCEPT", "kind=BUF5_READ_DROPPED", 1),
        }.items():
            mutated = temp / f"{case}.svh"
            mutated.write_text(mutate(addon.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
            negatives[case] = run([str(PYTHON), str(HDL_VALIDATOR), "--native", str(native), "--addon", str(mutated), "--parser", str(parser), "--workspace-root", str(ROOT)])
    negative_pass = all(row["exit_code"] != 0 for row in negatives.values())

    trace = predicate_trace(parser)
    write_json(LOCAL / "predicate_trace_validation.json", trace)
    current = {key: {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path), "mutable_provenance_only": key == "plan_mutable"} for key, path in RULES.items()}
    expected_rules = {key: {"path": current[key]["path"], "sha256": current[key]["sha256"], "current_match": True} for key in ("generation_index", "server", "common_config", "ndp_fields", "qlinearadd", "exact_uint8_tail")}
    prior = json.loads(PRIOR_PASS.read_text(encoding="utf-8"))
    shared = json.loads(shared_path.read_text(encoding="utf-8")) if shared_path.is_file() else {}
    checks = {
        "exact_zip_safe": safe,
        "manifest_exact_set_per_file": manifest_exact,
        "clean_extract_byte_exact": extract_exact,
        "build_zip_identity": build["zip"]["sha256"] == sha(ZIP) and build["zip"]["bytes"] == ZIP.stat().st_size,
        "sidecar_exact": SIDECAR.read_text(encoding="ascii").strip() == f"{sha(ZIP)}  {ZIP.name}",
        "source_v52_identity": source_root == SOURCE_NAME and source_structure["crc_valid"] and sha(SOURCE) == "7ed0e6e84d32900b015f70091b7b8bbefae074a63f019d75026f8b25bf9f52d0",
        "identity_claim_boundary": manifest.get("package_id") == NAME and manifest.get("install_name") == NAME and manifest.get("claim") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "current_rule_receipts": manifest.get("rule_receipts") == expected_rules,
        "prior_first_fresh_pass": sha(PRIOR_PASS) == PRIOR_PASS_SHA and prior.get("pass") is True and prior.get("upload_authorized") is True and manifest.get("first_fresh_extra_audit", {}).get("first_fresh_after_change") is False,
        "runner_control_flow_normalized_equal_v52": runner_control_equal,
        "frozen_payload_bitstream_execplan_golden": frozen_equal,
        "frozen_sca_semantics_identity_normalized": sca_equal,
        "commands_all_zero": all(row["exit_code"] == 0 for row in commands.values()),
        "shared_runtime_layout": shared.get("pass") is True and shared.get("errors") == [] and shared.get("zip", {}).get("sha256") == sha(ZIP),
        "three_hdl_negatives_fail_closed": negative_pass,
        "predicate_trace": trace["pass"] is True,
        "diagnostic_feature_four_way": all(token in files["PREPARE_AND_RUN.sh"].decode() for token in ("+QADD_TAILROUND_BUFREADY", "QADD_TAILROUND_BUFREADY_V53", "qlinearadd_node0007_tailround_bufready_canonical_v53.py", "qlinearadd_node0007_tailround_bufready_v53.svh")),
        "host_stimulus_not_producer": manifest.get("boundary_input_contract", {}).get("host_precomputed_internal_tensor") is True and manifest.get("boundary_input_contract", {}).get("producer_evidence_claimed") is False,
        "one_stage_28D_contract": manifest.get("split_segment_contract", {}).get("stage_names") == ["op_tail_round"] and manifest.get("split_segment_contract", {}).get("expected_output_count") == 28,
        "no_server_action": build.get("server_action") is False,
    }
    errors.extend(key for key, value in checks.items() if value is not True)
    hdl_positive = json.loads((LOCAL / "hdl_gate_positive.json").read_text(encoding="utf-8")) if (LOCAL / "hdl_gate_positive.json").is_file() else {}
    report = {
        "schema": "qlinearadd-node0007-tailround-bufready-v54-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP), "member_count": len(files)},
        "sidecar": {"path": SIDECAR.relative_to(ROOT).as_posix(), "bytes": SIDECAR.stat().st_size, "sha256": sha(SIDECAR)},
        "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": sha(SOURCE)},
        "commands": commands,
        "shared_runtime_layout": {"harness_path": harness_path.relative_to(ROOT).as_posix(), "harness_sha256": sha(harness_path), "validation_path": shared_path.relative_to(ROOT).as_posix(), "validation_sha256": sha(shared_path) if shared_path.is_file() else None, "pass": shared.get("pass")},
        "negative_controls": {"all_fail_closed": negative_pass, "exit_codes": {key: row["exit_code"] for key, row in negatives.items()}, "details": negatives},
        "package_local_hdl_gate": hdl_positive,
        "predicate_trace": {"path": (LOCAL / "predicate_trace_validation.json").relative_to(ROOT).as_posix(), "sha256": sha(LOCAL / "predicate_trace_validation.json"), "pass": trace["pass"]},
        "current_rule_receipts_after_generation": current,
        "release_gate_matrix": {
            "package_bootstrap_path_runtime_D": "PASS_EXACT_ZIP_INPUT_OPEN_AND_V52_CONTROL_RECEIPT_REUSE",
            "runner_compile_finalizer": "PASS_NORMALIZED_BYTE_EQUAL_CONTROL_FLOW_PLUS_BASH_PREFLIGHT",
            "package_local_hdl": "PASS_CHANGED_OBSERVER_EXACT_CONSUMER_CLOSURE_AND_THREE_NEGATIVES",
            "materialized_config": "NOT_APPLICABLE_BYTE_EQUAL_RECEIPT_REUSE",
            "observer_canonical": "PASS_CHANGED_PREDICATE_TRACE_STAGE_OWNER_AND_BOUNDARY_CASES",
            "return_result_conjunction": "PASS_LOCAL_CONTRACT_DYNAMIC_PENDING",
            "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
            "functional_RTL": "RECORD_ONLY_UNMODIFIED",
            "first_fresh_extra_audit": "PASS_PRIOR_EPOCH_RECEIPT_REUSE_FIRST_FRESH_AFTER_CHANGE_FALSE",
        },
        "package_release": "PACKAGE_READY_NOT_RUN" if not errors else "UPLOAD_HOLD",
        "claim_boundary": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY; isolated op_tail_round Buffer5 selected-read readiness; host FP32 stimulus is not producer evidence; no full-chain/E3/E4/E5 claim.",
        "numeric_workload_config_golden_repeated": False,
        "functional_rtl_changed": False,
        "server_action": False,
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
    }
    write_json(REPORT, report)
    write_json(LOCAL / "family_validation.json", {
        "schema": "qlinearadd-node0007-tailround-bufready-v54-family-validation-v1",
        "valid": not errors, "errors": errors, "checks": checks,
        "zip": report["zip"], "negative_controls": report["negative_controls"],
        "release_gate_matrix": report["release_gate_matrix"],
        "numeric_workload_config_golden_repeated": False, "functional_rtl_changed": False,
        "server_action": False, "claim_boundary": report["claim_boundary"],
    })
    print(json.dumps({"pass": not errors, "errors": errors, "report": str(REPORT), "zip_sha256": sha(ZIP)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
