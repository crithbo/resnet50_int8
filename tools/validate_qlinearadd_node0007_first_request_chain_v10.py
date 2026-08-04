from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


INSTALL_NAME = "r5_qadd_n7_first_request_chain_v10"
SOURCE_NAME = "r5_qadd_n7_progress_canon_v8"
PACKAGE_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
ZIP_SHA256 = (
    "573121def027a04b33650122e82d6c32cb8fbc4c9162cfc6cc831237a01869cf"
)
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "b74b18f906fbf32851ce016906c599889236e7088ad7209607e52368bad69100"
)
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
INDEX_SHA256 = (
    "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = (
    "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
)
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
QADD_RULE_SHA256 = (
    "c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b"
)
PARSER_REL = "package_tools/qlinearadd_progress_canonical_decision.py"
OBSERVER_REL = "tb_probe/native_return_observer.svh"
TAIL_REL = "tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh"
INCLUDE_LINE = (
    '`include "qlinearadd_node0007_first_request_observer_tail_v9.svh"'
)
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-first-request-chain-v10"
    / "report.json"
)
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rule_ids(path: Path) -> list[str]:
    return re.findall(
        r"规则 ID：`([^`]+)`", path.read_text(encoding="utf-8")
    )


def _load_zip(
    path: Path, expected_root: str
) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        infos = archive.infolist()
        unsafe = [
            info.filename
            for info in infos
            if (
                info.filename.startswith("/")
                or "\\" in info.filename
                or ".." in Path(info.filename).parts
            )
        ]
        duplicates = sorted(
            name
            for name in {info.filename for info in infos}
            if sum(item.filename == name for item in infos) != 1
        )
        members = {info.filename: archive.read(info) for info in infos}
    roots = sorted({name.split("/", 1)[0] for name in members})
    manifest_name = f"{expected_root}/TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(members[manifest_name])
    receipt = {
        "crc_valid": bad is None,
        "first_bad_crc_member": bad,
        "path_safe": not unsafe,
        "unsafe_members": unsafe,
        "duplicates_absent": not duplicates,
        "duplicate_members": duplicates,
        "root_exact": roots == [expected_root],
        "roots": roots,
    }
    return members, manifest, receipt


