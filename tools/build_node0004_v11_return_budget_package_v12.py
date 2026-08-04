from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v12_hangloc_returngate"
SOURCE_INSTALL_NAME = "r5_n4_hw_v11_hangloc_finalaudit"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v11_hangloc_finalaudit.zip"
)
SOURCE_ZIP_SHA256 = (
    "27b9c6b36076fd5e4c3a5ab7db283b7953254bcf1b2ba9005bb0a4fd6e134ea7"
)
BOUND_RETURN_SHA256 = (
    "37e84246a8908c38ec5056c3fc965d90198a2809b049f3c7303215e508d07dcf"
)
PLAN_SHA256 = (
    "8625b61df7094b20e71b07cb658e7fe80599df847d1c7b22adf5af613028b851"
)
SERVER_RULE_SHA256 = (
    "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def _configure_base() -> None:
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_INSTALL_NAME = SOURCE_INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    base.RETURN_ZIP_SHA256 = BOUND_RETURN_SHA256
    base.PLAN_SHA256 = PLAN_SHA256
    base.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    base.OBSERVER_TAIL = (
        ROOT / "tools/node0004_hang_localization_observer_tail_v10.svh"
    )
    base.RUNTIME_SOURCE = (
        ROOT / "tools/node0004_hang_localization_runtime_v12.py"
    )
    base.SOURCE_PREFIX = f"install/cfg_pkg/{SOURCE_INSTALL_NAME}/"
    base.CURRENT_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}/"


