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
from tools.validate_gap_node0071_observer_binding import (  # noqa: E402
    validate_with_negative_controls,
)


INSTALL_NAME = "r5_n71_gap_v5_obsbind"
SOURCE_NAME = "r5_n71_gap_v4_hangloc"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v4_hangloc.zip"
)
SOURCE_SHA256 = (
    "3c49472421dbf9e7a1cfc9bab42bdc677db6d2dc2781fb4ad18ff119968ac730"
)
RETURN_SHA256 = (
    "3708beafb70675f9f838cd38d01170241775ba78e2e1f1cf3d53949c69b60d44"
)
RETURN_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-gap-node0071-v4-hangloc-return-analysis"
    / "report.json"
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
ENABLE_MACRO = "+define+NATIVE_RETURN_OBSERVER_ENABLE"
TIME0_MARKER = "[RETURN_OBSERVER] enabled"


class PackageBuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    prefix = f"{SOURCE_NAME}/"
    entries: list[zipfile.ZipInfo] = []
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
            raise PackageBuildError(
                f"unsafe source member: {info.filename}"
            )
        seen.add(info.filename)
        if not info.is_dir():
            entries.append(info)
    return entries


def _extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise PackageBuildError("frozen v4 source identity differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise PackageBuildError("frozen v4 source CRC differs")
        for info in _safe_entries(archive):
            relative = PurePosixPath(info.filename).relative_to(SOURCE_NAME)
            target = package.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return package


def _replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [_replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_identity(item)
            for key, item in value.items()
        }
    return value


def _numeric_workload_records(package: Path) -> dict[str, Any]:
    records = file_records(
        package / "workload", exclude_manifest=False
    )
    records.pop("sca_cfg.json")
    records.pop("sca_cfg_D.json")
    return records


def _rebind_sca(package: Path) -> None:
    for relative in ("workload/sca_cfg.json", "workload/sca_cfg_D.json"):
        path = package / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        rebound = _replace_identity(value)
        if rebound == value:
            raise PackageBuildError(f"identity absent from {relative}")
        write_json(path, rebound)


def _patch_runtime(package: Path) -> None:
    path = (
        package
        / "package_tools/gap_node0071_complete_server_runtime.py"
    )
    text = path.read_text(encoding="utf-8")
    anchor = "len(allowlist) != 67"
    if text.count(anchor) != 1:
        raise PackageBuildError("runtime allowlist anchor differs")
    path.write_text(
        text.replace(anchor, "len(allowlist) != 68"),
        encoding="utf-8",
        newline="\n",
    )


def _patch_observer_guard(package: Path) -> None:
    path = (
        package
        / "package_tools/gap_node0071_package_observer_guard.py"
    )
    text = path.read_text(encoding="utf-8")
    old_signature = (
        "def observer_precompile_receipt(\n"
        "    package_root: Path, expected_sha256: str\n"
        ") -> dict[str, Any]:"
    )
    new_signature = (
        "def observer_precompile_receipt(\n"
        "    package_root: Path, expected_sha256: str, runner: Path\n"
        ") -> dict[str, Any]:"
    )
    if text.count(old_signature) != 1:
        raise PackageBuildError("observer guard signature anchor differs")
    text = text.replace(old_signature, new_signature)
    anchor = (
        "    return {\n"
        '        "schema": '
        '"gap-node0071-package-local-observer-precompile-v1",'
    )
    injected = (
        "    runner_path = runner.resolve()\n"
        "    runner_terms = {\n"
        '        "package_local_incdir": '
        '"+incdir+$package_root/tb_probe",\n'
        '        "compile_enable_macro": '
        '"+define+NATIVE_RETURN_OBSERVER_ENABLE",\n'
        '        "runtime_enable": "+RETURN_OBSERVER",\n'
        '        "runtime_output": "+RETURN_OBS_FILE=$observer_log",\n'
        '        "time0_marker_check": "[RETURN_OBSERVER] enabled",\n'
        '        "actual_compile_argv": "actual_compile_argv.txt",\n'
        '        "actual_simulator_argv": "actual_simulator_argv.txt",\n'
        '        "progress_return": "progress_samples.log",\n'
        "    }\n"
        "    runner_presence = {key: False for key in runner_terms}\n"
        "    if (\n"
        "        not runner_path.is_file()\n"
        "        or runner_path.is_symlink()\n"
        "        or not runner_path.is_relative_to(root)\n"
        "    ):\n"
        '        errors.append("package runner is unavailable or escapes root")\n'
        "    else:\n"
        '        runner_text = runner_path.read_text(encoding="utf-8")\n'
        "        runner_presence = {\n"
        "            key: term in runner_text\n"
        "            for key, term in runner_terms.items()\n"
        "        }\n"
        "        if not all(runner_presence.values()):\n"
        '            errors.append("observer four-way runner binding differs")\n'
        "\n"
        + anchor
    )
    if text.count(anchor) != 1:
        raise PackageBuildError("observer guard return anchor differs")
    text = text.replace(anchor, injected)
    receipt_anchor = (
        '        "compile_include_directory": '
        'str((root / "tb_probe").resolve()),\n'
    )
    receipt_extension = (
        receipt_anchor
        + '        "runner_path": str(runner_path),\n'
        + '        "runner_binding": runner_presence,\n'
        + '        "four_way_rule": '
        '"CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",\n'
    )
    if text.count(receipt_anchor) != 1:
        raise PackageBuildError("observer guard receipt anchor differs")
    text = text.replace(receipt_anchor, receipt_extension)
    cli_anchor = (
        '    parser.add_argument("--expected-sha256", required=True)\n'
    )
    if text.count(cli_anchor) != 1:
        raise PackageBuildError("observer guard CLI anchor differs")
    text = text.replace(
        cli_anchor,
        cli_anchor
        + '    parser.add_argument("--runner", type=Path, required=True)\n',
    )
    call_anchor = (
        "        args.package_root, args.expected_sha256\n"
    )
    if text.count(call_anchor) != 1:
        raise PackageBuildError("observer guard call anchor differs")
    text = text.replace(
        call_anchor,
        "        args.package_root, args.expected_sha256, args.runner\n",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8").replace(
        SOURCE_NAME, INSTALL_NAME
    )
    guard_anchor = (
        '  >"$evidence_root/observer_precompile.json" || exit 7'
    )
    if text.count(guard_anchor) != 1:
        raise PackageBuildError("observer guard runner anchor differs")
    text = text.replace(
        guard_anchor,
        '  --runner "$package_root/PREPARE_AND_RUN.sh" \\\n'
        '  >"$evidence_root/observer_precompile.json" || exit 7',
    )
    command_anchor = "VCS_EXTRA_OPTS=+incdir+<package-root>/tb_probe"
    if text.count(command_anchor) != 1:
        raise PackageBuildError("server command token differs")
    text = text.replace(
        command_anchor,
        "VCS_EXTRA_OPTS="
        + ENABLE_MACRO
        + " +incdir+<package-root>/tb_probe",
    )
    guard_done = (
        '  >"$evidence_root/observer_precompile.json" || exit 7\n'
    )
    if text.count(guard_done) != 1:
        raise PackageBuildError("observer guard completion anchor differs")
    text = text.replace(
        guard_done,
        guard_done
        + 'compile_extra_opts="'
        + ENABLE_MACRO
        + ' +incdir+$package_root/tb_probe"\n',
    )
    compile_anchor = "set +e\ntimeout --foreground"
    if text.count(compile_anchor) != 1:
        raise PackageBuildError("compile command anchor differs")
    actual_compile = (
        "printf 'make -C %q -f Makefile.tb_NDP_Top_new_phy compile "
        "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=%q "
        "VCS_EXTRA_OPTS=%q\\n' \\\n"
        '  "$server_root" "$run_root" "$compile_extra_opts" \\\n'
        '  >"$evidence_root/actual_compile_argv.txt"\n'
    )
    text = text.replace(
        compile_anchor,
        actual_compile + "set +e\ntimeout --foreground",
    )
    vcs_anchor = 'VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe"'
    if text.count(vcs_anchor) != 1:
        raise PackageBuildError("VCS option anchor differs")
    text = text.replace(
        vcs_anchor, 'VCS_EXTRA_OPTS="$compile_extra_opts"'
    )
    binding_anchor = (
        '  if [ -s "$observer_log" ] &&      '
        "grep -q 'Native NDP return observer' "
        '"$observer_log"; then\n'
    )
    if text.count(binding_anchor) != 1:
        raise PackageBuildError("observer binding anchor differs")
    text = text.replace(
        binding_anchor,
        '  if [ -s "$observer_log" ] && '
        "grep -Fq '[RETURN_OBSERVER] enabled' "
        '"$run_root/sim_results/sim.log" && '
        "grep -q 'Native NDP return observer' "
        '"$observer_log"; then\n',
    )
    text = text.replace(
        "observer_enabled_and_returned=true\\n",
        "observer_enabled_and_returned=true\\n"
        "time0_enabled_marker=true\\n",
    )
    text = text.replace(
        "observer_enabled_and_returned=false\\n",
        "observer_enabled_and_returned=false\\n"
        "time0_enabled_marker=false\\n",
    )
    required = (
        ENABLE_MACRO,
        "+incdir+$package_root/tb_probe",
        "+RETURN_OBSERVER",
        "+RETURN_OBS_FILE=$observer_log",
        TIME0_MARKER,
        "actual_compile_argv.txt",
        "actual_simulator_argv.txt",
        "progress_samples.log",
        "trap 'signal_name=INT",
    )
    if not all(term in text for term in required):
        raise PackageBuildError("patched runner four-way terms differ")
    path.write_text(text, encoding="utf-8", newline="\n")


def _add_compile_allowlist(manifest: dict[str, Any]) -> None:
    allowlist = manifest.get("return_allowlist")
    if not isinstance(allowlist, list) or len(allowlist) != 67:
        raise PackageBuildError("source return allowlist differs")
    allowlist.append(
        {
            "source_root": "evidence",
            "source_path": "actual_compile_argv.txt",
            "target_path": "evidence/actual_compile_argv.txt",
            "required": True,
            "max_bytes": 1 << 20,
            "missing_meaning": (
                "actual observer-enabled compile argv unavailable"
            ),
        }
    )


def _preflight(package: Path) -> dict[str, Any]:
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
        raise PackageBuildError(
            f"package preflight failed: {process.stdout} {process.stderr}"
        )
    value = json.loads(process.stdout)
    if not isinstance(value, dict) or value.get("valid") is not True:
        raise PackageBuildError("package preflight receipt differs")
    return value


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = _extract_source(destination)
    frozen_before = _numeric_workload_records(package)
    _rebind_sca(package)
    _patch_runtime(package)
    _patch_observer_guard(package)
    _patch_runner(package)
    (package / "README.md").write_text(
        "# GAP node0071 v5 observer compile binding\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX` and reuses "
        "the frozen v4 workload. It fixes only the package-side observer "
        "four-way binding by adding the compile enable macro, actual compile "
        "argv receipt, time-0 marker gate, return allowlist, and signal-trap "
        "collection. Run once with:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = _replace_identity(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    _add_compile_allowlist(manifest)
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v5",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "package-side observer compile binding repair only; frozen "
                "GAP sum/tail/golden/config unchanged; no functional fix "
                "and no E3/E4/E5"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "source_v4_return_sha256": RETURN_SHA256,
            "source_numeric_payload_reused_without_rebuild": True,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
            "observer_binding_contract": {
                "rule_id":
                    "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
                "source_relative_path":
                    "tb_probe/native_return_observer.svh",
                "source_sha256": OBSERVER_SHA256,
                "package_local_incdir":
                    "+incdir+$package_root/tb_probe",
                "enable_macro": ENABLE_MACRO,
                "runtime_plusarg": "+RETURN_OBSERVER",
                "time0_enabled_marker": TIME0_MARKER,
                "actual_compile_argv_returned": True,
                "actual_simulator_argv_returned": True,
                "observer_log_returned": True,
                "progress_summary_returned": True,
                "signal_trap_collection": True,
                "negative_controls_required": [
                    "delete_source",
                    "delete_incdir",
                    "delete_enable_macro",
                    "delete_runtime_return",
                ],
            },
        }
    )
    observer_contract = manifest.get("package_local_observer")
    if not isinstance(observer_contract, dict):
        raise PackageBuildError("source observer contract absent")
    observer_contract["compile_binding"] = (
        "VCS_EXTRA_OPTS="
        + ENABLE_MACRO
        + " +incdir+<package_root>/tb_probe"
    )
    observer_contract["compile_enable_macro"] = ENABLE_MACRO
    provenance = manifest.get("generation_provenance")
    if not isinstance(provenance, dict):
        raise PackageBuildError("generation provenance differs")
    provenance.update(
        {
            "tool": "tools/build_gap_node0071_v5_obsbind_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "bound_return_sha256": RETURN_SHA256,
            "bound_return_analysis":
                str(RETURN_ANALYSIS.relative_to(ROOT).as_posix()),
            "numeric_payload_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change":
                "observer compile/runtime/return binding only",
        }
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    checked = _preflight(package)
    frozen_after = _numeric_workload_records(package)
    if frozen_before != frozen_after:
        raise PackageBuildError("frozen numeric workload drifted")
    return package, {
        "numeric_workload_tree_equal": True,
        "numeric_workload_file_count": len(frozen_after),
        "package_preflight": checked,
    }


def _repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_records = file_records(package, exclude_manifest=False)
    first_sha = sha256(zip_path)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v5-repeat-"
    ) as temporary:
        repeat_package, repeat_proof = build_directory(Path(temporary))
        repeat_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeat_package, repeat_zip, archive_root=INSTALL_NAME
        )
        if (
            first_records
            != file_records(repeat_package, exclude_manifest=False)
            or first_sha != sha256(repeat_zip)
            or not repeat_proof["numeric_workload_tree_equal"]
        ):
            raise PackageBuildError("repeated build differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def _fresh_extract_preflight(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v5-bootstrap-"
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            if archive.testzip() is not None:
                raise PackageBuildError("package ZIP CRC failed")
            archive.extractall(root)
        package = root / INSTALL_NAME
        before = file_records(package, exclude_manifest=False)
        checked = _preflight(package)
        after = file_records(package, exclude_manifest=False)
        if before != after:
            raise PackageBuildError("fresh preflight mutated package")
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
    binding_path = (
        output_root / f"{INSTALL_NAME}.observer_binding_validation.json"
    )
    for path in (
        package_path,
        zip_path,
        sidecar,
        validation_path,
        binding_path,
    ):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        package, proof = build_directory(output_root)
        repeated = _repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        fresh = _fresh_extract_preflight(zip_path)
        binding = validate_with_negative_controls(zip_path)
        write_json(binding_path, binding)
        validation = {
            "schema":
                "gap-node0071-observer-binding-package-validation-v5",
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
            "bound_return_sha256": RETURN_SHA256,
            "numeric_workload_tree_equal":
                proof["numeric_workload_tree_equal"],
            "numeric_workload_file_count":
                proof["numeric_workload_file_count"],
            "package_preflight": proof["package_preflight"],
            "observer_four_way_final_zip": binding,
            "functional_fix": False,
            "functional_rtl_modified": False,
            "preloaded_runtime_readback_target_count": 0,
            "result_gate_fail_closed": True,
            "return_allowlist_only": True,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "server_action": False,
            "repeated_build": repeated,
            "fresh_extract_preflight": fresh,
        }
        write_json(validation_path, validation)
    except Exception as error:
        print(f"GAP v5 diagnostic build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
