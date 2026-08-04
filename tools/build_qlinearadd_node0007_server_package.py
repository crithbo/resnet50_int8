from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_closure import (  # noqa: E402
    CONTRACT_REL,
    TASK_RECORD_REL,
    validate_closure,
)
from resnet50_pipeline.qlinearadd_node0007_full_e2 import (  # noqa: E402
    LOCAL_ELEMENTS,
    ROOT_REL,
    load_physical_bundle,
)
from tools.qlinearadd_node0007_server_runtime import (  # noqa: E402
    file_records,
    preflight,
)


INSTALL_NAME = "r5_qadd_n7_relocated_v2"
MANIFEST_SCHEMA = "qlinearadd-node0007-relocated-server-package-v2"
PACKAGE_DESCRIPTION = (
    "ResNet50 node0007 QLinearAdd relocated full-E2 test"
)
GENERATOR_REL = "tools/build_qlinearadd_node0007_server_package.py"
OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
SOURCE_PIPELINE = (
    ROOT
    / ROOT_REL
    / "execplan/pipeline_output"
)
RUNTIME_SOURCE = ROOT / "tools/qlinearadd_node0007_server_runtime.py"
SERVER_RULE_REL = Path(".agents/rules/服务器测试包生成规则.md")
SERVER_RULE_SHA256 = (
    "153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2"
)
PAD_BYTES = 135_168
SUPERSEDED_V1_SHA256 = (
    "2c796e1a2b676bc2a1413552c85f0bbd93e6fa0a94d0afed2d1c84456a4462d4"
)
SUPERSEDED_IDENTITY = {
    "zip": (
        "artifacts/operator_config_validation/r5-server-test-packages/"
        "r5_qadd_n7_relocated_v1.zip"
    ),
    "sha256": SUPERSEDED_V1_SHA256,
    "reason": (
        "v1 declared return budgets but omitted the upload ZIP and "
        "extracted-size exception required for the large formal "
        "SCA_D exact-set"
    ),
    "v1_release_allowed": False,
}


class PackageBuildError(ValueError):
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
        raise PackageBuildError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_128bit(path: Path, payload: bytes) -> None:
    if len(payload) % 16:
        raise PackageBuildError(f"unaligned 128-bit payload: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            format(
                int.from_bytes(payload[offset : offset + 16], "little"),
                "0128b",
            )
            for offset in range(0, len(payload), 16)
        )
        + "\n",
        encoding="ascii",
        newline="\n",
    )


def _rebind_path(relative: str) -> str:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise PackageBuildError(f"unsafe SCA path: {relative}")
    return (
        PurePosixPath("install", "cfg_pkg", INSTALL_NAME).joinpath(rel).as_posix()
    )


def _sca_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    source = load_json(SOURCE_PIPELINE / "sca_cfg.json")
    sca: dict[str, Any] = {
        key: value
        for key, value in source.items()
        if key in {"Exec_Base", "Exec_Length", "Repeat_Num"}
    }
    execution = dict(source["ExecutionPlan"])
    execution["path"] = _rebind_path(str(execution["path"]))
    sca["ExecutionPlan"] = execution
    roots = (
        "op_a_dequant_matrixA_",
        "op_b_dequant_matrixA_",
        "op_relocation_pad_matrixA_",
    )
    for key, value in source.items():
        if key.startswith(roots):
            entry = dict(value)
            entry["path"] = _rebind_path(str(entry["path"]))
            sca[key] = entry

    source_d = load_json(SOURCE_PIPELINE / "sca_cfg_D.json")
    sca_d: dict[str, Any] = {}
    for key, value in source_d.items():
        if key.startswith("op_tail_round_matrixD_"):
            entry = dict(value)
            entry["path"] = _rebind_path(str(entry["path"]))
            sca_d[key] = entry
    if len(sca_d) != 28:
        raise PackageBuildError("terminal QAdd SCA_D exact-set differs")
    return sca, sca_d


