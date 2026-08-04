#!/usr/bin/env python3
"""Fail-closed runtime for the native Decode SiLU stock-RTL control."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

try:
    import requant_node0001_server_runtime as common
except ModuleNotFoundError:
    from tools import requant_node0001_server_runtime as common


MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
RUNTIME_SCHEMA = "decode-silu-control-server-runtime-v1"
RESULT_SCHEMA = "decode-silu-control-server-result-v1"
RETURN_SCHEMA = "decode-silu-control-server-return-v1"
ACTIVE_SLICES = (0, 1)
EXEC_LINES = 3
PRELOAD_COUNT = 5
FORMAL_COUNT = 2
D_LINES = 8
EXPECTED_WDATA_PER_SLICE = 8
MAX_FILE_BYTES = 512 * 1024
MAX_EXTRACTED_BYTES = 4 * 1024 * 1024
MAX_ZIP_BYTES = 2 * 1024 * 1024


class ControlRuntimeError(RuntimeError):
    """Raised when the control package or its evidence fails closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return result


def _safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ControlRuntimeError(f"unsafe relative path: {value!r}")
    return relative


def _inside(root: Path, value: str | PurePosixPath) -> Path:
    relative = _safe_relative(value) if isinstance(value, str) else value
    base = root.resolve()
    target = base.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ControlRuntimeError(f"path escapes root: {relative}") from exc
    return target


def _validate_json(path: Path) -> Any:
    value = _load_json(path)
    if path.read_text(encoding="utf-8") != (
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    ):
        raise ControlRuntimeError(f"JSON is not canonical pretty LF: {path}")
    return value


def _validate_128(path: Path, count: int) -> list[str]:
    raw = path.read_bytes()
    lines = raw.decode("ascii").splitlines()
    if (
        b"\r" in raw
        or len(lines) != count
        or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines)
        or raw != ("\n".join(lines) + "\n").encode("ascii")
    ):
        raise ControlRuntimeError(f"invalid {count}-line 128-bit text: {path}")
    return lines


def _payload_local(package: Path, install_name: str, runtime_path: str) -> Path:
    prefix = f"../install/cfg_pkg/{install_name}/"
    if not runtime_path.startswith(prefix):
        raise ControlRuntimeError(f"payload outside unique namespace: {runtime_path}")
    return _inside(package / "workload/runtime", runtime_path[len(prefix) :])


