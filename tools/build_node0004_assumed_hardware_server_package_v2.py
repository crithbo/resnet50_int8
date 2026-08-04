from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_assumed_hardware_server_package as base  # noqa: E402
from tools.node0004_assumed_hardware_server_runtime_v2 import (  # noqa: E402
    package_records,
    preflight,
)


INSTALL_NAME = "r5_node0004_hw_v2_failclosed"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
RUNTIME_SOURCE = (
    ROOT / "tools/node0004_assumed_hardware_server_runtime_v2.py"
)


class PackageBuildV2Error(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def add_readback_without_runtime_preload(
    package: Path,
    run_root: Path,
    run_id: str,
    relative: str,
    payload: bytes,
    checks: list[dict[str, Any]],
) -> None:
    del run_root
    runtime_path = Path("workload/runtime/runs") / run_id / relative
    golden_path = Path("validation/golden/runs") / run_id / relative
    runtime_target = package / runtime_path
    if runtime_target.exists():
        runtime_target.unlink()
    runtime_target.parent.mkdir(parents=True, exist_ok=True)
    base.write_128bit(package / golden_path, payload)
    checks.append(
        {
            "run_id": run_id,
            "runtime_path": (Path("runs") / run_id / relative).as_posix(),
            "golden_path": golden_path.as_posix(),
            "size_bytes": len(payload),
            "runtime_target_preloaded": False,
        }
    )


def run_script_v2() -> str:
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
python3 "$runtime" verify-install --package-root "$package_root" \
  --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || exit 6
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
    --run-root "$run_root" --cfg-root "$cfg_root" \
    --package-root "$package_root"
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


def _patched_build(destination: Path) -> Path:
    old_values = {
        "INSTALL_NAME": base.INSTALL_NAME,
        "RUNTIME_SOURCE": base.RUNTIME_SOURCE,
        "add_readback": base.add_readback,
        "run_script": base.run_script,
    }
    try:
        base.INSTALL_NAME = INSTALL_NAME
        base.RUNTIME_SOURCE = RUNTIME_SOURCE
        base.add_readback = add_readback_without_runtime_preload
        base.run_script = run_script_v2
        package = base.build_directory(destination)
    finally:
        for name, value in old_values.items():
            setattr(base, name, value)

    manifest_path = package / "package_manifest.json"
    manifest = base.load_json(manifest_path)
    manifest.update(
        {
            "schema": "resnet50-node0004-assumed-hardware-server-package-v2",
            "install_name": INSTALL_NAME,
            "supersedes_package_sha256": (
                "335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989"
            ),
            "repair_reason": [
                "v1 shipped all 320 runtime D targets pre-populated",
                "v1 result gate ignored compile/run exit status",
                "v1 return collector recursively copied non-allowlisted build files",
            ],
            "result_gate_requires_compile_and_run_zero": True,
            "preloaded_runtime_readback_target_count": 0,
            "return_collection_policy": "EXPLICIT_ALLOWLIST_ONLY",
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
        }
    )
    manifest["files"] = package_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    return package


def _validate_repeated_build(
    package: Path, output_zip: Path
) -> dict[str, Any]:
    base.deterministic_zip(package, output_zip)
    first_records = package_records(package, exclude_manifest=False)
    first_zip_sha = sha256(output_zip)
    with tempfile.TemporaryDirectory(prefix="node0004-v2-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package = _patched_build(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        second_records = package_records(
            repeat_package, exclude_manifest=False
        )
        second_zip_sha = sha256(repeat_zip)
        if first_records != second_records:
            raise PackageBuildV2Error("repeated package trees differ")
        if first_zip_sha != second_zip_sha:
            raise PackageBuildV2Error("repeated deterministic ZIPs differ")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_zip_sha,
    }


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
        package = _patched_build(output_root)
        repeat = _validate_repeated_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii")
        receipt = {
            "schema": "node0004-assumed-hardware-package-validation-v2",
            "status": "PACKAGE_READY_NOT_RUN",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "package_file_count": len(
                package_records(package, exclude_manifest=False)
            ),
            "preloaded_runtime_readback_target_count": 0,
            "result_gate_fail_closed": True,
            "return_allowlist_only": True,
            "functional_rtl_modified": False,
            "server_action": False,
            "repeated_build": repeat,
        }
        write_json(validation_path, receipt)
    except Exception as error:
        print(f"package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
