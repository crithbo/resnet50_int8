from __future__ import annotations

import argparse
import copy
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v19_final_zip as prior  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v20_buffer_mode_fix"
SOURCE_NAME = "r5_n4_hw_v19_buffer0_flow_diag"
ZIP_SHA256 = "e67775aed87d2065f51190049a9a7ba05fb98de9ba08a4362901612248f92ead"
FRESH_CONFIG_SHA256 = (
    "e528e963ddd76d775dd648d54eaf8bf4114d0053e5035073b914d3e7625dd8e5"
)
FRESH_BITSTREAM_SHA256 = (
    "1baf6986561eb9812d2c6e9adbe1c0c8ded0a1fade72a64b198d4f437bdd2388"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    f"{SOURCE_NAME}.zip"
)
BITSTREAM_REL = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
ORIGINAL_VALIDATE = prior.validate_payload


def source_entries() -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise ValueError("source v19 ZIP CRC failed")
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.parts[0] != SOURCE_NAME or len(path.parts) < 2:
                continue
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            result[relative] = archive.read(info)
    return result


def functional_checks(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
) -> dict[str, bool]:
    fix = manifest.get("configuration_fix", {})
    changes = fix.get("leaf_changes", [])
    normalized = {
        item.get("path"): (item.get("old"), item.get("new"))
        for item in changes
        if isinstance(item, dict)
    }
    source = source_entries()
    matrices = [
        path
        for path in entries
        if path.startswith("workload/runtime/runs/c0/install/op_w0/")
        and "/matrix_" in path
    ]
    return {
        "functional_fix_identity": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("schema")
            == "resnet50-node0004-buffer-mode-config-fix-package-v20"
            and manifest.get("classification")
            == "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            and manifest.get("candidate_release") is False
            and manifest.get("formal_readback_claimed") is False
        ),
        "controlled_config_rebuild": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt") is True
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("server_action") is False
        ),
        "exact_two_mode_leaf_changes": (
            normalized
            == {
                "buffer_config.buffer0.mode": (0, 1),
                "buffer_config.buffer1.mode": (0, 1),
            }
            and len(changes) == 2
        ),
        "fresh_config_bound": (
            fix.get("fresh_config_sha256") == FRESH_CONFIG_SHA256
        ),
        "fresh_bitstream_bound": (
            prior.sha256_bytes(entries.get(BITSTREAM_REL, b""))
            == FRESH_BITSTREAM_SHA256
        ),
        "frozen_matrix_payloads_preserved": (
            len(matrices) == 84
            and all(source.get(path) == entries[path] for path in matrices)
        ),
        "rtl_mode_equation_recorded": (
            "array_req_addr=array_counter_1"
            in str(fix.get("formula", ""))
            and "array_life_cnt=array_counter_0"
            in str(fix.get("formula", ""))
            and fix.get("mode0_counterexample")
            == "row address sequence begins 0,1"
        ),
    }


def validate_payload(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    zip_sha256: str,
    project_root: Path,
) -> tuple[bool, list[str], dict[str, bool], dict[str, str]]:
    # Reuse v19's four-way observer, runtime, flow-boundary, rule, and source
    # closure checks while presenting only its old classification predicates
    # through a shadow manifest. The real v20 functional predicates are checked
    # independently below.
    shadow = copy.deepcopy(manifest)
    shadow["schema"] = "resnet50-node0004-buffer0-flow-diagnostic-package-v19"
    shadow["classification"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    shadow["configuration_rebuilt"] = False
    valid, errors, checks, source_receipts = ORIGINAL_VALIDATE(
        entries, shadow, positive, zip_sha256, project_root
    )
    checks.pop("diagnostic_only", None)
    checks.pop("no_semantic_rebuild", None)
    checks["install_identity"] = manifest.get("install_name") == INSTALL_NAME
    own = functional_checks(entries, manifest)
    checks.update(own)
    own_errors = [
        f"semantic check failed: {name}"
        for name, status in own.items()
        if not status
    ]
    errors.extend(own_errors)
    return valid and not own_errors, errors, checks, source_receipts


def extra_negatives(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    zip_sha256: str,
    project_root: Path,
) -> dict[str, Any]:
    cases: dict[str, tuple[dict[str, bytes], dict[str, Any]]] = {}

    missing_leaf = copy.deepcopy(manifest)
    missing_leaf["configuration_fix"]["leaf_changes"] = missing_leaf[
        "configuration_fix"
    ]["leaf_changes"][:1]
    cases["missing_buffer1_mode_leaf"] = (entries, missing_leaf)

    old_bitstream = dict(entries)
    old_bitstream[BITSTREAM_REL] = source_entries()[BITSTREAM_REL]
    old_bitstream_manifest = copy.deepcopy(manifest)
    old_bitstream_manifest["files"][BITSTREAM_REL] = prior.sha256_bytes(
        old_bitstream[BITSTREAM_REL]
    )
    cases["old_bitstream_reintroduced"] = (
        old_bitstream,
        old_bitstream_manifest,
    )

    not_rebuilt = copy.deepcopy(manifest)
    not_rebuilt["configuration_rebuilt"] = False
    cases["configuration_rebuild_not_declared"] = (entries, not_rebuilt)

    result: dict[str, Any] = {}
    for name, (changed_entries, changed_manifest) in cases.items():
        valid, errors, _, _ = validate_payload(
            changed_entries,
            changed_manifest,
            positive,
            zip_sha256,
            project_root,
        )
        result[name] = {
            "expected_exit_code": 1,
            "observed_exit_code": 0 if valid else 1,
            "failed_closed": not valid,
            "errors": errors,
        }
    result["all_failed_closed"] = all(
        item.get("failed_closed") is True for item in result.values()
    )
    return result


def audit(
    project_root: Path,
    zip_path: Path,
    sidecar_path: Path,
    positive_path: Path,
) -> dict[str, Any]:
    prior.INSTALL_NAME = INSTALL_NAME
    prior.ZIP_SHA256 = ZIP_SHA256
    prior.prior.INSTALL_NAME = INSTALL_NAME
    prior.validate_payload = validate_payload
    report = prior.audit(
        project_root, zip_path, sidecar_path, positive_path
    )

    entries, _ = prior.prior.read_zip(zip_path)
    manifest = json.loads(entries["package_manifest.json"])
    positive = json.loads(positive_path.read_text(encoding="utf-8"))
    extra = extra_negatives(
        entries,
        manifest,
        positive,
        prior.sha256_file(zip_path),
        project_root,
    )
    report["negative_controls"].update(
        {key: value for key, value in extra.items() if key != "all_failed_closed"}
    )
    all_closed = (
        report["negative_controls"].get("all_failed_closed") is True
        and extra["all_failed_closed"] is True
    )
    report["negative_controls"]["all_failed_closed"] = all_closed
    report["all_required_negative_controls_fail_closed"] = all_closed
    if not all_closed:
        report["errors"].append("v20 functional negative control did not fail closed")
    report["schema"] = "node0004-v20-final-zip-current-rule-audit-v1"
    report["configuration_rebuilt"] = True
    report["claim_boundary"] = (
        "local config-functional-fix delivery validation; no server compile, "
        "simulation, natural terminal, formal D, E4, or E5 claim"
    )
    report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = (
        not report["errors"] and all_closed
    )
    report["error_count"] = len(report["errors"])
    report["status"] = (
        "PACKAGE_READY_NOT_RUN"
        if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"]
        else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--positive-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.project_root.resolve(),
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.positive_control.resolve(),
    )
    args.output.resolve().write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
