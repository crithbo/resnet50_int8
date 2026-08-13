from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from tools.validate_server_package_local_hdl_lexical import scan_hdl, validate_tree, validate_zip


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/server_package_local_hdl_lexical_validation_v1.schema.json"
DISPATCH = ROOT / "contracts/server_package_local_hdl_lexical_gate_dispatch_v1.json"


class PackageLocalHdlLexicalTests(unittest.TestCase):
    def _zip(self, directory: Path, members: dict[str, str]) -> Path:
        target = directory / "candidate.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, text in members.items():
                archive.writestr(f"pkg/{name}", text)
        return target

    def test_positive_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = validate_zip(
                self._zip(
                    Path(directory),
                    {
                        "tb_probe/probe.svh": (
                            "module probe;\n"
                            "  integer event_seq_id;\n"
                            "  logic [3:0] value_now, value_next;\n"
                            "  task automatic emit(input string candidate); endtask\n"
                            "  initial event_seq_id = 0;\n"
                            "endmodule\n"
                        )
                    },
                )
            )
            self.assertTrue(report["pass"], report["errors"])
            self.assertEqual(report["reserved_identifier_violations"], [])
            if jsonschema is not None:
                jsonschema.validate(report, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_staging_tree_and_final_zip_same_negative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            tree = base / "pkg"
            probe = tree / "tb_probe" / "probe.svh"
            probe.parent.mkdir(parents=True)
            probe.write_text("module p; integer sequence; endmodule\n", encoding="utf-8")
            tree_report = validate_tree(tree)
            zip_report = validate_zip(
                self._zip(base, {"tb_probe/probe.svh": probe.read_text(encoding="utf-8")})
            )
            self.assertFalse(tree_report["pass"])
            self.assertFalse(zip_report["pass"])
            self.assertEqual(tree_report["input"]["kind"], "tree")
            self.assertEqual(zip_report["input"]["kind"], "zip")
            self.assertEqual(
                [item["identifier"] for item in tree_report["reserved_identifier_violations"]],
                [item["identifier"] for item in zip_report["reserved_identifier_violations"]],
            )
            if jsonschema is not None:
                schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
                jsonschema.validate(tree_report, schema)
                jsonschema.validate(zip_report, schema)

    def test_real_s1_reserved_sequence_negative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = validate_zip(
                self._zip(
                    Path(directory),
                    {"tb_probe/fsdb_smoke_event_probe.svh": "module p; integer sequence; endmodule\n"},
                )
            )
            self.assertFalse(report["pass"])
            self.assertEqual(
                [item["identifier"] for item in report["reserved_identifier_violations"]],
                ["sequence"],
            )

    def test_aggregates_multiple_members_and_roles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = validate_zip(
                self._zip(
                    Path(directory),
                    {
                        "a.sv": "module p; logic property; endmodule\n",
                        "b.svh": "module m(input wire sequence); integer checker; endmodule\n",
                    },
                )
            )
            self.assertFalse(report["pass"])
            self.assertEqual(
                {item["identifier"] for item in report["reserved_identifier_violations"]},
                {"property", "sequence", "checker"},
            )
            self.assertEqual(report["hdl_member_count"], 2)

    def test_comments_strings_and_escaped_identifiers_are_not_false_positives(self) -> None:
        text = r'''
module p;
  // integer sequence;
  string message = "integer property;";
  integer \sequence ;
endmodule
'''
        self.assertEqual(scan_hdl(text, "pkg/p.sv"), [])

    def test_legal_sequence_construct_name_passes(self) -> None:
        text = "sequence valid_sequence; 1'b1; endsequence\n"
        self.assertEqual(scan_hdl(text, "pkg/assertions.sv"), [])

    def test_unsafe_or_duplicate_zip_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bad.zip"
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("pkg/a.sv", "module a; endmodule\n")
                archive.writestr("pkg/a.sv", "module b; endmodule\n")
            report = validate_zip(target)
            self.assertFalse(report["pass"])
            self.assertTrue(any("duplicate" in item for item in report["errors"]))

    def test_no_hdl_is_non_applicable_for_this_lexical_subgate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = validate_zip(self._zip(Path(directory), {"README.txt": "no HDL\n"}))
            self.assertTrue(report["pass"])
            self.assertFalse(report["applicable"])
            self.assertEqual(report["hdl_member_count"], 0)

    def test_dispatch_preserves_broader_frontend_conjunction(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(
            dispatch["classification"],
            "IMPLEMENTATION_HARDENING_EXISTING_RULE_SEMANTICS",
        )
        self.assertIn(
            "existing focused or production-compatible frontend pass on exact changed/required package-local HDL",
            dispatch["required_conjunction"],
        )
        self.assertIn("--tree", dispatch["commands"]["cheap_staging_aggregate"])
        self.assertIn("--zip", dispatch["commands"]["exact_final_zip_recheck"])
        self.assertEqual(dispatch["permanent_negative"]["source_return"], "serialized Conv FSDB smoke s1")


if __name__ == "__main__":
    unittest.main()
