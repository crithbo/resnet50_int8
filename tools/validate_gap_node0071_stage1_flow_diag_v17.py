from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT_NAME = "r5_n71_gap_v17_stage1_flow_diag"
OBSERVER = "tb_probe/native_return_observer.svh"
REQUIRED_SCHEMAS = {
    "STAGE1_FLOW_COUNTS_V1",
    "STAGE1_FLOW_STATE_V1",
}
REQUIRED_XMR = {
    "u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en",
    "u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en",
    "u_WR_Buffer_AG.buf_ag_ob_cnt",
    "u_Buffer.valid_buf",
    "u_Array_Request_Manager.array_counter_0",
    "u_Array_Request_Manager.array_counter_1",
    "u_GA_PE_Inbuffer.ga_pe_inbuffer_tag[0]",
    "u_GA_PE_Inbuffer.ga_pe_inbuffer_tag[2]",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_zip(path: Path, root_name: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failure")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.is_dir():
                continue
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                raise ValueError("unsafe ZIP path")
            if not pure.parts or pure.parts[0] != root_name:
                raise ValueError("wrong ZIP root")
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in files:
                raise ValueError("duplicate member")
            files[relative] = archive.read(info)
    return files


def validate_payload(
    files: dict[str, bytes],
    root_name: str,
) -> dict[str, Any]:
    errors: list[str] = []
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    observer = files[OBSERVER].decode("utf-8")
    if manifest.get("install_name") != root_name:
        errors.append("identity differs")
    if manifest.get("claim") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("package misclassified")
    if manifest.get("functional_fix") is not False:
        errors.append("functional_fix must be false")
    contract = manifest.get("stage1_flow_diagnostic_contract", {})
    if contract.get("record_schemas") != [
        "STAGE1_FLOW_COUNTS_V1",
        "STAGE1_FLOW_STATE_V1",
    ]:
        errors.append("stage1 flow record schema contract differs")
    if contract.get("excluded_from_monotonic_progress") is not True:
        errors.append("stage1 flow raw state not excluded from progress")
    feature = manifest.get("diagnostic_feature_runtime_enable_contract", {})
    if feature.get("runtime_enable_plusarg") != "+RETURN_OBS_ACCUM_STATE":
        errors.append("shared runtime feature gate differs")
    for schema in REQUIRED_SCHEMAS:
        if observer.count(schema) != 1:
            errors.append(f"observer schema count differs: {schema}")
    for token in REQUIRED_XMR:
        if token not in observer:
            errors.append(f"observer XMR absent: {token}")
    if "return_obs_flow_q_wr_count[flow]++" not in observer:
        errors.append("qualified queue counter absent")
    if "return_obs_flow_arm_accept_count[flow]++" not in observer:
        errors.append("qualified ARM counter absent")
    if "return_obs_flow_arm_clear_count[flow]++" not in observer:
        errors.append("qualified clear counter absent")
    if (
        "return_obs_flow_q_wr_count" in observer[
            observer.find("CANONICAL_DIAG_DECISION_V1"):
        ]
        and observer.find("CANONICAL_DIAG_DECISION_V1") >= 0
    ):
        errors.append("flow state leaked into canonical decision tail")
    source_record = manifest.get("files", {}).get(OBSERVER, {})
    if source_record.get("sha256") != sha256_bytes(files[OBSERVER]):
        errors.append("observer manifest SHA differs")
    if source_record.get("size_bytes") != len(files[OBSERVER]):
        errors.append("observer manifest size differs")
    xmr = manifest.get("package_local_observer", {}).get(
        "xmr_static_gate", {}
    )
    if xmr.get("status") != "pass":
        errors.append("manifest XMR static gate failed")
    if "return_obs_flow_group" not in xmr.get("declared_genvars", []):
        errors.append("flow genvars missing from manifest XMR receipt")
    if xmr.get("runtime_indexed_generated_instance_reference_count") != 0:
        errors.append("runtime-indexed generated XMR present")
    return {
        "valid": not errors,
        "errors": errors,
        "observer_sha256": sha256_bytes(files[OBSERVER]),
        "record_schemas": sorted(REQUIRED_SCHEMAS),
        "xmr_tokens_checked": sorted(REQUIRED_XMR),
    }


def _negative_controls(
    files: dict[str, bytes],
    root_name: str,
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []

    def run(name: str, mutated: dict[str, bytes]) -> None:
        result = validate_payload(mutated, root_name)
        controls.append(
            {
                "name": name,
                "failed_closed": not result["valid"],
                "errors": result["errors"],
            }
        )

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    mutated = dict(files)
    manifest["stage1_flow_diagnostic_contract"]["record_schemas"].remove(
        "STAGE1_FLOW_STATE_V1"
    )
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True).encode("utf-8")
    )
    run("missing_state_schema_contract", mutated)

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"u_Buffer.valid_buf", b"u_Buffer.valid_missing", 1
    )
    run("missing_buffer_valid_xmr", mutated)

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    mutated = dict(files)
    manifest["stage1_flow_diagnostic_contract"][
        "excluded_from_monotonic_progress"
    ] = False
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True).encode("utf-8")
    )
    run("flow_state_in_progress_contract", mutated)

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    mutated = dict(files)
    manifest["claim"] = "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True).encode("utf-8")
    )
    run("mislabeled_functional_fix", mutated)
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        files = _read_zip(args.zip_path, args.root_name)
        result = validate_payload(files, args.root_name)
        controls = _negative_controls(files, args.root_name)
        result["negative_controls"] = controls
        result["all_negative_controls_fail_closed"] = all(
            item["failed_closed"] for item in controls
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
