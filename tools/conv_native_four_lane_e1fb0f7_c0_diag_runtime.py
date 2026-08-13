from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True

try:
    import node0004_assumed_hardware_server_runtime_v2_base as numeric_base
except ImportError:
    from tools import node0004_assumed_hardware_server_runtime_v2 as numeric_base


INSTALL_NAME = "r5_n4_e1f_p5_c0diag"
PASS_STATUS = "NATIVE4_C0_DIAGNOSTIC_NATURAL_COMPLETE"
PARTIAL_STATUS = "NATIVE4_C0_DIAGNOSTIC_PARTIAL_RETURN"
EXPECTED_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
EXPECTED_LEAVES = {
    "Array_Request_Manager.sv": (
        "d3f100b2a1415ff561791ccafd157b038c4d8e80a80bf18dcedb89c1fec7c4eb"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "b5fc30fa970a4ed38ebdfaf825946a80562ded91d72c600dd1ee89d14103b1ef"
    ),
    "RD_Data_Channel.sv": (
        "6c612cdd0eb907678a4825215553fd4a1b1b79869b1314fafba9b0e8c072f60e"
    ),
    "Neighbor_Out_AG.sv": (
        "05a6b1eadd2d5fb125a6a9e6b01b03dbbf9cd1bddc32423c01b5b6651cced41e"
    ),
    "SA_PE_Float_CSA.v": (
        "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3"
    ),
    "SA_PE_Float_Control.v": (
        "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb"
    ),
    "SA_PE_Mul_Array.v": (
        "135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a"
    ),
    "SA_ALU.v": (
        "c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06"
    ),
}
PARSING_RE = re.compile(r"Parsing design file ['\"]([^'\"]+)['\"]")
NATURAL_MARKER = "$finish at simulation time"
FEATURE_MARKER = (
    "N4D_FEATURE_ENABLE_V2 feature=NATIVE4_C0_BOUNDARY enabled=1 "
    "heartbeat_cycles=262144 stall_cycles=1048576 slice=0"
)
CANONICAL_MARKER = "N4D_CANONICAL_V1"


