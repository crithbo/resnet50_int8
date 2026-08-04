from __future__ import annotations

import hashlib
import json
import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_bind_v6"
ZIP_PATH = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{INSTALL_NAME}.zip"
)
SIDECAR_PATH = ZIP_PATH.with_suffix(".zip.sha256")
ZIP_SHA256 = (
    "9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = (
    "4c960c5cee73355d08f17d9d1a17edb2931b6a0336ae3831372b41f6af4dc8dc"
)
OBSERVER_REL = "tb_probe/native_return_observer.svh"
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-progress-bind-v6-four-way"
    / "report.json"
)
RUNTIME_RETURN_TARGETS = {
    "evidence/progress_contract.json",
    "evidence/actual_compile_argv.txt",
    "evidence/actual_simulator_argv.txt",
    "evidence/host_timing.txt",
    "evidence/signal_status.txt",
    "evidence/progress_samples.log",
    "evidence/observer_binding.txt",
    "runs/return_observer.log",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_final_zip() -> tuple[dict[str, bytes], dict[str, object]]:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            raise ValueError("final ZIP CRC failed")
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("final ZIP contains duplicate members")
        for info in infos:
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                raise ValueError(f"unsafe final ZIP member: {info.filename}")
        members = {info.filename: archive.read(info) for info in infos}
    root = f"{INSTALL_NAME}/"
    manifest_name = root + "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(members[manifest_name])
    return members, manifest


def _replace_runner(
    members: dict[str, bytes],
    manifest: dict[str, object],
    transform: Callable[[str], str],
) -> None:
    name = f"{INSTALL_NAME}/PREPARE_AND_RUN.sh"
    updated = transform(members[name].decode("utf-8")).encode("utf-8")
    members[name] = updated
    manifest["files"]["PREPARE_AND_RUN.sh"] = {
        "sha256": sha256_bytes(updated),
        "size_bytes": len(updated),
    }
    members[f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _inspect(
    members: dict[str, bytes],
    manifest: dict[str, object],
    *,
    require_fresh_extract: bool,
) -> dict[str, object]:
    root = f"{INSTALL_NAME}/"
    runner_name = root + "PREPARE_AND_RUN.sh"
    observer_name = root + OBSERVER_REL
    runner = members.get(runner_name, b"").decode("utf-8", errors="replace")
    observer = members.get(observer_name, b"")
    observer_text = observer.decode("utf-8", errors="replace")
    files = manifest.get("files", {})
    binding = manifest.get("observer_binding_fix", {})

    observer_members = [
        name
        for name in members
        if name.endswith("/native_return_observer.svh")
    ]
    file_record = files.get(OBSERVER_REL)
    source_record_exact = (
        isinstance(file_record, dict)
        and file_record.get("sha256") == OBSERVER_SHA256
        and file_record.get("size_bytes") == len(observer)
    )
    source_binding_exact = (
        binding.get("source_path") == OBSERVER_REL
        and binding.get("sha256") == OBSERVER_SHA256
        and binding.get("installation_mode") == "PACKAGE_LOCAL_INCLUDE_ONLY"
    )
    source_ok = (
        observer_name in members
        and len(observer_members) == 1
        and sha256_bytes(observer) == OBSERVER_SHA256
        and source_record_exact
        and source_binding_exact
    )

    fresh_extract_readable = False
    if source_ok and require_fresh_extract:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            for name, payload in members.items():
                path = destination / PurePosixPath(name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            extracted = destination / observer_name
            fresh_extract_readable = (
                extracted.is_file()
                and extracted.read_bytes() == observer
                and sha256_file(extracted) == OBSERVER_SHA256
            )
    elif source_ok:
        fresh_extract_readable = True
    source_ok = source_ok and fresh_extract_readable

    incdir_literal = "+incdir+$package_root/tb_probe"
    include_occurrences = runner.count(incdir_literal)
    normalized_include = PurePosixPath("tb_probe")
    include_stays_in_package = (
        not normalized_include.is_absolute()
        and ".." not in normalized_include.parts
        and normalized_include.as_posix()
        == PurePosixPath(OBSERVER_REL).parent.as_posix()
    )
    include_ok = (
        include_occurrences >= 2
        and include_stays_in_package
        and binding.get("compile_include_directory") == "$package_root/tb_probe"
    )

    macro_literal = "+define+NATIVE_RETURN_OBSERVER_ENABLE"
    macro_occurrences = runner.count(macro_literal)
    compile_enable_ok = (
        macro_occurrences >= 2
        and binding.get("compile_enable_macro")
        == "NATIVE_RETURN_OBSERVER_ENABLE"
        and '$test$plusargs("RETURN_OBSERVER")' in observer_text
    )

    allowlist = manifest.get("return_allowlist", [])
    required_targets = {
        str(record.get("target_path"))
        for record in allowlist
        if record.get("required") is True
    }
    marker = "# Native NDP return observer v4"
    marker_position = observer_text.find(marker)
    initial_position = observer_text.rfind("initial begin", 0, marker_position)
    following_always = observer_text.find("always @(", marker_position)
    time0_marker_emitted = (
        marker_position >= 0
        and initial_position >= 0
        and following_always > marker_position
        and "return_obs_enabled = $test$plusargs(\"RETURN_OBSERVER\")"
        in observer_text[initial_position:marker_position]
    )
    runtime_plusarg_bound = (
        re.search(r"sim_args=\(.*?\+RETURN_OBSERVER.*?\)", runner, re.DOTALL)
        is not None
    )
    enabled_receipt_bound = (
        "grep -q 'Native NDP return observer' \"$observer_log\"" in runner
        and "observer_enabled_and_returned=true" in runner
    )
    actual_argv_bound = (
        "actual_compile_argv.txt" in runner
        and "actual_simulator_argv.txt" in runner
    )
    traps_bound = all(
        token in runner
        for token in (
            "trap 'finalize $?' EXIT",
            "trap 'signal_name=HUP; simulation_status=125; finalize 125' HUP",
            "trap 'signal_name=INT; simulation_status=125; finalize 125' INT",
            "trap 'signal_name=TERM; simulation_status=125; finalize 125' TERM",
            'python3 "$runtime" collect',
        )
    )
    runtime_return_ok = (
        runtime_plusarg_bound
        and time0_marker_emitted
        and enabled_receipt_bound
        and actual_argv_bound
        and RUNTIME_RETURN_TARGETS.issubset(required_targets)
        and traps_bound
        and binding.get("read_only") is True
        and binding.get("drives_dut") is False
        and binding.get("changes_timeout") is False
    )

    directions = {
        "source": source_ok,
        "include": include_ok,
        "compile_enable": compile_enable_ok,
        "runtime_return": runtime_return_ok,
    }
    return {
        "valid": all(directions.values()),
        "status": (
            "FOUR_WAY_BINDING_VALIDATED"
            if all(directions.values())
            else "PACKAGE_OBSERVER_BINDING_INCOMPLETE"
        ),
        "directions": directions,
        "source_receipt": {
            "member": observer_name,
            "unique_source_count": len(observer_members),
            "sha256": sha256_bytes(observer) if observer else None,
            "size_bytes": len(observer),
            "manifest_record_exact": source_record_exact,
            "binding_record_exact": source_binding_exact,
            "fresh_extract_readable": fresh_extract_readable,
        },
        "include_receipt": {
            "literal": incdir_literal,
            "occurrence_count": include_occurrences,
            "normalized_package_relative_directory": normalized_include.as_posix(),
            "stays_within_package": include_stays_in_package,
            "matches_source_parent": include_stays_in_package,
        },
        "compile_enable_receipt": {
            "literal": macro_literal,
            "occurrence_count": macro_occurrences,
            "manifest_macro": binding.get("compile_enable_macro"),
        },
        "runtime_return_receipt": {
            "runtime_plusarg_bound": runtime_plusarg_bound,
            "time0_marker": marker,
            "time0_marker_emitted_from_initial": time0_marker_emitted,
            "enabled_receipt_bound": enabled_receipt_bound,
            "actual_compile_argv_bound": "actual_compile_argv.txt" in runner,
            "actual_simulator_argv_bound": "actual_simulator_argv.txt" in runner,
            "required_return_targets_exact_subset": sorted(
                RUNTIME_RETURN_TARGETS
            ),
            "required_return_targets_present": RUNTIME_RETURN_TARGETS.issubset(
                required_targets
            ),
            "exit_signal_traps_collect": traps_bound,
        },
    }


def _negative_control(
    name: str,
    mutate: Callable[[dict[str, bytes], dict[str, object]], None],
    expected_failed_direction: str,
) -> dict[str, object]:
    members, manifest = _load_final_zip()
    mutate(members, manifest)
    report = _inspect(members, manifest, require_fresh_extract=False)
    return {
        "name": name,
        "expected_failed_direction": expected_failed_direction,
        "failed_closed": (
            report["valid"] is False
            and report["status"] == "PACKAGE_OBSERVER_BINDING_INCOMPLETE"
            and report["directions"][expected_failed_direction] is False
        ),
        "status": report["status"],
        "directions": report["directions"],
    }


def negative_control_receipts() -> dict[str, dict[str, object]]:
    def remove_source(
        members: dict[str, bytes], manifest: dict[str, object]
    ) -> None:
        members.pop(f"{INSTALL_NAME}/{OBSERVER_REL}")
        manifest["files"].pop(OBSERVER_REL)

    def remove_incdir(
        members: dict[str, bytes], manifest: dict[str, object]
    ) -> None:
        _replace_runner(
            members,
            manifest,
            lambda text: text.replace(
                "+incdir+$package_root/tb_probe ", "", 2
            ),
        )

    def remove_macro(
        members: dict[str, bytes], manifest: dict[str, object]
    ) -> None:
        _replace_runner(
            members,
            manifest,
            lambda text: text.replace(
                "+define+NATIVE_RETURN_OBSERVER_ENABLE", "", 2
            ),
        )

    def remove_runtime_return(
        members: dict[str, bytes], manifest: dict[str, object]
    ) -> None:
        _replace_runner(
            members,
            manifest,
            lambda text: text.replace("+RETURN_OBSERVER", "", 1).replace(
                'python3 "$runtime" collect',
                'printf "collector removed by negative control"',
                1,
            ),
        )
        manifest["return_allowlist"] = [
            record
            for record in manifest["return_allowlist"]
            if record.get("target_path")
            not in {
                "evidence/actual_simulator_argv.txt",
                "runs/return_observer.log",
            }
        ]
        members[f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"] = (
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

    return {
        "source_removed": _negative_control(
            "source_removed", remove_source, "source"
        ),
        "incdir_removed": _negative_control(
            "incdir_removed", remove_incdir, "include"
        ),
        "macro_removed": _negative_control(
            "macro_removed", remove_macro, "compile_enable"
        ),
        "runtime_return_removed": _negative_control(
            "runtime_return_removed", remove_runtime_return, "runtime_return"
        ),
    }


def validate_final_zip() -> dict[str, object]:
    observed_zip_sha = sha256_file(ZIP_PATH)
    sidecar_fields = SIDECAR_PATH.read_text(encoding="ascii").split()
    members, manifest = _load_final_zip()
    four_way = _inspect(members, manifest, require_fresh_extract=True)
    negative_controls = negative_control_receipts()
    zip_unchanged = observed_zip_sha == ZIP_SHA256
    sidecar_exact = sidecar_fields == [ZIP_SHA256, ZIP_PATH.name]
    server_rule_matches = sha256_file(SERVER_RULE) == SERVER_RULE_SHA256
    all_negative_controls_fail_closed = all(
        receipt["failed_closed"] for receipt in negative_controls.values()
    )
    valid = (
        four_way["valid"]
        and zip_unchanged
        and sidecar_exact
        and server_rule_matches
        and all_negative_controls_fail_closed
    )
    return {
        "schema": "qlinearadd-node0007-observer-four-way-final-zip-v1",
        "valid": valid,
        "status": (
            "FOUR_WAY_BINDING_VALIDATED"
            if valid
            else "PACKAGE_OBSERVER_BINDING_INCOMPLETE"
        ),
        "rule_id": "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        "server_rule_sha256": sha256_file(SERVER_RULE),
        "server_rule_matches": server_rule_matches,
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": observed_zip_sha,
        "expected_zip_sha256": ZIP_SHA256,
        "zip_unchanged": zip_unchanged,
        "sidecar_exact": sidecar_exact,
        "final_zip_member_count": len(members),
        "four_way": four_way,
        "negative_controls": negative_controls,
        "all_negative_controls_fail_closed": (
            all_negative_controls_fail_closed
        ),
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "package_rebuilt": False,
        "server_action": False,
    }


def main() -> int:
    report = validate_final_zip()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
