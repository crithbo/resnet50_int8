from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_v12_minimal_runtime_package as v12


SOURCE_NAME = "r5_n71_gap_v12_minruntime"
INSTALL_NAME = "r5_n71_gap_v13_buffer_to_ga_diag"
PACKAGE_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "a1e149e7e4a20cd254e84a8fd7199607beeafb11fd71cfe4d548226825b06d06"
)
SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
IDENTITY_POINTER = "/files/tb_probe~1native_return_observer.svh/sha256"
GATED_RULE_ID = "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    OBSERVER_RELATIVE,
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_identity(item) for key, item in value.items()}
    return value


def extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("source v12 ZIP SHA256 differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True, exist_ok=False)
    prefix = f"{SOURCE_NAME}/"
    seen: set[str] = set()
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("source v12 ZIP CRC differs")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or not info.filename.startswith(prefix)
            ):
                raise BuildError(f"unsafe source ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(info.filename).relative_to(SOURCE_NAME)
            rel = relative.as_posix()
            if rel in seen:
                raise BuildError(f"duplicate source member: {rel}")
            seen.add(rel)
            target = package.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return package


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"observer marker differs: {label}")
    return text.replace(old, new, 1)


def extend_observer(source: str) -> str:
    source = replace_once(
        source,
        "// v8 dual-ingress extension: uncapped counters distinguish the qualified\n",
        "// v13 buffer-to-GA extension: read-only qualified counters and raw-state\n"
        "// snapshots split Buffer0/4 ARM output, GA group0/2 ingress, and PE\n"
        "// operand tag visibility.  Source-domain counters are sampled only by\n"
        "// the independent clk_db heartbeat and never drive DUT behavior.\n"
        "//\n"
        "// v8 dual-ingress extension: uncapped counters distinguish the qualified\n",
        "header",
    )
    source = replace_once(
        source,
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_INPORT_NUM-1:0]\n"
        "          return_obs_ga_operand_capture_mon;\n",
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_INPORT_NUM-1:0]\n"
        "          return_obs_ga_operand_capture_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][`ARRAY_PORT_TAG-1:0] return_obs_buf_to_ga_rtag_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0] return_obs_buf_to_ga_bp_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0][`GA_INPORT_NUM-1:0][`GA_INPORT_TAG-1:0]\n"
        "          return_obs_ga_group_out_tag_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [1:0] return_obs_ga_group_bp_post_mon;\n"
        "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [`GA_ROW_PE_NUM-1:0][1:0][1:0]\n"
        "          return_obs_ga_operand_inport_valid_mon;\n",
        "monitor declarations",
    )
    source = replace_once(
        source,
        "                assign return_obs_lc0_port_mon\n",
        "                assign return_obs_buf_to_ga_rtag_mon\n"
        "                    [return_obs_group][return_obs_slice][0] =\n"
        "                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
        "                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
        "                        .u_slice_wrapper.u_Slice.buf2gene_array_rtag[0][0];\n"
        "                assign return_obs_buf_to_ga_rtag_mon\n"
        "                    [return_obs_group][return_obs_slice][1] =\n"
        "                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
        "                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
        "                        .u_slice_wrapper.u_Slice.buf2gene_array_rtag[2][0];\n"
        "                assign return_obs_buf_to_ga_bp_mon\n"
        "                    [return_obs_group][return_obs_slice][0] =\n"
        "                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
        "                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
        "                        .u_slice_wrapper.u_Slice.gene_array2buf_bp_post[0][0];\n"
        "                assign return_obs_buf_to_ga_bp_mon\n"
        "                    [return_obs_group][return_obs_slice][1] =\n"
        "                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
        "                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
        "                        .u_slice_wrapper.u_Slice.gene_array2buf_bp_post[2][0];\n"
        "                assign return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group][return_obs_slice][0] =\n"
        "                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
        "                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
        "                        .u_slice_wrapper.u_Slice.u_General_Array\n"
        "                        .GA_INPORT_GROUP[0].u_GA_Inport_Group.ga_inport_group_out_tag;\n"
        "                assign return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group][return_obs_slice][1] =\n"
        "                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
        "                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
        "                        .u_slice_wrapper.u_Slice.u_General_Array\n"
        "                        .GA_INPORT_GROUP[2].u_GA_Inport_Group.ga_inport_group_out_tag;\n"
        "                assign return_obs_ga_group_bp_post_mon\n"
        "                    [return_obs_group][return_obs_slice][0] =\n"
        "                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
        "                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
        "                        .u_slice_wrapper.u_Slice.u_General_Array\n"
        "                        .GA_INPORT_GROUP[0].u_GA_Inport_Group.ga_inport_bp_post;\n"
        "                assign return_obs_ga_group_bp_post_mon\n"
        "                    [return_obs_group][return_obs_slice][1] =\n"
        "                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
        "                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
        "                        .u_slice_wrapper.u_Slice.u_General_Array\n"
        "                        .GA_INPORT_GROUP[2].u_GA_Inport_Group.ga_inport_bp_post;\n"
        "                assign return_obs_lc0_port_mon\n",
        "buffer and group taps",
    )
    for col, slot in ((0, 0), (2, 1)):
        marker = (
            f"                    assign return_obs_ga_input_data_mon\n"
            f"                        [return_obs_group][return_obs_slice][return_obs_row][{slot}] =\n"
        )
        addition = (
            f"                    assign return_obs_ga_operand_inport_valid_mon\n"
            f"                        [return_obs_group][return_obs_slice][return_obs_row][{slot}][0] =\n"
            f"                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
            f"                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
            f"                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group\n"
            f"                            .GA_ROW_PE[return_obs_row].GA_COL_PE[{col}].GA_PE\n"
            f"                            .u_GA_PE.ga_pe_inport_tag[0][`GA_PE_PORT_TAG_WIDTH-1];\n"
            f"                    assign return_obs_ga_operand_inport_valid_mon\n"
            f"                        [return_obs_group][return_obs_slice][return_obs_row][{slot}][1] =\n"
            f"                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_group]\n"
            f"                            .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_slice]\n"
            f"                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group\n"
            f"                            .GA_ROW_PE[return_obs_row].GA_COL_PE[{col}].GA_PE\n"
            f"                            .u_GA_PE.ga_pe_inport_tag[2][`GA_PE_PORT_TAG_WIDTH-1];\n"
        )
        source = replace_once(
            source, marker, addition + marker, f"PE{col} inport tags"
        )
    source = replace_once(
        source,
        "    longint unsigned return_obs_ga_accept_count;\n",
        "    longint unsigned return_obs_ga_accept_count;\n"
        "    longint unsigned return_obs_sg_clock_edge_count;\n"
        "    time return_obs_sg_last_edge_time;\n"
        "    longint unsigned return_obs_buf0_arm_accept_count;\n"
        "    longint unsigned return_obs_buf4_arm_accept_count;\n"
        "    longint unsigned return_obs_ga_group0_accept_count;\n"
        "    longint unsigned return_obs_ga_group2_accept_count;\n",
        "counter declarations",
    )
    source = replace_once(
        source,
        "                    );\n"
        "                end\n"
        "                $fflush(return_obs_fd);\n",
        "                    );\n"
        "                    $fdisplay(\n"
        "                        return_obs_fd,\n"
        "                        \"%0t | BUFFER_TO_GA_COUNTS | event=%s sg_edges=%0d last_sg_edge_ps=%0t buf0_arm_accept=%0d buf4_arm_accept=%0d ga_group0_accept=%0d ga_group2_accept=%0d\",\n"
        "                        $time,\n"
        "                        event_name,\n"
        "                        return_obs_sg_clock_edge_count,\n"
        "                        return_obs_sg_last_edge_time,\n"
        "                        return_obs_buf0_arm_accept_count,\n"
        "                        return_obs_buf4_arm_accept_count,\n"
        "                        return_obs_ga_group0_accept_count,\n"
        "                        return_obs_ga_group2_accept_count\n"
        "                    );\n"
        "                    $fdisplay(\n"
        "                        return_obs_fd,\n"
        "                        \"%0t | BUFFER_TO_GA_STATE | event=%s buf_rtag=0x%0h buf_bp=0x%0h group_tag=0x%0h group_bp=0x%0h pe_operand_valid=0x%0h\",\n"
        "                        $time,\n"
        "                        event_name,\n"
        "                        return_obs_buf_to_ga_rtag_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_buf_to_ga_bp_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_group_out_tag_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_group_bp_post_mon[return_obs_group_id][return_obs_local_slice_id],\n"
        "                        return_obs_ga_operand_inport_valid_mon[return_obs_group_id][return_obs_local_slice_id]\n"
        "                    );\n"
        "                end\n"
        "                $fflush(return_obs_fd);\n",
        "summary snapshots",
    )
    source = replace_once(
        source,
        "        return_obs_ga_accept_count = 0;\n"
        "        return_obs_accum_count = 0;\n",
        "        return_obs_ga_accept_count = 0;\n"
        "        return_obs_sg_clock_edge_count = 0;\n"
        "        return_obs_sg_last_edge_time = 0;\n"
        "        return_obs_buf0_arm_accept_count = 0;\n"
        "        return_obs_buf4_arm_accept_count = 0;\n"
        "        return_obs_ga_group0_accept_count = 0;\n"
        "        return_obs_ga_group2_accept_count = 0;\n"
        "        return_obs_accum_count = 0;\n",
        "initial counter reset",
    )
    source = replace_once(
        source,
        "                return_obs_ga_accept_count = 0;\n"
        "                for (int channel = 0;\n",
        "                return_obs_ga_accept_count = 0;\n"
        "                return_obs_sg_clock_edge_count = 0;\n"
        "                return_obs_sg_last_edge_time = 0;\n"
        "                return_obs_buf0_arm_accept_count = 0;\n"
        "                return_obs_buf4_arm_accept_count = 0;\n"
        "                return_obs_ga_group0_accept_count = 0;\n"
        "                return_obs_ga_group2_accept_count = 0;\n"
        "                for (int channel = 0;\n",
        "exec counter reset",
    )
    source = replace_once(
        source,
        "    // Targeted int32 SUM accumulator-state probe.  One record is emitted for\n"
        "    // each accepted regular-GA input, up to a finite global limit.  The two\n"
        "    // outbuffer slots are printed even when their tags are invalid because\n"
        "    // the v5 return showed stale slot data being selected as input C at the\n"
        "    // first spatial positions of the next block.\n"
        "    always @(posedge u_NDP_Top_new.clk_sg) begin\n"
        "        if (\n"
        "            u_NDP_Top_new.rst_n_sg &&\n"
        "            return_obs_enabled &&\n"
        "            return_obs_accum_state_enabled &&\n"
        "            return_obs_active &&\n"
        "            return_obs_fd != 0\n"
        "        ) begin\n"
        "            for (int row = 0; row < `GA_ROW_PE_NUM; row++) begin\n",
        "    // Targeted int32 SUM accumulator-state probe.  One record is emitted for\n"
        "    // each accepted regular-GA input, up to a finite global limit.  The two\n"
        "    // outbuffer slots are printed even when their tags are invalid because\n"
        "    // the v5 return showed stale slot data being selected as input C at the\n"
        "    // first spatial positions of the next block.\n"
        "    always @(posedge u_NDP_Top_new.clk_sg) begin\n"
        "        if (\n"
        "            u_NDP_Top_new.rst_n_sg &&\n"
        "            return_obs_enabled &&\n"
        "            return_obs_accum_state_enabled &&\n"
        "            return_obs_active &&\n"
        "            return_obs_fd != 0\n"
        "        ) begin\n"
        "            return_obs_sg_clock_edge_count++;\n"
        "            return_obs_sg_last_edge_time = $time;\n"
        "            if (\n"
        "                (|return_obs_buf_to_ga_rtag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0]\n"
        "                    [`ARRAY_PORT_TAG-1 -: `BUFFER_BANK_NUM]) &&\n"
        "                return_obs_buf_to_ga_bp_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0]\n"
        "            ) begin\n"
        "                return_obs_buf0_arm_accept_count++;\n"
        "            end\n"
        "            if (\n"
        "                (|return_obs_buf_to_ga_rtag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1]\n"
        "                    [`ARRAY_PORT_TAG-1 -: `BUFFER_BANK_NUM]) &&\n"
        "                return_obs_buf_to_ga_bp_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1]\n"
        "            ) begin\n"
        "                return_obs_buf4_arm_accept_count++;\n"
        "            end\n"
        "            if (\n"
        "                (return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0][0][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0][1][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0][2][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0][3][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0][4][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0][5][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0][6][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0][7][`GA_INPORT_TAG-1]) &&\n"
        "                return_obs_ga_group_bp_post_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][0]\n"
        "            ) begin\n"
        "                return_obs_ga_group0_accept_count++;\n"
        "            end\n"
        "            if (\n"
        "                (return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1][0][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1][1][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1][2][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1][3][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1][4][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1][5][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1][6][`GA_INPORT_TAG-1] ||\n"
        "                 return_obs_ga_group_out_tag_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1][7][`GA_INPORT_TAG-1]) &&\n"
        "                return_obs_ga_group_bp_post_mon\n"
        "                    [return_obs_group_id][return_obs_local_slice_id][1]\n"
        "            ) begin\n"
        "                return_obs_ga_group2_accept_count++;\n"
        "            end\n"
        "            for (int row = 0; row < `GA_ROW_PE_NUM; row++) begin\n",
        "clk_sg qualified counters",
    )
    return source


