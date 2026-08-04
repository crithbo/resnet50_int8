from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-gap-ga-rtl-repair-v1"
REPAIR_ID = "gap-ga-int32-outbuffer-validity-v1"
DEFAULT_OUTPUT_REL = Path(
    "artifacts/operator_config_validation/r5-gap-ga-rtl-repair-v1"
)
INCLUDE_REL = Path("NDP_copy01/rtl/includes")
FILE_RELS = (
    Path("rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv"),
    Path("rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv"),
)


class GapGaRtlRepairError(ValueError):
    pass


OUTBUFFER_COUNT_BEFORE = """\
  else if (ga_pe_transout_calculate && (transout_calculate_cnt==3'b010 | transout_calculate_cnt==3'b101)) begin
    if (ga_pe_outbuffer_cnt_wr_update && ga_pe_outbuffer_cnt_rd_update) begin
      ga_pe_outbuffer_count <= ga_pe_outbuffer_count -2 ;
    end
    else if (ga_pe_outbuffer_cnt_wr_update) begin
      ga_pe_outbuffer_count <= ga_pe_outbuffer_count -1;
    end
    else if (ga_pe_outbuffer_cnt_rd_update) begin
      ga_pe_outbuffer_count <= ga_pe_outbuffer_count -3;
    end
    else begin
      ga_pe_outbuffer_count <= ga_pe_outbuffer_count -2;
    end
  end
"""

OUTBUFFER_COUNT_AFTER = """\
  else if (ga_pe_transout_result_last_bit) begin
    // The result-last path invalidates both tags, so occupancy must agree.
    ga_pe_outbuffer_count <= 0;
  end
  else if (ga_pe_transout_calculate && (transout_calculate_cnt==3'b010 | transout_calculate_cnt==3'b101)) begin
    // The compaction point invalidates both slots above.  Reset occupancy
    // instead of subtracting a fixed two entries from a possibly smaller
    // unsigned count (1-2 previously wrapped to the illegal value 3).
    ga_pe_outbuffer_count <= 0;
  end
"""

INBUFFER_MATCH_BEFORE = """\
assign ga_pe_inbuffer_matched = ga_pe_enable && ((!ga_pe_inport_enable[0]) | ga_pe_inbuffer_valid_bit[0])
                                             && ((!ga_pe_inport_enable[1]) | ga_pe_inbuffer_valid_bit[1])
                                             && ((!ga_pe_inport_enable[2]) | ga_pe_inbuffer_valid_bit[2] | (alu_op_is_transout&&(transout_initial[0]|transout_initial[1])) );// | inport2_not_used);
"""

INBUFFER_MATCH_AFTER = """\
wire int32_transout_feedback_required;
assign int32_transout_feedback_required = alu_op_is_transout && alu_is_int32
                                        && !ga_pe_transout_calculate
                                        && end_transout_initial;
assign ga_pe_inbuffer_matched = ga_pe_enable && ((!ga_pe_inport_enable[0]) | ga_pe_inbuffer_valid_bit[0])
                                             && ((!ga_pe_inport_enable[1]) | ga_pe_inbuffer_valid_bit[1])
                                             && ((!ga_pe_inport_enable[2]) | ga_pe_inbuffer_valid_bit[2] | (alu_op_is_transout&&(transout_initial[0]|transout_initial[1])))
                                             && (!int32_transout_feedback_required | ga_pe_outbuffer2alu_valid_bit);// | inport2_not_used);
"""

INBUFFER_TAG_DATA_BEFORE = """\
assign ga_pe_alu_input_tag     = !alu_op_is_transout           ? ga_pe_inbuffer2alu_tag        :                                // no transout, from inbuffer
                                 !alu_is_int8 && transout_initial==2'b00       ? ga_pe_inbuffer2alu_tag        :                                // first transout, from inbuffer
                                 ga_pe_transout_calculate      ? (ga_pe_transout_calculate_valid_port2 ? ga_pe_transout_tag : {`GA_PE_ALU_TAG_WIDTH{1'b0}} ) :   // transout caculate
                                 !end_transout_initial       ? ga_pe_inbuffer2alu_tag  :                                // first transout, from inbuffer
                                 ga_pe_outbuffer2alu_tag;//ga_pe_outbuffer2alu_valid_bit ? ga_pe_outbuffer2alu_tag       : ga_pe_inbuffer2alu_tag;        // other transout, from outbuffer

assign ga_pe_alu_input_data[2] = !alu_op_is_transout           ? ga_pe_inbuffer_data[2]        :                                // no transout, from inbuffer
                                 !alu_is_int8 && transout_initial==2'b00       ? ga_pe_inbuffer_data[2]        :                                // first transout, from inbuffer
                                 ga_pe_transout_calculate      ? (ga_pe_transout_calculate_valid_port2 ? ga_pe_outbuffer2alu_data : {`GA_PE_ALU_DATA_WIDTH{1'b0}} ) :  // transout caculate, from outbuffer
                                 !end_transout_initial       ? {`GA_PE_ALU_DATA_WIDTH{1'b0}} :                                // first transout, from inbuffer
                                 ga_pe_outbuffer2alu_data;//ga_pe_outbuffer2alu_valid_bit ? ga_pe_outbuffer2alu_data      : {`GA_PE_ALU_DATA_WIDTH{1'b0}}; // other transout, from outbuffer
"""

