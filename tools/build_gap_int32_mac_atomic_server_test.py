from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_int32_mac_bypass import W3_EXPECTED_PATH, W3_INPUT_PATH  # noqa: E402
from resnet50_pipeline.hashing import canonical_json_bytes, sha256_file  # noqa: E402


LOCAL_E2 = Path(
    "artifacts/operator_config_validation/gap-int32-mac-bypass-v1/local-e2"
)
OUTPUT = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "gap_int32_mac_stock_rtl_atomic_v1"
)
ZIP_PATH = OUTPUT.with_suffix(".zip")
PACKAGE_NAME = "gap_int32_mac_stock_rtl_atomic_v1"
INSTALL_PREFIX = f"install/cfg_pkg/{PACKAGE_NAME}"
SLICE_SHIFT = 25
FINAL_D_BASE = 0xBC000
CONFIG_BASES = tuple(0x100000 + index * 0x10000 for index in range(6))
EXEC_BASE = 0x1A0000


def _write_lines(path: Path, payload: bytes) -> None:
    if len(payload) % 16:
        raise ValueError(f"payload is not 128-bit aligned: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(f"{int.from_bytes(payload[i:i+16], 'little'):0128b}" for i in range(0, len(payload), 16))
        + "\n",
        encoding="ascii",
        newline="\n",
    )


