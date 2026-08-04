from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import file_records


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v24_prep_count_cause_diag"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "ad71f6d6ab75f0992505d9d4656c058aa4011776bfc9b7c1c14bd78ec9b428ab"
)
INSTALL_NAME = "r5_n71_gap_v25_hdl_scope_rulefix"
TEST_ID = "r5-gap-node0071-v25-hdl-scope-rulefix"
OBSERVER = "tb_probe/native_return_observer.svh"
OBSERVER_SHA256 = (
    "a4499c2532a3b0709a3cde34c0f6d29260195a469047fe29d6fd223f3df4fb5f"
)
RULE_ID = "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
ALLOWED_CHANGED = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "TEST_PACKAGE_MANIFEST.json",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}
IDENTITY_CHANGED = ALLOWED_CHANGED - {"README.md", "TEST_PACKAGE_MANIFEST.json"}

STATE_LEAVES = [
    "return_obs_pc_enabled",
    "return_obs_pc_limit",
    "return_obs_pc_emit_count",
    "return_obs_pc_started",
    "return_obs_pc_prev_rst_n",
    "return_obs_pc_prev_slice_rst",
    "return_obs_pc_prev_wr",
    "return_obs_pc_prev_rd",
    "return_obs_pc_prev_count",
    "return_obs_pc_prev_tsf",
    "return_obs_pc_prev_spatial",
    "return_obs_pc_wr_count",
    "return_obs_pc_rd_count",
    "return_obs_pc_count_change",
    "return_obs_pc_slice_rst_edge",
    "return_obs_pc_rst_n_edge",
    "return_obs_pc_no_effect_count",
    "return_obs_pc_first_no_effect",
    "return_obs_pc_last_no_effect",
    "return_obs_pc_first_local_reset",
    "return_obs_pc_last_local_reset",
    "return_obs_pc_no_effect_seen",
    "return_obs_pc_local_reset_seen",
]


