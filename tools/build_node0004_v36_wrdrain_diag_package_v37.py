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

import tools.build_node0004_v35_b5rd_diag_package_v36 as previous  # noqa: E402


base = previous.base
SOURCE_NAME = "r5_n4_hw_v36_b5rd_diag"
INSTALL_NAME = "r5_n4_hw_v37_wrdrain_diag"
SOURCE_SHA256 = "08a7d79c50896c18665d551c32522fc39f0f90f4802a8797caa024f4ac474bc2"
RETURN_SHA256 = "f98d448113aafb78c80cbab6cd002e8b783325082a79ae98cf265ffebc38bca5"
RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
RTL_SYNC_SHA256 = "c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c"
AGENT_SHA256 = "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
PLAN_MUTABLE_SHA256 = "ae72cd46d134c51eba8455da120d07e9a82dfe1aa29f1bd438e592d556de042e"
INDEX_SHA256 = "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2"
SERVER_RULE_SHA256 = "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1"
COMMON_RULE_SHA256 = "8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497"
NDP_RULE_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
INT8_SA_RULE_SHA256 = "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
README_SHA256 = "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
KEPT_FEATURES = (
    "RETURN_HANG_DIAG",
    "RETURN_OBS_MSE4_DESCRIPTOR",
    "RETURN_OBS_MSE4_INDEX",
    "RETURN_OBS_LC18_PE7",
    "RETURN_OBS_ROWLC4_BUFAG",
    "RETURN_OBS_B5RD",
    "RETURN_OBS_DWRITE_PATH",
    "RETURN_OBS_DATAHUB_DRAIN",
    "RETURN_OBS_WRDRAIN",
)


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v36 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v36 source CRC failed")
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
            raise BuildError(f"v36 root differs: {sorted(roots)}")
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


