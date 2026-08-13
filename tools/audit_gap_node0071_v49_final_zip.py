#!/usr/bin/env python3
"""Independent final-ZIP rule self-audit for GAP node0071 v49."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v49_mse4_maskwide_diag"
EXPECTED = {
    ".agents/agent.md":
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ".agents/rules/生成前必读索引.md":
        "3c2bd9017f351b6456eac49c966063cc9b76e96420d71162a1ca57d1b62b552c",
    ".agents/rules/服务器测试包生成规则.md":
        "89d27141f1a151ef5e6cc98603238050c9b0442a3d1937b2ec23cf92e55a27a2",
    ".agents/rules/算子配置规则.md":
        "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
    ".agents/rules/NDP硬件字段语义.md":
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ".agents/rules/GAP_int32_mac_bypass_rules.md":
        "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
    ".agents/rules/GAP_probe_v7_validator_rules.md":
        "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
    ".agents/rules/精确UINT8量化尾专项规则.md":
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md":
        "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip-a", type=Path, required=True)
    parser.add_argument("--zip-b", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--family-report", type=Path, required=True)
    parser.add_argument("--shared-report", type=Path, required=True)
    parser.add_argument("--shared-harness", type=Path, required=True)
    parser.add_argument("--shadow-profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {key: value.resolve() for key, value in vars(args).items()
             if isinstance(value, Path)}
    errors: list[str] = []
    zip_a = paths["zip_a"]
    zip_b = paths["zip_b"]
    sidecar = paths["sidecar"]
    family = load(paths["family_report"])
    shared = load(paths["shared_report"])
    harness = load(paths["shared_harness"])
    profile = load(paths["shadow_profile"])

    rule_receipts = {}
    for name, expected in EXPECTED.items():
        path = ROOT / name
        actual = sha(path)
        rule_receipts[name] = {
            "bytes": path.stat().st_size,
            "sha256": actual,
            "expected_sha256": expected,
            "current_match": actual == expected,
        }
        if actual != expected:
            errors.append(f"current rule drift: {name}")
    plan = ROOT / ".agents/plan.md"
    rule_receipts[".agents/plan.md"] = {
        "bytes": plan.stat().st_size,
        "sha256": sha(plan),
        "mutable_provenance_only": True,
    }

    with zipfile.ZipFile(zip_a) as archive:
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        crc = archive.testzip()
        symlink_free = all(
            ((info.external_attr >> 16) & 0o170000) != 0o120000
            for info in archive.infolist()
        )
        manifest = json.loads(
            archive.read(f"{NAME}/TEST_PACKAGE_MANIFEST.json")
        )
    zip_sha = sha(zip_a)
    sidecar_valid = (
        sidecar.read_text(encoding="ascii").strip()
        == f"{zip_sha}  {zip_a.name}"
    )
    zip_checks = {
        "deterministic_double_build": sha(zip_b) == zip_sha,
        "deterministic_double_build_bytes":
            zip_b.stat().st_size == zip_a.stat().st_size,
        "crc": crc is None,
        "single_root": roots == {NAME},
        "path_safe": all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name for name in names
        ),
        "duplicate_free": len(names) == len(set(names)),
        "symlink_free": symlink_free,
        "sidecar": sidecar_valid,
        "manifest_identity": manifest.get("install_name") == NAME,
    }
    errors.extend(f"zip:{name}" for name, ok in zip_checks.items() if not ok)

    report_checks = {
        "family_valid":
            family.get("valid") is True and family.get("errors") == [],
        "family_binds_zip":
            family.get("target_zip_sha256") == zip_sha,
        "shared_pass":
            shared.get("pass") is True and shared.get("errors") == [],
        "shared_binds_zip":
            shared.get("zip", {}).get("sha256") == zip_sha,
        "shared_exact_invocation":
            harness.get("derived_from_zip_sha256") == zip_sha,
        "shared_v2_14_of_14_reuse":
            harness.get("receipt_reuse", {}).get("shared_control_flow")
            == "INSTALL_ONLY_V2_14_OF_14_PASS",
        "shadow_contract":
            profile.get("contract_valid") is True
            and profile.get("preflight", {}).get("errors") == [],
    }
    errors.extend(f"report:{name}" for name, ok in report_checks.items() if not ok)

    release_gate_matrix = {
        "package_bootstrap_path_runtime": {
            "applicability": "blocking_applicable",
            "pass": report_checks["shared_pass"],
            "evidence": "exact final ZIP shared install-only V2 validator",
        },
        "runner_compile_finalizer": {
            "applicability": "blocking_applicable",
            "pass": report_checks["shared_v2_14_of_14_reuse"]
            and family["checks"]["runner"]["observer_absent_fail_closed"]
            and family["checks"]["runner"]["fallback_heredoc_syntax_fixed"]
            and family["checks"]["runner"]["fallback_all_four_outputs"],
            "evidence":
                "shared normal/preflight/compile/HUP/INT/TERM receipt plus "
                "GAP early-failure fail-closed decision output",
        },
        "package_local_hdl": {
            "applicability": "blocking_applicable",
            "pass": all(family["checks"]["hdl"].values()),
            "evidence":
                "exact changed observer focused positive and declaration/use/update negatives",
        },
        "materialized_config": {
            "applicability": "not_applicable_receipt_reuse",
            "pass": family["checks"]["frozen"]["numeric_73_exact"]
            and family["checks"]["frozen"]["config_mapping_exact"],
            "evidence":
                "73 numeric and all config/mapping/bitstream/execplan bytes "
                "equal to v47; SCA identity/output transport only",
        },
        "diagnostic_semantics": {
            "applicability": "blocking_applicable",
            "pass": all(family["checks"]["predicate"].values()),
            "evidence":
                "exact parser trace; HEARTBEAT stable level counts zero progress",
        },
        "return_result_conjunction": {
            "applicability": "blocking_applicable",
            "pass": all(family["checks"]["runner"].values()),
            "evidence":
                "77-item allowlist, 48 formal readbacks, runtime-D absent, "
                "signal-safe partial decisions and fixed simresult",
        },
        "report_style": {
            "applicability": "record_only",
            "pass": True,
            "evidence": "nonfunctional metadata",
        },
    }
    blocking = [
        name for name, row in release_gate_matrix.items()
        if row["applicability"] == "blocking_applicable"
        and row["pass"] is not True
    ]
    errors.extend(f"release_gate:{name}" for name in blocking)

    result = {
        "schema": "gap-node0071-v49-final-zip-rule-self-audit-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "evidence_ceiling": "E2_LOCAL_ONLY",
        "target_zip": str(zip_a.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": zip_a.stat().st_size,
        "target_zip_sha256": zip_sha,
        "target_sidecar": str(sidecar.relative_to(ROOT)).replace("\\", "/"),
        "target_sidecar_bytes": sidecar.stat().st_size,
        "target_sidecar_sha256": sha(sidecar),
        "zip_checks": zip_checks,
        "report_checks": report_checks,
        "rule_receipts": rule_receipts,
        "release_gate_matrix": release_gate_matrix,
        "blocking_failures": blocking,
        "shared_exact_final_zip_invocation_count": 1,
        "errors": errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "package_release": "PACKAGE_READY_NOT_RUN" if not errors else "NONE",
        "server_command":
            f"bash {NAME}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "fixed_return":
            f"/home/panqs/ndp/simresult/{NAME}_return.zip",
        "fixed_return_sidecar":
            f"/home/panqs/ndp/simresult/{NAME}_return.zip.sha256",
        "claim_boundary":
            "Local final-ZIP, frozen payload, changed observer/parser, shared "
            "runtime layout and fail-closed return gates only. No server action, "
            "production compile/simulation, natural terminal, formal-D, E3/E4/E5 claim.",
    }
    paths["output"].write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "output": str(paths["output"]),
        "sha256": sha(paths["output"]),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS":
            result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
        "errors": errors,
    }, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
