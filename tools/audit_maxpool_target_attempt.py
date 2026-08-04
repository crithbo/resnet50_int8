from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.native_json_maxpool_package import (  # noqa: E402
    validate_native_json_maxpool_package,
)


def _record(project_root: Path, relative: str) -> dict[str, object]:
    path = project_root / relative
    return {
        "path": relative,
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
    }


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    output = (
        project_root
        / "artifacts"
        / "w5"
        / "hwop-0002-00"
        / "maxpool_v1"
        / "complete_target_attempt.json"
    )
    if output.exists():
        raise RuntimeError(f"refusing to overwrite target attempt report: {output}")
    wsl = shutil.which("wsl") or shutil.which("wsl.exe")
    wsl_distributions: list[str] = []
    wsl_probe_status = "not_installed"
    if wsl:
        probe = subprocess.run(
            [wsl, "-l", "-q"], capture_output=True, check=False, timeout=15
        )
        raw = probe.stdout
        try:
            decoded = raw.decode("utf-16-le").strip("\x00\r\n ")
        except UnicodeDecodeError:
            decoded = raw.decode(errors="replace").strip()
        wsl_distributions = [item.strip("\x00 ") for item in decoded.splitlines() if item.strip("\x00 ")]
        wsl_probe_status = "available" if wsl_distributions else "no_distribution"
    config_root = project_root / "configs" / "maxpool" / "hwop-0002-00"
    package_root = project_root / "artifacts/w5/native_json_maxpool/v2/hardware_execplan_package"
    package_validation = validate_native_json_maxpool_package(package_root)
    package_manifest = _json(package_root / "manifest.json")
    overlay_zip = project_root / "artifacts/maxpool_server_v1.zip"
    sidecar = project_root / "artifacts/maxpool_server_v1.zip.sha256"
    round1_path = project_root / "artifacts/maxpool_server_v1_round1.json"
    round2_path = project_root / "artifacts/maxpool_server_v1_round2.json"
    runtime_identity_path = (
        project_root
        / "artifacts/maxpool_server_v1/NDP_copy01/install/cfg_pkg/"
        "node0002-maxpool1/metadata/runtime_identity.json"
    )
    if not all(
        path.is_file()
        for path in (overlay_zip, sidecar, round1_path, round2_path, runtime_identity_path)
    ):
        raise RuntimeError("validated MaxPool server-package evidence is incomplete")
    zip_sha256 = hashlib.sha256(overlay_zip.read_bytes()).hexdigest()
    sidecar_fields = sidecar.read_text(encoding="utf-8").split()
    round1 = _json(round1_path)
    round2 = _json(round2_path)
    if (
        sidecar_fields != [zip_sha256, overlay_zip.name]
        or round1.get("status") != "passed"
        or round1.get("zip_sha256") != zip_sha256
        or round2.get("status") != "passed"
        or round2.get("zip_sha256") != zip_sha256
        or round2.get("hdl_file_count") != 0
    ):
        raise RuntimeError("MaxPool ZIP/Round1/Round2 identity differs")
    report = {
        "schema_version": "0.1",
        "kind": "complete_target_execution_attempt_audit",
        "status": "test_package_ready_target_not_executed",
        "identity": {"node_id": "node-0002", "hwop_id": "hwop-0002-00"},
        "completed_prerequisites": {
            "frozen_wave_configs": sorted(path.name for path in config_root.glob("wave-*.json")),
            "official_encoder_evidence": (
                project_root
                / "artifacts/w5/hwop-0002-00/maxpool_v1/encoder_candidate_v2/evidence.json"
            ).is_file(),
            "rtl_unsigned_max_kernel_proof": (
                project_root
                / "artifacts/w5/hwop-0002-00/maxpool_v1/rtl_uint8_kernel_proof.json"
            ).is_file(),
            "hardware_execplan_package_validation": package_validation,
            "server_overlay_round1": {
                "path": str(round1_path.relative_to(project_root)).replace("\\", "/"),
                "status": round1["status"],
                "sha256": hashlib.sha256(round1_path.read_bytes()).hexdigest(),
            },
            "server_overlay_round2": {
                "path": str(round2_path.relative_to(project_root)).replace("\\", "/"),
                "status": round2["status"],
                "sha256": hashlib.sha256(round2_path.read_bytes()).hexdigest(),
            },
        },
        "target_entry_snapshot": [
            _record(project_root, "NDP_copy01/Makefile.tb_NDP_Top_new_phy"),
            _record(project_root, "NDP_copy01/tb_NDP_Top_new_phy.sv"),
            _record(project_root, "NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f"),
        ],
        "package_readiness": {
            "status": "ready_for_server_run1",
            "package_style": "immutable_native_json_two_real_channel_tile_control",
            "scope": {
                "logical_node": "node-0002",
                "hardware_op": "hwop-0002-00",
                "active_slices": [0, 1],
                "real_channel_tiles": [[0, 15], [16, 31]],
                "runtime_operator_count": package_manifest["runtime_operator_count"],
                "exec_128bit_line_count": package_manifest["exec_128bit_line_count"],
                "preload_transfer_count": package_validation["preload_transfer_count"],
                "readback_region_count": package_validation["readback_transfer_count"],
                "full_batch16_28_slice_package": False,
            },
            "hardware_execplan_package": {
                "path": str(package_root.relative_to(project_root)).replace("\\", "/"),
                "manifest_sha256": hashlib.sha256(
                    (package_root / "manifest.json").read_bytes()
                ).hexdigest(),
                "freeze_id": package_manifest["freeze_id"],
            },
            "server_overlay": {
                "path": str(overlay_zip.relative_to(project_root)).replace("\\", "/"),
                "size_bytes": overlay_zip.stat().st_size,
                "sha256": zip_sha256,
                "sidecar_path": str(sidecar.relative_to(project_root)).replace("\\", "/"),
                "install_name": "node0002-maxpool1",
                "runner": "RUN_SERVER_MAXPOOL1.sh",
                "hdl_file_count": 0,
            },
            "runtime_identity": {
                "path": str(runtime_identity_path.relative_to(project_root)).replace("\\", "/"),
                "sha256": hashlib.sha256(runtime_identity_path.read_bytes()).hexdigest(),
            },
            "return_analyzer": {
                "path": "tools/analyze_native_json_maxpool_return.py",
                "exists": (project_root / "tools/analyze_native_json_maxpool_return.py").is_file(),
            },
        },
        "local_execution_environment": {
            "platform": "Windows",
            "vcs": shutil.which("vcs"),
            "make": shutil.which("make"),
            "bash": shutil.which("bash"),
            "wsl": wsl,
            "wsl_probe_status": wsl_probe_status,
            "wsl_distributions": wsl_distributions,
            "native_readme_requirement": "Linux x86_64 + GNU make/bash + Synopsys VCS/license + DesignWare/AMBA VIP/DDR-PHY dependencies",
        },
        "attempt": {
            "target_process_started": False,
            "reason": "the content-addressed test package is ready, but this Windows host has no Linux/VCS/license target environment",
            "simulation_completed": False,
            "target_output_produced": False,
            "g6_validated": False,
            "g8_validated": False,
        },
        "next_required_work": [
            "upload maxpool_server_v1.zip and its SHA-256 sidecar to the Linux/VCS server",
            "merge NDP_copy01 and execute SERVER_RUN_ID=run1 bash RUN_SERVER_MAXPOOL1.sh",
            "validate the run1 return with tools/analyze_native_json_maxpool_return.py",
            "only after run1 passes, execute immutable run2 and compare repeated output identities",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )
    print(json.dumps({"status": report["status"], "output": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
