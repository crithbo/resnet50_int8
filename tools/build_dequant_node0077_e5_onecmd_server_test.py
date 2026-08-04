#!/usr/bin/env python3
"""Derive the fresh-identity Dequant node0077/v6 stock-RTL E5 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.dequant_node0077_server_runtime import (  # noqa: E402
    MANIFEST_NAME,
    expected_success_return_paths,
    preflight_package,
)


SCHEMA = "resnet50-dequant-node0077-stockrtl-e5-onecmd-package-v1"
E4_INSTALL_NAME = "dequant_node0077_stockrtl_e4_onecmd_v2"
INSTALL_NAME = "dequant_node0077_stockrtl_e5_onecmd_v1"
PACKAGE_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
E4_PACKAGE = PACKAGE_ROOT / E4_INSTALL_NAME
E4_ZIP = E4_PACKAGE.with_suffix(".zip")
E4_ZIP_SHA256 = (
    "2ac27a4856b36bb660c0293ff53f84794464283712f20fe0d84dabfa16b699e0"
)
E4_MANIFEST_SHA256 = (
    "5916ccd3c4999daa49368d61dd80a19ab09d3a501bbbcd43c92b0a3a77e61f10"
)
E4_PAYLOAD_TREE_SHA256 = (
    "e967bb42019b4b28d9bc97ba9d2a90d9a99773d3d5a5295768e8f947c07fc354"
)
E4_RETURN_ANALYSIS = (
    ROOT
    / "server_returns/dequant_node0077_stockrtl_e4_onecmd_v2_return_analysis_20260727.json"
)
E4_RETURN_ANALYSIS_SHA256 = (
    "c7d1380f6dd365b6349e050390a5e112125906eb04a73fcd54a3dec412bfe35f"
)
E4_PASS_RECORD = (
    ROOT
    / ".agents/task_records/20260727_dequant_node0077_full_v6_e4_pass.md"
)
E4_PASS_RECORD_SHA256 = (
    "e7fe4ceaf9a9581b68b5ddf16d57f7bc19a9f5ee6a34aa4b4b9235f16c81cc28"
)
DEFAULT_OUTPUT = PACKAGE_ROOT / INSTALL_NAME

MANDATORY_READS = (
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/DequantizeLinear算子配置规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    ".agents/plan.md",
    "server_returns/dequant_node0077_stockrtl_e4_onecmd_v2_return_analysis_20260727.json",
    ".agents/task_records/20260727_dequant_node0077_full_v6_e4_pass.md",
)
MANDATORY_READ_IDENTITIES = {
    ".agents/rules/生成前必读索引.md":
        "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7",
    ".agents/rules/服务器测试包生成规则.md":
        "b4019910c7ef65f334676a1b3a5679e63b8ac41dcde88b567ada4f096e50fe05",
    ".agents/rules/DequantizeLinear算子配置规则.md":
        "2374975170515252b1ea2d1c1ffc806af5b757c286322ba91b194c0bac0419d7",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md":
        "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7",
    ".agents/plan.md":
        "1eaf9491aa345c4559915b937161f293d4aaa1bc4f135024632645b7453a7d95",
    "server_returns/dequant_node0077_stockrtl_e4_onecmd_v2_return_analysis_20260727.json":
        E4_RETURN_ANALYSIS_SHA256,
    ".agents/task_records/20260727_dequant_node0077_full_v6_e4_pass.md":
        E4_PASS_RECORD_SHA256,
}
ACTUAL_CONSUMERS = (
    "NDP_copy01/Makefile.tb_NDP_Top_new_phy",
    "NDP_copy01/tb_NDP_Top_new_phy.sv",
    "NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f",
    "NDP_copy01/native_return_observer.svh",
    "tools/build_dequant_node0077_onecmd_server_test.py",
    "tools/dequant_node0077_server_runtime.py",
    "tools/build_dequant_node0077_e5_onecmd_server_test.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/json_loader.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/control_registers.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/output_writer.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/pipeline.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/instruction_generator.py",
    "ndp-sim-ref/bitstream/main.py",
    "ndp-sim-ref/bitstream/parse.py",
    "ndp-sim-ref/bitstream/config/mapper.py",
    "ndp-sim-ref/bitstream/config/general.py",
)
RULE_IDS = (
    "CDA-SERVER-WORKLOAD-PROVENANCE-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SERVER-RETURN-RECEIPT-001",
    "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
    "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
    "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
    "CDA-SCA-D-TB-READBACK-LENGTH-001",
    "CDA-DEQUANT-NODE0077-E4-V6-DYNAMIC-PASS-001",
    "CDA-DEQUANT-ONNX-ORDER-001",
    "CDA-DEQUANT-NO-AFFINE-MAC-001",
    "CDA-DEQUANT-TWO-STAGE-GA-001",
    "CDA-DEQUANT-NORMAL-OUTBUFFER-001",
    "CDA-DEQUANT-LAYOUT-HIGH4-001",
    "CDA-DEQUANT-STREAM-LIFECYCLE-001",
    "CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001",
    "CDA-DEQUANT-TYPED-CONSTANT-001",
    "CDA-DEQUANT-MAPPING-BINDING-001",
    "CDA-DEQUANT-E2-001",
    "CDA-DEQUANT-E4-E5-001",
)
FROZEN_VALIDATION_FILES = (
    "atomic_v3_return_analysis.json",
    "atomic_v3_task_record.md",
    "generation_receipt_v6.json",
    "instructions_explained.txt",
    "layout_evidence.json",
    "layout_inverse_contract.json",
    "local_e2_report_v6.json",
    "mapping_review.json",
    "numeric_evidence.json",
    "semantic_contract_v6.json",
    "SOURCE_V6_IDENTITY.json",
    "stage_manifest_v1.json",
    "stage_schedule_ir.json",
    "strict_config.json",
)


class DequantE5PackageError(RuntimeError):
    """Raised when the frozen-v6 E5 identity cannot be proved."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_lf(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _records(
    root: Path, *, exclude_manifest: bool = False
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return records


