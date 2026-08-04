from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (  # noqa: E402
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import (  # noqa: E402
    file_records,
)
from tools.validate_gap_node0071_canonical_package import (  # noqa: E402
    validate as validate_canonical,
)
from tools.validate_gap_node0071_observer_binding import (  # noqa: E402
    validate_with_negative_controls as validate_observer,
)


INSTALL_NAME = "r5_n71_gap_v6_canonical"
SOURCE_NAME = "r5_n71_gap_v5_obsbind"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v5_obsbind.zip"
)
SOURCE_SHA256 = (
    "159bebac586be3a40ae937736b0368593ced34c7b8128fde7858930b53ebef8d"
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
CANONICAL_TOOL = ROOT / "tools/gap_node0071_canonical_decision.py"
SERVER_RULE_SHA256 = (
    "ed3990f13c62ce67e5081458b0dfdcf6ca257908fe138fcc05a7000482afd2f8"
)
PLAN_SHA256 = (
    "21dec7853cf9dc1610e51ede1366550b390bfc301d8dc8d5bf6c560d5ecae545"
)
QUALIFIED_COUNTERS = [
    "gexec_fire",
    "request_handshake",
    "read_data_handshake",
    "write_data_handshake",
    "mse4_request_handshake_ch0",
    "mse4_request_handshake_ch1",
    "mse4_write_data_handshake_ch0",
    "mse4_write_data_handshake_ch1",
]


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    prefix = f"{SOURCE_NAME}/"
    result: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or info.filename in seen
            or (mode and stat.S_ISLNK(mode))
            or not info.filename.startswith(prefix)
        ):
            raise BuildError(f"unsafe source member: {info.filename}")
        seen.add(info.filename)
        if not info.is_dir():
            result.append(info)
    return result


def extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("frozen v5 ZIP differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("frozen v5 CRC differs")
        for info in safe_entries(archive):
            relative = PurePosixPath(info.filename).relative_to(SOURCE_NAME)
            target = package.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return package


def replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_identity(item) for key, item in value.items()}
    return value


def numeric_records(package: Path) -> dict[str, Any]:
    records = file_records(
        package / "workload", exclude_manifest=False
    )
    records.pop("sca_cfg.json")
    records.pop("sca_cfg_D.json")
    return records


def patch_runtime(package: Path) -> None:
    path = (
        package
        / "package_tools/gap_node0071_complete_server_runtime.py"
    )
    text = path.read_text(encoding="utf-8")
    if text.count("len(allowlist) != 68") != 1:
        raise BuildError("runtime allowlist anchor differs")
    path.write_text(
        text.replace("len(allowlist) != 68", "len(allowlist) != 70"),
        encoding="utf-8",
        newline="\n",
    )


def rebind_sca(package: Path) -> None:
    for relative in ("workload/sca_cfg.json", "workload/sca_cfg_D.json"):
        path = package / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        replaced = replace_identity(value)
        if replaced == value:
            raise BuildError(f"identity absent: {relative}")
        write_json(path, replaced)


