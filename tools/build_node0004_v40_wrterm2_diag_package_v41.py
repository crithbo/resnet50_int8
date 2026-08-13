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

import tools.build_node0004_v37_wrterm_diag_package_v38 as previous  # noqa: E402


base = previous.base
SOURCE_NAME = "r5_n4_hw_v40_wrterm_diag"
INSTALL_NAME = "r5_n4_hw_v41_wrterm2_diag"
SOURCE_SHA256 = "f1695ec3232e1e651a3242603e299c5ce0b4a46762ec9a23401e0bf7a5523d9e"
RETURN_SHA256 = "2d0851dd41db8c3c5c7d14eb986a1b1696438397a3f21ae7b452cf40398a777d"
RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
AGENT_SHA256 = "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
PLAN_MUTABLE_SHA256 = "003db92dfd8cc7fc0beda6201d522b79e264cfb982ec9571e7bbe135076af844"
INDEX_SHA256 = "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2"
SERVER_RULE_SHA256 = "5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9"
COMMON_RULE_SHA256 = "8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497"
NDP_RULE_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
INT8_SA_RULE_SHA256 = "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
README_SHA256 = "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
FEATURE = "RETURN_OBS_WRTERM"
FEATURE_LIMIT = 96
OLD_BEGIN = "    // v38 WRTERM_ACTUAL_CONSUMER_BEGIN"
OLD_END = "    // v38 WRTERM_ACTUAL_CONSUMER_END"


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v40 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v40 source CRC failed")
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
            raise BuildError(f"v40 root differs: {sorted(roots)}")
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


def mse4(leaf: str) -> str:
    return previous.mse4(leaf)


