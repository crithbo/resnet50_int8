from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import build_requant_atomic_onecmd_server_test as builder
from tools import requant_atomic_server_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]


class RequantAtomicServerPackageTests(unittest.TestCase):
    def test_v2_frozen_identities_and_claim_boundary(self) -> None:
        identities = builder._verify_sources()
        self.assertEqual(
            identities["manifest"]["sha256"],
            "c6e50200d01209147851d990e824b3eead748ecfec9fb64aaaf6cd0cd97d4097",
        )
        contract = json.loads(builder.CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["active_slices"], [0, 1])
        self.assertTrue(contract["stock_tb_completion_compatible"])
        self.assertFalse(contract["counts_as_node0001_e4"])
        self.assertFalse(contract["counts_as_node0001_e5"])

    def test_planner_adapter_changes_only_ids(self) -> None:
        graph, receipt = builder._planner_graph()
        self.assertEqual(
            [item["id"] for item in graph["operators"]],
            ["op_w0_s00_guard", "op_w0_s00_round"],
        )
        self.assertEqual(
            {item["used_slices"] for item in graph["operators"]},
            {"0b0000000000000000000000000011"},
        )
        self.assertFalse(receipt["config_json_changed"])
        self.assertFalse(receipt["shapes_addresses_masks_or_tensor_ids_changed"])

    def test_observer_is_read_only_and_two_slice_scoped(self) -> None:
        tail = builder._observer_tail()
        active = "\n".join(
            line.split("//", 1)[0]
            for line in tail.splitlines()
            if not line.lstrip().startswith("//")
        ).lower()
        for token in ("force ", "deposit", "release ", "<="):
            self.assertNotIn(token, active)
        self.assertIn('+REQUANT_ATOMIC_PROBE', tail)
        self.assertIn("for (int sid = 0; sid < 2; sid++)", tail)
        self.assertIn("local_wdata_hs[0][sid][4][ch]", tail)
        self.assertIn("MSE4_WRITE", tail)

    def test_observer_gate_accepts_per_slice_logs_without_fake_global_order(self) -> None:
        package = builder.DEFAULT_OUTPUT
        expected = json.loads(
            (
                package / "validation/expected_mse4_writes.json"
            ).read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            probe = run / "sim_results/requant_atomic_probe"
            probe.mkdir(parents=True)
            by_slice = {0: [], 1: []}
            for stage in expected["stages"]:
                for item in stage["writes"]:
                    by_slice[item["slice_id"]].append(item)
            for slice_id, writes in by_slice.items():
                lines = []
                for cycle, item in enumerate(writes, 1):
                    role = (
                        f"{item['role']:>14}"
                        if item["role"] == "guard"
                        else item["role"]
                    )
                    lines.append(
                        "0 | MSE4_WRITE | "
                        f"cycle={cycle} slice={slice_id} "
                        f"local_stage={item['stage_index']} role={role} "
                        "ch=0 accepted=1 valid=1 ready=1 "
                        f"strobe={item['strobe']} "
                        f"addr={item['word_address_128b']} data={item['data']}"
                    )
                (probe / f"slice{slice_id:02d}.log").write_text(
                    "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
                )
            report = runtime._observer_gate(run, package)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["actual_write_count"], 20)
        self.assertEqual(report["raw_mse4_marker_count"], 20)
        self.assertEqual(report["parsed_mse4_write_count"], 20)
        self.assertTrue(report["raw_count_receipt_consistent"])
        self.assertFalse(report["address_comparison_valid"])
        self.assertEqual(
            report["role_counts"], {"guard": 16, "round_saturate": 4}
        )

    def test_observer_gate_fails_if_raw_marker_cannot_be_parsed(self) -> None:
        package = builder.DEFAULT_OUTPUT
        expected = json.loads(
            (
                package / "validation/expected_mse4_writes.json"
            ).read_text(encoding="utf-8")
        )
        by_slice = {0: [], 1: []}
        for stage in expected["stages"]:
            for item in stage["writes"]:
                by_slice[int(item["slice_id"])].append(item)
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            probe = run / "sim_results/requant_atomic_probe"
            probe.mkdir(parents=True)
            for slice_id, writes in by_slice.items():
                lines = [
                    (
                        "0 | MSE4_WRITE | "
                        f"cycle={cycle} slice={slice_id} "
                        f"local_stage={item['stage_index']} role={item['role']} "
                        "ch=0 accepted=1 valid=1 ready=1 "
                        f"strobe={item['strobe']} "
                        f"addr={item['word_address_128b']} data={item['data']}"
                    )
                    for cycle, item in enumerate(writes, 1)
                ]
                if slice_id == 0:
                    lines[0] = lines[0].replace("data=0x", "payload=0x", 1)
                (probe / f"slice{slice_id:02d}.log").write_text(
                    "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
                )
            report = runtime._observer_gate(run, package)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["raw_mse4_marker_count"], 20)
        self.assertEqual(report["parsed_mse4_write_count"], 19)
        self.assertFalse(report["raw_count_receipt_consistent"])

    def test_built_package_is_exact_and_diagnostic_only(self) -> None:
        report = builder.validate_package(builder.DEFAULT_OUTPUT)
        self.assertEqual(report["status"], "package_preflight_passed")
        self.assertTrue(report["zip_exact_set"])
        self.assertEqual(
            report["bootstrap_immutability"]["status"], "pass"
        )
        self.assertTrue(
            report["bootstrap_immutability"][
                "exact_path_size_sha_unchanged"
            ]
        )
        manifest = json.loads(
            (builder.DEFAULT_OUTPUT / builder.MANIFEST_NAME).read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(manifest["candidate_release"])
        self.assertFalse(manifest["counts_as_node0001_e4"])
        self.assertFalse(manifest["counts_as_node0001_e5"])
        self.assertEqual(manifest["dynamic_baseline"], "NO_DYNAMIC_BASELINE")
        self.assertEqual(
            manifest["execution_contract"]["total_accepted_mse4_write_count"], 20
        )
        self.assertEqual(manifest["execution_contract"]["repeat_num"], 2)
        self.assertEqual(
            manifest["native_rebuild"]["sca_preload_count"], 6
        )
        self.assertEqual(
            manifest["native_rebuild"]["sca_d_readback_count"], 4
        )
        freeze = manifest["semantic_freeze_against_atomic_v1"]
        self.assertTrue(freeze["semantic_payload_byte_identical"])
        for category in (
            "operator_json",
            "mapping_review",
            "parsed_bitstream",
            "bitstream_64b",
            "bitstream_128b",
            "execplan",
            "golden",
            "expected_writes",
        ):
            self.assertGreater(freeze["categories"][category], 0)
        self.assertTrue(
            all(
                item["v1_sha256"] == item["v2_sha256"]
                and item["byte_identical"]
                for item in freeze["files"].values()
            )
        )
        self.assertTrue(
            all(
                item["normalized_equal"]
                for item in freeze[
                    "sca_identity_normalization"
                ].values()
            )
        )
        self.assertNotIn(
            True,
            [
                "rtl" in {part.lower() for part in Path(relative).parts}
                for relative in manifest["files"]
            ],
        )
        with zipfile.ZipFile(builder.DEFAULT_OUTPUT.with_suffix(".zip")) as archive:
            self.assertFalse(
                any(
                    "rtl" in {part.lower() for part in Path(name).parts}
                    for name in archive.namelist()
                )
            )

    def test_server_entry_is_one_command_and_does_not_modify_tb_or_rtl(self) -> None:
        script = (
            builder.DEFAULT_OUTPUT / "PREPARE_AND_RUN.sh"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX".count("\n"), 0
        )
        self.assertIn("DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0", script)
        export_at = script.index("export PYTHONDONTWRITEBYTECODE=1")
        first_python_at = script.index("python3")
        self.assertLess(export_at, first_python_at)
        self.assertIn('VCS_EXTRA_OPTS="+incdir+${ndp_root}"', script)
        self.assertIn("+REQUANT_ATOMIC_PROBE", script)
        self.assertNotRegex(script, r"\b(?:sed|perl)\b.*tb_NDP_Top_new_phy")
        self.assertNotRegex(script, r"\bcp\b.*tb_NDP_Top_new_phy")
        self.assertNotIn("force ", script.lower())
        self.assertNotIn("deposit", script.lower())

    def test_runtime_disables_bytecode_before_package_local_import(self) -> None:
        source = (
            builder.DEFAULT_OUTPUT
            / "package_tools/requant_atomic_server_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertLess(
            source.index("sys.dont_write_bytecode = True"),
            source.index("import requant_node0001_server_runtime as common"),
        )
        self.assertIn("Python bytecode payload is forbidden", source)

    def test_fresh_extracted_runtime_entry_preserves_exact_tree(self) -> None:
        report = builder._validate_bootstrap_immutability(
            builder.DEFAULT_OUTPUT
        )
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["fresh_zip_extraction"])
        self.assertTrue(report["preflight_output_outside_package"])
        self.assertTrue(report["exact_path_size_sha_unchanged"])
        self.assertEqual(
            report["package_file_count_before"],
            report["package_file_count_after"],
        )
        self.assertEqual(
            report["package_size_bytes_before"],
            report["package_size_bytes_after"],
        )
        self.assertEqual(
            report["package_tree_sha256_before"],
            report["package_tree_sha256_after"],
        )
        self.assertFalse(report["pycache_or_pyc_allowlisted"])


if __name__ == "__main__":
    unittest.main()
