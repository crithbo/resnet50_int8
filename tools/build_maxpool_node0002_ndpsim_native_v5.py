"""Build the fresh native-structure MaxPool node0002 server package."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n2_maxpool_ndpsim_native_v5"
RETURN_NAME = f"{INSTALL_NAME}_return"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
OUTPUT_ZIP = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
OUTPUT_SIDECAR = OUTPUT_ROOT / f"{INSTALL_NAME}.zip.sha256"
BUILD_RECEIPT = OUTPUT_ROOT / f"{INSTALL_NAME}.build.json"
SOURCE_JSON = (
    ROOT / "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json"
)
SOURCE_JSON_SHA256 = (
    "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
)
NATIVE_ROOT = (
    ROOT / "ndp-sim/model_execplan/output/node0002_maxpool_wave0_graph"
)
RUNTIME_SOURCE = ROOT / "tools/maxpool_node0002_ndpsim_native_runtime_v5.py"
CURRENT_FILES = (
    ROOT / ".agents/rules/生成前必读索引.md",
    ROOT / ".agents/rules/服务器测试包生成规则.md",
    ROOT / ".agents/rules/算子配置规则.md",
    ROOT / ".agents/rules/NDP硬件字段语义.md",
    ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
)
EXPECTED_CURRENT = {
    ".agents/rules/生成前必读索引.md": (
        "f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8"
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
    ),
    ".agents/rules/算子配置规则.md": (
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
    ),
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": (
        "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
    ),
}


class NativeMaxPoolBuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_records(root: Path, *, exclude_manifest: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "TEST_PACKAGE_MANIFEST.json":
            continue
        if path.is_symlink():
            raise NativeMaxPoolBuildError(f"symlink is forbidden: {path}")
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def _runtime_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "maxpool_node0002_ndpsim_native_runtime_v5", RUNTIME_SOURCE
    )
    if spec is None or spec.loader is None:
        raise NativeMaxPoolBuildError("cannot import native runtime")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_current_receipts() -> dict[str, str]:
    receipts: dict[str, str] = {}
    for path in CURRENT_FILES:
        relative = path.relative_to(ROOT).as_posix()
        digest = sha256(path)
        if EXPECTED_CURRENT.get(relative) != digest:
            raise NativeMaxPoolBuildError(
                f"current receipt drift: {relative}: {digest}"
            )
        receipts[relative] = digest
    return receipts


def _copy_native_tree(package: Path) -> dict[str, Any]:
    native = package / "workload/native"
    shutil.copytree(NATIVE_ROOT, native)
    receipts = package / "validation/native_generation_receipts"
    receipts.mkdir(parents=True)
    moved_receipts = []
    for name in ("decode_package_manifest.json", "maxpool_wave0_input_manifest.json"):
        source = native / name
        destination = receipts / name
        shutil.move(source, destination)
        moved_receipts.append(
            {
                "path": name,
                "size_bytes": destination.stat().st_size,
                "sha256": sha256(destination),
            }
        )
    golden_root = package / "validation/golden/op0"
    moved_golden = []
    for slice_id in range(28):
        source_dir = native / f"install/op0/slice{slice_id:02d}"
        destination_dir = golden_root / f"slice{slice_id:02d}"
        destination_dir.mkdir(parents=True)
        for path in sorted(source_dir.glob("matrix_D_linearized_128bit*")):
            destination = destination_dir / path.name
            shutil.move(path, destination)
            moved_golden.append(
                {
                    "slice_id": slice_id,
                    "name": path.name,
                    "size_bytes": destination.stat().st_size,
                    "sha256": sha256(destination),
                }
            )
    source_copy = (
        native
        / "source_config/maxpool_config_16_112_112_stride2_padding1.json"
    )
    source_copy.parent.mkdir()
    shutil.copyfile(SOURCE_JSON, source_copy)
    if sha256(source_copy) != SOURCE_JSON_SHA256:
        raise NativeMaxPoolBuildError("source JSON copy differs")
    return {
        "moved_native_receipts": moved_receipts,
        "moved_golden_files": moved_golden,
        "source_copy": source_copy.relative_to(package).as_posix(),
    }


def _adapt_sca(package: Path) -> dict[str, Any]:
    native = package / "workload/native"
    changes: dict[str, list[dict[str, str]]] = {}
    prefix = f"install/cfg_pkg/{INSTALL_NAME}/"
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        path = native / name
        original_bytes = path.read_bytes()
        original_text = original_bytes.decode("utf-8")
        value = json.loads(original_text)
        current: list[dict[str, str]] = []
        for key, item in value.items():
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                continue
            old = item["path"]
            if old.startswith("/") or ".." in Path(old).parts:
                raise NativeMaxPoolBuildError(f"unsafe native SCA path: {old}")
            new = prefix + old
            item["path"] = new
            old_token = json.dumps(old, ensure_ascii=False)
            new_token = json.dumps(new, ensure_ascii=False)
            if original_text.count(old_token) != 1:
                raise NativeMaxPoolBuildError(
                    f"native SCA path token is not unique: {name}:{key}:{old}"
                )
            original_text = original_text.replace(old_token, new_token, 1)
            current.append({"key": key, "before": old, "after": new})
        path.write_bytes(original_text.encode("utf-8"))
        changes[name] = current
    if len(changes["sca_cfg.json"]) != 30 or len(changes["sca_cfg_D.json"]) != 28:
        raise NativeMaxPoolBuildError("native SCA path count differs")
    return {
        "mechanical_namespace_only": True,
        "changes": changes,
    }


def _runner_text() -> str:
    return """#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *) echo "Server root must be absolute: $1" >&2; exit 2 ;;
