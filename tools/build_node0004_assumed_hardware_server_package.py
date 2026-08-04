from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_native_package import (  # noqa: E402
    ACCUMULATOR_BYTES,
)
from resnet50_pipeline.node0004_assumed_hardware import (  # noqa: E402
    HIGH_RING_OWNERS,
    LANES,
    SHARD_COUNT,
    SPATIAL,
    WAVE_SAMPLES,
    _wave_active_slices,
    load_fresh_physical_bundle,
)
from resnet50_pipeline.requant_native_package import requant_parameters  # noqa: E402
from tools.node0004_assumed_hardware_server_runtime import (  # noqa: E402
    package_records,
    preflight,
)


INSTALL_NAME = "r5_node0004_hw_v1"
LOCAL_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-node0004-assumed-hardware-v1"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
OUTPUT_ZIP = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
OUTPUT_SHA = OUTPUT_ROOT / f"{INSTALL_NAME}.zip.sha256"
VALIDATION = OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
RUNTIME_SOURCE = ROOT / "tools/node0004_assumed_hardware_server_runtime.py"


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
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_128bit(path: Path, payload: bytes) -> None:
    if len(payload) % 16:
        raise PackageBuildError(f"unaligned payload: {path}")
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


def prefix_sca(path: Path, run_id: str) -> None:
    value = load_json(path)
    prefix = f"install/cfg_pkg/{INSTALL_NAME}/runs/{run_id}/"
    for item in value.values():
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            old = str(item["path"])
            if old.startswith("/") or ".." in Path(old).parts:
                raise PackageBuildError(f"unsafe SCA path: {old}")
            item["path"] = prefix + old.replace("\\", "/")
    write_json(path, value)


def add_readback(
    package: Path,
    run_root: Path,
    run_id: str,
    relative: str,
    payload: bytes,
    checks: list[dict[str, Any]],
) -> None:
    runtime_path = Path("workload/runtime/runs") / run_id / relative
    golden_path = Path("validation/golden/runs") / run_id / relative
    write_128bit(package / runtime_path, payload)
    write_128bit(package / golden_path, payload)
    checks.append(
        {
            "run_id": run_id,
            "runtime_path": (
                Path("runs") / run_id / relative
            ).as_posix(),
            "golden_path": golden_path.as_posix(),
            "size_bytes": len(payload),
        }
    )


def copy_pipeline(source: Path, run_root: Path, run_id: str) -> Path:
    if not (source.parent / "bundle_manifest.json").is_file():
        raise PackageBuildError(f"execplan evidence incomplete: {source.parent}")
    destination = run_root / run_id
    destination.mkdir(parents=True)
    shutil.copytree(source / "install", destination / "install")
    shutil.copy2(source / "sca_cfg.json", destination / "sca_cfg.json")
    shutil.copy2(source / "sca_cfg_D.json", destination / "sca_cfg_D.json")
    prefix_sca(destination / "sca_cfg.json", run_id)
    prefix_sca(destination / "sca_cfg_D.json", run_id)
    return destination