def _manifest(package: Path, install_name: str) -> dict[str, Any]:
    manifest = _load_json(package / MANIFEST_NAME)
    if manifest.get("install_name") != install_name:
        raise ControlRuntimeError("install identity differs")
    if manifest.get("files") != _records(package, exclude_manifest=True):
        raise ControlRuntimeError("package payload differs from manifest exact set")
    return manifest


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = _manifest(package, install_name)
    if (
        manifest.get("candidate_release") is not False
        or manifest.get("counts_as_requant_e4") is not False
        or manifest.get("counts_as_requant_e5") is not False
        or manifest.get("run_kind") != "FIRST_DYNAMIC_CONTROL"
    ):
        raise ControlRuntimeError("control claim boundary differs")
    target_policy = manifest.get("tb_target_policy")
    if target_policy != {
        "target_root_source": "single PREPARE_AND_RUN.sh NDP_copyXX argument",
        "relative_path": "native_return_observer.svh",
        "candidate_write_path_count": 1,
        "basename_find_glob_rglob_forbidden": True,
    }:
        raise ControlRuntimeError("TB target directory-isolation policy differs")
    for relative in manifest["files"]:
        parts = {part.lower() for part in PurePosixPath(relative).parts}
        suffix = PurePosixPath(relative).suffix.lower()
        if "rtl" in parts or "__pycache__" in parts:
            raise ControlRuntimeError(f"forbidden package path: {relative}")
        if suffix in {
            ".pyc", ".pyo", ".zip", ".tar", ".tgz", ".gz", ".7z",
            ".v", ".sv", ".vh", ".vhd", ".vhdl", ".vcd", ".fsdb",
        }:
            raise ControlRuntimeError(f"forbidden package suffix: {relative}")
    runtime = package / "workload/runtime"
    sca = _validate_json(runtime / "sca_cfg.json")
    sca_d = _validate_json(runtime / "sca_cfg_D.json")
    if (
        sca.get("Exec_Base") != "0x0000_0C00"
        or sca.get("Exec_Length") != EXEC_LINES
        or sca.get("Repeat_Num") != 1
    ):
        raise ControlRuntimeError("execution identity differs")
    payloads = {
        key: value
        for key, value in sca.items()
        if isinstance(value, dict) and "path" in value
    }
    if len(payloads) != PRELOAD_COUNT:
        raise ControlRuntimeError("SCA preload exact count differs")
    for name, entry in payloads.items():
        target = _payload_local(package, install_name, entry["path"])
        if not target.is_file():
            raise ControlRuntimeError(f"missing runtime payload: {name}")
    _validate_128(
        _payload_local(package, install_name, sca["ExecutionPlan"]["path"]),
        EXEC_LINES,
    )
    _validate_128(
        _payload_local(package, install_name, sca["op0_config"]["path"]), 26
    )
    _validate_128(
        _payload_local(package, install_name, sca["op0_sfu_config"]["path"]), 50
    )
    expected_d = {
        "op0_matrixD_slice0": ("0x00000040", 8),
        "op0_matrixD_slice1": ("0x02000040", 8),
    }
    if set(sca_d) != set(expected_d):
        raise ControlRuntimeError("formal D exact set differs")
    for name, (address, length) in expected_d.items():
        if sca_d[name] != {
            "base_addr": address,
            "path": f"sim_results/formal_readback/{name}.txt",
            "length": length,
        }:
            raise ControlRuntimeError(f"formal D binding differs: {name}")
    for slice_id in ACTIVE_SLICES:
        _validate_128(
            runtime
            / f"install/op0/slice{slice_id:02d}/matrix_A_linearized_128bit.txt",
            4,
        )
        _validate_128(
            package
            / f"golden/slice{slice_id:02d}/matrix_D_linearized_128bit.txt",
            D_LINES,
        )
    tail = package / "tb_probe/requant_mse4_guard_observer_tail.svh"
    if not tail.is_file() or tail.stat().st_size > 64 * 1024:
        raise ControlRuntimeError("read-only control observer is missing or oversized")
    text = tail.read_text(encoding="utf-8")
    active = "\n".join(
        line.split("//", 1)[0]
        for line in text.splitlines()
        if not line.lstrip().startswith("//")
    ).lower()
    for forbidden in ("force ", "deposit", "release ", "<="):
        if forbidden in active:
            raise ControlRuntimeError(f"observer contains driver token: {forbidden}")
    if "+DECODE_SILU_CONTROL_PROBE" not in text:
        raise ControlRuntimeError("control observer plusarg differs")
    try:
        xmr = common.validate_observer_xmr_elaboration(text)
    except common.RequantRuntimeError as exc:
        raise ControlRuntimeError(str(exc)) from exc
    contract = _validate_json(
        package / "validation/decode_silu_control_contract.json"
    )
    if (
        contract.get("candidate_release") is not False
        or contract.get("oracle", {}).get("sha256")
        != "eafb7ec7cd47006dda15c1fc60d00601563a7a9f7e8ae12da3ce45e57baec6be"
    ):
        raise ControlRuntimeError("semantic contract identity differs")
    return {
        "schema": RUNTIME_SCHEMA,
        "status": "package_preflight_passed",
        "candidate_release": False,
        "active_slices": list(ACTIVE_SLICES),
        "start_comp_count": 1,
        "preload_count": PRELOAD_COUNT,
        "formal_readback_count": FORMAL_COUNT,
        "formal_lines_per_slice": D_LINES,
        "functional_rtl_file_count": 0,
        "observer_xmr_elaboration_gate": xmr,
    }


