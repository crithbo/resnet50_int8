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

import tools.build_node0004_v33_rowlc4_bufag_diag_package_v34 as previous  # noqa: E402


base = previous.base
SOURCE_NAME = "r5_n4_hw_v35_rowlc4_bufag_diag"
INSTALL_NAME = "r5_n4_hw_v36_b5rd_diag"
SOURCE_SHA256 = "af9f94d12275e9b5e9b138101354811bf5fdc4c7a5f4b3ef32cf7d94dd5f90cd"
RETURN_SHA256 = "e8c6496c95ae618d6f85c8c89f6ca3a0f17659cbe925857d71c545d5187a84ba"
RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
RTL_SYNC_REPORT = ROOT / "artifacts/rtl_sync/trassic_master_e1fb0f7_20260804/report.json"
RTL_SYNC_REPORT_SHA256 = "c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c"
AGENT_SHA256 = "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
PLAN_MUTABLE_SHA256 = "d9d63138769fea2cb26e70da9350bbcd2ea16dd4fcb15d74d21c5e194e56ca2e"
INDEX_SHA256 = "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2"
SERVER_RULE_SHA256 = "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1"
README_SHA256 = "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
RTL_LEAVES = (
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Connect.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster_Connect.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Memory_Req_Manager.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
)
KEPT_FEATURES = (
    "RETURN_HANG_DIAG",
    "RETURN_OBS_MSE4_DESCRIPTOR",
    "RETURN_OBS_MSE4_INDEX",
    "RETURN_OBS_LC18_PE7",
    "RETURN_OBS_ROWLC4_BUFAG",
    "RETURN_OBS_B5RD",
)


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v35 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v35 source CRC failed")
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
            raise BuildError(f"v35 root differs: {sorted(roots)}")
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


def lsu(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU"
        f".{leaf}"
    )


def stream(leaf: str) -> str:
    return lsu(f"u_Stream_Engine.{leaf}")


def mse4(leaf: str) -> str:
    return stream(
        "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine." + leaf
    )


def cluster(leaf: str) -> str:
    return lsu(f"u_Buffer_Manager_Cluster.{leaf}")


def bm5(leaf: str) -> str:
    return cluster(f"BUFFER_MANAGER[5].u_Buffer_Manager.{leaf}")