def wrterm2_block() -> str:
    q = mse4("u_WR_Data_Channel")
    rd = mse4("u_RD_Buffer_AG")
    mi = mse4("u_Memory_AG_Idx_Queue")
    bi = mse4("u_Buffer_AG_Idx_Queue")
    return f'''    // v41 WRTERM2_ACTUAL_CONSUMER_BEGIN
    // Corrected unique final-descriptor chronology. Levels are state only.
    bit return_obs_wt_enabled;
    integer return_obs_wt_limit;
    integer return_obs_wt_plusarg_status;
    integer return_obs_wt_records;
    bit return_obs_wt_after_desc_terminal;
    bit return_obs_wt_prev_hold;
    longint unsigned return_obs_wt_desc_terminal;
    longint unsigned return_obs_wt_post_addr1;
    longint unsigned return_obs_wt_post_desc_push;
    longint unsigned return_obs_wt_post_desc_pop;
    longint unsigned return_obs_wt_post_source_push;
    longint unsigned return_obs_wt_post_source_pop;
    longint unsigned return_obs_wt_post_tag_push;
    longint unsigned return_obs_wt_post_tag_pop;
    longint unsigned return_obs_wt_post_prepare;
    longint unsigned return_obs_wt_post_hold_rise;
    longint unsigned return_obs_wt_post_prefetch_no_desc;
    longint unsigned return_obs_wt_post_last0;
    logic [63:0] return_obs_wt_prev_source;
    bit return_obs_wt_prev_source_valid;

    initial begin
        return_obs_wt_enabled = $test$plusargs("{FEATURE}");
        return_obs_wt_limit = {FEATURE_LIMIT};
        return_obs_wt_plusarg_status = $value$plusargs(
            "{FEATURE}_LIMIT=%d", return_obs_wt_limit
        );
        return_obs_wt_records = 0;
        return_obs_wt_after_desc_terminal = 0;
        return_obs_wt_prev_hold = 0;
        return_obs_wt_desc_terminal = 0;
        return_obs_wt_post_addr1 = 0;
        return_obs_wt_post_desc_push = 0;
        return_obs_wt_post_desc_pop = 0;
        return_obs_wt_post_source_push = 0;
        return_obs_wt_post_source_pop = 0;
        return_obs_wt_post_tag_push = 0;
        return_obs_wt_post_tag_pop = 0;
        return_obs_wt_post_prepare = 0;
        return_obs_wt_post_hold_rise = 0;
        return_obs_wt_post_prefetch_no_desc = 0;
        return_obs_wt_post_last0 = 0;
        return_obs_wt_prev_source = '0;
        return_obs_wt_prev_source_valid = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature={FEATURE} enabled=%0d limit_name={FEATURE}_LIMIT limit=%0d schema=WRTERM2",
                return_obs_wt_enabled,
                return_obs_wt_limit
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit wt_desc_push;
        bit wt_desc_pop;
        bit wt_final_desc_pop;
        bit wt_addr1;
        bit wt_source_push;
        bit wt_source_pop;
        bit wt_source_replay;
        bit wt_tag_push;
        bit wt_tag_pop;
        bit wt_prepare;
        bit wt_hold_rise;
        bit wt_prefetch_no_desc;
        bit wt_tag_last0;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_wt_records = 0;
            return_obs_wt_after_desc_terminal = 0;
            return_obs_wt_prev_hold = 0;
            return_obs_wt_desc_terminal = 0;
            return_obs_wt_post_addr1 = 0;
            return_obs_wt_post_desc_push = 0;
            return_obs_wt_post_desc_pop = 0;
            return_obs_wt_post_source_push = 0;
            return_obs_wt_post_source_pop = 0;
            return_obs_wt_post_tag_push = 0;
            return_obs_wt_post_tag_pop = 0;
            return_obs_wt_post_prepare = 0;
            return_obs_wt_post_hold_rise = 0;
            return_obs_wt_post_prefetch_no_desc = 0;
            return_obs_wt_post_last0 = 0;
            return_obs_wt_prev_source = '0;
            return_obs_wt_prev_source_valid = 0;
        end else if (return_obs_wt_enabled && return_obs_active) begin
            // Exact final compiled HDL consumers used by the v41 decision.
            wt_desc_push = {q}.wr_chl_queue_wr_en && !{q}.wr_chl_queue_full;
            wt_desc_pop = {q}.wr_chl_queue_rd_en && !{q}.wr_chl_queue_empty;
            wt_final_desc_pop = wt_desc_pop && !wt_desc_push &&
                                ({q}.u_wr_chl_queue.fifo_counter == 1);
            wt_addr1 = {mi}.mse_mem_queue_bp_pre[1] &&
                       {mi}.mem_idx_valid_same_gotten_masked[1];
            wt_source_push = {bi}.buf_ag_idx_queue_wr_en &&
                             !{bi}.buf_ag_idx_queue_full;
            wt_source_pop = {bi}.buf_ag_idx_queue_rd_en &&
                            !{bi}.buf_ag_idx_queue_empty;
            wt_source_replay = wt_source_push && return_obs_wt_prev_source_valid &&
                               ({bi}.buf_ag_idx_queue_wr_data ==
                                return_obs_wt_prev_source);
            wt_tag_push = {rd}.buf_ag_ob_wr_en && !{rd}.buf_ag_ob_full;
            wt_tag_pop = {rd}.buf_ag_ob_rd_en && !{rd}.buf_ag_ob_empty;
            wt_prepare = {q}.wr_data_chl_prepared_data_wr_hs;
            wt_hold_rise = {q}.wr_data_chl_hold_data_vld &&
                           !return_obs_wt_prev_hold;
            wt_prefetch_no_desc = wt_tag_pop && {q}.wr_chl_queue_empty;
            wt_tag_last0 = wt_tag_push && {rd}.buf_ag_idx_last_bit &&
                           !(|{rd}.buf_ag_idx_last_index);

            if (wt_final_desc_pop) begin
                return_obs_wt_after_desc_terminal = 1;
                return_obs_wt_desc_terminal++;
                if (return_obs_wt_records < return_obs_wt_limit) begin
                    $fdisplay(
                        return_obs_fd,
                        "%0t | WRTERM2_FINAL_POP_V1 | n=%0d desc_count=%0d source_count=%0d source_wr=0x%0h source_rd=0x%0h src_row=0x%0h src_col=0x%0h tag_count=%0d wr_ptr=%0d rd_ptr=%0d head_row=0x%0h head_col=0x%0h prepared_count=%0d",
                        $time,
                        return_obs_wt_records + 1,
                        {q}.u_wr_chl_queue.fifo_counter,
                        {bi}.u_buf_ag_idx_queue.fifo_counter,
                        {bi}.buf_ag_idx_queue_wr_data,
                        {bi}.buf_ag_idx_queue_rd_data,
                        {bi}.mse_buf_queue_row_idx_masked,
                        {bi}.mse_buf_queue_col_idx_masked,
                        {rd}.buf_ag_ob_cnt,
                        {rd}.buf_ag_ob_wr_ptr,
                        {rd}.buf_ag_ob_rd_ptr,
                        {rd}.buf_ag_ob_row_addr[{rd}.buf_ag_ob_rd_ptr],
                        {rd}.buf_ag_ob_col_addr[{rd}.buf_ag_ob_rd_ptr],
                        {q}.wr_data_chl_prepared_data_cnt
                    );
                    return_obs_wt_records++;
                    $fflush(return_obs_fd);
                end
            end
            // Nonblocking state makes this begin on the cycle after final pop.
            if (return_obs_wt_after_desc_terminal) begin
                if (wt_addr1) return_obs_wt_post_addr1++;
                if (wt_desc_push) return_obs_wt_post_desc_push++;
                if (wt_desc_pop) return_obs_wt_post_desc_pop++;
                if (wt_source_push) return_obs_wt_post_source_push++;
                if (wt_source_pop) return_obs_wt_post_source_pop++;
                if (wt_tag_push) return_obs_wt_post_tag_push++;
                if (wt_tag_pop) return_obs_wt_post_tag_pop++;
                if (wt_prepare) return_obs_wt_post_prepare++;
                if (wt_hold_rise) return_obs_wt_post_hold_rise++;
                if (wt_prefetch_no_desc)
                    return_obs_wt_post_prefetch_no_desc++;
                if (wt_tag_last0) return_obs_wt_post_last0++;
                if (
                    return_obs_wt_records < return_obs_wt_limit &&
                    (wt_addr1 || wt_desc_push || wt_desc_pop ||
                     wt_source_push || wt_source_pop || wt_tag_push ||
                     wt_tag_pop || wt_prepare || wt_hold_rise)
                ) begin
                    $fdisplay(
                        return_obs_fd,
                        "%0t | WRTERM2_EDGE_V1 | n=%0d addr1=%0d desc_push=%0d desc_pop=%0d src_push=%0d src_pop=%0d src_replay=%0d tag_push=%0d tag_pop=%0d prepare=%0d hold_rise=%0d prefetch_no_desc=%0d src_wr=0x%0h src_rd=0x%0h src_row=0x%0h src_col=0x%0h mem1_tag=0x%0h mem1_vld=%0d mem1_same=%0d mem1_bp=%0d mem1_gotten=%0d desc_count=%0d src_count=%0d tag_count=%0d wr_ptr=%0d rd_ptr=%0d head_row=0x%0h head_col=0x%0h tag_last=%0d tag_index=%0d head_last=%0d head_index=%0d prepared_count=%0d hold=%0d",
                        $time,
                        return_obs_wt_records + 1,
                        wt_addr1,
                        wt_desc_push,
                        wt_desc_pop,
                        wt_source_push,
                        wt_source_pop,
                        wt_source_replay,
                        wt_tag_push,
                        wt_tag_pop,
                        wt_prepare,
                        wt_hold_rise,
                        wt_prefetch_no_desc,
                        {bi}.buf_ag_idx_queue_wr_data,
                        {bi}.buf_ag_idx_queue_rd_data,
                        {bi}.mse_buf_queue_row_idx_masked,
                        {bi}.mse_buf_queue_col_idx_masked,
                        {mi}.mse_mem_queue_tag[1],
                        {mi}.mem_idx_valid_bit_masked[1],
                        {mi}.mem_idx_same_bit_masked[1],
                        {mi}.mse_mem_queue_bp_pre[1],
                        {mi}.mem_idx_gotten[1],
                        {q}.u_wr_chl_queue.fifo_counter,
                        {bi}.u_buf_ag_idx_queue.fifo_counter,
                        {rd}.buf_ag_ob_cnt,
                        {rd}.buf_ag_ob_wr_ptr,
                        {rd}.buf_ag_ob_rd_ptr,
                        {rd}.buf_ag_ob_row_addr[{rd}.buf_ag_ob_rd_ptr],
                        {rd}.buf_ag_ob_col_addr[{rd}.buf_ag_ob_rd_ptr],
                        {rd}.buf_ag_idx_last_bit,
                        {rd}.buf_ag_idx_last_index,
                        {rd}.mse2buf_last,
                        {rd}.mse2buf_last_index,
                        {q}.wr_data_chl_prepared_data_cnt,
                        {q}.wr_data_chl_hold_data_vld
                    );
                    return_obs_wt_records++;
                    $fflush(return_obs_fd);
                end
            end
            if (wt_source_push) begin
                return_obs_wt_prev_source = {bi}.buf_ag_idx_queue_wr_data;
                return_obs_wt_prev_source_valid = 1;
            end
            return_obs_wt_prev_hold = {q}.wr_data_chl_hold_data_vld;
        end
    end

    task automatic return_obs_write_wrterm_state(input string event_name);
        begin
            if (return_obs_wt_enabled && return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | WRTERM2_BOUNDARY_V1 | event=%s desc_terminal=%0d post_addr1=%0d post_desc_push=%0d post_desc_pop=%0d post_src_push=%0d post_src_pop=%0d post_tag_push=%0d post_tag_pop=%0d post_prepare=%0d post_hold_rise=%0d post_prefetch_no_desc=%0d post_last0=%0d desc_empty=%0d desc_count=%0d src_empty=%0d src_count=%0d tag_count=%0d tag_full=%0d tag_empty=%0d wr_ptr=%0d rd_ptr=%0d head_row=0x%0h head_col=0x%0h head_last=%0d head_index=%0d prepared_count=%0d hold=%0d",
                    $time,
                    event_name,
                    return_obs_wt_desc_terminal,
                    return_obs_wt_post_addr1,
                    return_obs_wt_post_desc_push,
                    return_obs_wt_post_desc_pop,
                    return_obs_wt_post_source_push,
                    return_obs_wt_post_source_pop,
                    return_obs_wt_post_tag_push,
                    return_obs_wt_post_tag_pop,
                    return_obs_wt_post_prepare,
                    return_obs_wt_post_hold_rise,
                    return_obs_wt_post_prefetch_no_desc,
                    return_obs_wt_post_last0,
                    {q}.wr_chl_queue_empty,
                    {q}.u_wr_chl_queue.fifo_counter,
                    {bi}.buf_ag_idx_queue_empty,
                    {bi}.u_buf_ag_idx_queue.fifo_counter,
                    {rd}.buf_ag_ob_cnt,
                    {rd}.buf_ag_ob_full,
                    {rd}.buf_ag_ob_empty,
                    {rd}.buf_ag_ob_wr_ptr,
                    {rd}.buf_ag_ob_rd_ptr,
                    {rd}.buf_ag_ob_row_addr[{rd}.buf_ag_ob_rd_ptr],
                    {rd}.buf_ag_ob_col_addr[{rd}.buf_ag_ob_rd_ptr],
                    {rd}.mse2buf_last,
                    {rd}.mse2buf_last_index,
                    {q}.wr_data_chl_prepared_data_cnt,
                    {q}.wr_data_chl_hold_data_vld
                );
                $fflush(return_obs_fd);
            end
        end
    endtask
    // v41 WRTERM2_ACTUAL_CONSUMER_END'''


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if text.count(OLD_BEGIN) != 1 or text.count(OLD_END) != 1:
        raise BuildError("v40 WRTERM block markers differ")
    begin = text.index(OLD_BEGIN)
    end = text.index(OLD_END, begin) + len(OLD_END)
    text = text[:begin] + wrterm2_block() + text[end:]
    if "WRTERM_EDGE_V1" in text or "WRTERM_BOUNDARY_V1" in text:
        raise BuildError("legacy WRTERM schema remained")
    path.write_text(text, encoding="utf-8", newline="\n")
    return base.sha256(path)


