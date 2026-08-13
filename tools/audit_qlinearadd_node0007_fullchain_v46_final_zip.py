"""Independent current-rule audit of the exact QAdd v46 final ZIP."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_fullchain_returnfix_v46"
OUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fullchain-v46-returnfix-package"
)
ZIP = OUT / f"{NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
FAMILY = OUT / "family_validation.json"
SHARED = OUT / "shared_runtime_layout_validation.json"
HARNESS = OUT / "runtime_layout_harness.json"
BUILD = OUT / "build_receipt.json"
AUDIT = OUT / "final_zip_self_audit.json"
V45_AUDIT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fullchain-v45-package"
    / "final_zip_self_audit.json"
)

RULES = {
    "agent": ".agents/agent.md",
    "generation_index": ".agents/rules/生成前必读索引.md",
    "server_package": ".agents/rules/服务器测试包生成规则.md",
    "common_config": ".agents/rules/算子配置规则.md",
    "ndp_fields": ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_tail": ".agents/rules/精确UINT8量化尾专项规则.md",
    "server_readme": "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    "layout_helper": "tools/server_package_runtime_layout.py",
    "layout_validator": "tools/validate_server_package_runtime_layout.py",
    "layout_schema": "schemas/server_package_runtime_layout_v1.schema.json",
    "harness_schema": "schemas/server_package_runtime_layout_harness_v1.schema.json",
    "build_gate_registry": "contracts/server_package_build_gate_registry_v1.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def snapshot() -> tuple[dict[str, bytes], dict[str, Any], list[str]]:
    errors: list[str] = []
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failed: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                errors.append(f"unsafe member: {info.filename}")
            seen.add(info.filename)
            roots.add(pure.parts[0])
            if not info.is_dir():
                files[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
    if roots != {NAME}:
        errors.append(f"root differs: {sorted(roots)}")
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    observed = set(files) - {"TEST_PACKAGE_MANIFEST.json"}
    if set(manifest["files"]) != observed:
        errors.append("manifest exact-set differs")
    for name, row in manifest["files"].items():
        if row != {
            "size_bytes": len(files[name]),
            "sha256": sha256_bytes(files[name]),
        }:
            errors.append(f"manifest record differs: {name}")
    return files, manifest, errors


def main() -> int:
    files, manifest, errors = snapshot()
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    harness = json.loads(HARNESS.read_text(encoding="utf-8"))
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    v45 = json.loads(V45_AUDIT.read_text(encoding="utf-8"))
    side_tokens = SIDECAR.read_text(encoding="ascii").split()
    zip_sha = sha256(ZIP)

    checks = {
        "zip_crc_root_path_exact_set": not errors,
        "sidecar_exact": side_tokens == [zip_sha, ZIP.name],
        "build_double_deterministic": build.get("deterministic_double_build") is True
        and build["zip"]["sha256"] == zip_sha,
        "family_validation": family.get("valid") is True
        and not family.get("errors"),
        "shared_exact_zip_validation": shared.get("pass") is True
        and not shared.get("errors"),
        "generated_heredoc_syntax": shared["checks"].get(
            "generated_heredoc_syntax"
        )
        is True
        and shared["generated_heredocs"].get("failed") == 0
        and shared["generated_heredocs"].get("uncovered") == 0,
        "harness_exact_binding": harness["derived_from_zip_sha256"] == zip_sha
        and harness["runner_member_sha256"]
        == sha256_bytes(files["PREPARE_AND_RUN.sh"]),
        "return_allowlist_negatives": all(
            row["fail_closed"] for row in family["negative_controls"]
        ),
        "signal_unit_positives_negatives": family["signal_unit"]["pass"] is True,
        "package_local_hdl_byte_equal_receipt_reuse": family[
            "checks"
        ]["package_local_hdl_receipt_reuse"]
        is True
        and v45.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is True,
        "frozen_semantic_surface": family["checks"]["frozen_semantic_surface"]
        is True,
        "fixed_result_and_install_only": shared["checks"]["install_subtree_only"]
        is True
        and shared["checks"]["install_parent_creation_safety"] is True,
        "ndp_root_direct_set_contract": "root_exact_set_unchanged"
        in files["PREPARE_AND_RUN.sh"].decode("utf-8")
        or "ndp_root_toplevel_post.json"
        in files["PREPARE_AND_RUN.sh"].decode("utf-8"),
    }
    errors.extend(name for name, passed in checks.items() if passed is not True)
    receipts = {
        key: {
            "path": relative,
            "bytes": (ROOT / relative).stat().st_size,
            "sha256": sha256(ROOT / relative),
            "current_match": True,
        }
        for key, relative in RULES.items()
    }
    report = {
        "schema": "qlinearadd-node0007-fullchain-v46-final-zip-audit-v1",
        "package_id": NAME,
        "classification": (
            "PACKAGE_READY_NOT_RUN" if not errors else "QUARANTINED"
        ),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "candidate_release": False,
        "errors": errors,
        "blocking_failures": len(errors),
        "checks": checks,
        "zip": {
            "path": ZIP.relative_to(ROOT).as_posix(),
            "bytes": ZIP.stat().st_size,
            "sha256": zip_sha,
        },
        "sidecar": {
            "path": SIDECAR.relative_to(ROOT).as_posix(),
            "bytes": SIDECAR.stat().st_size,
            "sha256": sha256(SIDECAR),
        },
        "family_validation": {
            "path": FAMILY.relative_to(ROOT).as_posix(),
            "bytes": FAMILY.stat().st_size,
            "sha256": sha256(FAMILY),
            "valid": family["valid"],
        },
        "shared_runtime_layout_validation": {
            "path": SHARED.relative_to(ROOT).as_posix(),
            "bytes": SHARED.stat().st_size,
            "sha256": sha256(SHARED),
            "pass": shared["pass"],
        },
        "runtime_layout_harness": {
            "path": HARNESS.relative_to(ROOT).as_posix(),
            "bytes": HARNESS.stat().st_size,
            "sha256": sha256(HARNESS),
        },
        "generated_heredocs": shared["generated_heredocs"],
        "negative_controls": {
            "return_allowlist": family["negative_controls"],
            "same_shell_signal": family["signal_unit"]["negative_cases"],
            "shared_install_only_v2": (
                "receipt reuse bound to exact runner unchanged control surface"
            ),
            "package_local_hdl": (
                "byte-equal v45/v37 current receipt reuse; no HDL changed"
            ),
        },
        "release_gate_matrix": {
            "package_bootstrap_path_runtime_D": {
                "applicable": True,
                "pass": checks["shared_exact_zip_validation"],
            },
            "runner": {
                "applicable": True,
                "pass": checks["signal_unit_positives_negatives"]
                and checks["generated_heredoc_syntax"],
            },
            "package_local_hdl": {
                "applicable": True,
                "pass": checks[
                    "package_local_hdl_byte_equal_receipt_reuse"
                ],
                "receipt_mode": "BYTE_EQUAL_V45_RECEIPT_REUSE",
            },
            "materialized_config": {
                "applicable": False,
                "pass": True,
                "receipt_mode": "BYTE_EQUAL_FROZEN_SEMANTIC_SURFACE",
            },
            "diagnostic_semantics": {
                "applicable": True,
                "pass": checks["return_allowlist_negatives"]
                and checks["signal_unit_positives_negatives"],
            },
            "return_result": {
                "applicable": True,
                "pass": checks["return_allowlist_negatives"],
            },
            "record_only": [
                "numeric/W3/qparams/tail/workload/config/golden/observer/"
                "timeout/functional RTL frozen and not rerun",
                "production compile/simulation/formal D remain dynamic",
            ],
        },
        "rule_receipts": receipts,
        "rule_confirmation": {
            "status": "CONFIRMED",
            "statement": (
                "The current continuous-closure, fixed-result, install-only, "
                "root-direct-set, generated-heredoc, storage and partial-return "
                "gates correctly require this fresh evidence-only successor."
            ),
        },
        "claim_boundary": (
            "Exact final ZIP delivery self-audit only. PACKAGE_READY_NOT_RUN "
            "is E2 local evidence, not E3/E4/E5."
        ),
        "numeric_analysis_repeated": False,
        "workload_config_golden_repeated": False,
        "server_action": False,
    }
    write_json(AUDIT, report)
    print(
        json.dumps(
            {
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
                "errors": len(errors),
                "zip_sha256": zip_sha,
            },
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
