from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (  # noqa: E402
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import (  # noqa: E402
    file_records,
)
from tools.validate_gap_node0071_canonical_package import (  # noqa: E402
    validate as validate_canonical,
)
from tools.validate_gap_node0071_observer_binding import (  # noqa: E402
    validate_with_negative_controls as validate_observer,
)
from tools.gap_node0071_package_observer_guard import (  # noqa: E402
    observer_precompile_receipt,
)
from tools.validate_gap_node0071_v8_dual_ingress import (  # noqa: E402
    validate as validate_dual_ingress,
)


INSTALL_NAME = "r5_n71_gap_v9_ingress_rule"
SOURCE_NAME = "r5_n71_gap_v8_dual_ingress"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v8_dual_ingress.zip"
)
SOURCE_SHA256 = (
    "cb1b43b3e8228951a2c62e8de02b36f17291a2561048cb1b36c0a9ed876b5a0f"
)
OUTPUT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
RULE_RECEIPTS = [
    {
        "path": ".agents/rules/生成前必读索引.md",
        "sha256":
            "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
        "reason": "current routing index reread after package generation",
        "current_match": True,
    },
    {
        "path": ".agents/rules/服务器测试包生成规则.md",
        "sha256":
            "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa",
        "reason": "current common server-package rules",
        "current_match": True,
    },
    {
        "path": ".agents/rules/GAP_int32_mac_bypass_rules.md",
        "sha256":
            "b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96",
        "reason": "GAP int32_mac frozen sum-stage family",
        "current_match": True,
    },
    {
        "path": ".agents/rules/GAP_probe_v7_validator_rules.md",
        "sha256":
            "4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf",
        "reason": "GAP dynamic observer/readback gates",
        "current_match": True,
    },
    {
        "path": ".agents/rules/精确UINT8量化尾专项规则.md",
        "sha256":
            "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
        "reason": "GAP exact UINT8 tail family",
        "current_match": True,
    },
]
APPLICABLE_RULE_IDS = [
    "CDA-SERVER-WORKLOAD-PROVENANCE-001",
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
    "CDA-SCA-D-TB-READBACK-LENGTH-001",
    "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
    "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
    "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
    "CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001",
    "CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001",
    "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
    "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
    "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
    "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
    "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
    "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
    "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
    "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
    "CDA-SERVER-RETURN-RECEIPT-001",
    "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
    "CDA-GAP-INT32MAC-NONTRANSOUT-001",
    "CDA-GAP-INT32MAC-DUAL-INPUT-001",
    "CDA-GAP-INT32MAC-NORMAL-FIFO-001",
    "CDA-GAP-INT32MAC-TREE-001",
    "CDA-GAP-INT32MAC-STAGE-MEMORY-001",
    "CDA-GAP-INT32MAC-STAGE1-ALIGNED-EVEN-ODD-001",
    "CDA-GAP-INT32MAC-SUM-STAGE-LOCAL-E2-001",
    "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
    "CDA-GA-OUTBUFFER-OCCUPANCY-001",
    "CDA-GA-INVALID-SLOT-ISOLATION-001",
    "CDA-GA-CROSS-BLOCK-INIT-001",
    "CDA-GAP-ORTHOGONAL-DEFECTS-001",
    "CDA-GAP-D-READBACK-COVERAGE-001",
    "CDA-MSE4-MONITOR-EVIDENCE-001",
    "CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001",
    "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
    "CDA-QUANT-TAIL-ZP-AFTER-ROUND-001",
    "CDA-QUANT-TAIL-MAGIC-DOMAIN-001",
    "CDA-QUANT-TAIL-CAPABILITY-MATRIX-001",
]
NOT_APPLICABLE = [
    {
        "rule_id": "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
        "reason": "package does not install or modify a server TB target",
    },
    {
        "rule_id": "CDA-SERVER-FOCUSED-IDENTITY-001",
        "reason":
            "user-supplied-root no-source-preflight profile intentionally "
            "does not inspect server source identity; E4/E5 remain blocked",
    },
    {
        "rule_id":
            "CDA-QUANT-TAIL-NODE0004-ASSUMED-SIGNED-INGRESS-001",
        "reason": "node0004-only execution override; target is node0071",
    },
    {
        "rule_id": "CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001",
        "reason":
            "node0071 frozen exact tail does not use the raw signed max0 guard",
    },
]


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    prefix = f"{SOURCE_NAME}/"
    result: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or info.filename in seen
            or (mode and stat.S_ISLNK(mode))
            or not info.filename.startswith(prefix)
        ):
            raise BuildError(f"unsafe source member: {info.filename}")
        seen.add(info.filename)
        if not info.is_dir():
            result.append(info)
    return result


def extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("frozen v8 source differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("frozen v8 source CRC differs")
        for info in safe_entries(archive):
            relative = PurePosixPath(info.filename).relative_to(SOURCE_NAME)
            target = package.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return package


def replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_identity(item) for key, item in value.items()}
    return value


def numeric_records(package: Path) -> dict[str, Any]:
    records = file_records(
        package / "workload", exclude_manifest=False
    )
    records.pop("sca_cfg.json")
    records.pop("sca_cfg_D.json")
    return records


def immutable_records(package: Path) -> dict[str, Any]:
    records = file_records(package, exclude_manifest=False)
    for relative in (
        "TEST_PACKAGE_MANIFEST.json",
        "README.md",
        "PREPARE_AND_RUN.sh",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
    ):
        records.pop(relative)
    return records


def rebind_sca(package: Path) -> None:
    for relative in ("workload/sca_cfg.json", "workload/sca_cfg_D.json"):
        path = package / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        replaced = replace_identity(value)
        if replaced == value:
            raise BuildError(f"identity absent: {relative}")
        write_json(path, replaced)


def preflight(package: Path) -> dict[str, Any]:
    process = subprocess.run(
        [
            sys.executable,
            str(
                package
                / "package_tools/gap_node0071_complete_server_runtime.py"
            ),
            "preflight",
            "--package-root",
            str(package),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if process.returncode != 0:
        raise BuildError(
            f"package preflight failed: {process.stdout} {process.stderr}"
        )
    result = json.loads(process.stdout)
    if result.get("valid") is not True:
        raise BuildError("package preflight receipt differs")
    return result


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = extract_source(destination)
    before = numeric_records(package)
    immutable_before = immutable_records(package)
    rebind_sca(package)
    observer_path = package / "tb_probe/native_return_observer.svh"
    observer_sha = sha256(observer_path)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_observer = source_manifest.get("package_local_observer")
    if (
        not isinstance(source_observer, dict)
        or source_observer.get("sha256") != observer_sha
    ):
        raise BuildError("frozen v8 observer identity differs")
    observer_gate = observer_precompile_receipt(package, observer_sha)
    if observer_gate.get("valid") is not True:
        raise BuildError("frozen v8 observer precompile static gate differs")
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner_path.write_text(
        runner_path.read_text(encoding="utf-8").replace(
            SOURCE_NAME, INSTALL_NAME
        ),
        encoding="utf-8",
        newline="\n",
    )
    (package / "README.md").write_text(
        "# GAP node0071 v9 current-rule receipt refresh\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It reuses "
        "the frozen v8 workload/config/golden/observer byte-for-byte and "
        "refreshes only identity, SCA namespace, manifest, README, and "
        "current-rule receipts for "
        "`CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001`. Run once with:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = replace_identity(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v9",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "current-rule receipt refresh for the frozen v8 dual-ingress "
                "diagnostic; observer algorithm, GAP sum/tail/golden/config/"
                "workload unchanged; no functional fix and no E3/E4/E5"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "source_numeric_payload_reused_without_rebuild": True,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
            "final_zip_rule_self_audit_contract": {
                "rule_id":
                    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
                "read_receipt": RULE_RECEIPTS,
                "applicable_rule_ids": APPLICABLE_RULE_IDS,
                "not_applicable": NOT_APPLICABLE,
                "all_current_match": True,
                "plan_sha256_mutable_provenance_only":
                    "9a5d9de4b48508fd19d6800c905abb865a03da7a1745eb5301e2ae4dc63244c9",
                "final_zip_independent_validator_required": True,
                "final_zip_rule_self_audit_pass":
                    "PENDING_EXTERNAL_RELEASE_REPORT",
            },
            "rule_receipts": {
                "generation_index_sha256":
                    RULE_RECEIPTS[0]["sha256"],
                "server_rule_sha256": RULE_RECEIPTS[1]["sha256"],
                "gap_int32_rule_sha256": RULE_RECEIPTS[2]["sha256"],
                "gap_probe_rule_sha256": RULE_RECEIPTS[3]["sha256"],
                "exact_uint8_tail_rule_sha256":
                    RULE_RECEIPTS[4]["sha256"],
                "current_match": True,
                "plan_sha256_mutable_provenance_only":
                    "9a5d9de4b48508fd19d6800c905abb865a03da7a1745eb5301e2ae4dc63244c9",
            },
            "dual_ingress_localization_contract": {
                "purpose":
                    "resolve the v7 interval from accepted MSE0 input to "
                    "absent dual-operand GA acceptance",
                "qualified_counters": {
                    "mse0_buf_accept":
                        "MSE0 mse2buf_wvalid && buf2mse_wreq_ready",
                    "mse3_buf_accept":
                        "MSE3 mse2buf_wvalid && buf2mse_wreq_ready",
                    "ga_operand0_capture":
                        "GA inbuffer ga_pe_inbuffer_enable[0]",
                    "ga_operand2_capture":
                        "GA inbuffer ga_pe_inbuffer_enable[2]",
                    "ga_accept":
                        "ga_pe_alu_pipeline0_enable && alu_input_valid_bit",
                },
                "summary_record": "DUAL_INGRESS_COUNTS",
                "canonical_progress_predicate_changed": False,
                "level_only_activity_counts_as_progress": False,
                "functional_behavior_changed": False,
            },
            "rule_drift_refresh": {
                "trigger_rule_id":
                    "CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001",
                "publication_record":
                    ".agents/task_records/"
                    "20260731_gap_dual_operand_ingress_observability_"
                    "rule_publication.md",
                "publication_record_sha256":
                    "b8f4519c4cd98aec22498b250269e884e69bd893a52db71cd486424651f801c6",
                "source_gap_dynamic_rule_sha256":
                    "2dee42a883bde9c1650710c8312d23e661aeb3c66ef9d1d4e15524af79c33dc7",
                "current_gap_dynamic_rule_sha256":
                    "4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf",
                "source_v8_zip_sha256": SOURCE_SHA256,
                "source_v8_bytes_unchanged": True,
                "observer_algorithm_changed": False,
                "allowed_changed_paths": [
                    "TEST_PACKAGE_MANIFEST.json",
                    "README.md",
                    "PREPARE_AND_RUN.sh",
                    "workload/sca_cfg.json",
                    "workload/sca_cfg_D.json",
                ],
            },
        }
    )
    package_observer = manifest.get("package_local_observer")
    binding_contract = manifest.get("observer_binding_contract")
    if not isinstance(package_observer, dict) or not isinstance(
        binding_contract, dict
    ):
        raise BuildError("observer manifest contracts differ")
    if (
        package_observer.get("sha256") != observer_sha
        or binding_contract.get("source_sha256") != observer_sha
    ):
        raise BuildError("v9 observer algorithm or receipt drifted")
    provenance = manifest.get("generation_provenance")
    if not isinstance(provenance, dict):
        raise BuildError("generation provenance differs")
    provenance.update(
        {
            "tool":
                "tools/build_gap_node0071_v9_ingress_rule_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change":
                "identity/SCA namespace/manifest/README/current-rule receipt only",
        }
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    checked = preflight(package)
    after = numeric_records(package)
    if before != after:
        raise BuildError("frozen numeric workload drifted")
    immutable_after = immutable_records(package)
    if immutable_before != immutable_after:
        raise BuildError("non-receipt payload drifted")
    return package, {
        "numeric_workload_tree_equal": True,
        "numeric_workload_file_count": len(after),
        "immutable_nonreceipt_tree_equal": True,
        "immutable_nonreceipt_file_count": len(immutable_after),
        "observer_sha256": observer_sha,
        "package_preflight": checked,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v9-repeat-"
    ) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
        if (
            sha256(repeated_zip) != first_sha
            or file_records(repeated, exclude_manifest=False)
            != first_tree
        ):
            raise BuildError("repeat build differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def fresh_preflight(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v9-fresh-"
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        package = root / INSTALL_NAME
        before = file_records(package, exclude_manifest=False)
        checked = preflight(package)
        after = file_records(package, exclude_manifest=False)
        if before != after:
            raise BuildError("fresh preflight mutated package")
    return {"tree_unchanged": True, "preflight": checked}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation_path):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        fresh = fresh_preflight(zip_path)
        canonical = validate_canonical(zip_path)
        observer = validate_observer(zip_path)
        dual_ingress = validate_dual_ingress(zip_path)
        validation = {
            "schema":
                "gap-node0071-ingress-rule-refresh-validation-v9",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "source_v8_quarantined_for_rule_drift": True,
            "numeric_workload_tree_equal":
                proof["numeric_workload_tree_equal"],
            "numeric_workload_file_count":
                proof["numeric_workload_file_count"],
            "immutable_nonreceipt_tree_equal":
                proof["immutable_nonreceipt_tree_equal"],
            "immutable_nonreceipt_file_count":
                proof["immutable_nonreceipt_file_count"],
            "observer_sha256": proof["observer_sha256"],
            "package_preflight": proof["package_preflight"],
            "canonical_decision_validation": canonical,
            "observer_four_way_validation": observer,
            "dual_ingress_validation": dual_ingress,
            "functional_fix": False,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "server_action": False,
            "repeated_build": repeated,
            "fresh_extract_preflight": fresh,
        }
        write_json(validation_path, validation)
    except Exception as error:
        print(f"GAP v9 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
