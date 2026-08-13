from __future__ import annotations

import copy
import concurrent.futures
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import jsonschema

from tools.server_package_runtime_layout import LayoutError, prepare_layout
from tools.validate_server_package_runtime_layout import main, validate


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools/server_package_runtime_layout.py"
SCHEMA = ROOT / "schemas/server_package_runtime_layout_v1.schema.json"
HARNESS_SCHEMA = (
    ROOT / "schemas/server_package_runtime_layout_harness_v1.schema.json"
)
CASES = ROOT / "fixtures/server_package_runtime_layout_v1/cases.json"
P14_REGRESSION = (
    ROOT
    / "fixtures/server_package_runtime_layout_v1/"
    "p14_preflight_return_regression.json"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RuntimeLayoutFixture:
    package_root = "synthetic_runtime_layout_v1"
    package_id = "synthetic_pkg"
    install_name = "synthetic_install"
    attempt_max = 12
    source_prefix = "workload/runtime/"

    def __init__(self, root: Path, case_id: str):
        self.root = root
        self.case_id = case_id
        self.zip_path = root / f"{case_id}.zip"
        self.harness_path = root / f"{case_id}.harness.json"

    def _runner(self) -> bytes:
        python_body = [
            "import json",
            'payload={"line_separator":chr(10)}',
            "print(json.dumps(payload,sort_keys=True))",
        ]
        if self.case_id == "negative_generated_python_heredoc_syntax":
            python_body = [
                "import json,pathlib",
                'payload={"status":"FAIL_CLOSED"}',
                'pathlib.Path("decision.json").write_text(',
                '    json.dumps(payload,sort_keys=True)+"',
                '",encoding="utf-8")',
            ]
        lines = [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'package_root="$(cd "$(dirname "$0")" && pwd -P)"',
            'server_root="$1"',
            f'package_id="{self.package_id}"',
            f'install_name="{self.install_name}"',
            'attempt="attempt000001"',
            'return_tag="r$(date -u +%s%N)_$$"',
            'work_root=""',
            'cfg_root=""',
            'run_root=""',
            'evidence_root=""',
            'compile_root=""',
            'return_zip="/home/panqs/ndp/simresult/'
            '${package_id}_${return_tag}_return.zip"',
            "runner_fail() {",
            '  rc="$1"',
            "  shift",
            (
                "  printf 'RUNNER_ERROR code=%s package=%s message=%s\\n' "
                '"$rc" "$package_id" "$*" >&2'
            ),
            '  exit "$rc"',
            "}",
            "shared_finalize() {",
            "  python3 - <<'PYFINALIZER_FALLBACK'",
            *python_body,
            "PYFINALIZER_FALLBACK",
            '  printf "%s\\n" "$1" >/dev/null',
            (
                "  printf 'RUNNER_FINAL_STATUS package=%s exit=%s\\n' "
                '"$package_id" "$1" >&2'
            ),
            "}",
            'trap \'shared_finalize "$?"\' EXIT',
            "trap 'exit 129' HUP",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
            (
                'test -d "$server_root/install" || runner_fail 2 '
                '"server_root install directory is missing or unreadable"'
            ),
            (
                "command -v python3 >/dev/null 2>&1 || runner_fail 3 "
                '"required tool is missing: python3"'
            ),
            (
                '[ ! -e "$return_zip" ] || runner_fail 10 '
                '"return target collision; preserve existing evidence before retry"'
            ),
            (
                'eval "$(python3 "$package_root/package_tools/'
                'server_package_runtime_layout.py" prepare '
                '--server-root "$server_root" --package-id "$package_id" '
                '--install-name "$install_name" --attempt "$attempt" '
                '--format shell)"'
            ),
            'cfg_root="$CFG_ROOT"',
            'run_root="$RUN_ROOT"',
            'evidence_root="$EVIDENCE_ROOT"',
            'compile_root="$COMPILE_ROOT"',
            'cd "$server_root"',
            '"$COMPILE_STUB" --output "$compile_root/simv"',
            (
                '"$SIM_STUB" "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" '
                '"-l=$run_root/sim.log"'
            ),
        ]
        if self.case_id == "negative_external_workroot":
            lines.insert(12, 'work_root="/tmp/external_pkg_state"')
        if self.case_id == "negative_silent_return_collision":
            lines = [
                line.replace(
                    'runner_fail 10 "return target collision; preserve '
                    'existing evidence before retry"',
                    "exit 10",
                )
                for line in lines
            ]
        if self.case_id == "negative_silent_missing_tool":
            lines = [
                line.replace(
                    'runner_fail 3 "required tool is missing: python3"',
                    "exit 3",
                )
                for line in lines
            ]
        if self.case_id == "negative_silent_bad_root":
            lines = [
                line.replace(
                    'runner_fail 2 "server_root install directory is missing '
                    'or unreadable"',
                    "exit 2",
                )
                for line in lines
            ]
        if self.case_id == "negative_finalizer_late_arm":
            arm = lines.pop(lines.index('trap \'shared_finalize "$?"\' EXIT'))
            preflight = next(
                index
                for index, line in enumerate(lines)
                if line.startswith('test -d "$server_root/install"')
            )
            lines.insert(preflight + 1, arm)
        return ("\n".join(lines) + "\n").encode("utf-8")

    def _sca(self) -> dict:
        cfg_prefix = f"install/cfg_pkg/{self.install_name}"
        matrix = f"{cfg_prefix}/runs/c0/install/matrix_A.txt"
        if self.case_id == "negative_wrong_sca_prefix":
            matrix = f"external_work/{self.install_name}/matrix_A.txt"
        return {
            "Exec_Base": "0x0",
            "Exec_Length": 1,
            "Repeat_Num": 1,
            "matrix_A": {"base_addr": "0x0", "path": matrix},
            "bitstream": {
                "base_addr": "0x100",
                "path": (
                    f"{cfg_prefix}/runs/c0/install/"
                    "op_bitstream_128b.bin"
                ),
            },
        }

    def _projected(self, entries: dict[str, bytes]) -> set[str]:
        target = f"install/cfg_pkg/{self.install_name}/"
        attempt = "a" * self.attempt_max
        probe_prefix = (
            f"install/codex_runs/{self.package_id}/{attempt}/evidence/"
        )
        budget_probe = probe_prefix + "x" * (115 - len(probe_prefix))
        projected = {
            target + member[len(self.source_prefix) :]
            for member in entries
            if member.startswith(self.source_prefix)
        }
        projected.update(
            {
                f"install/cfg_pkg/{self.install_name}",
                f"install/codex_runs/{self.package_id}/{attempt}",
                f"install/codex_runs/{self.package_id}/{attempt}/evidence",
                f"install/codex_runs/{self.package_id}/{attempt}/compile",
                (
                    f"install/codex_runs/{self.package_id}/{attempt}/"
                    "formal_readback/matrix_D.txt"
                ),
                budget_probe,
            }
        )
        return projected

    def _contract_and_manifest(
        self, entries: dict[str, bytes]
    ) -> tuple[dict, dict]:
        projected = self._projected(entries)
        longest = max(projected, key=lambda item: (len(item), item))
        root_max = 96
        absolute = root_max + 1 + len(longest)
        budget = {
            "declared_target_root_max_chars": root_max,
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": absolute,
            "absolute_path_limit_chars": 240,
        }
        if self.case_id == "negative_wrong_declared_longest_length":
            budget["longest_projected_relative_path_chars"] -= 3
        manifest = {
            "schema": "synthetic-package-manifest-v1",
            "package_id": self.package_id,
            "install_name": self.install_name,
            "path_length_budget": budget,
        }
        contract = {
            "schema": "server_package_runtime_layout_v1",
            "package_id": self.package_id,
            "install_name": self.install_name,
            "runner_member": "PREPARE_AND_RUN.sh",
            "manifest_member": "TEST_PACKAGE_MANIFEST.json",
            "shared_layout_helper": {
                "member": (
                    "package_tools/server_package_runtime_layout.py"
                ),
                "sha256": sha(HELPER.read_bytes()),
            },
            "tb_cwd": "$server_root",
            "fixed_result_root": "/home/panqs/ndp/simresult",
            "required_preexisting_parents": [
                "install",
            ],
            "package_creatable_parent_dirs": [
                "install/cfg_pkg",
                "install/codex_runs",
            ],
            "runtime_roots": {
                "cfg_root": f"install/cfg_pkg/{self.install_name}",
                "run_root": (
                    f"install/codex_runs/{self.package_id}/{{attempt}}"
                ),
                "evidence_root": (
                    f"install/codex_runs/{self.package_id}/"
                    "{attempt}/evidence"
                ),
                "compile_root": (
                    f"install/codex_runs/{self.package_id}/"
                    "{attempt}/compile"
                ),
            },
            "payload_mounts": [
                {
                    "source_prefix": self.source_prefix,
                    "runtime_prefix": (
                        f"install/cfg_pkg/{self.install_name}/"
                    ),
                }
            ],
            "sca_consumers": [
                {
                    "plusarg": "SCA_CFG",
                    "member": "workload/runtime/runs/c0/sca_cfg.json",
                    "mode": "read_inputs",
                }
            ],
            "runner_bindings": {
                "layout_prepare_marker": (
                    'server_package_runtime_layout.py" prepare'
                ),
                "tb_cwd_marker": 'cd "$server_root"',
                "compile_marker": '"$COMPILE_STUB"',
                "simulation_marker": '"$SIM_STUB"',
            },
            "path_budget": {
                "attempt_max_chars": self.attempt_max,
                "declared_target_root_max_chars": root_max,
                "max_projected_absolute_path_chars": absolute,
                "absolute_path_limit_chars": 240,
                "additional_projected_paths": [
                    (
                        f"install/codex_runs/{self.package_id}/"
                        "{attempt}/formal_readback/matrix_D.txt"
                    ),
                    (
                        f"install/codex_runs/{self.package_id}/"
                        "{attempt}/evidence/"
                        + "x"
                        * (
                            115
                            - len(
                                "install/codex_runs/"
                                f"{self.package_id}/"
                                + "a" * self.attempt_max
                                + "/evidence/"
                            )
                        )
                    )
                ],
            },
            "repeat_execution": {
                "mode": "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS",
                "cfg_root_policy": "RESET_AND_RECREATE_EXACT_INSTALL_NAME",
                "run_root_policy": "RESET_AND_RECREATE_EXACT_PACKAGE_ATTEMPT",
                "foreign_sibling_policy": "PRESERVE",
                "symlink_or_special_entry_policy": "FAIL_CLOSED",
                "ownership_marker": ".codex_owner.{name}.json",
                "return_name_policy": (
                    "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS"
                ),
            },
            "finalizer": {
                "arm_marker": 'trap \'shared_finalize "$?"\' EXIT',
                "first_preflight_marker": (
                    'test -d "$server_root/install"'
                ),
                "required_scenarios": [
                    "normal",
                    "preflight_fail",
                    "compile_fail",
                    "HUP",
                    "INT",
                    "TERM",
                ],
            },
            "claim_boundary": "Synthetic runtime-layout fixture.",
        }
        if self.case_id == "negative_fixed_result_root_drift":
            contract["fixed_result_root"] = "/tmp/result"
        return contract, manifest

    def _harness(self, zip_sha: str, runner_sha: str) -> dict:
        before = [
            {"name": "install", "type": "directory"},
            {"name": "rtl", "type": "directory"},
        ]
        scenarios = {}
        for name in (
            "normal",
            "preflight_fail",
            "compile_fail",
            "HUP",
            "INT",
            "TERM",
        ):
            after = copy.deepcopy(before)
            if (
                self.case_id == "negative_new_root_entry"
                and name == "normal"
            ):
                after.append({"name": "work_root", "type": "directory"})
            scenarios[name] = {
                "command": (
                    "bash synthetic_runtime_layout_v1/"
                    "PREPARE_AND_RUN.sh /srv/NDP_copy01"
                ),
                "cwd": "/tmp/fresh_extract",
                "runner_exit": 0 if name == "normal" else 1,
                "compile_started": name in {"normal", "compile_fail"},
                "simulation_started": name == "normal",
                "finalizer_reached": True,
                "partial_return_published": name != "normal",
                "fixed_result_return_published": True,
                "return_zip": (
                    "/home/panqs/ndp/simresult/"
                    f"{self.package_id}_r1723000000000000000_123_return.zip"
                ),
                "return_sidecar": (
                    "/home/panqs/ndp/simresult/"
                    f"{self.package_id}_r1723000000000000000_123_return.zip.sha256"
                ),
                "preexisting_parents_verified": True,
                "preexisting_install_verified": True,
                "creatable_parents_initially_absent": True,
                "creatable_parents_real_after": True,
                "unknown_items_deleted_or_overwritten": False,
                "writes_outside_install": False,
                "root_exact_set_unchanged": before == after,
                "root_direct_entries_before": before,
                "root_direct_entries_after": after,
            }
        return {
            "schema": "server_package_runtime_layout_harness_v1",
            "derived_from_zip_sha256": zip_sha,
            "runner_member_sha256": runner_sha,
            "fixed_result_root": "/home/panqs/ndp/simresult",
            "scenarios": scenarios,
            "claim_boundary": "Synthetic safe runner harness only.",
        }

    def build(self) -> tuple[Path, Path]:
        entries = {
            "PREPARE_AND_RUN.sh": self._runner(),
            "package_tools/server_package_runtime_layout.py": (
                HELPER.read_bytes()
            ),
            "workload/runtime/runs/c0/sca_cfg.json": (
                json.dumps(self._sca(), indent=2, sort_keys=True) + "\n"
            ).encode("utf-8"),
            "workload/runtime/runs/c0/install/matrix_A.txt": b"0\n",
            (
                "workload/runtime/runs/c0/install/"
                "op_bitstream_128b.bin"
            ): b"\x00\x01",
        }
        if self.case_id == "negative_missing_matrix":
            entries.pop(
                "workload/runtime/runs/c0/install/matrix_A.txt"
            )
        contract, manifest = self._contract_and_manifest(entries)
        if self.case_id != "negative_fixed_result_root_drift":
            jsonschema.validate(
                contract, json.loads(SCHEMA.read_text(encoding="utf-8"))
            )
        entries["SERVER_RUNTIME_LAYOUT_CONTRACT.json"] = (
            json.dumps(contract, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        entries["TEST_PACKAGE_MANIFEST.json"] = (
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        with zipfile.ZipFile(
            self.zip_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for relative, data in sorted(entries.items()):
                archive.writestr(
                    f"{self.package_root}/{relative}", data
                )
        harness = self._harness(
            hashlib.sha256(self.zip_path.read_bytes()).hexdigest(),
            sha(entries["PREPARE_AND_RUN.sh"]),
        )
        jsonschema.validate(
            harness,
            json.loads(HARNESS_SCHEMA.read_text(encoding="utf-8")),
        )
        self.harness_path.write_text(
            json.dumps(harness, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.zip_path, self.harness_path


class ServerPackageRuntimeLayoutTests(unittest.TestCase):
    def test_only_install_preexists_helper_creates_safe_shared_parents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server_root = Path(temporary) / "NDP_copy01"
            (server_root / "install").mkdir(parents=True)
            (server_root / "rtl").mkdir()
            unknown = server_root / "install/keep_me.txt"
            unknown.write_bytes(b"preserve-me")
            before = sorted(path.name for path in server_root.iterdir())
            receipt = prepare_layout(
                server_root,
                "pkg",
                "install_name",
                "attempt01",
                create=True,
            )
            after = sorted(path.name for path in server_root.iterdir())
            self.assertEqual(before, after)
            self.assertTrue(receipt["root_exact_set_unchanged"])
            self.assertTrue(
                receipt["all_package_owned_paths_under_install"]
            )
            self.assertEqual(
                [row["relative_path"] for row in receipt["required_preexisting_parents"]],
                ["install"],
            )
            self.assertEqual(
                {
                    row["relative_path"]
                    for row in receipt["package_creatable_parents"]
                },
                {"install/cfg_pkg", "install/codex_runs"},
            )
            self.assertTrue((server_root / "install/cfg_pkg").is_dir())
            self.assertTrue((server_root / "install/codex_runs").is_dir())
            self.assertEqual(unknown.read_bytes(), b"preserve-me")
            self.assertFalse(receipt["unknown_items_deleted_or_overwritten"])

    def test_repeated_execution_resets_only_exact_package_owned_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server_root = Path(temporary) / "NDP_copy01"
            (server_root / "install").mkdir(parents=True)
            (server_root / "rtl").mkdir()
            first = prepare_layout(
                server_root,
                "pkg",
                "install_name",
                "attempt01",
                create=True,
            )
            cfg_root = Path(first["cfg_root"])
            run_root = Path(first["run_root"])
            (cfg_root / "stale.bin").write_bytes(b"stale-cfg")
            (run_root / "stale.log").write_bytes(b"stale-run")
            foreign_cfg = server_root / "install/cfg_pkg/other_pkg"
            foreign_run = server_root / "install/codex_runs/other_pkg/a0"
            foreign_cfg.mkdir()
            foreign_run.mkdir(parents=True)
            (foreign_cfg / "keep.bin").write_bytes(b"keep-cfg")
            (foreign_run / "keep.log").write_bytes(b"keep-run")
            before = sorted(path.name for path in server_root.iterdir())

            second = prepare_layout(
                server_root,
                "pkg",
                "install_name",
                "attempt01",
                create=True,
            )

            self.assertEqual(
                before, sorted(path.name for path in server_root.iterdir())
            )
            self.assertFalse((cfg_root / "stale.bin").exists())
            self.assertFalse((run_root / "stale.log").exists())
            self.assertEqual(
                (foreign_cfg / "keep.bin").read_bytes(), b"keep-cfg"
            )
            self.assertEqual(
                (foreign_run / "keep.log").read_bytes(), b"keep-run"
            )
            self.assertTrue(second["exact_package_owned_items_replaced"])
            replacements = {
                row["kind"]: row
                for row in second["repeat_execution"]["replacements"]
            }
            self.assertTrue(replacements["cfg_root"]["reset_performed"])
            self.assertTrue(replacements["run_root"]["reset_performed"])
            self.assertFalse(
                second["unknown_items_deleted_or_overwritten"]
            )

    def test_repeated_execution_rejects_symlink_inside_reset_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server_root = Path(temporary) / "NDP_copy01"
            (server_root / "install").mkdir(parents=True)
            receipt = prepare_layout(
                server_root,
                "pkg",
                "install_name",
                "attempt01",
                create=True,
            )
            target = Path(receipt["cfg_root"]) / "escape"
            try:
                target.symlink_to(
                    server_root / "install", target_is_directory=True
                )
            except OSError as error:
                self.skipTest(f"symlink creation is unavailable: {error}")
            with self.assertRaises(LayoutError):
                prepare_layout(
                    server_root,
                    "pkg",
                    "install_name",
                    "attempt01",
                    create=True,
                )
            self.assertTrue(target.is_symlink())

    def test_repeated_execution_rejects_mismatched_owner_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server_root = Path(temporary) / "NDP_copy01"
            (server_root / "install").mkdir(parents=True)
            receipt = prepare_layout(
                server_root,
                "pkg",
                "install_name",
                "attempt01",
                create=True,
            )
            marker = (
                server_root
                / "install/cfg_pkg/.codex_owner.install_name.json"
            )
            payload = json.loads(marker.read_text(encoding="utf-8"))
            payload["package_id"] = "foreign_pkg"
            marker.write_text(
                json.dumps(payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(LayoutError):
                prepare_layout(
                    server_root,
                    "pkg",
                    "install_name",
                    "attempt01",
                    create=True,
                )
            self.assertTrue(Path(receipt["cfg_root"]).is_dir())

    def test_repeated_execution_rejects_non_object_owner_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server_root = Path(temporary) / "NDP_copy01"
            (server_root / "install").mkdir(parents=True)
            receipt = prepare_layout(
                server_root,
                "pkg",
                "install_name",
                "attempt01",
                create=True,
            )
            marker = (
                server_root
                / "install/cfg_pkg/.codex_owner.install_name.json"
            )
            marker.write_text("[]\n", encoding="utf-8")
            with self.assertRaises(LayoutError):
                prepare_layout(
                    server_root,
                    "pkg",
                    "install_name",
                    "attempt01",
                    create=True,
                )
            self.assertTrue(Path(receipt["cfg_root"]).is_dir())

    def test_shared_layout_helper_rejects_install_and_parent_type_negatives(
        self,
    ) -> None:
        controls = [
            "install_missing",
            "install_file",
            "install_symlink",
            "cfg_pkg_file",
            "cfg_pkg_symlink",
            "codex_runs_file",
            "codex_runs_symlink",
        ]
        declared = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual(declared["helper_negative_controls"], controls)
        for control in controls:
            with self.subTest(control=control), tempfile.TemporaryDirectory() as temporary:
                server_root = Path(temporary) / "NDP_copy01"
                server_root.mkdir()
                install = server_root / "install"
                if control == "install_file":
                    install.write_bytes(b"not-a-directory")
                elif control != "install_missing":
                    install.mkdir()
                target = None
                if control.startswith("cfg_pkg"):
                    target = install / "cfg_pkg"
                elif control.startswith("codex_runs"):
                    target = install / "codex_runs"
                elif control == "install_symlink":
                    target = install
                if target is not None and control.endswith("_file"):
                    target.write_bytes(b"unknown-file")
                elif target is not None and control.endswith("_symlink"):
                    target.mkdir(exist_ok=True)

                original_is_symlink = Path.is_symlink

                def simulated_is_symlink(path: Path) -> bool:
                    if target is not None and path == target and control.endswith(
                        "_symlink"
                    ):
                        return True
                    return original_is_symlink(path)

                before_unknown = (
                    target.read_bytes()
                    if target is not None and target.is_file()
                    else None
                )
                with mock.patch.object(
                    Path, "is_symlink", autospec=True, side_effect=simulated_is_symlink
                ):
                    with self.assertRaises(LayoutError):
                        prepare_layout(
                            server_root,
                            "pkg",
                            "install_name",
                            "attempt01",
                            create=True,
                        )
                if before_unknown is not None:
                    self.assertEqual(target.read_bytes(), before_unknown)

    def test_shared_parent_creation_is_concurrent_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server_root = Path(temporary) / "NDP_copy01"
            (server_root / "install").mkdir(parents=True)
            (server_root / "rtl").mkdir()
            unknown = server_root / "install/unknown.bin"
            unknown.write_bytes(b"do-not-overwrite")
            before_root = sorted(path.name for path in server_root.iterdir())

            def run(number: int) -> dict:
                return prepare_layout(
                    server_root,
                    f"pkg{number}",
                    f"install{number}",
                    f"attempt{number}",
                    create=True,
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                receipts = list(pool.map(run, range(4)))
            self.assertTrue(all(row["root_exact_set_unchanged"] for row in receipts))
            self.assertEqual(
                before_root, sorted(path.name for path in server_root.iterdir())
            )
            self.assertEqual(unknown.read_bytes(), b"do-not-overwrite")
            self.assertTrue((server_root / "install/cfg_pkg").is_dir())
            self.assertTrue((server_root / "install/codex_runs").is_dir())

    def test_p14_real_preflight_regression_old_fails_new_passes(self) -> None:
        fixture = json.loads(P14_REGRESSION.read_text(encoding="utf-8"))
        self.assertEqual(
            fixture["actual_return"]["sha256"],
            "c08005d0a3daa9a8417488738ae3b67c77ab7b7a055d9f207ac722987060fd6d",
        )
        self.assertEqual(fixture["actual_return"]["bytes"], 2264)
        self.assertTrue(fixture["actual_return"]["duplicate_absent"])
        self.assertTrue(fixture["early_finalizer"]["partial_return_atomic_publish"])
        with tempfile.TemporaryDirectory() as temporary:
            server_root = Path(temporary) / "NDP_copy02"
            (server_root / "install/cfg_pkg").mkdir(parents=True)
            (server_root / "rtl").mkdir()
            legacy_missing = [
                relative
                for relative in fixture["legacy_required_preexisting_parents"]
                if not (server_root / relative).exists()
            ]
            self.assertEqual(legacy_missing, ["install/codex_runs"])
            self.assertIn(
                legacy_missing[0], fixture["actual_preflight_error"]
            )
            receipt = prepare_layout(
                server_root,
                fixture["package_id"],
                fixture["install_name"],
                "attempt000001",
                create=True,
            )
            self.assertTrue(receipt["root_exact_set_unchanged"])
            self.assertTrue((server_root / "install/codex_runs").is_dir())
            self.assertTrue(Path(receipt["cfg_root"]).is_dir())
            self.assertTrue(Path(receipt["run_root"]).is_dir())

    def test_declared_fixture_cases(self) -> None:
        fixture = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual(
            fixture["schema"],
            "server_package_runtime_layout_fixture_cases_v1",
        )
        self.assertEqual(len(fixture["cases"]), 12)
        for case in fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                with tempfile.TemporaryDirectory() as temporary:
                    harness = RuntimeLayoutFixture(
                        Path(temporary), case["case_id"]
                    )
                    zip_path, harness_path = harness.build()
                    report = validate(
                        zip_path,
                        harness_path,
                        HELPER,
                        require_runner_visibility=case.get(
                            "require_runner_visibility", False
                        ),
                    )
                    self.assertEqual(
                        report["pass"], case["expected_pass"], report["errors"]
                    )
                    if "expected_error" in case:
                        self.assertTrue(
                            any(
                                case["expected_error"] in error
                                for error in report["errors"]
                            ),
                            report["errors"],
                        )
                    if case["case_id"] == "positive_install_subtree_all_scenarios":
                        self.assertTrue(
                            report["checks"]["generated_heredoc_syntax"]
                        )
                        self.assertEqual(
                            report["generated_heredocs"]["python_compile_count"],
                            1,
                        )
                        self.assertEqual(
                            report["generated_heredocs"]["failed"], 0
                        )
                        self.assertTrue(
                            report["checks"]["runner_early_exit_visibility"]
                        )
                        self.assertTrue(
                            report["runner_early_exit_visibility"]["enforced"]
                        )
                        self.assertGreaterEqual(
                            report["runner_early_exit_visibility"]["call_count"],
                            3,
                        )
                        self.assertEqual(
                            report["runner_early_exit_visibility"][
                                "bare_nonzero_exit_count"
                            ],
                            0,
                        )

    def test_path_budget_negative_reports_exact_declared_and_computed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            harness = RuntimeLayoutFixture(
                Path(temporary),
                "negative_wrong_declared_longest_length",
            )
            zip_path, harness_path = harness.build()
            report = validate(zip_path, harness_path, HELPER)
            self.assertFalse(report["pass"])
            self.assertTrue(
                any(
                    "longest_projected_relative_path_chars" in error
                    for error in report["errors"]
                )
            )
            self.assertGreater(
                report["path_budget"][
                    "longest_projected_relative_path_chars"
                ],
                114,
            )
            self.assertEqual(
                report["path_budget"][
                    "longest_projected_relative_path_chars"
                ],
                115,
            )

    def test_cli_exit_policy_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            positive = RuntimeLayoutFixture(
                root, "positive_install_subtree_all_scenarios"
            )
            zip_path, harness_path = positive.build()
            output = root / "positive.report.json"
            self.assertEqual(
                main(
                    [
                        "--zip",
                        str(zip_path),
                        "--harness-report",
                        str(harness_path),
                        "--helper-reference",
                        str(HELPER),
                        "--require-runner-error-visibility",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertTrue(
                json.loads(output.read_text(encoding="utf-8"))["pass"]
            )

            negative = RuntimeLayoutFixture(
                root, "negative_external_workroot"
            )
            zip_path, harness_path = negative.build()
            output = root / "negative.report.json"
            self.assertEqual(
                main(
                    [
                        "--zip",
                        str(zip_path),
                        "--harness-report",
                        str(harness_path),
                        "--helper-reference",
                        str(HELPER),
                        "--output",
                        str(output),
                    ]
                ),
                1,
            )
            self.assertFalse(
                json.loads(output.read_text(encoding="utf-8"))["pass"]
            )


if __name__ == "__main__":
    unittest.main()
