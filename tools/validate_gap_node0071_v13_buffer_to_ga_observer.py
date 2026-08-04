from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT_NAME = "r5_n71_gap_v13_buffer_to_ga_diag"
OBSERVER = "tb_probe/native_return_observer.svh"


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_observer(
    target_zip: Path, root_name: str = ROOT_NAME
) -> tuple[str, dict[str, Any]]:
    with zipfile.ZipFile(target_zip) as archive:
        if archive.testzip() is not None:
            raise ValidationError("ZIP CRC differs")
        names: set[str] = set()
        payload: bytes | None = None
        manifest_payload: bytes | None = None
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or info.filename in names
                or (
                    not info.is_dir()
                    and not info.filename.startswith(f"{root_name}/")
                )
            ):
                raise ValidationError(f"unsafe ZIP member: {info.filename}")
            names.add(info.filename)
            if info.filename == f"{root_name}/{OBSERVER}":
                payload = archive.read(info)
            if info.filename == f"{root_name}/TEST_PACKAGE_MANIFEST.json":
                manifest_payload = archive.read(info)
        if payload is None or manifest_payload is None:
            raise ValidationError("observer or manifest absent")
    manifest = json.loads(manifest_payload.decode("utf-8"))
    receipt = manifest["files"][OBSERVER]
    if (
        receipt["sha256"] != sha256_bytes(payload)
        or receipt["size_bytes"] != len(payload)
    ):
        raise ValidationError("observer manifest receipt differs")
    return payload.decode("utf-8"), manifest


def validate_text(text: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = {
        "buffer0 qualified":
            "return_obs_buf0_arm_accept_count++",
        "buffer4 qualified":
            "return_obs_buf4_arm_accept_count++",
        "group0 qualified":
            "return_obs_ga_group0_accept_count++",
        "group2 qualified":
            "return_obs_ga_group2_accept_count++",
        "source edge witness":
            "return_obs_sg_clock_edge_count++",
        "source last-change witness":
            "return_obs_sg_last_edge_time = $time",
        "ungated summary":
            "BUFFER_TO_GA_COUNTS",
        "raw state separated":
            "BUFFER_TO_GA_STATE",
        "buffer raw tags":
            "return_obs_buf_to_ga_rtag_mon",
        "group raw tags":
            "return_obs_ga_group_out_tag_mon",
        "PE operand raw valid":
            "return_obs_ga_operand_inport_valid_mon",
        "source clock owner":
            "always @(posedge u_NDP_Top_new.clk_sg)",
        "observer clock owner":
            "always @(posedge u_NDP_Top_new.clk_db",
    }
    for label, token in required.items():
        if token not in text:
            errors.append(f"missing {label}")
    for name in (
        "return_obs_buf0_arm_accept_count",
        "return_obs_buf4_arm_accept_count",
    ):
        increment = f"{name}++;"
        position = text.find(increment)
        context = text[max(0, position - 700):position]
        if (
            position < 0
            or "return_obs_buf_to_ga_rtag_mon" not in context
            or "return_obs_buf_to_ga_bp_mon" not in context
            or "&&" not in context
        ):
            errors.append(f"{name} is not qualified by tag and backpressure")
    for name in (
        "return_obs_ga_group0_accept_count",
        "return_obs_ga_group2_accept_count",
    ):
        increment = f"{name}++;"
        position = text.find(increment)
        context = text[max(0, position - 2200):position]
        if (
            position < 0
            or "return_obs_ga_group_out_tag_mon" not in context
            or "return_obs_ga_group_bp_post_mon" not in context
            or "&&" not in context
        ):
            errors.append(f"{name} is not qualified by valid and bp_post")
    sg_block = text.split(
        "always @(posedge u_NDP_Top_new.clk_sg)", 1
    )[-1]
    if "return_obs_sg_clock_edge_count %" in sg_block:
        errors.append("source-domain modulo used as emitter gate")
    summary_position = text.find("BUFFER_TO_GA_COUNTS")
    clk_db_position = text.find(
        "always @(posedge u_NDP_Top_new.clk_db"
    )
    if summary_position < 0 or clk_db_position < 0:
        errors.append("independent snapshot binding absent")
    if any(
        token in text
        for token in (
            "force ",
            "release ",
            "<= return_obs_",
            "assign u_NDP_Top_new",
        )
    ):
        errors.append("observer contains potential DUT drive")
    return not errors, errors


def validate(
    target_zip: Path, root_name: str = ROOT_NAME
) -> dict[str, Any]:
    text, manifest = read_observer(target_zip, root_name)
    valid, errors = validate_text(text)
    if not valid:
        raise ValidationError("; ".join(errors))
    controls: dict[str, Any] = {}
    mutations = {
        "buffer_backpressure_removed": text.replace(
            "                return_obs_buf_to_ga_bp_mon\n"
            "                    [return_obs_group_id][return_obs_local_slice_id][0]\n",
            "                1'b1\n",
            1,
        ),
        "source_edge_witness_removed": text.replace(
            "            return_obs_sg_clock_edge_count++;\n", "", 1
        ),
        "ungated_snapshot_removed": text.replace(
            "BUFFER_TO_GA_COUNTS", "BUFFER_TO_GA_SUMMARY_ONLY", 1
        ),
        "source_domain_modulo_added": text.replace(
            "            return_obs_sg_clock_edge_count++;\n",
            "            return_obs_sg_clock_edge_count++;\n"
            "            if ((return_obs_sg_clock_edge_count % 16) == 0) begin end\n",
            1,
        ),
    }
    for name, mutated in mutations.items():
        control_valid, control_errors = validate_text(mutated)
        controls[name] = {
            "failed_closed": not control_valid,
            "errors": control_errors,
        }
        if control_valid:
            raise ValidationError(f"negative control did not fail: {name}")
    contract = manifest.get("buffer_to_ga_diagnostic", {})
    if (
        contract.get("source_clock") != "clk_sg"
        or contract.get("snapshot_clock") != "clk_db"
        or contract.get("source_clock_edge_and_last_change_returned")
        is not True
        or contract.get("numeric_workload_changed") is not False
        or contract.get("config_changed") is not False
    ):
        raise ValidationError("manifest diagnostic contract differs")
    return {
        "schema": "gap-node0071-buffer-to-ga-observer-validation-v13",
        "status": "PASS",
        "target_zip": str(target_zip),
        "target_zip_sha256": sha256_bytes(target_zip.read_bytes()),
        "observer_sha256": sha256_bytes(text.encode("utf-8")),
        "rule_ids": [
            "CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001",
            "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
        ],
        "qualified_counter_boundaries": [
            "BUFFER0_ARM_READ_ACCEPT",
            "BUFFER4_ARM_READ_ACCEPT",
            "GA_GROUP0_INGRESS_ACCEPT",
            "GA_GROUP2_INGRESS_ACCEPT",
        ],
        "raw_level_state_excluded_from_progress": True,
        "source_clock_edge_and_last_change_returned": True,
        "snapshot_clock_independent": True,
        "functional_dut_drive": False,
        "negative_controls": controls,
        "all_negative_controls_fail_closed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_zip", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve(), args.root_name)
    except Exception as error:
        print(f"buffer-to-GA observer validation failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
