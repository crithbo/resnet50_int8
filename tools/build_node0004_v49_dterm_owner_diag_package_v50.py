from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v48_mse3_branch_fix_package_v49 as prior


base = prior.base
SOURCE_NAME = "r5_n4_hw_v49_lc9_actual_compilefix"
INSTALL_NAME = "r5_n4_hw_v50_dterm_owner_diag"
SOURCE_SHA256 = "2b7faeb4b838133f041432ff707792047d113bf65871aa8936e3f2f4c502e27c"
RETURN_SHA256 = "722a1cee4b7e54564d060e202792d8179e6223570b8bfbb5fd51eac3f268637b"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
AGENT_SHA256 = "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
PLAN_SHA256 = "43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70"
INDEX_SHA256 = "2697fec8192f5008a0b5f288a4c38c36e9f493ff85db264479e4c5a88b03b706"
SERVER_SHA256 = "5540e9c724e9c313e9a874a8251ad291328d4df80f01382ca091520893e757a1"
COMMON_SHA256 = "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1"
NDP_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
INT8_SA_SHA256 = "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
README_SHA256 = "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v49_return_analysis/v50_build"


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v49 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise BuildError(f"v49 source CRC failed at {bad}")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if path.parts:
                roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v49 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def iga(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_Index_Generation_Array"
        f".{leaf}"
    )


def mse4(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
        f".{leaf}"
    )