def _files(root: Path) -> dict[str, dict[str, object]]:
    result = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def build(root: Path, output: Path) -> dict[str, object]:
    local = root / LOCAL_E2
    local_report = json.loads((local / "LOCAL_E2_REPORT.json").read_text(encoding="utf-8"))
    if (
        local_report.get("status") != "pass_local_e2"
        or local_report.get("server_package_allowed") is not True
        or local_report.get("rtl_patch_present") is not False
    ):
        raise ValueError("local E2 gate is not open")
    if output.exists():
        shutil.rmtree(output)
    (output / "install/cfg_pkg").mkdir(parents=True)
    shutil.copy2(local / "install/execplan.txt", output / "install/execplan.txt")
    shutil.copy2(local / "instructions_explained.txt", output / "instructions_explained.txt")
    for stage in range(1, 7):
        shutil.copy2(
            local / f"install/cfg_pkg/gap_int32_mac_stage{stage}_128b.bin",
            output / f"install/cfg_pkg/gap_int32_mac_stage{stage}_128b.bin",
        )
        source = root / f"configs/gap_int32_mac_bypass_v1/stage-{stage}"
        destination = output / f"config/stage-{stage}"
        destination.mkdir(parents=True)
        for name in ("config.json", "manifest.json"):
            candidate = source / name
            if candidate.is_file():
                shutil.copy2(candidate, destination / name)
        shutil.copy2(source / "encoded/mapping_review.json", destination / "mapping_review.json")
        shutil.copy2(source / "encoded/parsed_bitstream.txt", destination / "parsed_bitstream.txt")

    tensor = np.load(root / W3_INPUT_PATH, allow_pickle=False)
    expected = np.load(root / W3_EXPECTED_PATH, allow_pickle=False).reshape(16, 2048)
    matrix = tensor.reshape(16, 2048, 49).reshape(16, 256, 8, 49).transpose(0, 1, 3, 2)
    sca: dict[str, object] = {
        "Exec_Base": f"0x{EXEC_BASE:08X}",
        "Exec_Length": sum(
            bool(line.strip())
            for line in (output / "install/execplan.txt").read_text(encoding="ascii").splitlines()
        ),
        "Repeat_Num": 6,
        "ExecutionPlan": {
            "base_addr": f"0x{EXEC_BASE:08X}",
            "path": f"{INSTALL_PREFIX}/install/execplan.txt",
        },
    }
    sca_d: dict[str, object] = {}
    for stage, base in enumerate(CONFIG_BASES, start=1):
        sca[f"gap_mac_s{stage}_config"] = {
            "base_addr": f"0x{base:08X}",
            "path": (
                f"{INSTALL_PREFIX}/install/cfg_pkg/"
                f"gap_int32_mac_stage{stage}_128b.bin"
            ),
        }
    for slice_id in range(16):
        a = np.zeros((256, 32, 16), dtype=np.uint8)
        c = np.zeros((256, 32, 16), dtype=np.uint8)
        for output_index in range(32):
            left, right = output_index * 2, output_index * 2 + 1
            if left < 49:
                a[:, output_index, :8] = matrix[slice_id, :, left, :]
            if right < 49:
                c[:, output_index, :8] = matrix[slice_id, :, right, :]
        a_path = output / f"install/input/slice{slice_id:02d}/matrix_A_128bit.txt"
        c_path = output / f"install/input/slice{slice_id:02d}/matrix_C_128bit.txt"
        golden_path = output / f"golden/slice{slice_id:02d}/matrix_D_128bit.txt"
        _write_lines(a_path, a.tobytes())
        _write_lines(c_path, c.tobytes())
        _write_lines(golden_path, expected[slice_id].astype("<i4", copy=False).tobytes())
        prefix = slice_id << SLICE_SHIFT
        sca[f"gap_mac_s1_matrixA_slice{slice_id}"] = {
            "base_addr": f"0x{prefix:08X}",
            "path": f"{INSTALL_PREFIX}/{a_path.relative_to(output).as_posix()}",
        }
        sca[f"gap_mac_s1_matrixC_slice{slice_id}"] = {
            "base_addr": f"0x{prefix | 0x20000:08X}",
            "path": f"{INSTALL_PREFIX}/{c_path.relative_to(output).as_posix()}",
        }
        sca_d[f"gap_mac_s6_matrixD_slice{slice_id}"] = {
            "base_addr": f"0x{prefix | FINAL_D_BASE:08X}",
            "path": (
                f"{INSTALL_PREFIX}/readback/slice{slice_id:02d}/"
                "matrix_D_128bit.txt"
            ),
        }
    (output / "sca_cfg.json").write_text(
        json.dumps(sca, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "sca_cfg_D.json").write_text(
        json.dumps(sca_d, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    delivery = """# GAP int32_mac stock-RTL atomic v1

Evidence level at packaging: E2_LOCAL_ONLY; candidate_release=false.

This package contains no RTL, RTL patch, installer, observer, waveform, build tree,
or nested archive. It tests one hypothesis only: six fully reloaded stock-RTL
int32_mac(A,1,C) stages using READ_STREAM0/READ_STREAM3 and the normal GA FIFO.

Bind both files explicitly in the existing server invocation:

  +SCA_CFG=<package>/sca_cfg.json
  +SCA_CFG_D=<package>/sca_cfg_D.json

Return only sim.log, all 16 readback matrix_D files, and the focused GA/MSE
same-clock log if the existing server harness already provides it. Do not return
waveforms or a build tree. E4 requires every 16x512 readback line to match the
included golden and no normal-FIFO occupancy/invalid-slot violation.
"""
    (output / "DELIVERY.md").write_text(delivery, encoding="utf-8", newline="\n")
    pre_manifest_files = _files(output)
    manifest = {
        "schema": "gap-int32-mac-stock-rtl-atomic-server-test-v1",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "atomic_hypothesis_count": 1,
        "functional_rtl_modified": False,
        "rtl_patch_present": False,
        "nested_archive_present": False,
        "source_local_e2": {
            "path": (LOCAL_E2 / "LOCAL_E2_REPORT.json").as_posix(),
            "sha256": sha256_file(local / "LOCAL_E2_REPORT.json"),
        },
        "required_server_gates": {
            "formal_d_readback": "16 slices x 512 lines exact golden",
            "normal_fifo_count": "0<=count<=2 for all 8 ordinary PE",
            "invalid_slot_reuse": 0,
            "dual_mse_pairing": "READ_STREAM0/READ_STREAM3 same occurrence and tag",
            "stage_barriers": 6,
        },
        "golden_readback_contract": {
            f"slice{slice_id:02d}": {
                "path": f"golden/slice{slice_id:02d}/matrix_D_128bit.txt",
                "line_count": 512,
            }
            for slice_id in range(16)
        },
        "files": pre_manifest_files,
    }
    (output / "PACKAGE_MANIFEST.json").write_bytes(canonical_json_bytes(manifest) + b"\n")
    return manifest


def package(output: Path, zip_path: Path) -> dict[str, object]:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in output.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(
                path.relative_to(output).as_posix(),
                date_time=(2026, 7, 24, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = sha256_file(zip_path)
    sidecar = zip_path.with_suffix(zip_path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    return {
        "zip": str(zip_path),
        "sha256": digest,
        "size_bytes": zip_path.stat().st_size,
        "entry_count": len(_files(output)),
        "sidecar": str(sidecar),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = (root / OUTPUT).resolve()
    manifest = build(root, output)
    result = package(output, (root / ZIP_PATH).resolve())
    result["manifest_schema"] = manifest["schema"]
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
