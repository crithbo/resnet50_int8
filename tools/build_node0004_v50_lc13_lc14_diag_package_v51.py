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
SOURCE_NAME = "r5_n4_hw_v50_dterm_owner_diag"
INSTALL_NAME = "r5_n4_hw_v51_lc13_lc14_diag"
SOURCE_SHA256 = "c8a809f8ebb723c286b5c0190bcd1142f9ba2d8965731b8ee194182c0922c830"
RETURN_SHA256 = "5401413f1586e8b7de4ad6ed2be2f8b2a0b4eea5072a80349b5b3217601e9d8a"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
AGENT_SHA256 = "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
PLAN_SHA256 = "43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70"
INDEX_SHA256 = "37f75653e2c5c167a6fb5d178785b9d3f3a3262b78cddf19d34663418c179e88"
SERVER_SHA256 = "755672c11626accf38160ddd5e2959cdf8949c0b4483f1243ff6b3a3bdb0ad8c"
COMMON_SHA256 = "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1"
NDP_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
INT8_SA_SHA256 = "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
README_SHA256 = "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v50_return_analysis/v51_build"


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


def lc(index: int, leaf: str) -> str:
    return iga(f"IGA_LC[{index}].u_IGA_LC.{leaf}")


def lc13_lc14_observer_block() -> str:
    lc13 = lambda leaf: lc(13, leaf)
    lc14 = lambda leaf: lc(14, leaf)
    lc15 = lambda leaf: lc(15, leaf)
    return f'''

    // v51 LC13_LC14_ACTUAL_CONSUMER_BEGIN
    // Qualified handshakes are progress. Held valid/full/empty/config levels
    // are state-only corroboration.
    bit return_obs_lx_enabled;
    integer return_obs_lx_limit;
    integer return_obs_lx_plusarg_status;
    integer return_obs_lx_records;
    longint unsigned return_obs_lx_13_out;
    longint unsigned return_obs_lx_14_capture;
    longint unsigned return_obs_lx_14_write;
    longint unsigned return_obs_lx_14_out;
    longint unsigned return_obs_lx_15_capture;
    longint unsigned return_obs_lx_15_out;
    longint unsigned return_obs_lx_14_same_suppress;
    bit return_obs_lx_seen_13_hold;
    bit return_obs_lx_seen_14_capture;
    bit return_obs_lx_seen_14_write;
    bit return_obs_lx_seen_14_out;
    bit return_obs_lx_seen_15_capture;
    bit return_obs_lx_seen_15_out;

    initial begin
        return_obs_lx_enabled = $test$plusargs("RETURN_OBS_LC13_LC14");
        return_obs_lx_limit = 128;
        return_obs_lx_plusarg_status = $value$plusargs(
            "RETURN_OBS_LC13_LC14_LIMIT=%d", return_obs_lx_limit
        );
        return_obs_lx_records = 0;
        return_obs_lx_13_out = 0;
        return_obs_lx_14_capture = 0;
        return_obs_lx_14_write = 0;
        return_obs_lx_14_out = 0;
        return_obs_lx_15_capture = 0;
        return_obs_lx_15_out = 0;
        return_obs_lx_14_same_suppress = 0;
        return_obs_lx_seen_13_hold = 0;
        return_obs_lx_seen_14_capture = 0;
        return_obs_lx_seen_14_write = 0;
        return_obs_lx_seen_14_out = 0;
        return_obs_lx_seen_15_capture = 0;
        return_obs_lx_seen_15_out = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_LC13_LC14 enabled=%0d limit_name=RETURN_OBS_LC13_LC14_LIMIT limit=%0d schema=LC13_LC14",
                return_obs_lx_enabled, return_obs_lx_limit
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit lx_13_out;
        bit lx_13_hold;
        bit lx_14_capture;
        bit lx_14_write;
        bit lx_14_out;
        bit lx_15_capture;
        bit lx_15_out;
        bit lx_14_same_suppress;
        bit lx_trigger;
        logic [22:0] lx_13_port;
        logic [22:0] lx_14_port;
        logic [22:0] lx_15_port;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_lx_records = 0;
            return_obs_lx_13_out = 0;
            return_obs_lx_14_capture = 0;
            return_obs_lx_14_write = 0;
            return_obs_lx_14_out = 0;
            return_obs_lx_15_capture = 0;
            return_obs_lx_15_out = 0;
            return_obs_lx_14_same_suppress = 0;
            return_obs_lx_seen_13_hold = 0;
            return_obs_lx_seen_14_capture = 0;
            return_obs_lx_seen_14_write = 0;
            return_obs_lx_seen_14_out = 0;
            return_obs_lx_seen_15_capture = 0;
            return_obs_lx_seen_15_out = 0;
        end else if (return_obs_lx_enabled && return_obs_active) begin
            lx_13_port = {iga('iga_lc_outport[13]')};
            lx_14_port = {iga('iga_lc_outport[14]')};
            lx_15_port = {iga('iga_lc_outport[15]')};
            lx_13_out = lx_13_port[22] && {lc13('iga_lc_connect2ob_bp_post')};
            lx_13_hold = lx_13_port[22] && !{lc13('iga_lc_connect2ob_bp_post')};
            lx_14_capture =
                {lc14('iga_lc_inport_tag[6]')} &&
                {lc14('u_IGA_LC_Inbuffer.iga_lc_same_gotten_mask')} &&
                {lc14('iga_lc_inbuffer_bp_pre')};
            lx_14_write =
                {lc14('u_IGA_LC_Counter.iga_lc_outbuf_wr_en')} &&
                !{lc14('u_IGA_LC_Counter.iga_lc_outbuf_full')};
            lx_14_out = lx_14_port[22] && {lc14('iga_lc_connect2ob_bp_post')};
            lx_15_capture =
                {lc15('iga_lc_inport_tag[6]')} &&
                {lc15('u_IGA_LC_Inbuffer.iga_lc_same_gotten_mask')} &&
                {lc15('iga_lc_inbuffer_bp_pre')};
            lx_15_out = lx_15_port[22] && {lc15('iga_lc_connect2ob_bp_post')};
            lx_14_same_suppress =
                {lc14('u_IGA_LC_Inbuffer.iga_lc_gotten_bit')} &&
                !{lc14('u_IGA_LC_Inbuffer.iga_lc_same_gotten_mask')} &&
                {lc14('iga_lc_inport_tag[6]')};

            if (lx_13_out) return_obs_lx_13_out++;
            if (lx_14_capture) return_obs_lx_14_capture++;
            if (lx_14_write) return_obs_lx_14_write++;
            if (lx_14_out) return_obs_lx_14_out++;
            if (lx_15_capture) return_obs_lx_15_capture++;
            if (lx_15_out) return_obs_lx_15_out++;
            if (lx_14_same_suppress) return_obs_lx_14_same_suppress++;

            lx_trigger =
                (lx_13_hold && !return_obs_lx_seen_13_hold) ||
                (lx_14_capture && !return_obs_lx_seen_14_capture) ||
                (lx_14_write && !return_obs_lx_seen_14_write) ||
                (lx_14_out && !return_obs_lx_seen_14_out) ||
                (lx_15_capture && !return_obs_lx_seen_15_capture) ||
                (lx_15_out && !return_obs_lx_seen_15_out) ||
                (lx_14_same_suppress && (return_obs_lx_14_same_suppress == 1));
            if (lx_trigger && return_obs_lx_records < return_obs_lx_limit &&
                return_obs_fd != 0) begin
                return_obs_lx_records++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | LC13_LC14_EDGE_V1 | n=%0d q13_out=%0d q13_hold=%0d q14_capture=%0d q14_write=%0d q14_out=%0d q15_capture=%0d q15_out=%0d q14_same_suppress=%0d lc13=%h lc14=%h lc15=%h bp13=%h src13=%0d src14=%0d src15=%0d ib14_valid=%0d ib14_last=%0d ib14_index=%0d ib14_bp=%0d cnt14_count=%0d cnt14_full=%0d cnt14_empty=%0d cnt14_wr=%0d cnt14_rd=%0d",
                    $time, return_obs_lx_records,
                    lx_13_out, lx_13_hold, lx_14_capture, lx_14_write,
                    lx_14_out, lx_15_capture, lx_15_out,
                    lx_14_same_suppress, lx_13_port, lx_14_port, lx_15_port,
                    {iga('iga_lc_outport_bp_post[13]')},
                    {lc13('iga_lc_src_id')}, {lc14('iga_lc_src_id')},
                    {lc15('iga_lc_src_id')},
                    {lc14('iga_lc_inbuffer_valid_bit')},
                    {lc14('iga_lc_inbuffer_last_bit')},
                    {lc14('iga_lc_inbuffer_last_index')},
                    {lc14('iga_lc_inbuffer_bp_pre')},
                    {lc14('u_IGA_LC_Counter.iga_lc_outbuf_count')},
                    {lc14('u_IGA_LC_Counter.iga_lc_outbuf_full')},
                    {lc14('u_IGA_LC_Counter.iga_lc_outbuf_empty')},
                    {lc14('u_IGA_LC_Counter.iga_lc_outbuf_wr_en')},
                    {lc14('u_IGA_LC_Counter.iga_lc_outbuf_rd_en')}
                );
                $fflush(return_obs_fd);
            end
            if (lx_13_hold) return_obs_lx_seen_13_hold = 1;
            if (lx_14_capture) return_obs_lx_seen_14_capture = 1;
            if (lx_14_write) return_obs_lx_seen_14_write = 1;
            if (lx_14_out) return_obs_lx_seen_14_out = 1;
            if (lx_15_capture) return_obs_lx_seen_15_capture = 1;
            if (lx_15_out) return_obs_lx_seen_15_out = 1;
        end
    end

    task automatic return_obs_write_lc13_lc14_state(input string event_name);
        if (return_obs_lx_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "%0t | LC13_LC14_BOUNDARY_V1 | event=%s q13_out=%0d q14_capture=%0d q14_write=%0d q14_out=%0d q15_capture=%0d q15_out=%0d q14_same_suppress=%0d lc13=%h lc14=%h lc15=%h bp13=%h cfg13=%0d,%0d,%0d,%0d,%0d,%0d cfg14=%0d,%0d,%0d,%0d,%0d,%0d cfg15=%0d,%0d,%0d,%0d,%0d,%0d ib14=%0d,%0d,%0d,%0d,%0d cnt14=%0d,%0d,%0d,%0d,%0d,%0d,%0d ib15=%0d,%0d,%0d,%0d cnt15=%0d,%0d,%0d",
                $time, event_name,
                return_obs_lx_13_out, return_obs_lx_14_capture,
                return_obs_lx_14_write, return_obs_lx_14_out,
                return_obs_lx_15_capture, return_obs_lx_15_out,
                return_obs_lx_14_same_suppress,
                {iga('iga_lc_outport[13]')},
                {iga('iga_lc_outport[14]')},
                {iga('iga_lc_outport[15]')},
                {iga('iga_lc_outport_bp_post[13]')},
                {lc13('iga_lc_enable')}, {lc13('iga_lc_src_id')},
                {lc13('iga_lc_outmost_loop')}, {lc13('iga_lc_initial_value')},
                {lc13('iga_lc_stride_value')}, {lc13('iga_lc_end_value')},
                {lc14('iga_lc_enable')}, {lc14('iga_lc_src_id')},
                {lc14('iga_lc_outmost_loop')}, {lc14('iga_lc_initial_value')},
                {lc14('iga_lc_stride_value')}, {lc14('iga_lc_end_value')},
                {lc15('iga_lc_enable')}, {lc15('iga_lc_src_id')},
                {lc15('iga_lc_outmost_loop')}, {lc15('iga_lc_initial_value')},
                {lc15('iga_lc_stride_value')}, {lc15('iga_lc_end_value')},
                {lc14('iga_lc_inport_tag')},
                {lc14('u_IGA_LC_Inbuffer.iga_lc_gotten_bit')},
                {lc14('u_IGA_LC_Inbuffer.iga_lc_same_gotten_mask')},
                {lc14('u_IGA_LC_Inbuffer.iga_lc_inport_valid_bit_masked')},
                {lc14('iga_lc_inbuffer_bp_pre')},
                {lc14('u_IGA_LC_Counter.iga_lc_outbuf_count')},
                {lc14('u_IGA_LC_Counter.iga_lc_outbuf_full')},
                {lc14('u_IGA_LC_Counter.iga_lc_outbuf_empty')},
                {lc14('u_IGA_LC_Counter.iga_lc_outbuf_wr_en')},
                {lc14('u_IGA_LC_Counter.iga_lc_outbuf_rd_en')},
                {lc14('u_IGA_LC_Counter.iga_lc_outbuf_wr_ptr')},
                {lc14('u_IGA_LC_Counter.iga_lc_outbuf_rd_ptr')},
                {lc15('iga_lc_inport_tag')},
                {lc15('u_IGA_LC_Inbuffer.iga_lc_gotten_bit')},
                {lc15('u_IGA_LC_Inbuffer.iga_lc_same_gotten_mask')},
                {lc15('iga_lc_inbuffer_bp_pre')},
                {lc15('u_IGA_LC_Counter.iga_lc_outbuf_count')},
                {lc15('u_IGA_LC_Counter.iga_lc_outbuf_full')},
                {lc15('u_IGA_LC_Counter.iga_lc_outbuf_empty')}
            );
            $fflush(return_obs_fd);
        end
    endtask
    // v51 LC13_LC14_ACTUAL_CONSUMER_END
'''


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "LC13_LC14_BOUNDARY_V1" in text:
        raise BuildError("LC13/LC14 observer already present")
    anchor = '                return_obs_write_dterm_owner_state("DIAG_DECISION");'
    if text.count(anchor) != 1:
        raise BuildError("v50 DTERM decision hook differs")
    text = text.replace(
        anchor,
        anchor
        + '\n                return_obs_write_lc13_lc14_state("DIAG_DECISION");',
        1,
    )
    path.write_text(
        text + lc13_lc14_observer_block(), encoding="utf-8", newline="\n"
    )
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    plusarg = "+RETURN_OBS_DTERM_OWNER_LIMIT=96"
    if text.count(plusarg) != 2:
        raise BuildError("v50 runner DTERM argv differs")
    text = text.replace(
        plusarg,
        plusarg + " +RETURN_OBS_LC13_LC14 +RETURN_OBS_LC13_LC14_LIMIT=128",
    )
    old = '''install_name="r5_n4_hw_v51_lc13_lc14_diag"
cfg_root="${server_root}/install/cfg_pkg/${install_name}"
run_root="${server_root}/run_${install_name}"
evidence_root="${server_root}/evidence_${install_name}"
return_dir="${server_root}/${install_name}_return"
return_zip="${return_dir}.zip"
return_sha="${return_zip}.sha256"
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
python3 "$runtime" path-budget --package-root "$package_root" --target-root "$server_root" || exit 8
for fresh in "$cfg_root" "$run_root" "$evidence_root" "$return_dir" "$return_zip" "$return_sha"; do
  [ ! -e "$fresh" ] || { echo "Fresh namespace required: $fresh" >&2; exit 4; }
done
mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$run_root/c0" "$evidence_root"'''
    new = '''install_name="r5_n4_hw_v51_lc13_lc14_diag"
result_root="/home/panqs/ndp/simresult"
return_zip="${result_root}/${install_name}_return.zip"
return_sha="${return_zip}.sha256"
launch_cwd="$(pwd -P)"
mkdir -p -- "$result_root" || exit 9
[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9
resolved_result_root="$(cd "$result_root" && pwd -P)" || exit 9
[ "$resolved_result_root" = "$result_root" ] || {
  echo "Fixed result root resolved differently: $resolved_result_root" >&2
  exit 9
}
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || {
  echo "Fixed result target conflict: $return_zip or $return_sha" >&2
  exit 10
}
work_root="${result_root}/.${install_name}.run.$$"
cfg_root="${work_root}/install/cfg_pkg/${install_name}"
run_root="${work_root}/run"
evidence_root="${work_root}/evidence"
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
python3 "$runtime" path-budget --package-root "$package_root" --target-root "$result_root" || exit 8
for fresh in "$work_root" "$cfg_root" "$run_root" "$evidence_root"; do
  [ ! -e "$fresh" ] || { echo "Fresh namespace required: $fresh" >&2; exit 4; }
done
for duplicate_root in "$server_root" "$package_root" "$launch_cwd"; do
  [ ! -e "$duplicate_root/${install_name}_return.zip" ] || exit 11
  [ ! -e "$duplicate_root/${install_name}_return.zip.sha256" ] || exit 11
done
mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$run_root/c0" "$evidence_root"
cat > "$evidence_root/publication_preflight.json" <<EOF
{
  "schema": "fixed-simresult-publication-preflight-v1",
  "result_root": "/home/panqs/ndp/simresult",
  "return_zip": "/home/panqs/ndp/simresult/${install_name}_return.zip",
  "return_sidecar": "/home/panqs/ndp/simresult/${install_name}_return.zip.sha256",
  "publication_state": "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
  "server_root_duplicate_absent": true,
  "package_root_duplicate_absent": true,
  "install_namespace_duplicate_absent": true,
  "run_root_duplicate_absent": true,
  "launch_cwd_duplicate_absent": true
}
EOF'''
    if text.count(old) != 1:
        raise BuildError("v50 runner path preamble differs")
    text = text.replace(old, new, 1)
    old_collect = (
        'python3 "$runtime" collect --server-root "$server_root"'
        '     --install-name "$install_name" --evidence-root "$evidence_root"'
        '     --run-root "$run_root"'
    )
    new_collect = (
        'python3 "$runtime" collect --server-root "$result_root"'
        '     --install-name "$install_name" --evidence-root "$evidence_root"'
        '     --run-root "$run_root"'
    )
    if text.count(old_collect) != 1:
        raise BuildError("v50 collector root differs")
    path.write_text(
        text.replace(old_collect, new_collect, 1),
        encoding="utf-8",
        newline="\n",
    )