def rewrite_identity(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(SOURCE_NAME) < 1:
        raise BuildError("source v12 runner identity absent")
    runner.write_text(
        text.replace(SOURCE_NAME, INSTALL_NAME),
        encoding="utf-8",
        newline="\n",
    )
    for relative in ("workload/sca_cfg.json", "workload/sca_cfg_D.json"):
        path = package / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        replaced = replace_identity(value)
        if replaced == value:
            raise BuildError(f"source namespace absent: {relative}")
        write_json(path, replaced)


def current_rule_receipts() -> list[dict[str, Any]]:
    receipts = [dict(item) for item in v12.base.RULE_RECEIPTS]
    receipts[3]["sha256"] = SERVER_RULE_SHA256
    receipts[3]["reason"] = "current server-package rules"
    for receipt in receipts:
        observed = sha256(ROOT / receipt["path"])
        receipt["current_match"] = observed == receipt["sha256"]
        if not receipt["current_match"]:
            raise BuildError(f"current rule receipt differs: {receipt['path']}")
    return receipts


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = replace_identity(source_manifest)
    plan_sha = sha256(ROOT / ".agents/plan.md")
    receipts = current_rule_receipts()
    observer_sha = sha256(package / OBSERVER_RELATIVE)
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v13",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only Buffer0/4 ARM output, GA group0/2 ingress and PE "
                "operand-tag localization; frozen GAP sum/tail/config/golden "
                "and 73-file numeric workload unchanged; no E3/E4/E5"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    contract = manifest["final_zip_rule_self_audit_contract"]
    applicable = list(contract["applicable_rule_ids"])
    if GATED_RULE_ID not in applicable:
        applicable.append(GATED_RULE_ID)
    contract.update(
        {
            "read_receipt": receipts,
            "applicable_rule_ids": applicable,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only": plan_sha,
            "final_zip_independent_validator_required": True,
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    manifest["rule_receipts"].update(
        {
            "server_rule_sha256": SERVER_RULE_SHA256,
            "current_match": True,
            "plan_sha256_mutable_provenance_only": plan_sha,
        }
    )
    manifest["package_local_observer"].update(
        {
            "identity_json_pointer": IDENTITY_POINTER,
            "identity_single_source": True,
            "runtime_guard_expected_sha_hardcoded": False,
        }
    )
    manifest["observer_binding_contract"].update(
        {
            "source_identity_json_pointer": IDENTITY_POINTER,
            "runner_expected_sha_hardcoded": False,
        }
    )
    manifest["buffer_to_ga_diagnostic"] = {
        "trigger_return_zip_sha256":
            "a820abcbbb99dd468de1cdc42f4389780cb5c0fdc9ecf0f16a0f713c46b65c2d",
        "source_v12_zip_sha256": SOURCE_SHA256,
        "first_divergence":
            "BOTH_PRODUCER_TO_BUFFER_ACCEPTED_TO_ANY_GA_INBUFFER_CAPTURE_ABSENT",
        "qualified_boundaries": [
            "BUFFER0_ARM_READ_ACCEPT",
            "BUFFER4_ARM_READ_ACCEPT",
            "GA_GROUP0_INGRESS_ACCEPT",
            "GA_GROUP2_INGRESS_ACCEPT",
        ],
        "raw_state_only": [
            "BUFFER0_4_OUTPUT_TAG_AND_BACKPRESSURE",
            "GA_GROUP0_2_OUTPUT_TAG_AND_BACKPRESSURE",
            "PE_OPERAND0_2_INPORT_VALID",
        ],
        "source_clock": "clk_sg",
        "snapshot_clock": "clk_db",
        "source_clock_edge_and_last_change_returned": True,
        "observer_algorithm_changed": True,
        "numeric_workload_changed": False,
        "config_changed": False,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED),
    }
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_v13_buffer_to_ga_diag_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity/SCA namespace/manifest/README plus read-only "
                "Buffer-to-GA observer extension"
            ),
        }
    )
    manifest["files"] = file_records(package)
    if manifest["files"][OBSERVER_RELATIVE]["sha256"] != observer_sha:
        raise BuildError("observer manifest receipt differs")
    write_json(manifest_path, manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    numeric_before = {
        path: receipt
        for path, receipt in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    source_records = file_records(package, exclude_manifest=False)
    rewrite_identity(package)
    observer_path = package / OBSERVER_RELATIVE
    observer_path.write_text(
        extend_observer(observer_path.read_text(encoding="utf-8")),
        encoding="utf-8",
        newline="\n",
    )
    (package / "README.md").write_text(
        "# GAP node0071 v13 Buffer-to-GA diagnostic package\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves "
        "the v12 GAP sum/tail/config/golden and all 73 numeric workload files "
        "byte-for-byte. The only diagnostic change adds read-only qualified "
        "Buffer0/4 ARM-output and GA-group0/2 ingress counters, plus raw "
        "PE operand-tag state. Source-domain `clk_sg` counters are snapshotted "
        "by the independent `clk_db` heartbeat with source-clock edge and "
        "last-change witnesses. No DUT signal is driven.\n\nRun once with:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    preflight = v12.base.package_preflight(package)
    guard = v12.manifest_guard(package)
    numeric_after = {
        path: receipt
        for path, receipt in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric workload drifted")
    final_records = file_records(package, exclude_manifest=False)
    changed = {
        path
        for path in set(source_records) & set(final_records)
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    return package, {
        "source_v12_zip_sha256": SOURCE_SHA256,
        "observer_sha256": sha256(observer_path),
        "package_preflight": preflight,
        "manifest_observer_guard": guard,
        "numeric_workload_file_count": len(numeric_after),
        "numeric_workload_tree_equal": True,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v13-repeat-"
    ) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
        if (
            sha256(repeated_zip) != first_sha
            or file_records(repeated, exclude_manifest=False) != first_tree
        ):
            raise BuildError("repeat build differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation_path):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        validation = {
            "schema": "gap-node0071-buffer-to-ga-validation-v13",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "source_v12_quarantined": True,
            **proof,
            "repeated_build": repeated,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "config_rebuilt": False,
            "server_action": False,
        }
        write_json(validation_path, validation)
    except Exception as error:
        print(f"GAP v13 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
