from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v69_branch_owner_successor_v70 as previous  # noqa: E402

SOURCE = "r5_n4_hw_v70_branch_owner_diag"
INSTALL = "r5_n4_hw_v71_token_origin_diag"
SOURCE_SHA = "1076a9a5371d3988c31efbecfa750c10ee12b4ffc5e0777aeffa2a6ea710ec93"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v70_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v70_return_v71_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"replacement count differs count={text.count(old)}: {old[:100]!r}")
    return text.replace(old, new, 1)


def configure() -> None:
    previous.SOURCE = SOURCE
    previous.INSTALL = INSTALL
    previous.SOURCE_SHA = SOURCE_SHA
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    previous.configure()


def mse(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine." + leaf
    )


def observer_block() -> str:
    return f'''

    // v71 TOKEN_ORIGIN_ACTUAL_CONSUMER_BEGIN
    // All event classes are emitted as an all-class bitset in every record.
    bit return_obs_to_enabled;
    integer return_obs_to_limit;
    integer return_obs_to_plusarg_status;
    integer return_obs_to_records;
    longint unsigned return_obs_to_mem_wr;
    longint unsigned return_obs_to_buf_wr;
    longint unsigned return_obs_to_mem_pop;
    longint unsigned return_obs_to_buf_pop;
    longint unsigned return_obs_to_desc;

    initial begin
        return_obs_to_enabled = $test$plusargs("RETURN_OBS_TOKEN_ORIGIN");
        return_obs_to_limit = 128;
        return_obs_to_plusarg_status = $value$plusargs(
            "RETURN_OBS_TOKEN_ORIGIN_LIMIT=%d", return_obs_to_limit
        );
        return_obs_to_records = 0;
        return_obs_to_mem_wr = 0;
        return_obs_to_buf_wr = 0;
        return_obs_to_mem_pop = 0;
        return_obs_to_buf_pop = 0;
        return_obs_to_desc = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_TOKEN_ORIGIN enabled=%0d limit=%0d schema=TOKEN_ORIGIN multiclass=ALL_CLASS_BITSET",
                return_obs_to_enabled, return_obs_to_limit);
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit to_mem_wr, to_buf_wr, to_mem_pop, to_buf_pop, to_desc;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_to_records = 0;
            return_obs_to_mem_wr = 0;
            return_obs_to_buf_wr = 0;
            return_obs_to_mem_pop = 0;
            return_obs_to_buf_pop = 0;
            return_obs_to_desc = 0;
        end else if (return_obs_to_enabled && return_obs_active) begin
            to_mem_wr = {mse('u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_en')};
            to_buf_wr = {mse('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en')};
            to_mem_pop = {mse('u_Memory_AG_Idx_Queue.mem_ag_idx_queue_rd_en')} &&
                         !{mse('u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty')};
            to_buf_pop = {mse('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en')} &&
                         !{mse('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty')};
            to_desc = {mse('wr_data_chl_req_valid')} && {mse('wr_data_chl_req_ready')};
            if (to_mem_wr) return_obs_to_mem_wr++;
            if (to_buf_wr) return_obs_to_buf_wr++;
            if (to_mem_pop) return_obs_to_mem_pop++;
            if (to_buf_pop) return_obs_to_buf_pop++;
            if (to_desc) return_obs_to_desc++;
            if ((to_mem_wr || to_buf_wr || to_mem_pop || to_buf_pop || to_desc) &&
                return_obs_to_records < return_obs_to_limit && return_obs_fd != 0) begin
                return_obs_to_records++;
                $fdisplay(return_obs_fd,
                    "%0t | TOKEN_ORIGIN_EDGE_V1 | qn=%0d mem_wr_ev=%0d buf_wr_ev=%0d mem_pop_ev=%0d buf_pop_ev=%0d desc_ev=%0d mem_wr=%0d buf_wr=%0d mem_pop=%0d buf_pop=%0d desc=%0d mem_in_tag0=%h mem_in_tag1=%h mem_in_tag2=%h mem_bp=%h mem_qwr=%h mem_qrd=%h mem_qempty=%0d buf_row_tag=%h buf_col_tag=%h buf_bp=%h buf_qwr=%h buf_qrd=%h buf_qempty=%0d mem_out_valid=%0d mem_out_tag=%h buf_out_valid=%0d buf_out_tag=%h",
                    $time, return_obs_to_records,
                    to_mem_wr, to_buf_wr, to_mem_pop, to_buf_pop, to_desc,
                    return_obs_to_mem_wr, return_obs_to_buf_wr,
                    return_obs_to_mem_pop, return_obs_to_buf_pop,
                    return_obs_to_desc,
                    {mse('mse_mem_queue_tag[0]')}, {mse('mse_mem_queue_tag[1]')},
                    {mse('mse_mem_queue_tag[2]')}, {mse('mse_mem_queue_bp_pre')},
                    {mse('u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_data')},
                    {mse('u_Memory_AG_Idx_Queue.mem_ag_idx_queue_rd_data')},
                    {mse('u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty')},
                    {mse('mse_buf_queue_row_tag')}, {mse('mse_buf_queue_col_tag')},
                    {mse('mse_buf_queue_bp_pre')},
                    {mse('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_data')},
                    {mse('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_data')},
                    {mse('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty')},
                    {mse('mse_mem_ag_tag_valid')}, {mse('mse_mem_ag_tag')},
                    {mse('mse_buf_ag_tag_valid')}, {mse('mse_buf_ag_tag')});
                $fflush(return_obs_fd);
            end
        end
    end
    // v71 TOKEN_ORIGIN_ACTUAL_CONSUMER_END
'''