def buf5(leaf: str) -> str:
    return bm5(f"u_Buffer.{leaf}")


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "B5RD_BOUNDARY_V1" in text:
        raise BuildError("v36 Buffer5 read diagnostic already present")

    # v35 incorrectly treated a sustained comparator level as one transaction
    # per cycle. Qualify it as a rising witness.
    decl = "    longint unsigned return_obs_rb_rd_read;\n"
    if text.count(decl) != 1:
        raise BuildError("v35 match-prev declaration anchor differs")
    text = text.replace(
        decl,
        decl + "    bit return_obs_rb_buf_match_prev;\n",
        1,
    )
    init = "        return_obs_rb_rd_read = 0;\n"
    if text.count(init) != 2:
        raise BuildError("v35 match-prev init/reset anchor differs")
    text = text.replace(
        init,
        init + "        return_obs_rb_buf_match_prev = 0;\n",
    )
    old_match = (
        "            rb_buf_match = "
        f"{mse4('u_Buffer_AG_Idx_Queue.buf_all_idx_matched')};"
    )
    new_match = (
        "            rb_buf_match = "
        f"{mse4('u_Buffer_AG_Idx_Queue.buf_all_idx_matched')} &&\n"
        "                !return_obs_rb_buf_match_prev;\n"
        "            return_obs_rb_buf_match_prev = "
        f"{mse4('u_Buffer_AG_Idx_Queue.buf_all_idx_matched')};"
    )
    if text.count(old_match) != 1:
        raise BuildError("v35 match qualifier anchor differs")
    text = text.replace(old_match, new_match, 1)

    # v35 decision snapshots were accidentally children of the disabled
    # FINAL_RELEASE feature. Bind required snapshots directly to canonical.
    canonical = '                return_obs_write_final_release_state("DIAG_DECISION");'
    if text.count(canonical) != 1:
        raise BuildError("canonical snapshot anchor differs")
    text = text.replace(
        canonical,
        canonical
        + '\n                return_obs_write_rowlc4_bufag_state("DIAG_DECISION");'
        + '\n                return_obs_write_b5rd_state("DIAG_DECISION");',
        1,
    )

    block = f'''

    // v36: qualified Buffer5 read-request and return-path discriminator.
    bit return_obs_b5_enabled;
    integer return_obs_b5_limit;
    integer return_obs_b5_plusarg_status;
    integer return_obs_b5_records;
    longint unsigned return_obs_b5_rd_req_accept;
    longint unsigned return_obs_b5_cluster_accept;
    longint unsigned return_obs_b5_buffer_accept;
    longint unsigned return_obs_b5_rvalid_rise;
    longint unsigned return_obs_b5_rd_pop;
    logic [9:0] return_obs_b5_prev_state;

    initial begin
        return_obs_b5_enabled = $test$plusargs("RETURN_OBS_B5RD");
        return_obs_b5_limit = 96;
        return_obs_b5_plusarg_status = $value$plusargs(
            "RETURN_OBS_B5RD_LIMIT=%d", return_obs_b5_limit
        );
        return_obs_b5_records = 0;
        return_obs_b5_rd_req_accept = 0;
        return_obs_b5_cluster_accept = 0;
        return_obs_b5_buffer_accept = 0;
        return_obs_b5_rvalid_rise = 0;
        return_obs_b5_rd_pop = 0;
        return_obs_b5_prev_state = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_B5RD enabled=%0d limit_name=RETURN_OBS_B5RD_LIMIT limit=%0d",
                return_obs_b5_enabled, return_obs_b5_limit);
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit b5_rd_req_valid;
        bit b5_selected_ready;
        bit b5_cluster_valid;
        bit b5_cluster_ready;
        bit b5_mrm_valid;
        bit b5_bank_ready;
        bit b5_buffer_ready;
        bit b5_rvalid;
        bit b5_rd_pop_now;
        bit b5_rd_req_accept_now;
        bit b5_cluster_accept_now;
        bit b5_buffer_accept_now;
        bit b5_rvalid_rise_now;
        logic [9:0] b5_state;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_b5_records = 0;
            return_obs_b5_rd_req_accept = 0;
            return_obs_b5_cluster_accept = 0;
            return_obs_b5_buffer_accept = 0;
            return_obs_b5_rvalid_rise = 0;
            return_obs_b5_rd_pop = 0;
            return_obs_b5_prev_state = 0;
        end else if (return_obs_b5_enabled && return_obs_active) begin
            b5_rd_req_valid = |{stream('mse2buf_rreq_valid[0]')};
            b5_selected_ready = {stream('buf2mse_rreq_ready[0]')};
            b5_cluster_valid = |{cluster('se2mrm_req_valid[5]')};
            b5_cluster_ready = {cluster('mrm2se_req_ready[5]')};
            b5_mrm_valid = |{bm5('mrm2buf_req_valid')};
            b5_bank_ready = &{buf5('buf2mrm_rreq_bank_ready')};
            b5_buffer_ready = {buf5('buf2mrm_rreq_ready')};
            b5_rvalid = {cluster('mrm2se_rvalid[5]')};
            b5_rd_pop_now = {mse4('u_RD_Buffer_AG.buf_ag_ob_rd_en')} &&
                            !{mse4('u_RD_Buffer_AG.buf_ag_ob_empty')};
            b5_rd_req_accept_now = b5_rd_req_valid && b5_selected_ready;
            b5_cluster_accept_now = b5_cluster_valid && b5_cluster_ready;
            b5_buffer_accept_now =
                (|{buf5('mrm2buf_rd_en')}) && b5_buffer_ready;
            b5_rvalid_rise_now = b5_rvalid && !return_obs_b5_prev_state[8];
            b5_state = {{
                b5_rd_pop_now, b5_rvalid, b5_buffer_ready, b5_bank_ready,
                b5_mrm_valid, b5_cluster_ready, b5_cluster_valid,
                b5_selected_ready, {stream('mse_wreq_pingpong_sel[0]')},
                b5_rd_req_valid
            }};
            if (b5_rd_req_accept_now) return_obs_b5_rd_req_accept++;
            if (b5_cluster_accept_now) return_obs_b5_cluster_accept++;
            if (b5_buffer_accept_now) return_obs_b5_buffer_accept++;
            if (b5_rvalid_rise_now) return_obs_b5_rvalid_rise++;
            if (b5_rd_pop_now) return_obs_b5_rd_pop++;
            if (return_obs_b5_records < return_obs_b5_limit &&
                (b5_state != return_obs_b5_prev_state ||
                 b5_rd_req_accept_now || b5_cluster_accept_now ||
                 b5_buffer_accept_now || b5_rvalid_rise_now ||
                 b5_rd_pop_now)) begin
                $fdisplay(return_obs_fd,
                    "%0t | B5RD_EDGE_V1 | n=%0d q=0x%0h state=0x%0h rd_valid=0x%0h pingpong=%0d selected_ready=%0d cluster_valid=0x%0h cluster_ready=%0d mrm_valid=0x%0h mrm_strb=0x%0h req_addr=0x%0h bank_ready=0x%0h buffer_ready=%0d rd_en=0x%0h rvalid=%0d rd_count=%0d rd_full=%0d rd_empty=%0d",
                    $time, return_obs_b5_records + 1,
                    {{b5_rd_pop_now, b5_rvalid_rise_now,
                      b5_buffer_accept_now, b5_cluster_accept_now,
                      b5_rd_req_accept_now}},
                    b5_state, {stream('mse2buf_rreq_valid[0]')},
                    {stream('mse_wreq_pingpong_sel[0]')},
                    b5_selected_ready, {cluster('se2mrm_req_valid[5]')},
                    b5_cluster_ready, {bm5('mrm2buf_req_valid')},
                    {bm5('mrm2buf_req_strb')}, {bm5('mrm2buf_req_addr')},
                    {buf5('buf2mrm_rreq_bank_ready')}, b5_buffer_ready,
                    {buf5('mrm2buf_rd_en')}, b5_rvalid,
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_cnt')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_full')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_empty')});
                return_obs_b5_records++;
                $fflush(return_obs_fd);
            end
            return_obs_b5_prev_state = b5_state;
        end
    end

    task automatic return_obs_write_b5rd_state(input string event_name);
        begin
            if (return_obs_b5_enabled && return_obs_fd != 0) begin
                $fdisplay(return_obs_fd,
                    "%0t | B5RD_BOUNDARY_V1 | event=%s rd_req_accept=%0d cluster_accept=%0d buffer_accept=%0d rvalid_rise=%0d rd_pop=%0d state=0x%0h rd_valid=0x%0h pingpong=%0d selected_ready=%0d cluster_valid=0x%0h cluster_ready=%0d mrm_valid=0x%0h mrm_strb=0x%0h req_addr=0x%0h bank_ready=0x%0h buffer_ready=%0d rd_en=0x%0h rvalid=%0d rd_count=%0d rd_full=%0d rd_empty=%0d",
                    $time, event_name, return_obs_b5_rd_req_accept,
                    return_obs_b5_cluster_accept,
                    return_obs_b5_buffer_accept,
                    return_obs_b5_rvalid_rise, return_obs_b5_rd_pop,
                    return_obs_b5_prev_state,
                    {stream('mse2buf_rreq_valid[0]')},
                    {stream('mse_wreq_pingpong_sel[0]')},
                    {stream('buf2mse_rreq_ready[0]')},
                    {cluster('se2mrm_req_valid[5]')},
                    {cluster('mrm2se_req_ready[5]')},
                    {bm5('mrm2buf_req_valid')}, {bm5('mrm2buf_req_strb')},
                    {bm5('mrm2buf_req_addr')},
                    {buf5('buf2mrm_rreq_bank_ready')},
                    {buf5('buf2mrm_rreq_ready')},
                    {buf5('mrm2buf_rd_en')},
                    {cluster('mrm2se_rvalid[5]')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_cnt')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_full')},
                    {mse4('u_RD_Buffer_AG.buf_ag_ob_empty')});
                $fflush(return_obs_fd);
            end
        end
    endtask
'''
    path.write_text(text + block, encoding="utf-8", newline="\n")
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    identity = f'install_name="{INSTALL_NAME}"'
    if text.count(identity) != 1:
        raise BuildError("runner identity replacement differs")
    tool_anchor = (
        'for tool in python3 timeout make; do command -v "$tool" '
        ">/dev/null 2>&1 || exit 3; done"
    )
    if text.count(tool_anchor) != 1:
        raise BuildError("path-guard anchor differs")
    text = text.replace(
        tool_anchor,
        tool_anchor
        + '\npython3 "$runtime" path-budget --package-root "$package_root" '
        '--target-root "$server_root" || exit 8',
        1,
    )
    token = "+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128"
    if text.count(token) != 2:
        raise BuildError("B5RD runner anchor differs")
    text = text.replace(
        token, token + " +RETURN_OBS_B5RD +RETURN_OBS_B5RD_LIMIT=96"
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    feature_anchor = '''    {
        "feature": "RETURN_OBS_ROWLC4_BUFAG",
        "enable": "+RETURN_OBS_ROWLC4_BUFAG",
        "limits": ("+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_ROWLC4_BUFAG", "enabled=1", "limit=128",
        ),
    },
)'''
    feature_replacement = feature_anchor[:-2] + '''    {
        "feature": "RETURN_OBS_B5RD",
        "enable": "+RETURN_OBS_B5RD",
        "limits": ("+RETURN_OBS_B5RD_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_B5RD", "enabled=1", "limit=96",
        ),
    },
)'''
    if text.count(feature_anchor) != 1:
        raise BuildError("runtime feature anchor differs")
    text = text.replace(feature_anchor, feature_replacement, 1)
    old_tail = '''if __name__ == "__main__":
    raise SystemExit(main())
'''
    new_tail = '''def path_budget_main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--target-root", required=True, type=Path)
    args = parser.parse_args(sys.argv[2:])
    manifest = json.loads(
        (args.package_root / "package_manifest.json").read_text(encoding="utf-8")
    )
    budget = manifest["path_length_budget"]
    longest = budget["longest_projected_relative_path"]
    projected = len(str(args.target_root.resolve())) + 1 + len(longest)
    value = {
        "schema": "package-path-budget-runtime-v1",
        "valid": projected <= budget["max_projected_absolute_path_chars"],
        "target_root_chars": len(str(args.target_root.resolve())),
        "longest_projected_relative_path": longest,
        "projected_absolute_path_chars": projected,
        "limit": budget["max_projected_absolute_path_chars"],
    }
    print(json.dumps(value, sort_keys=True))
    return 0 if value["valid"] else 9


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "path-budget":
        raise SystemExit(path_budget_main())
    raise SystemExit(main())
'''
    if text.count(old_tail) != 1:
        raise BuildError("runtime main anchor differs")
    path.write_text(
        text.replace(old_tail, new_tail, 1),
        encoding="utf-8",
        newline="\n",
    )


def rtl_binding() -> dict[str, Any]:
    if base.sha256(RTL_SYNC_REPORT) != RTL_SYNC_REPORT_SHA256:
        raise BuildError("e1fb RTL sync report SHA differs")
    leaves = []
    for relative in RTL_LEAVES:
        path = ROOT / relative
        leaves.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": base.sha256(path),
            }
        )
    return {
        "schema": "node0004-v36-current-local-rtl-binding-v1",
        "current_local_rtl_commit": RTL_COMMIT,
        "sync_report_path": str(RTL_SYNC_REPORT.relative_to(ROOT)).replace("\\", "/"),
        "sync_report_sha256": RTL_SYNC_REPORT_SHA256,
        "focused_direct_consumers": leaves,
        "server_runtime_source_preflight": False,
        "server_actual_compile_commit_required_in_return": True,
        "claim_boundary": (
            "local successor build identity plus user-attested server baseline; "
            "formal return actual compile identity remains required for E3/E4/E5"
        ),
    }


