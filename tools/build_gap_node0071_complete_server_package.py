#!/usr/bin/env python3
"""Build the complete node0071 GAP PACKAGE_READY_NOT_RUN bundle."""

from __future__ import annotations

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

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_complete_config_only import (  # noqa: E402
    ARTIFACT_ROOT,
    CONFIG_ROOT,
    CONTRACT,
    FINAL_BASE,
    FINAL_BYTES,
    SCALED_BASE,
    SCALED_BYTES,
    SLICE_COUNT,
    SUM_BASE,
    SUM_BYTES,
    W3_OUTPUT,
    validate_local_e2,
)
from resnet50_pipeline.gap_sum_config_only import W3_INPUT, W3_SUM  # noqa: E402
from resnet50_pipeline.hashing import sha256_file  # noqa: E402
from tools.gap_node0071_complete_server_runtime import (  # noqa: E402
    file_records,
    preflight,
)


INSTALL_NAME = "r5_node0071_gap_hw_v1"
OUTPUT_ROOT = (
    Path("artifacts/operator_config_validation/r5-server-test-packages")
    / INSTALL_NAME
)
EXEC_BASE = 0x1A0000
SLICE_SHIFT = 25


class PackageBuildError(ValueError):
    pass


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
                int.from_bytes(payload[index : index + 16], "little"), "0128b"
            )
            for index in range(0, len(payload), 16)
        )
        + "\n",
        encoding="ascii",
        newline="\n",
    )


def line_count(path: Path) -> int:
    return sum(bool(line.strip()) for line in path.read_text(encoding="ascii").splitlines())


def run_script() -> str:
    return f"""#!/usr/bin/env bash
set -eu
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "NDP_copy path must be absolute" >&2; exit 2;; esac

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
server_root="$(cd "$1" && pwd)"
install_name="{INSTALL_NAME}"
cfg_root="${{server_root}}/install/cfg_pkg/${{install_name}}"
run_root="${{server_root}}/run_${{install_name}}"
evidence_root="${{server_root}}/evidence_${{install_name}}"
runtime="${{package_root}}/package_tools/gap_node0071_complete_server_runtime.py"

for target in "$cfg_root" "$run_root" "$evidence_root" \
  "${{server_root}}/${{install_name}}_return" \
  "${{server_root}}/${{install_name}}_return.zip" \
  "${{server_root}}/${{install_name}}_return.zip.sha256"; do
  if [ -e "$target" ]; then
    echo "Fresh target required: $target" >&2
    exit 3
  fi
done

python3 "$runtime" preflight --package-root "$package_root"
mkdir -p "${{server_root}}/install/cfg_pkg"
cp -a "${{package_root}}/workload" "$cfg_root"
mkdir "$evidence_root"
mkdir -p "${{cfg_root}}/readback"
cp "${{package_root}}/TEST_PACKAGE_MANIFEST.json" \
  "${{evidence_root}}/PACKAGE_MANIFEST.json"
python3 "$runtime" preflight-installed --package-root "$package_root" \
  --cfg-root "$cfg_root" >"${{evidence_root}}/installed_preflight.json"
printf '%s\\n' \
  "make -C <user-root> -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=<unique-run>; <unique-run>/sim_results/simv +SCA_CFG=install/cfg_pkg/${{install_name}}/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/${{install_name}}/sca_cfg_D.json" \
  >"${{evidence_root}}/server_command.txt"

compile_status=125
simulation_status=125
finalized=0
finalize() {{
  shell_status="$1"
  if [ "$finalized" -eq 1 ]; then return; fi
  finalized=1
  set +e
  runner_status="$shell_status"
  if [ "$compile_status" -ne 0 ] && [ "$compile_status" -ne 125 ]; then
    runner_status="$compile_status"
  elif [ "$simulation_status" -ne 0 ] && [ "$simulation_status" -ne 125 ]; then
    runner_status="$simulation_status"
  fi
  printf '%s\\n' "$compile_status" >"${{evidence_root}}/compile_exit_status.txt"
  printf '%s\\n' "$simulation_status" >"${{evidence_root}}/simulation_exit_status.txt"
  printf '%s\\n' "$runner_status" >"${{evidence_root}}/runner_exit_status.txt"
  python3 "$runtime" analyze --package-root "$package_root" \
    --cfg-root "$cfg_root" --evidence-root "$evidence_root" \
    --run-root "$run_root" --compile-status "$compile_status" \
    --simulation-status "$simulation_status"
  analysis_status=$?
  python3 "$runtime" collect --server-root "$server_root" \
    --install-name "$install_name" --evidence-root "$evidence_root" \
    --run-root "$run_root" --cfg-root "$cfg_root"
  collection_status=$?
  if [ "$compile_status" -ne 0 ]; then exit "$compile_status"; fi
  if [ "$simulation_status" -ne 0 ]; then exit "$simulation_status"; fi
  if [ "$analysis_status" -ne 0 ]; then exit "$analysis_status"; fi
  exit "$collection_status"
}}
trap 'finalize $?' EXIT HUP INT TERM

set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -C "$server_root" -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_root"
compile_status=$?

if [ "$compile_status" -eq 0 ]; then
  timeout --foreground --signal=TERM --kill-after=30s 12h \
    "$run_root/sim_results/simv" \
    -l "$run_root/sim_results/sim.log" +vcs+lic+wait +sim_time=100ms \
    +BITSTREAM=install/bitstream.txt \
    +SCA_CFG="install/cfg_pkg/${{install_name}}/sca_cfg.json" \
    +SCA_CFG_D="install/cfg_pkg/${{install_name}}/sca_cfg_D.json"
  simulation_status=$?
fi
set -e

finalize 0
"""