def patch_runtime_feature_contract(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = '''    {
        "feature": "RETURN_OBS_DTERM_OWNER",
        "enable": "+RETURN_OBS_DTERM_OWNER",
        "limits": ("+RETURN_OBS_DTERM_OWNER_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_DTERM_OWNER", "enabled=1", "limit=96",
        ),
    },
)'''
    addition = '''    {
        "feature": "RETURN_OBS_DTERM_OWNER",
        "enable": "+RETURN_OBS_DTERM_OWNER",
        "limits": ("+RETURN_OBS_DTERM_OWNER_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_DTERM_OWNER", "enabled=1", "limit=96",
        ),
    },
    {
        "feature": "RETURN_OBS_LC13_LC14",
        "enable": "+RETURN_OBS_LC13_LC14",
        "limits": ("+RETURN_OBS_LC13_LC14_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_LC13_LC14", "enabled=1", "limit=128",
        ),
    },
)'''
    if text.count(anchor) != 1:
        raise BuildError("v50 feature contract differs")
    path.write_text(
        text.replace(anchor, addition, 1), encoding="utf-8", newline="\n"
    )


def patch_atomic_collector(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime_v7.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "import json\nimport shutil\n",
        "import json\nimport os\nimport shutil\n",
        1,
    ) if "import shutil\n" in text else text.replace(
        "import json\n", "import json\nimport os\nimport shutil\n", 1
    )
    begin = text.index("def collect(\n")
    end = text.index("\ndef main() -> int:", begin)
    replacement = r'''def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    fixed = Path("/home/panqs/ndp/simresult")
    if server_root != fixed:
        raise DiagnosticRuntimeError("fixed result root differs")
    final_zip = fixed / f"{install_name}_return.zip"
    final_sha = Path(str(final_zip) + ".sha256")
    if final_zip.exists() or final_sha.exists():
        raise DiagnosticRuntimeError("fixed result target conflict")
    stage_root = fixed / f".{install_name}.publish.{os.getpid()}"
    if stage_root.exists():
        raise DiagnosticRuntimeError("publication staging conflict")
    return_dir = stage_root / f"{install_name}_return"
    staged_zip = stage_root / f"{install_name}_return.zip"
    staged_sha = Path(str(staged_zip) + ".sha256")
    return_dir.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    items = (
        (evidence_root / "package_preflight.json", "evidence/package_preflight.json", True),
        (evidence_root / "install_preflight.json", "evidence/install_preflight.json", True),
        (evidence_root / "observer_precompile.json", "evidence/observer_precompile.json", True),
        (evidence_root / "compile_exit_status.txt", "evidence/compile_exit_status.txt", True),
        (evidence_root / "run_exit_status.txt", "evidence/run_exit_status.txt", True),
        (evidence_root / "SERVER_RESULT_GATE.json", "evidence/SERVER_RESULT_GATE.json", True),
        (evidence_root / "signal_status.txt", "evidence/signal_status.txt", False),
        (evidence_root / "diagnostic_feature_binding.json", "evidence/diagnostic_feature_binding.json", True),
        (evidence_root / "publication_preflight.json", "evidence/publication_preflight.json", True),
        (run_root / "compile/sim_results/compile_driver.log", "runs/compile/sim_results/compile_driver.log", False),
        (run_root / "compile/sim_results/compile.log", "runs/compile/sim_results/compile.log", False),
        (run_root / "c0/sim.log", "runs/c0/sim.log", False),
        (run_root / "c0/return_observer.log", "runs/c0/return_observer.log", False),
        (run_root / "c0/host_progress.log", "runs/c0/host_progress.log", False),
        (run_root / "c0/simulator_argv.txt", "runs/c0/simulator_argv.txt", False),
    )
    for source, relative, required in items:
        _copy_limited(
            source,
            return_dir / Path(*PurePosixPath(relative).parts),
            relative,
            records,
            required,
        )
    package_root = Path(__file__).resolve().parents[1]
    _copy_limited(
        package_root / "package_manifest.json",
        return_dir / "evidence/returned_package_manifest.json",
        "evidence/returned_package_manifest.json",
        records,
        True,
    )
    publication = json.loads(
        (evidence_root / "publication_preflight.json").read_text(encoding="utf-8")
    )
    if (
        publication.get("result_root") != str(fixed)
        or publication.get("return_zip") != str(final_zip)
        or publication.get("return_sidecar") != str(final_sha)
        or not all(
            publication.get(name) is True
            for name in (
                "server_root_duplicate_absent",
                "package_root_duplicate_absent",
                "install_namespace_duplicate_absent",
                "run_root_duplicate_absent",
                "launch_cwd_duplicate_absent",
            )
        )
    ):
        raise DiagnosticRuntimeError("fixed publication receipt differs")
    records.sort(key=lambda item: item["path"])
    publication_contract = {
        "result_root": str(fixed),
        "return_zip": str(final_zip),
        "return_sidecar": str(final_sha),
        "publication_state": "STAGING_VALIDATED_BEFORE_ATOMIC_RENAME",
        "target_sha256_source": "adjacent sidecar after archive finalization",
        "server_root_duplicate_absent": True,
        "package_root_duplicate_absent": True,
        "install_namespace_duplicate_absent": True,
        "run_root_duplicate_absent": True,
        "launch_cwd_duplicate_absent": True,
    }
    allowlist = {
        "schema": "node0004-hang-localization-return-allowlist-v8",
        "install_name": install_name,
        "fixed_result_publication": publication_contract,
        "records": records,
    }
    write_json(return_dir / "RETURN_ALLOWLIST.json", allowlist)
    package_manifest_path = package_root / "package_manifest.json"
    return_manifest = {
        "schema": "node0004-return-manifest-v25",
        "install_name": install_name,
        "fixed_result_publication": publication_contract,
        "source_package_manifest": {
            "returned_path": "evidence/returned_package_manifest.json",
            "size_bytes": package_manifest_path.stat().st_size,
            "sha256": sha256(package_manifest_path),
        },
        "return_allowlist": {
            "path": "RETURN_ALLOWLIST.json",
            "size_bytes": (return_dir / "RETURN_ALLOWLIST.json").stat().st_size,
            "sha256": sha256(return_dir / "RETURN_ALLOWLIST.json"),
        },
        "records": records,
    }
    write_json(return_dir / "RETURN_MANIFEST.json", return_manifest)
    with zipfile.ZipFile(
        staged_zip, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for item in sorted(p for p in return_dir.rglob("*") if p.is_file()):
            archive.write(item, item.relative_to(return_dir.parent).as_posix())
    with zipfile.ZipFile(staged_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise DiagnosticRuntimeError(f"staged return CRC failure: {bad}")
    digest = sha256(staged_zip)
    staged_sha.write_text(
        f"{digest}  {final_zip.name}\n", encoding="ascii", newline="\n"
    )
    sidecar = staged_sha.read_text(encoding="ascii").split()
    if len(sidecar) != 2 or sidecar[0] != digest or sidecar[1] != final_zip.name:
        raise DiagnosticRuntimeError("staged sidecar differs")
    if final_zip.exists() or final_sha.exists():
        raise DiagnosticRuntimeError("fixed result target conflict before publish")
    os.replace(staged_zip, final_zip)
    os.replace(staged_sha, final_sha)
    if sha256(final_zip) != digest:
        raise DiagnosticRuntimeError("published return SHA differs")
    published_sidecar = final_sha.read_text(encoding="ascii").split()
    if (
        len(published_sidecar) != 2
        or published_sidecar[0] != digest
        or published_sidecar[1] != final_zip.name
    ):
        raise DiagnosticRuntimeError("published sidecar differs")
    shutil.rmtree(return_dir)
    stage_root.rmdir()
    return {
        "zip": str(final_zip),
        "sidecar": str(final_sha),
        "sha256": digest,
        "publication_state": "ATOMIC_PUBLISHED_VERIFIED",
        "duplicate_absent": True,
        "allowlisted_file_count": len(records) + 1,
    }
'''
    path.write_text(
        text[:begin] + replacement + text[end:],
        encoding="utf-8",
        newline="\n",
    )
    top_path = package / "package_tools/node0004_hang_localization_runtime.py"
    top = top_path.read_text(encoding="utf-8")
    if top.count('"node0004-return-manifest-v24"') != 1:
        raise BuildError("top-level return-manifest schema gate differs")
    top_path.write_text(
        top.replace(
            '"node0004-return-manifest-v24"',
            '"node0004-return-manifest-v25"',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )


def write_provenance(package: Path) -> Path:
    path = package / "provenance/v50_return_v51_lc13_lc14_diag.json"
    base.write_json(
        path,
        {
            "schema": "node0004-v50-return-v51-lc13-lc14-diag-v1",
            "bound_return_sha256": RETURN_SHA256,
            "source_v50_sha256": SOURCE_SHA256,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "last_proven_good": (
                "LC9_ACCEPTS_TRUE_LAST_INDEX0_AND_D_WRITES_32_DESCRIPTORS_"
                "WHILE_LC13_RELEASES_FIRST_NONTERMINAL_VALUE"
            ),
            "first_divergence": (
                "LC13_SECOND_OR_TERMINAL_VALUE_NOT_GLOBALLY_ACCEPTED_"
                "AND_LC14_LC15_NEVER_RELEASE"
            ),
            "candidate_observation_matrix": {
                "LC13_DOWNSTREAM_BACKPRESSURE": [
                    "LC13 held valid",
                    "exact LC13 destination ready vector",
                ],
                "LC14_SOURCE_OR_SAME_GOTTEN_SUPPRESSION": [
                    "LC14 src_id/config",
                    "selected input tag",
                    "gotten/same mask/masked valid",
                    "qualified capture",
                ],
                "LC14_COUNTER_NO_RELEASE": [
                    "qualified counter write",
                    "count/full/empty/pointers",
                    "qualified LC14 output",
                ],
                "LC13_LOCAL_TERMINAL_FAILURE": [
                    "LC13 config values",
                    "LC13 held/output tag",
                    "qualified LC13 output count",
                ],
                "LC14_TO_LC15_BACKPRESSURE": [
                    "LC15 selected capture",
                    "LC15 counter state",
                    "qualified LC15 output",
                ],
            },
            "fixed_server_result_root": "/home/panqs/ndp/simresult",
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
            "schema": "resnet50-node0004-lc13-lc14-package-v51",
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
        if item.get("reason") == "server package routing":
            item["sha256"] = INDEX_SHA256
        elif item.get("reason") == "common server package gates":
            item["sha256"] = SERVER_SHA256
        elif item.get("reason") == "Conv INT8 SA accumulate release gate":
            item["sha256"] = INT8_SA_SHA256
        elif item.get("reason") == "active server entry":
            item["sha256"] = README_SHA256
    for rule_id in [
        "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
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
        if row["gate_id"] == "PACKAGE_BOOTSTRAP_PATH_RUNTIME_D":
            row.update(
                {
                    "applicability": "blocking_applicable",
                    "reason": "v51 changes return publication to fixed atomic simresult",
                    "changed_surface": [
                        "PREPARE_AND_RUN.sh fixed result root/finalizer",
                        "runtime_v7 atomic collector",
                    ],
                    "evidence": [
                        "exact runner fixed-target parse",
                        "isolated publication harness normal/compile-fail/INT/TERM",
                        "conflict/rewrite/sidecar/duplicate negatives",
                    ],
                    "blocking": True,
                }
            )
        elif row["gate_id"] == "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL":
            row.update(
                {
                    "applicability": "blocking_applicable",
                    "reason": "v51 adds LC13/LC14 actual consumers",
                    "changed_surface": [
                        "native_return_observer.svh LC13_LC14 span"
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
                    "reason": "new LC13/LC14 qualified predicate slice",
                    "changed_surface": [
                        "LC13_LC14_EDGE_V1",
                        "LC13_LC14_BOUNDARY_V1",
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
                    "reason": "runtime/config/bitstream bytes frozen",
                    "changed_surface": [],
                    "evidence": ["source-successor runtime byte equality"],
                    "blocking": False,
                }
            )
    feature = {
        "feature": "RETURN_OBS_LC13_LC14",
        "runtime_enable_parameter": "+RETURN_OBS_LC13_LC14",
        "limit_or_budget_parameters": ["+RETURN_OBS_LC13_LC14_LIMIT=128"],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 "
            "feature=RETURN_OBS_LC13_LC14 enabled=1 "
            "limit_name=RETURN_OBS_LC13_LC14_LIMIT limit=128 "
            "schema=LC13_LC14"
        ),
        "expected_record_schema": "LC13_LC14_BOUNDARY_V1",
        "edge_record_schema": "LC13_LC14_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
    }
    manifest["diagnostic_feature_runtime_binding"]["features"].append(feature)
    manifest["lc13_lc14_diagnostic"] = {
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
    manifest["fixed_server_result_publication"] = {
        "result_root": "/home/panqs/ndp/simresult",
        "return_zip": (
            f"/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip"
        ),
        "return_sidecar": (
            f"/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip.sha256"
        ),
        "configurable": False,
        "shared_exactly_once_finalizer": True,
        "atomic_hidden_staging": True,
        "target_conflict_fail_closed": True,
        "local_workspace_mapping_forbidden": True,
    }
    manifest["v50_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "LC13_TO_LC14_BOUNDARY_UNRESOLVED",
        "user_attested_run_completed": True,
        "compile_exit": 0,
        "run_exit": 0,
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "lc9_true_last0_accepted": 1,
        "lc13_qualified_output": 1,
        "lc14_qualified_output": 0,
        "lc15_qualified_output": 0,
        "old_outbuffer_occupancy": "INVALIDATED_NOT_RTL_BUG",
    }
    manifest["superseded_v50_package"] = {
        "source_sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_TESTED_SUCCESSOR_V51",
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
        "+RETURN_OBS_LC13_LC14",
        "+RETURN_OBS_LC13_LC14_LIMIT=128",
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
    patch_atomic_collector(package)
    observer_sha = patch_observer(package)
    provenance = write_provenance(package)
    (package / "README.md").write_text(
        "# node0004 v51 LC13-to-LC14 diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v50 proved LC9 accepts true last-index-zero and 32 descriptor/data "
        "writes complete, while LC13 advances once and LC14/LC15 never "
        "release. v51 adds one qualified LC13-to-LC15 causal slice covering "
        "downstream ready, selected source, same-gotten masking, counter "
        "write/read/occupancy and first outputs. Numeric, W3, "
        "config, workload, timeout, backpressure and functional RTL are "
        "byte-frozen. Server return is atomically published only under "
        "`/home/panqs/ndp/simresult`.\n\n"
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
        raise BuildError("refusing to overwrite existing v51 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v51-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v51 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v50-return-v51-lc13-lc14-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v50_sha256": SOURCE_SHA256,
        "bound_v50_return_sha256": RETURN_SHA256,
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