def path_budget(package: Path) -> dict[str, Any]:
    members = [
        str(path.relative_to(package)).replace("\\", "/")
        for path in package.rglob("*")
        if path.is_file()
    ]
    longest_inner = max(members, key=len)
    projected = [
        f"install/cfg_pkg/{INSTALL_NAME}/{member}" for member in members
    ] + [
        f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
        f"evidence_{INSTALL_NAME}/SERVER_RESULT_GATE.json",
        f"{INSTALL_NAME}_return/runs/c0/return_observer.log",
    ]
    longest_projected = max(projected, key=len)
    max_component = max(len(part) for member in members for part in member.split("/"))
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": 96,
        "max_projected_absolute_path_chars": 240,
        "max_zip_member_chars": len(INSTALL_NAME) + 1 + len(longest_inner),
        "max_inner_suffix_chars": len(longest_inner),
        "max_inner_depth": max(member.count("/") + 1 for member in members),
        "max_inner_component_chars": max_component,
        "longest_inner_member": longest_inner,
        "longest_projected_relative_path": longest_projected,
        "declared_worst_projected_absolute_chars": 96 + 1 + len(longest_projected),
        "abbreviation_map": {
            "workload/runtime/runs/c0": "frozen canonical ABI; already <= budget",
            "tb_probe": "observer source",
            "package_tools": "runner support ABI",
            "provenance": "machine receipts",
        },
        "exceptions": [
            {
                "component": "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin",
                "chars": 53,
                "reason": "frozen canonical tool leaf; parents are compact and total suffix is 94",
            }
        ],
        "pass": (
            len(longest_inner) <= 128
            and max(member.count("/") + 1 for member in members) <= 8
            and 96 + 1 + len(longest_projected) <= 240
        ),
    }