def _return_allowlist(readbacks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def item(
        source_root: str,
        source_path: str,
        target_path: str,
        required: bool,
        max_bytes: int,
        missing_meaning: str,
    ) -> dict[str, Any]:
        return {
            "source_root": source_root,
            "source_path": source_path,
            "target_path": target_path,
            "required": required,
            "max_bytes": max_bytes,
            "missing_meaning": missing_meaning,
        }

    records = [
        item(
            "evidence",
            "package_preflight.json",
            "evidence/package_preflight.json",
            True,
            1 << 20,
            "package exact-set gate unavailable",
        ),
        item(
            "evidence",
            "installed_preflight.json",
            "evidence/installed_preflight.json",
            True,
            1 << 20,
            "post-install D-absence gate unavailable",
        ),
        item(
            "evidence",
            "compile_exit_status.txt",
            "evidence/compile_exit_status.txt",
            True,
            1024,
            "compile status unavailable",
        ),
        item(
            "evidence",
            "simulation_exit_status.txt",
            "evidence/simulation_exit_status.txt",
            True,
            1024,
            "simulation status unavailable",
        ),
        item(
            "evidence",
            "SERVER_RESULT_GATE.json",
            "evidence/SERVER_RESULT_GATE.json",
            True,
            2 << 20,
            "conjunctive result gate unavailable",
        ),
        item(
            "evidence",
            "PACKAGE_MANIFEST.json",
            "evidence/PACKAGE_MANIFEST.json",
            True,
            2 << 20,
            "bound package manifest unavailable",
        ),
        item(
            "run",
            "sim_results/compile_driver.log",
            "runs/compile_driver.log",
            False,
            8 << 20,
            "compile driver log unavailable",
        ),
        item(
            "run",
            "sim_results/compile.log",
            "runs/compile.log",
            False,
            8 << 20,
            "compiler log unavailable",
        ),
        item(
            "run",
            "sim_results/sim.log",
            "runs/sim.log",
            True,
            8 << 20,
            "natural completion and loader evidence unavailable",
        ),
        item(
            "run",
            "sim_results/profile.csv",
            "runs/profile.csv",
            False,
            8 << 20,
            "optional simulator profile unavailable",
        ),
    ]
    for record in readbacks:
        records.append(
            item(
                "cfg",
                str(record["runtime_path"]),
                f"readbacks/{record['runtime_path']}",
                True,
                8 << 20,
                "formal terminal QAdd readback unavailable",
            )
        )
    if len(records) != 38:
        raise PackageBuildError("return allowlist exact cardinality differs")
    return records


def run_script() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server root must be absolute" >&2; exit 2;; esac
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd -P)"
runtime="$package_root/package_tools/qlinearadd_node0007_server_runtime.py"
install_name="{INSTALL_NAME}"
cfg_rel="install/cfg_pkg/$install_name"
cfg_root="$server_root/$cfg_rel"
run_root="$server_root/run_$install_name"
evidence_root="$server_root/evidence_$install_name"
return_dir="$server_root/${{install_name}}_return"
return_zip="${{return_dir}}.zip"
return_sha="${{return_zip}}.sha256"
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
for fresh in "$cfg_root" "$run_root" "$evidence_root" "$return_dir" "$return_zip" "$return_sha"; do
  [ ! -e "$fresh" ] || {{ echo "Fresh namespace required: $fresh" >&2; exit 4; }}
done
mkdir -p "$cfg_root" "$run_root/sim_results" "$evidence_root"
python3 "$runtime" preflight --package-root "$package_root" \
  >"$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/runtime/." "$cfg_root/"
cp "$package_root/TEST_PACKAGE_MANIFEST.json" "$evidence_root/PACKAGE_MANIFEST.json"
python3 "$runtime" preflight-installed --package-root "$package_root" \
  --cfg-root "$cfg_root" >"$evidence_root/installed_preflight.json" || exit 6
