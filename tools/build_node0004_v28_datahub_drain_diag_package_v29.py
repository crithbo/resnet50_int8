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


SOURCE_NAME = "r5_n4_hw_v28_dwrite_path_diag_bind"
INSTALL_NAME = "r5_n4_hw_v29_datahub_drain_diag"
SOURCE_SHA256 = (
    "a3b2be33d395356b06c96e8311c017544cbdcc7b3e553006ae582acea176101f"
)
RETURN_SHA256 = (
    "959b945ebaa40dfcbedbdac73b3fcbb98f5fdf96f3dfa77dde8bd0971009c4a9"
)
SERVER_RULE_SHA256 = (
    "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v28 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v28 source CRC failed")
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
            raise BuildError(f"v28 root differs: {sorted(roots)}")
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


def datahub(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_datahub_top_wrapper.u_datahub_top."
        + leaf
    )


def queue(channel: int, leaf: str) -> str:
    return datahub(
        f"local_req_full_channels[{channel}].wr_en."
        f"u_local_req_full_channel.u_local_wr_req_queue.{leaf}"
    )


def full_channel(channel: int, leaf: str) -> str:
    return datahub(
        f"local_req_full_channels[{channel}].wr_en."
        f"u_local_req_full_channel.{leaf}"
    )


def crossbar(leaf: str) -> str:
    return datahub(f"u_datahub_req_crossbar.{leaf}")


def match_vector(channel: int) -> str:
    return (
        "{"
        + ", ".join(
            crossbar(f"total_req_match[{bank}][{channel}]")
            for bank in range(3, -1, -1)
        )
        + "}"
    )