def progress_contract() -> dict[str, Any]:
    return {
        "schema": "gap-node0071-progress-localization-v2",
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "enabled_by_default": True,
        "read_only": True,
        "target_slice": 0,
        "heartbeat_cycles": 262144,
        "stall_window_cycles": 1048576,
        "host_sample_period_seconds": 60,
        "minimum_monotonic_windows_for_progress": 2,
        "monotonic_counters": QUALIFIED_COUNTERS,
        "counter_qualification": {
            "gexec_fire": "gexec2slice_fire qualified dispatch",
            "request_handshake": "local_req_hs",
            "read_data_handshake": "local_rdata_hs",
            "write_data_handshake": "local_wdata_hs",
            "mse4_request_handshake_ch0":
                "slice0 MSE4 channel0 local_req_hs",
            "mse4_request_handshake_ch1":
                "slice0 MSE4 channel1 local_req_hs",
            "mse4_write_data_handshake_ch0":
                "slice0 MSE4 channel0 local_wdata_hs",
            "mse4_write_data_handshake_ch1":
                "slice0 MSE4 channel1 local_wdata_hs",
        },
        "raw_state_excluded_from_progress": [
            "ready",
            "enable",
            "valid_without_handshake",
            "buffer_occupancy",
            "buf4_wr",
            "buf4_rd",
            "buf5_wr",
            "buf5_rd",
            "sg_ga_input",
            "sg_ga_output",
            "deep_level_samples",
        ],
        "canonical_decision": {
            "schema":
                "gap-node0071-canonical-diagnostic-decision-v1",
            "version": 1,
            "unique_record": True,
            "required_fields": [
                "schema",
                "version",
                "decision",
                "reason",
                "boundary",
                "sample_range",
                "window_range",
                "qualified_counter_snapshot",
                "content_digest",
            ],
            "summary_only_prefix_forbidden": True,
            "conflict_policy":
                "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS",
        },
    }


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8").replace(
        SOURCE_NAME, INSTALL_NAME
    )
    variable_anchor = (
        'observer_guard="$package_root/package_tools/'
        'gap_node0071_package_observer_guard.py"\n'
    )
    if text.count(variable_anchor) != 1:
        raise BuildError("canonical tool variable anchor differs")
    text = text.replace(
        variable_anchor,
        variable_anchor
        + 'canonical_tool="$package_root/package_tools/'
        'gap_node0071_canonical_decision.py"\n',
    )
    guard_end = (
        '  >"$evidence_root/observer_precompile.json" || exit 7\n'
    )
    if text.count(guard_end) != 1:
        raise BuildError("canonical self-test anchor differs")
    text = text.replace(
        guard_end,
        guard_end
        + 'python3 "$canonical_tool" self-test '
        '>"$evidence_root/canonical_decision_self_test.json" || exit 8\n',
    )
    analyze_anchor = (
        '  python3 "$runtime" analyze --package-root "$package_root"'
    )
    if text.count(analyze_anchor) != 1:
        raise BuildError("canonical observe anchor differs")
    observe = (
        '  python3 "$canonical_tool" observe \\\n'
        '    --observer-log "$observer_log" \\\n'
        '    --sim-log "$run_root/sim_results/sim.log" \\\n'
        '    --signal "$signal_name" \\\n'
        '    --simulation-status "$simulation_status" \\\n'
        '    --stall-window-cycles 1048576 \\\n'
        '    --heartbeat-cycles 262144 \\\n'
        '    --output "$evidence_root/canonical_decision.json" >/dev/null\n'
        '  canonical_status=$?\n'
        '  [ "$canonical_status" -eq 0 ] || '
        'printf \'canonical_decision_status=%s\\n\' "$canonical_status" '
        '>>"$evidence_root/signal_status.txt"\n'
    )
    text = text.replace(analyze_anchor, observe + analyze_anchor)
    required = (
        'canonical_tool="$package_root/package_tools/'
        'gap_node0071_canonical_decision.py"',
        '"$canonical_tool" self-test',
        '"$canonical_tool" observe',
        "--stall-window-cycles 1048576",
        "--heartbeat-cycles 262144",
        "canonical_decision.json",
        "canonical_decision_self_test.json",
        "trap 'signal_name=INT",
    )
    if not all(term in text for term in required):
        raise BuildError("canonical runner terms differ")
    path.write_text(text, encoding="utf-8", newline="\n")


def allowlist_entry(
    source_path: str, target_path: str, missing: str
) -> dict[str, Any]:
    return {
        "source_root": "evidence",
        "source_path": source_path,
        "target_path": target_path,
        "required": True,
        "max_bytes": 1 << 20,
        "missing_meaning": missing,
    }