def reduction() -> dict[str, Any]:
    return {
        "schema": "node0004-v41-wrterm2-owner-chronology-v1",
        "rule_id": "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
        "observer_correction": {
            "old_predicate": "desc_pop && fifo_counter==1",
            "new_predicate": "desc_pop && !desc_push && fifo_counter==1",
            "reason": (
                "pre-state count one is also present during steady-state "
                "simultaneous push/pop"
            ),
        },
        "candidate_observation_matrix": {
            "DATA_TAG_SCHEDULE_EXCESS": [
                "post-final source queue push with new row/col/tag owner"
            ],
            "STALE_TAG_OR_DATA_LIFETIME": [
                "post-final source replay/equal owner or queued source pop "
                "without a new source push"
            ],
            "ADDRESS_TERMINAL_EARLY": [
                "Memory_AG input1 valid/same/backpressure/gotten state after "
                "the true final descriptor pop"
            ],
            "WR_PREFETCH_WITHOUT_DESCRIPTOR_GUARD": [
                "RD_Buffer_AG pop or prepared write while descriptor FIFO is "
                "empty"
            ],
        },
        "state_only": [
            "FIFO counts/full/empty",
            "pointers",
            "row/col/tag payloads",
            "prepared count",
            "hold level",
        ],
        "qualified_only": [
            "address input1 accept",
            "descriptor push/pop",
            "Buffer_AG source push/pop",
            "RD_Buffer_AG tag push/pop",
            "prepared write",
            "hold rising edge",
        ],
        "claim_boundary": "diagnostic only; not a functional or configuration fix",
    }


