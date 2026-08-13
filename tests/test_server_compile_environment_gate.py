from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "server_compile_environment_gate.py"
SPEC = importlib.util.spec_from_file_location("server_compile_environment_gate", TOOL_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


MODULES = ["DW_ecc", "DW_sync", "DW_lod", "DW_fifo_s1_sf"]
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


class CompileProviderClosureTests(unittest.TestCase):
    def _request(self, provider: Path, package: str = "pkg-a", modules=None):
        modules = modules or MODULES
        provider_text = str(provider)
        return {
            "schema": gate.REQUEST_SCHEMA,
            "package_id": package,
            "family": "fixture.family",
            "execution_group": "fixture-host-boot-1",
            "actual_compile": {
                "cwd": str(provider.parent),
                "argv": [
                    sys.executable,
                    "-c",
                    "pass",
                    "-y",
                    provider_text,
                    f"+incdir+{provider_text}",
                ],
            },
            "semantic_identity": {
                "selected_makefile_sha256": SHA_A,
                "recursive_source_identity_sha256": SHA_B,
                "top_filelist_sha256": SHA_C,
                "compile_environment": {"SYNOPSYS": "/tools/Synopsys/dc2023/syn/V-2023.12-SP3"},
            },
            "runtime_context": {
                "execution_epoch": "epoch-1",
                "boot_id": "boot-1",
                "hostname": "server-a",
            },
            "provider_sets": [
                {
                    "id": "designware-required-modules",
                    "required_modules": modules,
                    "candidates": [
                        {
                            "id": "designware-sim-ver",
                            "kind": "source_directory",
                            "path": provider_text,
                            "argv_bindings": [
                                {"form": "pair", "option": "-y"},
                                {"form": "plus_prefix", "prefix": "+incdir+"},
                            ],
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def _write_modules(root: Path, names):
        root.mkdir(parents=True)
        for name in names:
            (root / f"{name}.v").write_text(f"module {name}; endmodule\n", encoding="utf-8")

    @staticmethod
    def _valid_probe(initial):
        return {
            "schema": gate.PROBE_RECEIPT_SCHEMA,
            "semantic_fingerprint_sha256": initial["semantic_fingerprint_sha256"],
            "provider_state_sha256": initial["provider_state_sha256"],
            "required_modules": MODULES,
            "actual_probe_argv": ["vcs", "provider_probe.sv"],
            "compile_exit": 0,
            "unresolved_modules": [],
            "dut_compile_invoked": False,
            "simulation_invoked": False,
            "log_truncated": False,
            "pass": True,
            "errors": [],
        }

    def test_source_provider_closure_is_ready_without_probe(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "sim_ver"
            self._write_modules(provider, MODULES)
            result = gate.attest(self._request(provider))
            self.assertTrue(result["pass"], result["errors"])
            self.assertTrue(result["source_provider_closure"])
            self.assertEqual(result["disposition"], "MODULE_PROVIDER_CLOSURE_READY")
            self.assertFalse(result["compile_invoked"])

    def test_request_and_receipt_validate_against_public_schema(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "sim_ver"
            self._write_modules(provider, MODULES)
            request = self._request(provider)
            receipt = gate.attest(request)
            schema = json.loads((ROOT / "schemas" / "server_compile_environment_gate_v1.schema.json").read_text(encoding="utf-8"))
            validator = Draft202012Validator(schema)
            self.assertEqual(list(validator.iter_errors(request)), [])
            self.assertEqual(list(validator.iter_errors(receipt)), [])

    def test_missing_named_path_is_record_only_and_requires_probe(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "missing_sim_ver"
            result = gate.attest(self._request(provider))
            self.assertFalse(result["pass"])
            self.assertEqual(result["disposition"], "PROVIDER_PROBE_REQUIRED")
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["warnings"][0]["code"], "NAMED_PROVIDER_PATH_ABSENT_RECORD_ONLY")
            self.assertEqual(result["unresolved_before_probe"], sorted(MODULES))

    def test_v88_known_good_never_promotes_current_missing_path(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "missing_sim_ver"
            request = self._request(provider, "v89")
            first = gate.attest(request)
            request["known_good_compile"] = {
                "compile_exit": 0,
                "resolved_modules": MODULES,
                "semantic_fingerprint_sha256": first["semantic_fingerprint_sha256"],
            }
            result = gate.attest(request)
            self.assertFalse(result["pass"])
            self.assertTrue(result["known_good_comparison"]["required_modules_resolved"])
            self.assertEqual(result["disposition"], "PROVIDER_PROBE_REQUIRED")

    def test_exact_current_probe_closes_unenumerated_provider(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "missing_sim_ver"
            request = self._request(provider)
            initial = gate.attest(request)
            request["production_probe_receipt"] = self._valid_probe(initial)
            result = gate.attest(request)
            self.assertTrue(result["pass"], result["errors"])
            self.assertTrue(result["production_probe_valid"])

    def test_stale_probe_semantic_fingerprint_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "missing_sim_ver"
            request = self._request(provider)
            initial = gate.attest(request)
            probe = self._valid_probe(initial)
            probe["semantic_fingerprint_sha256"] = "0" * 64
            request["production_probe_receipt"] = probe
            result = gate.attest(request)
            self.assertFalse(result["pass"])
            self.assertIn("PROVIDER_PROBE_SEMANTIC_FINGERPRINT_INVALID", [e["code"] for e in result["errors"]])

    def test_unbound_provider_is_blocking_even_when_source_exists(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "sim_ver"
            self._write_modules(provider, MODULES)
            request = self._request(provider)
            request["actual_compile"]["argv"] = [sys.executable, "-c", "pass"]
            result = gate.attest(request)
            self.assertFalse(result["pass"])
            self.assertIn("PROVIDER_NOT_BOUND_TO_ACTUAL_ARGV", [e["code"] for e in result["errors"]])

    def test_make_wrapper_requires_exact_dry_run_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "sim_ver"
            self._write_modules(provider, MODULES)
            request = self._request(provider)
            provider_text = str(provider)
            request["actual_compile"]["argv"] = ["timeout", "2h", "make", "-f", "Makefile.tb", "compile", "DUMP_FSDB=0"]
            unresolved = gate.attest(request)
            self.assertIn("COMPILE_WRAPPER_RESOLUTION_ABSENT", [e["code"] for e in unresolved["errors"]])
            output = Path(td) / "make-dry-run.txt"
            compiler = str(Path(sys.executable).resolve())
            output.write_text(f'cd /tmp && "{compiler}" -c pass -y "{provider_text}" "+incdir+{provider_text}"\n', encoding="utf-8")
            request["actual_compile"]["resolver"] = {
                "method": "make_just_print",
                "argv": ["make", "-n", "-f", "Makefile.tb", "compile", "DUMP_FSDB=0"],
                "stdout_path": str(output),
                "stdout_sha256": gate._sha256_file(output),
                "compiler_basename": Path(sys.executable).name,
                "exit_code": 0,
            }
            resolved = gate.attest(request)
            self.assertTrue(resolved["pass"], resolved["errors"])

    def test_runtime_probe_executes_only_bound_module_lookup_command(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            provider = root / "missing_sim_ver"
            request = self._request(provider)
            work = root / "runtime" / "probe"
            work.mkdir(parents=True)
            source = work / "provider_probe.sv"
            log = work / "provider_probe.log"
            request["probe_spec"] = {
                "runtime_root": str(root / "runtime"),
                "cwd": str(work),
                "source_path": str(source),
                "log_path": str(log),
                "argv": [
                    sys.executable,
                    "-c",
                    "print('provider probe ok')",
                    "-y",
                    str(provider),
                    f"+incdir+{provider}",
                    str(source),
                ],
            }
            receipt = gate.run_provider_probe(request)
            self.assertTrue(receipt["pass"], receipt["errors"])
            self.assertEqual(receipt["compile_exit"], 0)
            self.assertFalse(receipt["dut_compile_invoked"])
            self.assertFalse(receipt["simulation_invoked"])

    def test_runtime_probe_unresolved_log_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            provider = root / "missing_sim_ver"
            request = self._request(provider)
            work = root / "runtime" / "probe"
            work.mkdir(parents=True)
            source = work / "provider_probe.sv"
            request["probe_spec"] = {
                "runtime_root": str(root / "runtime"),
                "cwd": str(work),
                "source_path": str(source),
                "log_path": str(work / "provider_probe.log"),
                "argv": [
                    sys.executable,
                    "-c",
                    "import sys; print('Error-[URMI] Unresolved modules'); sys.exit(2)",
                    "-y",
                    str(provider),
                    f"+incdir+{provider}",
                    str(source),
                ],
            }
            receipt = gate.run_provider_probe(request)
            self.assertFalse(receipt["pass"])
            self.assertEqual(receipt["compile_exit"], 2)
            self.assertTrue(receipt["unresolved_modules"])

    def test_reuse_requires_exact_runtime_and_provider_projection(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "sim_ver"
            self._write_modules(provider, MODULES)
            request = self._request(provider, "gap")
            prior = gate.attest(request)
            second = self._request(provider, "native")
            reused = gate.reuse_receipt(prior, second)
            self.assertTrue(reused["reuse_applicable"])
            second["runtime_context"]["boot_id"] = "boot-2"
            changed = gate.reuse_receipt(prior, second)
            self.assertFalse(changed["reuse_applicable"])

    def test_failed_provider_probe_reuses_only_for_exact_projection(self):
        with tempfile.TemporaryDirectory() as td:
            provider = Path(td).resolve() / "missing_sim_ver"
            first_request = self._request(provider, "gap")
            initial = gate.attest(first_request)
            failed_probe = self._valid_probe(initial)
            failed_probe.update(
                {
                    "compile_exit": 2,
                    "unresolved_modules": ["Error-[URMI] Unresolved modules"],
                    "pass": False,
                }
            )
            first_request["production_probe_receipt"] = failed_probe
            blocked = gate.attest(first_request)
            self.assertEqual(blocked["disposition"], "BLOCKED_BEFORE_PROVIDER_PROBE")
            second_request = self._request(provider, "native")
            reused = gate.reuse_receipt(blocked, second_request)
            self.assertTrue(reused["reuse_applicable"])
            self.assertEqual(reused["disposition"], "BLOCKED_BY_REUSED_PROVIDER_RECEIPT")

    def test_first_error_ignores_platform_prose_and_selects_urmi(self):
        log = (ROOT / "fixtures" / "server_compile_environment_gate_v1" / "misleading_platform_then_urmi.log").read_text(encoding="utf-8")
        result = gate.extract_first_error(log)
        self.assertTrue(result["found"])
        self.assertEqual(result["line"], "Error-[URMI] Unresolved modules")
        self.assertEqual(result["line_number"], 5)

    def _write_core(self, root: Path, argv, *, stale=False, omit=()):
        rels = {
            "actual_compile_sim_argv": "evidence/ACTUAL_COMPILE_SIM_ARGV.json",
            "sim_exit_receipt": "evidence/observer/SIM_EXIT_RECEIPT.json",
            "compile_core": "evidence/compile_rootcause/COMPILE_CORE.json",
            "return_core_manifest": "RETURN_CORE_MANIFEST.json",
        }
        documents = {
            "actual_compile_sim_argv": {"compile": {"cwd": "/run/compile", "argv": argv + (["DUMP_FSDB=1"] if stale else [])}},
            "sim_exit_receipt": {"simulation_started": False, "simulation_exit": 125},
            "compile_core": {"compile_exit": 2, "first_error": {"found": True, "line": "Error-[URMI] Unresolved modules"}},
        }
        for role, doc in documents.items():
            if role in omit:
                continue
            path = root / rels[role]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc) + "\n", encoding="utf-8")
        members = []
        for role, rel in rels.items():
            if role == "return_core_manifest" or role in omit:
                continue
            path = root / rel
            members.append({"path": rel, "bytes": path.stat().st_size, "sha256": gate._sha256_file(path)})
        (root / rels["return_core_manifest"]).write_text(json.dumps({"members": members}) + "\n", encoding="utf-8")
        return rels

    @staticmethod
    def _core_request(root: Path, rels, argv):
        return {
            "schema": gate.CORE_REQUEST_SCHEMA,
            "return_root": str(root),
            "required_members": rels,
            "expected": {"package_id": "native-p45", "execution_id": "run-1", "compile_cwd": "/run/compile", "compile_argv": argv},
        }

    def test_compile_failure_core_positive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            argv = ["vcs", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"]
            rels = self._write_core(root, argv)
            result = gate.audit_compile_failure_core(self._core_request(root, rels, argv))
            self.assertTrue(result["pass"], result["errors"])

    def test_p45_stale_argv_and_incomplete_core_are_aggregated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            argv = ["vcs", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"]
            rels = self._write_core(root, argv, stale=True, omit=("sim_exit_receipt", "compile_core"))
            result = gate.audit_compile_failure_core(self._core_request(root, rels, argv))
            codes = [e["code"] for e in result["errors"]]
            self.assertIn("RETURNED_ACTUAL_COMPILE_ARGV_STALE", codes)
            self.assertEqual(codes.count("REQUIRED_COMPILE_CORE_MEMBER_ABSENT"), 2)
            self.assertIn("RETURN_CORE_MANIFEST_EXACT_SET_MISMATCH", codes)
            self.assertTrue(result["all_errors_collected"])


if __name__ == "__main__":
    unittest.main()