INBUFFER_TAG_DATA_AFTER = """\
assign ga_pe_alu_input_tag     = !alu_op_is_transout           ? ga_pe_inbuffer2alu_tag        :                                // no transout, from inbuffer
                                 !alu_is_int8 && transout_initial==2'b00       ? ga_pe_inbuffer2alu_tag        :                                // first transout, from inbuffer
                                 ga_pe_transout_calculate      ? (ga_pe_transout_calculate_valid_port2 ? ga_pe_transout_tag : {`GA_PE_ALU_TAG_WIDTH{1'b0}} ) :   // transout caculate
                                 !end_transout_initial       ? ga_pe_inbuffer2alu_tag  :                                // first transout, from inbuffer
                                 ga_pe_outbuffer2alu_valid_bit ? ga_pe_outbuffer2alu_tag : {`GA_PE_ALU_TAG_WIDTH{1'b0}}; // other transout, valid outbuffer only

assign ga_pe_alu_input_data[2] = !alu_op_is_transout           ? ga_pe_inbuffer_data[2]        :                                // no transout, from inbuffer
                                 !alu_is_int8 && transout_initial==2'b00       ? ga_pe_inbuffer_data[2]        :                                // first transout, from inbuffer
                                 ga_pe_transout_calculate      ? (ga_pe_transout_calculate_valid_port2 ? ga_pe_outbuffer2alu_data : {`GA_PE_ALU_DATA_WIDTH{1'b0}} ) :  // transout caculate, from outbuffer
                                 !end_transout_initial       ? {`GA_PE_ALU_DATA_WIDTH{1'b0}} :                                // first transout, from inbuffer
                                 ga_pe_outbuffer2alu_valid_bit ? ga_pe_outbuffer2alu_data : {`GA_PE_ALU_DATA_WIDTH{1'b0}}; // other transout, valid outbuffer only
"""


def _canonical_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _canonical_sha256_text(text: str) -> str:
    return hashlib.sha256(_canonical_text(text).encode("utf-8")).hexdigest()


def _replace_once(text: str, before: str, after: str, replacement_id: str) -> str:
    count = text.count(before)
    if count != 1:
        raise GapGaRtlRepairError(
            f"{replacement_id} preimage occurrence count differs: {count}"
        )
    return text.replace(before, after, 1)


def repaired_sources(project_root: Path) -> dict[Path, str]:
    root = project_root.resolve()
    outbuffer_path = root / "NDP_copy01" / FILE_RELS[0]
    inbuffer_path = root / "NDP_copy01" / FILE_RELS[1]
    outbuffer = outbuffer_path.read_text(encoding="utf-8")
    inbuffer = inbuffer_path.read_text(encoding="utf-8")
    outbuffer = _replace_once(
        outbuffer,
        OUTBUFFER_COUNT_BEFORE,
        OUTBUFFER_COUNT_AFTER,
        "reset-occupancy-at-transout-compaction",
    )
    inbuffer = _replace_once(
        inbuffer,
        INBUFFER_MATCH_BEFORE,
        INBUFFER_MATCH_AFTER,
        "stall-int32-feedback-until-valid",
    )
    inbuffer = _replace_once(
        inbuffer,
        INBUFFER_TAG_DATA_BEFORE,
        INBUFFER_TAG_DATA_AFTER,
        "gate-int32-feedback-tag-and-data",
    )
    return {
        FILE_RELS[0]: _canonical_text(outbuffer) + "\n",
        FILE_RELS[1]: _canonical_text(inbuffer) + "\n",
    }


