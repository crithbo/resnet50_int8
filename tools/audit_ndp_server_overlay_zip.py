#!/usr/bin/env python3
"""Independent, fresh-extraction audit for an NDP server overlay ZIP.

This intentionally does not import the package generator or its validators.  It is
the second self-check entry point: all hashes and counts are recomputed from the
ZIP bytes after extraction into a new temporary directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping


SHA256_RE = re.compile(r"[0-9a-f]{64}")
BITS128_RE = re.compile(rb"[01]{128}")
AXI_DATA_BYTES = 16
AXI_MAX_BURST_BEATS = 256
AXI_PAGE_BYTES = 4096


class AuditError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditError(f"cannot read JSON object: {path}") from error
    if not isinstance(value, dict):
        raise AuditError(f"JSON root is not an object: {path}")
    return value


def safe_relative(raw: str, *, label: str) -> PurePosixPath:
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if (
        not raw
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.anchor)
        or "\\" in raw
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise AuditError(f"unsafe {label}: {raw!r}")
    return posix


def resolve_inside(root: Path, raw: str, *, label: str) -> Path:
    relative = safe_relative(raw, label=label)
    candidate = root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise AuditError(f"{label} escapes extraction root: {raw}") from error
    return candidate


def count_128bit_lines(path: Path) -> int:
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"SCA payload is not a regular file: {path}")
    count = 0
    with path.open("rb") as stream:
        for count, raw_line in enumerate(stream, 1):
            if not raw_line.endswith(b"\n"):
                raise AuditError(f"SCA payload has a partial final line: {path}")
            line = raw_line[:-1]
            if not BITS128_RE.fullmatch(line):
                raise AuditError(f"SCA payload line is not 128-bit binary: {path}:{count}")
    if count == 0:
        raise AuditError(f"SCA payload is empty: {path}")
    return count


def validate_axi_bursts(address: int, beats: int, *, label: str) -> None:
    if address < 0 or address % AXI_DATA_BYTES or beats <= 0:
        raise AuditError(f"invalid AXI transfer geometry: {label}")
    remaining = beats
    current = address
    while remaining:
        burst = min(remaining, AXI_MAX_BURST_BEATS)
        if current % AXI_PAGE_BYTES + burst * AXI_DATA_BYTES > AXI_PAGE_BYTES:
            raise AuditError(f"AXI burst crosses a 4-KiB boundary: {label}")
        current += burst * AXI_DATA_BYTES
        remaining -= burst


def sca_transfers(sca: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    result: list[tuple[str, Mapping[str, Any]]] = []
    for key, value in sca.items():
        if not isinstance(value, Mapping):
            continue
        nested = value.get("chunked_transport")
        if key == "ExecutionPlan" and isinstance(nested, Mapping):
            result.append((key, nested))
        elif isinstance(value.get("base_addr"), str) and isinstance(value.get("path"), str):
            result.append((key, value))
    return result


def extract_fresh(zip_path: Path, destination: Path) -> list[str]:
    names: list[str] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        seen: set[str] = set()
        for info in archive.infolist():
            raw = info.filename
            relative = safe_relative(raw.rstrip("/"), label="ZIP member")
            if raw in seen:
                raise AuditError(f"duplicate ZIP member: {raw}")
            seen.add(raw)
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(unix_mode):
                raise AuditError(f"ZIP contains a symlink: {raw}")
            if info.is_dir():
                destination.joinpath(*relative.parts).mkdir(parents=True, exist_ok=True)
                continue
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            names.append(raw)
    return names


def audit(args: argparse.Namespace) -> dict[str, Any]:
    zip_path = args.zip.resolve()
    sidecar_path = args.sidecar.resolve() if args.sidecar else Path(str(zip_path) + ".sha256")
    if not zip_path.is_file() or not sidecar_path.is_file():
        raise AuditError("ZIP or SHA-256 sidecar is missing")
    zip_sha256 = sha256_file(zip_path)
    expected_sidecar = f"{zip_sha256}  {zip_path.name}\n"
    if sidecar_path.read_text(encoding="ascii") != expected_sidecar:
        raise AuditError("ZIP SHA-256 sidecar differs from recomputed archive identity")

    with tempfile.TemporaryDirectory(prefix="ndp_overlay_audit_") as temp_dir:
        extracted = Path(temp_dir)
        zip_names = extract_fresh(zip_path, extracted)
        actual_files = {
            path.relative_to(extracted).as_posix(): path
            for path in extracted.rglob("*")
            if path.is_file()
        }
        if set(zip_names) != set(actual_files):
            raise AuditError("fresh extraction file set differs from ZIP member set")
        if any(path.is_symlink() for path in extracted.rglob("*")):
            raise AuditError("fresh extraction contains a symlink")
        if any(PurePosixPath(name).suffix.lower() in {".v", ".sv"} for name in actual_files):
            raise AuditError("overlay contains forbidden HDL source")

        overlay_manifest_path = extracted / "OVERLAY_MANIFEST.json"
        overlay = load_object(overlay_manifest_path)
        records = overlay.get("files")
        if not isinstance(records, list):
            raise AuditError("overlay file contract is not a list")
        expected_files: dict[str, tuple[int, str]] = {}
        for record in records:
            if not isinstance(record, Mapping):
                raise AuditError("overlay file contract record is not an object")
            raw_path = str(record.get("path", ""))
            safe_relative(raw_path, label="overlay file contract path")
            digest = str(record.get("sha256", ""))
            size = record.get("size_bytes")
            if raw_path in expected_files or not SHA256_RE.fullmatch(digest) or not isinstance(size, int):
                raise AuditError(f"invalid/duplicate overlay file record: {raw_path}")
            expected_files[raw_path] = (size, digest)
        if set(actual_files) != set(expected_files) | {"OVERLAY_MANIFEST.json"}:
            raise AuditError("overlay manifest exact file set differs from fresh extraction")
        for raw_path, (size, digest) in expected_files.items():
            path = actual_files[raw_path]
            if path.stat().st_size != size or sha256_file(path) != digest:
                raise AuditError(f"overlay file identity differs: {raw_path}")

        text_contract = overlay.get("text_file_contract")
        if not isinstance(text_contract, Mapping) or not isinstance(text_contract.get("paths"), list):
            raise AuditError("overlay text contract is invalid")
        for raw_path in text_contract["paths"]:
            path = resolve_inside(extracted, str(raw_path), label="text contract path")
            payload = path.read_bytes()
            if b"\r" in payload or (payload and not payload.endswith(b"\n")):
                raise AuditError(f"text contract is not complete LF-only text: {raw_path}")

        revision = args.revision
        readme_path = extracted / f"README_SERVER_{revision.upper()}.txt"
        if not readme_path.is_file():
            raise AuditError("revisioned server README is missing")
        expected_sidecar_command = f"sha256sum -c {zip_path.name}.sha256"
        readme_text = readme_path.read_text(encoding="utf-8")
        if expected_sidecar_command not in readme_text:
            raise AuditError(
                "server README does not name the delivered ZIP SHA-256 sidecar"
            )
        if not all(
            f"SERVER_RUN_ID={run_id} bash RUN_SERVER_{revision.upper()}.sh" in readme_text
            for run_id in ("run1", "run2")
        ):
            raise AuditError("server README does not require two preserved formal runs")
        ndp_root = extracted / "NDP_copy01"
        package_root = ndp_root / "install" / "cfg_pkg" / f"hwop-0004-00-{revision}"
        if not package_root.is_dir():
            raise AuditError("revisioned install package is missing")
        package_manifest_path = package_root / "metadata" / "manifest.json"
        package_manifest = load_object(package_manifest_path)
        if sha256_file(package_manifest_path) != overlay.get("package_manifest_sha256"):
            raise AuditError("package manifest identity differs from overlay binding")
        runtime_identity_path = package_root / "metadata" / "runtime_identity.json"
        runtime_identity = load_object(runtime_identity_path)
        if sha256_file(runtime_identity_path) != overlay.get("runtime_identity", {}).get("sha256"):
            raise AuditError("runtime identity differs from overlay binding")

        expected_counts = {
            "bank_data_file_count": args.expected_banks,
            "exec_128bit_line_count": args.expected_exec_lines,
            "runtime_operator_count": args.expected_stages,
        }
        for key, expected in expected_counts.items():
            if package_manifest.get(key) != expected:
                raise AuditError(f"package count differs: {key}")
        if runtime_identity.get("expected_testbench_repeat_num") != args.expected_repeat:
            raise AuditError("Repeat_Num differs from the approved runtime identity")
        if runtime_identity.get("expected_runtime_transfer_count") != args.expected_preloads:
            raise AuditError("preload count differs from the approved runtime identity")
        if runtime_identity.get("expected_region_count") != args.expected_readbacks:
            raise AuditError("readback count differs from the approved runtime identity")

        runner_record = runtime_identity.get("runner")
        identity_record = runtime_identity.get("runner_identity")
        if not isinstance(runner_record, Mapping) or not isinstance(identity_record, Mapping):
            raise AuditError("runner identity records are missing")
        runner_path = resolve_inside(extracted, str(runner_record.get("path", "")), label="runner path")
        runner_hash = sha256_file(runner_path)
        if runner_hash != runner_record.get("sha256"):
            raise AuditError("runner hash differs from runtime identity")
        runner_identity_path = resolve_inside(
            extracted, str(identity_record.get("path", "")), label="runner sidecar path"
        )
        if sha256_file(runner_identity_path) != identity_record.get("sha256"):
            raise AuditError("runner sidecar hash differs from runtime identity")
        if runner_identity_path.read_text(encoding="ascii") != f"{runner_hash}  {runner_path.name}\n":
            raise AuditError("runner self identity content differs")
        runner_text = runner_path.read_text(encoding="utf-8")
        if "set -Eeuo pipefail" not in runner_text:
            raise AuditError("runner strict shell mode is missing")
        if "git " in runner_text:
            raise AuditError("server runner must not depend on Git")
        for prohibited_snippet in (
            "validate_active_filelist_recursive",
            "validated_external_include_count",
            "server_filelist_member_outside_root",
            "testbench_continuous_transfer_burst_capability_mismatch",
            "server_make_effective_command_mismatch",
        ):
            if prohibited_snippet in runner_text:
                raise AuditError(
                    f"runner retains an overstrict source preflight: {prohibited_snippet}"
                )
        try:
            run_id_index = runner_text.index(
                'requested_server_run_id="${SERVER_RUN_ID:-run1}"'
            )
            identity_index = runner_text.index(
                "actual_runner_hash_line=$(sha256sum"
            )
            cleanup_index = runner_text.index(
                "# A run ID owns exactly one canonical return directory/archive"
            )
            trap_index = runner_text.index("trap unexpected_runner_error ERR")
            command_gate_index = runner_text.index("missing_server_commands=()")
        except ValueError as error:
            raise AuditError("runner identity/cleanup ordering markers are missing") from error
        if not run_id_index < identity_index < trap_index < command_gate_index < cleanup_index:
            raise AuditError(
                "runner identity/trap/command gate is not complete before evidence cleanup"
            )
        if "mkdir " in runner_text[:identity_index] or "rm " in runner_text[:identity_index]:
            raise AuditError("runner mutates evidence before authenticating itself")
        expected_runtime_log_policy = {
            "policy": "audited_sinks_unknown_log_guard_v2",
            "expected_sink_count": 1037,
            "allowed_regular_files": [
                "gexec2slice/slice_all/gexec2slice.log"
            ],
            "runtime_total_size_limit_bytes": 1073741824,
            "overlay_symlinks_allowed": False,
            "return_symlinks_allowed": False,
        }
        if runtime_identity.get("runtime_log_sink_policy") != expected_runtime_log_policy:
            raise AuditError("runtime unknown-log/total-size guard policy differs")

        argv_record = runtime_identity.get("run_command_contract")
        if not isinstance(argv_record, Mapping):
            raise AuditError("run-command contract identity is missing")
        argv_path = resolve_inside(extracted, str(argv_record.get("path", "")), label="run argv path")
        argv = argv_path.read_text(encoding="utf-8").splitlines()
        if len(argv) != 13 or argv_record.get("argument_count") != 13:
            raise AuditError("run argv must contain exactly 13 arguments")
        for argument in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"):
            if argv.count(argument) != 1:
                raise AuditError(f"run argv is missing exact waveform disable argument: {argument}")
        if "v10r8_sim_no_archive".replace("v10r8", revision) not in argv:
            raise AuditError("run argv is missing the revisioned no-archive target")

        policy = runtime_identity.get("immutable_testbench_capability_attestation")
        if not isinstance(policy, Mapping):
            raise AuditError("server entrypoint capability policy is missing")
        if policy.get("schema_version") != "resnet50-server-entrypoint-capability-policy-0.8":
            raise AuditError("server entrypoint capability policy version differs")
        if policy.get("identity_policy") != (
            "logical_entrypoints_unpinned_source_provenance"
        ):
            raise AuditError("server entrypoint capability identity policy differs")
        if policy.get("prestart_source_hash_required") is not False:
            raise AuditError("server source policy incorrectly pins server HDL content")
        required_entrypoints = policy.get("required_entrypoints")
        if required_entrypoints != [
            "Makefile.tb_NDP_Top_new_phy",
            "tb_NDP_Top_new_phy.sv",
            "rtl/filelists/NDP_Top_phy_filelist.f",
        ]:
            raise AuditError("server entrypoint contract differs")
        if (
            policy.get("recursive_filelist_validation_required") is not False
            or policy.get("logical_filelist_readability_required") is not True
            or policy.get("include_directory_validation_required") is not False
            or policy.get(
                "external_vendor_include_tree_equivalence_required"
            )
            is not False
            or policy.get("physical_source_path_inside_server_root_required")
            is not False
            or policy.get("server_source_content_scan_required") is not False
            or policy.get("transport_contract_source")
            != "package_axi4_4kb_report"
            or policy.get("make_effective_command_check_required") is not False
            or policy.get("static_install_exact_set_required") is not True
            or policy.get("make_environment_policy")
            != "unset_MAKEFLAGS_MAKEFILES_GNUMAKEFLAGS_MFLAGS_MAKELEVEL_before_launch"
        ):
            raise AuditError("minimal server-entrypoint capability policy differs")
        if any(token in runner_text for token in ("exit 11", "exit 14", "exit 15")):
            raise AuditError("runner bypasses unified failure archival")
        run_id_policy = runtime_identity.get("server_run_id_policy")
        if (
            not isinstance(run_id_policy, Mapping)
            or run_id_policy.get("default") != "run1"
            or run_id_policy.get("syntax") != "run1|run2"
            or run_id_policy.get("required_formal_run_ids") != ["run1", "run2"]
            or run_id_policy.get("preserve_distinct_archives") is not True
            or overlay.get("expected_return_archive")
            != f"run/sim_results_{revision}_<SERVER_RUN_ID>.zip"
            or overlay.get("required_formal_return_archives")
            != [
                f"run/sim_results_{revision}_run1.zip",
                f"run/sim_results_{revision}_run2.zip",
            ]
        ):
            raise AuditError("two-run result identity/preservation policy differs")
        server_source_policy = runtime_identity.get("server_source_policy")
        if (
            not isinstance(server_source_policy, Mapping)
            or server_source_policy.get("mode")
            != "readable_logical_entrypoints_with_nonblocking_provenance"
            or server_source_policy.get("content_hash_required") is not False
            or server_source_policy.get("actual_hash_inventory_required")
            != "entrypoints_and_DIR_HOME"
            or server_source_policy.get("include_directory_validation_required")
            is not False
            or server_source_policy.get(
                "external_vendor_include_tree_equivalence_required"
            )
            is not False
            or server_source_policy.get("physical_source_path_inside_server_root_required")
            is not False
            or server_source_policy.get("required_entrypoints") != required_entrypoints
        ):
            raise AuditError("runtime server-source inventory policy differs")
        if (
            runtime_identity.get("make_environment_policy")
            != "unset_MAKEFLAGS_MAKEFILES_GNUMAKEFLAGS_MFLAGS_MAKELEVEL_before_launch"
            or runtime_identity.get("static_install_exact_set_policy")
            != "launch_manifest_plus_four_content_addressed_identity_files"
        ):
            raise AuditError("runtime make/static-install policy differs")
        runner_contract_path = package_root / "metadata" / "runner_contract.json"
        required_return_metadata = load_object(runner_contract_path).get(
            "required_return_metadata"
        )
        required_provenance_fields = {
            "server_run_id",
            "execution_environment",
            "board_version",
            "firmware_version",
            "isa_contract",
            "server_source_provenance",
        }
        if not isinstance(required_return_metadata, list) or not required_provenance_fields.issubset(
            set(required_return_metadata)
        ):
            raise AuditError("server return provenance metadata contract is incomplete")

        sca_path = package_root / "sca_cfg.json"
        sca_d_path = package_root / "sca_cfg_D.json"
        sca = load_object(sca_path)
        sca_d = load_object(sca_d_path)
        if sca.get("Repeat_Num") != args.expected_repeat:
            raise AuditError("serialized SCA Repeat_Num differs")
        transfers = sca_transfers(sca)
        if len(transfers) != args.expected_preloads:
            raise AuditError("serialized SCA preload transfer count differs")
        payload_line_counts: dict[Path, int] = {}
        for key, entry in transfers:
            try:
                address = int(str(entry["base_addr"]).replace("_", ""), 16)
                raw_path = str(entry["path"])
            except (KeyError, TypeError, ValueError) as error:
                raise AuditError(f"invalid SCA transfer: {key}") from error
            payload_path = resolve_inside(ndp_root, raw_path, label=f"SCA payload ({key})")
            if payload_path not in payload_line_counts:
                payload_line_counts[payload_path] = count_128bit_lines(payload_path)
            beats = payload_line_counts[payload_path]
            declared = entry.get("line_count_128bit")
            if declared is not None and declared != beats:
                raise AuditError(f"SCA transfer line count differs: {key}")
            validate_axi_bursts(address, beats, label=f"SCA {key}")

        if len(sca_d) != args.expected_readbacks:
            raise AuditError("serialized SCA_D readback count differs")
        expected_regions: dict[str, int] = {}
        for key, entry in sca_d.items():
            if not isinstance(entry, Mapping):
                raise AuditError(f"invalid SCA_D entry: {key}")
            try:
                address = int(str(entry["base_addr"]).replace("_", ""), 16)
                length = int(entry["length"])
                raw_path = str(entry["path"])
            except (KeyError, TypeError, ValueError) as error:
                raise AuditError(f"invalid SCA_D entry: {key}") from error
            safe_relative(raw_path, label=f"SCA_D output ({key})")
            if raw_path in expected_regions:
                raise AuditError(f"duplicate SCA_D output path: {raw_path}")
            expected_regions[raw_path] = length
            validate_axi_bursts(address, length, label=f"SCA_D {key}")
        readback_path = resolve_inside(
            extracted,
            str(runtime_identity.get("readback_region_contract", {}).get("path", "")),
            label="readback contract path",
        )
        observed_regions: dict[str, int] = {}
        for line_number, line in enumerate(readback_path.read_text(encoding="utf-8").splitlines(), 1):
            fields = line.split("\t")
            if len(fields) != 2:
                raise AuditError(f"invalid readback contract line: {line_number}")
            raw_path, raw_length = fields
            if raw_path in observed_regions:
                raise AuditError(f"duplicate readback contract path: {raw_path}")
            observed_regions[raw_path] = int(raw_length)
        if observed_regions != expected_regions:
            raise AuditError("readback contract differs from serialized SCA_D")

        bindings = package_manifest.get("bitstream_bindings")
        if not isinstance(bindings, Mapping) or bindings.get("status") != "json_official_encoder_freeze_install_bound":
            raise AuditError("JSON/official-encoder/install bitstream binding status differs")
        binding_records = bindings.get("records")
        if not isinstance(binding_records, list) or len(binding_records) != 9:
            raise AuditError("bitstream binding record count differs")
        for record in binding_records:
            if not isinstance(record, Mapping) or not SHA256_RE.fullmatch(str(record.get("config_sha256", ""))):
                raise AuditError("bitstream binding has an invalid JSON config identity")
            install = record.get("install")
            if not isinstance(install, Mapping):
                raise AuditError("bitstream binding install record is missing")
            install_path = resolve_inside(package_root, str(install.get("path", "")), label="install bitstream")
            digest = sha256_file(install_path)
            line_count = count_128bit_lines(install_path)
            if (
                digest != install.get("raw_sha256")
                or digest != install.get("logical_sha256")
                or install_path.stat().st_size != install.get("raw_size_bytes")
                or line_count != install.get("line_count")
            ):
                raise AuditError("final install bitstream differs from its binding record")

        execplan_path = package_root / "install" / "execplan.txt"
        if count_128bit_lines(execplan_path) != args.expected_exec_lines:
            raise AuditError("final install execplan line count differs")

        return {
            "status": "passed",
            "selfcheck_round": 2,
            "entrypoint": "fresh_zip_extraction_independent_recomputation",
            "revision": revision,
            "zip": zip_path.as_posix(),
            "zip_sha256": zip_sha256,
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_file_count": len(actual_files),
            "overlay_manifest_record_count": len(expected_files),
            "hdl_file_count": 0,
            "runner_sha256": runner_hash,
            "bank_data_file_count": args.expected_banks,
            "exec_128bit_line_count": args.expected_exec_lines,
            "runtime_operator_count": args.expected_stages,
            "repeat_num": args.expected_repeat,
            "preload_transfer_count": len(transfers),
            "readback_region_count": len(expected_regions),
            "bitstream_binding_count": len(binding_records),
            "checks": [
                "safe fresh extraction and exact ZIP file set",
                "all extracted file hashes and sizes recomputed",
                "no symlink and no HDL source",
                "LF-only text contract",
                "README names the delivered ZIP SHA-256 sidecar",
                "runner self identity and identity/trap/command/cleanup ordering markers",
                "runner contract identities for static install, Make environment, runtime logs, and readback",
                "readable logical entrypoints plus DIR_HOME/vendor nonblocking provenance",
                "package-owned AXI 4-KiB transport contract",
                "distinct run1/run2 result archive policy",
                "waveform disabled and no-archive run argv",
                "SCA payload line counts and AXI 4-KiB burst safety",
                "SCA_D/readback exact binding",
                "JSON/official-encoder/final install bitstream binding",
            ],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--sidecar", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--expected-banks", type=int, default=28)
    parser.add_argument("--expected-exec-lines", type=int, default=314)
    parser.add_argument("--expected-stages", type=int, default=12)
    parser.add_argument("--expected-repeat", type=int, default=5)
    parser.add_argument("--expected-preloads", type=int, default=434)
    parser.add_argument("--expected-readbacks", type=int, default=168)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.report is not None and args.report.exists():
            raise FileExistsError(
                f"refusing to replace an existing round2 report: {args.report}"
            )
        report = audit(args)
    except (AuditError, OSError, ValueError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, indent=2))
        return 1
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
