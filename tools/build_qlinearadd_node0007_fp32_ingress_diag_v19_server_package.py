from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, preflight, write_json


INSTALL_NAME = "r5_qadd_n7_fp32_ingress_diag_v19"
SOURCE_NAME = "r5_qadd_n7_dbuf_colpair_v18"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "570abd6f483f47f144ae9cb9320418e4acd423e2cf011e1f44a0f5b2537edd1a"
EVIDENCE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fp32-ingress-diag-v19"
)
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
TAIL_RULE = ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"
COMMON_RULE = ROOT / ".agents/rules/算子配置规则.md"
NDP_RULE = ROOT / ".agents/rules/NDP硬件字段语义.md"
INDEX_SHA256 = "f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8"
SERVER_RULE_SHA256 = "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
QADD_RULE_SHA256 = "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"
TAIL_RULE_SHA256 = "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
COMMON_RULE_SHA256 = "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
NDP_RULE_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
OBSERVER_SOURCE = ROOT / "tools/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
PARSER_SOURCE = ROOT / "tools/qlinearadd_node0007_fp32_ingress_canonical_v19.py"
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_REL = (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-ingress-diag-v19/"
    "final_zip_self_audit.json"
)


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rule_ids(path: Path) -> list[str]:
    return re.findall(r"规则 ID：`([^`]+)`", path.read_text(encoding="utf-8"))


