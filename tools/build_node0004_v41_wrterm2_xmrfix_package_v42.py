from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v40_wrterm2_diag_package_v41 as previous  # noqa: E402


base = previous.base
SOURCE_NAME = "r5_n4_hw_v41_wrterm2_diag"
INSTALL_NAME = "r5_n4_hw_v42_wrterm2_compilefix"
VERSION = 42
SOURCE_SHA256 = "e314dfb65b1bc7b8ad0403aa559a79508073092988a45e20b8637f21917933b0"
RETURN_SHA256 = "b351089eb76255f23f8190e181a05cbe9bbac1d01c16b555b6eaa3af4424b011"
RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
PLAN_MUTABLE_SHA256 = "f2a671834e3f847829558d1c73b848a908c0546d577ebe662bc0eb690a970e8b"
SERVER_RULE_SHA256 = "da0e2dc8dab9a64d4eaca3f15ee0634b3af6b299dfa505e192d6b6bf30ff12b8"
COMMON_RULE_SHA256 = "8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
RULE_IDS = [
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
]


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v41 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v41 source CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if path.parts:
                roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v41 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    old_fmt = (
        "mem1_vld=%0d mem1_same=%0d mem1_bp=%0d mem1_gotten=%0d "
        "desc_count=%0d"
    )
    new_fmt = "mem1_vld=%0d mem1_same=%0d mem1_bp=%0d desc_count=%0d"
    old_arg = (
        "                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
        "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
        "u_Memory_AG_Idx_Queue.mem_idx_gotten[1],\n"
    )
    if text.count(old_fmt) != 1 or text.count(old_arg) != 1:
        raise BuildError("v41 failing observer consumer is not exact")
    text = text.replace(old_fmt, new_fmt, 1).replace(old_arg, "", 1)
    if "mem_idx_gotten[1]" in text or "mem1_gotten=" in text:
        raise BuildError("failing private XMR remained")
    path.write_text(text, encoding="utf-8", newline="\n")
    return base.sha256(path)