def execution_reduction() -> dict[str, Any]:
    return {
        "schema": "node0004-v36-diagnostic-execution-reduction-v1",
        "rule_id": "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
        "causal_slice": (
            "frozen c0 cumulative prefix through ROW/COL, Buffer_AG, "
            "RD_Buffer_AG and selected Buffer5 read-return path"
        ),
        "kept": {
            "stages": ["c0"],
            "payload": ["all 86 frozen c0 input leaves"],
            "readback": ["frozen formal-D contract"],
            "observer_features": list(KEPT_FEATURES),
        },
        "dropped": {
            "stages": [],
            "payload": [],
            "readback": [],
            "observer_runtime_features": [
                "RETURN_OBS_DEEP",
                "RETURN_OBS_ABPE",
                "RETURN_OBS_FINAL_RELEASE",
                "RETURN_OBS_DWRITE_PATH",
                "RETURN_OBS_DATAHUB_DRAIN",
            ],
        },
        "why_stage_payload_not_reduced": (
            "RD_Buffer_AG full state depends on the accumulated c0 prefix. No "
            "approved byte-exact internal checkpoint exists; host replay is forbidden."
        ),
        "candidate_observation_matrix": {
            "WRONG_MSE_PINGPONG_SELECTION": [
                "rd request valid",
                "pingpong selector",
                "selected ready",
            ],
            "STREAM_ENGINE_CLUSTER_MAPPING": [
                "selected Buffer5 request",
                "se2mrm_req_valid[5]",
                "mrm2se_req_ready[5]",
            ],
            "BUFFER5_MRM_DECODE_OR_READY": [
                "cluster accept",
                "mrm2buf_req_valid/strb/address",
                "buffer ready",
            ],
            "BUFFER5_VALID_BANK_OR_ADDRESS": [
                "mrm2buf read enable",
                "per-bank valid readiness",
                "request address",
            ],
            "BUFFER5_READ_RETURN": [
                "buffer accept",
                "mrm2se_rvalid",
                "RD_Buffer_AG pop",
            ],
        },
        "claim_boundary": (
            "diagnostic localization only; E4/E5 still require natural terminal "
            "and complete formal D"
        ),
    }


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v36-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    binding = rtl_binding()
    reduction = execution_reduction()
    provenance = package / "provenance"
    for stale in (
        provenance / "current_local_rtl_binding.json",
        provenance / "v35_diagnostic_execution_reduction.json",
    ):
        if not stale.is_file():
            raise BuildError(f"expected v35 provenance leaf missing: {stale.name}")
        stale.unlink()
    base.write_json(provenance / "rtl_e1fb.json", binding)
    base.write_json(provenance / "diag_reduction_v36.json", reduction)
    (package / "README.md").write_text(
        f"# node0004 v36 Buffer5 read-path diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v35 proved ROW/COL and Buffer_AG progress and two RD_Buffer_AG writes, "
        "then RD_Buffer_AG full with zero reads. v36 fixes the v35 observer's "
        "level-event and snapshot-gating errors and observes the complete selected "
        "Buffer5 read request/ready/return chain using qualified handshakes and "
        "change witnesses. Numeric, workload, config, golden, timeout, "
        "backpressure and functional RTL are unchanged.\n\n"
        f"Current local RTL binding: `{RTL_COMMIT}`.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-buffer5-read-diagnostic-package-v36",
            "install_name": INSTALL_NAME,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    receipts["agent_sha256"] = AGENT_SHA256
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    updates = {
        ".agents/agent.md": AGENT_SHA256,
        ".agents/plan.md": PLAN_MUTABLE_SHA256,
        ".agents/rules/生成前必读索引.md": INDEX_SHA256,
        ".agents/rules/服务器测试包生成规则.md": SERVER_RULE_SHA256,
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": README_SHA256,
    }
    for receipt in receipts["generation_read_receipt"]:
        if receipt.get("path") in updates:
            receipt["sha256"] = updates[receipt["path"]]
    for rule in (
        "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
        "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
        "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
    ):
        if rule not in receipts["rules"]:
            receipts["rules"].append(rule)
    manifest["v35_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE_WITH_REFINED_DUT_BOUNDARY",
        "last_proven_good": (
            "ROW_LC4_AND_COL_LC4_QUALIFIED_PROGRESS_THROUGH_BUFFER_AG_"
            "QUEUE_PUSH_POP_AND_TWO_RD_BUFFER_AG_WRITES"
        ),
        "first_divergence": (
            "RD_BUFFER_AG_FULL_AFTER_TWO_WRITES_WITH_ZERO_READ_ACCEPTS"
        ),
        "observer_defects_fixed": [
            "buf_match sustained level no longer counts once per cycle",
            "decision snapshots no longer depend on disabled FINAL_RELEASE feature",
        ],
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
    }
    b5_feature = {
        "feature": "RETURN_OBS_B5RD",
        "runtime_enable_parameter": "+RETURN_OBS_B5RD",
        "limit_or_budget_parameters": ["+RETURN_OBS_B5RD_LIMIT=96"],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 feature=RETURN_OBS_B5RD enabled=1 limit=96"
        ),
        "expected_record_schema": "B5RD_BOUNDARY_V1",
        "returned_record_target": "runs/c0/return_observer.log",
    }
    old_features = manifest["diagnostic_feature_runtime_binding"]["features"]
    by_name = {item["feature"]: item for item in old_features}
    by_name[b5_feature["feature"]] = b5_feature
    manifest["diagnostic_feature_runtime_binding"]["features"] = [
        by_name[name] for name in KEPT_FEATURES
    ]
    manifest["buffer5_read_diagnostic"] = {
        **b5_feature,
        "edge_record": "B5RD_EDGE_V1",
        "qualified_events": [
            "RD_Buffer_AG request accept",
            "Buffer5 cluster request accept",
            "Buffer5 bank read accept",
            "Buffer5 return-valid rise",
            "RD_Buffer_AG pop",
        ],
        "state_only": [
            "pingpong selector and selected ready",
            "request valid/strb/address",
            "bank readiness and RD_Buffer_AG occupancy",
        ],
        "candidate_observation_matrix": reduction["candidate_observation_matrix"],
        "functional_fix": False,
        "configuration_changed": False,
        "timeout_changed": False,
        "backpressure_changed": False,
    }
    manifest["diagnostic_execution_reduction"] = reduction
    manifest["current_local_rtl_binding"] = binding
    manifest["path_length_budget"] = path_budget(package)
    if not manifest["path_length_budget"]["pass"]:
        raise BuildError("path length budget failed")
    manifest["superseded_v35_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_V36_DIAGNOSTIC",
    }
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"].update(
        {
            "sha256": observer_sha,
            "size_bytes": (package / "tb_probe/native_return_observer.svh").stat().st_size,
        }
    )
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    receipt = base.observer_precompile_receipt(package, observer_sha)
    if not receipt["valid"]:
        raise BuildError(f"observer static gate failed: {receipt['errors']}")
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL_NAME,
        output / f"{INSTALL_NAME}.zip",
        output / f"{INSTALL_NAME}.zip.sha256",
        output / f"{INSTALL_NAME}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v36 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v36-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v36 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-buffer5-read-diagnostic-build-v36",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v35_sha256": SOURCE_SHA256,
        "bound_v35_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "current_local_rtl_commit": RTL_COMMIT,
        "rtl_sync_report_sha256": RTL_SYNC_REPORT_SHA256,
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