def ready_vector(channel: int) -> str:
    return (
        "{"
        + ", ".join(
            crossbar(f"total_req_ready[{bank}][{channel}]")
            for bank in range(3, -1, -1)
        )
        + "}"
    )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "DATAHUB_DRAIN_BOUNDARY_V1" in text:
        raise BuildError("v29 DataHub diagnostic already present")
    call = "                return_obs_write_dwrite_path_state(event_name);"
    replacement = call + "\n" + (
        "                return_obs_write_datahub_drain_state(event_name);"
    )
    if text.count(call) != 1:
        raise BuildError("observer decision hook anchor differs")
    text = text.replace(call, replacement, 1)
    block = f"""

    // v29: qualified MSE4 local write queue -> arbiter -> bank crossbar drain.
    // MSE4 channels flatten to local request channels 8 and 9. Level/full/
    // empty fields are state corroboration only and never increment progress.
    bit return_obs_dh_enabled;
    integer return_obs_dh_limit;
    integer return_obs_dh_plusarg_status;
    integer return_obs_dh_edge_records;
    longint unsigned return_obs_dh_addr_in_8;
    longint unsigned return_obs_dh_data_in_8;
    longint unsigned return_obs_dh_head_8;
    longint unsigned return_obs_dh_write_grant_8;
    longint unsigned return_obs_dh_crossbar_accept_8;
    longint unsigned return_obs_dh_addr_in_9;
    longint unsigned return_obs_dh_data_in_9;
    longint unsigned return_obs_dh_head_9;
    longint unsigned return_obs_dh_write_grant_9;
    longint unsigned return_obs_dh_crossbar_accept_9;
    longint unsigned return_obs_dh_head_x;
    longint unsigned return_obs_dh_no_bank_match;

    initial begin
        return_obs_dh_enabled = $test$plusargs("RETURN_OBS_DATAHUB_DRAIN");
        return_obs_dh_limit = 64;
        return_obs_dh_plusarg_status = $value$plusargs(
            "RETURN_OBS_DATAHUB_DRAIN_LIMIT=%d", return_obs_dh_limit
        );
        return_obs_dh_edge_records = 0;
        return_obs_dh_addr_in_8 = 0;
        return_obs_dh_data_in_8 = 0;
        return_obs_dh_head_8 = 0;
        return_obs_dh_write_grant_8 = 0;
        return_obs_dh_crossbar_accept_8 = 0;
        return_obs_dh_addr_in_9 = 0;
        return_obs_dh_data_in_9 = 0;
        return_obs_dh_head_9 = 0;
        return_obs_dh_write_grant_9 = 0;
        return_obs_dh_crossbar_accept_9 = 0;
        return_obs_dh_head_x = 0;
        return_obs_dh_no_bank_match = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_DATAHUB_DRAIN enabled=%0d limit_name=RETURN_OBS_DATAHUB_DRAIN_LIMIT limit=%0d",
                return_obs_dh_enabled,
                return_obs_dh_limit
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin
        bit dh_addr_in_8;
        bit dh_data_in_8;
        bit dh_head_8;
        bit dh_grant_8;
        bit dh_accept_8;
        bit dh_addr_in_9;
        bit dh_data_in_9;
        bit dh_head_9;
        bit dh_grant_9;
        bit dh_accept_9;
        bit dh_head_x_8;
        bit dh_head_x_9;
        bit dh_no_match_8;
        bit dh_no_match_9;
        if (!u_NDP_Top_new.rst_n_sg) begin
            return_obs_dh_edge_records = 0;
            return_obs_dh_addr_in_8 = 0;
            return_obs_dh_data_in_8 = 0;
            return_obs_dh_head_8 = 0;
            return_obs_dh_write_grant_8 = 0;
            return_obs_dh_crossbar_accept_8 = 0;
            return_obs_dh_addr_in_9 = 0;
            return_obs_dh_data_in_9 = 0;
            return_obs_dh_head_9 = 0;
            return_obs_dh_write_grant_9 = 0;
            return_obs_dh_crossbar_accept_9 = 0;
            return_obs_dh_head_x = 0;
            return_obs_dh_no_bank_match = 0;
        end
        else if (return_obs_dh_enabled && return_obs_active) begin
            dh_addr_in_8 = {queue(8, "req_fifo_wr_en")};
            dh_data_in_8 = {queue(8, "data_fifo_wr_en")};
            dh_head_8 = {queue(8, "hub_wr_req_valid")};
            dh_grant_8 = dh_head_8 && {full_channel(8, "arb_req_ready[0]")};
            dh_accept_8 = dh_head_8 && {queue(8, "hub_wr_req_ready")};
            dh_addr_in_9 = {queue(9, "req_fifo_wr_en")};
            dh_data_in_9 = {queue(9, "data_fifo_wr_en")};
            dh_head_9 = {queue(9, "hub_wr_req_valid")};
            dh_grant_9 = dh_head_9 && {full_channel(9, "arb_req_ready[0]")};
            dh_accept_9 = dh_head_9 && {queue(9, "hub_wr_req_ready")};
            dh_head_x_8 = dh_head_8 && $isunknown({queue(8, "hub_wr_req_addr")});
            dh_head_x_9 = dh_head_9 && $isunknown({queue(9, "hub_wr_req_addr")});
            dh_no_match_8 = dh_grant_8 &&
                !(|{match_vector(8)});
            dh_no_match_9 = dh_grant_9 &&
                !(|{match_vector(9)});
            if (dh_addr_in_8) return_obs_dh_addr_in_8++;
            if (dh_data_in_8) return_obs_dh_data_in_8++;
            if (dh_head_8) return_obs_dh_head_8++;
            if (dh_grant_8) return_obs_dh_write_grant_8++;
            if (dh_accept_8) return_obs_dh_crossbar_accept_8++;
            if (dh_addr_in_9) return_obs_dh_addr_in_9++;
            if (dh_data_in_9) return_obs_dh_data_in_9++;
            if (dh_head_9) return_obs_dh_head_9++;
            if (dh_grant_9) return_obs_dh_write_grant_9++;
            if (dh_accept_9) return_obs_dh_crossbar_accept_9++;
            if (dh_head_x_8 || dh_head_x_9) return_obs_dh_head_x++;
            if (dh_no_match_8 || dh_no_match_9) return_obs_dh_no_bank_match++;
            if (
                return_obs_dh_edge_records < return_obs_dh_limit &&
                (dh_addr_in_8 || dh_data_in_8 || dh_accept_8 ||
                 dh_addr_in_9 || dh_data_in_9 || dh_accept_9 ||
                 dh_head_x_8 || dh_head_x_9 || dh_no_match_8 ||
                 dh_no_match_9)
            ) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | DATAHUB_DRAIN_EDGE_V1 | n=%0d a8=%0d d8=%0d head8=%0d grant8=%0d accept8=%0d addr8=0x%0h bank8=%0d match8=0x%0h ready8=0x%0h a9=%0d d9=%0d head9=%0d grant9=%0d accept9=%0d addr9=0x%0h bank9=%0d match9=0x%0h ready9=0x%0h head_x=%0d no_match=%0d",
                    $time,
                    return_obs_dh_edge_records + 1,
                    dh_addr_in_8,
                    dh_data_in_8,
                    dh_head_8,
                    dh_grant_8,
                    dh_accept_8,
                    {queue(8, "hub_wr_req_addr")},
                    {crossbar("total_req_addr_bank[8]")},
                    {match_vector(8)},
                    {ready_vector(8)},
                    dh_addr_in_9,
                    dh_data_in_9,
                    dh_head_9,
                    dh_grant_9,
                    dh_accept_9,
                    {queue(9, "hub_wr_req_addr")},
                    {crossbar("total_req_addr_bank[9]")},
                    {match_vector(9)},
                    {ready_vector(9)},
                    dh_head_x_8 || dh_head_x_9,
                    dh_no_match_8 || dh_no_match_9
                );
                return_obs_dh_edge_records++;
            end
        end
    end

    task automatic return_obs_write_datahub_drain_state(input string event_name);
        begin
            if (return_obs_dh_enabled && return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | DATAHUB_DRAIN_BOUNDARY_V1 | event=%s addr_in8=%0d data_in8=%0d head_cycles8=%0d write_grant_cycles8=%0d crossbar_accept8=%0d addr_in9=%0d data_in9=%0d head_cycles9=%0d write_grant_cycles9=%0d crossbar_accept9=%0d head_x=%0d no_bank_match=%0d head_addr8=0x%0h head_addr9=0x%0h bank8=%0d bank9=%0d bank_match8=0x%0h bank_match9=0x%0h bank_ready=0x%0h queue_full8=%0d queue_full9=%0d",
                    $time,
                    event_name,
                    return_obs_dh_addr_in_8,
                    return_obs_dh_data_in_8,
                    return_obs_dh_head_8,
                    return_obs_dh_write_grant_8,
                    return_obs_dh_crossbar_accept_8,
                    return_obs_dh_addr_in_9,
                    return_obs_dh_data_in_9,
                    return_obs_dh_head_9,
                    return_obs_dh_write_grant_9,
                    return_obs_dh_crossbar_accept_9,
                    return_obs_dh_head_x,
                    return_obs_dh_no_bank_match,
                    {queue(8, "hub_wr_req_addr")},
                    {queue(9, "hub_wr_req_addr")},
                    {crossbar("total_req_addr_bank[8]")},
                    {crossbar("total_req_addr_bank[9]")},
                    {match_vector(8)},
                    {match_vector(9)},
                    {crossbar("req_cb_ready")},
                    {queue(8, "req_fifo_full")},
                    {queue(9, "req_fifo_full")}
                );
                $fflush(return_obs_fd);
            end
        end
    endtask
"""
    path.write_text(text + block, encoding="utf-8", newline="\n")
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    token = "+RETURN_OBS_DWRITE_PATH_LIMIT=64"
    if text.count(token) != 2:
        raise BuildError(f"runner insertion anchor differs: {text.count(token)}")
    text = text.replace(
        token,
        token
        + " +RETURN_OBS_DATAHUB_DRAIN"
        + " +RETURN_OBS_DATAHUB_DRAIN_LIMIT=64",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = """    {
        "feature": "RETURN_OBS_DWRITE_PATH",
        "enable": "+RETURN_OBS_DWRITE_PATH",
        "limits": ("+RETURN_OBS_DWRITE_PATH_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_DWRITE_PATH",
            "enabled=1",
            "limit=64",
        ),
    },
)
"""
    replacement = """    {
        "feature": "RETURN_OBS_DWRITE_PATH",
        "enable": "+RETURN_OBS_DWRITE_PATH",
        "limits": ("+RETURN_OBS_DWRITE_PATH_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_DWRITE_PATH",
            "enabled=1",
            "limit=64",
        ),
    },
    {
        "feature": "RETURN_OBS_DATAHUB_DRAIN",
        "enable": "+RETURN_OBS_DATAHUB_DRAIN",
        "limits": ("+RETURN_OBS_DATAHUB_DRAIN_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_DATAHUB_DRAIN",
            "enabled=1",
            "limit=64",
        ),
    },
)
"""
    if text.count(anchor) != 1:
        raise BuildError("runtime feature anchor differs")
    path.write_text(
        text.replace(anchor, replacement, 1),
        encoding="utf-8",
        newline="\n",
    )


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v29-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    readme = package / "README.md"
    readme.write_text(
        (
            "# node0004 v29 DataHub drain diagnostic\n\n"
            "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
            "v28 proved balanced MSE4 address/data acceptance into both DataHub "
            "local write channels, followed by queue-full backpressure without "
            "a natural terminal or formal D. This package keeps the v28 "
            "workload, configuration, golden, timeout, backpressure and "
            "functional RTL unchanged. It adds one qualified low-cost boundary "
            "covering queue ingress/head, write arbitration, bank match and "
            "bank-crossbar acceptance for local channels 8 and 9.\n\n"
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
            "schema": "resnet50-node0004-datahub-drain-diagnostic-package-v29",
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
    manifest["active_receipts"]["server_package_rule_sha256"] = (
        SERVER_RULE_SHA256
    )
    manifest["v28_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "DATAHUB_DRAIN_BOUNDARY_UNRESOLVED",
        "last_proven_good": (
            "MSE4_SOURCE_PREPARED_16_CHUNKS_AND_DATAHUB_ACCEPTED_"
            "7_ADDRESS_PLUS_7_DATA_PER_CHANNEL_WITH_ZERO_OUTSTANDING"
        ),
        "first_divergence": (
            "DATAHUB_LOCAL_WRITE_QUEUE_HEAD_TO_BANK_CROSSBAR_DRAIN_"
            "WHILE_MSE4_SOURCE_REMAINS_BACKPRESSURED"
        ),
        "root_cause": (
            "UNRESOLVED_REQUIRES_QUEUE_HEAD_ARBITER_BANK_MATCH_READY_BOUNDARY"
        ),
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
    }
    feature = {
        "feature": "RETURN_OBS_DATAHUB_DRAIN",
        "runtime_enable_parameter": "+RETURN_OBS_DATAHUB_DRAIN",
        "limit_or_budget_parameters": [
            "+RETURN_OBS_DATAHUB_DRAIN_LIMIT=64"
        ],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 "
            "feature=RETURN_OBS_DATAHUB_DRAIN enabled=1 limit=64"
        ),
        "expected_record_schema": "DATAHUB_DRAIN_BOUNDARY_V1",
    }
    manifest["diagnostic_feature_runtime_binding"]["features"].append(feature)
    manifest["datahub_drain_diagnostic"] = {
        **feature,
        "edge_record": "DATAHUB_DRAIN_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
        "qualified_boundary": (
            "MSE4 local channels 8/9 queue ingress -> head valid -> "
            "write arbiter grant -> bank match -> crossbar accept"
        ),
        "state_only": [
            "queue full/empty",
            "head address",
            "bank selector",
            "bank match vector",
            "bank ready vector",
        ],
        "functional_fix": False,
        "timeout_changed": False,
        "backpressure_changed": False,
        "configuration_changed": False,
    }
    manifest["superseded_v28_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_NARROWER_DIAGNOSTIC",
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
        raise BuildError("refusing to overwrite existing v29 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v29-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v29 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-datahub-drain-diagnostic-build-v29",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v28_sha256": SOURCE_SHA256,
        "bound_v28_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
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