class BuildError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("source v24 ZIP SHA256 differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("source v24 ZIP CRC differs")
        infos = archive.infolist()
        names = [item.filename for item in infos if not item.is_dir()]
        if len(names) != len(set(names)):
            raise BuildError("source v24 ZIP duplicate member")
        for info in infos:
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != SOURCE_NAME
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            if info.is_dir():
                continue
            relative = Path(*pure.parts[1:])
            target = package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            unix_mode = (info.external_attr >> 16) & 0o777
            if unix_mode:
                target.chmod(unix_mode)
    return package


def state_leaf_contract(identifier: str) -> dict[str, str]:
    if identifier in {"return_obs_pc_enabled", "return_obs_pc_limit"}:
        initialization = "initial plusarg/default initialization"
        update = "time-zero runtime feature binding"
        consumer = "feature gate or bounded emission predicate"
    elif identifier.startswith("return_obs_pc_prev_") or identifier == (
        "return_obs_pc_started"
    ):
        initialization = "return_obs_pc_reset task"
        update = "qualified clk_sg sample-window state update"
        consumer = "next qualified sample comparison"
    elif identifier == "return_obs_pc_emit_count":
        initialization = "return_obs_pc_reset task"
        update = "qualified pc_event increment under limit"
        consumer = "event budget and record sequence"
    else:
        initialization = "return_obs_pc_reset task"
        update = "qualified clk_sg prepared-count cause event update"
        consumer = "PREP_COUNT_CAUSE record or summary consumer"
    return {
        "identifier": identifier,
        "type": "package-local observer state",
        "owner": "prepared_count_cause feature on clk_sg",
        "initialization_or_reset": initialization,
        "qualified_update": update,
        "consumer": consumer,
    }


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "gap-node0071-hdl-scope-rulefix-package-v25",
            "test_id": TEST_ID,
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "status": "PACKAGE_READY_NOT_RUN",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "functional_fix": False,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    receipts = manifest["final_zip_rule_self_audit_contract"]["read_receipt"]
    for receipt in receipts:
        receipt["sha256"] = sha256(ROOT / receipt["path"])
        receipt["current_match"] = True
    audit = manifest["final_zip_rule_self_audit_contract"]
    audit["all_current_match"] = True
    audit["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    audit["final_zip_rule_self_audit_pass"] = (
        "PENDING_EXTERNAL_RELEASE_REPORT"
    )
    applicable = audit["applicable_rule_ids"]
    if RULE_ID not in applicable:
        applicable.append(RULE_ID)
    rules = manifest["rule_receipts"]
    rules["server_rule_sha256"] = sha256(
        ROOT / ".agents/rules/服务器测试包生成规则.md"
    )
    rules["current_match"] = True
    rules["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    observer_path = package / OBSERVER
    if sha256(observer_path) != OBSERVER_SHA256:
        raise BuildError("frozen observer bytes drifted")
    manifest["package_local_hdl_syntax_scope_contract"] = {
        "rule_id": RULE_ID,
        "members": [
            {
                "relative_path": OBSERVER,
                "bytes": observer_path.stat().st_size,
                "sha256": OBSERVER_SHA256,
                "kind": "package-local read-only observer include",
            }
        ],
        "include_order": [
            "package-local +incdir tb_probe",
            "tb_NDP_Top_new_phy.sv protected include native_return_observer.svh",
        ],
        "compile_macro_profile": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE; "
            "VCS production compile, Icarus focused local gate"
        ),
        "features": [
            {
                "name": "prepared_count_cause",
                "clock_owner": "clk_sg",
                "state_leaves": [
                    state_leaf_contract(identifier)
                    for identifier in STATE_LEAVES
                ],
                "external_dut_leaves": [
                    "rst_n",
                    "slice_rst",
                    "rd_data_chl_prepared_data_wr_hs",
                    "rd_data_chl_prepared_data_rd_hs",
                    "rd_data_chl_data_vld",
                    "prepared_data_lt_req",
                    "rd_data_chl_prepared_data_bp_pre",
                    "rd_data_chl_ob_bp_pre",
                    "rd_data_chl_prepared_data_cnt",
                    "rd_chl_queue_rd_tsf_size",
                    "mse_buf_spatial_size",
                ],
            }
        ],
        "required_negative_controls": [
            "delete_declaration",
            "misspell_consumer_use",
            "delete_qualified_update",
        ],
        "release_evidence": (
            "external final-ZIP exact-member validator report required"
        ),
        "safe_stub_is_not_hdl_evidence": True,
    }
    manifest["post_generation_rule_drift_refresh"] = {
        "classification": "FRESH_SUCCESSOR_REQUIRED",
        "source_package_status": (
            "QUARANTINED_MISSING_MANDATORY_HDL_STATE_MANIFEST_CONTRACT"
        ),
        "source_package_sha256": SOURCE_SHA256,
        "current_index_sha256": sha256(
            ROOT / ".agents/rules/生成前必读索引.md"
        ),
        "current_server_rule_sha256": sha256(
            ROOT / ".agents/rules/服务器测试包生成规则.md"
        ),
        "observer_bytes_changed": False,
        "numeric_or_config_bytes_changed": False,
    }
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_hdl_scope_rulefix_v25_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity and current-rule HDL/state ownership "
                "manifest contract; observer bytes unchanged"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = safe_extract_source(destination)
    source_records = file_records(package, exclude_manifest=False)
    old = SOURCE_NAME.encode("ascii")
    new = INSTALL_NAME.encode("ascii")
    for relative in IDENTITY_CHANGED:
        path = package / relative
        payload = path.read_bytes()
        if old not in payload:
            raise BuildError(f"identity marker absent: {relative}")
        path.write_bytes(payload.replace(old, new))
    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n## v25 current-rule HDL scope receipt\n\n"
        + "This fresh identity keeps the exact v24 observer and frozen "
        + "numeric/config/workload/golden bytes. It adds the mandatory "
        + "package-local HDL member, compile profile and prepared-count "
        + "state ownership contract required by "
        + f"`{RULE_ID}`.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package)
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("successor file set differs")
    changed = {
        path
        for path in source_records
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    observer_equal = source_records[OBSERVER] == final_records[OBSERVER]
    frozen = sorted(set(source_records) - ALLOWED_CHANGED)
    return package, {
        "source_v24_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_file_count": len(frozen),
        "frozen_tree_equal": all(
            source_records[path] == final_records[path] for path in frozen
        ),
        "observer_byte_equal": observer_equal,
        "observer_sha256": final_records[OBSERVER]["sha256"],
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "config_semantics_rebuilt": False,
        "functional_rtl_modified": False,
    }


def build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
    package, proof = build_directory(destination)
    zip_path = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    return package, zip_path, proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, zip_path, proof = build_once(output_root)
        digest = sha256(zip_path)
        tree = file_records(package, exclude_manifest=False)
        with tempfile.TemporaryDirectory(
            prefix="gap-node0071-v25-repeat-"
        ) as temp_name:
            repeated_package, repeated_zip, _ = build_once(Path(temp_name))
            repeat_equal = (
                sha256(repeated_zip) == digest
                and file_records(
                    repeated_package, exclude_manifest=False
                )
                == tree
            )
        if not repeat_equal:
            raise BuildError("deterministic double build differs")
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        result = {
            "schema": "gap-node0071-hdl-scope-rulefix-v25-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "test_id": TEST_ID,
            "package": str(package),
            "zip": str(zip_path),
            "zip_bytes": zip_path.stat().st_size,
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "sidecar_bytes": sidecar.stat().st_size,
            "sidecar_sha256": sha256(sidecar),
            "deterministic_double_build": repeat_equal,
            **proof,
            "server_action": False,
        }
        write_json(validation, result)
    except Exception as error:
        print(f"GAP v25 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