def preflight(package: Path) -> dict[str, Any]:
    process = subprocess.run(
        [
            sys.executable,
            str(
                package
                / "package_tools/gap_node0071_complete_server_runtime.py"
            ),
            "preflight",
            "--package-root",
            str(package),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        raise BuildError(
            f"preflight failed: {process.stdout} {process.stderr}"
        )
    result = json.loads(process.stdout)
    if result.get("valid") is not True:
        raise BuildError("preflight receipt differs")
    return result


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = extract_source(destination)
    before = numeric_records(package)
    rebind_sca(package)
    patch_runtime(package)
    shutil.copyfile(
        CANONICAL_TOOL,
        package
        / "package_tools/gap_node0071_canonical_decision.py",
    )
    write_json(
        package / "diagnostics/progress_contract.json",
        progress_contract(),
    )
    patch_runner(package)
    (package / "README.md").write_text(
        "# GAP node0071 v6 canonical progress decision\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It reuses "
        "the frozen v5 workload and changes only diagnostic evidence: "
        "qualified-event-only monotonic counters plus one complete canonical "
        "decision record. Run once with:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = replace_identity(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    allowlist = manifest.get("return_allowlist")
    if not isinstance(allowlist, list) or len(allowlist) != 68:
        raise BuildError("source allowlist differs")
    allowlist.extend(
        [
            allowlist_entry(
                "canonical_decision.json",
                "evidence/canonical_decision.json",
                "unique complete canonical progress decision unavailable",
            ),
            allowlist_entry(
                "canonical_decision_self_test.json",
                "evidence/canonical_decision_self_test.json",
                "canonical decision negative-control receipt unavailable",
            ),
        ]
    )
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v6",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "diagnostic decision canonicalization only; frozen GAP "
                "sum/tail/golden/config/workload unchanged; no functional "
                "fix and no E3/E4/E5"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "source_numeric_payload_reused_without_rebuild": True,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
            "canonical_decision_contract": {
                "rule_id":
                    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
                "schema":
                    "gap-node0071-canonical-diagnostic-decision-v1",
                "version": 1,
                "unique_complete_record": True,
                "qualified_counters": QUALIFIED_COUNTERS,
                "raw_level_excluded": True,
                "required_fields": [
                    "schema",
                    "version",
                    "decision",
                    "reason",
                    "boundary",
                    "sample_range",
                    "window_range",
                    "qualified_counter_snapshot",
                    "content_digest",
                ],
                "ambiguous_status":
                    "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS",
                "negative_controls": [
                    "continuous_high_level",
                    "summary_only_append_with_canonical_prefix",
                    "conflicting_double_decision",
                    "missing_reason",
                    "missing_boundary",
                ],
            },
            "default_progress_diagnostics": {
                "rule_id": "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
                "enabled_by_default": True,
                "read_only": True,
                "low_overhead": True,
                "rate_limited": True,
                "partial_return": True,
                "actual_compile_argv": True,
                "actual_simulator_argv": True,
                "time0_enable_receipt": True,
                "qualified_progress": True,
                "host_wall_clock": True,
                "simulation_time": True,
                "stall_window": 1048576,
                "signal_trap_collection": True,
                "canonical_decision": True,
                "return_allowlist": True,
                "changes_dut_input_or_backpressure": False,
            },
            "rule_receipts": {
                "server_rule_sha256": SERVER_RULE_SHA256,
                "plan_sha256_mutable_provenance_only": PLAN_SHA256,
            },
        }
    )
    provenance = manifest.get("generation_provenance")
    if not isinstance(provenance, dict):
        raise BuildError("generation provenance differs")
    provenance.update(
        {
            "tool": "tools/build_gap_node0071_v6_canonical_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change":
                "qualified-only canonical progress decision",
        }
    )
    manifest["progress_localization"] = progress_contract()
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    checked = preflight(package)
    after = numeric_records(package)
    if before != after:
        raise BuildError("frozen numeric workload drifted")
    self_test = subprocess.run(
        [
            sys.executable,
            str(
                package
                / "package_tools/gap_node0071_canonical_decision.py"
            ),
            "self-test",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if (
        self_test.returncode != 0
        or json.loads(self_test.stdout).get("status") != "PASS"
    ):
        raise BuildError("package canonical self-test differs")
    return package, {
        "numeric_workload_tree_equal": True,
        "numeric_workload_file_count": len(after),
        "package_preflight": checked,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v6-repeat-"
    ) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
        if (
            first_sha != sha256(repeated_zip)
            or first_tree
            != file_records(repeated, exclude_manifest=False)
        ):
            raise BuildError("repeat build differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def fresh_preflight(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v6-fresh-"
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        package = root / INSTALL_NAME
        before = file_records(package, exclude_manifest=False)
        checked = preflight(package)
        after = file_records(package, exclude_manifest=False)
        if before != after:
            raise BuildError("fresh preflight mutated package")
    return {"tree_unchanged": True, "preflight": checked}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    canonical_path = (
        output_root / f"{INSTALL_NAME}.canonical_validation.json"
    )
    observer_path = (
        output_root / f"{INSTALL_NAME}.observer_binding_validation.json"
    )
    for path in (
        package_path,
        zip_path,
        sidecar,
        validation_path,
        canonical_path,
        observer_path,
    ):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        fresh = fresh_preflight(zip_path)
        canonical = validate_canonical(zip_path)
        observer = validate_observer(zip_path)
        write_json(canonical_path, canonical)
        write_json(observer_path, observer)
        validation = {
            "schema":
                "gap-node0071-canonical-diagnostic-package-validation-v6",
            "status":
                "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "source_v5_quarantined": True,
            "numeric_workload_tree_equal":
                proof["numeric_workload_tree_equal"],
            "numeric_workload_file_count":
                proof["numeric_workload_file_count"],
            "package_preflight": proof["package_preflight"],
            "canonical_decision_validation": canonical,
            "observer_four_way_validation": observer,
            "functional_fix": False,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "server_action": False,
            "repeated_build": repeated,
            "fresh_extract_preflight": fresh,
        }
        write_json(validation_path, validation)
    except Exception as error:
        print(f"GAP v6 canonical build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
