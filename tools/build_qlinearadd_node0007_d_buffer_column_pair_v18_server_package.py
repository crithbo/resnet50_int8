from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_qlinearadd_node0007_d_buffer_supply_v15_server_package as base
from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, preflight, write_json


INSTALL_NAME = "r5_qadd_n7_dbuf_colpair_v18"
SOURCE_NAME = "r5_qadd_n7_dbuf_rule_v16"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5"
EVIDENCE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-d-buffer-column-pair-v18"
)
PIPELINE = EVIDENCE_ROOT / "execplan/pipeline_output"
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
TAIL_RULE = ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"
COMMON_RULE = ROOT / ".agents/rules/算子配置规则.md"
NDP_RULE = ROOT / ".agents/rules/NDP硬件字段语义.md"
INDEX_SHA256 = "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
SERVER_RULE_SHA256 = "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
QADD_RULE_SHA256 = "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"
TAIL_RULE_SHA256 = "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
COMMON_RULE_SHA256 = "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
NDP_RULE_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
RULE_ID = "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001"
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_REL = (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-column-pair-v18/"
    "final_zip_self_audit.json"
)


class BuildError(ValueError):
    pass


def _assert_receipts() -> None:
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
        str(path): {"expected": wanted, "actual": base.sha256(path)}
        for path, wanted in expected.items()
        if not path.is_file() or base.sha256(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")
    targeted = json.loads(
        (EVIDENCE_ROOT / "targeted_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    if not targeted.get("local_candidate_valid"):
        raise BuildError("local v18 targeted validation is not clean")
    if targeted.get("package_release") != "LOCAL_VALIDATED_READY_FOR_FRESH_PACKAGING":
        raise BuildError("local v18 is not ready for fresh packaging")


def _configure_base() -> None:
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_NAME = SOURCE_NAME
    base.SOURCE_DIR = SOURCE_DIR
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    base.EVIDENCE_ROOT = EVIDENCE_ROOT
    base.PIPELINE = PIPELINE
    base.INDEX_SHA256 = INDEX_SHA256
    base.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    base.QADD_RULE_SHA256 = QADD_RULE_SHA256
    base.COMMON_RULE_SHA256 = COMMON_RULE_SHA256
    base.NDP_RULE_SHA256 = NDP_RULE_SHA256
    base.VALIDATION_PATH = VALIDATION_PATH
    base.REPORT_REL = REPORT_REL


def _fix_stage_scoped_canonical_parser(package: Path) -> dict[str, Any]:
    parser = package / "package_tools/qlinearadd_progress_canonical_decision.py"
    text = parser.read_text(encoding="utf-8")
    old = """        if (
            after[\"active_cycles\"] < before[\"active_cycles\"]
            or any(value < 0 for value in delta.values())
        ):
            monotonic = False
        advanced = any(value > 0 for value in delta.values())
"""
    new = """        if after[\"active_cycles\"] < before[\"active_cycles\"]:
            window_records.append(
                {
                    \"index\": index,
                    \"start_line\": before[\"line_number\"],
                    \"end_line\": after[\"line_number\"],
                    \"start_active_cycles\": before[\"active_cycles\"],
                    \"end_active_cycles\": after[\"active_cycles\"],
                    \"qualified_delta\": delta,
                    \"qualified_advanced\": False,
                    \"stage_transition_reset\": True,
                }
            )
            consecutive_advancing = 0
            flat_start = after[\"active_cycles\"]
            continue
        if any(value < 0 for value in delta.values()):
            monotonic = False
        advanced = any(value > 0 for value in delta.values())
"""
    if text.count(old) != 1:
        raise BuildError("canonical stage-reset patch preimage differs")
    parser.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    return {
        "path": parser.relative_to(package).as_posix(),
        "old_sha256": "37d0ba34f2ef9805611fd0a1bee3871aa534b997bc12c5896fe6d0e5903430e8",
        "new_sha256": base.sha256(parser),
        "scope": "package-local diagnostic parser only",
        "functional_configuration_changed": False,
    }


def build_directory(destination: Path) -> Path:
    _assert_receipts()
    _configure_base()
    package = base._copy_source(destination)
    base._replace_namespace_tree(package)
    base._replace_fresh_native_chain(package)
    shutil.copy2(
        base.RUNTIME_SOURCE,
        package / "package_tools/qlinearadd_node0007_server_runtime.py",
    )
    preload_records = base._refresh_preload_contract(package)
    parser_patch = _fix_stage_scoped_canonical_parser(package)
    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 D-buffer column-pair fix v18\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "The v16 return completed both dequant stages and then stalled in "
        "op_relocation_pad. v18 changes only the three write stages so one "
        "physical 32-byte Buffer5 row is consumed as two accepted 16-byte "
        "ROW/COL windows: [0,16) and [16,32). It also makes the package-local "
        "canonical progress parser treat an active-cycle decrease as a stage "
        "transition instead of a functional counter regression. Numeric/W3, "
        "qparams, tail, workload, golden, DRAM occurrence/addressing and "
        "functional RTL are unchanged.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-d-buffer-column-pair-server-package-v18",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "package_class": "FUNCTIONAL_CONFIG_FIX_WITH_DEFAULT_PROGRESS_DIAGNOSTICS",
            "functional_fix": True,
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "claim_boundary": (
                "node0007 configuration-only D-buffer ROW/COL pair correction; "
                "no E4/E5, production, performance or functional-RTL claim"
            ),
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_ZIP_SHA256,
                "status": "QUARANTINED_DYNAMIC_STAGE3_WRITE_BACKEND_HANG",
                "numeric_workload_and_golden_unchanged": True,
            },
            "functional_configuration_fix": {
                "rule_id": RULE_ID,
                "first_dynamic_divergence": (
                    "op_relocation_pad after A/B dequant completion; downstream "
                    "qualified write-back counters flat for >=3 stall windows"
                ),
                "root_cause_scope": (
                    "v15/v16 ROW-only supply formula dynamically refuted; "
                    "corrected by paired ROW/COL byte-window conservation"
                ),
                "changed_semantic_layer": "D_BUFFER_ROW_COL_PAIR_SUPPLY",
                "changed_stages": [
                    "op_relocation_pad",
                    "op_tail_mul",
                    "op_tail_round",
                ],
                "changed_leaves_per_stage": {
                    "buffer_loop_configs.GROUP2.ROW_LC.end": [2, 1],
                    "buffer_loop_configs.GROUP2.COL_LC.end": [4, 32],
                    "buffer_loop_configs.GROUP2.COL_LC.stride": [2, 16],
                    "buffer_config.buffer5.buf_end_row_addr": [1, 0],
                },
                "transaction_bytes": 32,
                "buffer_row_bytes": 32,
                "mse_read_bytes": 16,
                "accepted_row_col_pairs": [[0, 0], [0, 16]],
                "byte_windows": [[0, 16], [16, 32]],
                "window_union_exact": [0, 32],
                "buffer5_actual_max_row": 0,
                "functional_rtl_modified": False,
                "w3_qparams_tail_workload_golden_changed": False,
                "dram_loop_address_occurrence_changed": False,
            },
            "config_preload_contract": {
                "owner": "QLinearAdd package SCA materializer",
                "expected_sca_preload_count": 91,
                "source_preload_count": 85,
                "added_config_preload_count": 6,
                "entries": preload_records,
            },
            "stage_scoped_canonical_parser_fix": parser_patch,
        }
    )
    manifest["canonical_decision_contract"]["parser_sha256"] = parser_patch[
        "new_sha256"
    ]
    manifest["provenance"].update(
        {
            "generator": (
                "tools/build_qlinearadd_node0007_"
                "d_buffer_column_pair_v18_server_package.py"
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
            "fresh_native_chain": {
                "root": EVIDENCE_ROOT.relative_to(ROOT).as_posix(),
                "execplan_validation_sha256": base.sha256(
                    PIPELINE.parent / "execplan_validation_report.json"
                ),
                "double_run_sha256": base.sha256(
                    PIPELINE.parent / "double_run_comparison.json"
                ),
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
        "applicable_server_rule_ids": base._rule_ids(SERVER_RULE),
        "applicable_qlinearadd_rule_ids": base._rule_ids(QADD_RULE),
        "applicable_exact_tail_rule_ids": base._rule_ids(TAIL_RULE),
        "direct_final_zip_and_sidecar_validation_required": True,
        "all_required_negative_controls_required": True,
        "pass_field": "FINAL_ZIP_RULE_SELF_AUDIT_PASS",
        "errors_must_equal": 0,
        "validator": (
            "tools/validate_qlinearadd_node0007_"
            "d_buffer_column_pair_v18_server_package.py"
        ),
        "report": REPORT_REL,
    }
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    return package


def _build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
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
        package, built, records = _build_once(PACKAGE_ROOT)
        with tempfile.TemporaryDirectory(prefix="qadd-v18-repeat-") as raw:
            _, repeat_zip, repeat_records = _build_once(Path(raw))
            repeated = {
                "package_tree_equal": records == repeat_records,
                "zip_equal": base.sha256(built) == base.sha256(repeat_zip),
                "repeat_zip_sha256": base.sha256(repeat_zip),
            }
        if not repeated["package_tree_equal"] or not repeated["zip_equal"]:
            raise BuildError("deterministic rebuild differs")
        digest = base.sha256(output)
        sidecar.write_text(
            f"{digest}  {output.name}\n", encoding="ascii", newline="\n"
        )
        receipt = {
            "schema": "qlinearadd-node0007-d-buffer-column-pair-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "zip_bytes": output.stat().st_size,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": base.sha256(sidecar),
            "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "file_count": len(records),
            "repeated_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "config_numeric_analysis_repeated": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(VALIDATION_PATH, receipt)
    except Exception as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