def _exact_set(
    members: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    root = f"{INSTALL_NAME}/"
    observed = {
        name[len(root) :]: {
            "size_bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
        for name, payload in members.items()
        if name.startswith(root)
        and name != root + "TEST_PACKAGE_MANIFEST.json"
    }
    expected = manifest.get("files", {})
    return {
        "valid": observed == expected,
        "missing": sorted(set(expected) - set(observed)),
        "extra": sorted(set(observed) - set(expected)),
        "changed": sorted(
            name
            for name in set(expected) & set(observed)
            if expected[name] != observed[name]
        ),
    }


def _workload_equivalence(
    source: dict[str, bytes], successor: dict[str, bytes]
) -> dict[str, Any]:
    old_prefix = f"{SOURCE_NAME}/workload/runtime/"
    new_prefix = f"{INSTALL_NAME}/workload/runtime/"
    old = {
        name[len(old_prefix) :]: payload
        for name, payload in source.items()
        if name.startswith(old_prefix)
    }
    new = {
        name[len(new_prefix) :]: payload
        for name, payload in successor.items()
        if name.startswith(new_prefix)
    }
    changed = []
    for name in sorted(set(old) & set(new)):
        normalized = new[name].replace(
            INSTALL_NAME.encode(), SOURCE_NAME.encode()
        )
        if normalized != old[name]:
            changed.append(name)
    return {
        "valid": (
            not changed and set(old) == set(new) and len(old) == len(new)
        ),
        "file_count": len(old),
        "changed_after_namespace_normalization": changed,
        "missing": sorted(set(old) - set(new)),
        "extra": sorted(set(new) - set(old)),
    }


def _required_allowlist_targets(manifest: dict[str, Any]) -> set[str]:
    return {
        str(item["target_path"])
        for item in manifest["return_allowlist"]
        if item.get("required") is True
    }


def _binding_errors(
    members: dict[str, bytes], manifest: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    root = f"{INSTALL_NAME}/"
    runner = members.get(root + "PREPARE_AND_RUN.sh", b"").decode(
        errors="replace"
    )
    base = members.get(root + OBSERVER_REL)
    tail = members.get(root + TAIL_REL)
    contract = manifest.get("first_request_internal_observability", {})
    required_targets = _required_allowlist_targets(manifest)
    if base is None or tail is None:
        errors.append("observer source exact-set is incomplete")
        return errors
    if contract.get("base_observer_path") != OBSERVER_REL:
        errors.append("base observer manifest path differs")
    if contract.get("tail_path") != TAIL_REL:
        errors.append("tail observer manifest path differs")
    if contract.get("base_observer_sha256") != sha256_bytes(base):
        errors.append("base observer manifest hash differs")
    if contract.get("tail_sha256") != sha256_bytes(tail):
        errors.append("tail observer manifest hash differs")
    base_text = base.decode(errors="replace")
    tail_text = tail.decode(errors="replace")
    if base_text.count(INCLUDE_LINE) != 1:
        errors.append("tail include binding is not unique")
    if "+incdir+$package_root/tb_probe" not in runner:
        errors.append("package-local observer include directory is absent")
    if "+define+NATIVE_RETURN_OBSERVER_ENABLE" not in runner:
        errors.append("observer compile enable macro is absent")
    if "+RETURN_OBSERVER" not in runner:
        errors.append("observer runtime plusarg is absent")
    if "# Native NDP return observer v4" not in base_text:
        errors.append("observer time-0 enabled marker is absent")
    if not all(
        f"trap 'signal_name={signal};" in runner
        for signal in ("HUP", "INT", "TERM")
    ):
        errors.append("signal-safe observer collection trap differs")
    required_returns = {
        "runs/return_observer.log",
        "evidence/actual_compile_argv.txt",
        "evidence/actual_simulator_argv.txt",
        "evidence/progress_samples.log",
        "evidence/observer_binding.txt",
        "evidence/CANONICAL_PROGRESS_DECISION.json",
        "evidence/canonical_decision_exit_status.txt",
    }
    if not required_returns <= required_targets:
        errors.append("observer runtime/return allowlist binding is incomplete")

    required_tail_tokens = (
        "FIRST_REQUEST_CHAIN",
        "qadd_fr_slice_start_run_prev",
        "!qadd_fr_slice_start_run_prev",
        "IGA_LC[2]",
        "IGA_LC[4]",
        "IGA_LC[6]",
        "IGA_LC[13]",
        "IGA_LC[18]",
        "mse_mem_queue_tag",
        "mse_mem_queue_bp_pre",
        "mem_all_idx_matched",
        "mem_ag_idx_queue_empty",
        "mem_ag_idx_queue_full",
        "mem_ag_idx_queue_wr_en",
        "mse_mem_ag_tag_valid",
        "mse_mem_ag_bp_post",
        "mem_ag_ob_vld_in",
        "mem_ag_ob_bp_pre",
        "mem_ag_ob_chl_hs",
    )
    missing_tokens = [
        token for token in required_tail_tokens if token not in tail_text
    ]
    if missing_tokens:
        errors.append(f"internal ready-chain tokens absent: {missing_tokens}")
    forbidden_drives = (
        "force ",
        "release ",
        "u_NDP_Top_new.",
    )
    # Hierarchical references are allowed only on the right-hand side.  A
    # direct procedural/continuous assignment into DUT would put the XMR
    # before '=' and is rejected separately.
    for line in tail_text.splitlines():
        stripped = line.strip()
        if (
            ("assign u_NDP_Top_new." in stripped)
            or re.match(r"u_NDP_Top_new\..*<=", stripped)
        ):
            errors.append("observer drives a DUT hierarchical signal")
            break
    if any(token in tail_text for token in forbidden_drives[:2]):
        errors.append("observer contains force/release")

    concatenated = base_text + "\n" + tail_text
    xmr_indices = re.findall(
        r"(?:slice_with_datahub_mc_group_gen|slice_group_gen|"
        r"MSE_INST|IGA_LC)\[([^\]]+)\]",
        concatenated,
    )
    allowed = {
        "0",
        "2",
        "4",
        "6",
        "13",
        "18",
        "return_obs_group",
        "return_obs_slice",
        "qadd_fr_group",
        "qadd_fr_slice",
    }
    if set(xmr_indices) - allowed:
        errors.append(
            "runtime/non-approved XMR instance index found: "
            f"{sorted(set(xmr_indices) - allowed)}"
        )
    for genvar in (
        "return_obs_group",
        "return_obs_slice",
        "qadd_fr_group",
        "qadd_fr_slice",
    ):
        if not re.search(rf"genvar\s+{genvar}\b", concatenated):
            errors.append(f"XMR instance index is not a declared genvar: {genvar}")
    return errors


def _bootstrap_receipt() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qadd-v10-bootstrap-") as name:
        destination = Path(name)
        with zipfile.ZipFile(ZIP_PATH) as archive:
            archive.extractall(destination)
        package = destination / INSTALL_NAME
        before = {
            path.relative_to(package).as_posix(): (
                path.stat().st_size,
                sha256_file(path),
            )
            for path in package.rglob("*")
            if path.is_file()
        }
        runtime = (
            package / "package_tools/qlinearadd_node0007_server_runtime.py"
        )
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(runtime),
                "preflight",
                "--package-root",
                str(package),
            ],
            cwd=package,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        after = {
            path.relative_to(package).as_posix(): (
                path.stat().st_size,
                sha256_file(path),
            )
            for path in package.rglob("*")
            if path.is_file()
        }
    return {
        "command": (
            "<current-python> -B package_tools/"
            "qlinearadd_node0007_server_runtime.py preflight "
            "--package-root <fresh-extract>"
        ),
        "exit_code": result.returncode,
        "stdout_is_json": result.stdout.lstrip().startswith("{"),
        "stderr": result.stderr,
        "package_tree_unchanged": before == after,
        "pycache_absent": not any(
            "__pycache__" in path or path.endswith(".pyc") for path in after
        ),
        "passed": (
            result.returncode == 0
            and before == after
            and not any(
                "__pycache__" in path or path.endswith(".pyc")
                for path in after
            )
        ),
    }


def _load_final_parser(payload: bytes) -> Any:
    with tempfile.TemporaryDirectory(prefix="qadd-v10-parser-") as name:
        path = Path(name) / "parser.py"
        path.write_bytes(payload)
        spec = importlib.util.spec_from_file_location(
            "qadd_v10_final_parser", path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot import final parser")
        module = importlib.util.module_from_spec(spec)
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
        return module


def _base_line(cycle: int, req: int = 0) -> str:
    return (
        f"{cycle} | HEARTBEAT | slice=0 active_cycles={cycle} "
        f"gexec=1 gconfig=0 req={req} rdata=0 wdata=0 "
        "buf4_wr=0 buf4_rd=0 buf5_wr=0 buf5_rd=0"
    )


def _chain_line(
    cycle: int, lc_hs: str = "0,0,0,0,0"
) -> str:
    return (
        f"{cycle} | FIRST_REQUEST_CHAIN | slice=0 active_cycles={cycle} "
        f"slice_start=1 lc_enable=0x1f lc_valid=0x1f lc_ready=0x1f "
        f"lc_hs={lc_hs} mse0_in_valid=0x7 mse0_in_ready=0x7 "
        "mse0_in_hs=0,0,0 mse0_match=0 mse0_empty=1 mse0_full=0 "
        "mse0_queue_wr=0 mse0_ag_valid=0 mse0_ag_ready=1 mse0_ag_hs=0 "
        "mse0_req_enq_valid=0 mse0_req_enq_ready=1 mse0_req_enq=0 "
        "mse4_in_valid=0x7 mse4_in_ready=0x7 mse4_in_hs=0,0,0 "
        "mse4_match=0 mse4_empty=1 mse4_full=0 mse4_queue_wr=0"
    )


def _observer_payload(*lines: str) -> bytes:
    return (
        "# Native NDP return observer v4 enabled\n"
        "0 | EXEC_START | slice=0 active_cycles=0 gexec=1 gconfig=0 "
        "req=0 rdata=0 wdata=0 buf4_wr=0 buf4_rd=0 "
        "buf5_wr=0 buf5_rd=0\n"
        + "\n".join(lines)
        + "\n"
    ).encode()


def _canonical_negative_controls(parser: Any) -> dict[str, Any]:
    base_payload = _observer_payload(
        _base_line(10),
        _chain_line(10),
        _base_line(110),
        _chain_line(110),
    )
    base_record = parser.decide(
        base_payload,
        stall_window_cycles=100,
        minimum_monotonic_windows=2,
    )
    controls: dict[str, Any] = {}

    high_level = base_record["decision"].startswith("LONG_RUNNING_HANG_AT_")
    controls["sustained_high_level_not_progress"] = {
        "exit_code": 1 if high_level else 0,
        "failed_closed": high_level,
        "observed_decision": base_record["decision"],
    }

    appended = parser.decide(
        base_payload + b"999 | SUMMARY_ONLY | decision=STILL_PROGRESSING\n",
        stall_window_cycles=100,
        minimum_monotonic_windows=2,
    )
    summary_ok = (
        appended["decision"] == base_record["decision"]
        and appended["content_summary"]["summary_only_lines_ignored"] == 1
    )
    controls["summary_only_append_ignored"] = {
        "exit_code": 1 if summary_ok else 0,
        "failed_closed": summary_ok,
    }

    two = (json.dumps(base_record) + "\n" + json.dumps(base_record)).encode()
    try:
        parser.load_unique_record(two)
        conflict_closed = False
    except Exception:
        conflict_closed = True
    controls["conflicting_double_decision"] = {
        "exit_code": 1 if conflict_closed else 0,
        "failed_closed": conflict_closed,
    }

    for field in ("reason", "boundary"):
        mutated = dict(base_record)
        mutated.pop(field)
        try:
            parser.load_unique_record(json.dumps(mutated).encode())
            closed = False
        except Exception:
            closed = True
        controls[f"missing_{field}"] = {
            "exit_code": 1 if closed else 0,
            "failed_closed": closed,
        }

    absent = parser.decide(
        _observer_payload(_base_line(10), _base_line(110)),
        stall_window_cycles=100,
        minimum_monotonic_windows=2,
    )
    closed = absent["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
    controls["missing_first_request_chain"] = {
        "exit_code": 1 if closed else 0,
        "failed_closed": closed,
        "observed_decision": absent["decision"],
    }
    return controls


def _binding_negative_controls(
    members: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    root = f"{INSTALL_NAME}/"
    controls: dict[str, Any] = {}

    def run(name: str, changed: dict[str, bytes], changed_manifest: dict[str, Any]) -> None:
        errors = _binding_errors(changed, changed_manifest)
        controls[name] = {
            "exit_code": 1 if errors else 0,
            "failed_closed": bool(errors),
            "first_error": errors[0] if errors else None,
        }

    changed = dict(members)
    changed.pop(root + OBSERVER_REL)
    run("delete_base_observer_source", changed, manifest)

    changed = dict(members)
    changed.pop(root + TAIL_REL)
    run("delete_tail_observer_source", changed, manifest)

    for name, old, new in (
        (
            "delete_incdir",
            "+incdir+$package_root/tb_probe",
            "+incdir+MISSING",
        ),
        (
            "delete_enable_macro",
            "+define+NATIVE_RETURN_OBSERVER_ENABLE",
            "+define+OBSERVER_DISABLED",
        ),
        ("delete_runtime_plusarg", "+RETURN_OBSERVER", "+OBSERVER_OFF"),
    ):
        changed = dict(members)
        runner_key = root + "PREPARE_AND_RUN.sh"
        changed[runner_key] = changed[runner_key].replace(
            old.encode(), new.encode()
        )
        run(name, changed, manifest)

    changed_manifest = json.loads(json.dumps(manifest))
    changed_manifest["return_allowlist"] = [
        item
        for item in changed_manifest["return_allowlist"]
        if item["target_path"] != "runs/return_observer.log"
    ]
    run("delete_runtime_return_binding", members, changed_manifest)

    changed = dict(members)
    changed[root + OBSERVER_REL] = changed[root + OBSERVER_REL].replace(
        INCLUDE_LINE.encode(), b""
    )
    run("delete_tail_include", changed, manifest)

    for name, token in (
        ("delete_active_lc_probe", b"IGA_LC[18]"),
        ("delete_mse_match_probe", b"mem_all_idx_matched"),
        ("delete_mse_queue_probe", b"mem_ag_idx_queue_empty"),
        ("delete_request_enqueue_probe", b"mem_ag_ob_chl_hs"),
        ("delete_slice_start_edge_witness", b"!qadd_fr_slice_start_run_prev"),
    ):
        changed = dict(members)
        changed[root + TAIL_REL] = changed[root + TAIL_REL].replace(
            token, b"MISSING_TOKEN"
        )
        run(name, changed, manifest)
    return controls


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    members, manifest, zip_structure = _load_zip(ZIP_PATH, INSTALL_NAME)
    source_members, _, source_structure = _load_zip(
        SOURCE_ZIP, SOURCE_NAME
    )
    root = f"{INSTALL_NAME}/"
    runner = members[root + "PREPARE_AND_RUN.sh"].decode(errors="replace")
    runtime = members[
        root + "package_tools/qlinearadd_node0007_server_runtime.py"
    ].decode(errors="replace")
    parser_payload = members[root + PARSER_REL]
    parser = _load_final_parser(parser_payload)
    exact_set = _exact_set(members, manifest)
    workload = _workload_equivalence(source_members, members)
    binding_errors = _binding_errors(members, manifest)
    binding_negatives = _binding_negative_controls(members, manifest)
    canonical_negatives = _canonical_negative_controls(parser)
    bootstrap = _bootstrap_receipt()
    build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))

    current_receipts = {
        "generation_index": {
            "path": INDEX.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(INDEX),
            "current_match": sha256_file(INDEX) == INDEX_SHA256,
        },
        "server_package_rule": {
            "path": SERVER_RULE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(SERVER_RULE),
            "current_match": sha256_file(SERVER_RULE) == SERVER_RULE_SHA256,
        },
        "qlinearadd_rule": {
            "path": QADD_RULE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(QADD_RULE),
            "current_match": sha256_file(QADD_RULE) == QADD_RULE_SHA256,
        },
    }
    audit = manifest.get("final_zip_rule_self_audit", {})
    rule_receipts_valid = (
        audit.get("rule_receipts") == current_receipts
        and all(item["current_match"] for item in current_receipts.values())
    )
    rule_ids_valid = (
        audit.get("applicable_server_rule_ids") == _rule_ids(SERVER_RULE)
        and audit.get("applicable_qlinearadd_rule_ids")
        == _rule_ids(QADD_RULE)
    )

    actual_zip_sha = sha256_file(ZIP_PATH)
    sidecar_text = SIDECAR_PATH.read_text(encoding="ascii")
    sidecar_valid = (
        sidecar_text
        == f"{actual_zip_sha}  {ZIP_PATH.name}\n"
        and actual_zip_sha == ZIP_SHA256
    )
    deterministic = (
        build.get("repeated_build", {}).get("package_tree_equal") is True
        and build.get("repeated_build", {}).get("zip_equal") is True
        and build.get("repeated_build", {}).get("repeat_zip_sha256")
        == ZIP_SHA256
    )
    required_targets = _required_allowlist_targets(manifest)
    formal_targets = {
        "workload/runtime/" + str(item["runtime_path"])
        for item in manifest["readback_checks"]
    }
    runtime_d_absent = not any(
        root + target in members for target in formal_targets
    )
    one_command = (
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        in members[root + "README.md"].decode(errors="replace")
        and runner.count('if [ "$#" -ne 1 ]') == 1
    )
    actual_sca_binding = (
        "+SCA_CFG=$cfg_rel/sca_cfg.json" in runner
        and "+SCA_CFG_D=$cfg_rel/sca_cfg_D.json" in runner
    )
    result_conjunction = (
        manifest.get("result_gate")
        == (
            "compile0 AND simulation0 AND natural_terminal AND loader_exact "
            "AND readback_exact_set AND missing0 AND mismatch0"
        )
        and "compile_status == 0" in runtime
        and "simulation_status == 0" in runtime
        and "natural_completion_exact" in runtime
        and "formal_readback_exact_set_complete" in runtime
        and "all_terms_true" in runtime
        and "missing_count" in runtime
        and "mismatch_count" in runtime
    )
    allowlist_valid = (
        len(manifest["return_allowlist"])
        == len(
            {
                str(item["target_path"])
                for item in manifest["return_allowlist"]
            }
        )
        and "MANIFEST_EXPLICIT_ALLOWLIST_ONLY"
        == manifest.get("return_collection_policy")
        and "return_allowlist" in runtime
    )
    default_progress = manifest.get("default_progress_diagnostics", {})
    progress_valid = (
        default_progress.get("enabled_by_default") is True
        and default_progress.get("read_only") is True
        and default_progress.get("rate_limited") is True
        and default_progress.get("changes_dut_input") is False
        and default_progress.get("changes_ready_or_backpressure") is False
        and default_progress.get("changes_timeout") is False
        and {
            "evidence/host_timing.txt",
            "runs/return_observer.log",
            "evidence/CANONICAL_PROGRESS_DECISION.json",
        }
        <= required_targets
    )
    parser_manifest = manifest.get("canonical_decision_contract", {})
    parser_valid = (
        parser_manifest.get("schema")
        == "qlinearadd-first-request-canonical-decision-v1"
        and parser_manifest.get("parser_path") == PARSER_REL
        and parser_manifest.get("parser_sha256")
        == sha256_bytes(parser_payload)
        and parser_manifest.get("unique_complete_record_required") is True
    )
    no_forbidden_entries = not any(
        (
            "/rtl/" in name
            or name.endswith((".v", ".sv"))
            or "/csrc/" in name
            or "/simv.daidir/" in name
            or name.endswith((".vcd", ".fsdb", ".zip"))
        )
        for name in members
    )
    no_server_source_preflight = (
        manifest.get("server_source_preflight_performed") is False
        and "server_source_inspected" not in runner
        and "git " not in runner
        and "find " not in runner
    )
    all_negatives = all(
        item["failed_closed"]
        for family in (binding_negatives, canonical_negatives)
        for item in family.values()
    )

    checks = {
        "zip_sha_and_sidecar": sidecar_valid,
        "zip_crc_path_root": (
            zip_structure["crc_valid"]
            and zip_structure["path_safe"]
            and zip_structure["duplicates_absent"]
            and zip_structure["root_exact"]
            and source_structure["crc_valid"]
            and source_structure["path_safe"]
            and source_structure["duplicates_absent"]
            and source_structure["root_exact"]
        ),
        "source_zip_identity": sha256_file(SOURCE_ZIP)
        == SOURCE_ZIP_SHA256,
        "exact_set": exact_set["valid"],
        "deterministic_double_build": deterministic,
        "bootstrap_immutability": bootstrap["passed"],
        "frozen_workload_equivalence": workload["valid"],
        "manifest_identity": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("claim")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
        ),
        "rule_receipts_current": rule_receipts_valid,
        "all_rule_ids_bound": rule_ids_valid,
        "one_command": one_command,
        "no_server_source_preflight": no_server_source_preflight,
        "runtime_d_absent": runtime_d_absent,
        "sca_and_sca_d_bound": actual_sca_binding,
        "result_gate_conjunction": result_conjunction,
        "return_allowlist": allowlist_valid,
        "default_progress_diagnostics": progress_valid,
        "observer_four_way_and_internal_chain": not binding_errors,
        "canonical_parser": parser_valid,
        "forbidden_entries_absent": no_forbidden_entries,
        "all_negative_controls_fail_closed": all_negatives,
    }
    errors = [name for name, passed in checks.items() if not passed]
    errors.extend(f"observer: {error}" for error in binding_errors)
    passed = not errors
    report: dict[str, Any] = {
        "schema": (
            "qlinearadd-node0007-first-request-chain-"
            "final-zip-self-audit-v1"
        ),
        "status": (
            "PACKAGE_READY_NOT_RUN"
            if passed
            else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
        ),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
        "errors": errors,
        "error_count": len(errors),
        "checks": checks,
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": actual_zip_sha,
        "zip_bytes": ZIP_PATH.stat().st_size,
        "sidecar": SIDECAR_PATH.relative_to(ROOT).as_posix(),
        "sidecar_sha256": sha256_file(SIDECAR_PATH),
        "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "source_zip_sha256": sha256_file(SOURCE_ZIP),
        "zip_structure": zip_structure,
        "exact_set": exact_set,
        "frozen_workload_equivalence": workload,
        "bootstrap_receipt": bootstrap,
        "rule_receipts": current_receipts,
        "server_rule_ids": _rule_ids(SERVER_RULE),
        "qlinearadd_rule_ids": _rule_ids(QADD_RULE),
        "binding_errors": binding_errors,
        "four_way_and_chain_negative_controls": binding_negatives,
        "canonical_negative_controls": canonical_negatives,
        "all_required_negative_controls_fail_closed": all_negatives,
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "server_action": False,
        "functional_fix": False,
        "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "evidence_level": "E2_LOCAL_ONLY",
        "unique_server_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        ),
        "expected_return": f"{INSTALL_NAME}_return.zip",
        "expected_return_sidecar": f"{INSTALL_NAME}_return.zip.sha256",
        "v9_status": (
            "QUARANTINED_NOT_RUN_EVENT_QUALIFICATION_SELF_AUDIT"
        ),
        "v6_v7_v8_status": "QUARANTINED",
    }
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        build["status"] = report["status"]
        build["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = passed
        build["final_self_audit_report"] = REPORT_PATH.relative_to(
            ROOT
        ).as_posix()
        build["final_self_audit_report_sha256"] = sha256_file(REPORT_PATH)
        BUILD_RECEIPT.write_text(
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = validate_final_zip()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
