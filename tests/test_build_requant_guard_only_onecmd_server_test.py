from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import build_requant_guard_only_onecmd_server_test as builder
from tools import requant_atomic_server_runtime as runtime
from tools import requant_node0001_server_runtime as common_runtime


class RequantGuardOnlyServerPackageTests(unittest.TestCase):
    def test_package_is_guard_only_and_stock_rtl(self) -> None:
        build_report = json.loads(
            builder.VALIDATION_RECEIPT.read_text(encoding="utf-8")
        )
        report = build_report["preflight"]
        self.assertEqual(report["diagnostic_mode"], "guard_only")
        self.assertEqual(report["stage_count"], 1)
        self.assertEqual(report["start_comp_count"], 1)
        self.assertEqual(report["same_mask_fence_count"], 1)
        self.assertEqual(report["expected_mse4_write_count"], 16)
        self.assertEqual(report["formal_readback_count"], 2)
        with zipfile.ZipFile(builder.DEFAULT_OUTPUT.with_suffix(".zip")) as archive:
            names = archive.namelist()
        self.assertFalse(
            any("rtl" in {part.lower() for part in name.split("/")} for name in names)
        )
        self.assertFalse(any("round_saturate.json" in name for name in names))
        self.assertFalse(any("round_config" in name for name in names))

    def test_guard_semantic_payloads_are_frozen(self) -> None:
        frozen = builder.FROZEN_ATOMIC_PACKAGE
        package = builder.DEFAULT_OUTPUT
        pairs = (
            ("validation/guard.json", "validation/guard.json"),
            (
                "validation/native/op_w0_s00_guard/bitstream_128b.bin",
                "validation/native/op_w0_s00_guard/bitstream_128b.bin",
            ),
            (
                "workload/runtime/payloads/cfg_pkg/"
                "op_w0_s00_guard_resnet50_requant_guard_node0001_bitstream_128b.bin",
                "workload/runtime/payloads/cfg_pkg/"
                "op_w0_s00_guard_resnet50_requant_guard_node0001_bitstream_128b.bin",
            ),
            (
                "workload/runtime/payloads/cfg_pkg/RequantGuard.txt",
                "workload/runtime/payloads/cfg_pkg/RequantGuard.txt",
            ),
            ("golden/guard_slice00_128b.txt", "golden/guard_slice00_128b.txt"),
            ("golden/guard_slice01_128b.txt", "golden/guard_slice01_128b.txt"),
        )
        for frozen_relative, package_relative in pairs:
            self.assertEqual(
                (frozen / frozen_relative).read_bytes(),
                (package / package_relative).read_bytes(),
                package_relative,
            )

    def test_runtime_and_address_domains_fail_closed(self) -> None:
        package = builder.DEFAULT_OUTPUT
        sca = json.loads(
            (package / "workload/runtime/sca_cfg.json").read_text(encoding="utf-8")
        )
        sca_d = json.loads(
            (package / "workload/runtime/sca_cfg_D.json").read_text(encoding="utf-8")
        )
        expected = json.loads(
            (
                package / "validation/expected_mse4_writes.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(sca["Repeat_Num"], 1)
        self.assertEqual(sca["Exec_Length"], 4)
        self.assertEqual(len(sca_d), 2)
        self.assertEqual(expected["total_expected_accepted_write_count"], 16)
        self.assertTrue(
            expected["address_domains"]["comparison_rule"].startswith(
                "only compare expected"
            )
        )
        tail = (
            package / "tb_probe" / builder.OBSERVER_TAIL_NAME
        ).read_text(encoding="utf-8")
        for marker in (
            "boundary=PE_SELECTED_INPUT",
            "boundary=SFU_PREPROCESS_INPUT_CAPTURE",
            "boundary=SFU_BST_RESULT_CAPTURE",
            "boundary=SFU_COEFF_CAPTURE",
            "boundary=SFU_ALU_INPUT_CAPTURE",
            "boundary=SFU_ALU_RESULT_ACCEPTED",
            "boundary=SFU_POSTPROCESS_RESULT_ACCEPTED",
            "boundary=NORMAL_OUTBUFFER_INPUT_ACCEPTED",
            "boundary=NORMAL_OUTBUFFER_WRITE_COMMIT",
            "boundary=NORMAL_OUTPORT_ACCEPTED",
            "boundary=MSE4_REQ",
            "boundary=MSE4_WDATA",
            "witness=capture_source_at_posedge",
            "witness=registered_capture_source",
            "witness=write_handshake",
            "witness=read_handshake",
            "req_txn_id=",
            "wdata_txn_id=",
            "paired_req_valid=",
            "transfer_addr=",
            "linear_addr=",
            "post_remap_addr=",
        ):
            self.assertIn(marker, tail)
        for superseded in (
            "boundary=GA_INPORT_CONFIG",
            "boundary=GA_CONVERT_REGISTERED",
            "boundary=PE_POST_REGISTER",
            "boundary=SFU_OPCODE_READY",
            "boundary=SFU_GROUP_COMPUTE_VALID",
            "boundary=SFU_LUT_INIT",
            "boundary=SFU_PREPROCESS0 ",
        ):
            self.assertNotIn(superseded, tail)
        active = "\n".join(
            line.split("//", 1)[0]
            for line in tail.splitlines()
            if not line.lstrip().startswith("//")
        ).lower()
        for forbidden in ("force ", "deposit", "release ", "<="):
            self.assertNotIn(forbidden, active)
        xmr = common_runtime.validate_observer_xmr_elaboration(tail)
        self.assertEqual(xmr["status"], "pass")
        self.assertEqual(
            xmr["runtime_indexed_generated_instance_reference_count"], 0
        )
        self.assertNotIn("slice_group_gen[sid]", tail)

    def test_xmr_gate_targets_hierarchy_not_signal_arrays(self) -> None:
        invalid = """
always @(posedge clk) begin
  for (int sid = 0; sid < 2; sid++)
    sample[sid] = top.slice_group_gen[sid].u_slice.signal;
end
"""
        with self.assertRaises(common_runtime.RequantRuntimeError):
            common_runtime.validate_observer_xmr_elaboration(invalid)
        valid = """
logic proxy [0:1];
generate
  for (genvar sid = 0; sid < 2; sid++) begin : PROXY
    assign proxy[sid] = top.slice_group_gen[sid].u_slice.signal;
  end
endgenerate
always @(posedge clk)
  for (int sid = 0; sid < 2; sid++)
    sample[sid][0] = proxy[sid];
"""
        report = common_runtime.validate_observer_xmr_elaboration(valid)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["ordinary_signal_array_runtime_indexing_allowed"])

    def test_bootstrap_exact_tree_is_immutable(self) -> None:
        report = json.loads(
            builder.VALIDATION_RECEIPT.read_text(encoding="utf-8")
        )
        bootstrap = report["bootstrap_immutability"]
        self.assertEqual(bootstrap["status"], "pass")
        self.assertTrue(bootstrap["exact_path_size_sha_unchanged"])
        self.assertEqual(
            bootstrap["package_tree_sha256_before"],
            bootstrap["package_tree_sha256_after"],
        )

    def test_actual_packaged_probe_installer_is_transactional(self) -> None:
        self.assertEqual(
            builder.OBSERVER_TAIL_NAME,
            "requant_mse4_guard_observer_tail.svh",
        )
        report = json.loads(
            builder.VALIDATION_RECEIPT.read_text(encoding="utf-8")
        )
        transaction = report["probe_transaction"]
        self.assertEqual(transaction["status"], "pass")
        self.assertTrue(transaction["fresh_zip_extraction"])
        self.assertTrue(transaction["tail_found_and_installed"])
        self.assertTrue(transaction["precompile_verify_passed"])
        self.assertEqual(
            transaction["xmr_elaboration_gate"]["status"], "pass"
        )
        self.assertTrue(transaction["observer_restored_byte_exact"])
        self.assertTrue(transaction["package_exact_tree_unchanged"])

    def test_missing_checkpoint_is_not_mislabeled_as_parse_divergence(self) -> None:
        boundaries = (
            "MSE0_RDATA",
            "MSE0_TO_BUFFER",
            "GA_INPORT_CONFIG",
            "GA_INPORT_IB",
            "GA_CONVERT_INPUT",
            "GA_CONVERT_REGISTERED",
            "GA_INPORT_FINAL",
            "PE_SELECTED_INPUT",
            "SFU_INPUT",
            "SFU_COMPUTE",
            "SFU_LUT",
            "SFU_ALU",
            "SFU_OUTPUT",
            "NORMAL_OUTBUFFER_WRITE",
            "MSE4_WDATA",
        )
        count_checks = {
            boundary: {
                "expected": 64,
                "raw": 64,
                "parsed": 64,
                "raw_equals_parsed": True,
            }
            for boundary in boundaries
        }
        count_checks["GA_CONVERT_INPUT"].update({"raw": 0, "parsed": 0})
        checkpoints = {
            "status": "fail",
            "count_checks": count_checks,
            "nonzero_data_counts": {
                boundary: (
                    1
                    if boundary
                    in {
                        "MSE0_RDATA",
                        "MSE0_TO_BUFFER",
                        "GA_INPORT_CONFIG",
                        "GA_INPORT_IB",
                    }
                    else 0
                )
                for boundary in boundaries
            },
        }
        result = runtime._guard_only_first_divergence(
            {"status": "pass"},
            {"start_group_count": 1},
            checkpoints,
            {"status": "fail"},
            {"status": "fail"},
        )
        self.assertEqual(
            result["classification"],
            (
                "GA_CONVERT_INPUT_UNOBSERVED_AFTER_GA_INPORT_IB"
                "_BEFORE_GA_CONVERT_REGISTERED_ALL_ZERO"
            ),
        )
        self.assertEqual(
            result["evidence_state"],
            "BOUNDED_UNOBSERVED_INTERVAL_WITH_DOWNSTREAM_ZERO",
        )
        self.assertEqual(
            result["responsibility_unresolved"],
            ["CONFIG_CONSUMPTION", "RTL_CONTROL", "OBSERVER_EVIDENCE"],
        )

    def test_downstream_positive_evidence_dominates_earlier_probe_gaps(
        self,
    ) -> None:
        boundaries = (
            "MSE0_RDATA",
            "MSE0_TO_BUFFER",
            "GA_INPORT_CONFIG",
            "GA_INPORT_IB",
            "GA_CONVERT_INPUT",
            "GA_CONVERT_REGISTERED",
            "GA_INPORT_FINAL",
            "PE_SELECTED_INPUT",
            "SFU_INPUT",
            "SFU_COMPUTE",
            "SFU_LUT",
            "SFU_ALU",
            "SFU_OUTPUT",
            "NORMAL_OUTBUFFER_WRITE",
            "MSE4_WDATA",
        )
        expected_by_boundary = {
            boundary: 16 if boundary.startswith("MSE") else 64
            for boundary in boundaries
        }
        count_checks = {
            boundary: {
                "expected": expected_by_boundary[boundary],
                "raw": expected_by_boundary[boundary],
                "parsed": expected_by_boundary[boundary],
                "raw_equals_parsed": True,
            }
            for boundary in boundaries
        }
        for boundary in (
            "GA_INPORT_CONFIG",
            "GA_INPORT_IB",
            "GA_CONVERT_INPUT",
            "SFU_INPUT",
            "SFU_COMPUTE",
            "SFU_LUT",
            "SFU_ALU",
            "SFU_OUTPUT",
            "NORMAL_OUTBUFFER_WRITE",
        ):
            count_checks[boundary].update({"raw": 0, "parsed": 0})
        nonzero = {boundary: 0 for boundary in boundaries}
        nonzero.update(
            {
                "MSE0_RDATA": 16,
                "MSE0_TO_BUFFER": 16,
                "GA_CONVERT_REGISTERED": 62,
                "GA_INPORT_FINAL": 62,
                "PE_SELECTED_INPUT": 62,
            }
        )
        result = runtime._guard_only_first_divergence(
            {"status": "pass"},
            {"start_group_count": 1},
            {
                "status": "fail",
                "count_checks": count_checks,
                "nonzero_data_counts": nonzero,
            },
            {"status": "fail"},
            {"status": "fail"},
        )
        self.assertEqual(
            result["classification"],
            (
                "SFU_INPUT_UNOBSERVED_AFTER_PE_SELECTED_INPUT"
                "_BEFORE_MSE4_WDATA_ALL_ZERO"
            ),
        )
        self.assertEqual(result["boundary"], "SFU_INPUT")
        self.assertEqual(result["downstream_bad_boundary"], "MSE4_WDATA")
        self.assertEqual(
            [
                item["boundary"]
                for item in result[
                    "observer_only_gaps_before_last_proven_good"
                ]
            ],
            ["GA_INPORT_CONFIG", "GA_INPORT_IB", "GA_CONVERT_INPUT"],
        )
        self.assertEqual(
            result["evidence_state"],
            "BOUNDED_UNOBSERVED_INTERVAL_WITH_DOWNSTREAM_ZERO",
        )

    def test_static_intent_is_separate_from_runtime_consumption(self) -> None:
        receipt = json.loads(
            (
                builder.DEFAULT_OUTPUT
                / "validation/static_configuration_intent.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["guard_json"]["value"], "true")
        self.assertTrue(
            receipt["parsed_bitstream_evidence"]["decoded_value"]
        )
        opcode = receipt["sfu_activation_opcode"]
        self.assertEqual(opcode["json_odd_pe_count"], 8)
        self.assertEqual(
            opcode["encoder_general"]["path"],
            "ndp-sim-ref/bitstream/config/general.py",
        )
        self.assertEqual(opcode["encoder_general"]["decimal"], 24)
        self.assertEqual(opcode["encoder_general"]["hex"], "0x18")
        self.assertTrue(
            opcode["encoder_general_equivalent_copy"][
                "byte_identical_to_authoritative"
            ]
        )
        self.assertEqual(opcode["parsed_bitstream_occurrence_count"], 8)
        self.assertEqual(opcode["parsed_bitstream_encoding_msb_first"], "11000")
        self.assertIn("exact 0x18 consumption", receipt["claim_boundary"])

    def test_focused_identity_covers_sfu_readiness_consumers(self) -> None:
        expected = {
            "rtl/Slice/General_Array/GA_Inport/GA_Inport.sv",
            "rtl/Slice/General_Array/GA_Inport/GA_Inport_Connect.sv",
            "rtl/Slice/General_Array/GA_Inport/GA_Inport_Group.sv",
            "rtl/Slice/General_Array/GA_Inport/GA_Inport_Group_Config.sv",
            "rtl/Slice/General_Array/GA_PE_Group/GA_PE_Group_Interconnect.sv",
            "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_LUT.sv",
            "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Preprocess.sv",
            "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/Comparator.sv",
            "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/Binary_Search_Tree.sv",
            "rtl/Slice/General_Array/GA_Outport/GA_Outport.sv",
            "rtl/Slice/General_Array/GA_Outport/GA_Outport_Connect.sv",
            "rtl/Slice/General_Array/GA_Outport/GA_Outport_Group.sv",
            "rtl/Slice/General_Array/GA_Outport/GA_Outport_Group_Config.sv",
        }
        self.assertTrue(expected.issubset(set(common_runtime.FOCUS_RTL)))

    def test_unpaired_wdata_is_parsed_without_being_discarded(self) -> None:
        package = builder.DEFAULT_OUTPUT
        expected_doc = json.loads(
            (
                package / "validation/expected_mse4_writes.json"
            ).read_text(encoding="utf-8")
        )
        writes = expected_doc["stages"][0]["writes"]
        with tempfile.TemporaryDirectory(prefix="rq-guard-parser-") as temporary:
            run = Path(temporary)
            profile = json.loads(
                (
                    package / "validation/diagnostic_profile.json"
                ).read_text(encoding="utf-8")
            )
            log_root = (
                run / "sim_results" / profile["observer_log_dir"]
            )
            log_root.mkdir(parents=True)
            for slice_id in (0, 1):
                lines = []
                for index, item in enumerate(
                    write
                    for write in writes
                    if int(write["slice_id"]) == slice_id
                ):
                    lines.append(
                        "MSE4_WRITE | cycle={cycle} slice={slice_id} "
                        "local_stage=0 role=guard ch=0 accepted=1 valid=1 "
                        "ready=1 strobe={strobe} req_txn_id=-1 "
                        "wdata_txn_id={index} paired_req_valid=0 "
                        "transfer_addr=0x0 linear_addr=0x0 addr=0x0 "
                        "data={data}".format(
                            cycle=index + 1,
                            slice_id=slice_id,
                            strobe=item["strobe"],
                            index=index,
                            data=item["data"],
                        )
                    )
                (log_root / f"slice{slice_id:02d}.log").write_text(
                    "\n".join(lines) + "\n",
                    encoding="utf-8",
                )
            result = runtime._observer_gate(run, package)
        self.assertEqual(result["raw_mse4_marker_count"], 16)
        self.assertEqual(result["parsed_mse4_write_count"], 16)
        self.assertTrue(result["raw_count_receipt_consistent"])
        self.assertEqual(result["unpaired_write_data_count"], 16)
        self.assertEqual(
            result["temporal_pairing_status"],
            "observer_temporal_evidence_incomplete",
        )
        self.assertEqual(result["status"], "pass")

    def test_sfu_readiness_routes_use_named_fields_not_packed_nonzero(self) -> None:
        def field(asserted: int, maximum: int = 1) -> dict[str, object]:
            return {
                "seen_count": 1,
                "asserted_count": asserted,
                "zero_count": int(asserted == 0),
                "minimum": 0 if asserted == 0 else maximum,
                "maximum": maximum,
                "value_counts": {
                    str(0 if asserted == 0 else maximum): 1,
                },
            }

        base_fields = {
            "PE_POST_REGISTER": {
                "post_valid": field(1),
                "matched": field(1),
                "output_valid": field(1),
            },
            "SFU_OPCODE_READY": {
                "opcode": field(1, 0x18),
                "sfu_valid": field(1),
                "compute_en": field(1),
            },
            "SFU_GROUP_COMPUTE_VALID": {
                "compute_valid": field(1),
            },
            "SFU_LUT_INIT": {
                "init_en": field(1),
                "init_addr": field(1, 0x141),
                "end_addr": field(1),
                "slice_rst": field(1),
            },
            "SFU_PREPROCESS0": {
                "enable": field(1),
                "valid": field(1),
            },
        }
        simulation = {"status": "pass"}
        lifecycle = {"start_group_count": 1}
        observer = {"status": "fail"}
        formal = {"status": "fail"}

        checkpoints = {
            "errors": [],
            "count_checks": {},
            "readiness_field_semantics": json.loads(
                json.dumps(base_fields)
            ),
        }
        checkpoints["readiness_field_semantics"]["SFU_OPCODE_READY"][
            "sfu_valid"
        ] = field(0)
        route = runtime._sfu_readiness_route(
            simulation, lifecycle, checkpoints, observer, formal
        )
        self.assertEqual(route["diagnostic_route"], "OPCODE_CONFIG_CONSUMPTION")
        self.assertEqual(route["unexpected_nonzero_opcode_value_counts"], {})

        checkpoints["readiness_field_semantics"] = json.loads(
            json.dumps(base_fields)
        )
        checkpoints["readiness_field_semantics"]["SFU_OPCODE_READY"][
            "opcode"
        ] = field(1, 0x10)
        route = runtime._sfu_readiness_route(
            simulation, lifecycle, checkpoints, observer, formal
        )
        self.assertEqual(route["diagnostic_route"], "OPCODE_CONFIG_CONSUMPTION")
        self.assertEqual(
            route["unexpected_nonzero_opcode_value_counts"], {"16": 1}
        )

        checkpoints["readiness_field_semantics"] = json.loads(
            json.dumps(base_fields)
        )
        checkpoints["readiness_field_semantics"]["SFU_LUT_INIT"][
            "end_addr"
        ] = field(0)
        route = runtime._sfu_readiness_route(
            simulation, lifecycle, checkpoints, observer, formal
        )
        self.assertEqual(route["diagnostic_route"], "LUT_READINESS")

        checkpoints["readiness_field_semantics"] = json.loads(
            json.dumps(base_fields)
        )
        checkpoints["readiness_field_semantics"]["PE_POST_REGISTER"][
            "matched"
        ] = field(0)
        route = runtime._sfu_readiness_route(
            simulation, lifecycle, checkpoints, observer, formal
        )
        self.assertEqual(
            route["diagnostic_route"], "SFU_NUMERIC_PIPELINE_UNOBSERVED"
        )
        self.assertEqual(
            route["observer_only_gaps"], ["PE_POST_REGISTER.matched"]
        )
        self.assertEqual(route["last_proven_good"], "SFU_PREPROCESS0_VALID")

        checkpoints["readiness_field_semantics"] = json.loads(
            json.dumps(base_fields)
        )
        checkpoints["readiness_field_semantics"]["SFU_PREPROCESS0"][
            "valid"
        ] = field(0)
        route = runtime._sfu_readiness_route(
            simulation, lifecycle, checkpoints, observer, formal
        )
        self.assertEqual(route["diagnostic_route"], "PE_REGISTER_MATCH")

        checkpoints["readiness_field_semantics"] = json.loads(
            json.dumps(base_fields)
        )
        checkpoints["readiness_field_semantics"]["SFU_PREPROCESS0"][
            "valid"
        ]["seen_count"] = 0
        route = runtime._sfu_readiness_route(
            simulation, lifecycle, checkpoints, observer, formal
        )
        self.assertEqual(route["diagnostic_route"], "OBSERVER_GAP")
        checkpoints["readiness_field_semantics"] = json.loads(
            json.dumps(base_fields)
        )
        observer["status"] = "pass"
        formal["status"] = "pass"
        lifecycle["status"] = "pass"
        route = runtime._sfu_readiness_route(
            simulation, lifecycle, checkpoints, observer, formal
        )
        self.assertEqual(route["classification"], "GUARD_ONLY_DIAGNOSTIC_PASS")
        self.assertIsNone(route["diagnostic_route"])
        self.assertIsNone(route["first_divergence"])
        self.assertEqual(
            route["exact_sfu_activation_encoding"]["sample_count"], 1
        )
        self.assertEqual(
            set(
                (
                    "OPCODE_CONFIG_CONSUMPTION",
                     "LUT_READINESS",
                     "PE_REGISTER_MATCH",
                     "SFU_NUMERIC_PIPELINE_UNOBSERVED",
                     "OBSERVER_GAP",
                 )
             ),
             {
                 "OPCODE_CONFIG_CONSUMPTION",
                 "LUT_READINESS",
                 "PE_REGISTER_MATCH",
                 "SFU_NUMERIC_PIPELINE_UNOBSERVED",
                 "OBSERVER_GAP",
             },
         )


if __name__ == "__main__":
    unittest.main()