class RuntimeErrorContract(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeErrorContract(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _status(path: Path, fallback: int = 125) -> int:
    try:
        return int(path.read_text(encoding="ascii").strip())
    except (OSError, UnicodeError, ValueError):
        return fallback


def _signal(path: Path) -> str:
    try:
        return path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return "MISSING"


def _safe_child(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise RuntimeErrorContract(f"unsafe relative path: {relative}")
    target = (root / Path(*pure.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise RuntimeErrorContract(f"path escapes root: {relative}")
    return target


def preflight(package_root: Path) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = load_json(package / "package_manifest.json")
    expected = manifest.get("files")
    if not isinstance(expected, dict):
        raise RuntimeErrorContract("package exact-set is missing")
    observed = numeric_base.package_records(package)
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        changed = sorted(
            path
            for path in set(expected) & set(observed)
            if expected[path] != observed[path]
        )
        raise RuntimeErrorContract(
            "package exact-set differs: "
            f"missing={missing[:3]} extra={extra[:3]} changed={changed[:3]}"
        )
    if (
        manifest.get("install_name") != INSTALL_NAME
        or manifest.get("candidate_class")
        != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
        or manifest.get("candidate_release") is not False
        or manifest.get("conv_run_ids") != ["c0"]
        or manifest.get("tail_run_ids") != []
        or manifest.get("readback_checks") != []
        or manifest.get("formal_readback_count") != 0
        or manifest.get("expected_production_rtl_identity", {}).get("commit")
        != EXPECTED_COMMIT
        or manifest.get("expected_production_rtl_identity", {}).get("leaves")
        != EXPECTED_LEAVES
    ):
        raise RuntimeErrorContract("p5 diagnostic identity differs")
    budget = manifest.get("path_length_budget")
    if not isinstance(budget, dict):
        raise RuntimeErrorContract("package path budget is missing")
    relative_paths = sorted(observed)
    max_suffix = max(map(len, relative_paths))
    max_depth = max(
        len(PurePosixPath(relative).parts) for relative in relative_paths
    )
    max_zip_member = max(
        len(f"{INSTALL_NAME}/{relative}") for relative in relative_paths
    )
    if (
        max_suffix > budget.get("max_inner_suffix_chars", -1)
        or max_depth > budget.get("max_inner_depth", -1)
        or max_zip_member > budget.get("max_zip_member_chars", -1)
        or any(
            INSTALL_NAME in PurePosixPath(relative).parts
            for relative in relative_paths
        )
    ):
        raise RuntimeErrorContract("package internal path budget differs")
    runtime_root = package / "workload/runtime"
    run_ids = [
        path.name
        for path in (runtime_root / "runs").iterdir()
        if path.is_dir()
    ]
    if run_ids != ["c0"]:
        raise RuntimeErrorContract("diagnostic run tree differs")
    marker = f"install/cfg_pkg/{INSTALL_NAME}/"
    for name, allow_missing in (
        ("sca_cfg.json", False),
        ("sca_cfg_D.json", True),
    ):
        value = load_json(runtime_root / f"runs/c0/{name}")
        for record in value.values():
            if not isinstance(record, dict) or "path" not in record:
                continue
            consumer = record["path"]
            if not isinstance(consumer, str) or not consumer.startswith(marker):
                raise RuntimeErrorContract(
                    f"{name} consumer identity differs"
                )
            target = _safe_child(runtime_root, consumer[len(marker) :])
            if allow_missing:
                if target.exists():
                    raise RuntimeErrorContract(
                        "diagnostic D target is preseeded"
                    )
            elif not target.is_file():
                raise RuntimeErrorContract(
                    f"{name} direct consumer is missing"
                )
    return {
        "schema": "conv-native-four-lane-e1fb0f7-c0diag-preflight-v1",
        "valid": True,
        "file_count": len(observed),
        "run_ids": ["c0"],
        "formal_readback_count": 0,
        "candidate_release": False,
        "path_budget_valid": True,
        "consumer_closure_valid": True,
    }


def verify_install(package_root: Path, cfg_root: Path) -> dict[str, Any]:
    expected = numeric_base.package_records(
        package_root / "workload/runtime", exclude_manifest=False
    )
    observed = numeric_base.package_records(
        cfg_root, exclude_manifest=False
    )
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        changed = sorted(
            path
            for path in set(expected) & set(observed)
            if expected[path] != observed[path]
        )
        raise RuntimeErrorContract(
            "installed exact-set differs: "
            f"missing={missing[:3]} extra={extra[:3]} changed={changed[:3]}"
        )
    if any(path.name.startswith("matrix_D_") for path in cfg_root.rglob("*")):
        raise RuntimeErrorContract("diagnostic runtime must not preload D")
    return {
        "schema": "conv-native-four-lane-e1fb0f7-c0diag-install-v1",
        "valid": True,
        "file_count": len(observed),
        "preloaded_D_count": 0,
    }


def path_budget(package_root: Path, server_root: Path) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    budget = manifest.get("path_length_budget", {})
    relative_chars = budget.get("max_projected_relative_path_chars")
    limit = budget.get("max_projected_absolute_path_limit_chars")
    longest = budget.get("longest_projected_relative_path")
    if (
        not isinstance(relative_chars, int)
        or not isinstance(limit, int)
        or not isinstance(longest, str)
        or len(longest) != relative_chars
    ):
        raise RuntimeErrorContract("path budget is malformed")
    server = server_root.resolve()
    projected = len(str(server)) + 1 + relative_chars
    receipt = {
        "schema": "conv-native-four-lane-e1fb0f7-c0diag-path-budget-v1",
        "valid": projected <= limit,
        "server_root": str(server),
        "server_root_chars": len(str(server)),
        "max_projected_relative_path_chars": relative_chars,
        "max_projected_absolute_path_chars": projected,
        "max_projected_absolute_path_limit_chars": limit,
        "longest_projected_relative_path": longest,
        "required_shortening_chars": max(0, projected - limit),
    }
    if not receipt["valid"]:
        raise RuntimeErrorContract(
            f"server root exceeds path budget: {projected}>{limit}"
        )
    return receipt


def collect_compile_identity(
    compile_log: Path, output: Path
) -> dict[str, Any]:
    text = compile_log.read_text(encoding="utf-8", errors="replace")
    parsed = [Path(match.group(1)) for match in PARSING_RE.finditer(text)]
    leaves: dict[str, Any] = {}
    errors: list[str] = []
    for basename, expected in EXPECTED_LEAVES.items():
        matches = sorted(
            {str(path) for path in parsed if path.name == basename}
        )
        if len(matches) != 1:
            errors.append(
                f"{basename}: expected one compiled path, found {len(matches)}"
            )
            continue
        path = Path(matches[0])
        if not path.is_file():
            errors.append(f"{basename}: compiled path is unreadable")
            continue
        observed = sha256(path)
        leaves[basename] = {
            "compiled_path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": observed,
            "expected_sha256": expected,
            "match": observed == expected,
        }
        if observed != expected:
            errors.append(f"{basename}: production source SHA differs")
    receipt = {
        "schema": (
            "conv-native-four-lane-e1fb0f7-c0diag-production-identity-v1"
        ),
        "valid": not errors,
        "errors": errors,
        "compile_log": str(compile_log),
        "compile_log_sha256": sha256(compile_log),
        "expected_commit": EXPECTED_COMMIT,
        "expected_byte_identity": (
            "immutable Git blob/raw Linux checkout bytes"
        ),
        "identity_source": (
            "actual VCS parsing receipts followed by post-compile leaf hashing"
        ),
        "precompile_server_source_preflight": False,
        "leaves": leaves,
    }
    write_json(output, receipt)
    if errors:
        raise RuntimeErrorContract("; ".join(errors))
    return receipt


def qualify_run(
    sim_log: Path, observer_log: Path, output: Path
) -> dict[str, Any]:
    sim_text = sim_log.read_text(encoding="utf-8", errors="replace")
    observer_text = observer_log.read_text(
        encoding="utf-8", errors="replace"
    )
    natural_count = sim_text.count(NATURAL_MARKER)
    feature_sim_count = sim_text.count(FEATURE_MARKER)
    feature_log_count = observer_text.count(FEATURE_MARKER)
    canonical = [
        line
        for line in observer_text.splitlines()
        if line.startswith(CANONICAL_MARKER)
    ]
    slice_finish_count = sum(
        "decision=SLICE_FINISH" in line for line in canonical
    )
    valid = (
        natural_count == 1
        and feature_sim_count == 1
        and feature_log_count == 1
        and len(canonical) == 1
        and slice_finish_count == 1
        and all(
            token in canonical[0]
            for token in (
                "schema=n4d-canonical-v1",
                "reason=qualified_slice_finish",
                "boundary=c0_exec_to_slice_finish",
                "sample_start=",
                "sample_end=",
                "delta=",
                "total=",
            )
        )
    )
    receipt = {
        "schema": (
            "conv-native-four-lane-e1fb0f7-c0diag-natural-terminal-v1"
        ),
        "valid": valid,
        "natural_terminal_count": natural_count,
        "feature_sim_count": feature_sim_count,
        "feature_log_count": feature_log_count,
        "canonical_record_count": len(canonical),
        "slice_finish_count": slice_finish_count,
        "last_canonical": canonical[-1] if canonical else None,
        "sim_log_sha256": sha256(sim_log),
        "observer_log_sha256": sha256(observer_log),
    }
    write_json(output, receipt)
    if not valid:
        raise RuntimeErrorContract("c0 natural diagnostic receipt differs")
    return receipt


def feature_binding(
    sim_log: Path, observer_log: Path, output: Path
) -> dict[str, Any]:
    sim_text = sim_log.read_text(encoding="utf-8", errors="replace")
    observer_text = observer_log.read_text(
        encoding="utf-8", errors="replace"
    )
    sim_count = sim_text.count(FEATURE_MARKER)
    observer_count = observer_text.count(FEATURE_MARKER)
    valid = sim_count == 1 and observer_count == 1
    receipt = {
        "schema": (
            "conv-native-four-lane-e1fb0f7-c0diag-feature-binding-v1"
        ),
        "valid": valid,
        "feature": "NATIVE4_C0_BOUNDARY",
        "runtime_enable": "+N4D_C0_BOUNDARY_DIAG",
        "heartbeat_cycles": 262_144,
        "stall_cycles": 1_048_576,
        "slice": 0,
        "expected_marker": FEATURE_MARKER,
        "sim_marker_count": sim_count,
        "observer_marker_count": observer_count,
        "sim_log_sha256": sha256(sim_log),
        "observer_log_sha256": sha256(observer_log),
    }
    write_json(output, receipt)
    if not valid:
        raise RuntimeErrorContract("c0 feature binding receipt differs")
    return receipt


def analyze(
    package_root: Path, evidence_root: Path, run_root: Path
) -> dict[str, Any]:
    compile_status = _status(evidence_root / "compile_exit_status.txt")
    run_status = _status(evidence_root / "run_exit_status.txt")
    signal_status = _signal(evidence_root / "signal_status.txt")
    identity_path = evidence_root / "production_rtl_identity.json"
    identity = (
        load_json(identity_path)
        if identity_path.is_file()
        else {"valid": False, "missing": True}
    )
    terminal_path = evidence_root / "natural_terminal/c0.json"
    terminal = (
        load_json(terminal_path)
        if terminal_path.is_file()
        else {"valid": False, "missing": True}
    )
    feature_path = evidence_root / "feature_binding/c0.json"
    feature = (
        load_json(feature_path)
        if feature_path.is_file()
        else {"valid": False, "missing": True}
    )
    observer_path = run_root / "c0/return_observer.log"
    canonical: list[str] = []
    if observer_path.is_file():
        canonical = [
            line
            for line in observer_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if line.startswith(CANONICAL_MARKER)
        ]
    natural_complete = (
        compile_status == 0
        and run_status == 0
        and signal_status == "NONE"
        and identity.get("valid") is True
        and feature.get("valid") is True
        and terminal.get("valid") is True
    )
    result = {
        "schema": (
            "conv-native-four-lane-e1fb0f7-c0diag-server-result-v1"
        ),
        "status": PASS_STATUS if natural_complete else PARTIAL_STATUS,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "execution_gate": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "compile_succeeded": compile_status == 0,
            "actual_compile_identity_match": identity.get("valid") is True,
            "feature_binding_match": feature.get("valid") is True,
            "c0_natural_terminal": terminal.get("valid") is True,
            "diagnostic_natural_complete": natural_complete,
            "formal_D_claimed": False,
            "E3_claimed": False,
            "E4_claimed": False,
            "E5_claimed": False,
        },
        "production_rtl_identity": identity,
        "feature_binding_receipt": feature,
        "natural_terminal_receipt": terminal,
        "canonical_record_count": len(canonical),
        "last_canonical": canonical[-1] if canonical else None,
        "package_manifest_sha256": sha256(
            package_root / "package_manifest.json"
        ),
    }
    write_json(evidence_root / "SERVER_RESULT_GATE.json", result)
    return result


def _copy_if_present(
    source: Path,
    return_dir: Path,
    relative: str,
    records: list[dict[str, Any]],
    *,
    required: bool,
    max_bytes: int,
    source_root_name: str,
    source_relative: str,
    missing_semantics: str,
) -> None:
    if not source.is_file():
        if required:
            raise RuntimeErrorContract(f"required return file missing: {source}")
        return
    if source.stat().st_size > max_bytes:
        raise RuntimeErrorContract(f"return file exceeds budget: {source}")
    target = _safe_child(return_dir, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    records.append(
        {
            "path": relative,
            "source_root": source_root_name,
            "source_path": source_relative,
            "size_bytes": target.stat().st_size,
            "sha256": sha256(target),
            "required": required,
            "max_bytes": max_bytes,
            "missing_semantics": missing_semantics,
        }
    )


def _pack_return(return_dir: Path, return_zip: Path) -> None:
    with zipfile.ZipFile(
        return_zip, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(
            item for item in return_dir.rglob("*") if item.is_file()
        ):
            relative = (
                f"{return_dir.name}/"
                f"{path.relative_to(return_dir).as_posix()}"
            )
            info = zipfile.ZipInfo(relative, (2026, 8, 5, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def collect(
    server_root: Path,
    evidence_root: Path,
    run_root: Path,
    package_root: Path,
) -> dict[str, Any]:
    return_dir = server_root / f"{INSTALL_NAME}_return"
    return_zip = return_dir.with_suffix(".zip")
    return_sidecar = Path(str(return_zip) + ".sha256")
    return_dir.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    manifest = load_json(package_root / "package_manifest.json")
    declarations = manifest.get("return_allowlist")
    if not isinstance(declarations, list) or not declarations:
        raise RuntimeErrorContract("manifest return allowlist is missing")
    roots = {
        "evidence": evidence_root,
        "run": run_root,
        "package": package_root,
    }
    for declaration in declarations:
        if not isinstance(declaration, dict):
            raise RuntimeErrorContract("return allowlist entry is malformed")
        source_root_name = declaration.get("source_root")
        source_relative = declaration.get("source_path")
        target_relative = declaration.get("target_path")
        required = declaration.get("required")
        maximum = declaration.get("max_bytes")
        missing_semantics = declaration.get("missing_semantics")
        if (
            source_root_name not in roots
            or not isinstance(source_relative, str)
            or not isinstance(target_relative, str)
            or not isinstance(required, bool)
            or not isinstance(maximum, int)
            or maximum <= 0
            or not isinstance(missing_semantics, str)
            or not missing_semantics
        ):
            raise RuntimeErrorContract(
                "return allowlist entry contract differs"
            )
        _copy_if_present(
            _safe_child(roots[source_root_name], source_relative),
            return_dir,
            target_relative,
            records,
            required=required,
            max_bytes=maximum,
            source_root_name=source_root_name,
            source_relative=source_relative,
            missing_semantics=missing_semantics,
        )
    result = load_json(evidence_root / "SERVER_RESULT_GATE.json")
    return_manifest = {
        "schema": (
            "conv-native-four-lane-e1fb0f7-c0diag-return-manifest-v1"
        ),
        "install_name": INSTALL_NAME,
        "source_package_manifest_sha256": sha256(
            package_root / "package_manifest.json"
        ),
        "server_result_status": result.get("status"),
        "records_excluding_this_manifest": sorted(
            records, key=lambda item: str(item["path"])
        ),
        "return_exact_set_policy": (
            "records plus RETURN_MANIFEST.json and RETURN_ALLOWLIST.json only"
        ),
        "declared_allowlist": declarations,
    }
    manifest_path = return_dir / "RETURN_MANIFEST.json"
    write_json(manifest_path, return_manifest)
    records.append(
        {
            "path": "RETURN_MANIFEST.json",
            "size_bytes": manifest_path.stat().st_size,
            "sha256": sha256(manifest_path),
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
        }
    )
    write_json(
        return_dir / "RETURN_ALLOWLIST.json",
        {
            "schema": (
                "conv-native-four-lane-e1fb0f7-c0diag-allowlist-v1"
            ),
            "install_name": INSTALL_NAME,
            "declared_allowlist": declarations,
            "records": sorted(records, key=lambda item: str(item["path"])),
        },
    )
    unpacked_bytes = sum(
        path.stat().st_size
        for path in return_dir.rglob("*")
        if path.is_file()
    )
    maximum_unpacked = int(
        manifest.get("return_budget", {}).get(
            "uncompressed_max_bytes", 0
        )
    )
    if maximum_unpacked <= 0 or unpacked_bytes > maximum_unpacked:
        raise RuntimeErrorContract("return uncompressed budget exceeded")
    _pack_return(return_dir, return_zip)
    maximum_zip = int(
        manifest.get("return_budget", {}).get("zip_max_bytes", 0)
    )
    if maximum_zip <= 0 or return_zip.stat().st_size > maximum_zip:
        raise RuntimeErrorContract("return ZIP budget exceeded")
    with zipfile.ZipFile(return_zip) as archive:
        bad = archive.testzip()
        names = [info.filename for info in archive.infolist()]
        expected_names = sorted(
            f"{return_dir.name}/{path.relative_to(return_dir).as_posix()}"
            for path in return_dir.rglob("*")
            if path.is_file()
        )
        if (
            bad is not None
            or sorted(names) != expected_names
            or len(names) != len(set(names))
        ):
            raise RuntimeErrorContract("return ZIP exact-set differs")
    return_sha = sha256(return_zip)
    return_sidecar.write_text(
        f"{return_sha}  {return_zip.name}\n", encoding="ascii", newline="\n"
    )
    return {
        "schema": (
            "conv-native-four-lane-e1fb0f7-c0diag-collection-v1"
        ),
        "return_zip": str(return_zip),
        "return_zip_bytes": return_zip.stat().st_size,
        "return_zip_sha256": return_sha,
        "sidecar": str(return_sidecar),
        "record_count": len(records) + 1,
        "uncompressed_bytes": unpacked_bytes,
        "return_zip_max_bytes": maximum_zip,
        "uncompressed_max_bytes": maximum_unpacked,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-root", type=Path, required=True)
    ins = sub.add_parser("verify-install")
    ins.add_argument("--package-root", type=Path, required=True)
    ins.add_argument("--cfg-root", type=Path, required=True)
    path = sub.add_parser("path-budget")
    path.add_argument("--package-root", type=Path, required=True)
    path.add_argument("--server-root", type=Path, required=True)
    comp = sub.add_parser("compile-identity")
    comp.add_argument("--compile-log", type=Path, required=True)
    comp.add_argument("--output", type=Path, required=True)
    qual = sub.add_parser("qualify-run")
    qual.add_argument("--sim-log", type=Path, required=True)
    qual.add_argument("--observer-log", type=Path, required=True)
    qual.add_argument("--output", type=Path, required=True)
    feat = sub.add_parser("feature-binding")
    feat.add_argument("--sim-log", type=Path, required=True)
    feat.add_argument("--observer-log", type=Path, required=True)
    feat.add_argument("--output", type=Path, required=True)
    ana = sub.add_parser("analyze")
    ana.add_argument("--package-root", type=Path, required=True)
    ana.add_argument("--evidence-root", type=Path, required=True)
    ana.add_argument("--run-root", type=Path, required=True)
    col = sub.add_parser("collect")
    col.add_argument("--server-root", type=Path, required=True)
    col.add_argument("--evidence-root", type=Path, required=True)
    col.add_argument("--run-root", type=Path, required=True)
    col.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        value = preflight(args.package_root)
    elif args.command == "verify-install":
        value = verify_install(args.package_root, args.cfg_root)
    elif args.command == "path-budget":
        value = path_budget(args.package_root, args.server_root)
    elif args.command == "compile-identity":
        value = collect_compile_identity(args.compile_log, args.output)
    elif args.command == "qualify-run":
        value = qualify_run(
            args.sim_log, args.observer_log, args.output
        )
    elif args.command == "feature-binding":
        value = feature_binding(
            args.sim_log, args.observer_log, args.output
        )
    elif args.command == "analyze":
        value = analyze(
            args.package_root, args.evidence_root, args.run_root
        )
    else:
        value = collect(
            args.server_root,
            args.evidence_root,
            args.run_root,
            args.package_root,
        )
    print(json.dumps(value, ensure_ascii=False))
    if args.command == "analyze" and value.get("status") not in {
        PASS_STATUS,
        PARTIAL_STATUS,
    }:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
