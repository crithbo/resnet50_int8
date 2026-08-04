#!/usr/bin/env python3
"""Build the native Decode SiLU capture-edge stock-RTL control package."""

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


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_requant_atomic_onecmd_server_test as base  # noqa: E402
from tools import build_requant_guard_only_onecmd_server_test as rq_builder  # noqa: E402
from tools import decode_silu_control_server_runtime as runtime  # noqa: E402


INSTALL_NAME = "decode_silu_fp16N_fp32N_control_stock_v1"
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
MATERIALIZED = (
    ROOT
    / "configs/native_ndp_sim/decode_silu_fp16N_fp32N_control_stocktb_v1/materialized"
)
CONTRACT = (
    ROOT
    / "contracts/operator_config/decode_silu_fp16N_fp32N_control_stocktb_v1.json"
)
CONTRACT_SHA256 = "a4a5787aa3bd344f809b897c1bcb0e8a76a40d235c62f8c7aaa493cf15ec0a44"
MATERIALIZATION_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/r5-decode-silu-control-stocktb-v1/"
    "local_materialization_report.json"
)
ORACLE = ROOT / "ndp-sim/jsons/decode_silu_fp16N_fp32N.json"
ORACLE_SHA256 = "eafb7ec7cd47006dda15c1fc60d00601563a7a9f7e8ae12da3ce45e57baec6be"
OBSERVER_TAIL_NAME = "requant_mse4_guard_observer_tail.svh"
READ_RECEIPT = (
    ROOT
    / ".agents/task_records/20260727_decode_silu_control_stock_v1_read_receipt.json"
)

MANDATORY_READS = (
    (
        ".agents/agent.md",
        "367f4f4260246d40531d83cc6d24fe94946cb05bce6fbef18c428f05b634c083",
        "entry",
    ),
    (
        ".agents/plan.md",
        "a9f0c3397dad32473f542c82852bef9d244535ca40abdb688623aa3c47f14354",
        "plan",
    ),
    (
        ".agents/rules/生成前必读索引.md",
        "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7",
        "index",
    ),
    (
        ".agents/rules/服务器测试包生成规则.md",
        "e4b4a215a60a3efbca83d00998d9618b17c8fb591aadb0a537828869a276b1ee",
        "server_rule",
    ),
    (
        ".agents/rules/RequantizeUint8算子配置规则.md",
        "5f7bc1fc7087d3aafce0b74982588df9c68abeea583a7ea501c87031c3ef9e52",
        "claim_boundary_rule",
    ),
    (
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7",
        "server_entry",
    ),
    (
        ".agents/rules/算子配置规则.md",
        "a5fbe2f0fa2e26d8cd4ebfe8772d5a3c69516d6918cfaa5087198706a352427b",
        "config_rule",
    ),
    (
        ".agents/rules/NDP硬件字段语义.md",
        "7f446adb1719658ce75c2614c6d619fc2c7cdcabf5e4fd34945482645539158f",
        "hardware_fields",
    ),
)

ACTUAL_CONSUMERS = (
    "ndp-sim/model_execplan/README.md",
    "ndp-sim/model_execplan/README_op_json.md",
    "ndp-sim/model_execplan/src/execution_plan_generator/pipeline.py",
    "ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py",
    "ndp-sim/model_execplan/src/execution_plan_generator/output_writer.py",
    "ndp-sim/bitstream/config/general.py",
    "ndp-sim/bitstream/config/mapper.py",
    "ndp-sim/bitstream/config/stream.py",
    "NDP_copy01/Makefile.tb_NDP_Top_new_phy",
    "NDP_copy01/tb_NDP_Top_new_phy.sv",
    "NDP_copy01/native_return_observer.svh",
    "NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Preprocess.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/Binary_Search_Tree.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/Comparator.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Postprocess.sv",
)