esac
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || {
  echo "Server root is not enterable: $1" >&2
  exit 2
}
package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
runtime_tool="${package_root}/package_tools/maxpool_node0002_ndpsim_native_runtime_v5.py"
identity_json="$(python3 "${runtime_tool}" identity --package-root "${package_root}")" || exit 5
install_name="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["install_name"])' <<<"${identity_json}")"
return_name="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["return_name"])' <<<"${identity_json}")"
[ -n "${install_name}" ] && [ -n "${return_name}" ] || exit 5

cfg_root="${server_root}/install/cfg_pkg/${install_name}"
run_dir="${server_root}/run_${install_name}"
evidence_root="${server_root}/evidence_${install_name}"
return_dir="${server_root}/${return_name}"
return_zip="${return_dir}.zip"
return_sha="${return_zip}.sha256"
for tool in python3 timeout make; do
  command -v "${tool}" >/dev/null 2>&1 || {
    echo "Missing command: ${tool}" >&2
    exit 3
  }
done
for target in "${cfg_root}" "${run_dir}" "${evidence_root}" \
  "${return_dir}" "${return_zip}" "${return_sha}"; do
  [ ! -e "${target}" ] || {
    echo "Fresh namespace required: ${target}" >&2
    exit 4
  }
done

mkdir -p "${evidence_root}"
compile_status=125
simulation_status=125
runner_status=125
termination_signal=""
finalization_started=0

