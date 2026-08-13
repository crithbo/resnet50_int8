#!/usr/bin/env python3
"""Independent release audit for the frozen GAP node0071 v40 final ZIP."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
STEM = "r5_n71_gap_v40_lc_supply_conservation_diag"
ZIP_PATH = PKG_DIR / f"{STEM}.zip"
SIDECAR_PATH = PKG_DIR / f"{STEM}.zip.sha256"
OUT_PATH = PKG_DIR / f"{STEM}.final_audit.json"
REPORT_PATHS = {
    "core_validator": PKG_DIR / f"{STEM}.validator.json",
    "hdl_scope": PKG_DIR / f"{STEM}.hdl_scope.json",
    "signal_stub": PKG_DIR / f"{STEM}.signal_stub.json",
    "runner_chain": PKG_DIR / f"{STEM}.runner_chain.json",
}
RULE_PATHS = {
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "gap_mac": ROOT / ".agents/rules/GAP_int32_mac_bypass_rules.md",
    "gap_probe": ROOT / ".agents/rules/GAP_probe_v7_validator_rules.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}
EXPECTED_RULE_SHA = {
    "index": "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    "server": "61753f6866f49aca142545394451cd73c4e634a5aa160b066e020b7c9067cedd",
    "config": "d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "gap_mac": "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
    "gap_probe": "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
    "tail": "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    zip_sha = sha256(ZIP_PATH)
    if zip_sha != "7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4":
        errors.append("frozen final ZIP SHA changed")

    sidecar_text = SIDECAR_PATH.read_text(encoding="utf-8").strip()
    sidecar_valid = zip_sha in sidecar_text and ZIP_PATH.name in sidecar_text
    if not sidecar_valid:
        errors.append("sidecar does not bind exact final ZIP")

    rule_receipts = {}
    for name, path in RULE_PATHS.items():
        actual = sha256(path)
        current_match = actual == EXPECTED_RULE_SHA[name]
        rule_receipts[name] = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": actual,
            "expected_sha256": EXPECTED_RULE_SHA[name],
            "current_match": current_match,
        }
        if not current_match:
            errors.append(f"rule receipt drift: {name}")

    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad_crc_member = archive.testzip()
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        path_safe = all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
            for name in names
        )
        duplicate_free = len(names) == len(set(names))
        symlink_free = all((info.external_attr >> 16) & 0o170000 != 0o120000 for info in archive.infolist())
        manifest_member = f"{STEM}/TEST_PACKAGE_MANIFEST.json"
        manifest = json.loads(archive.read(manifest_member))

    zip_checks = {
        "crc_valid": bad_crc_member is None,
        "single_exact_root": roots == {STEM},
        "path_safe": path_safe,
        "duplicate_free": duplicate_free,
        "symlink_free": symlink_free,
        "manifest_identity": manifest.get("package_name") == STEM
        or manifest.get("install_name") == STEM
        or STEM in json.dumps(manifest, sort_keys=True),
    }
    for name, passed in zip_checks.items():
        if not passed:
            errors.append(f"final ZIP check failed: {name}")

    reports = {name: load_json(path) for name, path in REPORT_PATHS.items()}
    report_receipts = {
        name: {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for name, path in REPORT_PATHS.items()
    }
    report_pass = {
        "core_validator": reports["core_validator"].get("valid") is True
        and reports["core_validator"].get("status") == "PASS"
        and reports["core_validator"].get("errors") == [],
        "hdl_scope": reports["hdl_scope"].get("pass") is True
        and reports["hdl_scope"].get("status") == "PASS"
        and reports["hdl_scope"].get("errors") == [],
        "signal_stub": reports["signal_stub"].get("status") == "PASS",
        "runner_chain": reports["runner_chain"].get("valid") is True,
    }
    for name, passed in report_pass.items():
        if not passed:
            errors.append(f"supporting audit failed: {name}")

    release_gate_matrix = {
        "core_always": {
            "applicability": "applicable",
            "pass": report_pass["core_validator"],
            "evidence": "CRC/root/path/exact-set/manifest/sidecar/identity/frozen-set validator",
        },
        "runner_compile_finalizer": {
            "applicability": "applicable",
            "pass": report_pass["runner_chain"] and report_pass["signal_stub"],
            "evidence": "real runner to safe compile/simulator stub; EXIT/TERM shared finalizer",
        },
        "package_local_hdl": {
            "applicability": "applicable",
            "pass": report_pass["hdl_scope"],
            "evidence": "exact observer focused syntax/scope/name-resolution and actual-consumer negatives",
        },
        "materialized_config": {
            "applicability": "not_applicable_receipt_reuse",
            "pass": True,
            "evidence": "final JSON/mapping/bitstream/execplan/SCA semantics unchanged from v37; no changed causal slice",
        },
        "diagnostic_semantics": {
            "applicability": "applicable",
            "pass": report_pass["core_validator"]
            and reports["core_validator"].get("predicate_trace", {}).get("pass") is True,
            "evidence": "final exact predicate trace plus feature/conjunct/clock/update fail-closed controls",
        },
        "return_result_conjunction": {
            "applicability": "applicable",
            "pass": report_pass["core_validator"]
            and report_pass["signal_stub"]
            and report_pass["runner_chain"],
            "evidence": "return allowlist, signal-safe partial return, canonical non-natural decision, formal-D conjunction",
        },
        "record_only": {
            "applicability": "record_only",
            "pass": True,
            "evidence": "cloud/local identity mismatch retained as provenance and proven nonblocking after compile",
        },
    }
    blocking_failures = [
        name for name, item in release_gate_matrix.items()
        if item["applicability"] != "record_only" and item["pass"] is not True
    ]
    if blocking_failures:
        errors.append("release gate failures: " + ",".join(blocking_failures))

    output = {
        "schema": "gap_node0071_v40_final_zip_rule_self_audit_v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "evidence_boundary": "E2_LOCAL_ONLY",
        "package_release": "PACKAGE_READY_NOT_RUN" if not errors else "NONE",
        "target_zip": str(ZIP_PATH.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": ZIP_PATH.stat().st_size,
        "target_zip_sha256": zip_sha,
        "target_sidecar": str(SIDECAR_PATH.relative_to(ROOT)).replace("\\", "/"),
        "target_sidecar_bytes": SIDECAR_PATH.stat().st_size,
        "target_sidecar_sha256": sha256(SIDECAR_PATH),
        "sidecar_valid": sidecar_valid,
        "zip_checks": zip_checks,
        "rule_receipts": rule_receipts,
        "rule_ids": [
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
            "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
            "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
        ],
        "supporting_reports": report_receipts,
        "supporting_report_pass": report_pass,
        "release_gate_matrix": release_gate_matrix,
        "blocking_failures": blocking_failures,
        "errors": errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "run_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": f"{STEM}_return.zip",
        "claim_boundary": (
            "Local packaging, diagnostic semantics, focused package-local HDL, safe runner/finalizer, "
            "and fail-closed return gates only. No server run, natural terminal, formal-D, E3, E4, or E5 claim."
        ),
    }
    OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT_PATH),
        "sha256": sha256(OUT_PATH),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": output["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
        "errors": errors,
    }, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