def preflight_installed(
    package_root: Path, ndp_root: Path, install_name: str
) -> dict[str, Any]:
    report = preflight_package(package_root, install_name)
    source = package_root.resolve() / "workload/runtime"
    installed = ndp_root.resolve() / "install/cfg_pkg" / install_name
    if not installed.is_dir() or _records(installed) != _records(source):
        raise ControlRuntimeError("installed namespace differs from package")
    return {**report, "status": "installed_preflight_passed"}


def _resolve_tb_target(ndp_root: Path, relative_value: str) -> tuple[Path, Path]:
    root = ndp_root.resolve(strict=True)
    relative = _safe_relative(relative_value)
    if relative.as_posix() != "native_return_observer.svh":
        raise ControlRuntimeError("manifest-bound TB relative path differs")
    literal = root.joinpath(*relative.parts)
    if literal.is_symlink():
        raise ControlRuntimeError("TB target symlink is forbidden")
    target = literal.resolve(strict=True)
    if target != literal or root not in target.parents:
        raise ControlRuntimeError("TB target escapes or differs from root/relative")
    return root, target


def _augment_probe_receipt(
    evidence_root: Path,
    *,
    root: Path,
    target: Path,
    preimage_size: int,
    preimage_sha256: str,
) -> dict[str, Any]:
    receipt_path = evidence_root.resolve() / "tb_probe_install_receipt.json"
    receipt = _load_json(receipt_path)
    receipt["target_directory_isolation"] = {
        "rule_id": "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
        "normalized_target_root": root.as_posix(),
        "normalized_unique_target_path": target.as_posix(),
        "manifest_relative_path": "native_return_observer.svh",
        "candidate_write_path_count": 1,
        "target_equals_root_plus_manifest_relative_path": True,
        "basename_find_glob_rglob_used": False,
        "preimage_size_bytes": preimage_size,
        "preimage_sha256": preimage_sha256,
    }
    _write_json(receipt_path, receipt)
    return receipt


def install_probe(
    ndp_root: Path,
    package_root: Path,
    evidence_root: Path,
    tb_relative_path: str,
) -> dict[str, Any]:
    root, target = _resolve_tb_target(ndp_root, tb_relative_path)
    preimage_size = target.stat().st_size
    preimage_sha = _sha256(target)
    common.install_probe(root, package_root.resolve(), evidence_root.resolve())
    return _augment_probe_receipt(
        evidence_root,
        root=root,
        target=target,
        preimage_size=preimage_size,
        preimage_sha256=preimage_sha,
    )


def verify_probe_installed(
    ndp_root: Path,
    evidence_root: Path,
    tb_relative_path: str,
    output: Path,
) -> dict[str, Any]:
    root, target = _resolve_tb_target(ndp_root, tb_relative_path)
    receipt_path = evidence_root.resolve() / "tb_probe_install_receipt.json"
    receipt = _load_json(receipt_path)
    isolation = receipt.get("target_directory_isolation", {})
    if (
        isolation.get("normalized_target_root") != root.as_posix()
        or isolation.get("normalized_unique_target_path") != target.as_posix()
        or isolation.get("candidate_write_path_count") != 1
    ):
        raise ControlRuntimeError("probe verify target differs from install target")
    result = common.verify_probe_installed(root, evidence_root.resolve())
    result["target_directory_isolation"] = isolation
    _write_json(output, result)
    return result


def restore_probe(
    ndp_root: Path,
    evidence_root: Path,
    tb_relative_path: str,
) -> dict[str, Any]:
    root, target = _resolve_tb_target(ndp_root, tb_relative_path)
    receipt_path = evidence_root.resolve() / "tb_probe_install_receipt.json"
    receipt = _load_json(receipt_path)
    isolation = receipt.get("target_directory_isolation", {})
    if (
        isolation.get("normalized_target_root") != root.as_posix()
        or isolation.get("normalized_unique_target_path") != target.as_posix()
        or isolation.get("candidate_write_path_count") != 1
    ):
        raise ControlRuntimeError("probe restore target differs from install target")
    preimage_size = int(isolation["preimage_size_bytes"])
    preimage_sha = str(isolation["preimage_sha256"])
    result = common.restore_probe(root, evidence_root.resolve())
    _augment_probe_receipt(
        evidence_root,
        root=root,
        target=target,
        preimage_size=preimage_size,
        preimage_sha256=preimage_sha,
    )
    return result


