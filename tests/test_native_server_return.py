from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from resnet50_pipeline.native_server_return import (
    NativeServerReturnError,
    analyze_native_server_return,
)


ROOT = Path(__file__).resolve().parents[1]
GAP_WORKLOAD = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-workloads/"
    "gap_hwop0071_sum_graph"
)
GAP_PROFILE = (
    ROOT / "contracts/server_return_profiles/gap_hwop0071_sum_v1.json"
)


def _synthetic_gap_return(root: Path) -> None:
    log = root / "sim_results" / "sim.log"
    log.parent.mkdir(parents=True)
    log.write_text(
        "\n".join(
            [
                "Command: simv +SCA_CFG=install/cfg_pkg/"
                "gap_hwop0071_sum_graph/sca_cfg.json "
                "+SCA_CFG_D=install/cfg_pkg/"
                "gap_hwop0071_sum_graph/sca_cfg_D.json",
                "Using SCA cfg file: install/cfg_pkg/"
                "gap_hwop0071_sum_graph/sca_cfg.json",
                "Using SCA cfg D file: install/cfg_pkg/"
                "gap_hwop0071_sum_graph/sca_cfg_D.json",
                "JSON config: 18 matrices loaded",
                "JSON: Exec_Length = 17",
                "[100] INFO: slice start",
                "[200] INFO: slice completed after 100 cycles",
                "JSON_D config: 16 matrices dumped",
                "Simulation completed successfully!",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    for slice_id in range(16):
        relative = Path(
            f"install/op0/slice{slice_id:02d}/"
            "matrix_D_linearized_128bit.txt"
        )
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(GAP_WORKLOAD / relative, destination)

    gexec = root / "sim_results/gexec2slice/slice_all/gexec2slice.log"
    gexec.parent.mkdir(parents=True)
    gexec.write_text(
        "# test\n100 | 0 | 0x0000000000000005\n",
        encoding="ascii",
        newline="\n",
    )
    local = root / "sim_results/local/slice0"
    local.mkdir(parents=True)
    (local / "local_mse0_req.log").write_text(
        "# test\n100 | 0 | 0x0 | 0 | 0 | 0 | 0 | 1\n",
        encoding="ascii",
        newline="\n",
    )
    (local / "local_mse0_rdata.log").write_text(
        "# test\n110 | 0 | 0 | 100 | 0x0\n",
        encoding="ascii",
        newline="\n",
    )
    (local / "local_mse4_req.log").write_text(
        "# test\n150 | 0 | 0x0 | 0 | 0 | 0 | 1 | 1\n",
        encoding="ascii",
        newline="\n",
    )
    (local / "local_mse4_wdata.log").write_text(
        "# test\n160 | 0 | 0x0\n",
        encoding="ascii",
        newline="\n",
    )


class NativeServerReturnTests(unittest.TestCase):
    def test_synthetic_gap_return_passes_numeric_readback(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            returned = Path(temp) / "returned"
            _synthetic_gap_return(returned)
            report = analyze_native_server_return(
                returned,
                GAP_WORKLOAD,
                profile_path=GAP_PROFILE,
            )
            self.assertEqual(report["status"], "passed")
            self.assertEqual(
                report["classification"], "numeric_readback_pass_e4_candidate"
            )
            self.assertEqual(report["numeric"]["passed_matrix_count"], 16)
            self.assertEqual(
                report["checkpoint_analysis"]["furthest_direct_checkpoint"],
                "numeric_compare",
            )

    def test_synthetic_gap_numeric_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            returned = Path(temp) / "returned"
            _synthetic_gap_return(returned)
            target = (
                returned
                / "install/op0/slice03/matrix_D_linearized_128bit.txt"
            )
            lines = target.read_text(encoding="ascii").splitlines()
            lines[0] = ("1" if lines[0][0] == "0" else "0") + lines[0][1:]
            target.write_text(
                "\n".join(lines) + "\n", encoding="ascii", newline="\n"
            )
            report = analyze_native_server_return(
                returned,
                GAP_WORKLOAD,
                profile_path=GAP_PROFILE,
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["classification"], "numeric_mismatch")
            self.assertGreater(report["numeric"]["total_mismatch_byte_count"], 0)
            self.assertIn(
                "NUMERIC_MISMATCH",
                {item["code"] for item in report["issues"]},
            )

    def test_gap_profile_rejects_a_different_workload_tree_hash(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            returned = Path(temp) / "returned"
            _synthetic_gap_return(returned)
            profile = json.loads(GAP_PROFILE.read_text(encoding="utf-8"))
            profile["workload_binding"]["payload_tree_sha256"] = "0" * 64
            altered_profile = Path(temp) / "altered_profile.json"
            altered_profile.write_text(
                json.dumps(profile, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                NativeServerReturnError,
                "payload_tree_sha256 differs from workload",
            ):
                analyze_native_server_return(
                    returned,
                    GAP_WORKLOAD,
                    profile_path=altered_profile,
                )

    def test_sca_command_and_echo_mismatch_is_a_setup_failure(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            returned = Path(temp) / "returned"
            _synthetic_gap_return(returned)
            sim_log = returned / "sim_results/sim.log"
            text = sim_log.read_text(encoding="utf-8")
            text = text.replace(
                "Using SCA cfg D file: install/cfg_pkg/"
                "gap_hwop0071_sum_graph/sca_cfg_D.json",
                "Using SCA cfg D file: install/cfg_pkg/"
                "wrong_graph/sca_cfg_D.json",
            )
            sim_log.write_text(text, encoding="utf-8", newline="\n")
            report = analyze_native_server_return(
                returned,
                GAP_WORKLOAD,
                profile_path=GAP_PROFILE,
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["classification"], "setup_or_binding_failure")
            codes = {item["code"] for item in report["issues"]}
            self.assertIn("SCA_D_COMMAND_ECHO_MISMATCH", codes)
            self.assertIn("SCA_PACKAGE_DIRECTORY_MISMATCH", codes)

    def test_return_observer_stall_cannot_be_misreported_as_passed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            returned = Path(temp) / "returned"
            _synthetic_gap_return(returned)
            observer = (
                returned
                / "sim_results/return_observer/return_observer.log"
            )
            observer.parent.mkdir(parents=True)
            observer.write_text(
                "\n".join(
                    [
                        "# Native NDP return observer v1",
                        "100 | HEARTBEAT | slice=0 active_cycles=4096",
                        "101 | INTERNAL_STATE | event=HEARTBEAT slice=0 "
                        "buf4_wr_en=0x0 buf4_rd_en=0x1 "
                        "buf5_wr_en=0x0 buf5_rd_en=0x0",
                        "120 | STALL | slice=0 pe=PE00 opcode=5 "
                        "p0_valid=1 bp_post=0 enable=0 cycles=4096",
                        "",
                    ]
                ),
                encoding="ascii",
                newline="\n",
            )
            report = analyze_native_server_return(
                returned,
                GAP_WORKLOAD,
                profile_path=GAP_PROFILE,
            )
            self.assertEqual(report["status"], "stalled")
            self.assertEqual(
                report["classification"], "internal_pipeline_stall_observed"
            )
            self.assertIn(
                "RETURN_OBSERVER_STALL",
                {item["code"] for item in report["issues"]},
            )
            self.assertEqual(
                report["auxiliary"]["return_observer_heartbeat_count"], 1
            )
            self.assertEqual(
                report["auxiliary"]["return_observer_internal_state_count"], 1
            )
            self.assertIn(
                "buf4_rd_en=0x1",
                report["auxiliary"]["return_observer_last_internal_state"],
            )

    def test_return_observer_is_opt_in_and_wired_to_known_rtl_signals(self) -> None:
        tb = (ROOT / "NDP_copy01/tb_NDP_Top_new_phy.sv").read_text(
            encoding="utf-8"
        )
        observer = (ROOT / "NDP_copy01/native_return_observer.svh").read_text(
            encoding="utf-8"
        )
        makefile = (
            ROOT / "NDP_copy01/Makefile.tb_NDP_Top_new_phy"
        ).read_text(encoding="utf-8")
        ga_inbuffer = (
            ROOT
            / "NDP_copy01/rtl/Slice/General_Array/"
            "GA_PE_Group/GA_PE_Inbuffer.sv"
        ).read_text(encoding="utf-8")
        slice_rtl = (ROOT / "NDP_copy01/rtl/Slice/Slice_cdc.sv").read_text(
            encoding="utf-8"
        )
        buffer_rtl = (
            ROOT
            / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv"
        ).read_text(encoding="utf-8")
        self.assertIn('`include "native_return_observer.svh"', tb)
        self.assertIn("+incdir+$(TB_DIR)", makefile)
        self.assertIn('$test$plusargs("RETURN_OBSERVER")', observer)
        self.assertIn("return_observer/return_observer.log", observer)
        for signal in (
            "ga_pe_enable",
            "ga_pe_alu_opcode",
            "alu_input_valid_bit",
            "alu_pipeline0_valid_bit",
            "alu_pipeline0_bp_post",
            "ga_pe_alu_pipeline0_enable",
            "ga_pe_inbuffer_bp_pre",
        ):
            self.assertIn(signal, observer)
            self.assertIn(signal, ga_inbuffer)
        for signal in (
            "sa_inport_group_in_tag",
            "sa_outport_group_out_tag",
            "buf2spec_array_rtag",
            "spec_array2buf_wtag",
            "buf2spec_array_bp_pre",
        ):
            self.assertIn(signal, observer)
            self.assertIn(signal, slice_rtl)
        for signal in ("buf_wr_en", "buf_rd_en"):
            self.assertIn(signal, observer)
            self.assertIn(signal, buffer_rtl)

    def test_zip_return_is_supported_without_extraction(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            returned = Path(temp) / "returned"
            _synthetic_gap_return(returned)
            archive = Path(temp) / "returned.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as out:
                for path in sorted(returned.rglob("*")):
                    if path.is_file():
                        out.write(path, Path("wrapped") / path.relative_to(returned))
            report = analyze_native_server_return(
                archive,
                GAP_WORKLOAD,
                profile_path=GAP_PROFILE,
            )
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["inputs"]["return_kind"], "zip")

    def test_historical_int8_maxpool_stall_is_classified_at_write_data(self) -> None:
        report = analyze_native_server_return(
            ROOT / "server_returns/native_int8_maxpool16_sim4_2_20260723",
            ROOT / "ndp-sim/model_execplan/output/native_int8_maxpool16_r1_graph",
            run_id="diagnostic",
        )
        self.assertEqual(report["status"], "stalled")
        self.assertEqual(
            report["classification"], "write_address_without_write_data"
        )
        self.assertIn(
            "WRITE_ADDRESS_WITHOUT_WRITE_DATA",
            {item["code"] for item in report["issues"]},
        )
        activity = report["checkpoint_analysis"]["aggregate_memory_activity"]
        self.assertGreater(activity["read_data"], 0)
        self.assertGreater(activity["write_address"], 0)
        self.assertEqual(activity["write_data"], 0)

    def test_historical_fp32_completion_without_returned_d_is_incomplete(self) -> None:
        report = analyze_native_server_return(
            ROOT / "server_returns/int8_fp32_pair_20260723/sim5_raw",
            ROOT
            / "ndp-sim/model_execplan/output/"
            "native_deepseek_fp32_max_control_r1_graph",
            run_id="diagnostic",
        )
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(
            report["classification"],
            "runtime_and_readback_logged_return_payload_missing",
        )
        self.assertTrue(report["runtime"]["simulation_success_marker"])
        self.assertEqual(report["runtime"]["readback_matrix_count"], 28)
        self.assertEqual(report["numeric"]["missing_matrix_count"], 28)

    def test_historical_wrong_sca_path_is_setup_failure(self) -> None:
        report = analyze_native_server_return(
            ROOT / "server_returns/int8_fp32_pair_20260723/sim4_raw",
            ROOT / "ndp-sim/model_execplan/output/native_int8_maxpool16_r1_graph",
            run_id="diagnostic",
        )
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["classification"], "setup_or_binding_failure")
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("SCA_D_PLUSARG_MISSING", codes)
        self.assertIn("SERVER_FILE_OPEN_FAILED", codes)


if __name__ == "__main__":
    unittest.main()