def path_budget(package: Path) -> dict[str, Any]:
    members = [
        str(path.relative_to(package)).replace("\\", "/")
        for path in package.rglob("*")
        if path.is_file()
    ]
    longest = max(members, key=len)
    projected_members = [
        f"install/cfg_pkg/{INSTALL_NAME}/{member}" for member in members
    ] + [
        f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
        f"evidence_{INSTALL_NAME}/SERVER_RESULT_GATE.json",
        f"{INSTALL_NAME}_return/runs/c0/return_observer.log",
    ]
    longest_projected = max(projected_members, key=len)
    depth = max(member.count("/") + 1 for member in members)
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": 96,
        "max_projected_absolute_path_chars": 240,
        "max_zip_member_chars": len(INSTALL_NAME) + 1 + len(longest),
        "max_inner_suffix_chars": len(longest),
        "max_inner_depth": depth,
        "max_inner_component_chars": max(
            len(part) for member in members for part in member.split("/")
        ),
        "longest_inner_member": longest,
        "longest_projected_relative_path": longest_projected,
        "declared_worst_projected_absolute_chars": 97 + len(longest_projected),
        "pass": (
            len(longest) <= 128
            and depth <= 8
            and 97 + len(longest_projected) <= 240
        ),
    }


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v41-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)

    provenance = package / "provenance"
    base.write_json(provenance / "diag_reduction_v41.json", reduction())
    (package / "README.md").write_text(
        "# node0004 v41 corrected descriptor-terminal owner diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v40 compiled and ran, but its observer armed the terminal window on "
        "every steady-state pop at FIFO count one. v41 requires the unique "
        "pop-without-push at count one, then records post-terminal Buffer_AG "
        "source ownership, row/column payloads, queue pointers, address state "
        "and descriptor-unaware prefetch. Numeric, workload, config, golden, "
        "timeout, backpressure and functional RTL are unchanged.\n\n"
        f"Current local/user server RTL baseline: `{RTL_COMMIT}`; formal return "
        "still owns actual compile identity and E3/E4/E5.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-wrterm2-diagnostic-package-v41",
            "install_name": INSTALL_NAME,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts.update(
        {
            "agent_sha256": AGENT_SHA256,
            "plan_mutable_provenance_sha256": PLAN_MUTABLE_SHA256,
            "server_package_rule_sha256": SERVER_RULE_SHA256,
            "common_operator_rule_sha256": COMMON_RULE_SHA256,
            "ndp_hardware_fields_rule_sha256": NDP_RULE_SHA256,
        }
    )
    receipt_updates = {
        ".agents/rules/閻㈢喐鍨氶崜宥呯箑鐠囪崵鍌ㄥ?md": INDEX_SHA256,
        ".agents/rules/閺堝秴濮熼崳銊︾ゴ鐠囨洖瀵橀悽鐔稿灇鐟欏嫬鍨?md": SERVER_RULE_SHA256,
        ".agents/rules/INT8_SA閻愬湱袧娑撴捇銆嶇憴鍕灟.md": INT8_SA_RULE_SHA256,
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": README_SHA256,
    }
    for item in receipts["generation_read_receipt"]:
        if item.get("path") in receipt_updates:
            item["sha256"] = receipt_updates[item["path"]]

    for item in manifest["diagnostic_feature_runtime_binding"]["features"]:
        if item.get("feature") == FEATURE:
            item.update(
                {
                    "time_zero_marker": (
                        "DIAGNOSTIC_FEATURE_ENABLE_V1 "
                        f"feature={FEATURE} enabled=1 limit={FEATURE_LIMIT} "
                        "schema=WRTERM2"
                    ),
                    "expected_record_schema": "WRTERM2_BOUNDARY_V1",
                }
            )
    manifest["v40_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": (
            "OBSERVER_FINAL_DESCRIPTOR_PREDICATE_DEFECT_WITH_RAW_"
            "CHRONOLOGY_CONSUMABLE"
        ),
        "last_proven_good": (
            "UNIQUE_FINAL_DESCRIPTOR_POP_AFTER_32_DESCRIPTORS_AND_"
            "32_DATA_GROUPS_REACH_DATAHUB"
        ),
        "first_divergence": (
            "FIRST_POST_FINAL_CYCLE_HAS_TAG_PUSH_POP_AND_PREPARE_WITH_"
            "NO_ADDRESS_OR_DESCRIPTOR_PROGRESS"
        ),
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "regression": False,
        "observer_correction": (
            "require descriptor pop without simultaneous push at pre-count one"
        ),
    }
    manifest["wr_descriptor_terminal_diagnostic"] = {
        "feature": FEATURE,
        "runtime_enable_parameter": f"+{FEATURE}",
        "limit_or_budget_parameters": [f"+{FEATURE}_LIMIT={FEATURE_LIMIT}"],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 "
            f"feature={FEATURE} enabled=1 limit={FEATURE_LIMIT} schema=WRTERM2"
        ),
        "expected_record_schema": "WRTERM2_BOUNDARY_V1",
        "returned_record_target": "runs/c0/return_observer.log",
        "edge_record": "WRTERM2_EDGE_V1",
        "terminal_record": "WRTERM2_FINAL_POP_V1",
        "candidate_observation_matrix": reduction()[
            "candidate_observation_matrix"
        ],
        "functional_fix": False,
        "configuration_changed": False,
        "timeout_changed": False,
        "backpressure_changed": False,
    }
    manifest["diagnostic_execution_reduction"] = reduction()
    manifest["path_length_budget"] = path_budget(package)
    if not manifest["path_length_budget"]["pass"]:
        raise BuildError("v41 path-length budget failed")
    manifest["superseded_v40_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_V41_DIAGNOSTIC",
    }
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"].update(
        {
            "sha256": observer_sha,
            "size_bytes": (
                package / "tb_probe/native_return_observer.svh"
            ).stat().st_size,
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
        raise BuildError("refusing to overwrite existing v41 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v41-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v41 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-wrterm2-diagnostic-build-v41",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v40_sha256": SOURCE_SHA256,
        "bound_v40_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "builder_plan_mutable_provenance_sha256": PLAN_MUTABLE_SHA256,
        "current_local_rtl_commit": RTL_COMMIT,
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