def _simulation_gate(run_dir: Path, install_name: str, status: int) -> dict[str, Any]:
    path = run_dir / "sim_results/sim.log"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    markers = {
        "sca": f"../install/cfg_pkg/{install_name}/sca_cfg.json" in text,
        "sca_d": f"../install/cfg_pkg/{install_name}/sca_cfg_D.json" in text,
        "preload": f"JSON config: {PRELOAD_COUNT} matrices loaded" in text,
        "readback": f"JSON_D config: {FORMAL_COUNT} matrices dumped" in text,
        "start": text.count("INFO: slice start") == 1,
        "finish": text.count("INFO: slice completed after") == 1,
        "success": "Simulation completed successfully!" in text,
    }
    forbidden = [
        token for token in ("Cannot open", "$fatal", "SIMULATION TIMEOUT")
        if token in text
    ]
    return {
        "passed": status == 0 and all(markers.values()) and not forbidden,
        "run_status": status,
        "markers": markers,
        "forbidden_markers": forbidden,
    }


def _formal_gate(package: Path, run_dir: Path) -> dict[str, Any]:
    records = []
    for slice_id in ACTIVE_SLICES:
        name = f"op0_matrixD_slice{slice_id}"
        actual = run_dir / f"sim_results/formal_readback/{name}.txt"
        golden = (
            package
            / f"golden/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        )
        try:
            actual_lines = _validate_128(actual, D_LINES)
            golden_lines = _validate_128(golden, D_LINES)
            passed = actual_lines == golden_lines and not any(
                set(line.lower()) & {"x", "z"} for line in actual_lines
            )
            error = None
        except Exception as exc:
            passed = False
            error = str(exc)
            actual_lines = []
            golden_lines = _validate_128(golden, D_LINES)
        first = next(
            (
                index
                for index, (lhs, rhs) in enumerate(zip(actual_lines, golden_lines))
                if lhs != rhs
            ),
            None,
        )
        records.append(
            {
                "slice": slice_id,
                "passed": passed,
                "line_count": len(actual_lines),
                "first_mismatch_line": first,
                "actual_sha256": _sha256(actual) if actual.is_file() else None,
                "golden_sha256": _sha256(golden),
                "error": error,
            }
        )
    return {"passed": all(item["passed"] for item in records), "records": records}


def _observer_gate(run_dir: Path) -> dict[str, Any]:
    required = {
        "SFU_PREPROCESS_INPUT_CAPTURE": 32,
        "SFU_BST_RESULT_CAPTURE": 32,
        "SFU_COEFF_CAPTURE": 32,
        "SFU_ALU_INPUT_CAPTURE": 32,
        "SFU_ALU_RESULT_ACCEPTED": 32,
        "SFU_POSTPROCESS_RESULT_ACCEPTED": 32,
        "NORMAL_OUTBUFFER_INPUT_ACCEPTED": 32,
        "NORMAL_OUTBUFFER_WRITE_COMMIT": 32,
        "NORMAL_OUTPORT_ACCEPTED": 32,
        "MSE4_WDATA": EXPECTED_WDATA_PER_SLICE,
    }
    records = []
    for slice_id in ACTIVE_SLICES:
        path = (
            run_dir
            / f"sim_results/decode_silu_control_probe/slice{slice_id:02d}.log"
        )
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        counts = {
            boundary: len(
                re.findall(rf"(?:boundary={re.escape(boundary)}\b|\b{re.escape(boundary)}\b)", text)
            )
            for boundary in required
        }
        data_words = [
            int(match, 16)
            for match in re.findall(r"\bdata=0x([0-9a-fA-F]{8,32})\b", text)
        ]
        passed = all(counts[name] == count for name, count in required.items())
        records.append(
            {
                "slice": slice_id,
                "passed": passed,
                "counts": counts,
                "expected_counts": required,
                "captured_data_word_count": len(data_words),
                "captured_nonzero_count": sum(value != 0 for value in data_words),
                "log_sha256": _sha256(path) if path.is_file() else None,
            }
        )
    return {"passed": all(item["passed"] for item in records), "records": records}


def analyze(
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
    output: Path,
) -> dict[str, Any]:
    package = package_root.resolve()
    preflight = preflight_package(package, install_name)
    simulation = _simulation_gate(run_dir.resolve(), install_name, run_status)
    formal = _formal_gate(package, run_dir.resolve())
    observer = _observer_gate(run_dir.resolve())
    identity_path = evidence_root.resolve() / "stock_rtl_identity_receipt.json"
    identity = _load_json(identity_path) if identity_path.is_file() else {}
    identity_passed = (
        identity.get("functional_rtl_unchanged") is True
        and identity.get("tb_probe_transactionally_restored") is True
    )
    passed = (
        simulation["passed"]
        and formal["passed"]
        and observer["passed"]
        and identity_passed
    )
    if not simulation["passed"]:
        divergence = "SIMULATION_OR_LIFECYCLE_INCOMPLETE"
    elif not formal["passed"]:
        divergence = "FORMAL_D_BIT_MISMATCH"
    elif not observer["passed"]:
        divergence = "CAPTURE_EDGE_OBSERVER_COVERAGE_INCOMPLETE"
    elif not identity_passed:
        divergence = "STOCK_RTL_OR_PROBE_IDENTITY_INCOMPLETE"
    else:
        divergence = None
    result = {
        "schema": RESULT_SCHEMA,
        "status": "pass" if passed else "fail",
        "candidate_release": False,
        "counts_as_requant_e4": False,
        "counts_as_requant_e5": False,
        "claim": "shared native SFU/normal-outbuffer/observer control only",
        "preflight": preflight,
        "simulation": simulation,
        "formal_d": formal,
        "capture_edge_observer": observer,
        "stock_identity_passed": identity_passed,
        "first_divergence": divergence,
    }
    _write_json(output, result)
    return result


def _copy_if_file(source: Path, target: Path, *, tail_limit: int | None = None) -> None:
    if not source.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if tail_limit is None or source.stat().st_size <= tail_limit:
        shutil.copyfile(source, target)
    else:
        data = source.read_bytes()[-tail_limit:]
        target.write_bytes(data)


def collect_return(
    ndp_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    output = root / f"{install_name}_return"
    zip_path = output.with_suffix(".zip")
    sidecar = Path(f"{zip_path}.sha256")
    for target in (output, zip_path, sidecar):
        if target.exists():
            raise ControlRuntimeError(f"fresh return identity required: {target}")
    output.mkdir()
    _copy_if_file(package / MANIFEST_NAME, output / "TEST_PACKAGE_MANIFEST.json")
    _copy_if_file(
        package / "validation/decode_silu_control_contract.json",
        output / "validation/decode_silu_control_contract.json",
    )
    for name in (
        "package_preflight.json", "installed_preflight.json",
        "server_identity_pre_install.json",
        "server_identity_post_probe_install.json",
        "server_identity_post_compile.json", "server_identity_post_run.json",
        "server_identity_post_restore.json", "tb_probe_install_receipt.json",
        "tb_probe_precompile_receipt.json", "stock_rtl_identity_receipt.json",
        "compile_exit_status.txt", "sim_exit_status.txt", "run_exit_status.txt",
        "termination_signal.txt", "SERVER_RESULT_GATE.json", "server_command.txt",
    ):
        _copy_if_file(evidence / name, output / "evidence" / name)
    _copy_if_file(
        run / "sim_results/sim.log",
        output / "run/sim.log.tail.txt",
        tail_limit=160_000,
    )
    _copy_if_file(
        run / "sim_results/compile_driver.log",
        output / "run/compile_driver.log.tail.txt",
        tail_limit=160_000,
    )
    for slice_id in ACTIVE_SLICES:
        _copy_if_file(
            run / f"sim_results/decode_silu_control_probe/slice{slice_id:02d}.log",
            output / f"run/observer/slice{slice_id:02d}.log",
        )
        name = f"op0_matrixD_slice{slice_id}"
        _copy_if_file(
            run / f"sim_results/formal_readback/{name}.txt",
            output / f"run/formal_readback/{name}.txt",
        )
    files = _records(output)
    receipt = {
        "schema": RETURN_SCHEMA,
        "status": "collected",
        "install_name": install_name,
        "run_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    _write_json(output / "RETURN_RECEIPT.json", receipt)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in output.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(output).as_posix())
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    if zip_path.stat().st_size > MAX_ZIP_BYTES:
        raise ControlRuntimeError("return ZIP exceeds limit")
    digest = _sha256(zip_path)
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    return {
        "schema": RETURN_SCHEMA,
        "status": "return_zip_created",
        "zip": zip_path.as_posix(),
        "zip_sha256": digest,
        "sidecar": sidecar.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight-package")
    pre.add_argument("--package-root", type=Path, required=True)
    pre.add_argument("--install-name", required=True)
    pre.add_argument("--output", type=Path)
    installed = sub.add_parser("preflight-installed")
    installed.add_argument("--package-root", type=Path, required=True)
    installed.add_argument("--ndp-root", type=Path, required=True)
    installed.add_argument("--install-name", required=True)
    installed.add_argument("--output", type=Path)
    install_probe_parser = sub.add_parser("install-probe")
    install_probe_parser.add_argument("--ndp-root", type=Path, required=True)
    install_probe_parser.add_argument("--package-root", type=Path, required=True)
    install_probe_parser.add_argument("--evidence-root", type=Path, required=True)
    install_probe_parser.add_argument("--tb-relative-path", required=True)
    verify_probe_parser = sub.add_parser("verify-probe-installed")
    verify_probe_parser.add_argument("--ndp-root", type=Path, required=True)
    verify_probe_parser.add_argument("--evidence-root", type=Path, required=True)
    verify_probe_parser.add_argument("--tb-relative-path", required=True)
    verify_probe_parser.add_argument("--output", type=Path, required=True)
    restore_probe_parser = sub.add_parser("restore-probe")
    restore_probe_parser.add_argument("--ndp-root", type=Path, required=True)
    restore_probe_parser.add_argument("--evidence-root", type=Path, required=True)
    restore_probe_parser.add_argument("--tb-relative-path", required=True)
    analysis = sub.add_parser("analyze")
    analysis.add_argument("--package-root", type=Path, required=True)
    analysis.add_argument("--install-name", required=True)
    analysis.add_argument("--evidence-root", type=Path, required=True)
    analysis.add_argument("--run-dir", type=Path, required=True)
    analysis.add_argument("--run-status", type=int, required=True)
    analysis.add_argument("--output", type=Path, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--ndp-root", type=Path, required=True)
    collect.add_argument("--package-root", type=Path, required=True)
    collect.add_argument("--install-name", required=True)
    collect.add_argument("--evidence-root", type=Path, required=True)
    collect.add_argument("--run-dir", type=Path, required=True)
    collect.add_argument("--run-status", type=int, required=True)
    collect.add_argument("--server-command", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight-package":
            result = preflight_package(args.package_root, args.install_name)
        elif args.command == "preflight-installed":
            result = preflight_installed(
                args.package_root, args.ndp_root, args.install_name
            )
        elif args.command == "install-probe":
            result = install_probe(
                args.ndp_root, args.package_root, args.evidence_root,
                args.tb_relative_path
            )
        elif args.command == "verify-probe-installed":
            result = verify_probe_installed(
                args.ndp_root, args.evidence_root, args.tb_relative_path,
                args.output
            )
        elif args.command == "restore-probe":
            result = restore_probe(
                args.ndp_root, args.evidence_root, args.tb_relative_path
            )
        elif args.command == "analyze":
            result = analyze(
                args.package_root, args.install_name, args.evidence_root,
                args.run_dir, args.run_status, args.output
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "pass" else 1
        else:
            result = collect_return(
                args.ndp_root, args.package_root, args.install_name,
                args.evidence_root, args.run_dir, args.run_status,
                args.server_command
            )
        if getattr(args, "output", None):
            _write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"decode SiLU control runtime failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
