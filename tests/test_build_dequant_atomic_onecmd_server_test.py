from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import build_dequant_atomic_onecmd_server_test as builder
from tools import dequant_atomic_server_runtime as runtime
from tools import requant_node0001_server_runtime as common_runtime


class DequantAtomicServerPackageTests(unittest.TestCase):
    def test_frozen_sources_and_claim_boundary(self) -> None:
        identities = builder._verify_sources()
        self.assertEqual(
            identities["config"]["sha256"],
            "c974e9ca8bdd8635a2cf804bbb90b7c72aae2265084dd4256e4fa267da846718",
        )
        self.assertEqual(
            identities["manifest"]["sha256"],
            "d2d514fd81e0cdcbd439a6b7a83365dcb5cee0891a8be98181c2220a97fac708",
        )
        contract = json.loads(builder.CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["active_slices"], [0, 1])
        self.assertEqual(contract["repeat_num"], 1)
        self.assertFalse(contract["counts_as_node0077_e4"])
        self.assertFalse(contract["counts_as_node0077_e5"])

    def test_planner_adapter_is_transport_only(self) -> None:
        graph, receipt = builder._planner_graph()
        operator = graph["operators"][0]
        self.assertEqual(operator["id"], "op0")
        self.assertEqual(
            operator["used_slices"],
            "0b0000000000000000000000000011",
        )
        self.assertFalse(receipt["semantic_json_or_tensor_changed"])
        self.assertEqual(
            receipt["frozen_config_sha256"],
            "c974e9ca8bdd8635a2cf804bbb90b7c72aae2265084dd4256e4fa267da846718",
        )
        self.assertEqual(
            receipt["upstream_semantic_change_from_atomic_v1"],
            {
                "field": "buffer_loop_configs.GROUP2.ROW_LC.end",
                "old": 1,
                "new": 4,
                "reason": "supply four 16-byte rows for one 64-byte D transaction",
            },
        )

    def test_built_package_is_exact_and_diagnostic_only(self) -> None:
        report = builder.validate_package(builder.DEFAULT_OUTPUT)
        self.assertEqual(report["status"], "validated")
        self.assertTrue(report["zip_audit"]["exact_set"])
        self.assertTrue(
            report["bootstrap_immutability"]["exact_path_size_sha_unchanged"]
        )
        self.assertTrue(report["probe_transaction"]["restored_byte_exact"])
        self.assertTrue(report["probe_transaction"]["package_tree_unchanged"])
        manifest = json.loads(
            (builder.DEFAULT_OUTPUT / runtime.MANIFEST_NAME).read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(manifest["candidate_release"])
        self.assertFalse(manifest["counts_as_node0077_e4"])
        self.assertFalse(manifest["counts_as_node0077_e5"])
        self.assertEqual(manifest["execution_contract"]["stage_count"], 1)
        self.assertEqual(manifest["execution_contract"]["repeat_num"], 1)
        self.assertEqual(
            manifest["execution_contract"]["physical_slice_instances"],
            [0, 1],
        )
        self.assertEqual(
            manifest["execution_contract"]["accepted_mse4_write_count"], 8
        )
        self.assertEqual(manifest["execution_contract"]["group2_row_lc_end"], 4)
        self.assertEqual(manifest["native_rebuild"]["sca_preload_count"], 4)
        self.assertEqual(manifest["native_rebuild"]["sca_d_readback_count"], 2)
        self.assertFalse(
            any(
                "rtl" in {part.lower() for part in Path(relative).parts}
                for relative in manifest["files"]
            )
        )
        with zipfile.ZipFile(
            builder.DEFAULT_OUTPUT.with_suffix(".zip")
        ) as archive:
            self.assertFalse(
                any(
                    "rtl" in {part.lower() for part in Path(name).parts}
                    for name in archive.namelist()
                )
            )

    def test_server_entry_and_python_bootstrap_are_safe(self) -> None:
        package = builder.DEFAULT_OUTPUT
        script = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        export_at = script.index("export PYTHONDONTWRITEBYTECODE=1")
        first_python = script.index("python3 ")
        self.assertLess(export_at, first_python)
        self.assertIn("DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0", script)
        self.assertIn("+DEQUANT_ATOMIC_PROBE", script)
        self.assertNotRegex(script, r"\b(?:sed|perl)\b.*tb_NDP_Top_new_phy")
        self.assertNotRegex(script, r"\bcp\b.*tb_NDP_Top_new_phy")
        runtime_text = (
            package / "package_tools/dequant_atomic_server_runtime.py"
        ).read_text(encoding="utf-8")
        flag_at = runtime_text.index("sys.dont_write_bytecode = True")
        local_import_at = runtime_text.index(
            "import requant_node0001_server_runtime"
        )
        self.assertLess(flag_at, local_import_at)

    def test_observer_is_read_only_and_two_slice_scoped(self) -> None:
        tail = builder._observer_tail()
        active = "\n".join(
            line.split("//", 1)[0]
            for line in tail.splitlines()
            if not line.lstrip().startswith("//")
        ).lower()
        for token in ("force ", "deposit", "release ", "<="):
            self.assertNotIn(token, active)
        self.assertIn('$test$plusargs("DEQUANT_ATOMIC_PROBE")', tail)
        self.assertIn("for (int sid = 0; sid < 2; sid++)", tail)
        self.assertIn("for (genvar dq_sid = 0; dq_sid < 2; dq_sid++)", tail)
        self.assertNotIn("slice_group_gen[sid]", tail)
        self.assertIn("local_wdata_hs[0][sid][4][ch]", tail)
        self.assertIn("MSE4_WRITE", tail)
        self.assertIn("transfer_addr_nooff", tail)
        self.assertIn("linear_addr=0x%0h", tail)
        self.assertIn("post_remap_addr=0x%0h", tail)
        self.assertIn("outstanding_addr_count=%0d", tail)
        self.assertIn("outstanding_data_count=%0d", tail)
        self.assertEqual(
            common_runtime.validate_observer_xmr_elaboration(tail)["status"],
            "pass",
        )

    def test_observer_lifecycle_and_formal_gates_accept_exact_evidence(self) -> None:
        package = builder.DEFAULT_OUTPUT
        expected = json.loads(
            (package / "validation/expected_mse4_writes.json").read_text(
                encoding="utf-8"
            )
        )["writes"]
        with tempfile.TemporaryDirectory(prefix="dq-at-gates-") as temporary:
            run = Path(temporary)
            for slice_id in (0, 1):
                probe = (
                    run
                    / f"sim_results/dequant_atomic_probe/slice{slice_id:02d}.log"
                )
                probe.parent.mkdir(parents=True, exist_ok=True)
                lines = []
                for cycle, item in enumerate(
                    [value for value in expected if value["slice_id"] == slice_id],
                    1,
                ):
                    lines.append(
                        "0 | MSE4_WRITE | "
                        f"cycle={cycle} slice={slice_id} local_stage=0 "
                        "role=dequantize ch=0 accepted=1 valid=1 ready=1 "
                        f"strobe={item['strobe']} "
                        f"transfer_addr=0x{cycle - 1:x} "
                        f"linear_addr={item['word_address_128b']} "
                        f"post_remap_addr=0x{0x400000 + cycle:x} "
                        f"data={item['data']}"
                    )
                lines.append(
                    "0 | STAGE_FINISH | "
                    f"cycle=99 slice={slice_id} local_stage=0 "
                    "accepted_req_count=4 accepted_wdata_count=4 "
                    "accepted_write_count=4 outstanding_addr_count=0 "
                    "outstanding_data_count=0"
                )
                probe.write_text(
                    "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
                )
                events = (
                    run / f"sim_results/sem_events/slice{slice_id}/sem_events.log"
                )
                events.parent.mkdir(parents=True, exist_ok=True)
                events.write_text(
                    (
                        f"{100 + slice_id} | Start Comp |\n"
                        f"{200 + slice_id} | Comp Finish |\n"
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                formal = (
                    run
                    / "sim_results/formal_readback"
                    / f"op0_matrixD_slice{slice_id}.txt"
                )
                formal.parent.mkdir(parents=True, exist_ok=True)
                formal.write_bytes(
                    (package / f"golden/slice{slice_id:02d}_128b.txt").read_bytes()
                )
            observer = runtime._observer_gate(run, package)
            lifecycle = runtime._lifecycle_gate(run)
            formal = runtime._formal_gate(run, package)
        self.assertEqual(observer["status"], "pass")
        self.assertEqual(observer["actual_write_count"], 8)
        self.assertEqual(observer["finish_drain_status"], "pass")
        self.assertFalse(
            observer["address_domain"]["post_remap_compared_to_linear"]
        )
        self.assertEqual(lifecycle["status"], "pass")
        self.assertEqual(formal["status"], "pass")
        self.assertTrue(formal["all_lines_non_x"])
        self.assertTrue(formal["all_bit_exact"])

    def test_xmr_gate_rejects_old_process_index_but_allows_proxy_array(self) -> None:
        invalid = """
always @(posedge clk)
  for (int sid = 0; sid < 2; sid++)
    if (top.slice_group_gen[sid].u_mse.signal) sample[sid] = 1'b1;
"""
        with self.assertRaises(common_runtime.RequantRuntimeError):
            common_runtime.validate_observer_xmr_elaboration(invalid)
        valid = """
logic proxy [0:1][0:1];
generate
  for (genvar dq_sid = 0; dq_sid < 2; dq_sid++) begin : DQ_PROXY
    assign proxy[dq_sid][0] =
      top.slice_group_gen[dq_sid].MSE_INST[4].signal;
  end
endgenerate
always @(posedge clk)
  for (int sid = 0; sid < 2; sid++)
    for (int ch = 0; ch < 2; ch++) sample[sid][ch] = proxy[sid][ch];
"""
        report = common_runtime.validate_observer_xmr_elaboration(valid)
        self.assertEqual(report["status"], "pass")

    def test_identity_gate_uses_boolean_facts_not_status_literal(self) -> None:
        identity = {
            "status": "stock_rtl_and_transactional_tb_probe_verified",
            "functional_rtl_unchanged": True,
            "tb_probe_transactionally_restored": True,
            "tb_probe_verified_immediately_before_compile": True,
            "package_manifest_stable": True,
            "server_command_stable": True,
            "installed_namespace_stable": True,
            "focused_rtl": {"rtl/a.sv": True},
            "support_files": {"native_return_observer.svh": True},
            "phases": [
                "pre_install",
                "post_probe_install",
                "post_compile",
                "post_run",
                "post_restore",
            ],
        }
        gate = runtime._identity_gate(identity)
        self.assertEqual(gate["status"], "pass")
        self.assertTrue(gate["identity_status_string_is_not_a_gate"])
        identity["support_files"]["native_return_observer.svh"] = False
        self.assertEqual(runtime._identity_gate(identity)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