finalize_return() {
  original_status="$1"
  if [ "${finalization_started}" -ne 0 ]; then
    exit "${original_status}"
  fi
  finalization_started=1
  trap - EXIT HUP INT TERM
  set +e
  [ -z "${termination_signal}" ] || \
    printf '%s\n' "${termination_signal}" > "${evidence_root}/termination_signal.txt"
  printf '%s\n' "${compile_status}" > "${evidence_root}/compile_exit_status.txt"
  printf '%s\n' "${simulation_status}" > "${evidence_root}/simulation_exit_status.txt"
  printf '%s\n' "${runner_status}" > "${evidence_root}/runner_exit_status.txt"
  python3 "${runtime_tool}" analyze \
    --server-root "${server_root}" --package-root "${package_root}" \
    --install-name "${install_name}" --run-dir "${run_dir}" \
    --compile-status "${compile_status}" \
    --simulation-status "${simulation_status}" \
    --output "${evidence_root}/SERVER_RESULT_GATE.json" >/dev/null
  analysis_status=$?
  python3 - "${original_status}" "${analysis_status}" <<'PY' \
    > "${evidence_root}/finalizer_status.json"
import json,sys
print(json.dumps({
  "schema": "maxpool-native-finalizer-status-v1",
  "original_status": int(sys.argv[1]),
  "analysis_status": int(sys.argv[2]),
  "finalizer_entered": True
}, indent=2))
PY
  python3 "${runtime_tool}" collect \
    --server-root "${server_root}" --package-root "${package_root}" \
    --install-name "${install_name}" --evidence-root "${evidence_root}" \
    --run-dir "${run_dir}" --runner-status "${runner_status}" >/dev/null
  collection_status=$?
  if [ -f "${return_zip}" ] && [ -f "${return_sha}" ]; then
    echo "Return ZIP: ${return_zip}"
  else
    echo "Return collection did not produce ZIP and sidecar." >&2
  fi
  final_status="${original_status}"
  for status in "${analysis_status}" "${collection_status}"; do
    if [ "${final_status}" -eq 0 ] && [ "${status}" -ne 0 ]; then
      final_status="${status}"
    fi
  done
  exit "${final_status}"
}
trap 'finalize_return $?' EXIT
trap 'termination_signal=HUP; runner_status=129; exit 129' HUP
trap 'termination_signal=INT; runner_status=130; exit 130' INT
trap 'termination_signal=TERM; runner_status=143; exit 143' TERM

python3 "${runtime_tool}" preflight-package \
  --package-root "${package_root}" \
  --output "${evidence_root}/package_preflight.json" >/dev/null || exit 5
mkdir -p "${cfg_root}" "${run_dir}/sim_results"
cp -a "${package_root}/workload/native/." "${cfg_root}/"
python3 "${runtime_tool}" preflight-installed \
  --package-root "${package_root}" --server-root "${server_root}" \
  --install-name "${install_name}" \
  --output "${evidence_root}/installed_preflight.json" >/dev/null || exit 5

cd "${server_root}"
compile_argv="make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=${run_dir}"
printf '%s\n' "${compile_argv}" > "${evidence_root}/actual_compile_argv.txt"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="${run_dir}" \
  > "${run_dir}/sim_results/compile_driver.log" 2>&1
compile_status=$?
if [ "${compile_status}" -eq 0 ]; then
  simulator_argv="${run_dir}/sim_results/simv -l ${run_dir}/sim_results/sim.log +vcs+lic+wait +SCA_CFG=${cfg_root}/sca_cfg.json +SCA_CFG_D=${cfg_root}/sca_cfg_D.json"
  printf '%s\n' "${simulator_argv}" > "${evidence_root}/actual_simulator_argv.txt"
  timeout --foreground --signal=TERM --kill-after=30s 12h \
    "${run_dir}/sim_results/simv" \
    -l "${run_dir}/sim_results/sim.log" +vcs+lic+wait \
    "+SCA_CFG=${cfg_root}/sca_cfg.json" \
    "+SCA_CFG_D=${cfg_root}/sca_cfg_D.json"
  simulation_status=$?
else
  simulation_status=125
  printf '%s\n' "simulation_not_started_compile_status=${compile_status}" \
    > "${evidence_root}/actual_simulator_argv.txt"
fi
if [ "${compile_status}" -ne 0 ]; then
  runner_status="${compile_status}"
else
  runner_status="${simulation_status}"
