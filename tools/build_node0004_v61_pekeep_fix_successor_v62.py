from __future__ import annotations

import argparse
import hashlib
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

from tools.build_node0004_v51_ndp_root_gate_package_v52 import (  # noqa: E402
    deterministic_zip,
    sha256,
)


SOURCE = "r5_n4_hw_v61_lcmap_argv_fix"
INSTALL = "r5_n4_hw_v62_pekeep_fix"
SOURCE_SHA = "c78e62cde4f8e185f801900773117017982920b9a479996a1c31af8a1dae1e96"
RETURN_SHA = "a883838b289150d287d566da240e4d18a27a08bda027fa4a0ef7042ed3a1da9e"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v61_return_v62_successor/build"
FRESH_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-pe1-keep-last-index-fix-c0-v62"
)
FRESH_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/"
    "r5_node0004_pe1_keep_last_index_fix_c0_v62/"
    "accumulate_waves/wave-0.json"
)
ANALYSIS = ROOT / "outputs/conv_node0004_v61_return_analysis/report.json"
RULE_PATHS = {
    "agent": ROOT / ".agents/agent.md",
    "plan": ROOT / ".agents/plan.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common": ROOT / ".agents/rules/算子配置规则.md",
    "ndp": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "int8_sa": ROOT / ".agents/rules/INT8_SA点积专项规则.md",
    "readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("v61 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v61 source CRC differs")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or mode == 0o120000
            ):
                raise BuildError(f"unsafe/duplicate source member:{info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"v61 source root differs:{sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE


def replace_identity(package: Path) -> tuple[str, str]:
    observer = package / "tb_probe/native_return_observer.svh"
    old_observer_sha = sha256(observer)
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE in text:
            path.write_text(
                text.replace(SOURCE, INSTALL), encoding="utf-8", newline="\n"
            )
    return old_observer_sha, sha256(observer)


def prefix_sca(path: Path, *, output: bool) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    prefix = (
        f"install/codex_runs/{INSTALL}/{{attempt}}/c0/"
        if output
        else f"install/cfg_pkg/{INSTALL}/runs/c0/"
    )
    for item in value.values():
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            old = item["path"]
            pure = PurePosixPath(old)
            if (
                not old.startswith("install/")
                or pure.is_absolute()
                or ".." in pure.parts
            ):
                raise BuildError(f"unsafe fresh SCA path:{old}")
            item["path"] = prefix + old
    write_json(path, value)


def inject_fresh_c0_assets(package: Path) -> dict[str, Any]:
    report_path = FRESH_ROOT / "local_rebuild_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        report.get("status") != "LOCAL_C0_PHYSICAL_REBUILD_PASS"
        or report.get("authorized_leaf_changes")
        != [
            {
                "path": "lc_pe_configs.PE1.inport0.keep_last_index",
                "old": 2,
                "new": 3,
            }
        ]
        or report.get("bitstream", {}).get("changed_offsets") != [1301]
    ):
        raise BuildError("fresh PE keep fix rebuild report differs")
    pipeline = FRESH_ROOT / "execplan_conv/wave-0/pipeline_output"
    run = package / "workload/runtime/runs/c0"
    copied: list[str] = []
    for name in (
        "execplan.txt",
        "execplan_op_w0.txt",
        "cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin",
    ):
        source = pipeline / "install" / name
        target = run / "install" / name
        if not source.is_file() or not target.is_file():
            raise BuildError(f"C0 physical endpoint missing:{name}")
        shutil.copy2(source, target)
        copied.append(name)
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        source = pipeline / name
        target = run / name
        if not source.is_file() or not target.is_file():
            raise BuildError(f"C0 SCA endpoint missing:{name}")
        shutil.copy2(source, target)
        prefix_sca(target, output=name == "sca_cfg_D.json")
        copied.append(name)
    return {
        "local_rebuild_report": {
            "path": report_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(report_path),
        },
        "fresh_config": {
            "path": FRESH_CONFIG.relative_to(ROOT).as_posix(),
            "sha256": sha256(FRESH_CONFIG),
        },
        "fresh_final_json": report["final_json"],
        "fresh_mapping": report["mapping"],
        "fresh_bitstream": report["bitstream"],
        "fresh_execplan": report["execplan"],
        "fresh_sca": report["sca"],
        "causal_transaction_ledger": report["causal_transaction_ledger"],
        "boundary_microtrace": report["boundary_microtrace"],
        "copied_physical_assets": copied,
    }


def replace_hash(value: object, old: str, new: str) -> object:
    if isinstance(value, dict):
        return {key: replace_hash(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_hash(item, old, new) for item in value]
    if value == old:
        return new
    return value


def package_records(package: Path) -> dict[str, str]:
    manifest_path = package / "package_manifest.json"
    return {
        path.relative_to(package).as_posix(): sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest_path
    }


def update_path_budget(package: Path) -> None:
    contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    manifest_path = package / "package_manifest.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    budget = manifest["path_length_budget"]
    longest = budget["longest_projected_relative_path"]
    longest_chars = len(longest)
    root_chars = contract["path_budget"]["declared_target_root_max_chars"]
    projected = root_chars + 1 + longest_chars
    budget["longest_projected_relative_path_chars"] = longest_chars
    budget["max_projected_absolute_path_chars"] = projected
    budget["pass"] = projected <= budget["absolute_path_limit_chars"]
    contract["path_budget"]["max_projected_absolute_path_chars"] = projected
    write_json(contract_path, contract)
    write_json(manifest_path, manifest)


def refresh_receipts(manifest: dict[str, Any]) -> None:
    current = {key: sha256(path) for key, path in RULE_PATHS.items()}
    receipts = manifest.setdefault("active_receipts", {})
    receipts["agent_sha256"] = current["agent"]
    receipts["plan_mutable_provenance_sha256"] = current["plan"]
    receipts["generation_index_sha256"] = current["index"]
    receipts["server_package_rule_sha256"] = current["server"]
    receipts["common_operator_rule_sha256"] = current["common"]
    receipts["ndp_hardware_field_rule_sha256"] = current["ndp"]
    receipts["int8_sa_rule_sha256"] = current["int8_sa"]
    receipts["hardware_readme_sha256"] = current["readme"]
    path_to_sha = {
        ".agents/agent.md": current["agent"],
        ".agents/plan.md": current["plan"],
        ".agents/rules/生成前必读索引.md": current["index"],
        ".agents/rules/服务器测试包生成规则.md": current["server"],
        ".agents/rules/算子配置规则.md": current["common"],
        ".agents/rules/NDP硬件字段语义.md": current["ndp"],
        ".agents/rules/INT8_SA点积专项规则.md": current["int8_sa"],
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": current["readme"],
    }
    for item in receipts.get("generation_read_receipt", []):
        path = item.get("path")
        if path in path_to_sha:
            item["sha256"] = path_to_sha[path]
    rules = receipts.setdefault("rules", [])
    for rule in (
        "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
        "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
        "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
        "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
        "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
    ):
        if rule not in rules:
            rules.append(rule)


def update_manifest(
    package: Path,
    old_observer_sha: str,
    new_observer_sha: str,
    injection: dict[str, Any],
) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest = replace_hash(manifest, old_observer_sha, new_observer_sha)
    assert isinstance(manifest, dict)
    manifest.update(
        {
            "install_name": INSTALL,
            "source_package_sha256": SOURCE_SHA,
            "classification": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "evidence_level": (
                "E2_LOCAL_CONFIG_FIX_PLUS_QUALIFIED_PROGRESS_DIAGNOSTICS"
            ),
            "configuration_rebuilt": True,
            "configuration_rebuilt_in_this_successor": True,
            "mapping_rebuilt": True,
            "bitstream_rebuilt": True,
            "execplan_rebuilt": True,
            "sca_semantics_rebuilt": True,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
            "formal_readback_claimed": False,
        }
    )
    refresh_receipts(manifest)
    manifest["cloud_rtl_authority"] = {
        "repository": "xlsjdjdk/Trassic2.0_RTL",
        "branch": "master",
        "approved_commit": "0ccae916ef61904a64d6cf8ec1d1931b45e428d8",
        "local_disk_commit": "0ccae916ef61904a64d6cf8ec1d1931b45e428d8",
        "identity_difference_blocks_compile_or_simulation": False,
        "actual_compile_identity_required_in_return": True,
    }
    manifest["v61_return_adjudication"] = {
        "return_sha256": RETURN_SHA,
        "status": "CONFIG_PE1_INPORT0_KEEP_LAST_INDEX_TOO_LOW",
        "last_proven_good": (
            "PHYSICAL_LC17_VALUE_ACCEPTED_BY_LC18_AND_PE7_THEN_LC18_"
            "GENERATED_INDEX3_TERMINAL_OUTPUT"
        ),
        "first_divergence": (
            "LC18_INDEX3_TERMINAL_TO_PE7_KEEP_INPORT0_RELEASE_AND_NEXT_"
            "PHYSICAL_LC17_ADVANCE"
        ),
        "root_cause": (
            "PE1 keep threshold 2 cannot release on LC9/physical-LC18 "
            "terminal last_index 3; physical LC17 is therefore blocked by "
            "PE7 inport0 while LC18 itself is ready"
        ),
        "functional_rtl_root_cause_proven": False,
        "configuration_root_cause_proven": True,
    }
    manifest["configuration_fix"] = {
        "owner": "Conv/SA owner",
        "leaf_changes": [
            {
                "path": "lc_pe_configs.PE1.inport0.keep_last_index",
                "old": 2,
                "new": 3,
            }
        ],
        "formula": (
            "keep_last_index = immediate buffer-loop terminal "
            "last_index = DRAM_LC.LC9.last_index = 3"
        ),
        "rtl_consumer": "IGA_PE_Inbuffer.sv:167",
        "dynamic_counterexample": {
            "LC18_terminal_index3_occurrences": 2,
            "LC17_to_LC18_ready": 1,
            "LC17_to_PE7_in0_ready": 0,
            "LC17_advance_count": 1,
        },
        "functional_rtl_changed": False,
        **injection,
    }
    matrix = [
        row
        for row in manifest.get("release_gate_matrix", [])
        if row.get("gate_id") not in {"MATERIALIZED_CONFIG", "materialized_config"}
    ]
    matrix.append(
        {
            "gate_id": "materialized_config",
            "applicability": "blocking_applicable",
            "blocking": True,
            "status": "PASS_PENDING_FINAL_ZIP_VALIDATION",
            "changed_surface": [
                "lc_pe_configs.PE1.inport0.keep_last_index 2->3",
                "final mapping/bitstream/execplan/SCA consumer closure",
            ],
            "evidence": [
                injection["local_rebuild_report"],
                injection["causal_transaction_ledger"],
                injection["boundary_microtrace"],
            ],
        }
    )
    manifest["release_gate_matrix"] = matrix
    manifest["files"] = package_records(package)
    write_json(path, manifest)
    manifest["files"] = package_records(package)
    write_json(path, manifest)


def build_directory(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise BuildError(f"refusing to overwrite:{package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="node0004-v61-source-") as temp:
        shutil.copytree(extract_source(Path(temp)), package)
    old_observer_sha, new_observer_sha = replace_identity(package)
    injection = inject_fresh_c0_assets(package)
    readme = package / "README.md"
    readme.write_text(
        "# node0004 v62 PE keep-terminal config fix\n\n"
        "Classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.\n\n"
        "The v61 formal return proves physical LC17 is ready toward LC18 but "
        "blocked only toward PE7 inport0 after LC18 emits terminal "
        "last_index=3. The active PE keep predicate releases only when "
        "`buffer_last_index <= keep_last_index`; the materialized value 2 "
        "therefore cannot release. v62 changes exactly "
        "`lc_pe_configs.PE1.inport0.keep_last_index: 2 -> 3` and freshly "
        "regenerates mapping, bitstream, execplan, and SCA. Numeric inputs, "
        "W3, qparams, matrices, golden, observer, timeout, backpressure, "
        "functional RTL, ISA, and hardware are frozen.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        package / "provenance/v61_to_v62_pekeep_fix.json",
        {
            "schema": "node0004-v61-to-v62-pekeep-config-fix-v1",
            "source_v61_sha256": SOURCE_SHA,
            "bound_v61_return_sha256": RETURN_SHA,
            "classification": "CONFIG_FUNCTIONAL_FIX",
            "changed_surface": [
                "fresh identity",
                "PE1 inport0 keep_last_index 2->3",
                "mapping/bitstream/execplan/SCA mechanical regeneration",
                "manifest/provenance/README",
            ],
            "frozen": [
                "numeric",
                "W3",
                "qparam",
                "tail",
                "workload matrices",
                "golden",
                "observer semantics",
                "timeout",
                "backpressure",
                "functional RTL",
                "ISA",
                "hardware",
                "active ndp-sim",
            ],
            "local_rebuild": injection,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    )
    update_path_budget(package)
    update_manifest(package, old_observer_sha, new_observer_sha, injection)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL,
        output / f"{INSTALL}.zip",
        output / f"{INSTALL}.zip.sha256",
        output / f"{INSTALL}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v62 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v62-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v62 deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v61-to-v62-pekeep-fix-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v61_sha256": SOURCE_SHA,
        "bound_v61_return_sha256": RETURN_SHA,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": True,
        "mapping_rebuilt": True,
        "bitstream_rebuilt": True,
        "execplan_rebuilt": True,
        "sca_semantics_rebuilt": True,
        "observer_semantics_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{INSTALL}.validation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