compile_status=125
simulation_status=125
finalized=0
finalize() {{
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1
  trap - EXIT HUP INT TERM
  set +e
  printf '%s\\n' "$compile_status" >"$evidence_root/compile_exit_status.txt"
  printf '%s\\n' "$simulation_status" >"$evidence_root/simulation_exit_status.txt"
  python3 "$runtime" analyze --package-root "$package_root" \
    --cfg-root "$cfg_root" --evidence-root "$evidence_root" \
    --run-root "$run_root" --compile-status "$compile_status" \
    --simulation-status "$simulation_status"
  analysis_status=$?
  python3 "$runtime" collect --server-root "$server_root" \
    --install-name "$install_name" --package-root "$package_root" \
    --cfg-root "$cfg_root" --evidence-root "$evidence_root" \
    --run-root "$run_root"
  collection_status=$?
  final="$original"
  [ "$final" -ne 0 ] || [ "$analysis_status" -eq 0 ] || final="$analysis_status"
  [ "$final" -ne 0 ] || [ "$collection_status" -eq 0 ] || final="$collection_status"
  exit "$final"
}}
trap 'finalize $?' EXIT HUP INT TERM
cd "$server_root"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root" \
  >"$run_root/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
simv="$run_root/sim_results/simv"
timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" \
  -l "$run_root/sim_results/sim.log" +vcs+lic+wait \
  "+SCA_CFG=$cfg_rel/sca_cfg.json" \
  "+SCA_CFG_D=$cfg_rel/sca_cfg_D.json"