fi
set -e
exit "${runner_status}"
"""


def _build_directory(destination: Path, receipts: dict[str, str]) -> Path:
    package = destination / INSTALL_NAME
    package.mkdir(parents=True)
    native_receipt = _copy_native_tree(package)
    namespace_receipt = _adapt_sca(package)
    write_json(
        package / "validation/native_structure_receipt.json",
        {
            "schema": "maxpool-node0002-native-structure-receipt-v1",
            "authority": (
                "ndp-sim/model_execplan/output/node0002_maxpool_wave0_graph"
            ),
            "isomorphic_sample": "jsons/gemv_local",
            "direct_consumer": "ndp-sim/model_execplan/main.py",
            "native_directory_style": [
                "jsons",
                "config",
                "install",
                "sca_cfg.json",
                "sca_cfg_D.json",
                "instructions_explained.txt",
                "*_withbaseaddr.json",
            ],
            "generic_observer_schema_present": False,
            "generic_canonical_diagnostic_present": False,
            "v4_workaround_reused": False,
            **native_receipt,
            "namespace_adaptation": namespace_receipt,
        },
    )
    package_tools = package / "package_tools"
    package_tools.mkdir()
    shutil.copyfile(
        RUNTIME_SOURCE,
        package_tools / "maxpool_node0002_ndpsim_native_runtime_v5.py",
    )
    runner = package / "PREPARE_AND_RUN.sh"
    runner.write_text(_runner_text(), encoding="utf-8", newline="\n")
    os.chmod(runner, 0o755)
    (package / "README.md").write_text(
        "# Native ndp-sim MaxPool node0002 server package\n\n"
        "Run from this extracted package directory:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "The workload retains the standard ndp-sim single-operator directory "
        "style. The authoritative source JSON is byte-identical. Only SCA path "
        "namespace binding and formal-D/golden separation are mechanical server "
        "packaging transformations. No observer, canonical diagnostic schema, "
        "v4 workaround, functional RTL, or server source preflight is included.\n",
        encoding="utf-8",
        newline="\n",
    )
    installed = file_records(package / "workload/native")
    payload = file_records(package, exclude_manifest=True)
    manifest = {
        "schema": "maxpool-node0002-ndpsim-native-server-package-v1",
        "install_name": INSTALL_NAME,
        "run_name": f"run_{INSTALL_NAME}",
        "return": {"name": RETURN_NAME, "zip": f"{RETURN_NAME}.zip"},
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "user_override": {
            "maxpool_fully_tested_reuse_authority": True,
            "skip_generic_successor_observer_route": True,
            "native_structure_only": True,
        },
        "source_json": {
            "path": (
                "workload/native/source_config/"
                "maxpool_config_16_112_112_stride2_padding1.json"
            ),
            "sha256": SOURCE_JSON_SHA256,
            "byte_identical": True,
            "semantic_identity": True,
        },
        "native_structure": {
            "authority": (
                "ndp-sim/model_execplan/output/node0002_maxpool_wave0_graph"
            ),
            "direct_consumer": "ndp-sim/model_execplan/main.py",
            "isomorphic_sample": "jsons/gemv_local",
            "operator_count": 1,
            "active_slice_count": 28,
            "execplan_128bit_lines": 29,
            "sca_input_count": 28,
            "formal_D_count": 28,
            "materialized_diff_paths": [
                "$.stream_engine.stream0.base_addr",
                "$.stream_engine.stream1.base_addr",
            ],
            "namespace_only_sca_path_adaptation": True,
            "runtime_D_initially_absent": True,
        },
        "diagnostics": {
            "observer_present": False,
            "canonical_diagnostic_present": False,
            "exemption": (
                "user explicitly confirmed MaxPool fully tested and requested "
                "the native ndp-sim structure without the prior generic observer route"
            ),
            "bounded_compile_and_sim_log_tails": True,
            "exit_and_signal_finalizer": True,
        },
        "server_profile": {
            "user_supplied_root": True,
            "server_source_preflight": False,
            "functional_rtl_modified": False,
        },
        "only_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        ),
        "rule_receipts": receipts,
        "applied_rule_ids": [
            "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
            "CDA-SERVER-WORKLOAD-PROVENANCE-001",
            "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "CDA-SERVER-ONE-COMMAND-001",
            "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
            "CDA-SCA-D-TB-READBACK-LENGTH-001",
            "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
            "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
        ],
        "explicit_not_applicable": {
            "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001": (
                "user override requires the already-validated native MaxPool "
                "structure and forbids the previous generic observer route"
            ),
            "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001": (
                "single native stage, no package-local diagnostic observer"
            ),
            "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001": (
                "no observer is packaged or relied upon"
            ),
        },
        "installed_files": installed,
        "files": payload,
    }
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)
    result = _runtime_module().preflight_package(package)
    if not result.get("valid"):
        raise NativeMaxPoolBuildError("fresh package preflight failed")
    return package


def _write_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _safe_extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        roots: set[str] = set()
        for info in archive.infolist():
            relative = Path(info.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise NativeMaxPoolBuildError(f"unsafe ZIP path: {info.filename}")
            if info.filename.endswith("/"):
                continue
            roots.add(relative.parts[0])
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    if roots != {INSTALL_NAME}:
        raise NativeMaxPoolBuildError(f"ZIP roots differ: {roots}")
    return destination / INSTALL_NAME


def validate_zip(zip_path: Path) -> dict[str, Any]:
    if not zip_path.is_file():
        raise NativeMaxPoolBuildError(f"missing ZIP: {zip_path}")
    with tempfile.TemporaryDirectory() as temp_text:
        package = _safe_extract(zip_path, Path(temp_text))
        manifest = json.loads(
            (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        if manifest.get("install_name") != INSTALL_NAME:
            raise NativeMaxPoolBuildError("final ZIP identity differs")
        actual = file_records(package, exclude_manifest=True)
        if actual != manifest.get("files"):
            raise NativeMaxPoolBuildError("final ZIP exact set/hash differs")
        runtime = _runtime_module()
        preflight = runtime.preflight_package(package)
        before = file_records(package)
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(
                    package
                    / "package_tools/maxpool_node0002_ndpsim_native_runtime_v5.py"
                ),
                "preflight-package",
                "--package-root",
                str(package),
                "--output",
                str(Path(temp_text) / "preflight.json"),
            ],
            cwd=package,
            check=True,
            capture_output=True,
            text=True,
        )
        after = file_records(package)
        if before != after:
            raise NativeMaxPoolBuildError("fresh-extract preflight changed package")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        forbidden = (
            "+RETURN_OBSERVER",
            "NATIVE_RETURN_OBSERVER_ENABLE",
            "CANONICAL_DIAG_DECISION",
            "tb_probe",
            "r5_n2_maxpool_native_reuse_v4",
        )
        hits = [item for item in forbidden if item in runner]
        if hits:
            raise NativeMaxPoolBuildError(f"forbidden generic route in runner: {hits}")
        return {
            "schema": "maxpool-node0002-ndpsim-native-final-zip-validation-v1",
            "valid": True,
            "zip_path": zip_path.relative_to(ROOT).as_posix(),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": sha256(zip_path),
            "entry_count": len(actual) + 1,
            "source_json_sha256": preflight["source_json_sha256"],
            "source_json_byte_identical": True,
            "materialized_diff_paths": preflight["materialized_diff_paths"],
            "native_structure_valid": True,
            "runtime_D_initially_absent": True,
            "generic_observer_schema_present": False,
            "generic_canonical_present": False,
            "fresh_extract_tree_immutable": True,
        }


def build() -> dict[str, Any]:
    if sha256(SOURCE_JSON) != SOURCE_JSON_SHA256:
        raise NativeMaxPoolBuildError("source JSON authority drift")
    receipts = _read_current_receipts()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as first_text, tempfile.TemporaryDirectory() as second_text:
        first_root = Path(first_text)
        second_root = Path(second_text)
        first_package = _build_directory(first_root, receipts)
        second_package = _build_directory(second_root, receipts)
        first_zip = first_root / f"{INSTALL_NAME}.zip"
        second_zip = second_root / f"{INSTALL_NAME}.zip"
        _write_zip(first_package, first_zip)
        _write_zip(second_package, second_zip)
        if first_zip.read_bytes() != second_zip.read_bytes():
            raise NativeMaxPoolBuildError("deterministic ZIP builds differ")
        shutil.copyfile(first_zip, OUTPUT_ZIP)
    validation = validate_zip(OUTPUT_ZIP)
    OUTPUT_SIDECAR.write_text(
        f"{validation['zip_sha256']}  {OUTPUT_ZIP.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report = {
        **validation,
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_release": False,
        "user_override_applied": True,
        "deterministic_double_build": True,
        "sidecar_path": OUTPUT_SIDECAR.relative_to(ROOT).as_posix(),
        "sidecar_sha256": sha256(OUTPUT_SIDECAR),
        "only_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        ),
        "expected_return": f"{RETURN_NAME}.zip",
        "server_action": False,
    }
    write_json(BUILD_RECEIPT, report)
    return report


def main() -> int:
    try:
        report = build()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"MaxPool native v5 build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
