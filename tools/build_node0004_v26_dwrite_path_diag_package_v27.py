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

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


SOURCE_NAME = "r5_n4_hw_v26_transout_threshold_fix"
INSTALL_NAME = "r5_n4_hw_v27_dwrite_path_diag"
SOURCE_SHA256 = (
    "94beb61460e033fbf8ec7afd4cd64e38cd23681fb894df9960bd3cb4be962ddb"
)
RETURN_SHA256 = (
    "2a3e041737376a8afdfcb70d85e30c9f4c7fbc12d5bdad94c9ec2c9b7fa78d68"
)
AGENT_SHA256 = (
    "d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721"
)
INDEX_SHA256 = (
    "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5"
)
SERVER_RULE_SHA256 = (
    "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
)
INT8_SA_SHA256 = (
    "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
)
README_SHA256 = (
    "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


class BuildError(RuntimeError):
    pass


def safe_extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v26 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v26 source CRC failed")
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
                raise BuildError(f"unsafe/duplicate source member: {info.filename}")
            seen.add(info.filename)
            if path.parts:
                roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"source root differs: {sorted(roots)}")
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


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(f"patch anchor count differs for {path}: {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def xmr(module: str, leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        f".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.{module}.{leaf}"
    )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "DWRITE_PATH_BOUNDARY_V1" in text:
        raise BuildError("v27 D-write diagnostic already present")
    call = '                return_obs_write_terminal_match_state(event_name);'
    replacement = (
        call
        + "\n"
        + '                return_obs_write_dwrite_path_state(event_name);'
    )
    if text.count(call) != 1:
        raise BuildError("terminal-state call anchor differs")
    text = text.replace(call, replacement, 1)
    block = f"""

    // v27: narrow MSE4 Buffer5-read/tag -> last-index0 -> slice-finish path.
    // Counters below increment only on qualified handshakes. Queue/count/level
    // fields are emitted only as corroborating state.
    bit return_obs_dw_enabled;
    integer return_obs_dw_limit;
    integer return_obs_dw_plusarg_status;
    longint unsigned return_obs_dw_tag_accept;
    longint unsigned return_obs_dw_tag_last;
    longint unsigned return_obs_dw_tag_last0;
    longint unsigned return_obs_dw_buf_read_accept;
    longint unsigned return_obs_dw_buf_read_last;
    longint unsigned return_obs_dw_buf_read_last0;
    longint unsigned return_obs_dw_prepare_accept;
    longint unsigned return_obs_dw_prepare_last;
    longint unsigned return_obs_dw_ob_write_accept;
    longint unsigned return_obs_dw_ob_last_write;
    longint unsigned return_obs_dw_wdata_accept;
    longint unsigned return_obs_dw_wdata_last_accept;
    longint unsigned return_obs_dw_slice_finish;
    integer return_obs_dw_edge_records;

    initial begin
        return_obs_dw_enabled = $test$plusargs("RETURN_OBS_DWRITE_PATH");
        return_obs_dw_limit = 64;
        return_obs_dw_plusarg_status = $value$plusargs(
            "RETURN_OBS_DWRITE_PATH_LIMIT=%d", return_obs_dw_limit
        );
        return_obs_dw_tag_accept = 0;
        return_obs_dw_tag_last = 0;
        return_obs_dw_tag_last0 = 0;
        return_obs_dw_buf_read_accept = 0;
        return_obs_dw_buf_read_last = 0;
        return_obs_dw_buf_read_last0 = 0;
        return_obs_dw_prepare_accept = 0;
        return_obs_dw_prepare_last = 0;
        return_obs_dw_ob_write_accept = 0;
        return_obs_dw_ob_last_write = 0;
        return_obs_dw_wdata_accept = 0;
        return_obs_dw_wdata_last_accept = 0;
        return_obs_dw_slice_finish = 0;
        return_obs_dw_edge_records = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_DWRITE_PATH enabled=%0d limit_name=RETURN_OBS_DWRITE_PATH_LIMIT limit=%0d",
                return_obs_dw_enabled,
                return_obs_dw_limit
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        bit dw_tag_hs;
        bit dw_buf_hs;
        bit dw_prepare_hs;
        bit dw_ob_wr_hs;
        bit dw_wdata_hs;
        bit dw_last0;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_dw_tag_accept = 0;
            return_obs_dw_tag_last = 0;
            return_obs_dw_tag_last0 = 0;
            return_obs_dw_buf_read_accept = 0;
            return_obs_dw_buf_read_last = 0;
            return_obs_dw_buf_read_last0 = 0;
            return_obs_dw_prepare_accept = 0;
            return_obs_dw_prepare_last = 0;
            return_obs_dw_ob_write_accept = 0;
            return_obs_dw_ob_last_write = 0;
            return_obs_dw_wdata_accept = 0;
            return_obs_dw_wdata_last_accept = 0;
            return_obs_dw_slice_finish = 0;
            return_obs_dw_edge_records = 0;
        end
        else if (return_obs_dw_enabled && return_obs_active) begin
            dw_tag_hs =
                {xmr("u_RD_Buffer_AG", "buf_ag_ob_wr_en")} &&
                !{xmr("u_RD_Buffer_AG", "buf_ag_ob_full")};
            dw_buf_hs =
                (|{xmr("u_RD_Buffer_AG", "mse2buf_rreq_valid")}) &&
                {xmr("u_RD_Buffer_AG", "buf2mse_rreq_ready")};
            dw_prepare_hs =
                {xmr("u_WR_Data_Channel", "wr_data_chl_prepared_data_wr_hs")};
            dw_ob_wr_hs =
                |{xmr("u_WR_Data_Channel", "wr_chl_ob_wr_hs")};
            dw_wdata_hs =
                |(
                    {xmr("u_WR_Data_Channel", "mse2mem_wdata_valid")} &
                    {xmr("u_WR_Data_Channel", "mem2mse_wdata_ready")}
                );
            dw_last0 =
                {xmr("u_RD_Buffer_AG", "mse2buf_last")} &&
                !(|{xmr("u_RD_Buffer_AG", "mse2buf_last_index")});
            if (dw_tag_hs) begin
                return_obs_dw_tag_accept++;
                if ({xmr("u_RD_Buffer_AG", "buf_ag_idx_last_bit")})
                    return_obs_dw_tag_last++;
                if (
                    {xmr("u_RD_Buffer_AG", "buf_ag_idx_last_bit")} &&
                    !(|{xmr("u_RD_Buffer_AG", "buf_ag_idx_last_index")})
                )
                    return_obs_dw_tag_last0++;
            end
            if (dw_buf_hs) begin
                return_obs_dw_buf_read_accept++;
                if ({xmr("u_RD_Buffer_AG", "mse2buf_last")})
                    return_obs_dw_buf_read_last++;
                if (dw_last0)
                    return_obs_dw_buf_read_last0++;
            end
            if (dw_prepare_hs) begin
                return_obs_dw_prepare_accept++;
                if ({xmr("u_WR_Data_Channel", "wr_data_chl_last_flag")})
                    return_obs_dw_prepare_last++;
            end
            if (dw_ob_wr_hs) begin
                return_obs_dw_ob_write_accept++;
                if (
                    {xmr("u_WR_Data_Channel", "wr_data_chl_last_bitmap_reg")}
                    [{xmr("u_WR_Data_Channel", "wr_data_chl_last_bitmap_rptr")}]
                )
                    return_obs_dw_ob_last_write++;
            end
            if (dw_wdata_hs) begin
                return_obs_dw_wdata_accept++;
                if (
                    |(
                        {xmr("u_WR_Data_Channel", "wr_data_chl_ob_last_data_flag")} &
                        {xmr("u_WR_Data_Channel", "mem2mse_wdata_ready")}
                    )
                )
                    return_obs_dw_wdata_last_accept++;
            end
            if ({xmr("u_WR_Data_Channel", "slice_cmpt_finish")})
                return_obs_dw_slice_finish++;
            if (
                return_obs_dw_edge_records < return_obs_dw_limit &&
                (dw_tag_hs || dw_buf_hs || dw_prepare_hs ||
                 dw_ob_wr_hs || dw_wdata_hs)
            ) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | DWRITE_PATH_EDGE_V1 | n=%0d tag_hs=%0d tag_last=%0d tag_index=%0d queue_count=%0d queue_full=%0d queue_empty=%0d buf_hs=%0d buf_last=%0d buf_index=%0d prepare_hs=%0d prepare_last=%0d prepared_count=%0d ob_wr_hs=%0d ob_last=%0d wdata_hs=%0d wdata_last=%0d slice_finish=%0d",
                    $time,
                    return_obs_dw_edge_records + 1,
                    dw_tag_hs,
                    {xmr("u_RD_Buffer_AG", "buf_ag_idx_last_bit")},
                    {xmr("u_RD_Buffer_AG", "buf_ag_idx_last_index")},
                    {xmr("u_RD_Buffer_AG", "buf_ag_ob_cnt")},
                    {xmr("u_RD_Buffer_AG", "buf_ag_ob_full")},
                    {xmr("u_RD_Buffer_AG", "buf_ag_ob_empty")},
                    dw_buf_hs,
                    {xmr("u_RD_Buffer_AG", "mse2buf_last")},
                    {xmr("u_RD_Buffer_AG", "mse2buf_last_index")},
                    dw_prepare_hs,
                    {xmr("u_WR_Data_Channel", "wr_data_chl_last_flag")},
                    {xmr("u_WR_Data_Channel", "wr_data_chl_prepared_data_cnt")},
                    dw_ob_wr_hs,
                    |(
                        {xmr("u_WR_Data_Channel", "wr_data_chl_ob_last_data_flag")}
                    ),
                    dw_wdata_hs,
                    |(
                        {xmr("u_WR_Data_Channel", "wr_data_chl_ob_last_data_flag")} &
                        {xmr("u_WR_Data_Channel", "mem2mse_wdata_ready")}
                    ),
                    {xmr("u_WR_Data_Channel", "slice_cmpt_finish")}
                );
                return_obs_dw_edge_records++;
            end
        end
    end

    task automatic return_obs_write_dwrite_path_state(input string event_name);
        begin
            if (return_obs_dw_enabled && return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | DWRITE_PATH_BOUNDARY_V1 | event=%s tag_accept=%0d tag_last=%0d tag_last0=%0d buf_read_accept=%0d buf_read_last=%0d buf_read_last0=%0d prepare_accept=%0d prepare_last=%0d ob_write_accept=%0d ob_last_write=%0d wdata_accept=%0d wdata_last_accept=%0d slice_finish=%0d queue_count=%0d queue_full=%0d queue_empty=%0d current_tag_last=%0d current_tag_index=%0d current_buf_last=%0d current_buf_index=%0d buf_ready=%0d wr_ready=%0d prepared_count=%0d ob_last_state=0x%0h",
                    $time,
                    event_name,
                    return_obs_dw_tag_accept,
                    return_obs_dw_tag_last,
                    return_obs_dw_tag_last0,
                    return_obs_dw_buf_read_accept,
                    return_obs_dw_buf_read_last,
                    return_obs_dw_buf_read_last0,
                    return_obs_dw_prepare_accept,
                    return_obs_dw_prepare_last,
                    return_obs_dw_ob_write_accept,
                    return_obs_dw_ob_last_write,
                    return_obs_dw_wdata_accept,
                    return_obs_dw_wdata_last_accept,
                    return_obs_dw_slice_finish,
                    {xmr("u_RD_Buffer_AG", "buf_ag_ob_cnt")},
                    {xmr("u_RD_Buffer_AG", "buf_ag_ob_full")},
                    {xmr("u_RD_Buffer_AG", "buf_ag_ob_empty")},
                    {xmr("u_RD_Buffer_AG", "buf_ag_idx_last_bit")},
                    {xmr("u_RD_Buffer_AG", "buf_ag_idx_last_index")},
                    {xmr("u_RD_Buffer_AG", "mse2buf_last")},
                    {xmr("u_RD_Buffer_AG", "mse2buf_last_index")},
                    {xmr("u_RD_Buffer_AG", "buf2mse_rreq_ready")},
                    {xmr("u_RD_Buffer_AG", "wr_data_chl_ready")},
                    {xmr("u_WR_Data_Channel", "wr_data_chl_prepared_data_cnt")},
                    {xmr("u_WR_Data_Channel", "wr_data_chl_ob_last_data_flag")}
                );
                $fflush(return_obs_fd);
            end
        end
    endtask
"""
    path.write_text(text + block, encoding="utf-8", newline="\n")
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    prepare = package / "PREPARE_AND_RUN.sh"
    text = prepare.read_text(encoding="utf-8")
    token = "+RETURN_OBS_FINAL_RELEASE_LIMIT=256"
    if text.count(token) != 2:
        raise BuildError(f"runtime insertion anchor count differs: {text.count(token)}")
    text = text.replace(
        token,
        token + " +RETURN_OBS_DWRITE_PATH +RETURN_OBS_DWRITE_PATH_LIMIT=64",
    )
    prepare.write_text(text, encoding="utf-8", newline="\n")


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v27-source-") as temp:
        shutil.copytree(safe_extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runner(package)
    (package / "README.md").write_text(
        (
            "# node0004 v27 D-write path diagnostic\n\n"
            "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
            "v26 crossed the transout terminal-ignore boundary and accepted "
            "28 D requests plus 28 D write-data beats, but no slice completion "
            "or formal D appeared. This package keeps the v26 configuration, "
            "numeric inputs, matrices, golden, timeout, backpressure and "
            "functional RTL byte-identical. It adds one low-cost qualified "
            "boundary from MSE4 Buffer5 tag/read acceptance through write-data "
            "last propagation and slice finish.\n\n"
            f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh "
            "/absolute/path/to/NDP_copy`\n\n"
            f"Expected return: `{INSTALL_NAME}_return.zip`.\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-dwrite-path-diagnostic-package-v27",
            "install_name": INSTALL_NAME,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "evidence_level": "E2_FROZEN_PLUS_NARROW_DWRITE_PATH_DIAGNOSTIC",
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "frozen_c0_inputs_reused_read_only": True,
            "formal_readback_claimed": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    receipts["agent_sha256"] = AGENT_SHA256
    for item in receipts["generation_read_receipt"]:
        current = {
            ".agents/rules/鐢熸垚鍓嶅繀璇荤储寮?md": INDEX_SHA256,
            ".agents/rules/鏈嶅姟鍣ㄦ祴璇曞寘鐢熸垚瑙勫垯.md": SERVER_RULE_SHA256,
            ".agents/rules/INT8_SA鐐圭Н涓撻」瑙勫垯.md": INT8_SA_SHA256,
            "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": README_SHA256,
        }
        if item["path"] in current:
            item["sha256"] = current[item["path"]]
    for rule in (
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        "CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001",
        "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
        "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
    ):
        if rule not in receipts["rules"]:
            receipts["rules"].append(rule)
    manifest["v26_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "NEW_BOUNDARY_AFTER_TRANSOUT_FIX",
        "last_proven_good": (
            "D_WRITE_REQUEST_AND_WRITE_DATA_ACCEPTED_28_AFTER_"
            "TRANSOUT_TERMINAL_MATCH"
        ),
        "first_divergence": (
            "D_WRITE_DATA_ACCEPT_TO_BUFFER5_NEXT_READ_OR_LAST_INDEX0_"
            "SLICE_FINISH"
        ),
        "root_cause": "UNRESOLVED_REQUIRES_ONE_NARROW_DWRITE_PATH_BOUNDARY",
        "transout_fix_crossed": True,
        "terminal_ignore": 0,
        "d_request": 28,
        "d_write_data": 28,
        "natural_terminal": False,
        "formal_d_present": 0,
    }
    manifest["dwrite_path_diagnostic"] = {
        "feature": "RETURN_OBS_DWRITE_PATH",
        "runtime_enable_parameter": "+RETURN_OBS_DWRITE_PATH",
        "limit_parameter": "+RETURN_OBS_DWRITE_PATH_LIMIT=64",
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 "
            "feature=RETURN_OBS_DWRITE_PATH enabled=1 limit=64"
        ),
        "edge_record": "DWRITE_PATH_EDGE_V1",
        "decision_record": "DWRITE_PATH_BOUNDARY_V1",
        "returned_record_target": "runs/c0/return_observer.log",
        "qualified_boundary": (
            "MSE4 RD_Buffer_AG tag accept -> Buffer5 read accept -> "
            "WR_Data_Channel prepared/OB/write-data accept -> last0/slice finish"
        ),
        "state_only": [
            "queue count/full/empty",
            "current tag/last/index",
            "prepared count",
            "outbuffer last flag",
        ],
        "functional_fix": False,
        "timeout_changed": False,
        "backpressure_changed": False,
        "configuration_changed": False,
    }
    manifest["superseded_v26_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "CONSUMED_RETURN_SUPERSEDED_BY_NARROWER_DIAGNOSTIC",
    }
    features = manifest["diagnostic_feature_runtime_binding"]["features"]
    features.append(
        {
            "feature": "RETURN_OBS_DWRITE_PATH",
            "runtime_enable_parameter": "+RETURN_OBS_DWRITE_PATH",
            "limit_or_budget_parameters": [
                "+RETURN_OBS_DWRITE_PATH_LIMIT=64"
            ],
            "time_zero_marker": (
                "DIAGNOSTIC_FEATURE_ENABLE_V1 "
                "feature=RETURN_OBS_DWRITE_PATH enabled=1 limit=64"
            ),
            "expected_record_schema": "DWRITE_PATH_BOUNDARY_V1",
        }
    )
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
    observer_receipt = base.observer_precompile_receipt(package, observer_sha)
    if not observer_receipt["valid"]:
        raise BuildError(f"observer static gate failed: {observer_receipt['errors']}")
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
        raise BuildError("refusing to overwrite existing v27 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v27-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v27 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-dwrite-path-diagnostic-build-v27",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v26_sha256": SOURCE_SHA256,
        "bound_v26_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    validation = output / f"{INSTALL_NAME}.validation.json"
    base.write_json(validation, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