class ControlPackageError(RuntimeError):
    """Raised when the control package fails a local release gate."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _copy_lf(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n"),
        encoding="utf-8",
        newline="\n",
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _verify_sources() -> dict[str, Any]:
    if not MATERIALIZED.is_dir():
        raise ControlPackageError("canonical native materialization is missing")
    if _sha256(CONTRACT) != CONTRACT_SHA256:
        raise ControlPackageError("frozen control contract identity differs")
    if _sha256(ORACLE) != ORACLE_SHA256:
        raise ControlPackageError("native oracle identity differs")
    receipt_items = []
    for relative, expected, role in MANDATORY_READS:
        path = ROOT / relative
        if not path.is_file() or _sha256(path) != expected:
            raise ControlPackageError(f"mandatory read identity differs: {relative}")
        receipt_items.append(
            {
                "path": relative,
                "role": role,
                "size_bytes": path.stat().st_size,
                "sha256": expected,
                "read_completely": True,
            }
        )
    consumer_items = []
    for relative in ACTUAL_CONSUMERS:
        path = ROOT / relative
        if not path.is_file():
            raise ControlPackageError(f"actual consumer missing: {relative}")
        consumer_items.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "read_or_directly_inspected": True,
            }
        )
    receipt = {
        "schema": "decode-silu-control-generation-read-receipt-v1",
        "status": "complete",
        "mandatory_reads": receipt_items,
        "actual_consumers": consumer_items,
        "oracle": {
            "path": ORACLE.relative_to(ROOT).as_posix(),
            "sha256": ORACLE_SHA256,
        },
        "contract": {
            "path": CONTRACT.relative_to(ROOT).as_posix(),
            "sha256": CONTRACT_SHA256,
        },
    }
    _write_json(READ_RECEIPT, receipt)
    return receipt


def _observer_tail() -> str:
    text = rq_builder._sfu_numeric_observer_tail()
    replacements = (
        ("REQUANT_GUARD_SFU_NUMERIC_PROBE", "DECODE_SILU_CONTROL_PROBE"),
        ("requant_guard_sfu_numeric_probe", "decode_silu_control_probe"),
        ("Requant node0001 guard-only", "Native Decode SiLU control"),
        ("guard-only", "native-silu-control"),
        ("GUARD_PATH", "SILU_PATH"),
        ("role=guard", "role=native_silu_control"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return text.lstrip()


def _build_tree(package: Path, read_receipt: dict[str, Any]) -> dict[str, Any]:
    package.mkdir(parents=True)
    workload = package / "workload/runtime"
    validation = package / "validation"
    for relative in (
        "runtime/sca_cfg.json",
        "runtime/sca_cfg_D.json",
        "install/execplan.txt",
        "install/cfg_pkg/op0_decode_silu_fp16N_fp32N_bitstream_128b.bin",
        "install/cfg_pkg/SiLU.txt",
        "install/op0/slice00/matrix_A_linearized_128bit.txt",
        "install/op0/slice01/matrix_A_linearized_128bit.txt",
    ):
        source = MATERIALIZED / relative
        target_relative = relative.removeprefix("runtime/")
        _copy_lf(source, workload / target_relative)
    for slice_id in (0, 1):
        _copy_lf(
            MATERIALIZED
            / f"golden/slice{slice_id:02d}/matrix_D_linearized_128bit.txt",
            package
            / f"golden/slice{slice_id:02d}/matrix_D_linearized_128bit.txt",
        )
    for relative, target in (
        ("jsons/op0_decode_silu_fp16N_fp32N.json", "address_bound_config.json"),
        ("config/op0/mapping_review.json", "mapping_review.json"),
        ("config/op0/parsed_bitstream.txt", "parsed_bitstream.txt"),
        ("instructions_explained.txt", "instructions_explained.txt"),
    ):
        _copy(MATERIALIZED / relative, validation / target)
    _copy(CONTRACT, validation / "decode_silu_control_contract.json")
    _copy(MATERIALIZATION_REPORT, validation / "local_materialization_report.json")
    _copy(ORACLE, validation / "native_oracle_unmodified.json")
    _write_json(validation / "generation_read_receipt.json", read_receipt)
    _write_json(
        validation / "address_binding_provenance.json",
        {
            "schema": "decode-silu-control-address-binding-provenance-v1",
            "oracle_path": ORACLE.relative_to(ROOT).as_posix(),
            "oracle_sha256": ORACLE_SHA256,
            "oracle_byte_identity_preserved_in_validation": True,
            "derived_address_bound_path": "validation/address_bound_config.json",
            "derived_address_bound_sha256": _sha256(
                validation / "address_bound_config.json"
            ),
            "derived_file_is_oracle_byte_identity": False,
            "mapping_sha256": _sha256(validation / "mapping_review.json"),
            "bitstream_sha256": _sha256(
                workload
                / "install/cfg_pkg/"
                "op0_decode_silu_fp16N_fp32N_bitstream_128b.bin"
            ),
            "execplan_sha256": _sha256(workload / "install/execplan.txt"),
            "native_empty_cache_rebuild_count": 2,
            "fixed_seed": 42,
        },
    )
    _copy(
        ROOT / "tools/decode_silu_control_server_runtime.py",
        package / "package_tools/decode_silu_control_server_runtime.py",
    )
    _copy(
        ROOT / "tools/requant_node0001_server_runtime.py",
        package / "package_tools/requant_node0001_server_runtime.py",
    )
    base._write_lf(
        package / "tb_probe" / OBSERVER_TAIL_NAME,
        _observer_tail(),
    )
    script = (
        base._run_script()
        .replace(
            "package_tools/requant_atomic_server_runtime.py",
            "package_tools/decode_silu_control_server_runtime.py",
        )
        .replace("+REQUANT_ATOMIC_PROBE", "+DECODE_SILU_CONTROL_PROBE")
        .replace("12h", "4h")
    )
    script = script.replace(
        f'install_name="{INSTALL_NAME}"\n',
        (
            f'install_name="{INSTALL_NAME}"\n'
            'tb_relative_path="native_return_observer.svh"\n'
        ),
    )
    script = script.replace(
        '"${common_tool}" install-probe',
        '"${runtime_tool}" install-probe',
    ).replace(
        '"${common_tool}" verify-probe-installed',
        '"${runtime_tool}" verify-probe-installed',
    ).replace(
        '"${common_tool}" restore-probe',
        '"${runtime_tool}" restore-probe',
    )
    script = script.replace(
        '--evidence-root "${evidence_root}" >/dev/null',
        (
            '--evidence-root "${evidence_root}" '
            '--tb-relative-path "${tb_relative_path}" >/dev/null'
        ),
    )
    script = script.replace(
        '--evidence-root "${evidence_root}" \\\n'
        '  --output "${evidence_root}/tb_probe_precompile_receipt.json"',
        (
            '--evidence-root "${evidence_root}" \\\n'
            '  --tb-relative-path "${tb_relative_path}" \\\n'
            '  --output "${evidence_root}/tb_probe_precompile_receipt.json"'
        ),
    )
    script = script.replace(
        '--evidence-root "${evidence_root}"   '
        '--output "${evidence_root}/tb_probe_precompile_receipt.json"',
        (
            '--evidence-root "${evidence_root}"   '
            '--tb-relative-path "${tb_relative_path}"   '
            '--output "${evidence_root}/tb_probe_precompile_receipt.json"'
        ),
    )
    base._write_lf(package / "PREPARE_AND_RUN.sh", script)
    base._write_lf(
        package / "README.md",
        (
            "# Native Decode SiLU FP16-to-FP32 stock-RTL control\n\n"
            "Run exactly one command from the extracted package directory:\n\n"
            "```bash\n"
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
            "```\n\n"
            "This FIRST_DYNAMIC control tests only the native shared SiLU SFU, "
            "FP16-to-FP32 conversion, normal outbuffer, capture-edge observer, "
            "and two independent 8-line formal D readbacks. It is not a "
            "Requant guard/round/alias/E4/E5 result and candidate_release "
            "remains false.\n"
        ),
    )
    records = base._records(package, exclude_manifest=True)
    manifest = {
        "schema": "decode-silu-fp16n-fp32n-control-stockrtl-package-v1",
        "install_name": INSTALL_NAME,
        "run_kind": "FIRST_DYNAMIC_CONTROL",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "candidate_release": False,
        "counts_as_requant_e4": False,
        "counts_as_requant_e5": False,
        "functional_rtl_file_count": 0,
        "rtl_or_tb_file_included": False,
        "observer_mode": "transactional_read_only_non_rtl_tail",
        "observer_capture_mode": "capture_edge_payload_witness",
        "tb_target_policy": {
            "target_root_source": (
                "single PREPARE_AND_RUN.sh NDP_copyXX argument"
            ),
            "relative_path": "native_return_observer.svh",
            "candidate_write_path_count": 1,
            "basename_find_glob_rglob_forbidden": True,
        },
        "claim": "shared native SFU/normal-outbuffer/observer path control only",
        "claim_excludes": [
            "Requant guard",
            "Requant round-only",
            "Requant alias lifetime",
            "Requant E4/E5",
        ],
        "server_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        ),
        "expected_return": [
            f"{INSTALL_NAME}_return.zip",
            f"{INSTALL_NAME}_return.zip.sha256",
        ],
        "rule_ids": [
            "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "CDA-SERVER-ONE-COMMAND-001",
            "CDA-SERVER-RETURN-RECEIPT-001",
            "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
            "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
            "CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001",
            "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
        ],
        "payload_tree_sha256": base._tree_sha256(records),
        "files": records,
    }
    _write_json(package / base.MANIFEST_NAME, manifest)
    preflight = runtime.preflight_package(package, INSTALL_NAME)
    return {"manifest": manifest, "preflight": preflight}


def _fresh_extract_self_check(package: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="decode-silu-control-check-") as temporary:
        root = Path(temporary)
        extract = root / "extract"
        extract.mkdir()
        with zipfile.ZipFile(package.with_suffix(".zip")) as archive:
            archive.extractall(extract)
        fresh = extract / INSTALL_NAME
        before = base._records(fresh)
        ndp = root / "NDP_copy_mock"
        evidence = root / "evidence"
        ndp.mkdir()
        evidence.mkdir()
        observer = ndp / "native_return_observer.svh"
        _copy(ROOT / "NDP_copy01/native_return_observer.svh", observer)
        preimage = observer.read_bytes()
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        runtime_tool = fresh / "package_tools/decode_silu_control_server_runtime.py"

        def run(tool: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
            completed = subprocess.run(
                [sys.executable, str(tool), *arguments],
                cwd=fresh,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                raise ControlPackageError(
                    f"fresh-extract self-check failed: {arguments[0]}: "
                    f"{completed.stderr.strip()}"
                )
            return completed

        preflight_output = root / "package_preflight.json"
        run(
            runtime_tool,
            "preflight-package",
            "--package-root",
            str(fresh),
            "--install-name",
            INSTALL_NAME,
            "--output",
            str(preflight_output),
        )
        run(
            runtime_tool,
            "install-probe",
            "--ndp-root",
            str(ndp),
            "--package-root",
            str(fresh),
            "--evidence-root",
            str(evidence),
            "--tb-relative-path",
            "native_return_observer.svh",
        )
        installed_sha256 = _sha256(observer)
        verify_output = evidence / "tb_probe_precompile_receipt.json"
        run(
            runtime_tool,
            "verify-probe-installed",
            "--ndp-root",
            str(ndp),
            "--evidence-root",
            str(evidence),
            "--tb-relative-path",
            "native_return_observer.svh",
            "--output",
            str(verify_output),
        )
        run(
            runtime_tool,
            "restore-probe",
            "--ndp-root",
            str(ndp),
            "--evidence-root",
            str(evidence),
            "--tb-relative-path",
            "native_return_observer.svh",
        )
        after = base._records(fresh)
        if observer.read_bytes() != preimage or before != after:
            raise ControlPackageError("bootstrap/probe transaction changed bytes")
        verify = json.loads(verify_output.read_text(encoding="utf-8"))
        return {
            "schema": "decode-silu-control-fresh-extract-self-check-v1",
            "status": "pass",
            "fresh_zip_extraction": True,
            "actual_packaged_runtime_entry": (
                "package_tools/decode_silu_control_server_runtime.py "
                "preflight-package"
            ),
            "actual_packaged_probe_entry": (
                "package_tools/decode_silu_control_server_runtime.py "
                "install-probe --tb-relative-path native_return_observer.svh"
            ),
            "python_dont_write_bytecode": True,
            "package_exact_tree_unchanged": True,
            "package_file_count": len(before),
            "package_tree_sha256": base._tree_sha256(before),
            "observer_installed_sha256": installed_sha256,
            "observer_xmr_elaboration_gate": verify["xmr_elaboration_gate"],
            "observer_restored_byte_exact": True,
            "run_script_entry_present": (fresh / "PREPARE_AND_RUN.sh").is_file(),
        }


def _validate_zip(package: Path) -> dict[str, Any]:
    preflight = runtime.preflight_package(package, INSTALL_NAME)
    zip_path = package.with_suffix(".zip")
    sidecar = zip_path.with_suffix(".zip.sha256")
    if not zip_path.is_file() or not sidecar.is_file():
        raise ControlPackageError("ZIP or sidecar is missing")
    digest = _sha256(zip_path)
    if sidecar.read_text(encoding="ascii") != f"{digest}  {zip_path.name}\n":
        raise ControlPackageError("ZIP sidecar differs")
    with zipfile.ZipFile(zip_path) as archive:
        expected = [
            f"{package.name}/{path.relative_to(package).as_posix()}"
            for path in sorted(item for item in package.rglob("*") if item.is_file())
        ]
        if archive.namelist() != expected:
            raise ControlPackageError("ZIP exact-set/order differs")
        for name in expected:
            relative = Path(*name.split("/")[1:])
            if archive.read(name) != (package / relative).read_bytes():
                raise ControlPackageError(f"ZIP payload differs: {name}")
            if "rtl" in {part.lower() for part in Path(name).parts}:
                raise ControlPackageError(f"ZIP contains rtl/ entry: {name}")
    return {
        **preflight,
        "zip_exact_set": True,
        "zip_sha256": digest,
        "zip_size_bytes": zip_path.stat().st_size,
        "sidecar": sidecar.as_posix(),
    }


def build_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output = output.resolve()
    if output.name != INSTALL_NAME:
        raise ControlPackageError(f"output directory must be named {INSTALL_NAME}")
    previous = base.INSTALL_NAME
    base.INSTALL_NAME = INSTALL_NAME
    try:
        base._fresh_final_targets(output)
        read_receipt = _verify_sources()
        with tempfile.TemporaryDirectory(
            prefix="decode-silu-control-a-"
        ) as left_parent, tempfile.TemporaryDirectory(
            prefix="decode-silu-control-b-"
        ) as right_parent:
            left = Path(left_parent) / INSTALL_NAME
            right = Path(right_parent) / INSTALL_NAME
            left_report = _build_tree(left, read_receipt)
            _build_tree(right, read_receipt)
            left_zip, left_sha = base._zip_tree(left)
            right_zip, right_sha = base._zip_tree(right)
            if (
                left_sha != right_sha
                or left_zip.read_bytes() != right_zip.read_bytes()
                or base._records(left) != base._records(right)
            ):
                raise ControlPackageError("two deterministic builds differ")
            shutil.copytree(right, output)
            shutil.copyfile(right_zip, output.with_suffix(".zip"))
            shutil.copyfile(
                right_zip.with_suffix(".zip.sha256"),
                output.with_suffix(".zip.sha256"),
            )
        validation = _validate_zip(output)
        # The sole full fresh-extract package self-check is intentionally last.
        self_check = _fresh_extract_self_check(output)
        report = {
            "schema": "decode-silu-control-package-validation-v1",
            "status": "PACKAGE_READY_NOT_RUN",
            "package": output.as_posix(),
            "zip": output.with_suffix(".zip").as_posix(),
            "zip_size_bytes": output.with_suffix(".zip").stat().st_size,
            "zip_sha256": validation["zip_sha256"],
            "sidecar": output.with_suffix(".zip.sha256").as_posix(),
            "manifest_sha256": _sha256(output / base.MANIFEST_NAME),
            "payload_tree_sha256": left_report["manifest"]["payload_tree_sha256"],
            "payload_file_count": len(left_report["manifest"]["files"]),
            "deterministic_build_count": 2,
            "deterministic_zip_byte_identical": True,
            "full_fresh_extract_self_check_count": 1,
            "fresh_extract_self_check": self_check,
            "functional_rtl_file_count": 0,
            "candidate_release": False,
            "counts_as_requant_e4": False,
            "counts_as_requant_e5": False,
            "server_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
            ),
            "expected_return": [
                f"{INSTALL_NAME}_return.zip",
                f"{INSTALL_NAME}_return.zip.sha256",
            ],
        }
        receipt = output.with_name(f"{INSTALL_NAME}_validation.json")
        report["validation_receipt"] = receipt.as_posix()
        _write_json(receipt, report)
        return report
    finally:
        base.INSTALL_NAME = previous


def validate_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    previous = base.INSTALL_NAME
    base.INSTALL_NAME = INSTALL_NAME
    try:
        zip_report = _validate_zip(output.resolve())
        preflight = runtime.preflight_package(output.resolve(), INSTALL_NAME)
        return {"zip": zip_report, "preflight": preflight}
    finally:
        base.INSTALL_NAME = previous


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
    except Exception as exc:
        print(f"decode SiLU control package failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
