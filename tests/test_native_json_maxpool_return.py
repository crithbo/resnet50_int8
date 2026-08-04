from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from tools.analyze_native_json_maxpool_return import analyze_return


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "artifacts/w5/native_json_maxpool/v2/hardware_execplan_package"
OVERLAY = ROOT / "artifacts/maxpool_server_v1"
INSTALL = (
    OVERLAY / "NDP_copy01/install/cfg_pkg/node0002-maxpool1"
)
RUNTIME_IDENTITY = INSTALL / "metadata/runtime_identity.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


class NativeJsonMaxPoolReturnTests(unittest.TestCase):
    def _build_return(self, root: Path) -> None:
        identity = _json(RUNTIME_IDENTITY)
        package_manifest = _json(PACKAGE / "manifest.json")
        fixed = {
            "sca_cfg.json": INSTALL / "sca_cfg.json",
            "sca_cfg_D.json": INSTALL / "sca_cfg_D.json",
            "metadata/manifest.json": PACKAGE / "manifest.json",
            "metadata/runner_contract.json": PACKAGE / "runner_contract.json",
            "metadata/dump_contract.json": PACKAGE / "dump_contract.json",
            "metadata/readback_regions.tsv": INSTALL / "metadata/readback_regions.tsv",
            "metadata/expected_runtime_stages.tsv": INSTALL
            / "metadata/expected_runtime_stages.tsv",
            "metadata/runtime_identity.json": RUNTIME_IDENTITY,
        }
        for key in (
            "launch_file_contract",
            "launch_identity",
            "runtime_make_override",
            "run_command_contract",
            "runner_identity",
        ):
            source = OVERLAY / identity[key]["path"]
            fixed[f"metadata/{source.name}"] = source
        for relative, source in fixed.items():
            _copy(source, root / "config" / relative)
        inventory = root / "config/server_source_inventory.tsv"
        inventory.parent.mkdir(parents=True, exist_ok=True)
        inventory.write_bytes(b"synthetic fixture\n")

        sca_d = _json(INSTALL / "sca_cfg_D.json")
        golden_lines = {
            slice_id: (PACKAGE / f"golden/slice{slice_id:02d}.txt")
            .read_text(encoding="ascii")
            .splitlines()
            for slice_id in (0, 1)
        }
        for entry in sca_d.values():
            semantic_key = str(entry["semantic_key"])
            slice_id = int(semantic_key.rsplit("slice", 1)[1])
            index = int(entry["axi4_segment_index"])
            length = int(entry["length"])
            start = 0 if index == 0 else int(entry["semantic_length"]) - length
            payload = "\n".join(golden_lines[slice_id][start : start + length]) + "\n"
            raw_path = PurePosixPath(str(entry["path"]))
            hwop_index = max(
                i for i, part in enumerate(raw_path.parts) if part.startswith("hwop-")
            )
            destination = root / "readback_regions" / Path(*raw_path.parts[hwop_index:])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload.encode("ascii"))

        console = []
        for index in range(11):
            console.extend(
                [
                    f"[{index}] JSON: Loading matrix[{index}]: fixture -> 0x00000000",
                    f"[{index}] *** PASS: Continuous transfer completed successfully!",
                ]
            )
        console.extend(
            [
                "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING",
                "[100] INFO: slice start",
                "[200] INFO: slice completed after 10 cycles",
                "Simulation completed successfully!",
                "Simulation exit status: 0",
            ]
        )
        console_path = root / "run_sim_results/maxpool1_console.log"
        console_path.parent.mkdir(parents=True, exist_ok=True)
        console_path.write_bytes(("\n".join(console) + "\n").encode("utf-8"))
        (root / "preload_readback_report.json").write_bytes(
            (
                json.dumps(
                    {
                        "status": "passed",
                        "expected_transfer_count": 11,
                        "passed_transfer_count": 11,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        )
        (root / "server_source_provenance.json").write_bytes(
            b'{"server_run_id":"run1"}\n'
        )
        metadata = {
            "server_run_id": "run1",
            "execution_environment": "rtl_simulation",
            "board_version": "not_applicable_rtl_simulation",
            "firmware_version": "not_applicable_rtl_simulation",
            "isa_contract": "model_execplan_package_manifest_and_execplan_128bit_v1",
            "server_source_provenance": "server_source_provenance.json",
            "simulator_version": "synthetic-vcs",
            "exit_status": 0,
            "process_exit_status": 0,
            "make_exit_status": 0,
            "tee_exit_status": 0,
            "phase_watchdog_exit_status": 0,
            "raw_phase_watchdog_exit_status": 0,
            "simulator_exit_status": 0,
            "simulator_exit_status_observed": True,
            "phase_watchdog_done": True,
            "phase_stall_seconds": 0,
            "termination_kind": "natural_process_exit",
            "preflight_status": "passed",
            "timeout_status": "not_timed_out",
            "phase_timeout_status": "not_timed_out",
            "phase_failure_reason": "none",
            "stage_marker_status": "passed",
            "all_stages_marker_status": "passed",
            "readback_region_contract_status": "passed",
            "make_archive_policy": "runner_no_archive_target_v1",
            "return_archive_policy": "bounded_exact_set_allowlist_v2",
            "testbench_observer_mode": "fixed_slice0_start_slice1_finish",
            "completed_runtime_stage_count": 2,
            "expected_runtime_stage_count": 2,
            "expected_testbench_repeat_num": 1,
            "observed_slice0_start_count": 1,
            "observed_slice1_finish_count": 1,
            "reserved_clock_force_marker_count": 1,
            "reserved_clock_failure_marker_count": 0,
            "returned_region_count": 4,
            "expected_region_count": 4,
            "freeze_id": package_manifest["freeze_id"],
            "freeze_manifest_sha256": package_manifest["freeze_manifest_sha256"],
            "package_manifest_sha256": _sha256(PACKAGE / "manifest.json"),
            "runtime_identity_sha256": _sha256(RUNTIME_IDENTITY),
            "sca_cfg_sha256": _sha256(INSTALL / "sca_cfg.json"),
            "sca_cfg_D_sha256": _sha256(INSTALL / "sca_cfg_D.json"),
            "readback_contract_sha256": _sha256(
                INSTALL / "metadata/readback_regions.tsv"
            ),
        }
        (root / "run_metadata.json").write_bytes(
            (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        contract_path = root / "return_file_contract.tsv"
        records = []
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if path == contract_path:
                continue
            records.append(
                f"{path.relative_to(root).as_posix()}\t{path.stat().st_size}\t{_sha256(path)}"
            )
        contract_path.write_bytes(("\n".join(records) + "\n").encode("utf-8"))

    def test_synthetic_success_return_matches_every_golden_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            root = Path(temp_text) / "maxpool1_run1_return"
            root.mkdir()
            self._build_return(root)
            report = analyze_return(PACKAGE, root, RUNTIME_IDENTITY)
            self.assertEqual(report["status"], "passed_single_server_return")
            self.assertEqual(report["logical_mismatch_count"], 0)
            self.assertEqual(len(report["regions"]), 2)
            self.assertFalse(report["g6_validated"])


if __name__ == "__main__":
    unittest.main()