def _iverilog_check(project_root: Path, sources: Mapping[Path, Path]) -> dict[str, Any]:
    root = project_root.resolve()
    executable = shutil.which("iverilog")
    if executable is None:
        return {
            "available": False,
            "passed": None,
            "reason": "iverilog_not_found",
        }
    records: list[dict[str, Any]] = []
    for relative, path in sources.items():
        top = path.stem
        result = subprocess.run(
            [
                executable,
                "-g2012",
                "-tnull",
                "-s",
                top,
                "-I",
                str(root / INCLUDE_REL),
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        records.append(
            {
                "path": relative.as_posix(),
                "top": top,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
    return {
        "available": True,
        "passed": all(item["returncode"] == 0 for item in records),
        "records": records,
    }


def build_gap_ga_rtl_repair(project_root: Path, output_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise GapGaRtlRepairError(f"output must be fresh: {output}")
    repaired = repaired_sources(root)
    output.mkdir(parents=True)
    written: dict[Path, Path] = {}
    file_records: dict[str, dict[str, Any]] = {}
    for relative, text in repaired.items():
        source = root / "NDP_copy01" / relative
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8", newline="\n")
        written[relative] = destination
        file_records[relative.as_posix()] = {
            "source_path": f"NDP_copy01/{relative.as_posix()}",
            "source_size_bytes": source.stat().st_size,
            "source_sha256": sha256_file(source),
            "source_canonical_text_sha256": _canonical_sha256_text(
                source.read_text(encoding="utf-8")
            ),
            "patched_path": relative.as_posix(),
            "patched_size_bytes": destination.stat().st_size,
            "patched_sha256": sha256_file(destination),
            "patched_canonical_text_sha256": _canonical_sha256_text(text),
        }
    syntax = _iverilog_check(root, written)
    if syntax.get("available") and syntax.get("passed") is not True:
        raise GapGaRtlRepairError(f"iverilog rejected repair: {syntax}")
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "repair_id": REPAIR_ID,
        "status": "rtl_repair_bundle_ready_local_validation_only",
        "scope": {
            "functional_rtl_modified_on_server_during_test": True,
            "source_reference_modified": False,
            "server_install_hash_gated": True,
            "server_restore_required": True,
            "target": "GAP int32 SUM transout/outbuffer control",
        },
        "fixes": [
            {
                "issue": "outbuffer_count_unsigned_underflow",
                "rule": (
                    "tag-clearing transout compaction/result-last paths set "
                    "occupancy to zero"
                ),
            },
            {
                "issue": "invalid_outbuffer_slot_reused_as_input_c",
                "rule": (
                    "INT32 feedback waits for outbuffer valid and invalid tag/data "
                    "are forced to zero"
                ),
            },
        ],
        "files": file_records,
        "local_syntax_check": syntax,
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    manifest_path = output / "RTL_PATCH_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def validate_gap_ga_rtl_repair(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    manifest_path = output / "RTL_PATCH_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = manifest.pop("manifest_sha256", None)
    if expected_hash != sha256_bytes(canonical_json_bytes(manifest)):
        raise GapGaRtlRepairError("RTL repair manifest receipt differs")
    manifest["manifest_sha256"] = expected_hash
    repaired = repaired_sources(root)
    expected_paths = {relative.as_posix() for relative in FILE_RELS}
    if set(manifest.get("files", {})) != expected_paths:
        raise GapGaRtlRepairError("RTL repair file set differs")
    written: dict[Path, Path] = {}
    for relative, expected_text in repaired.items():
        source = root / "NDP_copy01" / relative
        patched = output / relative
        if patched.read_text(encoding="utf-8") != expected_text:
            raise GapGaRtlRepairError(f"patched RTL differs: {relative}")
        record = manifest["files"][relative.as_posix()]
        if (
            record.get("source_sha256") != sha256_file(source)
            or record.get("patched_sha256") != sha256_file(patched)
            or record.get("source_canonical_text_sha256")
            != _canonical_sha256_text(source.read_text(encoding="utf-8"))
            or record.get("patched_canonical_text_sha256")
            != _canonical_sha256_text(expected_text)
        ):
            raise GapGaRtlRepairError(f"RTL repair identity differs: {relative}")
        written[relative] = patched
    syntax = _iverilog_check(root, written)
    if syntax.get("available") and syntax.get("passed") is not True:
        raise GapGaRtlRepairError("iverilog rejected checked RTL repair")
    return manifest


def repaired_outbuffer_count(
    current: int,
    *,
    compaction: bool,
    result_last: bool,
    write: bool,
    read: bool,
) -> int:
    if current < 0 or current > 2:
        raise GapGaRtlRepairError("input occupancy is outside depth-2 range")
    if result_last or compaction:
        return 0
    if write and not read:
        return min(current + 1, 2)
    if read and not write:
        return max(current - 1, 0)
    return current


def int32_feedback_allowed(
    *,
    transout: bool,
    int32_mode: bool,
    calculating: bool,
    initialization_done: bool,
    outbuffer_valid: bool,
) -> bool:
    feedback_required = (
        transout and int32_mode and not calculating and initialization_done
    )
    return not feedback_required or outbuffer_valid


__all__ = [
    "DEFAULT_OUTPUT_REL",
    "FILE_RELS",
    "GapGaRtlRepairError",
    "REPAIR_ID",
    "SCHEMA",
    "build_gap_ga_rtl_repair",
    "int32_feedback_allowed",
    "repaired_outbuffer_count",
    "repaired_sources",
    "validate_gap_ga_rtl_repair",
]
