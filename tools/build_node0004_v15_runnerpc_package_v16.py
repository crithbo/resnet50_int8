from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v14_abpe_syntax_fix_package_v15 as prior  # noqa: E402
import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v16_abpe_runnerpc"
PLAN_SHA256 = "532d176ed70fb630dbc797263409887a2d32bafecd5f9af3a21077d56a157bfe"
SERVER_RULE_SHA256 = (
    "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a"
)
SOURCE_V15 = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v15_abpe_syntax_fix.zip"
)
SOURCE_V15_SHA256 = (
    "65e5b50b00046d662d219b71054f7f3f64c5794c98bf87dc134b5b3dd09a2130"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
RULE_ID = "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001"
STRICT_RULE_ID = "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001"
ROOT_RULE_ID = "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001"
BOUND_V15_RETURN_SHA256 = (
    "592d792e9f0d647f1a3d43bdc8b3a5bbffb1956d4ff908916d0f6d78cf9a94d2"
)


def _readme() -> str:
    return f"""# node0004 v16 ABPE observer and runner positive-control binding

Classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.

This fresh identity keeps the exact v15 Conv configuration, physical workload,
and golden payload.  It fixes the remaining package-local ABPE task terminator
and updates the
package-local active-rule receipt to server-package rule
`{SERVER_RULE_SHA256}` and binds `{STRICT_RULE_ID}`, `{RULE_ID}`, and
`{ROOT_RULE_ID}`.

The final-ZIP delivery audit must fresh-extract this archive and invoke the
actual `PREPARE_AND_RUN.sh` with a safe compile stub.  The positive control must
reach the one real `make ... compile` call after package, installed, and
package-local observer preflight; the stub exits exactly 73.  A mutated
package-local identity must fail before the compile stub is invoked.

The runner accepts one user-supplied absolute server root and does not inspect
or bind any pre-existing server RTL, TB, Makefile, filelist, Git state, README,
observer, or source-tree identity.  The package-local observer guard reads its
expected identity only from the final package manifest; the runner contains no
second hard-coded SHA.  This local control does not establish server VCS
compile, E3, E4, or E5.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def _patch_missing_endtask(package: Path) -> dict[str, Any]:
    observer = package / "tb_probe/native_return_observer.svh"
    old_sha = base.sha256(observer)
    text = observer.read_text(encoding="utf-8")
    marker = "task automatic return_obs_write_abpe_state(input string event_name);"
    start = text.index(marker)
    tail = text[start:]
    old = """                $fflush(return_obs_fd);
            end
        end
    end
"""
    new = """                $fflush(return_obs_fd);
            end
        end
    endtask
"""
    if tail.count(old) != 1 or "endtask" in tail:
        raise base.BuildError("v15 missing-endtask source shape differs")
    text = text[:start] + tail.replace(old, new, 1)
    observer.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": observer.relative_to(package).as_posix(),
        "old_sha256": old_sha,
        "new_sha256": base.sha256(observer),
        "repair": (
            "replace the final task-closing end with endtask for "
            "return_obs_write_abpe_state"
        ),
    }


def _patch_manifest_sourced_observer_guard(package: Path) -> None:
    guard = package / "package_tools/node0004_package_observer_guard.py"
    text = guard.read_text(encoding="utf-8")
    old = """    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    receipt = observer_precompile_receipt(
        args.package_root, args.expected_sha256
    )
"""
    new = """    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected_sha256 = manifest["observer_binding_four_way"]["source"]["sha256"]
    receipt = observer_precompile_receipt(
        args.package_root, expected_sha256
    )
    receipt["expected_identity_source"] = (
        "package_manifest.json:"
        "observer_binding_four_way.source.sha256"
    )
"""
    if text.count(old) != 1:
        raise base.BuildError("observer guard CLI source shape differs")
    guard.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    runner = package / "PREPARE_AND_RUN.sh"
    runner_text = runner.read_text(encoding="utf-8")
    old_call = (
        'python3 "$observer_guard" --package-root "$package_root"   '
        '--expected-sha256 "'
    )
    call_start = runner_text.find(old_call)
    if call_start < 0:
        raise base.BuildError("runner hard-coded observer guard call differs")
    call_end = runner_text.find(
        '   > "$evidence_root/observer_precompile.json" || exit 7',
        call_start,
    )
    if call_end < 0:
        raise base.BuildError("runner observer guard redirection differs")
    call_end += len(
        '   > "$evidence_root/observer_precompile.json" || exit 7'
    )
    replacement = (
        'python3 "$observer_guard" --package-root "$package_root"   '
        '--manifest "$package_root/package_manifest.json"   '
        '> "$evidence_root/observer_precompile.json" || exit 7'
    )
    runner_text = runner_text[:call_start] + replacement + runner_text[call_end:]
    runner.write_text(runner_text, encoding="utf-8", newline="\n")


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    prior.INSTALL_NAME = INSTALL_NAME
    prior.PLAN_SHA256 = PLAN_SHA256
    prior.prior.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    package, source_proof = prior.build_directory(destination)
    task_repair = _patch_missing_endtask(package)
    _patch_manifest_sourced_observer_guard(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "resnet50-node0004-runner-positive-control-package-v16"
    manifest["install_name"] = INSTALL_NAME
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    for item in receipts["generation_read_receipt"]:
        if item["path"].endswith("服务器测试包生成规则.md") or (
            item["sha256"]
            == "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
        ):
            item["sha256"] = SERVER_RULE_SHA256
    for rule_id in (STRICT_RULE_ID, RULE_ID, ROOT_RULE_ID):
        if rule_id not in receipts["rules"]:
            receipts["rules"].append(rule_id)
    observer_sha = task_repair["new_sha256"]
    manifest["observer_binding_four_way"]["source"]["sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["size_bytes"] = (
        package / "tb_probe/native_return_observer.svh"
    ).stat().st_size
    manifest["observer_sha256"] = observer_sha
    manifest["observer_compile_repair"]["new_sha256"] = observer_sha
    manifest["observer_compile_repair"]["size_bytes"] = (
        package / "tb_probe/native_return_observer.svh"
    ).stat().st_size
    manifest["observer_task_terminator_repair"] = {
        "classification": "PACKAGE_LOCAL_READ_ONLY_OBSERVER_SYNTAX_FIX",
        "bound_return_sha256": BOUND_V15_RETURN_SHA256,
        "first_divergence": (
            "VCS reports keyword endtask missing at v15 package-local "
            "observer line 2433 before elaboration/simulation"
        ),
        "functional_semantics_changed": False,
        "qualified_progress_changed": False,
        **task_repair,
    }
    manifest["runtime_preflight_profile"] = {
        "rule_ids": [STRICT_RULE_ID, ROOT_RULE_ID],
        "user_supplied_root": True,
        "server_source_identity_bound": False,
        "forbidden_server_preflight_targets": [
            "rtl",
            "tb",
            "Makefile",
            "filelist",
            "support_file",
            "Git",
            "README",
            "observer",
            "source_tree",
        ],
        "package_local_observer_expected_identity_source": (
            "package_manifest.json:"
            "observer_binding_four_way.source.sha256"
        ),
        "runner_hardcoded_observer_sha_count": 0,
    }
    manifest["runner_preflight_to_compile_positive_control"] = {
        "rule_id": RULE_ID,
        "final_zip_external_execution_required": True,
        "runner": "PREPARE_AND_RUN.sh",
        "fresh_extract_required": True,
        "ordered_boundaries": [
            "package_preflight",
            "fresh_namespace_install",
            "installed_preflight",
            "observer_precompile_identity_guard",
            "actual_make_compile_call",
        ],
        "safe_compile_stub": {
            "expected_invocation_count": 1,
            "expected_exit_code": 73,
            "actual_compile_argv_required": True,
        },
        "negative_control": {
            "mutation": "package-local observer SHA differs from manifest",
            "compile_stub_invocation_count": 0,
            "must_fail_before_compile": True,
        },
        "claim_boundary": (
            "runner control-flow proof only; no server VCS/elaboration, "
            "simulation, E3, E4, or E5"
        ),
    }
    manifest["superseded_rule_drift_package"] = {
        "path": SOURCE_V15.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_V15_SHA256,
        "status": "QUARANTINED_POST_GENERATION_RULE_DRIFT",
        "reason": (
            "missing current server rule SHA, strict-local/minimal-runtime "
            "profile, manifest-sourced observer identity, and runner "
            "positive control in final ZIP"
        ),
    }
    manifest["numeric_analysis_repeated"] = False
    manifest["node0004_workload_rebuilt"] = False
    manifest["configuration_rebuilt"] = False
    manifest["functional_rtl_modified"] = False
    manifest["server_rtl_entries"] = 0
    (package / "README.md").write_text(
        _readme(), encoding="utf-8", newline="\n"
    )
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    return package, {
        "preflight": source_proof["preflight"],
        "observer": source_proof["observer"],
        "final_zip_runner_positive_control_required": True,
        "final_zip_rule_self_audit_required": True,
    }


def _repeat(package: Path, zip_path: Path) -> dict[str, Any]:
    base.deterministic_zip(package, zip_path)
    records = base.package_records(package)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v16-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        if records != base.package_records(repeat_package):
            raise base.BuildError("repeated v16 package trees differ")
        if digest != base.sha256(repeat_zip):
            raise base.BuildError("repeated v16 ZIPs differ")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    package = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    validation = output / f"{INSTALL_NAME}.validation.json"
    for target in (package, zip_path, sidecar, validation):
        if target.exists():
            raise base.BuildError(f"refusing to overwrite: {target}")
    package, proof = build_directory(output)
    repeated = _repeat(package, zip_path)
    digest = base.sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-runner-positive-control-package-validation-v16",
        "status": "PACKAGE_BUILT_PENDING_FINAL_RUNNER_AND_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_v15_sha256": SOURCE_V15_SHA256,
        **proof,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "repeated_build": repeated,
        "final_zip_rule_self_audit_pending": True,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