def wdc(leaf: str) -> str:
    return previous.mse4(f"u_WR_Data_Channel.{leaf}")


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "WRDRAIN_BOUNDARY_V1" in text:
        raise BuildError("v37 WR drain diagnostic already present")

    canonical = '                return_obs_write_b5rd_state("DIAG_DECISION");'
    if text.count(canonical) != 1:
        raise BuildError("v36 canonical B5 snapshot anchor differs")
    text = text.replace(
        canonical,
        canonical
        + '\n                return_obs_write_mse4_descriptor_state("DIAG_DECISION");'
        + '\n                return_obs_write_mse4_index_state("DIAG_DECISION");'
        + '\n                return_obs_write_dwrite_path_state("DIAG_DECISION");'
        + '\n                return_obs_write_datahub_drain_state("DIAG_DECISION");'
        + '\n                return_obs_write_wrdrain_state("DIAG_DECISION");',
        1,
    )

    block = f'''

    // v37: state-only discriminator after qualified descriptor/data counters.
    // None of these levels contributes to canonical progress.
    bit return_obs_wrd_enabled;
    integer return_obs_wrd_plusarg_status;
    integer return_obs_wrd_limit;

    initial begin
        return_obs_wrd_enabled = $test$plusargs("RETURN_OBS_WRDRAIN");
        return_obs_wrd_limit = 1;
        return_obs_wrd_plusarg_status = $value$plusargs(
            "RETURN_OBS_WRDRAIN_LIMIT=%d", return_obs_wrd_limit
        );
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_WRDRAIN enabled=%0d limit_name=RETURN_OBS_WRDRAIN_LIMIT limit=%0d",
                return_obs_wrd_enabled,
                return_obs_wrd_limit
            );
            $fflush(return_obs_fd);
        end
    end

    task automatic return_obs_write_wrdrain_state(input string event_name);
        begin
            if (return_obs_wrd_enabled && return_obs_fd != 0) begin
                $fdisplay(
                    return_obs_fd,
                    "%0t | WRDRAIN_BOUNDARY_V1 | event=%s desc_empty=%0d desc_full=%0d desc_count=%0d desc_size=%0d mask_flag=%0d mask_vld=0x%0h mask_bp=0x%0h raw_col_vld=%0d hold_vld=%0d prepared_count=%0d prepared_vld=%0d prepared_bp=%0d ob_sel=%0d ob_vld_in=0x%0h ob_vld=0x%0h ob_bp=0x%0h ob_wr=0x%0h ob_rd=0x%0h mem_ready=0x%0h mse_valid=0x%0h",
                    $time,
                    event_name,
                    {wdc('wr_chl_queue_empty')},
                    {wdc('wr_chl_queue_full')},
                    {wdc('u_wr_chl_queue.fifo_counter')},
                    {wdc('wr_chl_queue_rd_tsf_size')},
                    {wdc('wr_chl_queue_rd_mask_flag')},
                    {wdc('wr_chl_mask_buf_vld')},
                    {wdc('wr_chl_mask_buf_bp_post')},
                    {wdc('raw_col_data_valid')},
                    {wdc('wr_data_chl_hold_data_vld')},
                    {wdc('wr_data_chl_prepared_data_cnt')},
                    {wdc('wr_data_chl_prepared_data_vld')},
                    {wdc('wr_chl_prepared_data_bp_pre')},
                    {wdc('wr_chl_ob_sel')},
                    {wdc('wr_chl_ob_vld_in')},
                    {wdc('wr_chl_ob_vld')},
                    {wdc('wr_chl_ob_bp_pre')},
                    {wdc('wr_chl_ob_wr_hs')},
                    {wdc('wr_chl_ob_rd_hs')},
                    {wdc('mem2mse_wdata_ready')},
                    {wdc('mse2mem_wdata_valid')}
                );
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
    token = "+RETURN_OBS_B5RD_LIMIT=96"
    if text.count(token) != 2:
        raise BuildError("v36 runner feature anchor differs")
    addition = (
        token
        + " +RETURN_OBS_DWRITE_PATH +RETURN_OBS_DWRITE_PATH_LIMIT=64"
        + " +RETURN_OBS_DATAHUB_DRAIN +RETURN_OBS_DATAHUB_DRAIN_LIMIT=64"
        + " +RETURN_OBS_WRDRAIN +RETURN_OBS_WRDRAIN_LIMIT=1"
    )
    path.write_text(
        text.replace(token, addition),
        encoding="utf-8",
        newline="\n",
    )


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = '''    {
        "feature": "RETURN_OBS_B5RD",
        "enable": "+RETURN_OBS_B5RD",
        "limits": ("+RETURN_OBS_B5RD_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_B5RD", "enabled=1", "limit=96",
        ),
    },
)'''
    addition = anchor[:-2] + '''    {
        "feature": "RETURN_OBS_DWRITE_PATH",
        "enable": "+RETURN_OBS_DWRITE_PATH",
        "limits": ("+RETURN_OBS_DWRITE_PATH_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_DWRITE_PATH", "enabled=1", "limit=64",
        ),
    },
    {
        "feature": "RETURN_OBS_DATAHUB_DRAIN",
        "enable": "+RETURN_OBS_DATAHUB_DRAIN",
        "limits": ("+RETURN_OBS_DATAHUB_DRAIN_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_DATAHUB_DRAIN", "enabled=1", "limit=64",
        ),
    },
    {
        "feature": "RETURN_OBS_WRDRAIN",
        "enable": "+RETURN_OBS_WRDRAIN",
        "limits": ("+RETURN_OBS_WRDRAIN_LIMIT=1",),
        "marker_tokens": (
            "feature=RETURN_OBS_WRDRAIN", "enabled=1", "limit=1",
        ),
    },
)'''
    if text.count(anchor) != 1:
        raise BuildError("v36 runtime feature anchor differs")
    path.write_text(
        text.replace(anchor, addition, 1),
        encoding="utf-8",
        newline="\n",
    )


def feature(
    name: str, limit: str, schema: str
) -> dict[str, Any]:
    return {
        "feature": name,
        "runtime_enable_parameter": f"+{name}",
        "limit_or_budget_parameters": [f"+{name}_LIMIT={limit}"],
        "time_zero_marker": (
            f"DIAGNOSTIC_FEATURE_ENABLE_V1 feature={name} "
            f"enabled=1 limit={limit}"
        ),
        "expected_record_schema": schema,
        "returned_record_target": "runs/c0/return_observer.log",
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
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": 96,
        "max_projected_absolute_path_chars": 240,
        "max_zip_member_chars": len(INSTALL_NAME) + 1 + len(longest_inner),
        "max_inner_suffix_chars": len(longest_inner),
        "max_inner_depth": max(member.count("/") + 1 for member in members),
        "max_inner_component_chars": max(
            len(part) for member in members for part in member.split("/")
        ),
        "longest_inner_member": longest_inner,
        "longest_projected_relative_path": longest_projected,
        "declared_worst_projected_absolute_chars": 97 + len(longest_projected),
        "pass": (
            len(longest_inner) <= 128
            and max(member.count("/") + 1 for member in members) <= 8
            and 97 + len(longest_projected) <= 240
        ),
    }


def execution_reduction() -> dict[str, Any]:
    return {
        "schema": "node0004-v37-wr-prepared-output-datahub-reduction-v1",
        "rule_id": "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
        "causal_slice": (
            "frozen cumulative c0 prefix through 35 Buffer5 returned reads, "
            "WR prepared-data occupancy and MSE4/DataHub write drain"
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
            ],
        },
        "why_stage_payload_not_reduced": (
            "The prepared-data count=32 backpressure state is reached only after "
            "the frozen cumulative c0 prefix; no approved internal checkpoint exists."
        ),
        "candidate_observation_matrix": {
            "WR_DESCRIPTOR_QUEUE_STARVATION": [
                "MSE4_DESCRIPTOR qualified push/pop/count/size",
                "WRDRAIN descriptor empty/full/count/size snapshot",
            ],
            "MASKED_WRITE_OLD_DATA_DEPENDENCY": [
                "WRDRAIN mask flag, selected mask-valid/backpressure",
                "raw-column-valid and prepared-valid snapshot",
            ],
            "WR_OUTPUT_SELECTOR_OR_SLOT_BLOCK": [
                "WRDRAIN selector, ob_vld_in, ob_vld, ob_bp, ob_wr/rd",
                "DWRITE qualified prepared and output-buffer accepts",
            ],
            "MSE_WDATA_READY_BACKPRESSURE": [
                "WRDRAIN mse-valid/mem-ready",
                "DWRITE qualified wdata accepts",
            ],
            "DATAHUB_ARBITER_BANK_DRAIN": [
                "DATAHUB qualified address/data input, head, grant and crossbar accept",
                "DataHub bank match/ready/full state",
            ],
        },
        "claim_boundary": (
            "diagnostic localization only; E4/E5 require DUT natural terminal "
            "and all 320 formal-D items"
        ),
    }


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v37-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)

    provenance = package / "provenance"
    stale = provenance / "diag_reduction_v36.json"
    if not stale.is_file():
        raise BuildError("expected v36 reduction provenance missing")
    stale.unlink()
    reduction = execution_reduction()
    base.write_json(provenance / "diag_reduction_v37.json", reduction)

    (package / "README.md").write_text(
        "# node0004 v37 WR prepared/output/DataHub diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v36 proved all five Buffer5 request/ready/return candidates false and "
        "observed 35 qualified returned reads, while WR prepared-data reached "
        "count 32/backpressure with no explained drain. v37 enables the already "
        "compiled qualified descriptor, write-data and DataHub paths and adds one "
        "state-only WR drain snapshot to distinguish all remaining candidates in "
        "one run. Numeric, workload, config, golden, timeout, backpressure and "
        "functional RTL are unchanged.\n\n"
        f"Current local/user server RTL baseline: `{RTL_COMMIT}`; the formal "
        "return must still prove actual compile identity and E3/E4/E5.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-wr-prepared-output-datahub-diagnostic-package-v37",
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
    receipts.update(
        {
            "agent_sha256": AGENT_SHA256,
            "plan_mutable_provenance_sha256": PLAN_MUTABLE_SHA256,
            "server_package_rule_sha256": SERVER_RULE_SHA256,
            "common_operator_rule_sha256": COMMON_RULE_SHA256,
            "ndp_hardware_fields_rule_sha256": NDP_RULE_SHA256,
        }
    )
    updates = {
        ".agents/rules/生成前必读索引.md": INDEX_SHA256,
        ".agents/rules/服务器测试包生成规则.md": SERVER_RULE_SHA256,
        ".agents/rules/INT8_SA点积专项规则.md": INT8_SA_RULE_SHA256,
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": README_SHA256,
    }
    for receipt in receipts["generation_read_receipt"]:
        if receipt.get("path") in updates:
            receipt["sha256"] = updates[receipt["path"]]

    old_features = manifest["diagnostic_feature_runtime_binding"]["features"]
    by_name = {item["feature"]: item for item in old_features}
    by_name["RETURN_OBS_DWRITE_PATH"] = feature(
        "RETURN_OBS_DWRITE_PATH", "64", "DWRITE_PATH_BOUNDARY_V1"
    )
    by_name["RETURN_OBS_DATAHUB_DRAIN"] = feature(
        "RETURN_OBS_DATAHUB_DRAIN", "64", "DATAHUB_DRAIN_BOUNDARY_V1"
    )
    by_name["RETURN_OBS_WRDRAIN"] = feature(
        "RETURN_OBS_WRDRAIN", "1", "WRDRAIN_BOUNDARY_V1"
    )
    manifest["diagnostic_feature_runtime_binding"]["features"] = [
        by_name[name] for name in KEPT_FEATURES
    ]
    manifest["v36_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "UNRESOLVED_AFTER_V36_FIVE_CANDIDATES_EXCLUDED",
        "last_proven_good": (
            "BUFFER5_SELECTED_READ_REQUEST_ACCEPTED_THROUGH_CLUSTER_MRM_BANK_"
            "AND_RETURNED_TO_MSE_WITH_35_QUALIFIED_RD_BUFFER_POPS"
        ),
        "first_divergence": (
            "WR_DATA_CHANNEL_PREPARED_FIFO_REACHES_COUNT32_BACKPRESSURE_"
            "WITH_NO_OBSERVED_PREPARED_TO_OUTPUT_DRAIN_CAUSE"
        ),
        "v35_observer_defects_closed": True,
        "excluded_v36_candidates": [
            "wrong MSE pingpong selection",
            "stream-engine cluster mapping",
            "Buffer5 MRM decode or ready",
            "Buffer5 bank/address refusal",
            "Buffer5 read return missing",
        ],
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
    }
    wr_feature = by_name["RETURN_OBS_WRDRAIN"]
    manifest["wr_prepared_output_datahub_diagnostic"] = {
        **wr_feature,
        "qualified_features": [
            "RETURN_OBS_MSE4_DESCRIPTOR",
            "RETURN_OBS_DWRITE_PATH",
            "RETURN_OBS_DATAHUB_DRAIN",
        ],
        "state_only_fields": [
            "descriptor FIFO empty/full/count/size",
            "mask flag/mask buffer valid/backpressure/raw-column-valid",
            "prepared count/valid/backpressure",
            "output selector/valid-in/valid/backpressure",
            "memory write valid/ready",
        ],
        "candidate_observation_matrix": reduction["candidate_observation_matrix"],
        "functional_fix": False,
        "configuration_changed": False,
        "timeout_changed": False,
        "backpressure_changed": False,
    }
    manifest["diagnostic_execution_reduction"] = reduction
    manifest["path_length_budget"] = path_budget(package)
    if not manifest["path_length_budget"]["pass"]:
        raise BuildError("v37 path-length budget failed")
    manifest["superseded_v36_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_V37_DIAGNOSTIC",
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
        raise BuildError("refusing to overwrite existing v37 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v37-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v37 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-wr-prepared-output-datahub-diagnostic-build-v37",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v36_sha256": SOURCE_SHA256,
        "bound_v36_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "current_local_rtl_commit": RTL_COMMIT,
        "rtl_sync_report_sha256": RTL_SYNC_SHA256,
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