def add_runtime_feature(runtime: str) -> str:
    anchor = '''    {
        "feature": "RETURN_OBS_BRANCH_OWNER",
        "enable": "+RETURN_OBS_BRANCH_OWNER",
        "limits": (
            "+RETURN_OBS_BRANCH_OWNER_LIMIT=128",
            "+RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=8",
        ),
        "marker_tokens": (
            "feature=RETURN_OBS_BRANCH_OWNER", "enabled=1",
            "qualified_limit=128", "state_limit=8",
        ),
    },
)'''
    replacement = anchor[:-2] + '''    {
        "feature": "RETURN_OBS_TOKEN_ORIGIN",
        "enable": "+RETURN_OBS_TOKEN_ORIGIN",
        "limits": ("+RETURN_OBS_TOKEN_ORIGIN_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_TOKEN_ORIGIN", "enabled=1", "limit=128",
            "multiclass=ALL_CLASS_BITSET",
        ),
    },
)'''
    return once(runtime, anchor, replacement)


def build_directory(output: Path) -> Path:
    configure()
    with tempfile.TemporaryDirectory(prefix="node0004-v71-source-") as td:
        source = base.extract_source(Path(td))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)

    op = package / "tb_probe/native_return_observer.svh"
    observer = op.read_text(encoding="utf-8").rstrip() + observer_block() + "\n"
    op.write_text(observer, encoding="utf-8", newline="\n")

    rp = package / "PREPARE_AND_RUN.sh"
    runner = rp.read_text(encoding="utf-8")
    anchor = " +RETURN_OBS_BRANCH_OWNER +RETURN_OBS_BRANCH_OWNER_LIMIT=128 +RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=8"
    if runner.count(anchor) != 2:
        raise BuildError("v70 branch-owner runner binding count differs")
    runner = runner.replace(anchor, anchor + " +RETURN_OBS_TOKEN_ORIGIN +RETURN_OBS_TOKEN_ORIGIN_LIMIT=128")
    rp.write_text(runner, encoding="utf-8", newline="\n")

    runtime_path = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime_path.write_text(add_runtime_feature(runtime_path.read_text(encoding="utf-8")),
                            encoding="utf-8", newline="\n")
    manifest_path = package / "package_manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_sha, new_sha = old["observer_sha256"], base.sha256(op)
    manifest = base.replace_hash(old, old_sha, new_sha)
    manifest.setdefault("diagnostic_features", {})["RETURN_OBS_TOKEN_ORIGIN"] = {
        "runtime_enable_parameter": "+RETURN_OBS_TOKEN_ORIGIN",
        "limit_parameters": ["+RETURN_OBS_TOKEN_ORIGIN_LIMIT=128"],
        "edge_schema": "TOKEN_ORIGIN_EDGE_V1",
        "owner_clock": "u_NDP_Top_new.clk_db",
        "owner_reset": "u_NDP_Top_new.rst_n_db",
        "multiclass_strategy": "ALL_CLASS_BITSET_PER_RECORD",
        "required_classes": ["mem_queue_write", "buf_queue_write", "mem_queue_pop",
                             "buf_queue_pop", "descriptor_accept"],
        "parser_policy": "consume every event bit independent of record label",
        "causal_scope": ["Memory_AG combined input queue write/tag", "Buffer_AG combined row/col queue write/tag",
                         "both queue pops", "descriptor accept"],
    }
    manifest.update({
        "install_name": INSTALL, "source_package_sha256": SOURCE_SHA,
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "observer_sha256": new_sha, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False, "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False, "configuration_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False, "mapping_rebuilt": False,
        "bitstream_rebuilt": False, "execplan_rebuilt": False,
        "sca_semantics_rebuilt": False, "functional_rtl_modified": False,
        "server_action": False,
    })
    base.write_json(package / "provenance/v70_to_v71_token_origin.json", {
        "schema": "node0004-v70-to-v71-token-origin-v1",
        "source_v70_sha256": SOURCE_SHA,
        "v70_return_sha256": "3860731999ee024b3589094a95bb3c7e78684424f49b2ea5099fd0f573d5cff7",
        "analysis_sha256": base.sha256(ANALYSIS),
        "last_proven_good": "DESCRIPTOR_18_AND_PREPARED_GROUP_18_JOIN_DRAIN_WITH_BUFFER_POP_21",
        "first_divergence": "POST_DESCRIPTOR_BUFFER_POP_22_ACCEPTS_TAG_0X35_AND_PREPARED_GROUP_20_WITH_NO_DESCRIPTOR",
        "changed_surface": ["fresh identity", "all-class Memory_AG/Buffer_AG token-origin ledger",
                            "runtime feature binding"],
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure",
                   "functional RTL/ISA/hardware/active ndp-sim"],
    })
    receipts = manifest.setdefault("active_receipts", {})
    rule_id = "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001"
    if rule_id not in receipts.setdefault("rules", []):
        receipts["rules"].append(rule_id)
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    a = ap.parse_args()
    out = a.output_root.resolve(); out.mkdir(parents=True, exist_ok=True)
    package = build_directory(out)
    archive = out / f"{INSTALL}.zip"; base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v71-repeat-") as td:
        repeat = build_directory(Path(td)); rz = Path(td) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, rz); deterministic = base.sha256(rz) == digest
    if not deterministic:
        raise BuildError("deterministic rebuild differs")
    sidecar = out / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {"schema": "node0004-v70-to-v71-token-origin-build-v1",
              "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
              "zip": str(archive), "zip_bytes": archive.stat().st_size, "zip_sha256": digest,
              "sidecar": str(sidecar), "deterministic_rebuild_equal": deterministic,
              "source_v70_sha256": SOURCE_SHA, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
              "numeric_analysis_repeated": False, "node0004_workload_rebuilt": False,
              "configuration_rebuilt": False, "functional_rtl_modified": False, "server_action": False}
    base.write_json(out / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