def build_directory(destination: Path) -> Path:
    package = destination / INSTALL_NAME
    if package.exists():
        raise PackageBuildError(f"fresh package path required: {package}")
    run_root = package / "workload/runtime/runs"
    validation = package / "validation"
    tools_root = package / "package_tools"
    run_root.mkdir(parents=True)
    validation.mkdir()
    tools_root.mkdir()

    _, bundle, _, _ = load_fresh_physical_bundle(ROOT)
    multiplier, zero_point, typed_identity = requant_parameters(ROOT)
    if zero_point != 0:
        raise PackageBuildError("node0004 output zero point differs")
    checks: list[dict[str, Any]] = []
    tail_materialization: list[dict[str, Any]] = []

    transport = load_json(LOCAL_ROOT / "conv_transport/manifest.json")
    transport_by_wave_slice = {
        (int(record["wave_index"]), int(record["slice_id"])): record
        for record in transport["records"]
    }
    for wave in range(3):
        run_id = f"c{wave}"
        destination_run = copy_pipeline(
            LOCAL_ROOT
            / "execplan_conv"
            / f"wave-{wave}"
            / "pipeline_output",
            run_root,
            run_id,
        )
        for slice_id in range((28, 28, 8)[wave]):
            record = transport_by_wave_slice[(wave, slice_id)]
            for tensor in ("A", "B", "C"):
                source = LOCAL_ROOT / "conv_transport" / record["matrices"][tensor]["path"]
                target = (
                    destination_run
                    / "install"
                    / f"op_w{wave}"
                    / f"slice{slice_id:02d}"
                    / f"matrix_{tensor}_linearized_128bit.txt"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            source_d = LOCAL_ROOT / "conv_transport" / record["matrices"]["D"]["path"]
            add_readback(
                package,
                run_root,
                run_id,
                (
                    f"install/op_w{wave}/slice{slice_id:02d}/"
                    "matrix_D_linearized_128bit.txt"
                ),
                source_d.read_bytes()
                if source_d.suffix == ".bin"
                else bundle.read("P", slice_id)[
                    wave * ACCUMULATOR_BYTES : (wave + 1) * ACCUMULATOR_BYTES
                ],
                checks,
            )

    for wave in range(3):
        for shard in range(SHARD_COUNT):
            run_id = f"t{wave}{shard:02d}"
            destination_run = copy_pipeline(
                LOCAL_ROOT
                / "execplan_tail"
                / f"wave-{wave}-shard-{shard:02d}"
                / "pipeline_output",
                run_root,
                run_id,
            )
            channels = np.arange(shard * LANES, (shard + 1) * LANES)
            lane_half = shard % 2
            active_slices = _wave_active_slices(wave, shard)
            for group_id, slice_id in enumerate(active_slices):
                p_slot = bundle.read("P", slice_id)[
                    wave * ACCUMULATOR_BYTES : (wave + 1) * ACCUMULATOR_BYTES
                ]
                p_hwc16 = np.frombuffer(p_slot, dtype="<i4").reshape(SPATIAL, 16)
                accum = p_hwc16[:, lane_half * LANES : (lane_half + 1) * LANES]
                scaled = np.multiply(
                    accum.astype(np.float32),
                    multiplier[channels][None, :],
                    dtype=np.float32,
                )
                rounded = np.rint(scaled).clip(0, 255).astype(np.uint8)
                mul_op = f"op_mul_w{wave}_s{shard:02d}"
                round_op = f"op_round_w{wave}_s{shard:02d}"
                mul_a = (
                    f"install/{mul_op}/slice{slice_id:02d}/"
                    "matrix_A_linearized_128bit.txt"
                )
                round_a = (
                    f"install/{round_op}/slice{slice_id:02d}/"
                    "matrix_A_linearized_128bit.txt"
                )
                write_128bit(destination_run / round_a, bytes(100352))
                add_readback(
                    package,
                    run_root,
                    run_id,
                    (
                        f"install/{mul_op}/slice{slice_id:02d}/"
                        "matrix_D_linearized_128bit.txt"
                    ),
                    scaled.astype("<f4", copy=False).tobytes(),
                    checks,
                )
                add_readback(
                    package,
                    run_root,
                    run_id,
                    (
                        f"install/{round_op}/slice{slice_id:02d}/"
                        "matrix_D_linearized_128bit.txt"
                    ),
                    rounded.tobytes(),
                    checks,
                )
                tail_materialization.append(
                    {
                        "wave": wave,
                        "shard": shard,
                        "group_id": group_id,
                        "slice_id": slice_id,
                        "lane_half": lane_half,
                        "conv_readback": (
                            f"runs/c{wave}/install/op_w{wave}/"
                            f"slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
                        ),
                        "tail_input": (
                            f"runs/{run_id}/{mul_a}"
                        ),
                    }
                )

    shutil.copy2(
        RUNTIME_SOURCE,
        tools_root / "node0004_assumed_hardware_server_runtime.py",
    )
    runner = package / "PREPARE_AND_RUN.sh"
    runner.write_text(run_script(), encoding="utf-8", newline="\n")
    os.chmod(runner, 0o755)
    (package / "README.md").write_text(
        "# ResNet50 node0004 assumed-hardware test\n\n"
        "Run exactly:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/server_root\n"
        "```\n\n"
        "This package assumes the hardware team fixes are present. It performs "
        "three Conv waves, mechanically relayouts only the hardware-produced "
        "INT32 accumulator, then performs 24 two-stage hardware requant runs. "
        "It does not inspect or modify server RTL/TB/observer files.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest: dict[str, Any] = {
        "schema": "resnet50-node0004-assumed-hardware-server-package-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "install_name": INSTALL_NAME,
        "server_source_identity_bound": False,
        "server_source_preflight_performed": False,
        "hardware_semantics_assumed_available": True,
        "compile_count": 1,
        "simulation_run_count": 27,
        "conv_run_ids": [f"c{wave}" for wave in range(3)],
        "tail_run_ids": [
            f"t{wave}{shard:02d}"
            for wave in range(3)
            for shard in range(8)
        ],
        "typed_identity": typed_identity,
        "tail_materialization": tail_materialization,
        "readback_checks": checks,
        "files": package_records(package),
    }
    write_json(package / "package_manifest.json", manifest)
    preflight(package)
    return package


def run_script() -> str:
    tail_ids = " ".join(
        f"t{wave}{shard:02d}"
        for wave in range(3)
        for shard in range(8)
    )
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd -P)"
runtime="${{package_root}}/package_tools/node0004_assumed_hardware_server_runtime.py"
install_name="{INSTALL_NAME}"
cfg_root="${{server_root}}/install/cfg_pkg/${{install_name}}"
run_root="${{server_root}}/run_${{install_name}}"
evidence_root="${{server_root}}/evidence_${{install_name}}"
return_dir="${{server_root}}/${{install_name}}_return"
return_zip="${{return_dir}}.zip"
return_sha="${{return_zip}}.sha256"
for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
for fresh in "$cfg_root" "$run_root" "$evidence_root" "$return_dir" "$return_zip" "$return_sha"; do
  [ ! -e "$fresh" ] || {{ echo "Fresh namespace required: $fresh" >&2; exit 4; }}