def assert_receipts() -> None:
    expected = {
        SOURCE_ZIP: SOURCE_ZIP_SHA256,
        INDEX: INDEX_SHA256,
        SERVER_RULE: SERVER_RULE_SHA256,
        QADD_RULE: QADD_RULE_SHA256,
        TAIL_RULE: TAIL_RULE_SHA256,
        COMMON_RULE: COMMON_RULE_SHA256,
        NDP_RULE: NDP_RULE_SHA256,
    }
    drift = {
        str(path): {"expected": wanted, "actual": sha256(path)}
        for path, wanted in expected.items()
        if not path.is_file() or sha256(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")
    for path in (SOURCE_DIR, OBSERVER_SOURCE, PARSER_SOURCE):
        if not path.exists():
            raise BuildError(f"required source absent: {path}")


def replace_namespace(package: Path) -> None:
    binary_suffixes = {".bin", ".png", ".npy", ".npz"}
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in binary_suffixes:
            continue
        payload = path.read_bytes()
        if SOURCE_NAME.encode() in payload:
            path.write_bytes(payload.replace(SOURCE_NAME.encode(), INSTALL_NAME.encode()))


def patch_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(f"{label} preimage count differs: {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def patch_runner(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    patch_once(
        runner,
        'canonical_decision="$evidence_root/CANONICAL_PROGRESS_DECISION.json"\n',
        'canonical_decision="$evidence_root/CANONICAL_PROGRESS_DECISION.json"\n'
        'feature_receipt="$evidence_root/fp32_ingress_feature_receipt.txt"\n',
        "runner feature receipt variable",
    )
    patch_once(
        runner,
        """  if [ -s "$observer_log" ] &&      grep -q 'Native NDP return observer' "$observer_log"; then
    printf 'observer_enabled_and_returned=true\\n' >"$evidence_root/observer_binding.txt"
  else
    printf 'observer_enabled_and_returned=false\\n' >"$evidence_root/observer_binding.txt"
  fi
""",
        """  if [ -s "$observer_log" ] && grep -q 'Native NDP return observer' "$observer_log"; then
    printf 'observer_enabled_and_returned=true\\n' >"$evidence_root/observer_binding.txt"
  else
    printf 'observer_enabled_and_returned=false\\n' >"$evidence_root/observer_binding.txt"
  fi
  feature_argv=false
  feature_time0=false
  feature_snapshot=false
  grep -q '+QADD_FP32_INGRESS_OBSERVER' "$evidence_root/actual_simulator_argv.txt" && feature_argv=true
  grep -q 'QADD_FP32_INGRESS_OBSERVER_V19_TIME0' "$run_root/sim_results/sim.log" && feature_time0=true
  grep -q '# QADD_FP32_INGRESS_OBSERVER_V19 ' "$observer_log" && feature_snapshot=true
  printf 'feature=QADD_FP32_INGRESS_OBSERVER\\nargv_enabled=%s\\ntime0_marker=%s\\nreturned_snapshot_marker=%s\\n' \
    "$feature_argv" "$feature_time0" "$feature_snapshot" >"$feature_receipt"
""",
        "runner feature finalizer",
    )
    patch_once(
        runner,
        "  +RETURN_OBS_DEEP\n",
        "  +RETURN_OBS_DEEP\n  +QADD_FP32_INGRESS_OBSERVER\n",
        "runner feature plusarg",
    )


def build_directory(destination: Path) -> Path:
    assert_receipts()
    package = destination / INSTALL_NAME
    if package.exists():
        raise BuildError(f"destination exists: {package}")
    shutil.copytree(SOURCE_DIR, package)
    replace_namespace(package)

    observer_tail = package / "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
    shutil.copy2(OBSERVER_SOURCE, observer_tail)
    native = package / "tb_probe/native_return_observer.svh"
    with native.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            '\n`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"\n'
        )
    parser = package / "package_tools/qlinearadd_progress_canonical_decision.py"
    shutil.copy2(PARSER_SOURCE, parser)
    patch_runner(package)

    contract_path = package / "diagnostics/progress_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract.update(
        {
            "schema": "qlinearadd-node0007-fp32-ingress-localization-v19",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "target_stage": "op_fp32_add",
            "unique_error_interval": (
                "op_fp32_add stream0+stream1/MSE0+MSE1 qualified read ingress "
                "through Buffer0+Buffer2 paired readiness to first qualified "
                "GA input accept/output"
            ),
            "feature_plusarg": "+QADD_FP32_INGRESS_OBSERVER",
            "feature_time0_marker": "QADD_FP32_INGRESS_OBSERVER_V19_TIME0",
            "feature_return_marker": "# QADD_FP32_INGRESS_OBSERVER_V19",
            "counter_source_clock": "clk_sg",
            "snapshot_clock": "clk_db",
            "qualified_internal_counters": [
                "mse0_mse1_request_accept",
                "mse0_mse1_rdata_accept",
                "mse0_mse1_to_buffer_accept",
                "buffer0_buffer2_write_accept",
                "buffer0_buffer2_arm_read_accept",
                "buffer0_buffer2_array_delivery",
                "ga_operand0_operand1_capture",
                "ga_pair_match",
                "ga_consumer_accept",
                "ga_first_output",
            ],
            "level_snapshots_not_counted_as_progress": [
                "buffer0_buffer2_any_valid",
                "buffer0_buffer2_arm_ready",
                "unpaired_mse_valid_or_ready",
            ],
            "minimum_monotonic_windows": 3,
            "return_allowlist_entry_count": 11,
        }
    )
    write_json(contract_path, contract)

    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 FP32 ingress diagnostic v19\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "This package is DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. It preserves the "
        "v18 workload, JSON, mapping, bitstreams, execplan, SCA, qparams, tail "
        "and golden byte-for-byte while adding a low-rate read-only observer "
        "for MSE0/MSE1, Buffer0/2 and the GA dual-input acceptance chain. "
        "It does not extend the timeout and modifies no functional RTL.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    feature_entry = {
        "max_bytes": 1048576,
        "missing_meaning": "FP32 ingress runtime feature receipt unavailable",
        "required": True,
        "source_path": "fp32_ingress_feature_receipt.txt",
        "source_root": "evidence",
        "target_path": "evidence/fp32_ingress_feature_receipt.txt",
    }
    manifest["return_allowlist"].append(feature_entry)
    manifest.update(
        {
            "schema": "qlinearadd-node0007-fp32-ingress-diagnostic-server-package-v19",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "localizes the frozen v18 op_fp32_add ingress interval only; "
                "no functional, E4/E5, production, performance or RTL claim"
            ),
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_ZIP_SHA256,
                "status": "QUARANTINED_DYNAMIC_FP32_ADD_HANG",
                "numeric_workload_config_golden_unchanged": True,
            },
            "successor_reason": {
                "last_proven_good": "OP_RELOCATION_PAD_COMP_FINISH",
                "first_divergence": (
                    "OP_FP32_ADD_AFTER_FINITE_READ_ACTIVITY_BEFORE_GA_INPUT_ACCEPT"
                ),
                "unique_root_cause_proven": False,
                "diagnostic_gap": (
                    "v18 omitted MSE1, Buffer2 and qualified GA dual-ingress "
                    "events, so config versus RTL backpressure cannot be separated"
                ),
            },
            "fp32_ingress_observer": {
                "feature_plusarg": "+QADD_FP32_INGRESS_OBSERVER",
                "source_path": observer_tail.relative_to(package).as_posix(),
                "source_sha256": sha256(observer_tail),
                "native_observer_sha256": sha256(native),
                "counter_source_clock": "clk_sg",
                "snapshot_clock": "clk_db",
                "rate_limited": True,
                "level_counts_as_progress": False,
                "functional_rtl_modified": False,
                "workload_or_configuration_modified": False,
                "timeout_modified": False,
                "feature_receipt": "evidence/fp32_ingress_feature_receipt.txt",
            },
        }
    )
    manifest["canonical_decision_contract"] = {
        "rule_id": "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
        "schema": "qlinearadd-node0007-fp32-ingress-canonical-v19",
        "version": 1,
        "parser_path": parser.relative_to(package).as_posix(),
        "parser_sha256": sha256(parser),
        "output_path": "evidence/CANONICAL_PROGRESS_DECISION.json",
        "unique_complete_record_required": True,
        "ordered_final_stage_scope": True,
        "individual_mse_levels_or_unpaired_inputs_excluded_from_progress": True,
        "level_snapshots_excluded_from_progress": True,
    }
    manifest["default_progress_diagnostics"].update(
        {
            "observer_time0_receipt": "evidence/fp32_ingress_feature_receipt.txt",
            "qualified_request_data_accept_completion": "runs/return_observer.log",
            "changes_timeout": False,
        }
    )
    manifest["progress_localization"].update(
        {
            "schema": "qlinearadd-node0007-fp32-ingress-localization-v19",
            "return_allowlist_entry_count": 11,
            "unique_error_interval": (
                "op_fp32_add MSE0+MSE1 read ingress -> Buffer0+2 paired "
                "delivery -> first qualified GA consumer accept/output"
            ),
        }
    )
    manifest["provenance"].update(
        {
            "generator": (
                "tools/build_qlinearadd_node0007_"
                "fp32_ingress_diag_v19_server_package.py"
            ),
            "generation_index": {
                "path": INDEX.relative_to(ROOT).as_posix(),
                "sha256": INDEX_SHA256,
            },
            "server_package_rule": {
                "path": SERVER_RULE.relative_to(ROOT).as_posix(),
                "sha256": SERVER_RULE_SHA256,
            },
            "qlinearadd_rule": {
                "path": QADD_RULE.relative_to(ROOT).as_posix(),
                "sha256": QADD_RULE_SHA256,
            },
            "exact_uint8_tail_rule": {
                "path": TAIL_RULE.relative_to(ROOT).as_posix(),
                "sha256": TAIL_RULE_SHA256,
            },
            "v18_return_analysis_report": {
                "path": (
                    "artifacts/operator_config_validation/"
                    "r5-qlinearadd-node0007-d-buffer-column-pair-v18-return-analysis/"
                    "report.json"
                ),
                "sha256": "a32a6023b930de3c25c1072d6692e11b36b012cbebed721b8f6fa890be66fdf8",
            },
        }
    )
    manifest["final_zip_rule_self_audit"] = {
        "rule_id": "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "rule_receipts": {
            "generation_index": {
                "path": INDEX.relative_to(ROOT).as_posix(),
                "sha256": INDEX_SHA256,
                "current_match": True,
            },
            "server_package_rule": {
                "path": SERVER_RULE.relative_to(ROOT).as_posix(),
                "sha256": SERVER_RULE_SHA256,
                "current_match": True,
            },
            "qlinearadd_rule": {
                "path": QADD_RULE.relative_to(ROOT).as_posix(),
                "sha256": QADD_RULE_SHA256,
                "current_match": True,
            },
            "exact_uint8_tail_rule": {
                "path": TAIL_RULE.relative_to(ROOT).as_posix(),
                "sha256": TAIL_RULE_SHA256,
                "current_match": True,
            },
        },
        "applicable_server_rule_ids": rule_ids(SERVER_RULE),
        "applicable_qlinearadd_rule_ids": rule_ids(QADD_RULE),
        "applicable_exact_tail_rule_ids": rule_ids(TAIL_RULE),
        "direct_final_zip_and_sidecar_validation_required": True,
        "all_required_negative_controls_required": True,
        "pass_field": "FINAL_ZIP_RULE_SELF_AUDIT_PASS",
        "errors_must_equal": 0,
        "validator": (
            "tools/validate_qlinearadd_node0007_"
            "fp32_ingress_diag_v19_server_package.py"
        ),
        "report": REPORT_REL,
    }
    manifest["server_tb_or_observer_entries"] = 3
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    return package