def release_gate_matrix() -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "PACKAGE_BOOTSTRAP_PATH_RUNTIME_D",
            "applicable": True,
            "reason": "fresh identity and package root",
            "changed_surface": ["install_name", "README", "manifest"],
            "evidence": ["manifest exact-set", "path budget", "runtime-D absent"],
            "blocking": True,
        },
        {
            "gate_id": "RUNNER_TO_COMPILE_AND_FINALIZER",
            "applicable": True,
            "reason": "fresh identity must reach the unchanged real runner",
            "changed_surface": ["identity substitution only"],
            "evidence": ["safe compile positive", "EXIT/TERM finalizer"],
            "blocking": True,
        },
        {
            "gate_id": "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL",
            "applicable": True,
            "reason": "v41 failed production scope resolution",
            "changed_surface": [
                "remove nonessential private mem_idx_gotten display XMR"
            ],
            "evidence": [
                "final exact observer consumer closure",
                "public-surface applicability",
                "actual-consumer typo negative",
            ],
            "blocking": True,
        },
        {
            "gate_id": "CHANGED_MATERIALIZED_CONFIG_CONSUMER_CONTRACT",
            "applicable": False,
            "reason": "configuration is byte-equal after identity normalization",
            "changed_surface": [],
            "evidence": ["runtime payload byte comparison"],
            "blocking": False,
        },
        {
            "gate_id": "CHANGED_OBSERVER_OR_CANONICAL_SEMANTICS",
            "applicable": True,
            "reason": "one display-only XMR is removed; terminal predicate retained",
            "changed_surface": ["WRTERM2 edge record display payload"],
            "evidence": ["final-exact predicate trace", "schema/argument closure"],
            "blocking": True,
        },
        {
            "gate_id": "RETURN_RESULT_JOINT_GATE",
            "applicable": True,
            "reason": "diagnostic return must remain formally adjudicable",
            "changed_surface": ["fresh expected return identity"],
            "evidence": ["allowlist/exact-set/result conjunction negatives"],
            "blocking": True,
        },
        {
            "gate_id": "FROZEN_NUMERIC_W3_GOLDEN",
            "applicable": False,
            "reason": "byte-equal frozen payload",
            "changed_surface": [],
            "evidence": ["identity-normalized byte comparison"],
            "blocking": False,
        },
        {
            "gate_id": "UNRELATED_FUNCTIONAL_RTL",
            "applicable": False,
            "reason": "server_rtl_entries=0 and functional RTL is unchanged",
            "changed_surface": [],
            "evidence": ["manifest classification"],
            "blocking": False,
        },
        {
            "gate_id": "REPORT_STYLE_OR_SYNONYMOUS_NEGATIVES",
            "applicable": False,
            "reason": "record_only; no semantic release impact",
            "changed_surface": [],
            "evidence": ["release report"],
            "blocking": False,
        },
    ]


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v42-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)

    provenance = package / "provenance"
    base.write_json(
        provenance / f"v41_xmr_compilefix_v{VERSION}.json",
        {
            "schema": f"node0004-v41-xmr-compilefix-v{VERSION}",
            "bound_return_sha256": RETURN_SHA256,
            "source_v41_sha256": SOURCE_SHA256,
            "compile_error": {
                "path": "tb_probe/native_return_observer.svh",
                "source_line": 5974,
                "token": "mem_idx_gotten",
                "production_error": "VCS XMRE",
            },
            "repair": {
                "action": "remove nonessential private display-only XMR",
                "public_surface_basis": [
                    "mse_mem_queue_tag[1]",
                    "mse_mem_queue_bp_pre[1]",
                    "qualified wt_addr1",
                ],
                "functional_or_config_change": False,
            },
            "release_gate_matrix": release_gate_matrix(),
        },
    )
    (package / "README.md").write_text(
        f"# node0004 v{VERSION} WRTERM2 observer compile fix\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v41 did not start simulation because the package-local observer "
        "referenced nonexistent private leaf `mem_idx_gotten[1]`. "
        f"v{VERSION} removes "
        "that display-only field; the existing public tag/backpressure surfaces "
        "and qualified address-accept predicate retain the candidate split. "
        "The corrected true-final predicate is unchanged. Numeric, workload, "
        "config, golden, timeout, backpressure and functional RTL are unchanged.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": (
                f"resnet50-node0004-wrterm2-compilefix-package-v{VERSION}"
            ),
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    receipts["common_operator_rule_sha256"] = COMMON_RULE_SHA256
    for rule_id in RULE_IDS:
        if rule_id not in receipts["rules"]:
            receipts["rules"].append(rule_id)
    for item in receipts["generation_read_receipt"]:
        if item.get("reason") == "common server package gates":
            item["sha256"] = SERVER_RULE_SHA256

    manifest["v41_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "PACKAGE_LOCAL_OBSERVER_XMRE_COMPILE_FAILURE",
        "compile_exit": 2,
        "run_exit": 125,
        "simulation_started": False,
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "last_proven_good": (
            "PACKAGE_AND_INSTALL_PREFLIGHT_PASS_AND_VCS_PARSES_FINAL_OBSERVER"
        ),
        "first_divergence": (
            "VCS_SCOPE_RESOLUTION_FAILS_ON_OBSERVER_LINE_5974_"
            "TOKEN_MEM_IDX_GOTTEN"
        ),
    }
    manifest[f"package_local_observer_compile_fix_v{VERSION}"] = {
        "failing_leaf": "u_Memory_AG_Idx_Queue.mem_idx_gotten[1]",
        "action": "removed display-only private XMR",
        "public_surface_or_xmr_adjudication": {
            "rule_id": "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
            "private_xmr_required": False,
            "reason": (
                "existing public tag/backpressure and qualified accept evidence "
                "already distinguish the candidate"
            ),
            "new_private_xmr_count": 0,
        },
        "terminal_predicate_unchanged": (
            "desc_pop && !desc_push && pre_count==1"
        ),
        "functional_fix": False,
        "configuration_changed": False,
    }
    manifest["release_gate_matrix"] = release_gate_matrix()
    manifest["predicate_trace_contract"] = {
        "rule_id": "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
        "exact_predicate": "pop && !push && pre_count==1",
        "clock_owner": "u_NDP_Top_new.clk_db",
        "reset_owner": "u_NDP_Top_new.rst_n_db",
        "trace_receipt": (
            f"outputs/conv_node0004_v{VERSION}_package_validation/"
            "predicate_trace.json"
        ),
        "server_dut_run_required": False,
    }
    manifest["superseded_v41_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": (
            f"RETURN_CONSUMED_SUPERSEDED_BY_V{VERSION}_COMPILE_FIX"
        ),
    }
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"].update(
        {
            "sha256": observer_sha,
            "size_bytes": (
                package / "tb_probe/native_return_observer.svh"
            ).stat().st_size,
        }
    )
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    receipt = base.observer_precompile_receipt(package, observer_sha)
    if not receipt["valid"]:
        raise BuildError(f"observer static gate failed: {receipt['errors']}")
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL_NAME,
        output / f"{INSTALL_NAME}.zip",
        output / f"{INSTALL_NAME}.zip.sha256",
        output / f"{INSTALL_NAME}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError(
            f"refusing to overwrite existing v{VERSION} target"
        )
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(
        prefix=f"node0004-v{VERSION}-repeat-"
    ) as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError(f"v{VERSION} deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": f"node0004-wrterm2-compilefix-build-v{VERSION}",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v41_sha256": SOURCE_SHA256,
        "bound_v41_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "builder_plan_mutable_provenance_sha256": PLAN_MUTABLE_SHA256,
        "current_local_rtl_commit": RTL_COMMIT,
        "release_gate_matrix_entry_count": len(release_gate_matrix()),
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(output / f"{INSTALL_NAME}.validation.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