def _tree_sha256(records: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(records.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return digest.hexdigest()


def _file_receipt(relative: str, scope: str) -> dict[str, Any]:
    path = ROOT / relative
    if not path.is_file():
        raise DequantE5PackageError(f"required read target missing: {relative}")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "read_scope": scope,
    }


def _read_receipt() -> dict[str, Any]:
    return {
        "schema": "dequant-node0077-full-e5-generation-read-receipt-v1",
        "status": "complete",
        "read_session_date": "2026-07-27",
        "mandatory_files": [
            _file_receipt(relative, "complete_file")
            for relative in MANDATORY_READS
        ],
        "actual_consumers": [
            _file_receipt(relative, "actual_consumed_file")
            for relative in ACTUAL_CONSUMERS
        ],
        "rule_ids": list(RULE_IDS),
    }


def _verify_authority_reads() -> None:
    for relative, expected_sha256 in MANDATORY_READ_IDENTITIES.items():
        path = ROOT / relative
        if not path.is_file() or _sha256(path) != expected_sha256:
            raise DequantE5PackageError(
                f"mandatory read identity differs: {relative}"
            )


def _verify_e4_source() -> tuple[dict[str, Any], dict[str, Any]]:
    _verify_authority_reads()
    if not E4_ZIP.is_file() or not E4_PACKAGE.is_dir():
        raise DequantE5PackageError("frozen E4 v2 package directory/ZIP missing")
    if _sha256(E4_ZIP) != E4_ZIP_SHA256:
        raise DequantE5PackageError("frozen E4 v2 ZIP identity differs")
    if (
        not E4_RETURN_ANALYSIS.is_file()
        or _sha256(E4_RETURN_ANALYSIS) != E4_RETURN_ANALYSIS_SHA256
    ):
        raise DequantE5PackageError(
            "authoritative E4 return analysis identity differs"
        )
    if (
        not E4_PASS_RECORD.is_file()
        or _sha256(E4_PASS_RECORD) != E4_PASS_RECORD_SHA256
    ):
        raise DequantE5PackageError(
            "authoritative E4 pass record identity differs"
        )
    manifest_path = E4_PACKAGE / MANIFEST_NAME
    if _sha256(manifest_path) != E4_MANIFEST_SHA256:
        raise DequantE5PackageError("frozen E4 v2 manifest identity differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = _records(E4_PACKAGE, exclude_manifest=True)
    if (
        manifest.get("install_name") != E4_INSTALL_NAME
        or manifest.get("files") != records
        or manifest.get("payload_tree_sha256") != E4_PAYLOAD_TREE_SHA256
        or _tree_sha256(records) != E4_PAYLOAD_TREE_SHA256
    ):
        raise DequantE5PackageError("frozen E4 directory exact-set differs")
    with zipfile.ZipFile(E4_ZIP) as archive:
        expected = {
            f"{E4_INSTALL_NAME}/{path.relative_to(E4_PACKAGE).as_posix()}":
            path.read_bytes()
            for path in sorted(
                item for item in E4_PACKAGE.rglob("*") if item.is_file()
            )
        }
        if archive.namelist() != list(expected):
            raise DequantE5PackageError("frozen E4 ZIP exact-set differs")
        if any(archive.read(name) != raw for name, raw in expected.items()):
            raise DequantE5PackageError("frozen E4 ZIP payload differs")
    return manifest, records


def _write_deterministic_zip(package: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _audit_zip(package: Path, zip_path: Path) -> dict[str, Any]:
    expected = {
        f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}": path.read_bytes()
        for path in sorted(item for item in package.rglob("*") if item.is_file())
    }
    with zipfile.ZipFile(zip_path) as archive:
        if archive.namelist() != list(expected):
            raise DequantE5PackageError("E5 ZIP exact-set/order differs")
        for name, raw in expected.items():
            if archive.read(name) != raw:
                raise DequantE5PackageError(f"E5 ZIP payload differs: {name}")
    return {
        "entry_count": len(expected),
        "exact_set": True,
        "payloads_byte_exact": True,
        "deterministic_timestamp": "1980-01-01T00:00:00",
    }


def _frozen_workload_gate(package: Path) -> dict[str, Any]:
    e4_workload = E4_PACKAGE / "workload"
    e5_workload = package / "workload"
    e4_records = _records(e4_workload)
    e5_records = _records(e5_workload)
    if set(e4_records) != set(e5_records):
        raise DequantE5PackageError("E5 workload exact path set differs")
    normalized = 0
    for relative in sorted(e4_records):
        e4_raw = (e4_workload / relative).read_bytes()
        e5_raw = (e5_workload / relative).read_bytes()
        if relative == "runtime/sca_cfg.json":
            normalized_raw = e5_raw.replace(
                INSTALL_NAME.encode(), E4_INSTALL_NAME.encode()
            )
            if normalized_raw != e4_raw:
                raise DequantE5PackageError("normalized E5 SCA differs from E4")
            normalized += 1
        elif e5_raw != e4_raw:
            raise DequantE5PackageError(
                f"frozen E5 workload byte differs: {relative}"
            )
    for name in FROZEN_VALIDATION_FILES:
        if (
            package.joinpath("validation", name).read_bytes()
            != E4_PACKAGE.joinpath("validation", name).read_bytes()
        ):
            raise DequantE5PackageError(f"frozen validation differs: {name}")
    sca = json.loads(
        (e5_workload / "runtime/sca_cfg.json").read_text(encoding="utf-8")
    )
    sca_d = json.loads(
        (e5_workload / "runtime/sca_cfg_D.json").read_text(encoding="utf-8")
    )
    paths = [
        entry["path"]
        for entry in sca.values()
        if isinstance(entry, dict) and "path" in entry
    ]
    if len(paths) != 30 or any(
        f"../install/cfg_pkg/{INSTALL_NAME}/" not in path for path in paths
    ):
        raise DequantE5PackageError("E5 SCA namespace rewrite is incomplete")
    if (
        len(sca_d) != 28
        or sum(int(entry["length"]) for entry in sca_d.values()) != 5264
        or any(int(entry["length"]) != 188 for entry in sca_d.values())
    ):
        raise DequantE5PackageError("E5 formal D geometry differs")
    return {
        "status": "pass",
        "e4_zip_sha256": E4_ZIP_SHA256,
        "workload_file_count": len(e5_records),
        "byte_exact_file_count": len(e5_records) - normalized,
        "identity_normalized_sca_file_count": normalized,
        "sca_preload_payload_count": len(paths),
        "formal_d_slice_count": len(sca_d),
        "formal_d_lines_per_slice": 188,
        "formal_d_total_128bit_lines": 5264,
        "expected_raw_mse4_request_count": 5264,
        "expected_raw_mse4_wdata_count": 5264,
        "strict_json_mapping_bitstream_execplan_input_golden_inverse_frozen": True,
        "address_and_length_semantics_frozen": True,
    }


def _readme() -> str:
    return f"""# ResNet50 DequantizeLinear node0077 — stock RTL E5

This is the fresh-identity repeat dynamic run of the exact v6 workload that
passed stock-RTL E4 in `{E4_INSTALL_NAME}`. JSON, mapping, bitstream, execplan,
input, golden, addresses, formal-D layout and inverse are frozen.

Run one command from this extracted directory:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

The package installs into `{INSTALL_NAME}`, uses an isolated run directory,
checks 28 natural slice completions, 28 × 188 formal D lines, positive-zero
tails, the full 16 × 1000 inverse, 5,264 raw MSE4 requests and 5,264 raw
write-data events, stock RTL/TB identity, and an allowlist-only return.
It contains no RTL/TB replacement or patch. `candidate_release` remains false
until this E5 return is independently accepted.
"""


def _derive_tree(output: Path) -> dict[str, Any]:
    e4_manifest, _ = _verify_e4_source()
    for target in (output, output.with_suffix(".zip"), Path(f"{output}.zip.sha256")):
        if target.exists():
            raise DequantE5PackageError(f"output must be fresh: {target}")
    shutil.copytree(E4_PACKAGE, output)
    (output / MANIFEST_NAME).unlink()

    sca_path = output / "workload/runtime/sca_cfg.json"
    sca_text = sca_path.read_text(encoding="utf-8")
    if sca_text.count(E4_INSTALL_NAME) != 30:
        raise DequantE5PackageError("frozen E4 SCA namespace occurrence differs")
    _write_lf(sca_path, sca_text.replace(E4_INSTALL_NAME, INSTALL_NAME))

    runner_path = output / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    if E4_INSTALL_NAME not in runner:
        raise DequantE5PackageError("frozen E4 runner identity missing")
    _write_lf(runner_path, runner.replace(E4_INSTALL_NAME, INSTALL_NAME))
    shutil.copyfile(
        ROOT / "tools/dequant_node0077_server_runtime.py",
        output / "package_tools/dequant_node0077_server_runtime.py",
    )
    _write_lf(output / "README.md", _readme())

    validation = output / "validation"
    shutil.copyfile(
        validation / "GENERATION_READ_RECEIPT.json",
        validation / "E4_GENERATION_READ_RECEIPT.json",
    )
    _write_json(validation / "GENERATION_READ_RECEIPT.json", _read_receipt())
    shutil.copyfile(
        E4_RETURN_ANALYSIS,
        validation / "E4_DYNAMIC_PASS_ANALYSIS.json",
    )
    shutil.copyfile(
        E4_PASS_RECORD,
        validation / "E4_DYNAMIC_PASS_TASK_RECORD.md",
    )
    _write_json(
        validation / "EXPECTED_RETURN_EXACT_SET.json",
        {
            "schema": "dequant-node0077-full-e5-expected-return-exact-set-v1",
            "status": "success_path_exact_set",
            "install_name": INSTALL_NAME,
            "path_count": len(expected_success_return_paths()),
            "paths": expected_success_return_paths(),
            "partial_return_policy": (
                "allowlist subset plus RETURN_RECEIPT required_missing"
            ),
        },
    )
    _write_json(
        validation / "RELEASE_GATE.json",
        {
            "schema": "resnet50-dequant-node0077-server-release-gate-v2",
            "status": "E5_PACKAGE_READY_NOT_RUN_V6_FULL_28_SLICE",
            "classification": "REPEAT_DYNAMIC_RUN_NOT_STARTED",
            "dynamic_run_gate": "E5",
            "candidate_release": False,
            "release_gate_passed": False,
            "completed_evidence": ["E2_LOCAL_ONLY", "E4_SERVER_FORMAL_PASS"],
            "remaining_blockers": ["B_DEQUANT_SERVER_E5"],
            "e5_required": (
                "fresh identity; 28 natural completions; 28x188 formal D "
                "bit-exact; positive-zero tails; full inverse; 5264 raw "
                "request and wdata counts; natural exit; exact-set return; "
                "stable stock RTL and transactional observer identity"
            ),
        },
    )
    frozen_gate = _frozen_workload_gate(output)

    manifest = dict(e4_manifest)
    manifest.update(
        {
            "schema": SCHEMA,
            "status": "E5_ONE_COMMAND_PACKAGE_READY",
            "classification": "REPEAT_DYNAMIC_RUN_NOT_STARTED",
            "dynamic_run_gate": "E5",
            "install_name": INSTALL_NAME,
            "candidate_release": False,
            "release_gate_passed": False,
            "evidence_level": "E4_SERVER_FORMAL_PASS_E5_NOT_RUN",
            "remaining_blockers": ["B_DEQUANT_SERVER_E5"],
            "single_hypothesis": (
                "the frozen node0077/v6 workload repeats the complete E4 "
                "stock-RTL result under a fresh E5 identity"
            ),
            "source_e4_pass": {
                "package_install_name": E4_INSTALL_NAME,
                "package_zip_sha256": E4_ZIP_SHA256,
                "package_manifest_sha256": E4_MANIFEST_SHA256,
                "package_payload_tree_sha256": E4_PAYLOAD_TREE_SHA256,
                "return_analysis_sha256": E4_RETURN_ANALYSIS_SHA256,
                "task_record_sha256": E4_PASS_RECORD_SHA256,
                "return_analysis_path": (
                    "validation/E4_DYNAMIC_PASS_ANALYSIS.json"
                ),
                "task_record_path": (
                    "validation/E4_DYNAMIC_PASS_TASK_RECORD.md"
                ),
                "classification": "FIRST_DYNAMIC_PASS",
            },
            "frozen_workload_gate": frozen_gate,
            "server_operation": {
                "only_command": (
                    "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
                ),
                "command_line_count": 1,
                "automatic_install_validate_compile_run_analyze_collect": True,
            },
            "e5_boundary": (
                "this package runs E5 only; candidate_release remains false "
                "until independent return acceptance"
            ),
        }
    )
    manifest["runtime_policy"] = {
        **dict(e4_manifest["runtime_policy"]),
        "unique_namespace": f"install/cfg_pkg/{INSTALL_NAME}",
        "unique_run_dir": f"run_{INSTALL_NAME}",
        "unique_return_identity": f"{INSTALL_NAME}_return",
    }
    manifest["dynamic_e5_gates"] = manifest.pop("dynamic_e4_gates")
    manifest["rules"] = {
        "mandatory_files_read": list(MANDATORY_READS),
        "actual_consumers_read": list(ACTUAL_CONSUMERS),
        "generation_read_receipt": "validation/GENERATION_READ_RECEIPT.json",
        "rule_ids": list(RULE_IDS),
    }
    records = _records(output, exclude_manifest=True)
    manifest["payload_file_count"] = len(records)
    manifest["payload_tree_sha256"] = _tree_sha256(records)
    manifest["files"] = records
    _write_json(output / MANIFEST_NAME, manifest)
    preflight = preflight_package(output, INSTALL_NAME)

    zip_path = output.with_suffix(".zip")
    _write_deterministic_zip(output, zip_path)
    digest = _sha256(zip_path)
    sidecar = Path(f"{zip_path}.sha256")
    _write_lf(sidecar, f"{digest}  {zip_path.name}\n")
    return {
        "schema": SCHEMA,
        "status": "built",
        "directory": output.as_posix(),
        "manifest_sha256": _sha256(output / MANIFEST_NAME),
        "payload_file_count": len(records),
        "payload_tree_sha256": manifest["payload_tree_sha256"],
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": sidecar.as_posix(),
        "preflight": preflight,
        "frozen_workload_gate": frozen_gate,
    }


def _fresh_extract_complete_self_check(package: Path) -> dict[str, Any]:
    zip_path = package.with_suffix(".zip")
    with tempfile.TemporaryDirectory(prefix="dq-full-e5-check-") as temporary:
        root = Path(temporary)
        extract_root = root / "fresh_extract"
        extract_root.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        fresh_package = extract_root / INSTALL_NAME
        before = _records(fresh_package)
        before_size = sum(item["size_bytes"] for item in before.values())
        runtime = (
            fresh_package / "package_tools/dequant_node0077_server_runtime.py"
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        def run(*arguments: str) -> None:
            completed = subprocess.run(
                [sys.executable, str(runtime), *arguments],
                cwd=fresh_package,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                raise DequantE5PackageError(
                    f"fresh-extract {arguments[0]} failed: "
                    f"{completed.stderr.strip()}"
                )

        run(
            "preflight-package",
            "--package-root",
            str(fresh_package),
            "--install-name",
            INSTALL_NAME,
            "--output",
            str(root / "package_preflight.json"),
        )
        ndp_root = root / "NDP_copy_mock"
        evidence = root / "evidence"
        ndp_root.mkdir()
        evidence.mkdir()
        observer = ndp_root / "native_return_observer.svh"
        shutil.copyfile(ROOT / "NDP_copy01/native_return_observer.svh", observer)
        observer_preimage = observer.read_bytes()
        run(
            "install-probe",
            "--ndp-root",
            str(ndp_root),
            "--package-root",
            str(fresh_package),
            "--evidence-root",
            str(evidence),
        )
        run(
            "verify-probe-installed",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
            "--output",
            str(evidence / "tb_probe_precompile_receipt.json"),
        )
        run(
            "restore-probe",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
        )
        if observer.read_bytes() != observer_preimage:
            raise DequantE5PackageError("observer was not restored byte-exact")
        after = _records(fresh_package)
        after_size = sum(item["size_bytes"] for item in after.values())
        if before != after or before_size != after_size:
            raise DequantE5PackageError(
                "fresh-extracted package changed during complete self-check"
            )
        forbidden = [
            relative
            for relative in after
            if "__pycache__" in {
                part.lower() for part in relative.split("/")
            }
            or Path(relative).suffix.lower() in {".pyc", ".pyo"}
        ]
        if forbidden:
            raise DequantE5PackageError(
                f"Python bytecode materialized: {forbidden[:4]}"
            )
        return {
            "schema": "dequant-full-e5-fresh-extract-self-check-v1",
            "status": "pass",
            "complete_self_check_count": 1,
            "runtime_preflight_passed": True,
            "observer_install_verify_restore_passed": True,
            "observer_restored_byte_exact": True,
            "package_file_count_before": len(before),
            "package_file_count_after": len(after),
            "package_size_bytes_before": before_size,
            "package_size_bytes_after": after_size,
            "package_tree_sha256_before": _tree_sha256(before),
            "package_tree_sha256_after": _tree_sha256(after),
            "bootstrap_exact_path_size_sha_unchanged": True,
            "python_bytecode_file_count": 0,
        }


def validate_package(package: Path) -> dict[str, Any]:
    package = package.resolve()
    if package.name != INSTALL_NAME:
        raise DequantE5PackageError(f"output name must be {INSTALL_NAME}")
    manifest = json.loads(
        (package / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    records = _records(package, exclude_manifest=True)
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("dynamic_run_gate") != "E5"
        or manifest.get("install_name") != INSTALL_NAME
        or manifest.get("candidate_release") is not False
        or manifest.get("files") != records
        or manifest.get("payload_tree_sha256") != _tree_sha256(records)
    ):
        raise DequantE5PackageError("E5 manifest exact-set/status differs")
    rtl_entries = [
        relative
        for relative in records
        if "rtl" in {part.lower() for part in relative.split("/")}
    ]
    if rtl_entries:
        raise DequantE5PackageError(f"package contains RTL paths: {rtl_entries}")
    script = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    if (
        script.find("export PYTHONDONTWRITEBYTECODE=1") < 0
        or script.find("export PYTHONDONTWRITEBYTECODE=1")
        > script.find("python3 ")
        or E4_INSTALL_NAME in script
        or f'install_name="{INSTALL_NAME}"' not in script
        or "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0" not in script
    ):
        raise DequantE5PackageError("E5 one-command runner identity differs")
    preflight = preflight_package(package, INSTALL_NAME)
    frozen = _frozen_workload_gate(package)
    zip_path = package.with_suffix(".zip")
    zip_audit = _audit_zip(package, zip_path)
    digest = _sha256(zip_path)
    sidecar = Path(f"{zip_path}.sha256")
    if sidecar.read_text(encoding="ascii") != f"{digest}  {zip_path.name}\n":
        raise DequantE5PackageError("E5 ZIP sidecar differs")
    self_check = _fresh_extract_complete_self_check(package)
    return {
        "schema": SCHEMA,
        "status": "validated",
        "manifest_sha256": _sha256(package / MANIFEST_NAME),
        "payload_file_count": len(records),
        "payload_tree_sha256": _tree_sha256(records),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": sidecar.as_posix(),
        "zip_audit": zip_audit,
        "preflight": preflight,
        "frozen_workload_gate": frozen,
        "fresh_extract_complete_self_check": self_check,
        "functional_rtl_file_count": 0,
        "rtl_path_entry_count": 0,
        "server_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        ),
        "expected_return": [
            f"{INSTALL_NAME}_return.zip",
            f"{INSTALL_NAME}_return.zip.sha256",
        ],
        "expected_return_exact_set": expected_success_return_paths(),
        "release_gate": (
            "candidate_release=false; E4 passed; "
            "B_DEQUANT_SERVER_E5 remains until return acceptance"
        ),
    }


def build_package(output: Path) -> dict[str, Any]:
    output = output.resolve()
    if output.name != INSTALL_NAME:
        raise DequantE5PackageError(f"output name must be {INSTALL_NAME}")
    for target in (
        output,
        output.with_suffix(".zip"),
        Path(f"{output}.zip.sha256"),
    ):
        if target.exists():
            raise DequantE5PackageError(f"output must be fresh: {target}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="dq-full-e5-a-"
    ) as left_parent, tempfile.TemporaryDirectory(
        prefix="dq-full-e5-b-"
    ) as right_parent:
        left = Path(left_parent) / INSTALL_NAME
        right = Path(right_parent) / INSTALL_NAME
        left_report = _derive_tree(left)
        right_report = _derive_tree(right)
        if (
            left_report["zip_sha256"] != right_report["zip_sha256"]
            or left.with_suffix(".zip").read_bytes()
            != right.with_suffix(".zip").read_bytes()
            or _records(left) != _records(right)
        ):
            raise DequantE5PackageError(
                "two fresh E5 builds are not byte-identical"
            )
        shutil.copytree(right, output)
        shutil.copyfile(right.with_suffix(".zip"), output.with_suffix(".zip"))
        shutil.copyfile(
            Path(f"{right}.zip.sha256"), Path(f"{output}.zip.sha256")
        )
    validation = validate_package(output)
    return {
        **right_report,
        **validation,
        "directory": output.as_posix(),
        "deterministic_package_build_count": 2,
        "deterministic_zip_byte_identical": True,
        "complete_package_self_check_count": 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        report = (
            validate_package(args.output)
            if args.validate_only
            else build_package(args.output)
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Dequant node0077 E5 package failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