def observer_block() -> str:
    ports = [iga(f"iga_lc_outport[{index}]") for index in (13, 14, 15, 9)]
    bps = [iga(f"iga_lc_outport_bp_post[{index}]") for index in (13, 14, 15, 9)]
    return f'''

    // v50 DTERM_OWNER_ACTUAL_CONSUMER_BEGIN
    // v50 D-terminal owner chain. Only valid&&all-ready, FIFO transfers,
    // and selected last-tag transfers count as progress. Held levels are state.
    bit return_obs_dt_enabled;
    integer return_obs_dt_limit;
    integer return_obs_dt_plusarg_status;
    integer return_obs_dt_records;
    longint unsigned return_obs_dt_lc_adv [0:3];
    longint unsigned return_obs_dt_lc_last0 [0:3];
    longint unsigned return_obs_dt_row_out;
    longint unsigned return_obs_dt_row_last0;
    longint unsigned return_obs_dt_col_out;
    longint unsigned return_obs_dt_col_last0;
    longint unsigned return_obs_dt_buf_push;
    longint unsigned return_obs_dt_buf_last0;
    longint unsigned return_obs_dt_buf_pop;
    longint unsigned return_obs_dt_desc_push;
    longint unsigned return_obs_dt_desc_pop;
    longint unsigned return_obs_dt_post_desc_buf_push;
    bit return_obs_dt_after_desc_terminal;

    initial begin
        return_obs_dt_enabled = $test$plusargs("RETURN_OBS_DTERM_OWNER");
        return_obs_dt_limit = 96;
        return_obs_dt_plusarg_status = $value$plusargs(
            "RETURN_OBS_DTERM_OWNER_LIMIT=%d", return_obs_dt_limit
        );
        return_obs_dt_records = 0;
        for (int dt_i = 0; dt_i < 4; dt_i++) begin
            return_obs_dt_lc_adv[dt_i] = 0;
            return_obs_dt_lc_last0[dt_i] = 0;
        end
        return_obs_dt_row_out = 0;
        return_obs_dt_row_last0 = 0;
        return_obs_dt_col_out = 0;
        return_obs_dt_col_last0 = 0;
        return_obs_dt_buf_push = 0;
        return_obs_dt_buf_last0 = 0;
        return_obs_dt_buf_pop = 0;
        return_obs_dt_desc_push = 0;
        return_obs_dt_desc_pop = 0;
        return_obs_dt_post_desc_buf_push = 0;
        return_obs_dt_after_desc_terminal = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_DTERM_OWNER enabled=%0d limit_name=RETURN_OBS_DTERM_OWNER_LIMIT limit=%0d schema=DTERM_OWNER",
                return_obs_dt_enabled, return_obs_dt_limit
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit dt_lc_adv [0:3];
        bit dt_lc_last0 [0:3];
        bit dt_row_out;
        bit dt_row_last0;
        bit dt_col_out;
        bit dt_col_last0;
        bit dt_buf_push;
        bit dt_buf_last0;
        bit dt_buf_pop;
        bit dt_desc_push;
        bit dt_desc_pop;
        bit dt_desc_terminal;
        bit dt_trigger;
        logic [22:0] dt_port [0:3];
        logic [22:0] dt_row_port;
        logic [22:0] dt_col_port;
        logic [`MSE_BUF_AG_INPORT_TAG_WIDTH-1:0] dt_buf_tag;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_dt_records = 0;
            for (int dt_i = 0; dt_i < 4; dt_i++) begin
                return_obs_dt_lc_adv[dt_i] = 0;
                return_obs_dt_lc_last0[dt_i] = 0;
            end
            return_obs_dt_row_out = 0;
            return_obs_dt_row_last0 = 0;
            return_obs_dt_col_out = 0;
            return_obs_dt_col_last0 = 0;
            return_obs_dt_buf_push = 0;
            return_obs_dt_buf_last0 = 0;
            return_obs_dt_buf_pop = 0;
            return_obs_dt_desc_push = 0;
            return_obs_dt_desc_pop = 0;
            return_obs_dt_post_desc_buf_push = 0;
            return_obs_dt_after_desc_terminal = 0;
        end else if (return_obs_dt_enabled && return_obs_active) begin
            dt_port[0] = {ports[0]};
            dt_port[1] = {ports[1]};
            dt_port[2] = {ports[2]};
            dt_port[3] = {ports[3]};
            dt_lc_adv[0] = dt_port[0][22] && (&{bps[0]});
            dt_lc_adv[1] = dt_port[1][22] && (&{bps[1]});
            dt_lc_adv[2] = dt_port[2][22] && (&{bps[2]});
            dt_lc_adv[3] = dt_port[3][22] && (&{bps[3]});
            for (int dt_i = 0; dt_i < 4; dt_i++)
                dt_lc_last0[dt_i] = dt_lc_adv[dt_i] &&
                    dt_port[dt_i][21] && (dt_port[dt_i][19:16] == 0);

            dt_row_port = {iga('IGA_ROW_LC[4].u_IGA_ROW_LC.iga_row_lc_outport')};
            dt_col_port = {iga('IGA_COL_LC[4].u_IGA_COL_LC.iga_col_lc_outport')};
            dt_row_out =
                {iga('IGA_ROW_LC[4].u_IGA_ROW_LC.u_IGA_ROW_LC_Counter.iga_row_lc_cnt_outport_valid_bit')} &&
                {iga('IGA_ROW_LC[4].u_IGA_ROW_LC.iga_row_lc_cnt_bp_post')};
            dt_col_out =
                {iga('IGA_COL_LC[4].u_IGA_COL_LC.u_IGA_COL_LC_Counter.iga_col_lc_cnt_outport_valid_bit')} &&
                {iga('IGA_COL_LC[4].u_IGA_COL_LC.iga_col_lc_cnt_bp_post')};
            dt_row_last0 = dt_row_out && dt_row_port[21] &&
                           (dt_row_port[19:16] == 0);
            dt_col_last0 = dt_col_out && dt_col_port[21] &&
                           (dt_col_port[19:16] == 0);

            dt_buf_tag = {mse4('u_Buffer_AG_Idx_Queue.mse_buf_ag_tag')};
            dt_buf_push =
                {mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en')} &&
                !{mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full')};
            dt_buf_pop =
                {mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_rd_en')} &&
                !{mse4('u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_empty')};
            dt_buf_last0 = dt_buf_pop && dt_buf_tag[5] &&
                           (dt_buf_tag[3:0] == 0);
            dt_desc_push =
                {mse4('u_WR_Data_Channel.wr_chl_queue_wr_en')} &&
                !{mse4('u_WR_Data_Channel.wr_chl_queue_full')};
            dt_desc_pop =
                {mse4('u_WR_Data_Channel.wr_chl_queue_rd_en')} &&
                !{mse4('u_WR_Data_Channel.wr_chl_queue_empty')};
            dt_desc_terminal = dt_desc_pop && !dt_desc_push &&
                ({mse4('u_WR_Data_Channel.u_wr_chl_queue.fifo_counter')} == 1);

            for (int dt_i = 0; dt_i < 4; dt_i++) begin
                if (dt_lc_adv[dt_i]) return_obs_dt_lc_adv[dt_i]++;
                if (dt_lc_last0[dt_i]) return_obs_dt_lc_last0[dt_i]++;
            end
            if (dt_row_out) return_obs_dt_row_out++;
            if (dt_row_last0) return_obs_dt_row_last0++;
            if (dt_col_out) return_obs_dt_col_out++;
            if (dt_col_last0) return_obs_dt_col_last0++;
            if (dt_buf_push) return_obs_dt_buf_push++;
            if (dt_buf_last0) return_obs_dt_buf_last0++;
            if (dt_buf_pop) return_obs_dt_buf_pop++;
            if (dt_desc_push) return_obs_dt_desc_push++;
            if (dt_desc_pop) return_obs_dt_desc_pop++;
            if (return_obs_dt_after_desc_terminal && dt_buf_push)
                return_obs_dt_post_desc_buf_push++;
            if (dt_desc_terminal) return_obs_dt_after_desc_terminal = 1;

            dt_trigger = dt_desc_terminal ||
                (return_obs_dt_after_desc_terminal && dt_buf_push &&
                 (return_obs_dt_post_desc_buf_push == 0));
            for (int dt_i = 0; dt_i < 4; dt_i++)
                dt_trigger = dt_trigger || dt_lc_last0[dt_i] ||
                             (dt_lc_adv[dt_i] &&
                              (return_obs_dt_lc_adv[dt_i] == 1));
            dt_trigger = dt_trigger || dt_row_last0 || dt_col_last0 ||
                         dt_buf_last0;
            if (dt_trigger && return_obs_dt_records < return_obs_dt_limit &&
                return_obs_fd != 0) begin
                return_obs_dt_records++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | DTERM_OWNER_EDGE_V1 | n=%0d lc13=%h lc14=%h lc15=%h lc9=%h adv=0x%0h last0=0x%0h row=%h col=%h row_out=%0d row_last0=%0d col_out=%0d col_last0=%0d buf_push=%0d buf_pop=%0d buf_tag=%h buf_last0=%0d desc_push=%0d desc_pop=%0d desc_terminal=%0d post_desc_buf_push=%0d",
                    $time, return_obs_dt_records,
                    dt_port[0], dt_port[1], dt_port[2], dt_port[3],
                    {{dt_lc_adv[3], dt_lc_adv[2], dt_lc_adv[1], dt_lc_adv[0]}},
                    {{dt_lc_last0[3], dt_lc_last0[2],
                      dt_lc_last0[1], dt_lc_last0[0]}},
                    dt_row_port, dt_col_port, dt_row_out, dt_row_last0,
                    dt_col_out, dt_col_last0, dt_buf_push, dt_buf_pop,
                    dt_buf_tag, dt_buf_last0, dt_desc_push, dt_desc_pop,
                    dt_desc_terminal, return_obs_dt_post_desc_buf_push
                );
                $fflush(return_obs_fd);
            end
        end
    end

    task automatic return_obs_write_dterm_owner_state(input string event_name);
        if (return_obs_dt_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "%0t | DTERM_OWNER_BOUNDARY_V1 | event=%s lc13_adv=%0d lc14_adv=%0d lc15_adv=%0d lc9_adv=%0d lc13_last0=%0d lc14_last0=%0d lc15_last0=%0d lc9_last0=%0d row_out=%0d row_last0=%0d col_out=%0d col_last0=%0d buf_push=%0d buf_pop=%0d buf_last0=%0d desc_push=%0d desc_pop=%0d post_desc_buf_push=%0d lc13=%h lc14=%h lc15=%h lc9=%h row=%h col=%h buf_tag=%h buf_mode=%h buf_keep=%h desc_empty=%0d desc_count=%0d",
                $time, event_name,
                return_obs_dt_lc_adv[0], return_obs_dt_lc_adv[1],
                return_obs_dt_lc_adv[2], return_obs_dt_lc_adv[3],
                return_obs_dt_lc_last0[0], return_obs_dt_lc_last0[1],
                return_obs_dt_lc_last0[2], return_obs_dt_lc_last0[3],
                return_obs_dt_row_out, return_obs_dt_row_last0,
                return_obs_dt_col_out, return_obs_dt_col_last0,
                return_obs_dt_buf_push, return_obs_dt_buf_pop,
                return_obs_dt_buf_last0, return_obs_dt_desc_push,
                return_obs_dt_desc_pop, return_obs_dt_post_desc_buf_push,
                {ports[0]}, {ports[1]}, {ports[2]}, {ports[3]},
                {iga('IGA_ROW_LC[4].u_IGA_ROW_LC.iga_row_lc_outport')},
                {iga('IGA_COL_LC[4].u_IGA_COL_LC.iga_col_lc_outport')},
                {mse4('u_Buffer_AG_Idx_Queue.mse_buf_ag_tag')},
                {mse4('u_Buffer_AG_Idx_Queue.mse_buf_idx_mode')},
                {mse4('u_Buffer_AG_Idx_Queue.mse_buf_idx_keep_last_index')},
                {mse4('u_WR_Data_Channel.wr_chl_queue_empty')},
                {mse4('u_WR_Data_Channel.u_wr_chl_queue.fifo_counter')}
            );
            $fflush(return_obs_fd);
        end
    endtask
    // v50 DTERM_OWNER_ACTUAL_CONSUMER_END
'''


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "DTERM_OWNER_BOUNDARY_V1" in text:
        raise BuildError("D-terminal owner observer already present")
    anchor = (
        '                return_obs_write_lc9_actual_state("DIAG_DECISION");'
    )
    if text.count(anchor) != 1:
        raise BuildError("decision hook anchor differs")
    text = text.replace(
        anchor,
        anchor
        + '\n                return_obs_write_dterm_owner_state("DIAG_DECISION");',
        1,
    )
    path.write_text(text + observer_block(), encoding="utf-8", newline="\n")
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = "+RETURN_OBS_LC9_ACTUAL_LIMIT=192"
    if text.count(anchor) != 2:
        raise BuildError("runtime argv anchor differs")
    text = text.replace(
        anchor,
        anchor
        + " +RETURN_OBS_DTERM_OWNER +RETURN_OBS_DTERM_OWNER_LIMIT=96",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime_feature_contract(package: Path) -> None:
    path = (
        package
        / "package_tools/node0004_hang_localization_runtime.py"
    )
    text = path.read_text(encoding="utf-8")
    anchor = '''    {
        "feature": "RETURN_OBS_LC9_ACTUAL",
        "enable": "+RETURN_OBS_LC9_ACTUAL",
        "limits": ("+RETURN_OBS_LC9_ACTUAL_LIMIT=192",),
        "marker_tokens": (
            "feature=RETURN_OBS_LC9_ACTUAL", "enabled=1", "limit=192",
        ),
    },
)'''
    addition = '''    {
        "feature": "RETURN_OBS_LC9_ACTUAL",
        "enable": "+RETURN_OBS_LC9_ACTUAL",
        "limits": ("+RETURN_OBS_LC9_ACTUAL_LIMIT=192",),
        "marker_tokens": (
            "feature=RETURN_OBS_LC9_ACTUAL", "enabled=1", "limit=192",
        ),
    },
    {
        "feature": "RETURN_OBS_DTERM_OWNER",
        "enable": "+RETURN_OBS_DTERM_OWNER",
        "limits": ("+RETURN_OBS_DTERM_OWNER_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_DTERM_OWNER", "enabled=1", "limit=96",
        ),
    },
)'''
    if text.count(anchor) != 1:
        raise BuildError("runtime feature-contract anchor differs")
    path.write_text(
        text.replace(anchor, addition, 1), encoding="utf-8", newline="\n"
    )


def write_provenance(package: Path) -> Path:
    path = package / "provenance/v49_return_v50_dterm_owner_diag.json"
    base.write_json(
        path,
        {
            "schema": "node0004-v49-return-v50-dterm-owner-diag-v1",
            "bound_return_sha256": RETURN_SHA256,
            "source_v49_sha256": SOURCE_SHA256,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "last_proven_good": (
                "LC9_GLOBAL_ACCEPT_TO_LC7_CAPTURE_AND_MSE3_QUEUE_PROGRESS_"
                "PLUS_32_DESCRIPTOR_DATAHUB_WRITES"
            ),
            "first_divergence": (
                "D_BUFFER_SOURCE_SCHEDULE_CONTINUES_AFTER_MEMORY_DESCRIPTOR_"
                "TERMINAL_WITHOUT_LAST_INDEX0_PROPAGATION"
            ),
            "candidate_observation_matrix": {
                "UPSTREAM_LC13_SOURCE_STALL": [
                    "lc13 qualified advance",
                    "lc13 last0",
                ],
                "LC13_TO_LC14_TO_LC15_CHAIN_STALL": [
                    "lc13/lc14/lc15 qualified advance counts",
                    "first accepted tags",
                ],
                "LC15_TO_LC9_TERMINAL_LOSS": [
                    "lc15 versus lc9 qualified advance",
                    "lc15 versus lc9 last0",
                ],
                "GROUP4_EXPANSION_EXCEEDS_DESCRIPTOR_LIFETIME": [
                    "row/col qualified outputs",
                    "Buffer_AG push/pop",
                    "descriptor push/pop",
                    "first post-terminal Buffer_AG push",
                ],
                "BUFFER_TAG_TERMINAL_OWNER_MISMATCH": [
                    "row/col last0",
                    "selected Buffer_AG tag last0",
                    "materialized mode/keep fields",
                ],
            },
            "frozen": {
                "numeric_w3_qparam_tail_workload_config_golden": True,
                "timeout_backpressure": True,
                "functional_rtl": True,
            },
            "hardware_change_forbidden": True,
        },
    )
    return path


def update_manifest(package: Path, observer_sha: str, provenance: Path) -> None:
    path = package / "package_manifest.json"
    manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-dterm-owner-package-v50",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
            "observer_sha256": observer_sha,
        }
    )
    receipts = manifest["active_receipts"]
    receipts.update(
        {
            "agent_sha256": AGENT_SHA256,
            "plan_mutable_provenance_sha256": PLAN_SHA256,
            "server_package_rule_sha256": SERVER_SHA256,
            "common_operator_rule_sha256": COMMON_SHA256,
            "ndp_hardware_fields_rule_sha256": NDP_SHA256,
        }
    )
    for item in receipts["generation_read_receipt"]:
        reason = item.get("reason")
        if reason == "server package routing":
            item["sha256"] = INDEX_SHA256
        elif reason == "common server package gates":
            item["sha256"] = SERVER_SHA256
        elif reason == "Conv INT8 SA accumulate release gate":
            item["sha256"] = INT8_SA_SHA256
        elif reason == "active server entry":
            item["sha256"] = README_SHA256
    for rule_id in [
        "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
        "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
        "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
        "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
        "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    ]:
        if rule_id not in receipts["rules"]:
            receipts["rules"].append(rule_id)

    for row in manifest["release_gate_matrix"]:
        if row["gate_id"] == "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL":
            row.update(
                {
                    "applicability": "blocking_applicable",
                    "reason": "v50 adds exact D-terminal owner-chain consumers",
                    "changed_surface": [
                        "native_return_observer.svh DTERM_OWNER span"
                    ],
                    "evidence": [
                        "focused compatible-frontend syntax",
                        "actual-consumer identifier closure",
                        "leaf deletion/rename/wrong-sibling negatives",
                    ],
                    "blocking": True,
                }
            )
        elif row["gate_id"] == "CHANGED_OBSERVER_OR_CANONICAL_SEMANTICS":
            row.update(
                {
                    "applicability": "blocking_applicable",
                    "reason": "new triggered D-terminal owner predicate",
                    "changed_surface": [
                        "DTERM_OWNER_EDGE_V1",
                        "DTERM_OWNER_BOUNDARY_V1",
                    ],
                    "evidence": [
                        "qualified predicate trace",
                        "candidate-observation matrix",
                    ],
                    "blocking": True,
                }
            )
        elif row["gate_id"] == "CHANGED_MATERIALIZED_CONFIG_CONSUMER_CONTRACT":
            row.update(
                {
                    "applicability": "receipt_reuse",
                    "reason": "all runtime/config/bitstream bytes are frozen",
                    "changed_surface": [],
                    "evidence": [
                        "source-successor runtime byte equality"
                    ],
                    "blocking": False,
                }
            )

    feature = {
        "feature": "RETURN_OBS_DTERM_OWNER",
        "runtime_enable_parameter": "+RETURN_OBS_DTERM_OWNER",
        "limit_or_budget_parameters": [
            "+RETURN_OBS_DTERM_OWNER_LIMIT=96"
        ],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 "
            "feature=RETURN_OBS_DTERM_OWNER enabled=1 "
            "limit_name=RETURN_OBS_DTERM_OWNER_LIMIT limit=96 "
            "schema=DTERM_OWNER"
        ),
        "expected_record_schema": "DTERM_OWNER_BOUNDARY_V1",
        "edge_record_schema": "DTERM_OWNER_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
    }
    manifest["diagnostic_feature_runtime_binding"]["features"].append(feature)
    manifest["dterm_owner_diagnostic"] = {
        **feature,
        "candidate_observation_matrix_path": provenance.relative_to(
            package
        ).as_posix(),
        "owner_clock": "u_NDP_Top_new.clk_db",
        "owner_reset": "u_NDP_Top_new.rst_n_db",
        "qualified_progress_only": True,
        "held_level_is_state_only": True,
        "functional_fix": False,
        "configuration_changed": False,
    }
    manifest["v49_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "LC9_ACTUAL_BRANCH_CROSSED_D_TERMINAL_OWNER_UNRESOLVED",
        "compile_exit": 0,
        "run_exit": 0,
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "lc9_advance": 2,
        "lc7_capture": 2,
        "mse3_push": 79,
        "mse3_pop": 71,
        "descriptor_datahub_writes": 32,
        "buffer_source_pushes": 53,
        "old_outbuffer_occupancy": "INVALIDATED_NOT_RTL_BUG",
    }
    manifest["superseded_v49_package"] = {
        "source_sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_TESTED_SUCCESSOR_V50",
    }
    manifest["observer_binding_four_way"]["source"].update(
        {
            "sha256": observer_sha,
            "size_bytes": (
                package / "tb_probe/native_return_observer.svh"
            ).stat().st_size,
        }
    )
    runtime = manifest["observer_binding_four_way"]["runtime_return"]
    for arg in [
        "+RETURN_OBS_DTERM_OWNER",
        "+RETURN_OBS_DTERM_OWNER_LIMIT=96",
    ]:
        if arg not in runtime["simulator_plusargs"]:
            runtime["simulator_plusargs"].append(arg)
    manifest["server_triggered_causal_observability"].update(
        {
            "exact_final_hdl_binding": True,
            "owner_clock": "u_NDP_Top_new.clk_db",
            "owner_reset": "u_NDP_Top_new.rst_n_db",
            "per_event_text_io": False,
            "full_wave_dump": False,
            "slowdown_is_blocking": False,
        }
    )
    manifest["cloud_rtl_authority"].update(
        {
            "approved_commit": RTL_COMMIT,
            "local_disk_commit": RTL_COMMIT,
            "identity_difference_blocks_compile_or_simulation": False,
        }
    )
    manifest["files"] = base.package_records(package)
    base.write_json(path, manifest)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(path, manifest)


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="node0004-v50-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    patch_runner(package)
    patch_runtime_feature_contract(package)
    observer_sha = patch_observer(package)
    provenance = write_provenance(package)
    (package / "README.md").write_text(
        "# node0004 v50 D-terminal owner diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v49 proved LC9 globally advances into LC7 and MSE3, and proved 32 "
        "descriptor/data writes. It did not identify why GROUP4 continues "
        "after descriptor terminal without last-index-zero. v50 adds one "
        "triggered owner-chain observer for LC13/14/15/9, GROUP4 row/column, "
        "Buffer_AG selected terminal, and descriptor lifetime. Numeric, W3, "
        "config, workload, timeout, backpressure and functional RTL are "
        "byte-frozen.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, observer_sha, provenance)
    receipt = base.observer_precompile_receipt(package, observer_sha)
    if not receipt["valid"]:
        raise BuildError(f"observer static gate failed: {receipt['errors']}")
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL_NAME,
        output / f"{INSTALL_NAME}.zip",
        output / f"{INSTALL_NAME}.zip.sha256",
        output / f"{INSTALL_NAME}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v50 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v50-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v50 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v49-return-v50-dterm-owner-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v49_sha256": SOURCE_SHA256,
        "bound_v49_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_SHA256,
        "current_common_rule_sha256": COMMON_SHA256,
        "builder_plan_mutable_provenance_sha256": PLAN_SHA256,
        "cloud_rtl_authority_commit": RTL_COMMIT,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(output / f"{INSTALL_NAME}.validation.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