def deterministic_zip(
    package: Path, output: Path, *, archive_root: str | None = None
) -> None:
    root_name = archive_root or package.name
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{root_name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def build_directory(destination: Path) -> Path:
    local = validate_local_e2(ROOT)
    if not local["valid"] or not local["complete_gap_target"]:
        raise PackageBuildError("complete local E2 gate is not green")
    if destination.exists():
        raise PackageBuildError(f"fresh package identity required: {destination}")
    destination.mkdir(parents=True)
    workload = destination / "workload"
    artifact = ROOT / ARTIFACT_ROOT
    prefix = f"install/cfg_pkg/{INSTALL_NAME}"

    (destination / "package_tools").mkdir()
    shutil.copy2(
        ROOT / "tools/gap_node0071_complete_server_runtime.py",
        destination / "package_tools/gap_node0071_complete_server_runtime.py",
    )
    (destination / "PREPARE_AND_RUN.sh").write_text(
        run_script(), encoding="utf-8", newline="\n"
    )
    (destination / "README.md").write_text(
        "# ResNet50 node0071 complete GAP hardware-assumption package\n\n"
        "Status: `PACKAGE_READY_NOT_RUN`. Run exactly:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "The package performs one compile and one eight-stage simulation. It "
        "contains no RTL, does no host replay of sum/scaled/final tensors, and "
        "returns INT32 sum, FP32 scaled scratch and UINT8 final readbacks. "
        "It is a CONFIG_ONLY_CORRECTNESS_BASELINE, not E4/E5 or production.\n",
        encoding="utf-8",
        newline="\n",
    )

    shutil.copytree(artifact / "install", workload / "install")
    for name in (
        "validation_report.json",
        "sum_reuse_binding.json",
        "materialized_roundtrip_report.json",
        "config_bound_simulator_report.json",
    ):
        target = destination / "provenance" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact / name, target)
    shutil.copy2(ROOT / CONTRACT, destination / "provenance/machine_contract.json")
    shutil.copytree(ROOT / CONFIG_ROOT, destination / "provenance/tail_configs")
    shutil.copytree(
        artifact / "mapping/run-a", destination / "provenance/tail_mapping"
    )

    source = np.load(ROOT / W3_INPUT, allow_pickle=False)
    sum_value = np.load(ROOT / W3_SUM, allow_pickle=False).reshape(16, 2048)
    output = np.load(ROOT / W3_OUTPUT, allow_pickle=False).reshape(16, 2048)
    physical = (
        source.reshape(16, 256, 8, 49)
        .transpose(0, 1, 3, 2)
        .copy()
    )
    scaled = np.multiply(
        sum_value.astype(np.float32),
        np.float32(0.0661861002445221),
        dtype=np.float32,
    )

    sca: dict[str, Any] = {
        "Exec_Base": f"0x{EXEC_BASE:08X}",
        "Exec_Length": line_count(workload / "install/execplan.txt"),
        "Repeat_Num": 8,
        "ExecutionPlan": {
            "base_addr": f"0x{EXEC_BASE:08X}",
            "path": f"{prefix}/install/execplan.txt",
        },
    }
    config_bases = [
        *(0x100000 + index * 0x10000 for index in range(6)),
        0x160000,
        0x170000,
    ]
    bitstreams = sorted((workload / "install/cfg_pkg").glob("*.bin"))
    ordered_names = [
        *(f"gap_node0071_sum_s{index}_128b.bin" for index in range(1, 7)),
        "gap_node0071_tail_mul_128b.bin",
        "gap_node0071_tail_round_128b.bin",
    ]
    if [path.name for path in bitstreams] != sorted(ordered_names):
        raise PackageBuildError("eight installed bitstream names differ")
    for index, (name, base) in enumerate(
        zip(ordered_names, config_bases, strict=True), start=1
    ):
        sca[f"stage{index}_config"] = {
            "base_addr": f"0x{base:08X}",
            "path": f"{prefix}/install/cfg_pkg/{name}",
        }

    sca_d: dict[str, Any] = {}
    readback_checks = []
    for slice_id in range(SLICE_COUNT):
        input_rel = Path(f"input/slice{slice_id:02d}/matrix_A_128bit.txt")
        write_128bit(workload / input_rel, physical[slice_id].tobytes())
        sca[f"node0071_input_slice{slice_id}"] = {
            "base_addr": f"0x{slice_id << SLICE_SHIFT:08X}",
            "path": f"{prefix}/{input_rel.as_posix()}",
        }
        for role, base, payload, size in (
            (
                "sum_int32",
                SUM_BASE,
                sum_value[slice_id].astype("<i4", copy=False).tobytes(),
                SUM_BYTES,
            ),
            (
                "scaled_fp32",
                SCALED_BASE,
                scaled[slice_id].astype("<f4", copy=False).tobytes(),
                SCALED_BYTES,
            ),
            (
                "final_uint8",
                FINAL_BASE,
                output[slice_id].tobytes(),
                FINAL_BYTES,
            ),
        ):
            golden_rel = Path(
                f"golden/{role}/slice{slice_id:02d}/matrix_D_128bit.txt"
            )
            runtime_rel = Path(
                f"readback/{role}/slice{slice_id:02d}/matrix_D_128bit.txt"
            )
            write_128bit(workload / golden_rel, payload)
            key = f"{role}_slice{slice_id}"
            sca_d[key] = {
                "base_addr": f"0x{(slice_id << SLICE_SHIFT) | base:08X}",
                "path": f"{prefix}/{runtime_rel.as_posix()}",
                "length": size // 16,
            }
            readback_checks.append(
                {
                    "role": role,
                    "slice": slice_id,
                    "runtime_path": runtime_rel.as_posix(),
                    "golden_path": f"workload/{golden_rel.as_posix()}",
                    "size_bytes": size,
                }
            )
    write_json(workload / "sca_cfg.json", sca)
    write_json(workload / "sca_cfg_D.json", sca_d)

    manifest = {
        "schema": "gap-node0071-complete-server-package-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "install_name": INSTALL_NAME,
        "package_name": INSTALL_NAME,
        "run_name": f"run_{INSTALL_NAME}",
        "return_name": f"{INSTALL_NAME}_return",
        "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "evidence_level": "E2_LOCAL_COMPLETE_NODE",
        "complete_gap_target_local_e2": True,
        "compile_count": 1,
        "simulation_run_count": 1,
        "repeat_num": 8,
        "readback_checks": readback_checks,
        "server_source_preflight_performed": False,
        "server_source_identity_bound": False,
        "server_run_performed": False,
        "lease_acquired": False,
        "uploaded": False,
        "functional_rtl_modified": False,
        "transout_consumed": False,
        "repair_v9_consumed": False,
        "host_precomputed_internal_tensor_replay": False,
        "input_materialization": (
            "typed node0070 uint8 producer bytes reshaped C8HW8 only; "
            "all sum/scaled/final golden tensors are compare-only"
        ),
        "sum_reuse": {
            "class": "IMMUTABLE_FULL_BINDING",
            "numeric_analysis_repeated": False,
            "mapping_rebuilt": False,
        },
        "production_blockers": [
            "final Trassic2.0_RTL commit not bound",
            "server dynamic execution not performed",
            "E4/E5 absent",
            "performance/resource closure absent",
        ],
        "generation_provenance": {
            "tool": "tools/build_gap_node0071_complete_server_package.py",
            "cwd": ".",
            "command": (
                "bundled-python "
                "tools/build_gap_node0071_complete_server_package.py"
            ),
            "exit_code": 0,
            "planner_to_package_chain": [
                "final address-bound tail JSON",
                "isolated exact mapping x2",
                "128-bit bitstream",
                "eight-stage execplan",
                "SCA/SCA_D",
            ],
            "local_contract_sha256": sha256_file(ROOT / CONTRACT),
        },
        "forbidden_package_content": [
            "functional RTL",
            "server source identity snapshot",
            "runtime readback target",
            "waveform",
            "build tree",
            "nested archive",
        ],
        "budgets": {
            "package_zip_max_bytes": 16 * 1024 * 1024,
            "return_zip_max_bytes": 16 * 1024 * 1024,
            "return_extracted_max_bytes": 32 * 1024 * 1024,
            "single_text_max_bytes": 8 * 1024 * 1024,
        },
        "return_allowlist": [],
        "files": {},
    }
    manifest["return_allowlist"] = [
        {
            "source_root": "evidence",
            "source_path": source,
            "target_path": f"evidence/{source}",
            "required": required,
            "max_bytes": 8 * 1024 * 1024,
            "missing_meaning": meaning,
        }
        for source, required, meaning in (
            ("PACKAGE_MANIFEST.json", True, "package identity unavailable"),
            ("installed_preflight.json", True, "post-install preflight unavailable"),
            ("compile_exit_status.txt", True, "compile status unavailable"),
            ("simulation_exit_status.txt", True, "simulation status unavailable"),
            ("runner_exit_status.txt", True, "runner status unavailable"),
            ("server_command.txt", True, "actual argv receipt unavailable"),
            ("SERVER_RESULT_GATE.json", True, "result conjunction unavailable"),
        )
    ] + [
        {
            "source_root": "run",
            "source_path": source,
            "target_path": f"logs/{Path(source).name}",
            "required": required,
            "max_bytes": 8 * 1024 * 1024,
            "missing_meaning": meaning,
        }
        for source, required, meaning in (
            ("sim_results/compile.log", False, "compile did not emit a bounded log"),
            ("sim_results/sim.log", False, "simulation did not start or emit a log"),
        )
    ] + [
        {
            "source_root": "cfg",
            "source_path": source,
            "target_path": f"config/{source}",
            "required": True,
            "max_bytes": 1024 * 1024,
            "missing_meaning": "installed SCA identity unavailable",
        }
        for source in ("sca_cfg.json", "sca_cfg_D.json")
    ] + [
        {
            "source_root": "cfg",
            "source_path": record["runtime_path"],
            "target_path": f"readback/{record['role']}/slice{record['slice']:02d}.txt",
            "required": True,
            "max_bytes": record["size_bytes"] * 9,
            "missing_meaning": "formal DUT readback absent",
        }
        for record in readback_checks
    ]
    manifest["files"] = file_records(destination)
    write_json(destination / "TEST_PACKAGE_MANIFEST.json", manifest)
    checked = preflight(destination)
    if not checked["valid"]:
        raise PackageBuildError("package preflight failed")
    return destination


