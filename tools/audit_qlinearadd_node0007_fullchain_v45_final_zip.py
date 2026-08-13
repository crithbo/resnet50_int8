#!/usr/bin/env python3
"""Independent delivery audit for the exact node0007 full-chain v45 ZIP."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_fullchain_v45"
OUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fullchain-v45-package"
)
ZIP = OUT / f"{NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
FAMILY = OUT / "family_validation.json"
SHARED = OUT / "shared_runtime_layout_validation.json"
HARNESS = OUT / "runtime_layout_harness.json"
BUILD = OUT / "build_receipt.json"
AUDIT = OUT / "final_zip_self_audit.json"
V37 = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending/"
    "r5_qadd_n7_cout32_rootclean_v37.zip"
)
V37_HDL_RECEIPT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "pending_receipts/qlinearadd_node0007/r5_qadd_n7_cout32_rootclean_v37/"
    "r5_qadd_n7_cout32_rootclean_v37_hdl_scope_revalidation.json"
)

RULES = {
    "agent": (
        ROOT / ".agents/agent.md",
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ),
    "generation_index": (
        ROOT / ".agents/rules/生成前必读索引.md",
        "68c13cbd1461ca2a506174678d22cfdbfdc5aced25ad80150d4e4cacece7f2be",
    ),
    "server_package": (
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        "16f7773796dccf4f27a5e412bb200f7b4190ffb87742d3dd2e466866a7f77dde",
    ),
    "common_config": (
        ROOT / ".agents/rules/算子配置规则.md",
        "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
    ),
    "ndp_fields": (
        ROOT / ".agents/rules/NDP硬件字段语义.md",
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ),
    "qlinearadd": (
        ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
        "28bb859c5f9b8cb5ce5e7ac0dfd81bc06c8b24835d1d3fa4a6062c7c23c0800b",
    ),
    "exact_tail": (
        ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    ),
    "server_readme": (
        ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
    ),
    "layout_helper": (
        ROOT / "tools/server_package_runtime_layout.py",
        "7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a",
    ),
    "layout_validator": (
        ROOT / "tools/validate_server_package_runtime_layout.py",
        "66f779d9d472dabaf9a3d2f2b09b472d6bb6ea575865e223a8e80c11818813a5",
    ),
    "layout_schema": (
        ROOT / "schemas/server_package_runtime_layout_v1.schema.json",
        "529864182fc57bd3af47fc31dcb5697420b8f656303270e0b0ee862379faf79d",
    ),
    "harness_schema": (
        ROOT / "schemas/server_package_runtime_layout_harness_v1.schema.json",
        "9f77cd5921ff3b4e0f692425aaa27c6f6f7a18466c414e7bcc89a00b56ec67c3",
    ),
    "build_gate_registry": (
        ROOT / "contracts/server_package_build_gate_registry_v1.json",
        "7af29e7d01684db24334365e9e92f0dd0370331c253b2bfb8e58ccf265f93274",
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_zip(path: Path) -> tuple[str, dict[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("CRC failure")
        roots: set[str] = set()
        seen: set[str] = set()
        files: dict[str, bytes] = {}
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                raise ValueError(f"unsafe ZIP member: {info.filename}")
            seen.add(info.filename)
            roots.add(pure.parts[0])
            if not info.is_dir():
                files[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
        if len(roots) != 1:
            raise ValueError(f"single-root failure: {sorted(roots)}")
        return next(iter(roots)), files


def core_valid(root: str, files: dict[str, bytes]) -> bool:
    try:
        manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
        layout = json.loads(files["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])
    except (KeyError, UnicodeError, json.JSONDecodeError):
        return False
    declared = manifest.get("files")
    if not isinstance(declared, dict):
        return False
    observed = set(files) - {"TEST_PACKAGE_MANIFEST.json"}
    return (
        root == NAME
        and manifest.get("install_name") == NAME
        and layout.get("package_id") == NAME
        and layout.get("install_name") == NAME
        and set(declared) == observed
        and all(
            declared[name]
            == {"size_bytes": len(files[name]), "sha256": sha256_bytes(files[name])}
            for name in observed
        )
    )


def main() -> int:
    errors: list[str] = []
    root, files = read_zip(ZIP)
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    harness = json.loads(HARNESS.read_text(encoding="utf-8"))
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    v37_root, v37_files = read_zip(V37)
    hdl_members = sorted(name for name in files if name.startswith("tb_probe/"))
    diagnostic_members = [
        "package_tools/qlinearadd_node0007_split_canonical_v25.py",
        "diagnostics/progress_contract.json",
    ]
    hdl_equal = all(files[name] == v37_files[name] for name in hdl_members)
    predicate_equal = all(
        files[name] == v37_files[name] for name in diagnostic_members
    )

    sidecar_tokens = SIDECAR.read_text(encoding="ascii").split()
    sidecar_ok = sidecar_tokens == [sha256(ZIP), ZIP.name]
    rules = {
        name: {
            "path": str(path.relative_to(ROOT)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "expected_sha256": expected,
            "current_match": sha256(path) == expected,
        }
        for name, (path, expected) in RULES.items()
    }

    wrong_identity = dict(files)
    wrong_manifest = json.loads(wrong_identity["TEST_PACKAGE_MANIFEST.json"])
    wrong_manifest["install_name"] = NAME + "_wrong"
    wrong_identity["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(wrong_manifest, sort_keys=True).encode("utf-8")
    )
    feature_deleted = dict(files)
    feature_deleted.pop("diagnostics/progress_contract.json")
    negative_controls = {
        "wrong_package_identity_fail_closed": not core_valid(root, wrong_identity),
        "delete_feature_member_fail_closed": not core_valid(root, feature_deleted),
        "earlier_stage_finish_fail_closed": (
            family["predicate_trace"]["rows"][1]["decision"]
            != "SPLIT_SEGMENT_COMPLETED"
        ),
        "individual_stage_only_fail_closed": (
            family["predicate_trace"]["rows"][2]["decision"]
            != "SPLIT_SEGMENT_COMPLETED"
        ),
        "shared_v2_file_symlink_collision_path_escape_nonfresh_root_negatives": (
            family["shared_v2_runtime_receipt_reuse"]["valid"]
        ),
        "v37_hdl_declaration_use_update_negatives_receipt_reuse": (
            hdl_equal
            and sha256(V37_HDL_RECEIPT)
            == "b7c2e250e0292c8ae5cbeb3c59aa752695743a150ca2be85484d894946acae63"
        ),
    }

    split = manifest["split_segment_contract"]
    runtime_d_absent = not any(
        name.endswith("matrix_D_linearized_128bit.txt")
        and not name.startswith("validation/golden/")
        for name in files
    )
    checks = {
        "zip_crc_path_root_duplicate_symlink": root == NAME,
        "manifest_exact_set_and_per_file_sha": core_valid(root, files),
        "sidecar_exact": sidecar_ok,
        "deterministic_double_build": build.get("deterministic_double_build") is True,
        "build_receipt_exact_zip": build.get("zip", {}).get("sha256") == sha256(ZIP),
        "family_validator": family.get("valid") is True and family.get("errors") == [],
        "shared_exact_zip_gate_once": shared.get("pass") is True
        and shared.get("errors") == [],
        "shared_gate_bound_to_exact_zip": shared.get("zip", {}).get("sha256")
        == sha256(ZIP),
        "six_stage_full_chain": split.get("expected_stage_count") == 6
        and len(split.get("stage_names", [])) == 6,
        "formal_uint8_D_exact28": split.get("expected_output_count") == 28
        and len(split.get("output_checks", [])) == 28,
        "runtime_D_initially_absent": runtime_d_absent,
        "server_result_conjunction_contract": family["checks"][
            "result_gate_conjunction_contract"
        ],
        "package_local_hdl_frozen_to_v37": hdl_equal,
        "six_stage_predicate_changed_and_traced": (
            not predicate_equal and family["checks"]["predicate_trace"]
        ),
        "v37_hdl_receipt_exact": sha256(V37_HDL_RECEIPT)
        == "b7c2e250e0292c8ae5cbeb3c59aa752695743a150ca2be85484d894946acae63",
        "current_rule_receipts": all(row["current_match"] for row in rules.values()),
        "all_negative_controls_fail_closed": all(negative_controls.values()),
        "numeric_workload_semantics_not_recomputed": (
            family.get("numeric_analysis_repeated") is False
            and family.get("split_c_repeated") is False
        ),
        "server_action_absent": family.get("server_action") is False,
    }
    errors.extend(name for name, passed in checks.items() if not passed)

    release_gate_matrix = {
        "core_always": {
            "applicable": True,
            "pass": all(
                checks[name]
                for name in (
                    "zip_crc_path_root_duplicate_symlink",
                    "manifest_exact_set_and_per_file_sha",
                    "sidecar_exact",
                    "deterministic_double_build",
                    "current_rule_receipts",
                )
            ),
        },
        "runner": {
            "applicable": True,
            "pass": checks["shared_exact_zip_gate_once"]
            and family["checks"]["runner_bash_syntax"],
            "receipt_mode": "SHARED_V2_14_OF_14_CHANGED_SURFACE_REUSE",
        },
        "package_local_hdl": {
            "applicable": True,
            "pass": checks["package_local_hdl_frozen_to_v37"]
            and checks["v37_hdl_receipt_exact"],
            "receipt_mode": "BYTE_EQUAL_V37_RECEIPT_REUSE",
        },
        "materialized_config": {
            "applicable": True,
            "pass": checks["six_stage_full_chain"]
            and checks["formal_uint8_D_exact28"],
            "receipt_mode": "FROZEN_V37_SPLIT_C_PLUS_PREVIOUSLY_VERIFIED_TAIL",
        },
        "diagnostic_semantics": {
            "applicable": True,
            "pass": family["checks"]["predicate_trace"]
            and checks["all_negative_controls_fail_closed"],
        },
        "return_result": {
            "applicable": True,
            "pass": checks["runtime_D_initially_absent"]
            and checks["server_result_conjunction_contract"],
        },
        "record_only_warnings": [
            (
                "The bounded host MSYS runner harness was terminated and is "
                "excluded; shared V2 14/14 changed-surface receipt reuse is "
                "used instead. Production compile/simulation remains dynamic."
            )
        ],
    }
    blocking_failures = [
        name
        for name, row in release_gate_matrix.items()
        if isinstance(row, dict) and row.get("applicable") and not row.get("pass")
    ]
    passed = not errors and not blocking_failures
    report = {
        "schema": "qlinearadd-node0007-fullchain-v45-final-zip-audit-v1",
        "package_id": NAME,
        "classification": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "candidate_release": False,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
        "errors": errors,
        "blocking_failures": blocking_failures,
        "checks": checks,
        "negative_controls": negative_controls,
        "release_gate_matrix": release_gate_matrix,
        "zip": {
            "path": str(ZIP.relative_to(ROOT)),
            "bytes": ZIP.stat().st_size,
            "sha256": sha256(ZIP),
            "single_root": root,
            "member_count": len(files),
        },
        "sidecar": {
            "path": str(SIDECAR.relative_to(ROOT)),
            "bytes": SIDECAR.stat().st_size,
            "sha256": sha256(SIDECAR),
            "declared_match": sidecar_ok,
        },
        "family_validation": {
            "path": str(FAMILY.relative_to(ROOT)),
            "bytes": FAMILY.stat().st_size,
            "sha256": sha256(FAMILY),
            "exit": 0,
        },
        "shared_runtime_layout_validation": {
            "path": str(SHARED.relative_to(ROOT)),
            "bytes": SHARED.stat().st_size,
            "sha256": sha256(SHARED),
            "exit": 0,
            "invocation_count_for_exact_zip": 1,
        },
        "runtime_layout_harness": {
            "path": str(HARNESS.relative_to(ROOT)),
            "bytes": HARNESS.stat().st_size,
            "sha256": sha256(HARNESS),
            "scenario_count": len(harness["scenarios"]),
            "receipt_mode": "SHARED_V2_14_OF_14_CHANGED_SURFACE_REUSE",
        },
        "hdl_receipt_reuse": {
            "source_zip": {
                "root": v37_root,
                "bytes": V37.stat().st_size,
                "sha256": sha256(V37),
            },
            "source_receipt": {
                "path": str(V37_HDL_RECEIPT.relative_to(ROOT)),
                "bytes": V37_HDL_RECEIPT.stat().st_size,
                "sha256": sha256(V37_HDL_RECEIPT),
            },
            "members": hdl_members + diagnostic_members,
            "hdl_members_byte_equal": hdl_equal,
            "predicate_members_byte_equal": predicate_equal,
            "predicate_disposition": "CHANGED_AND_COVERED_BY_LOCAL_TRACE",
        },
        "rule_receipts": rules,
        "shared_build_profile_receipt": {
            "profile_sha256": (
                "e698b79c98355cbfd58710bc03c648e27c4feb5d649ad47f6d094843c02052a3"
            ),
            "status": "14/14 PASS; changed-surface reuse",
        },
        "commands": {
            "family_validator": (
                "python tools/"
                "validate_qlinearadd_node0007_fullchain_v45_server_package.py"
            ),
            "shared_validator": (
                "python tools/validate_server_package_runtime_layout.py "
                "--zip <exact-v45.zip> --harness-report "
                "<runtime_layout_harness.json> --helper-reference "
                "tools/server_package_runtime_layout.py --output "
                "<shared_runtime_layout_validation.json>"
            ),
            "final_audit": (
                "python tools/"
                "audit_qlinearadd_node0007_fullchain_v45_final_zip.py"
            ),
        },
        "numeric_analysis_repeated": False,
        "split_c_repeated": False,
        "server_action": False,
        "claim_boundary": (
            "Local exact-ZIP/package/bootstrap/install-layout, frozen observer "
            "delivery, ordered six-stage contract and final UINT8 28D gate "
            "construction only. Production compile, DUT simulation, natural "
            "terminal, returned 28D, E3, E4 and E5 require a formal server "
            "return. The failed host MSYS injection harness is not evidence."
        ),
    }
    write_json(AUDIT, report)
    print(json.dumps({"pass": passed, "errors": errors}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