def build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
    package = build_directory(destination)
    output = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, output)
    return package, output, file_records(package, exclude_manifest=False)


def main() -> int:
    package = PACKAGE_ROOT / INSTALL_NAME
    output = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(output) + ".sha256")
    for path in (package, output, sidecar, VALIDATION_PATH):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, output, records = build_once(PACKAGE_ROOT)
        with tempfile.TemporaryDirectory(prefix="qadd-v19-repeat-") as raw:
            _, repeat_zip, repeat_records = build_once(Path(raw))
            repeated = {
                "package_tree_equal": records == repeat_records,
                "zip_equal": sha256(output) == sha256(repeat_zip),
                "repeat_zip_sha256": sha256(repeat_zip),
            }
        if not all((repeated["package_tree_equal"], repeated["zip_equal"])):
            raise BuildError("deterministic rebuild differs")
        digest_value = sha256(output)
        sidecar.write_text(
            f"{digest_value}  {output.name}\n",
            encoding="ascii",
            newline="\n",
        )
        receipt = {
            "schema": "qlinearadd-node0007-fp32-ingress-diag-build-v19",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest_value,
            "zip_bytes": output.stat().st_size,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": sha256(sidecar),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "file_count": len(records),
            "repeated_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "configuration_changed": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(VALIDATION_PATH, receipt)
    except Exception as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