def main() -> int:
    destination = ROOT / OUTPUT_ROOT
    zip_path = destination.with_suffix(".zip")
    sha_path = Path(str(zip_path) + ".sha256")
    validation_path = destination.with_suffix(".validation.json")
    parent = destination.parent
    build_a = parent / f"{INSTALL_NAME}__determinism_a"
    build_b = parent / f"{INSTALL_NAME}__determinism_b"
    zip_a = parent / f"{INSTALL_NAME}__determinism_a.zip"
    zip_b = parent / f"{INSTALL_NAME}__determinism_b.zip"
    for target in (
        destination,
        zip_path,
        sha_path,
        validation_path,
        build_a,
        build_b,
        zip_a,
        zip_b,
    ):
        if target.exists():
            print(f"fresh package target required: {target}", file=sys.stderr)
            return 1
    try:
        build_directory(build_a)
        build_directory(build_b)
        if file_records(build_a, exclude_manifest=False) != file_records(
            build_b, exclude_manifest=False
        ):
            raise PackageBuildError("independent package trees differ")
        deterministic_zip(build_a, zip_a, archive_root=INSTALL_NAME)
        deterministic_zip(build_b, zip_b, archive_root=INSTALL_NAME)
        hash_a = hashlib.sha256(zip_a.read_bytes()).hexdigest()
        hash_b = hashlib.sha256(zip_b.read_bytes()).hexdigest()
        if zip_a.read_bytes() != zip_b.read_bytes():
            raise PackageBuildError("independent deterministic ZIPs differ")
        shutil.copytree(build_a, destination)
        deterministic_zip(destination, zip_path)
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if digest != hash_a or digest != hash_b:
            raise PackageBuildError("final ZIP differs from isolated rebuilds")
        if zip_path.stat().st_size > 16 * 1024 * 1024:
            raise PackageBuildError("package ZIP exceeds declared budget")
        sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii")
        with zipfile.ZipFile(zip_path, "r") as archive:
            names = archive.namelist()
            if any(
                ".." in Path(name).parts
                or not name.startswith(f"{INSTALL_NAME}/")
                for name in names
            ):
                raise PackageBuildError("ZIP entry path audit failed")
        with tempfile.TemporaryDirectory(
            prefix=f"{INSTALL_NAME}_bootstrap_", dir=parent
        ) as temporary:
            extracted_root = Path(temporary)
            with zipfile.ZipFile(zip_path, "r") as archive:
                archive.extractall(extracted_root)
            extracted = extracted_root / INSTALL_NAME
            before = file_records(extracted, exclude_manifest=False)
            environment = dict(os.environ)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            process = subprocess.run(
                [
                    sys.executable,
                    str(
                        extracted
                        / "package_tools/gap_node0071_complete_server_runtime.py"
                    ),
                    "preflight",
                    "--package-root",
                    str(extracted),
                ],
                cwd=extracted,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            after = file_records(extracted, exclude_manifest=False)
            if process.returncode != 0 or before != after:
                raise PackageBuildError(
                    "fresh-extract runtime bootstrap immutability failed: "
                    f"{process.stdout} {process.stderr}"
                )
        report = {
            "schema": "gap-node0071-complete-package-validation-v1",
            "valid": True,
            "status": "PACKAGE_READY_NOT_RUN",
            "install_name": INSTALL_NAME,
            "directory": OUTPUT_ROOT.as_posix(),
            "zip": zip_path.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "package_preflight": preflight(destination),
            "independent_builds": {
                "count": 2,
                "tree_identical": True,
                "zip_byte_identical": True,
                "zip_sha256_a": hash_a,
                "zip_sha256_b": hash_b,
            },
            "fresh_extract_bootstrap": {
                "runtime_entry_invoked": True,
                "python_dont_write_bytecode": True,
                "tree_unchanged": True,
            },
            "server_run_performed": False,
        }
        write_json(validation_path, report)
        shutil.rmtree(build_a)
        shutil.rmtree(build_b)
        zip_a.unlink()
        zip_b.unlink()
    except Exception as error:
        print(f"node0071 GAP package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
