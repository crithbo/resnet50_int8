from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT_NAME = "r5_n71_gap_v18_bp_pre_factor_diag"
TEST_ID = "r5-gap-node0071-v18-bp-pre-factor-observability"
OBSERVER = "tb_probe/native_return_observer.svh"
RUNNER = "PREPARE_AND_RUN.sh"
RULE_ID = "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001"
SCHEMAS = {
    "BP_PRE_FACTOR_EDGE_V1",
    "BP_PRE_FACTOR_COUNTS_V1",
    "BP_PRE_FACTOR_STATE_V1",
    "BP_PRE_FACTOR_WITNESS_V1",
}
XMR_TOKENS = {
    "buf_ag_bp_pre": "u_WR_Buffer_AG.buf_ag_bp_pre",
    "buf_ag_ob_full": "u_WR_Buffer_AG.buf_ag_ob_full",
    "rd_data_chl_data_ready":
        "u_RD_Data_Channel.rd_data_chl_data_ready",
    "rd_data_chl_data_vld":
        "u_RD_Data_Channel.rd_data_chl_data_vld",
    "rd_data_chl_prepared_data_cnt":
        "u_RD_Data_Channel.rd_data_chl_prepared_data_cnt",
    "rd_data_chl_ob_full":
        "u_RD_Data_Channel.rd_data_chl_ob_full",
    "nse2mse_req_barrier": ".nse2mse_req_barrier",
    "buf_ag_idx_queue_rd_en":
        "u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en",
    "buf_ag_ob_wr_en": "u_WR_Buffer_AG.buf_ag_ob_wr_en",
    "buf_ag_idx_queue_occupancy":
        "u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_counter",
}
OWNER_NAMES = set(XMR_TOKENS)
RETURN_TARGETS = {
    "evidence/actual_compile_argv.txt",
    "evidence/actual_simulator_argv.txt",
    "evidence/observer_binding.txt",
    "runs/return_observer.log",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_zip(path: Path, root_name: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if info.is_dir():
                continue
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or not pure.parts
                or pure.parts[0] != root_name
            ):
                raise ValueError(f"unsafe/wrong-root ZIP member: {info.filename}")
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in files:
                raise ValueError(f"duplicate ZIP member: {relative}")
            files[relative] = archive.read(info)
    return files


def _manifest(files: dict[str, bytes]) -> dict[str, Any]:
    return json.loads(files["TEST_PACKAGE_MANIFEST.json"])


def _refresh_record(
    files: dict[str, bytes],
    relative: str,
) -> dict[str, bytes]:
    updated = dict(files)
    manifest = _manifest(updated)
    record = manifest["files"][relative]
    record["sha256"] = sha256_bytes(updated[relative])
    record["size_bytes"] = len(updated[relative])
    updated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return updated


def validate_payload(
    files: dict[str, bytes],
    root_name: str,
) -> dict[str, Any]:
    errors: list[str] = []
    manifest = _manifest(files)
    observer = files[OBSERVER].decode("utf-8")
    runner = files[RUNNER].decode("utf-8")
    if manifest.get("install_name") != root_name:
        errors.append("identity differs")
    if manifest.get("test_id") != TEST_ID:
        errors.append("test_id differs")
    if manifest.get("claim") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("package misclassified")
    if manifest.get("candidate_release") is not False:
        errors.append("candidate_release must be false")
    if manifest.get("functional_fix") is not False:
        errors.append("functional_fix must be false")
    if manifest.get("functional_rtl_modified") is not False:
        errors.append("functional_rtl_modified must be false")
    contract = manifest.get("bp_pre_factor_observability_contract", {})
    if contract.get("rule_id") != RULE_ID:
        errors.append("factor rule ID differs")
    if contract.get("runtime_enable_plusarg") != "+RETURN_OBS_BP_FACTORS":
        errors.append("factor runtime enable contract differs")
    if contract.get("runtime_limit_plusarg") != (
        "+RETURN_OBS_BP_FACTOR_LIMIT=512"
    ):
        errors.append("factor runtime limit contract differs")
    if contract.get("effective_limit") != 512:
        errors.append("factor effective limit differs")
    if contract.get("source_clock") != "clk_sg":
        errors.append("factor source clock differs")
    if contract.get("snapshot_clock") != "clk_db":
        errors.append("factor snapshot clock differs")
    if contract.get("record_schemas") != [
        "BP_PRE_FACTOR_EDGE_V1",
        "BP_PRE_FACTOR_COUNTS_V1",
        "BP_PRE_FACTOR_STATE_V1",
        "BP_PRE_FACTOR_WITNESS_V1",
    ]:
        errors.append("factor record schemas differ")
    if contract.get("stable_levels_excluded_from_monotonic_progress") is not True:
        errors.append("stable level leaked into monotonic progress contract")
    if contract.get("factor_edge_counts_excluded_from_canonical_progress") is not True:
        errors.append("factor edge count leaked into canonical progress contract")
    if contract.get("output_zero_leaf_attribution_forbidden") is not True:
        errors.append("zero-output leaf attribution guard absent")
    conjuncts = contract.get("conjuncts", [])
    declared_names = {item.get("name") for item in conjuncts}
    if declared_names != OWNER_NAMES:
        errors.append("conjunct owner/name exact-set differs")
    for item in conjuncts:
        if not item.get("owner") or not item.get("sampling"):
            errors.append(f"conjunct owner/sampling absent: {item.get('name')}")
    marker_tokens = set(
        contract.get("time0_marker", {}).get("required_tokens", [])
    )
    if marker_tokens != {"bp_factor=1", "bp_factor_limit=512"}:
        errors.append("factor time0 marker contract differs")
    binding = contract.get("feature_specific_binding_receipt", {})
    success_lines = set(binding.get("success_exact_lines", []))
    if success_lines != {
        "bp_pre_factor_observability_enabled=true",
        "bp_pre_factor_limit=512",
        "bp_pre_factor_records_returned=true",
    }:
        errors.append("factor binding receipt differs")
    allowlist_targets = {
        item.get("target_path")
        for item in manifest.get("return_allowlist", [])
    }
    if not RETURN_TARGETS.issubset(allowlist_targets):
        errors.append("factor return allowlist target absent")
    if set(contract.get("return_allowlist_targets", [])) != RETURN_TARGETS:
        errors.append("factor contract return targets differ")
    applicable = set(
        manifest.get("final_zip_rule_self_audit_contract", {}).get(
            "applicable_rule_ids", []
        )
    )
    if RULE_ID not in applicable:
        errors.append("factor rule absent from applicable rule IDs")
    for schema in SCHEMAS:
        if observer.count(schema) != 1:
            errors.append(f"observer schema count differs: {schema}")
    for name, token in XMR_TOKENS.items():
        if token not in observer:
            errors.append(f"observer XMR absent: {name}")
    required_observer_tokens = {
        "return_obs_bp_factor_enabled",
        "return_obs_bp_factor_emit_count < return_obs_bp_factor_limit",
        "return_obs_bp_first_block",
        "return_obs_bp_last_block",
        "return_obs_bp_window_start_edge",
        "return_obs_bp_window_last_edge",
        "$test$plusargs(\"RETURN_OBS_BP_FACTORS\")",
        "\"RETURN_OBS_BP_FACTOR_LIMIT=%d\"",
        "bp_factor=%0d bp_factor_limit=%0d",
    }
    for token in required_observer_tokens:
        if token not in observer:
            errors.append(f"observer factor mechanism absent: {token}")
    if runner.count("+RETURN_OBS_BP_FACTORS") < 2:
        errors.append("runner factor enable absent")
    if runner.count("+RETURN_OBS_BP_FACTOR_LIMIT=512") < 2:
        errors.append("runner factor limit not bound in receipt and argv")
    for token in (
        "bp_pre_factor_observability_enabled=true",
        "bp_pre_factor_limit=512",
        "bp_pre_factor_records_returned=true",
        "grep -Fq 'bp_factor=1'",
        "grep -Fq 'BP_PRE_FACTOR_COUNTS_V1'",
        "grep -Fq 'BP_PRE_FACTOR_STATE_V1'",
        "grep -Fq 'BP_PRE_FACTOR_WITNESS_V1'",
    ):
        if token not in runner:
            errors.append(f"runner factor binding absent: {token}")
    canonical = files[
        "package_tools/gap_node0071_canonical_decision.py"
    ].decode("utf-8")
    if "BP_PRE_FACTOR_" in canonical:
        errors.append("factor state entered canonical progress parser")
    for relative in (OBSERVER, RUNNER):
        record = manifest.get("files", {}).get(relative, {})
        if record.get("sha256") != sha256_bytes(files[relative]):
            errors.append(f"manifest SHA differs: {relative}")
        if record.get("size_bytes") != len(files[relative]):
            errors.append(f"manifest size differs: {relative}")
    xmr = manifest.get("package_local_observer", {}).get(
        "xmr_static_gate", {}
    )
    if xmr.get("status") != "pass":
        errors.append("manifest XMR static gate failed")
    if "return_obs_bp_group" not in xmr.get("declared_genvars", []):
        errors.append("factor group genvar absent from XMR receipt")
    if "return_obs_bp_slice" not in xmr.get("declared_genvars", []):
        errors.append("factor slice genvar absent from XMR receipt")
    if xmr.get("runtime_indexed_generated_instance_reference_count") != 0:
        errors.append("runtime-indexed generated XMR present")
    return {
        "valid": not errors,
        "errors": errors,
        "observer_sha256": sha256_bytes(files[OBSERVER]),
        "runner_sha256": sha256_bytes(files[RUNNER]),
        "record_schemas": sorted(SCHEMAS),
        "conjunct_names": sorted(OWNER_NAMES),
        "xmr_tokens_checked": XMR_TOKENS,
        "return_targets_checked": sorted(RETURN_TARGETS),
    }


def negative_controls(
    files: dict[str, bytes],
    root_name: str,
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []

    def run(
        name: str,
        mutated: dict[str, bytes],
        expected_fragment: str,
    ) -> None:
        result = validate_payload(mutated, root_name)
        controls.append(
            {
                "name": name,
                "failed_closed": not result["valid"],
                "expected_error_observed": any(
                    expected_fragment in error
                    for error in result["errors"]
                ),
                "errors": result["errors"],
            }
        )

    for name, token in XMR_TOKENS.items():
        mutated = dict(files)
        mutated[OBSERVER] = files[OBSERVER].replace(
            token.encode("utf-8"),
            f"XMR_REMOVED_{name}".encode("utf-8"),
        )
        mutated = _refresh_record(mutated, OBSERVER)
        run(
            f"missing_conjunct_xmr_{name}",
            mutated,
            f"observer XMR absent: {name}",
        )

    for name in sorted(OWNER_NAMES):
        mutated = dict(files)
        manifest = _manifest(mutated)
        manifest["bp_pre_factor_observability_contract"]["conjuncts"] = [
            item
            for item in manifest[
                "bp_pre_factor_observability_contract"
            ]["conjuncts"]
            if item["name"] != name
        ]
        mutated["TEST_PACKAGE_MANIFEST.json"] = (
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        run(
            f"missing_conjunct_owner_{name}",
            mutated,
            "conjunct owner/name exact-set differs",
        )

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"  +RETURN_OBS_BP_FACTORS\n", b"", 1
    )
    mutated = _refresh_record(mutated, RUNNER)
    run("missing_feature_runtime_enable", mutated, "runner factor enable absent")

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"+RETURN_OBS_BP_FACTOR_LIMIT=512",
        b"+RETURN_OBS_BP_FACTOR_LIMIT=511",
    )
    mutated = _refresh_record(mutated, RUNNER)
    run(
        "tampered_feature_runtime_limit",
        mutated,
        "runner factor limit not bound",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"bp_factor=%0d bp_factor_limit=%0d",
        b"bp_feature_marker_removed",
        1,
    )
    mutated = _refresh_record(mutated, OBSERVER)
    run(
        "missing_feature_time0_marker",
        mutated,
        "observer factor mechanism absent",
    )

    mutated = dict(files)
    manifest = _manifest(mutated)
    manifest["return_allowlist"] = [
        item
        for item in manifest["return_allowlist"]
        if item.get("target_path") != "runs/return_observer.log"
    ]
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    run(
        "missing_feature_return_target",
        mutated,
        "factor return allowlist target absent",
    )

    mutated = dict(files)
    manifest = _manifest(mutated)
    manifest["bp_pre_factor_observability_contract"][
        "feature_specific_binding_receipt"
    ]["success_exact_lines"].remove(
        "bp_pre_factor_records_returned=true"
    )
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    run(
        "missing_feature_binding_receipt",
        mutated,
        "factor binding receipt differs",
    )

    mutated = dict(files)
    manifest = _manifest(mutated)
    manifest["bp_pre_factor_observability_contract"][
        "stable_levels_excluded_from_monotonic_progress"
    ] = False
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    run(
        "stable_level_promoted_to_progress",
        mutated,
        "stable level leaked into monotonic progress contract",
    )

    mutated = dict(files)
    manifest = _manifest(mutated)
    manifest["final_zip_rule_self_audit_contract"][
        "applicable_rule_ids"
    ].remove(RULE_ID)
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    run("missing_current_factor_rule", mutated, "factor rule absent")
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        files = read_zip(args.zip_path, args.root_name)
        result = validate_payload(files, args.root_name)
        controls = negative_controls(files, args.root_name)
        result["negative_controls"] = controls
        result["all_negative_controls_fail_closed"] = all(
            item["failed_closed"] and item["expected_error_observed"]
            for item in controls
        )
        result["valid"] = (
            result["valid"] and result["all_negative_controls_fail_closed"]
        )
        result["status"] = "PASS" if result["valid"] else "FAIL"
    except Exception as error:
        result = {
            "valid": False,
            "errors": [str(error)],
            "negative_controls": [],
            "all_negative_controls_fail_closed": False,
            "status": "FAIL",
        }
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