done
mkdir -p "$cfg_root" "$run_root/compile/sim_results" "$evidence_root"
python3 "$runtime" preflight --package-root "$package_root" \
  > "$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/runtime/." "$cfg_root/"
compile_status=125
run_status=125
finalized=0
finalize() {{
  original="$1"; [ "$finalized" -eq 0 ] || exit "$original"; finalized=1
  trap - EXIT INT TERM HUP
  set +e
  printf '%s\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"
  printf '%s\n' "$run_status" > "$evidence_root/run_exit_status.txt"
  python3 "$runtime" analyze --package-root "$package_root" \
    --cfg-root "$cfg_root" --evidence-root "$evidence_root"
  analysis=$?
  python3 "$runtime" collect --server-root "$server_root" \
    --install-name "$install_name" --evidence-root "$evidence_root" \
    --run-root "$run_root" --cfg-root "$cfg_root"
  collection=$?
  final="$original"
  [ "$final" -ne 0 ] || [ "$analysis" -eq 0 ] || final="$analysis"
  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
  exit "$final"
}}
trap 'finalize $?' EXIT
cd "$server_root"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 \
  TB_DUMP_FSDB=0 RUN_DIR="$run_root/compile" \
  > "$run_root/compile/sim_results/compile_driver.log" 2>&1
compile_status=$?
[ "$compile_status" -eq 0 ] || exit "$compile_status"
simv="$run_root/compile/sim_results/simv"
run_one() {{
  id="$1"; mkdir -p "$run_root/$id"
  timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" \
    -l "$run_root/$id/sim.log" +vcs+lic+wait \
    "+SCA_CFG=$cfg_root/runs/$id/sca_cfg.json" \
    "+SCA_CFG_D=$cfg_root/runs/$id/sca_cfg_D.json"
}}
for id in c0 c1 c2; do
  run_one "$id" || {{ run_status=$?; exit "$run_status"; }}
done
python3 "$runtime" materialize-tail --package-root "$package_root" \
  --cfg-root "$cfg_root" --output "$evidence_root/tail_materialization.json" \
  || {{ run_status=$?; exit "$run_status"; }}
for id in {tail_ids}; do
  run_one "$id" || {{ run_status=$?; exit "$run_status"; }}
done
run_status=0
exit 0
"""


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (2026, 7, 29, 0, 0, 0))
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation_path):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        package = build_directory(output_root)
        deterministic_zip(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii")
        receipt = {
            "schema": "node0004-assumed-hardware-package-validation-v1",
            "status": "PACKAGE_READY_NOT_RUN",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "package_file_count": len(package_records(package, exclude_manifest=False)),
            "server_action": False,
        }
        write_json(validation_path, receipt)
    except Exception as error:
        print(f"package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