simulation_status=$?
[ "$simulation_status" -eq 0 ] || exit "$simulation_status"
exit 0
"""


def build_directory(destination: Path) -> Path:
    if sha256(ROOT / SERVER_RULE_REL) != SERVER_RULE_SHA256:
        raise PackageBuildError("server package rule SHA drifted")
    closure = validate_closure(ROOT)
    if not closure["valid"] or closure["status"] != "E2_LOCAL_COMPLETE":
        raise PackageBuildError(f"local E2 is not closed: {closure['errors']}")
    package = destination / INSTALL_NAME
    if package.exists():
        raise PackageBuildError(f"fresh package identity required: {package}")
    runtime_root = package / "workload/runtime"
    install = runtime_root / "install"
    golden_root = package / "validation/golden"
    tools_root = package / "package_tools"
    install.parent.mkdir(parents=True)
    golden_root.mkdir(parents=True)
    tools_root.mkdir()
    shutil.copytree(SOURCE_PIPELINE / "install", install)
    sca, sca_d = _sca_configs()
    write_json(runtime_root / "sca_cfg.json", sca)
    write_json(runtime_root / "sca_cfg_D.json", sca_d)

    _, _, _, bundle = load_physical_bundle(ROOT)
    zeros = np.zeros(PAD_BYTES // 4, dtype="<f4").tobytes()
    readbacks: list[dict[str, Any]] = []
    for slice_id in range(28):
        write_128bit(
            runtime_root
            / f"install/op_a_dequant/slice{slice_id:02d}/"
            "matrix_A_linearized_128bit.txt",
            bundle.read("A", slice_id)[:LOCAL_ELEMENTS],
        )
        write_128bit(
            runtime_root
            / f"install/op_b_dequant/slice{slice_id:02d}/"
            "matrix_A_linearized_128bit.txt",
            bundle.read("B", slice_id)[:LOCAL_ELEMENTS],
        )
        write_128bit(
            runtime_root
            / f"install/op_relocation_pad/slice{slice_id:02d}/"
            "matrix_A_linearized_128bit.txt",
            zeros,
        )
        relative = (
            f"install/op_tail_round/slice{slice_id:02d}/"
            "matrix_D_linearized_128bit.txt"
        )
        golden = f"validation/golden/slice{slice_id:02d}_Y_128bit.txt"
        payload = bundle.read("D", slice_id)[:LOCAL_ELEMENTS]
        write_128bit(package / golden, payload)
        readbacks.append(
            {
                "slice_id": slice_id,
                "runtime_path": relative,
                "golden_path": golden,
                "size_bytes": len(payload),
                "expected_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    shutil.copy2(
        RUNTIME_SOURCE,
        tools_root / "qlinearadd_node0007_server_runtime.py",
    )
    runner = package / "PREPARE_AND_RUN.sh"
    runner.write_text(run_script(), encoding="utf-8", newline="\n")
    os.chmod(runner, 0o755)
    (package / "README.md").write_text(
        f"# {PACKAGE_DESCRIPTION}\n\n"
        "Run exactly once from this extracted directory:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "The package uses stock RTL and one six-stage native execplan. It "
        "preloads only A, B, and a frozen noncomputational zero relocation "
        "spacer. All 28 formal terminal Y targets are absent until the "
        "simulator creates them. No server source identity is inspected.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "status": "PACKAGE_READY_NOT_RUN",
        "install_name": INSTALL_NAME,
        "node_id": "node-0007",
        "hw_op_id": "hwop-0007-00",
        "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "claim_boundary": (
            "candidate_release=false; E2 local only; no server attempt and no "
            "binding to a final Trassic2.0_RTL commit"
        ),
        "evidence_level": "E2_LOCAL_ONLY",
        "candidate_release": False,
        "compile_count": 1,
        "simulation_run_count": 1,
        "server_source_preflight_performed": False,
        "hardware_semantics_assumed_available": True,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_tb_or_observer_entries": 0,
        "numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "host_precomputed_internal_tensor": False,
        "preloaded_tensors": ["A", "B", "FROZEN_ZERO_RELOCATION_PAD"],
        "formal_readback_runtime_targets_packaged": 0,
        "supersedes_local_selfcheck_identity": SUPERSEDED_IDENTITY,
        "readback_checks": readbacks,
        "result_gate": (
            "compile0 AND simulation0 AND natural_terminal AND loader_exact "
            "AND readback_exact_set AND missing0 AND mismatch0"
        ),
        "return_collection_policy": "MANIFEST_EXPLICIT_ALLOWLIST_ONLY",
        "return_allowlist": _return_allowlist(readbacks),
        "budgets": {
            "upload_zip_max_bytes": 64 << 20,
            "upload_extracted_max_bytes": 512 << 20,
            "return_zip_max_bytes": 64 << 20,
            "return_extracted_max_bytes": 256 << 20,
            "single_text_max_bytes": 8 << 20,
            "formal_readback_logical_bytes": LOCAL_ELEMENTS * 28,
            "formal_readback_text_bytes": sum(
                (package / item["golden_path"]).stat().st_size
                for item in readbacks
            ),
            "formal_readback_sca_d_exact_count": 28,
            "large_node_exception_reason": (
                "28 exact SCA_D terminal outputs plus the independent golden "
                "set for a [16,256,56,56] QLinearAdd node"
            ),
        },
        "provenance": {
            "closure_contract": {
                "path": CONTRACT_REL.as_posix(),
                "sha256": sha256(ROOT / CONTRACT_REL),
            },
            "execplan_bundle_manifest": closure["provenance"][
                "execplan_bundle_manifest"
            ],
            "server_package_rule": {
                "path": SERVER_RULE_REL.as_posix(),
                "sha256": SERVER_RULE_SHA256,
            },
            "generator": GENERATOR_REL,
        },
    }
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)
    preflight(package)
    return package


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (2026, 7, 29, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def repeated_build(package: Path, output_zip: Path) -> dict[str, Any]:
    deterministic_zip(package, output_zip)
    first_records = file_records(package, exclude_manifest=False)
    first_sha = sha256(output_zip)
    with tempfile.TemporaryDirectory(prefix="qadd-node0007-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeat_package, repeat_zip)
        if first_records != file_records(
            repeat_package, exclude_manifest=False
        ):
            raise PackageBuildError("repeated package trees differ")
        if first_sha != sha256(repeat_zip):
            raise PackageBuildError("repeated deterministic ZIPs differ")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def _publish_receipts(receipt: dict[str, Any]) -> None:
    contract = load_json(ROOT / CONTRACT_REL)
    contract["package_release"] = {
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "zip": receipt["zip"],
        "zip_sha256": receipt["zip_sha256"],
        "sidecar": receipt["sidecar"],
    }
    write_json(ROOT / CONTRACT_REL, contract)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        package = build_directory(output_root)
        repeated = repeated_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
        )
        receipt = {
            "schema": "qlinearadd-node0007-package-validation-v1",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": zip_path.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "file_count": len(file_records(package, exclude_manifest=False)),
            "formal_readback_count": 28,
            "preloaded_runtime_readback_target_count": 0,
            "result_gate_fail_closed": True,
            "return_allowlist_only": True,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
            "server_source_inspected": False,
            "repeated_build": repeated,
        }
        write_json(validation, receipt)
        _publish_receipts(receipt)
    except Exception as error:
        print(f"package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
