#!/usr/bin/env python3
"""Current-rule final-ZIP audit for the node0071 -> node0075 v9 package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_n75_0cc_bankrow_v9"
PACKAGE_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages" / NAME
)
ZIP_PATH = PACKAGE_ROOT.with_suffix(".zip")
SIDECAR = Path(str(ZIP_PATH) + ".sha256")
BUILD_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-0ccae91-bankrow-package-v9/build_report.json"
)
OUTPUT = BUILD_REPORT.parent / "final_zip_self_audit.json"
BASE_PATH = (
    ROOT
    / "tools/audit_node0071_node0075_e1fb0f7_native_ordering_v5_final_zip.py"
)
SPEC = importlib.util.spec_from_file_location("node0071_node0075_v5_audit", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load v5 audit helpers")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.NAME = NAME
BASE.PACKAGE_ROOT = PACKAGE_ROOT
BASE.ZIP_PATH = ZIP_PATH
BASE.SIDECAR = SIDECAR
BASE.BUILD_REPORT = BUILD_REPORT

V5_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_n75_e1f_native_v5"
)
V5_AUDIT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-ordering-package-v5/"
    "final_zip_self_audit.json"
)
V5_RETURN = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-v5-return-analysis/report.json"
)
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
LOCAL_HINT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"


class AuditError(RuntimeError):
    pass


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def physical_bank_row(addr: int) -> dict[str, int | bool]:
    local_byte = addr & 0x01FFFFFF
    line = local_byte >> 4
    bank = (line >> 19) & 0x3
    row = (line >> 6) & 0x1FFF
    col = line & 0x3F
    return {
        "bank": bank,
        "row": row,
        "col": col,
        "enabled": row < 6144,
    }


def materialized_address_gate(package: Path) -> dict[str, Any]:
    sca = load_json(package / "workload/sca_cfg.json")
    sca_d = load_json(package / "workload/sca_cfg_D.json")
    intervals: list[dict[str, Any]] = []

    def add(name: str, base: int, line_count: int, kind: str) -> None:
        first = physical_bank_row(base)
        last = physical_bank_row(base + 16 * (line_count - 1))
        bad = []
        for line_index in range(line_count):
            decoded = physical_bank_row(base + 16 * line_index)
            if not decoded["enabled"]:
                bad.append({"line_index": line_index, **decoded})
                if len(bad) == 8:
                    break
        intervals.append(
            {
                "name": name,
                "kind": kind,
                "base_addr": f"0x{base:08X}",
                "line_count": line_count,
                "first": first,
                "last": last,
                "invalid_sample": bad,
                "valid": not bad,
            }
        )

    exec_base = int(str(sca["Exec_Base"]), 16)
    add("ExecutionPlan", exec_base, int(sca["Exec_Length"]), "execplan")
    for name, item in sorted(sca.items()):
        if not name.endswith("_cfg"):
            continue
        path = package / PurePosixPath(str(item["path"])).name
        path = package / "workload/c" / (
            ("71s" + name[5:7] + ".bin")
            if name.startswith("n71_s")
            else (
                "75"
                + {"a": "a", "s": "s", "r": "r"}[name[4]]
                + name[5:7]
                + ".bin"
            )
        )
        if not path.is_file():
            raise AuditError(f"config payload path resolution failed: {name}")
        line_count = len(path.read_bytes().splitlines())
        add(name, int(str(item["base_addr"]), 16), line_count, "config")
    for name, item in sorted(sca_d.items()):
        add(
            name,
            int(str(item["base_addr"]), 16),
            int(item["length"]),
            "formal_d",
        )
    valid = (
        sca["Exec_Base"] == "0x002ACC00"
        and sca["ExecutionPlan"]["base_addr"] == "0x002ACC00"
        and len(intervals) == 177
        and all(item["valid"] for item in intervals)
    )
    return {
        "valid": valid,
        "address_fields": {
            "slice_local_byte_mask": "0x01FFFFFF",
            "line_shift": 4,
            "bank_bits": "[20:19]",
            "row_bits": "[18:6]",
            "col_bits": "[5:0]",
            "enabled_row_predicate": "row < 6144",
        },
        "exec_base": sca["Exec_Base"],
        "interval_count": len(intervals),
        "invalid_interval_count": sum(not item["valid"] for item in intervals),
        "intervals": intervals,
    }


def allowlist_gate(manifest: dict[str, Any], runtime: str) -> dict[str, Any]:
    contract = manifest["return_allowlist"]
    records = contract["records"]
    destinations = [str(item["destination"]) for item in records]
    formal = [item for item in records if item["source_scope"] == "server"]
    schema = all(
        item["source_scope"] in {"package", "evidence", "run", "server"}
        and isinstance(item["required"], bool)
        and isinstance(item["max_bytes"], int)
        and item["max_bytes"] > 0
        and item["copy_mode"] in {"exact", "head_tail"}
        and bool(item["missing_semantics"])
        for item in records
    )
    valid = (
        contract["schema"]
        == "node0071-node0075-native-ordering-return-allowlist-v1"
        and len(records) == 162
        and len(destinations) == len(set(destinations))
        and len(formal) == 144
        and "e/observer_binding.txt" in destinations
        and schema
        and "allowlist = _return_allowlist_records(manifest)" in runtime
        and "for item in allowlist:" in runtime
        and "required_sources = {" not in runtime
    )
    return {
        "valid": valid,
        "record_count": len(records),
        "formal_d_record_count": len(formal),
        "duplicate_destination_count": len(destinations) - len(set(destinations)),
        "cloud_identity_carrier_returned": "e/observer_binding.txt" in destinations,
    }


def rule_receipt_gate(manifest: dict[str, Any]) -> dict[str, Any]:
    records = []
    for item in manifest["rule_receipts"]:
        relative = str(item["path"])
        path = ROOT / PurePosixPath(relative)
        observed = sha(path) if path.is_file() else None
        records.append(
            {
                "path": relative,
                "package_sha256": item["sha256"],
                "observed_sha256": observed,
                "match": observed == item["sha256"],
            }
        )
    return {"valid": bool(records) and all(item["match"] for item in records), "records": records}


def receipt_reuse_gate(package: Path) -> dict[str, Any]:
    audit = load_json(V5_AUDIT)
    pairs = {}
    for current_relative, frozen_relative in (
        ("obs/native_return_observer.svh", "obs/native_return_observer.svh"),
        ("pkg/runtime_base.py", "pkg/runtime.py"),
    ):
        current = package / current_relative
        frozen = V5_PACKAGE / frozen_relative
        pairs[current_relative] = {
            "current_sha256": sha(current),
            "v5_sha256": sha(frozen),
            "byte_equal": current.read_bytes() == frozen.read_bytes(),
        }
    wrapper_text = (package / "pkg/runtime.py").read_text(encoding="utf-8")
    wrapper_guard = (
        wrapper_text.count('old = \'sca.get("Exec_Base") != "0x01706400"\'') == 1
        and wrapper_text.count('new = \'sca.get("Exec_Base") != "0x002ACC00"\'') == 1
        and "source.replace(old, new, 1)" in wrapper_text
    )
    valid = (
        audit.get("valid") is True
        and audit["package_local_hdl_gate"]["pass"] is True
        and audit["diagnostic_predicate_trace_gate"]["pass"] is True
        and all(item["byte_equal"] for item in pairs.values())
        and wrapper_guard
    )
    return {
        "valid": valid,
        "v5_audit": {
            "path": V5_AUDIT.relative_to(ROOT).as_posix(),
            "sha256": sha(V5_AUDIT),
            "status": audit.get("status"),
        },
        "byte_equal_members": pairs,
        "materialized_config_wrapper_exact_guard": wrapper_guard,
        "claim": (
            "observer/parser/canonical bytes are frozen; no diagnostic predicate "
            "trace or numeric/golden rerun is applicable"
        ),
    }


def make_cloud_nonblocking_stubs(
    root: Path, sim_marker: Path, run_dir: Path
) -> Path:
    stub_bin = root / "stub-bin"
    stub_bin.mkdir(parents=True)
    python_stub = stub_bin / "python3"
    python_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{Path(sys.executable).resolve().as_posix()}" -B "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    creator = root / "create_simv.py"
    simv_text = (
        "#!/usr/bin/env bash\n"
        f"printf 'SIMULATOR_STUB_REACHED\\n' >'{BASE.git_bash_path(sim_marker)}'\n"
        "observer=''\n"
        "for arg in \"$@\"; do case \"$arg\" in "
        "+RETURN_OBS_FILE=*) observer=\"${arg#*=}\";; esac; done\n"
        "if [ -n \"$observer\" ]; then\n"
        "  printf 'N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1\\n' "
        ">\"$observer\"\n"
        "fi\n"
        "exit 87\n"
    )
    creator.write_text(
        "import os\n"
        "from pathlib import Path\n"
        f"path=Path({str(run_dir / 'sim_results/simv')!r})\n"
        "path.parent.mkdir(parents=True,exist_ok=True)\n"
        f"path.write_text({simv_text!r},encoding='utf-8',newline='\\n')\n"
        "os.chmod(path,0o755)\n",
        encoding="utf-8",
        newline="\n",
    )
    make_stub = stub_bin / "make"
    make_stub.write_text(
        "#!/usr/bin/env bash\n"
        f"python3 '{BASE.git_bash_path(creator)}' || exit 70\n"
        "echo SAFE_COMPILE_ZERO_STUB_REACHED\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(python_stub, 0o755)
    os.chmod(make_stub, 0o755)
    return stub_bin


def cloud_nonblocking_runner_control(
    package: Path, root: Path, cloud_audit: dict[str, Any]
) -> dict[str, Any]:
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    server = root / "cloud-nonblocking-server"
    server.mkdir()
    (server / "install/cfg_pkg").mkdir(parents=True)
    changed = (
        "rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC.sv"
    )
    changed_path = server / PurePosixPath(changed)
    changed_path.parent.mkdir(parents=True)
    changed_path.write_bytes(b"LOCAL_CONTROL_IDENTITY_DIFFERENT_FROM_CLOUD\n")
    sim_marker = root / "cloud-nonblocking-sim-marker.txt"
    run_dir = server / f"run_{NAME}"
    stub_bin = make_cloud_nonblocking_stubs(
        root / "cloud-nonblocking-control", sim_marker, run_dir
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = str(stub_bin) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [
            str(bash),
            str(package / "PREPARE_AND_RUN.sh"),
            BASE.git_bash_path(server),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
        check=False,
    )
    identity_path = server / f"evidence_{NAME}/cloud_rtl_identity.json"
    identity = load_json(identity_path) if identity_path.is_file() else {}
    expected_sha = next(
        item["cloud"]["sha256"]
        for item in cloud_audit["changed_files"]
        if item["path"].endswith("/IGA_ROW_LC.sv")
    )
    observed = next(
        (
            item
            for item in identity.get("actual_files", [])
            if item["path"] == changed
        ),
        {},
    )
    return_zip = server / f"{NAME}_return.zip"
    receipt = BASE.return_zip_receipt(return_zip)
    returned_identity = False
    if return_zip.is_file():
        with zipfile.ZipFile(return_zip) as archive:
            binding_name = next(
                (
                    item.filename
                    for item in archive.infolist()
                    if item.filename.endswith("/e/observer_binding.txt")
                ),
                None,
            )
            if binding_name is not None:
                returned_identity = (
                    b"cloud_rtl_identity_json=" in archive.read(binding_name)
                )
    valid = (
        result.returncode == 87
        and sim_marker.is_file()
        and identity.get("compile_exit_status") == 0
        and identity.get("identity_difference_is_simulation_blocker") is False
        and observed.get("exists") is True
        and observed.get("sha256") != expected_sha
        and receipt["valid"]
        and returned_identity
    )
    return {
        "valid": valid,
        "runner_exit": result.returncode,
        "compile_exit_status": identity.get("compile_exit_status"),
        "actual_differs_from_cloud": observed.get("sha256") != expected_sha,
        "simulator_stub_reached": sim_marker.is_file(),
        "identity_receipt_returned": returned_identity,
        "return_zip": receipt,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def audit(zip_path: Path, sidecar: Path) -> dict[str, Any]:
    entries, zip_receipt = BASE.read_zip(zip_path)
    manifest = json.loads(entries["TEST_PACKAGE_MANIFEST.json"])
    actual_records = BASE.record_map(entries, {"TEST_PACKAGE_MANIFEST.json"})
    declared_records = manifest["files"]
    manifest_exact = {
        item["path"]: (item["size_bytes"], item["sha256"])
        for item in declared_records
    } == {
        item["path"]: (item["size_bytes"], item["sha256"])
        for item in actual_records
    }
    digest = sha(zip_path)
    sidecar_valid = (
        sidecar.is_file()
        and sidecar.read_text(encoding="ascii")
        == f"{digest}  {zip_path.name}\n"
    )
    build_report = load_json(BUILD_REPORT)
    deterministic = (
        build_report.get("deterministic_double_build") is True
        and build_report["zip"]["sha256"] == digest
        and build_report["zip"]["size_bytes"] == zip_path.stat().st_size
    )
    rules = rule_receipt_gate(manifest)
    with tempfile.TemporaryDirectory(
        prefix="n71n75-v7-final-",
        dir=ROOT / "artifacts/operator_config_validation",
    ) as temporary:
        extract = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract)
        package = extract / NAME
        before = BASE.tree_records(package)
        runtime_path = package / "pkg/runtime.py"
        runtime_text = runtime_path.read_text(encoding="utf-8")
        runtime_base_text = (
            package / "pkg/runtime_base.py"
        ).read_text(encoding="utf-8")
        runtime_contract_text = runtime_text + "\n" + runtime_base_text
        runner_text = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        observer_text = (
            package / "obs/native_return_observer.svh"
        ).read_text(encoding="utf-8")
        paths = {
            path.relative_to(package).as_posix()
            for path in package.rglob("*")
            if path.is_file()
        }
        preflight = BASE.run_python(
            runtime_path, ["preflight", "--package-root", str(package)]
        )
        sca = BASE.sca_receipt(package, manifest)
        execplan = BASE.execplan_receipt(package)
        address = materialized_address_gate(package)
        binding = BASE.runner_binding(
            manifest, runner_text, runtime_contract_text, observer_text, paths
        )
        feature = BASE.feature_gate(
            manifest, runner_text, observer_text, runtime_contract_text
        )
        allowlist = allowlist_gate(manifest, runtime_contract_text)
        path_positive = BASE.path_contract(paths, manifest, runner_text)
        overdeep = set(paths)
        overdeep.add("x/" + "z" * 129)
        repeated = set(paths)
        repeated.add(f"workload/{NAME}/{NAME}/duplicate.bin")
        stale_runner = runner_text.replace(
            "+incdir+$package_root/obs", "+incdir+$package_root/o", 1
        )
        path_negatives = {
            "over_budget_member_fail_closed": not BASE.path_contract(
                overdeep, manifest, runner_text, require_references=False
            ),
            "repeated_identity_fail_closed": not BASE.path_contract(
                repeated, manifest, runner_text, require_references=False
            ),
            "stale_consumer_fail_closed": not BASE.path_contract(
                paths, manifest, stale_runner
            ),
        }
        frozen_semantics = receipt_reuse_gate(package)
        cloud_audit = load_json(package / "p/cloud_rtl_0ccae91_impact.json")
        causal = load_json(package / "p/causal_transaction_ledger.json")
        boundary = load_json(package / "p/boundary_microtrace.json")
        v5_return = load_json(package / "p/v5_return_analysis.json")
        compile_control = BASE.runner_compile_control(package, extract)
        identity_negative = BASE.runner_identity_negative(package, extract)
        signal_control = BASE.runner_signal_control(package, extract)
        cloud_control = cloud_nonblocking_runner_control(
            package, extract, cloud_audit
        )
        after = BASE.tree_records(package)

    checks = {
        "zip_core": all(
            zip_receipt[key]
            for key in (
                "crc_valid",
                "single_root",
                "path_safe",
                "duplicate_free",
                "symlink_free",
            )
        ),
        "sidecar_exact": sidecar_valid,
        "manifest_exact_set_size_sha": manifest_exact,
        "package_identity_claim": (
            manifest.get("package_name") == NAME
            and manifest.get("install_name") == NAME
            and manifest.get("status") == "PACKAGE_READY_NOT_RUN"
            and manifest.get("diagnostic_only") is True
            and manifest.get("candidate_release") is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("explicit_barrier_claim") is False
            and manifest.get("opcode110_is_barrier") is False
        ),
        "current_rule_receipts": rules["valid"],
        "deterministic_double_build": deterministic,
        "fresh_extract_preflight": (
            preflight["exit_code"] == 0
            and preflight["parsed"].get("status") == "PACKAGE_PREFLIGHT_PASS"
            and preflight["parsed"].get("return_allowlist_record_count") == 162
        ),
        "sca_runtime_d": sca["valid"],
        "execplan_order": execplan["valid"],
        "physical_bank_row": address["valid"],
        "configured_eight_pass": (
            manifest["a_coverage"]["reload_pass_count"] == 8
            and manifest["a_coverage"]["accepted_occurrence_count"] == 8192
            and manifest["a_coverage"]["accepted_traffic_bytes"] == 262144
            and manifest["a_coverage"]["unique_consumer_byte_count"] == 32768
        ),
        "observer_binding": binding["valid"],
        "feature_binding": feature["valid"],
        "frozen_observer_parser_receipt": frozen_semantics["valid"],
        "causal_ledger": causal.get("status") == "PASS",
        "boundary_microtrace": boundary.get("status") == "PASS",
        "cloud_causal_cone": (
            cloud_audit.get("status")
            == "AFFECTED_CAUSAL_CONE_REVALIDATION_PASS"
            and cloud_audit["authority"]["cloud_approved_commit"] == CLOUD_COMMIT
        ),
        "v5_return_first_divergence": (
            v5_return.get("status")
            == "RETURN_ANALYSIS_PASS_SUCCESSOR_REQUIRED_BANKROW_RELOCATION"
        ),
        "return_allowlist": allowlist["valid"],
        "path_positive": path_positive,
        "path_negatives": all(path_negatives.values()),
        "runner_compile_failure_return": compile_control["valid"],
        "runner_identity_precompile_negative": identity_negative["valid"],
        "runner_signal_finalizer": signal_control["valid"],
        "cloud_diff_nonblocking_simulator_positive": cloud_control["valid"],
        "bootstrap_tree_immutable": before == after,
        "no_server_action": True,
    }

    release_gate_matrix = {
        "package_bootstrap_path_runtime_d": {
            "applicable": True,
            "blocking": True,
            "changed_surface": True,
            "reason": "fresh v7 identity and relocated runtime-D/CONFIG/exec binding",
            "evidence": {
                key: checks[key]
                for key in (
                    "zip_core",
                    "sidecar_exact",
                    "manifest_exact_set_size_sha",
                    "package_identity_claim",
                    "fresh_extract_preflight",
                    "sca_runtime_d",
                    "path_positive",
                    "path_negatives",
                    "bootstrap_tree_immutable",
                )
            },
        },
        "runner_compile_finalizer": {
            "applicable": True,
            "blocking": True,
            "changed_surface": True,
            "reason": "runner adds post-compile nonblocking cloud identity receipt",
            "evidence": {
                "compile_failure_return": compile_control["valid"],
                "precompile_package_identity_negative": identity_negative["valid"],
                "signal_shared_finalizer": signal_control["valid"],
                "cloud_diff_compile0_reaches_simulator": cloud_control["valid"],
            },
        },
        "package_local_hdl": {
            "applicable": True,
            "blocking": True,
            "changed_surface": False,
            "reason": (
                "observer bytes are v5-frozen; cloud RD target changed only queue "
                "depth while private leaf declaration/name/width remains exact"
            ),
            "evidence": {
                "v5_hdl_and_xmr_receipt_reuse": frozen_semantics["valid"],
                "cloud_affected_binding_audit": checks["cloud_causal_cone"],
                "future_actual_production_compile_dynamic_gate": True,
            },
        },
        "materialized_config": {
            "applicable": True,
            "blocking": True,
            "changed_surface": (
                "D_CONFIG_EXECPLAN_PHYSICAL_STORAGE_ADDRESS_RELOCATION"
            ),
            "reason": "v5 failed before stage00 at a disabled physical bank row",
            "evidence": {
                "sca_roundtrip": sca["valid"],
                "execplan": execplan["valid"],
                "physical_bank_row": address["valid"],
                "causal_transaction_ledger": checks["causal_ledger"],
                "boundary_microtrace": checks["boundary_microtrace"],
            },
        },
        "diagnostic_observer_canonical": {
            "applicable": False,
            "blocking": False,
            "changed_surface": False,
            "reason": (
                "observer, runtime parser and canonical predicates are byte-equal "
                "to passed v5 final audit"
            ),
            "evidence": {"receipt_reuse": frozen_semantics},
        },
        "return_result_joint_gate": {
            "applicable": True,
            "blocking": True,
            "changed_surface": True,
            "reason": "fresh optional cloud identity evidence member plus 144 D",
            "evidence": {
                "allowlist": allowlist["valid"],
                "compile_failure_return": compile_control["valid"],
                "signal_partial_return": signal_control["valid"],
            },
        },
        "cloud_github_authority_nonblocking": {
            "applicable": True,
            "blocking": True,
            "changed_surface": True,
            "reason": "node0071/node0075 uses changed ARM/Buffer/RD/SA causal cone",
            "evidence": {
                "authority_commit": CLOUD_COMMIT,
                "targeted_local_audit": checks["cloud_causal_cone"],
                "compile0_actual_diff_reaches_simulator_stub": cloud_control["valid"],
                "actual_identity_match_claim": "NONE_NONBLOCKING_RECEIPT_ONLY",
            },
        },
        "record_only": [
            {
                "id": "PLAN_MUTABLE_PROVENANCE",
                "blocking": False,
                "message": "plan is recorded at generation/audit time, not rewritten",
            },
            {
                "id": "FROZEN_NUMERIC_W3_GOLDEN",
                "blocking": False,
                "message": "byte-equal numeric/W3/golden assets were not rerun",
            },
            {
                "id": "SERVER_DYNAMIC_E3_E4_E5",
                "blocking": False,
                "message": (
                    "actual producer/pass00 order, 8192 accepted reads, natural "
                    "terminal and 144 D remain return-only"
                ),
            },
        ],
    }
    for key, gate in release_gate_matrix.items():
        if key == "record_only":
            continue
        gate["pass"] = all(
            value is True
            for value in gate["evidence"].values()
            if isinstance(value, bool)
        )
    blocking_failures = [
        key
        for key, gate in release_gate_matrix.items()
        if key != "record_only"
        and gate["applicable"]
        and gate["blocking"]
        and not gate["pass"]
    ]
    valid = all(checks.values()) and not blocking_failures
    return {
        "schema": "node0071-node0075-0ccae91-bankrow-v9-final-zip-audit-v1",
        "status": "PASS" if valid else "FAIL",
        "valid": valid,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_release": "PACKAGE_READY_NOT_RUN" if valid else "NONE",
        "candidate_release": False,
        "errors": [key for key, value in checks.items() if not value],
        "blocking_failures": blocking_failures,
        "checks": checks,
        "release_gate_matrix": release_gate_matrix,
        "zip": {
            "path": zip_path.relative_to(ROOT).as_posix(),
            "size_bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "sidecar": {
            "path": sidecar.relative_to(ROOT).as_posix(),
            "size_bytes": sidecar.stat().st_size,
            "sha256": sha(sidecar),
            "content_valid": sidecar_valid,
        },
        "zip_receipt": zip_receipt,
        "manifest_sha256": sha_bytes(entries["TEST_PACKAGE_MANIFEST.json"]),
        "manifest_file_count": len(entries),
        "rule_receipts": rules,
        "plan_mutable_provenance": {
            "current_sha256": sha(ROOT / ".agents/plan.md"),
            "package_generation_sha256": next(
                item["sha256"]
                for item in manifest["source_inputs"]
                if item["path"] == ".agents/plan.md"
            ),
        },
        "sca_gate": sca,
        "execplan_gate": execplan,
        "physical_bank_row_gate": address,
        "observer_binding": binding,
        "feature_binding": feature,
        "frozen_semantics_receipt": frozen_semantics,
        "cloud_impact_audit": cloud_audit,
        "causal_transaction_ledger": causal,
        "boundary_microtrace": boundary,
        "return_allowlist_gate": allowlist,
        "runner_compile_stub_control": compile_control,
        "runner_identity_negative_control": identity_negative,
        "runner_signal_stub_control": signal_control,
        "cloud_nonblocking_runner_control": cloud_control,
        "server_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        ),
        "expected_return": f"{NAME}_return.zip",
        "server_uploaded": False,
        "server_run": False,
        "lease_taken": False,
        "functional_rtl_modified": False,
        "claim_boundary": (
            "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX; local config-bound E2 and "
            "package controls only. No explicit barrier/fence claim. Cloud/local "
            "actual identity difference is nonblocking after compile; dynamic "
            "ordering, accepted traffic, terminal and 144 D require a return."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=ZIP_PATH)
    parser.add_argument("--sidecar", type=Path, default=SIDECAR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        report = audit(args.zip.resolve(), args.sidecar.resolve())
    except Exception as exc:
        report = {
            "schema": "node0071-node0075-0ccae91-bankrow-v9-final-zip-audit-v1",
            "status": "FAIL",
            "valid": False,
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": False,
            "package_release": "NONE",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "valid": report.get("valid"),
                "package_release": report.get("package_release"),
                "errors": report.get("errors"),
                "blocking_failures": report.get("blocking_failures"),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
