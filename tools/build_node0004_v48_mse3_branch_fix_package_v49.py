from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v47_actual_lc9_diag_package_v48 as prior


base = prior.base
SOURCE_NAME = "r5_n4_hw_v48_lc9_actual"
INSTALL_NAME = "r5_n4_hw_v49_lc9_actual_compilefix"
SOURCE_SHA256 = "cdb13ac9039cbaac88306669b8b6e6d9bdb3d3956a4f38425610c6b4f2b7971b"
RETURN_SHA256 = "91cb18d7e0a1d687597503026ed0155af0c8cf2f491a1712318897122148a27a"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
AGENT_SHA256 = "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
PLAN_SHA256 = "2f296a76c75cffbf9cdc7eab92394f8fd722e018805c66948e4e87932cf8f447"
INDEX_SHA256 = "3c0c9d5e836e2ea9cb7d697252fe2f46dfd5cce8facfdbd332d8bbd3d0fe48cc"
SERVER_SHA256 = "4ff581d2add191c6345948489b90d3ccaa43fcae9c31eab8b75bcc99fae2de0b"
COMMON_SHA256 = "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1"
NDP_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
INT8_SA_SHA256 = "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
README_SHA256 = "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
OLD_BRANCH = "MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine"
NEW_BRANCH = "MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine"


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v48 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v48 source CRC failed")
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
            raise BuildError(f"v48 root differs: {sorted(roots)}")
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


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if text.count(OLD_BRANCH) != 15:
        raise BuildError("v48 MSE3 wrong-branch occurrence count differs")
    text = text.replace(OLD_BRANCH, NEW_BRANCH)
    old_event = (
        "            la_any_event = la_lc9_advance || la_lc7_capture ||\n"
        "                           la_lc7_out_accept || la_mem3_in2_capture ||\n"
        "                           la_mem3_push || la_mem3_pop || la_bp_change ||\n"
        "                           (la_lc9_valid && la_lc9_port[5] &&\n"
        "                            (la_lc9_port[4:0] == 0));"
    )
    new_event = (
        "            // v49: text output is trigger-only. Qualified counters\n"
        "            // remain complete; first-event and backpressure-transition\n"
        "            // snapshots are bounded and do not drive DUT behavior.\n"
        "            la_any_event = la_bp_change ||\n"
        "                (la_lc9_advance && (return_obs_la_lc9_advance == 0)) ||\n"
        "                (la_lc7_capture && (return_obs_la_lc7_capture == 0)) ||\n"
        "                (la_lc7_out_accept &&\n"
        "                 (return_obs_la_lc7_out_accept == 0)) ||\n"
        "                (la_mem3_in2_capture &&\n"
        "                 (return_obs_la_mem3_in2_capture == 0)) ||\n"
        "                (la_mem3_push && (return_obs_la_mem3_push == 0)) ||\n"
        "                (la_mem3_pop && (return_obs_la_mem3_pop == 0)) ||\n"
        "                ((la_lc9_valid && la_lc9_port[5] &&\n"
        "                  (la_lc9_port[4:0] == 0)) &&\n"
        "                 (return_obs_la_lc9_last0 == 0));"
    )
    if text.count(old_event) != 1:
        raise BuildError("v48 LC9 event predicate differs")
    text = text.replace(old_event, new_event, 1)
    text = text.replace(
        "// v48 LC9_ACTUAL_ACTUAL_CONSUMER_BEGIN",
        "// v49 LC9_ACTUAL_COMPILEFIX_TRIGGERED_BEGIN",
        1,
    ).replace(
        "// v48 LC9_ACTUAL_ACTUAL_CONSUMER_END",
        "// v49 LC9_ACTUAL_COMPILEFIX_TRIGGERED_END",
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")
    return base.sha256(path)


def profile_bundle() -> dict[str, Any]:
    baseline = json.loads(
        (
            ROOT
            / "contracts/server_triggered_causal_observability_current_five_v1.json"
        ).read_text(encoding="utf-8")
    )
    source_profile = next(
        profile
        for profile in baseline["profiles"]
        if profile["family"] == "conv_int32_accumulate_serialized"
    )
    profile = deepcopy(source_profile)
    profile.update(
        {
            "profile_id": "serialized_conv_node0004_v49_triggered_causal_v1",
            "maturity": "BOUND_CALIBRATION_PENDING",
            "release_eligible": False,
            "current_package": {
                "path": (
                    "artifacts/operator_config_validation/"
                    "r5-server-test-packages/r5_n4_hw_v48_lc9_actual.zip"
                ),
                "sha256": SOURCE_SHA256,
                "disposition": "READ_ONLY_NOT_MODIFIED",
            },
            "claim_boundary": (
                "Fresh v49 profile bound to the exact final observer, 0cc "
                "Stream_Engine generate branch, clk_db/rst_n_db and returned "
                "formal-D collector. Same-event A/B slowdown calibration is "
                "pending and nonblocking; dynamic success remains unclaimed."
            ),
        }
    )
    profile["boundaries"] = [
        {
            "boundary_id": "sconv49.runtime.simulator_started",
            "role": "infrastructure",
            "stage_gate": "runtime",
            "owner_clock_binding": "HOST_MONOTONIC",
            "qualification": "actual simulator invocation receipt",
            "direct_consumer_binding": "RUNNER_EXACT_CONSUMER_REQUIRED",
            "records": ["count", "first_time", "last_time"],
        },
        {
            "boundary_id": "sconv49.buffer_source.push",
            "role": "source_produce",
            "stage_gate": "c0",
            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "qualification": "qualified Buffer source push",
            "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "records": ["count", "first_time", "last_time", "last_tag"],
        },
        {
            "boundary_id": "sconv49.lc7.capture",
            "role": "consumer_accept",
            "stage_gate": "c0",
            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "qualification": "LC7 masked-valid and inbuffer-ready acceptance",
            "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "records": ["count", "first_time", "last_time", "last_tag"],
        },
        {
            "boundary_id": "sconv49.mse3.input2.capture",
            "role": "consumer_accept",
            "stage_gate": "c0",
            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "qualification": "MSE3 input2 masked-valid and local ready",
            "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "records": ["count", "first_time", "last_time", "last_tag"],
        },
        {
            "boundary_id": "sconv49.mse3.queue.push",
            "role": "queue_enqueue",
            "stage_gate": "c0",
            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "qualification": "mem_ag_idx_queue_wr_en and not full",
            "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "records": [
                "count",
                "first_time",
                "last_time",
                "max_occupancy",
                "first_full_time",
            ],
        },
        {
            "boundary_id": "sconv49.mse3.queue.pop",
            "role": "queue_dequeue",
            "stage_gate": "c0",
            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "qualification": "mem_ag_idx_queue_rd_en and not empty",
            "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "records": ["count", "first_time", "last_time", "outstanding"],
        },
        {
            "boundary_id": "sconv49.mse3.match",
            "role": "internal_match_compute",
            "stage_gate": "c0",
            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "qualification": "all enabled MSE3 indices matched and queue push qualified",
            "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "records": ["count", "first_time", "last_time", "last_tag"],
        },
        {
            "boundary_id": "sconv49.lc9.global_advance",
            "role": "output_accept",
            "stage_gate": "c0",
            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "qualification": "LC9 valid and all destination backpressure bits ready",
            "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "records": ["count", "first_time", "last_time", "last_terminal"],
        },
        {
            "boundary_id": "sconv49.global_last0",
            "role": "terminal_propagation",
            "stage_gate": "c0",
            "owner_clock_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "qualification": "qualified LC9 last with last_index zero",
            "direct_consumer_binding": "EXACT_FINAL_SOURCE_REQUIRED",
            "records": ["count", "first_time", "last_time", "last_terminal"],
        },
        {
            "boundary_id": "sconv49.formal_d",
            "role": "formal_d_collection",
            "stage_gate": "result",
            "owner_clock_binding": "NOT_APPLICABLE",
            "qualification": "320-item exact formal-D collector",
            "direct_consumer_binding": "FORMAL_D_COLLECTOR_REQUIRED",
            "records": ["count", "first_time", "last_time", "ordered_digest"],
        },
    ]
    profile["hypotheses"] = [
        {
            "hypothesis_id": "sconv49_lc7_nonaccept",
            "classification": "DYNAMIC_FLOW_CONTROL_STALL",
            "distinguished_by": [
                "sconv49.buffer_source.push",
                "sconv49.lc7.capture",
            ],
            "decision": "source advances while LC7 source-slot8 does not capture",
        },
        {
            "hypothesis_id": "sconv49_mse3_input2_nonaccept",
            "classification": "DYNAMIC_FLOW_CONTROL_STALL",
            "distinguished_by": [
                "sconv49.buffer_source.push",
                "sconv49.mse3.input2.capture",
            ],
            "decision": "source advances while MSE3 source-slot5/input2 does not capture",
        },
        {
            "hypothesis_id": "sconv49_mse3_match_no_push",
            "classification": "DYNAMIC_FLOW_CONTROL_STALL",
            "distinguished_by": [
                "sconv49.mse3.input2.capture",
                "sconv49.mse3.match",
                "sconv49.mse3.queue.push",
            ],
            "decision": "MSE3 input2 captures but the complete match cannot enqueue",
        },
        {
            "hypothesis_id": "sconv49_mse3_queue_no_pop",
            "classification": "DYNAMIC_FLOW_CONTROL_STALL",
            "distinguished_by": [
                "sconv49.mse3.queue.push",
                "sconv49.mse3.queue.pop",
            ],
            "decision": "MSE3 queue accepts but downstream does not drain",
        },
        {
            "hypothesis_id": "sconv49_global_advance_blocked",
            "classification": "DYNAMIC_FLOW_CONTROL_STALL",
            "distinguished_by": [
                "sconv49.lc7.capture",
                "sconv49.mse3.queue.pop",
                "sconv49.lc9.global_advance",
            ],
            "decision": "both actual branches progress but global LC9 does not advance",
        },
        {
            "hypothesis_id": "sconv49_terminal_missing",
            "classification": "TERMINAL_PROPAGATION_FAILURE",
            "distinguished_by": [
                "sconv49.lc9.global_advance",
                "sconv49.global_last0",
            ],
            "decision": "LC9 advances but accepted last-index-zero is absent",
        },
        {
            "hypothesis_id": "sconv49_result_missing",
            "classification": "RESULT_COLLECTION_FAILURE",
            "distinguished_by": [
                "sconv49.global_last0",
                "sconv49.formal_d",
            ],
            "decision": "terminal propagates but the exact 320-item D set is incomplete",
        },
    ]
    all_dynamic = [
        boundary["boundary_id"]
        for boundary in profile["boundaries"]
        if boundary["stage_gate"] == "c0"
    ]
    profile["triggers"] = [
        {
            "trigger_id": "FIRST_QUEUE_FULL",
            "condition": "first MSE3 queue full transition",
            "snapshot_boundaries": [
                "sconv49.mse3.queue.push",
                "sconv49.mse3.queue.pop",
            ],
            "one_shot": True,
        },
        {
            "trigger_id": "FIRST_BRANCH_DIVERGENCE",
            "condition": "LC7 and MSE3 qualified counts first diverge",
            "snapshot_boundaries": [
                "sconv49.lc7.capture",
                "sconv49.mse3.input2.capture",
                "sconv49.lc9.global_advance",
            ],
            "one_shot": True,
        },
        {
            "trigger_id": "NO_PROGRESS_WINDOW",
            "condition": "qualified measured-rate window has no causal progress",
            "snapshot_boundaries": all_dynamic,
            "one_shot": False,
        },
        {
            "trigger_id": "TERMINAL_GAP",
            "condition": "LC9 progress completes without global last0",
            "snapshot_boundaries": [
                "sconv49.lc9.global_advance",
                "sconv49.global_last0",
                "sconv49.formal_d",
            ],
            "one_shot": True,
        },
        {
            "trigger_id": "STAGE_TRANSITION",
            "condition": "qualified c0 stage transition",
            "snapshot_boundaries": [
                "sconv49.buffer_source.push",
                "sconv49.global_last0",
            ],
            "one_shot": False,
        },
        {
            "trigger_id": "EXIT_OR_SIGNAL",
            "condition": "EXIT HUP INT TERM or natural finalizer",
            "snapshot_boundaries": [
                "sconv49.runtime.simulator_started",
                *all_dynamic,
                "sconv49.formal_d",
            ],
            "one_shot": True,
        },
    ]
    return {
        "schema": "server_triggered_causal_observability_profiles_v1",
        "version": 1,
        "bundle_scope": "FRESH_SUCCESSOR_BOUND_PROFILE",
        "policy": baseline["policy"],
        "profiles": [profile],
        "claim_boundary": (
            "v49 package-local bound profile. It validates one-round causal "
            "coverage and nonintrusive triggered storage; production compile, "
            "simulation, terminal, formal D, E4 and E5 remain dynamic."
        ),
    }


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v49-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    profile = profile_bundle()
    profile_path = package / "provenance/triggered_causal_observability_v1.json"
    base.write_json(profile_path, profile)
    base.write_json(
        package / "provenance/v48_return_v49_mse3_branch_fix.json",
        {
            "schema": "node0004-v48-return-v49-mse3-branch-fix-v1",
            "bound_return_sha256": RETURN_SHA256,
            "source_v48_sha256": SOURCE_SHA256,
            "last_proven_good": (
                "PACKAGE_INSTALL_PREFLIGHT_AND_PRODUCTION_VCS_PARSE_"
                "REACHED_OBSERVER_ELABORATION"
            ),
            "first_divergence": (
                "OBSERVER_MSE3_PATH_SELECTS_NONEXISTENT_WR_MSE_GENERATE_BRANCH"
            ),
            "minimum_fix": {
                "old": OLD_BRANCH,
                "new": NEW_BRANCH,
                "occurrences": 15,
                "functional_rtl_changed": False,
                "configuration_changed": False,
            },
            "triggered_profile": profile_path.relative_to(package).as_posix(),
        },
    )
    (package / "README.md").write_text(
        "# node0004 v49 LC9 actual-consumer compile fix\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v48 stopped in production VCS because its package-local observer used "
        "`MSE_INST[3].WR_MSE`; current Stream_Engine generates MSE3 under "
        "`RD_MSE`. v49 changes only that observer hierarchy and changes its "
        "bounded LC9 text records to first-event/backpressure triggers. DUT "
        "inputs, config, numeric/W3/golden, timeout and functional RTL are "
        "byte-frozen.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-lc9-actual-compilefix-package-v49",
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
        "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
        "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    ]:
        if rule_id not in receipts["rules"]:
            receipts["rules"].append(rule_id)

    matrix = manifest["release_gate_matrix"]
    for row in matrix:
        if row["gate_id"] == "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL":
            row.update(
                {
                    "applicability": "blocking_applicable",
                    "reason": "v49 fixes exact MSE3 RD_MSE generate branch",
                    "changed_surface": [
                        "native_return_observer.svh v49 span"
                    ],
                    "evidence": [
                        "0cc generate-branch resolver positive",
                        "wrong-branch/missing/sibling negatives",
                        "focused compatible-frontend syntax",
                    ],
                    "blocking": True,
                }
            )
        elif row["gate_id"] == "CHANGED_OBSERVER_OR_CANONICAL_SEMANTICS":
            row.update(
                {
                    "applicability": "blocking_applicable",
                    "reason": (
                        "MSE3 scope fix plus trigger-only bounded LC9 records"
                    ),
                    "changed_surface": [
                        "MSE3 RD_MSE path",
                        "LC9 trigger-only event predicate",
                    ],
                    "evidence": [
                        "predicate trace",
                        "bound triggered-causal profile",
                    ],
                    "blocking": True,
                }
            )
    manifest["server_triggered_causal_observability"] = {
        "rule_id": "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
        "contract_path": profile_path.relative_to(package).as_posix(),
        "contract_sha256": base.sha256(profile_path),
        "exact_final_hdl_binding": True,
        "owner_clock": "u_NDP_Top_new.clk_db",
        "owner_reset": "u_NDP_Top_new.rst_n_db",
        "per_event_text_io": False,
        "full_wave_dump": False,
        "slowdown_calibration": "PENDING_FRESH_BOUND_PROFILE",
        "slowdown_preferred_max_percent": 50,
        "slowdown_is_blocking": False,
    }
    manifest["v48_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "PACKAGE_LOCAL_OBSERVER_MSE3_GENERATE_BRANCH_XMRE",
        "compile_exit": 2,
        "run_exit": 125,
        "simulation_started": False,
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "old_outbuffer_occupancy": "INVALIDATED_NOT_RTL_BUG",
    }
    manifest["observer_public_surface_or_xmr_proof"].update(
        {
            "private_consumers_required": [
                "IGA_LC7 masked-valid/inbuffer ready/config source",
                "MSE3 RD_MSE Memory_AG_Idx_Queue masked-valid/match/FIFO transfers",
            ],
            "exact_target_module_path": (
                "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine.sv"
            ),
            "exact_target_module_sha256": (
                "a8718b4c4b043ffbf8c2bd59842ac677f18861783d70ce5eaa3d809c79ac6365"
            ),
            "wrong_generate_branch_negative": "WR_MSE_FAIL_CLOSED",
        }
    )
    manifest["superseded_v48_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_V49_COMPILEFIX",
    }
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
        raise BuildError("refusing to overwrite existing v49 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v49-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v49 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-v48-return-v49-lc9-compilefix-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v48_sha256": SOURCE_SHA256,
        "bound_v48_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_SHA256,
        "current_common_rule_sha256": COMMON_SHA256,
        "builder_plan_mutable_provenance_sha256": PLAN_SHA256,
        "current_cloud_rtl_authority_commit": RTL_COMMIT,
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
