#!/usr/bin/env python3
"""Build the single serialized-Conv v82 successor from frozen v81 bytes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v80_return_successor_v81 as old

SOURCE = "r5_n4_hw_v81_ack_phase_targetfix"
INSTALL = "r5_n4_hw_v82b_phase_collectfix"
SOURCE_SHA = "fc3e7049822af17d956bfed7b95c9c13abdf9d151ef2881e2b68107d7b0c0389"
RETURN_SHA = "9702b2d926c04476368ff78e865d6dcc8bc602b997d2530323bfe724d905aff6"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v81_return_v82_successor/return_analysis.json"
OUT = ROOT / "outputs/conv_node0004_v81_return_v82_successor"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
RTL = ROOT / "NDP_copy01/rtl"
RTL_TREE = "c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093"
TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue"
)
NEAR_TARGET = TARGET.replace("slice_with_datahub_mc_group_gen[13]", "slice_with_datahub_mc_group_gen[12]")


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> None:
    value = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    if value.returncode:
        raise BuildError(f"command failed {value.returncode}: {' '.join(argv)}\n{value.stdout}\n{value.stderr}")


def load_generator():
    spec = importlib.util.spec_from_file_location("source_bound_generator_v82", GENERATOR)
    if spec is None or spec.loader is None:
        raise BuildError("cannot load current source-bound generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_old() -> None:
    old.SOURCE = SOURCE
    old.INSTALL = INSTALL
    old.SOURCE_SHA = SOURCE_SHA
    old.RETURN_SHA = RETURN_SHA
    old.SOURCE_ZIP = SOURCE_ZIP
    old.ANALYSIS = ANALYSIS
    old.OUT = OUT
    old.EPOCH = EPOCH


def patch_phase_and_post_sim(package: Path) -> None:
    shutil.copy2(ROOT / "tools/node0004_v82_buffer_ack_phase_observer.svh", package / "tb_probe/buffer_ack_phase_observer.svh")
    shutil.copy2(ROOT / "tools/node0004_v82_buffer_ack_phase_parser.py", package / "package_tools/buffer_ack_phase_parser.py")
    shutil.copy2(ROOT / "tools/node0004_v82_post_sim_plugin.py", package / "package_tools/node0004_v82_post_sim_plugin.py")
    shutil.copy2(ROOT / "tools/server_post_sim_return.py", package / "package_tools/server_post_sim_return.py")
    widths = {"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,"bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7}
    fixture_rows = []
    for index, phase in enumerate(("ACTIVE", "INACTIVE", "POSTNBA", "HALF", "NEXT")):
        gotten = "3" if phase in {"POSTNBA", "HALF", "NEXT"} else "0"
        bp = gotten
        fields = {"wr":"1","full":"0","all":"1","valid":"3","same":"3","gotten":gotten,"keep":"3","bpmask":"3","bp":bp,"mode":"2","row":"1","col":"1f","rowtag":"7f","coltag":"7f"}
        payload = 0
        for name, width in widths.items():
            payload = (payload << width) | int(fields[name], 16)
        fixture_rows.append(
            f"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance={TARGET} time={100+index} mask=1 payload={payload:x} payload_known=1 payload_width=38 seq=0 phase={phase} "
            + " ".join(f"{name}={fields[name]}" for name in widths)
        )
    fixture_path = package / "diagnostics/partial_exit_live/buffer_ack_phase_live.log"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text("\n".join(fixture_rows) + "\n", encoding="utf-8", newline="\n")

    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = INSTALL
    request["plugins"][0]["argv"] = [
        "python3", "{package_root}/package_tools/node0004_v82_post_sim_plugin.py",
        "--package-root", "{package_root}", "--attempt-root", "{attempt_root}",
        "--phase-live-log", "{attempt_root}/c0/sim.log",
        "--phase-output", "{attempt_root}/c0/buffer_ack_phase_decision.json",
    ]
    write(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["package_id"] = INSTALL
    contract["helper_sha256"] = sha(package / "package_tools/server_post_sim_return.py")
    contract["request_sha256"] = sha(request_path)
    contract["claim_boundary"] = (
        "Exact target phase decision is persisted before the frozen bounded source-bound collector mutates sim.log; "
        "core return remains independent and no natural-terminal, formal-D, E4 or E5 claim is made."
    )
    write(contract_path, contract)

    phase_semantics = {
        "schema": "conv-node0004-v82-buffer-ack-phase-semantics-v1",
        "package_id": INSTALL,
        "boundary_id": "buf_ack_phase_target",
        "expected_instance": TARGET,
        "near_miss_instance": NEAR_TARGET,
        "record_grouping_key": ["boundary_id", "instance", "seq"],
        "payload": {
            "field_order_msb_to_lsb": ["wr", "full", "all", "valid", "same", "gotten", "keep", "bpmask", "bp", "mode", "row", "col", "rowtag", "coltag"],
            "field_widths": {"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,"bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7},
            "width_bits": 38,
            "required_binary_known": True,
            "unknown_disposition": "EVIDENCE_INCOMPLETE",
        },
        "phases": ["ACTIVE", "INACTIVE", "POSTNBA", "HALF", "NEXT"],
        "observer_sha256": sha(package / "tb_probe/buffer_ack_phase_observer.svh"),
        "parser_sha256": sha(package / "package_tools/buffer_ack_phase_parser.py"),
        "post_sim_plugin_sha256": sha(package / "package_tools/node0004_v82_post_sim_plugin.py"),
        "collector_order": "PHASE_PARSE_AND_PERSIST_BEFORE_BOUNDED_SOURCE_BOUND_PROJECTION",
    }
    canonical = json.dumps(phase_semantics, sort_keys=True, separators=(",", ":")).encode()
    phase_semantics["diagnostic_semantics_sha256"] = hashlib.sha256(canonical).hexdigest()
    write(package / "diagnostics/buffer_ack_phase_semantics_contract.json", phase_semantics)


def migrate_source_bound_v2(package: Path) -> None:
    catalog_path = package / "diagnostics/source_bound_probe_catalog.json"
    plan_path = package / "diagnostics/source_bound_probe_plan.json"
    sources = [
        RTL / "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
        RTL / "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv",
        RTL / "includes/NDP_Parameters.svh",
    ]
    argv = [sys.executable, str(GENERATOR), "catalog", "--rtl-root", str(RTL), "--rtl-tree-sha256", RTL_TREE]
    for source in sources:
        argv.extend(["--source", str(source)])
    argv.extend(["--output", str(catalog_path)])
    run(argv)
    generator = load_generator()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["schema"] = "server-source-bound-probe-plan-v2"
    plan["package_id"] = INSTALL
    plan["catalog_identity"] = {"rtl_tree_sha256": RTL_TREE, "catalog_semantic_sha256": generator.semantic_sha256(catalog)}
    plan["diagnostic_semantics"] = {
        "instance_match": "EXACT_CANONICAL_EQUALITY",
        "record_grouping_key": ["boundary_id", "canonical_instance", "seq"],
        "unknown_payload": "EVIDENCE_INCOMPLETE",
        "numeric_parse_failure": "EVIDENCE_INCOMPLETE",
        "candidate_match_cardinality": "EXACTLY_ONE",
    }
    mem_parent = TARGET.rsplit(".", 1)[0] + ".u_Memory_AG_Idx_Queue"
    buf_parent = TARGET
    near_mem_parent = NEAR_TARGET.rsplit(".", 1)[0] + ".u_Memory_AG_Idx_Queue"
    near_buf_parent = NEAR_TARGET
    identity = {
        "schema": "conv-node0004-v82-source-bound-exact-instance-identity-v1",
        "source_return": {"sha256": RETURN_SHA, "execution_id": "r1786384658245449969_758671"},
        "selection": "exact slice13/group1/MSE4 Memory_AG and Buffer_AG bound probe instances; slice12 is permanent near-miss negative",
        "boundaries": {},
    }
    symbols = {row["symbol_id"]: row for row in catalog["symbols"]}
    for boundary in plan["boundaries"]:
        boundary_id = boundary["boundary_id"]
        module = boundary["target_module"]
        parent = mem_parent if module == "Memory_AG_Idx_Queue" else buf_parent
        near_parent = near_mem_parent if module == "Memory_AG_Idx_Queue" else near_buf_parent
        suffix = f".codex_probe_{boundary_id}_inst"
        identity["boundaries"][boundary_id] = {"expected_instance": parent + suffix, "near_miss_instance": near_parent + suffix}
    identity_path = package / "diagnostics/source_bound_exact_instance_identity.json"
    write(identity_path, identity)
    identity_sha = sha(identity_path)
    for boundary in plan["boundaries"]:
        boundary_id = boundary["boundary_id"]
        row = identity["boundaries"][boundary_id]
        boundary["instance_scope"] = {
            "mode": "EXACT_CANONICAL_INSTANCE",
            "expected_instances": [row["expected_instance"]],
            "near_miss_instances": [row["near_miss_instance"]],
            "identity_provenance": {"path": "diagnostics/source_bound_exact_instance_identity.json", "sha256": identity_sha, "selector": f"boundaries.{boundary_id}"},
        }
        width = sum(int(symbols[symbol_id]["width_bits"]) for symbol_id in boundary["payload_symbol_ids"])
        boundary["payload_contract"] = {"width_bits": width, "required_binary_known": True, "unknown_disposition": "EVIDENCE_INCOMPLETE"}
    plan["decision_observations"].append({"observation_id":"buf_ack_witness_count_nonzero","boundary_id":"buf_ack_equation_witness","metric":"count_nonzero"})
    plan["decision_observations"].append({"observation_id":"mem_source_match_count_nonzero","boundary_id":"mem_source_match","metric":"count_nonzero"})
    for candidate in plan["candidates"]:
        candidate["signature"]["buf_ack_witness_count_nonzero"] = True
        candidate["signature"]["mem_source_match_count_nonzero"] = True
    plan["claim_boundary"] = (
        "Exact slice13/group1/MSE4 generated Memory_AG/Buffer_AG causal probes with exact canonical instance identity, "
        "binary-known literal payload widths and semantic fingerprint; wrong instance/X/Z/knownness/width/duplicate fail closed."
    )
    write(plan_path, plan)

    with tempfile.TemporaryDirectory(prefix="n4v82-source-bound-") as raw:
        generated = Path(raw) / "generated"
        report_path = Path(raw) / "report.json"
        cheap_path = Path(raw) / "cheap.json"
        run([sys.executable, str(GENERATOR), "materialize", "--catalog", str(catalog_path), "--plan", str(plan_path), "--output-dir", str(generated), "--report", str(report_path), "--cheap-check-output", str(cheap_path)])
        shutil.copy2(generated / "source_bound_causal_observer.svh", package / "tb_probe/source_bound_causal_observer.svh")
        shutil.copy2(generated / "source_bound_causal_parser.py", package / "package_tools/source_bound_causal_parser.py")
        shutil.copy2(generated / "source_bound_probe_binding.json", package / "diagnostics/source_bound_probe_binding.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["catalog"]["path"] = "diagnostics/source_bound_probe_catalog.json"
        report["plan"]["path"] = "diagnostics/source_bound_probe_plan.json"
        write(package / "diagnostics/source_bound_observer_generation_report.json", report)
        cheap = json.loads(cheap_path.read_text(encoding="utf-8"))
        write(package / "diagnostics/source_bound_observer_generation.json", cheap)
    write(package / "diagnostics/source_bound_final_zip_contract.json", {
        "schema": "server-source-bound-final-zip-contract-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "enforcement": "required_next_fresh",
        "members": {
            "catalog": "diagnostics/source_bound_probe_catalog.json",
            "plan": "diagnostics/source_bound_probe_plan.json",
            "observer": "tb_probe/source_bound_causal_observer.svh",
            "parser": "package_tools/source_bound_causal_parser.py",
            "binding": "diagnostics/source_bound_probe_binding.json",
            "generation_report": "diagnostics/source_bound_observer_generation_report.json",
            "runner": "PREPARE_AND_RUN.sh",
        },
        "compile_observer_token": "source_bound_causal_observer.svh",
        "runtime_plusarg": "+CODEX_CAUSAL_OBSERVER",
        "return_log_token": "source_bound_causal.log",
        "return_decision_token": "source_bound_causal_decision.json",
    })


def build_directory(output: Path) -> Path:
    configure_old()
    output.mkdir(parents=True, exist_ok=True)
    package = old.extract_source(output)
    old.rebase_identity(package)
    patch_phase_and_post_sim(package)
    migrate_source_bound_v2(package)
    old.base.update_path_budget(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["status"] = "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT"
    manifest["first_fresh_extra_audit"] = {
        "epoch_id": EPOCH, "notification_acknowledged": True,
        "first_fresh_after_change": True, "bound_package_id": INSTALL,
        "upload_hold_until_final_audit_pass": True,
    }
    manifest["v81_return_adjudication"] = {
        "formal_return_sha256": RETURN_SHA,
        "return_analysis_sha256": sha(ANALYSIS),
        "last_proven_good": "EXACT_SLICE13_GROUP1_MSE4_PHASE_TRIGGER_CONDITION_OCCURRED_13_TIMES",
        "first_divergence": "EXACT_TARGET_PHASE_EVENT_TO_POST_SIM_PHASE_PARSER_INPUT_PRESERVATION",
        "root_leaf_status": "PACKAGE_LOCAL_POST_SIM_COLLECTOR_ORDER_AND_LOG_MUTATION_DEFECT",
    }
    manifest["buffer_ack_phase_diagnostic"] = {
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "target_instance": TARGET,
        "payload_width_bits": 38,
        "required_binary_known": True,
        "sample_phases": ["ACTIVE", "INACTIVE_DELTA", "POSTNBA", "HALF_CYCLE", "NEXT_POSEDGE"],
        "collector_order": "PHASE_PARSE_AND_PERSIST_BEFORE_BOUNDED_SOURCE_BOUND_PROJECTION",
        "natural_terminal_or_formal_d_claim": False,
    }
    manifest["rule_change_ack"] = {
        "epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "rule_ids": [
            "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
            "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
            "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
        ],
        "upload_hold_until": "INDEPENDENT_EXTRA_AUDIT_PASS",
    }
    write(package / "diagnostics/rule_change_ack.json", {"schema":"conv-node0004-v82-rule-change-ack-v1","package_id":INSTALL,**manifest["rule_change_ack"]})
    write(package / "provenance/v81_return_to_v82_phase_collectfix.json", {
        "schema": "conv-node0004-v81-return-to-v82-phase-collectfix-v1",
        "source_package_zip_sha256": SOURCE_SHA,
        "formal_return_sha256": RETURN_SHA,
        "return_analysis_sha256": sha(ANALYSIS),
        "changed_surface": ["fresh identity", "post-sim phase parse-before-projection ordering", "38-bit binary-known phase payload ABI", "v2 exact-instance generated source-bound plan and fingerprint"],
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure", "functional RTL/ISA/hardware/active ndp-sim"],
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
    })
    old.base.refresh_receipts(manifest)
    manifest.setdefault("active_receipts", {})["source_bound_generator_sha256"] = sha(GENERATOR)
    manifest["active_receipts"]["exact_instance_payload_semantic_dispatch_sha256"] = sha(ROOT / "contracts/server_source_bound_observer_next_fresh_dispatch_v1.json")
    rules = manifest["active_receipts"].setdefault("rules", [])
    for rule in manifest["rule_change_ack"]["rule_ids"]:
        if rule not in rules:
            rules.append(rule)
    write(manifest_path, manifest)
    manifest["files"] = old.base.package_records(package)
    write(manifest_path, manifest)
    manifest["files"] = old.base.package_records(package)
    write(manifest_path, manifest)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUT / "build")
    args = parser.parse_args()
    out = args.output_root.resolve()
    package = build_directory(out)
    with tempfile.TemporaryDirectory(prefix="n4v82-repeat-") as raw:
        repeat = build_directory(Path(raw))
        if old.base.package_records(package) != old.base.package_records(repeat):
            raise BuildError("deterministic directory rebuild differs")
    archive = out / f"{INSTALL}.zip"
    old.base.deterministic_zip(package, archive)
    digest = sha(archive)
    sidecar = out / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-node0004-v82-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDIT",
        "package_id": INSTALL,
        "zip": str(archive), "zip_bytes": archive.stat().st_size, "zip_sha256": digest,
        "sidecar": str(sidecar), "deterministic_directory_rebuild_equal": True,
        "epoch_id": EPOCH, "first_fresh_after_change": True,
        "cheap_aggregate_invocations": 1, "final_zip_count": 1,
        "numeric_analysis_repeated": False, "workload_rebuilt": False,
        "configuration_rebuilt": False, "functional_rtl_modified": False, "server_action": False,
    }
    write(out / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