def _readme() -> str:
    return f"""# node0004 v12 return-gated hang-localization package

Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

This package reuses the frozen v11 c0 workload without rebuilding node0004
numeric inputs. It preserves qualified-only progress and the complete,
versioned canonical decision record. The executable changes are confined to
the return collector: exact-set, aggregate/per-file budgets and mandatory
progress evidence after compile success. An external signal before the
observer decision produces an explicit fail-closed canonical record.

The package does not modify functional RTL or the server TB and cannot
establish E4/E5.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    _configure_base()
    package, _ = base.build_directory(destination)
    tools_dir = package / "package_tools"
    shutil.copy2(
        ROOT / "tools/node0004_hang_localization_runtime_v7.py",
        tools_dir / "node0004_hang_localization_runtime_v7.py",
    )
    (package / "README.md").write_text(
        _readme(), encoding="utf-8", newline="\n"
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "resnet50-node0004-hang-localization-package-v12"
    manifest["install_name"] = INSTALL_NAME
    manifest["evidence_level"] = (
        "E2_LOCAL_PLUS_V11_RETURN_GATE_REPAIR"
    )
    manifest["frozen_source_package"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_ZIP_SHA256,
    }
    manifest.pop("bound_v6_return_sha256", None)
    manifest.pop("bound_v7_return_sha256", None)
    manifest["bound_v7_return_sha256"] = BOUND_RETURN_SHA256
    manifest["active_receipts"] = {
        "plan_mutable_provenance_sha256": PLAN_SHA256,
        "server_package_rule_sha256": SERVER_RULE_SHA256,
        "generation_read_receipt": [
            {
                "path": ".agents/rules/生成前必读索引.md",
                "sha256": (
                    "12583308ec9a16dbb8ea15571a5280291"
                    "fed7e152167d2e4e8e00509a9a6370f"
                ),
                "reason": "server package routing",
            },
            {
                "path": ".agents/rules/服务器测试包生成规则.md",
                "sha256": SERVER_RULE_SHA256,
                "reason": "common server package gates",
            },
            {
                "path": ".agents/rules/INT8_SA点积专项规则.md",
                "sha256": (
                    "54a1e12541aaeb6f62dadb19c47a6154e"
                    "b0462b758a35a9a5bc4a0043cb37dce"
                ),
                "reason": "Conv INT8 SA accumulate release gate",
            },
            {
                "path": "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
                "sha256": (
                    "4318f3a28de399fb522740315f11bdddf"
                    "346e71969cf1e45686899a568b042d7"
                ),
                "reason": "active server entry",
            },
        ],
        "rules": [
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "CDA-SERVER-ONE-COMMAND-001",
            "CDA-SCA-D-TB-READBACK-LENGTH-001",
            "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
            "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
            "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
            "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
            "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
            "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            "CDA-SERVER-RETURN-RECEIPT-001",
            "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
            "CDA-SA-NODE0004-ASSUMED-FIXED-HARDWARE-001",
        ],
    }
    manifest["package_side_repair"] = {
        "classification": "SERVER_TEST_RETURN_COLLECTION_GATE_FAILURE",
        "first_defect": (
            "v11 collector enforced an 8 MiB per-file limit but did not "
            "enforce the final return exact-set or aggregate compressed and "
            "uncompressed budgets"
        ),
        "second_defect": (
            "v11 treated progress logs as optional after compile success and "
            "had no complete canonical fallback when an external signal "
            "arrived before the observer decision"
        ),
        "repair": (
            "validate final return ZIP/sidecar exact set, hashes, CRC, "
            "16 MiB compressed, 32 MiB uncompressed and 8 MiB per-file "
            "limits; require argv/sim/observer/host logs after compile "
            "success; emit fail-closed external-signal canonical evidence"
        ),
        "functional_semantics_changed": False,
    }
    manifest["unresolved_boundary"] = (
        "v7 evidence bounds the stall after qualified read-data acceptance "
        "and before any Buffer5 write witness; v12 changes only return "
        "collection and fail-closed diagnostic recording"
    )
    manifest["progress_contract"].update(
        {
            "default_progress_diagnostics_enabled": True,
            "default_progress_diagnostics_exemption": None,
            "normal_minimum_progress_event": (
                "a qualified external request, read-data, or write-data "
                "handshake on streams 0/1/3/4"
            ),
            "buffer_level_samples_count_as_progress": False,
            "buffer_level_semantics": (
                "raw state only; rising-edge witness is reported separately"
            ),
            "decision_parser_requires_reason_and_boundary": True,
            "canonical_prefix": "CANONICAL_DIAG_DECISION_V1",
            "canonical_record_count": 1,
            "summary_prefix": "DIAG_SUMMARY",
            "canonical_fail_closed_status": (
                "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
            ),
            "post_generation_final_zip_rule_self_audit_required": True,
            "external_signal_canonical_fallback": True,
        }
    )
    manifest["return_budget"] = {
        "compressed_zip_max_bytes": 16777216,
        "uncompressed_max_bytes": 33554432,
        "per_text_file_max_bytes": 8388608,
        "final_exact_set_required": True,
        "crc_required": True,
        "sidecar_required": True,
        "forbidden_suffixes": [
            ".vcd",
            ".fsdb",
            ".daidir",
            ".sdb",
            ".so",
            ".a",
            ".pyc",
            ".zip",
        ],
    }
    manifest["return_diagnostics_required_after_compile_success"] = [
        "runs/c0/simulator_argv.txt",
        "runs/c0/sim.log",
        "runs/c0/return_observer.log",
        "runs/c0/host_progress.log",
    ]
    manifest["decision_table"][2] = [
        "READ_DATA_TO_BUFFER4_READ_WITNESS",
        "read data exists, no Buffer4 read-enable rising-edge witness",
    ]
    manifest["decision_table"][3] = [
        "BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS",
        "Buffer4 read witness exists, no Buffer5 write-enable rising edge",
    ]
    manifest["decision_table"][4] = [
        "BUFFER5_WRITE_WITNESS_TO_BUFFER5_READ_WITNESS",
        "Buffer5 write witness exists, no Buffer5 read-enable rising edge",
    ]
    manifest["decision_table"][5] = [
        "BUFFER5_READ_WITNESS_TO_D_WRITE_REQUEST",
        "Buffer5 read witness exists, no qualified D request",
    ]
    manifest["numeric_analysis_repeated"] = False
    manifest["node0004_workload_rebuilt"] = False
    manifest["frozen_c0_inputs_reused_read_only"] = True
    manifest["superseded_diagnostic_package"] = {
        "name": "r5_n4_hw_v11_hangloc_finalaudit.zip",
        "sha256": SOURCE_ZIP_SHA256,
        "status": "QUARANTINED_RETURN_COLLECTION_GATE_DEFECT",
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    proof = base.preflight(package)
    observer_sha = manifest["observer_binding_four_way"]["source"]["sha256"]
    observer = base.observer_precompile_receipt(package, observer_sha)
    if not observer["valid"]:
        raise base.BuildError(f"observer XMR gate failed: {observer['errors']}")
    return package, {"preflight": proof, "observer": observer}


def _repeat(package: Path, zip_path: Path) -> dict[str, Any]:
    base.deterministic_zip(package, zip_path)
    records = base.package_records(package)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v12-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        if records != base.package_records(repeat_package):
            raise base.BuildError("repeated package trees differ")
        if digest != base.sha256(repeat_zip):
            raise base.BuildError("repeated deterministic ZIPs differ")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    package_path = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    output.mkdir(parents=True, exist_ok=True)
    package, proof = build_directory(output)
    repeated = _repeat(package, zip_path)
    digest = base.sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "node0004-hang-localization-package-validation-v12",
        "status": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN",
        "package": str(package),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "bound_return_sha256": BOUND_RETURN_SHA256,
        "package_file_count": proof["preflight"]["package_file_count"],
        "observer_sha256": proof["preflight"]["observer_sha256"],
        "observer_static_gate": proof["observer"]["xmr_static_gate"],
        "observer_runtime_enabled": True,
        "observer_compile_enable_macro_bound": True,
        "observer_return_allowlisted": True,
        "qualified_progress_only": True,
        "reason_bearing_decision_parser": True,
        "canonical_decision_unique": True,
        "canonical_decision_complete": True,
        "canonical_decision_fail_closed": True,
        "bootstrap_sys_dont_write_bytecode_before_local_import": True,
        "return_budget_gate_bound": True,
        "return_exact_set_gate_bound": True,
        "progress_diagnostics_required_after_compile_success": True,
        "external_signal_canonical_fallback": True,
        "final_zip_rule_self_audit_pending": True,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "repeated_build": repeated,
    }
    base.write_json(validation, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
