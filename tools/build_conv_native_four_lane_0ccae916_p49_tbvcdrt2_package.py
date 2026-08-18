#!/usr/bin/env python3
"""Build the p48-return-driven native-Conv TB-VCD runtime-v3 successor."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "tools/build_conv_native_four_lane_0ccae916_p47_tbvcdcone_package.py"
P48 = "r5_n4_0cc_p48_xmrscopefix"
PACKAGE = "r5_n4_0cc_p49_tbvcdrt2"
EPOCH = "tb-vcd-exit-mechanism-consistency-v3"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "pending" / f"{P48}.zip"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_release"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
ANALYSIS = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_return_analysis_"
    "r1786704774390782459_2297616"
)


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("conv_native_p47_builder", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import native Conv TB-VCD builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_extract_p48(builder: Any, source: Path) -> None:
    build_parent = builder.TREE.parent
    if builder.OUT.exists():
        shutil.rmtree(builder.OUT)
    build_parent.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("p48 source ZIP CRC failure")
        roots = {
            PurePosixPath(item.filename).parts[0]
            for item in archive.infolist()
            if item.filename
        }
        if roots != {P48}:
            raise RuntimeError(f"p48 source root differs: {roots}")
        old_tree = build_parent / P48
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                raise RuntimeError(f"unsafe source member: {info.filename}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"source symlink forbidden: {info.filename}")
            target = build_parent.joinpath(*pure.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
        builder.TREE.mkdir(parents=True)
        for child in old_tree.iterdir():
            target = builder.TREE / child.name
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)
        shutil.rmtree(old_tree)


def exact_tb(builder: Any, signals: list[dict[str, Any]]) -> str:
    source = builder.tb_source()
    invalid = tuple(
        f".MSE_INST[{index}].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish"
        for index in (5, 6, 7)
    )
    source = "\n".join(
        line for line in source.splitlines() if not any(token in line for token in invalid)
    ) + "\n"
    first = source.index("      $dumpvars(")
    last = source.index("      $dumpon;", first)
    dump_rows = "\n".join(
        f"      $dumpvars(0, {item['exact_hierarchy']});" for item in signals
    )
    source = source[:first] + dump_rows + "\n" + source[last:]
    source = source.replace("CODEX_TBVCD_START_V1", "CODEX_TBVCD_START_V2")
    source = source.replace("CODEX_TBVCD_PLATEAU_SUSPECT_V1", "CODEX_TBVCD_PLATEAU_SUSPECT_V2")
    source = source.replace("CODEX_TBVCD_DUMPOFF_V1", "CODEX_TBVCD_DUMPOFF_V2")
    source = source.replace("CODEX_TBVCD_STOP_V1", "CODEX_TBVCD_STOP_V2")
    source = source.replace("CODEX_TBVCD_TERMINAL_WITNESS_V1", "CODEX_TBVCD_TERMINAL_WITNESS_V2")
    source = source.replace("CODEX_TBVCD_FLUSH_V1", "CODEX_TBVCD_FLUSH_V2")
    source = source.replace(
        "  logic [7:0] codex_previous_global;",
        "  logic [7:0] codex_previous_global;\n  logic codex_target_entry_seen;",
        1,
    )
    source = source.replace(
        "    codex_previous_global = 'x;",
        "    codex_previous_global = 'x;\n    codex_target_entry_seen = 0;",
        1,
    )
    source = source.replace(
        "  always @(posedge clk) if (codex_enabled) begin\n    codex_cycles <= codex_cycles + 1;",
        "  always @(posedge clk) if (codex_enabled) begin\n"
        "    codex_cycles <= codex_cycles + 1;\n"
        "    if (mse_enable && !codex_target_entry_seen) begin\n"
        "      codex_target_entry_seen <= 1;\n"
        "      $display(\"CODEX_TBVCD_TARGET_ENTRY_V2 sim_time=%0t owner_cycles=%0d\", $time, codex_cycles);\n"
        "    end",
        1,
    )
    old_heartbeat = (
        "    if ((codex_cycles & 262143) == 0)\n"
        "      $display(\"CODEX_TBVCD_HEARTBEAT_V1 sim_time=%0t owner_cycles=%0d progress=%0d "
        "state=%016h global=%0d unresolved_xz=%0d\", $time, codex_cycles, codex_progress, "
        "codex_fold(codex_state), codex_global_progress, codex_unresolved_xz);"
    )
    new_heartbeat = (
        "    if ((codex_cycles & 64'h3fff) == 0)\n"
        "      $display(\"CODEX_TBVCD_HEARTBEAT_V2 sim_time=%0t owner_cycles=%0d progress=%0d "
        "state=%016h global=%0d unresolved_xz=%0d target_entry=%0d\", $time, codex_cycles, "
        "codex_progress, codex_fold(codex_state), codex_global_progress, codex_unresolved_xz, "
        "codex_target_entry_seen || mse_enable);"
    )
    if old_heartbeat not in source:
        raise RuntimeError("p48 heartbeat replacement anchor absent")
    source = source.replace(old_heartbeat, new_heartbeat, 1)
    old_finish = (
        '        $display("CODEX_TBVCD_STOP_V2 reason=CAUSAL_PLATEAU sim_time=%0t owner_cycles=%0d", '
        '$time, codex_cycles);\n'
        '        $finish;'
    )
    new_finish = (
        '        $display("CODEX_TBVCD_STOP_V2 reason=CAUSAL_PLATEAU sim_time=%0t owner_cycles=%0d", '
        '$time, codex_cycles);\n'
        '        // The shared packaged runtime evaluator is the sole outer stop authority.'
    )
    if old_finish not in source:
        raise RuntimeError("p48 package-local plateau finish anchor absent")
    source = source.replace(old_finish, new_finish, 1)
    return source


def exact_contract(
    builder: Any, signals: list[dict[str, Any]], tb_path: Path
) -> dict[str, Any]:
    contract = builder.vcd_contract(signals, tb_path)
    ids = [item["signal_id"] for item in signals]
    contract["package_id"] = PACKAGE
    contract["execution"]["dump_targeting"] = {
        "mode": "EXACT_CATALOG_SIGNALS",
        "module_scope_dump": False,
        "dumpvars_depth": 0,
        "signal_ids": ids,
    }
    boundaries = contract["boundaries"]
    membership = {
        item["signal_id"]: [
            boundary["boundary_id"]
            for boundary in boundaries
            if item["signal_id"] in boundary["signal_ids"]
        ]
        for item in signals
    }
    contract["scope"]["dump_scopes"] = [
        {
            "scope_id": f"exact_{item['signal_id']}",
            "exact_hierarchy": item["exact_hierarchy"],
            "depth": 0,
            "boundary_ids": membership[item["signal_id"]] or [boundaries[0]["boundary_id"]],
            "source_bound_signal_ids": [item["signal_id"]],
        }
        for item in signals
    ]
    contract["runtime_policy"].update(
        {
            "heartbeat_source": "APPENDED_VCD_TIMESTAMP",
            "heartbeat_width_bits": 64,
            "heartbeat_signed": False,
            "heartbeat_cadence_cycles": 16_384,
            "decision_authority": "SHARED_RUNTIME_EVALUATOR_ONLY",
            "outer_runner_independent_exit_logic": False,
            "required_replay_cases": [
                "ADVANCING_VCD_TIMESTAMP",
                "PLATEAU_SUSPECTED_ONLY",
                "PLATEAU_DUMP_OFF_PLUS_GRACE",
                "THREE_INTERVAL_TRUE_FREEZE",
            ],
            "archive_timestamp_binding": "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT",
        }
    )
    contract["claim_boundary"] = (
        "p48-return-driven runtime-v3 exact-signal bounded causal-cone transport only; local gates do not "
        "establish production execution, root cause, natural terminal, formal D, E3, E4 or E5."
    )
    return contract


def update_manifest(builder: Any, contract_path: Path, selector_path: Path) -> None:
    manifest_path = builder.TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "conv-native-four-lane-p49-tb-vcd-runtime-v3-package-v1",
            "package_identity": PACKAGE,
            "install_name": PACKAGE,
            "status": "PACKAGE_READY_NOT_RUN",
            "activation_epoch": EPOCH,
            "source_package": P48,
            "previous_version_progress": (
                "p41 proved production compile beyond Datahub; p42 fixed the two-bit vector predicate; p46 proved "
                "descriptor/buffer/MemAG/wdata accepts; p48 compiled and advanced VCD to 303783125 ps but a stale "
                "display-heartbeat false freeze stopped matrix preload before MSE4 target entry."
            ),
            "current_version_purpose": (
                "Preserve the p42 predicate and MSE4 FIFO/outstanding/last/FSM/drain/finish target while applying "
                "current runtime-v3 sole-shared-evaluator, archive-bound appended timestamp, exact-signal, "
                "64-bit heartbeat and partial/flush/reap gates."
            ),
            "vcd_contract_sha256": builder.sha(contract_path),
            "mode_selector_sha256": builder.sha(selector_path),
            "package_build_failure_rule_audit": "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
            "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
            "server_actions_performed": [],
        }
    )
    manifest["files"] = {
        path.relative_to(builder.TREE).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": builder.sha(path),
        }
        for path in sorted(item for item in builder.TREE.rglob("*") if item.is_file())
        if path != manifest_path
    }
    manifest_path.write_bytes(builder.canonical(manifest))


def main() -> int:
    if not SOURCE_ZIP.is_file():
        raise RuntimeError("protected p48 pending ZIP is absent")
    if not (ANALYSIS / "formal_return_analysis.json").is_file():
        raise RuntimeError("p48 formal return analysis is absent")
    if not (ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json").is_file():
        raise RuntimeError("mandatory package-build-failure audit is absent")
    audit = json.loads(
        (ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json").read_text(encoding="utf-8")
    )
    if audit.get("rule_disposition") != "RULE_CONFIRMATION_NO_CHANGE":
        raise RuntimeError("p48 package-build-failure audit disposition differs")

    builder = load_base()
    builder.PACKAGE_ID = PACKAGE
    builder.ACTIVATION_EPOCH = EPOCH
    builder.SOURCE_ZIP = SOURCE_ZIP
    builder.OUT = OUT
    builder.TREE = TREE
    builder.ZIP = ZIP
    builder.safe_extract = lambda source: safe_extract_p48(builder, source)
    builder.build()

    signals = builder.build_signals()
    tb_path = TREE / "tb_probe/native_mse4_bounded_causal_cone_vcd.sv"
    tb_path.write_text(exact_tb(builder, signals), encoding="utf-8", newline="\n")
    shutil.copyfile(
        ROOT / "tools/conv_native_p49_tb_vcd_live_supervision.py",
        TREE / "package_tools/tb_vcd_live_supervision.py",
    )
    shutil.copyfile(
        ROOT / "tools/conv_native_p49_tb_vcd_finalize.py",
        TREE / "package_tools/tb_vcd_finalize.py",
    )
    shutil.copyfile(
        ROOT / "tools/server_tb_vcd_runtime_supervision.py",
        TREE / "package_tools/server_tb_vcd_runtime_supervision.py",
    )
    shutil.copyfile(
        ROOT / "tools/conv_native_p49_package_release_preflight.py",
        TREE / "package_tools/package_release_preflight.py",
    )
    for path in (
        TREE / "package_tools/tb_vcd_live_supervision.py",
        TREE / "package_tools/tb_vcd_finalize.py",
        TREE / "package_tools/package_release_preflight.py",
    ):
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    old_live = (
        '--process-supervisor "$package_root/package_tools/server_process_tree_supervision.py" '
        '--sim-log "$run_root/c0/sim.log"'
    )
    new_live = (
        '--process-supervisor "$package_root/package_tools/server_process_tree_supervision.py" '
        '--runtime-evaluator "$package_root/package_tools/server_tb_vcd_runtime_supervision.py" '
        '--decision-receipt "$evidence_root/TB_VCD_LIVE_DECISION_RECEIPT.json" '
        '--sim-log "$run_root/c0/sim.log"'
    )
    if old_live not in runner:
        raise RuntimeError("p49 live shared-evaluator runner anchor absent")
    runner = runner.replace(old_live, new_live, 1)
    runner_path.write_text(runner, encoding="utf-8", newline="\n")
    runner_sha = builder.sha(runner_path)
    runner_contract_path = TREE / "server_runner_return_resilience_contract.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["runner_sha256"] = runner_sha
    runner_contract["return_allowlist_tokens"] = sorted(
        set(runner_contract.get("return_allowlist_tokens", []))
        | {"TB_VCD_LIVE_DECISION_RECEIPT.json"}
    )
    runner_contract_path.write_bytes(builder.canonical(runner_contract))
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["runner_sha256"] = runner_sha
    layout_path.write_bytes(builder.canonical(layout))

    provenance = TREE / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        ANALYSIS / "formal_return_analysis.json", provenance / "p48_formal_return_analysis.json"
    )
    shutil.copyfile(
        ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        provenance / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
    )
    builder.write_json(
        "provenance/p48_to_p49_runtime_v3.json",
        {
            "schema": "conv-native-p48-to-p49-runtime-v3-v1",
            "source_package": P48,
            "package_id": PACKAGE,
            "classification": "PACKAGE_LOCAL_TBVCD_FALSE_FREEZE_RUNTIME_ESCAPE",
            "changed_surfaces": [
                "fresh identity",
                "exact catalog signal dump",
                "appended VCD timestamp supervisor",
                "unsigned 64-bit 16384-cycle heartbeat",
                "partial/flush/reap/exact-set finalization",
            ],
            "frozen_surfaces": [
                "config",
                "numeric",
                "workload",
                "golden",
                "functional RTL",
                "p42 vector predicate",
                "MSE4 causal target",
            ],
            "server_actions_performed": [],
        },
    )

    catalog_path = TREE / "diagnostics/tb_vcd_causal_signal_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["schema"] = "conv-native-p49-tb-vcd-causal-signal-catalog-v1"
    catalog["package_id"] = PACKAGE
    catalog_path.write_bytes(builder.canonical(catalog))
    contract = exact_contract(builder, signals, tb_path)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract_path.write_bytes(builder.canonical(contract))
    matrix_path = TREE / "diagnostics/tb_vcd_candidate_boundary_matrix.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix["schema"] = "conv-native-p49-candidate-boundary-matrix-v1"
    matrix["package_id"] = PACKAGE
    matrix_path.write_bytes(builder.canonical(matrix))
    builder.write_json(
        "diagnostics/tb_vcd_exact_dump_plan.json",
        {
            "schema": "conv-native-p49-tb-vcd-exact-dump-plan-v1",
            "package_id": PACKAGE,
            "strategy": "EXPLICIT_SOURCE_BOUND_SIGNAL_ONLY",
            "signal_count": len(signals),
            "signal_ids": [item["signal_id"] for item in signals],
            "exact_hierarchies": [item["exact_hierarchy"] for item in signals],
            "module_scope_dump_forbidden": True,
            "uncataloged_signal_forbidden": True,
            "pass": True,
        },
    )

    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = builder.selector(contract_path)
    selector["package_id"] = PACKAGE
    selector["return_members"] = sorted(
        set(selector["return_members"])
        | {
            "evidence/TB_VCD_RETURN_EXACT_SET.json",
            "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json",
        }
    )
    selector_path.write_bytes(builder.canonical(selector))
    request = builder.post_request()
    request["package_id"] = PACKAGE
    additions = [
        {
            "source_root": "attempt",
            "source": "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json",
            "archive": "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json",
            "required": True,
        },
        {
            "source_root": "attempt",
            "source": "evidence/TB_VCD_RETURN_EXACT_SET.json",
            "archive": "evidence/TB_VCD_RETURN_EXACT_SET.json",
            "required": True,
        },
        {
            "source_root": "attempt",
            "source": "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json",
            "archive": "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json",
            "required": True,
        },
    ]
    existing_archives = {row["archive"] for row in request["core_entries"]}
    request["core_entries"].extend(
        row for row in additions if row["archive"] not in existing_archives
    )
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request_path.write_bytes(builder.canonical(request))
    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["request_sha256"] = builder.sha(request_path)
    post_contract["runner_sha256"] = builder.sha(runner_path)
    post_contract_path.write_bytes(builder.canonical(post_contract))

    root = f"{PACKAGE}_return/"
    required_return = [
        root + row["archive"] for row in request["core_entries"] if row.get("required") is True
    ]
    required_return += [
        root + "RETURN_CORE_MANIFEST.json",
        root + "return_core/SIM_EXIT_RECEIPT.json",
        root + "return_core/RETURN_CORE_STATUS.json",
    ]
    allowlist_path = TREE / "RETURN_ALLOWLIST.json"
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    allowlist.update(
        {
            "schema": "conv-native-p49-tb-vcd-return-allowlist-v1",
            "package_id": PACKAGE,
            "required": sorted(set(required_return)),
            "vcd_member": root + "runs/c0/native_mse4_causal.vcd",
            "no_size_limit": True,
            "no_truncation": True,
            "no_sampling": True,
        }
    )
    allowlist_path.write_bytes(builder.canonical(allowlist))
    pointer_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer.update(
        {
            "schema": "conv-native-four-lane-p49-tb-vcd-runtime-v3-pointer-v1",
            "package_identity": PACKAGE,
            "activation_epoch": EPOCH,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    pointer_path.write_bytes(builder.canonical(pointer))
    (TREE / "README.md").write_text(
        f"# {PACKAGE}\n\n"
        "Previous progress: p41 passed production compile beyond Datahub, p42 fixed the vector predicate, p46 "
        "proved descriptor/buffer/MemAG/wdata accepts, and p48 passed compile but falsely stopped during matrix "
        "preload while appended VCD time still advanced.\n\n"
        "Current purpose: preserve the p42/MSE4 target and run the exact-signal bounded causal cone under "
        "runtime-v3 appended-timestamp supervision, unsigned 64-bit 16384-cycle heartbeat and fail-closed "
        "partial/flush/reap/exact-set return. The byte-equal shared evaluator is the sole outer stop authority.\n\n"
        f"Only after separate server authorization: `bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "DUMP_VCD=0, DUMP_FSDB=0 and TB_DUMP_FSDB=0 remain fixed. No server action was performed.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(builder, contract_path, selector_path)
    builder.deterministic_zip(ZIP)
    builder.deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic exact-ZIP recomputation differs")
    build_receipt = {
        "schema": "conv-native-p49-tb-vcd-runtime-v3-build-v1",
        "package_id": PACKAGE,
        "family": "conv_native_four_lane",
        "activation_epoch": EPOCH,
        "source_p48_pending": builder.identity(SOURCE_ZIP),
        "formal_return_analysis": builder.identity(ANALYSIS / "formal_return_analysis.json"),
        "package_build_failure_rule_audit": builder.identity(
            ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
        ),
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "zip": builder.identity(ZIP),
        "repeat_zip": builder.identity(REPEAT),
        "frozen_surfaces": [
            "config",
            "numeric",
            "workload",
            "golden",
            "functional_rtl",
            "p42_vector_predicate",
            "MSE4_target",
        ],
        "server_actions_performed": [],
        "pass": True,
        "errors": [],
    }
    (OUT / "build_receipt.json").write_bytes(builder.canonical(build_receipt))
    print(json.dumps({"package_id": PACKAGE, "zip": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
