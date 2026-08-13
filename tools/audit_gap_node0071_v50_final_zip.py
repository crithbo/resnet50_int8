#!/usr/bin/env python3
"""Independent exact-final-ZIP audit for GAP node0071 v50."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v50_ga_ob_conjunction_diag"
RULES = {
    ".agents/agent.md":
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ".agents/rules/生成前必读索引.md":
        "bded239d169c4768ca0c54e93a90eeb0a9285955252995afaf098322a00bd688",
    ".agents/rules/服务器测试包生成规则.md":
        "a8f628413367805d5fe9822233b39460e5386b1ecaf321ba050546a96cd843d8",
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip-a", type=Path, required=True)
    ap.add_argument("--zip-b", type=Path, required=True)
    ap.add_argument("--sidecar", type=Path, required=True)
    ap.add_argument("--family-report", type=Path, required=True)
    ap.add_argument("--shared-report", type=Path, required=True)
    ap.add_argument("--runner-harness", type=Path, required=True)
    ap.add_argument("--shared-harness", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    paths = {k: v.resolve() for k, v in vars(args).items() if isinstance(v, Path)}
    errors: list[str] = []
    za, zb = paths["zip_a"], paths["zip_b"]
    zsha = sha(za)
    family = load(paths["family_report"])
    shared = load(paths["shared_report"])
    runner = load(paths["runner_harness"])
    harness = load(paths["shared_harness"])

    receipts = {}
    for rel, expected in RULES.items():
        path = ROOT / rel
        actual = sha(path)
        receipts[rel] = {
            "bytes": path.stat().st_size,
            "sha256": actual,
            "expected_sha256": expected,
            "current_match": actual == expected,
        }
        if actual != expected:
            errors.append(f"rule_drift:{rel}")
    plan = ROOT / ".agents/plan.md"
    receipts[".agents/plan.md"] = {
        "bytes": plan.stat().st_size,
        "sha256": sha(plan),
        "mutable_provenance_only": True,
    }

    with zipfile.ZipFile(za) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        roots = {PurePosixPath(n).parts[0] for n in names if n}
        manifest = json.loads(archive.read(f"{NAME}/TEST_PACKAGE_MANIFEST.json"))
        expected_files = {
            f"{NAME}/{rel}": (row["size_bytes"], row["sha256"])
            for rel, row in manifest["files"].items()
        }
        actual_files = {
            i.filename: (i.file_size, hashlib.sha256(archive.read(i)).hexdigest())
            for i in infos
            if not i.is_dir()
            and i.filename != f"{NAME}/TEST_PACKAGE_MANIFEST.json"
        }
    sidecar_expected = f"{zsha}  {za.name}"
    zip_checks = {
        "double_build_byte_equal": za.read_bytes() == zb.read_bytes(),
        "crc": zipfile.ZipFile(za).testzip() is None,
        "single_root": roots == {NAME},
        "path_safe": all(
            not PurePosixPath(n).is_absolute()
            and ".." not in PurePosixPath(n).parts
            and "\\" not in n for n in names
        ),
        "duplicate_free": len(names) == len(set(names)),
        "symlink_free": all(
            ((i.external_attr >> 16) & 0o170000) != 0o120000 for i in infos
        ),
        "manifest_exact_set_and_receipts": actual_files == expected_files,
        "identity": manifest.get("install_name") == NAME,
        "sidecar": paths["sidecar"].read_text(encoding="ascii").strip()
        == sidecar_expected,
        "manifest_current_server_rule":
            manifest["rule_receipts"]["server_package_rule_sha256"]
            == RULES[".agents/rules/服务器测试包生成规则.md"],
        "manifest_current_index":
            manifest["rule_receipts"]["generation_index_sha256"]
            == RULES[".agents/rules/生成前必读索引.md"],
    }
    errors.extend(f"zip:{k}" for k, ok in zip_checks.items() if not ok)

    scenarios = runner.get("scenarios", {})
    required = {
        "normal": 0, "preflight_fail": 5, "compile_fail": 73,
        "HUP": 129, "INT": 130, "TERM": 143,
    }
    scenario_ok = all(
        scenarios.get(name, {}).get("runner_exit") == code
        and scenarios[name].get("finalizer_reached") is True
        and scenarios[name].get("fixed_result_return_published") is True
        and scenarios[name].get("root_exact_set_unchanged") is True
        and scenarios[name].get("sidecar_valid") is True
        for name, code in required.items()
    )
    report_checks = {
        "family_valid": family.get("valid") is True and family.get("errors") == [],
        "family_binds_zip": family.get("target_zip_sha256") == zsha,
        "shared_pass": shared.get("pass") is True and shared.get("errors") == [],
        "shared_binds_zip": shared.get("zip", {}).get("sha256") == zsha,
        "runner_valid": runner.get("valid") is True and runner.get("errors") == [],
        "shared_harness_binds_zip": harness.get("derived_from_zip_sha256") == zsha,
        "six_control_flows": scenario_ok,
        "fixed_simresult":
            harness.get("fixed_result_root") == "/home/panqs/ndp/simresult",
    }
    errors.extend(f"report:{k}" for k, ok in report_checks.items() if not ok)

    matrix = {
        "package_bootstrap_path_runtime_D": {
            "applicability": "blocking_applicable",
            "pass": report_checks["shared_pass"] and report_checks["six_control_flows"],
        },
        "runner_compile_finalizer": {
            "applicability": "blocking_applicable",
            "pass": shared["checks"]["runner_early_exit_visibility"]
            and report_checks["six_control_flows"],
        },
        "package_local_hdl": {
            "applicability": "blocking_applicable",
            "pass": family["hdl_scope"]["checks"]["positive_exit_zero"]
            and family["hdl_scope"]["checks"]["delete_declaration_exit_nonzero"]
            and family["hdl_scope"]["checks"]["typo_use_exit_nonzero"]
            and all(family["public_surface_proof"].values()),
        },
        "materialized_config": {
            "applicability": "not_applicable_receipt_reuse",
            "pass": family["freeze_checks"]["numeric_byte_equal"]
            and family["freeze_checks"]["numeric_file_count"]
            and family["freeze_checks"]["sca_identity_only"]
            and family["freeze_checks"]["timeout_unchanged"],
        },
        "diagnostic_semantics": {
            "applicability": "blocking_applicable",
            "pass": all(family["observer_semantics"].values())
            and family["predicate_trace"]["all_checks_true"]
            and all(family["negative_semantics"].values()),
        },
        "return_result_conjunction": {
            "applicability": "blocking_applicable",
            "pass": len(manifest["readback_checks"]) == 48
            and shared["checks"]["contract_shape"]
            and report_checks["six_control_flows"],
        },
        "report_style": {
            "applicability": "record_only",
            "pass": True,
        },
    }
    blocking = [
        k for k, row in matrix.items()
        if row["applicability"] == "blocking_applicable" and row["pass"] is not True
    ]
    errors.extend(f"release_gate:{k}" for k in blocking)

    result = {
        "schema": "gap-node0071-v50-final-zip-rule-self-audit-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "evidence_ceiling": "E2_LOCAL_ONLY",
        "target_zip": str(za.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": za.stat().st_size,
        "target_zip_sha256": zsha,
        "target_sidecar": str(paths["sidecar"].relative_to(ROOT)).replace("\\", "/"),
        "target_sidecar_bytes": paths["sidecar"].stat().st_size,
        "target_sidecar_sha256": sha(paths["sidecar"]),
        "zip_checks": zip_checks,
        "report_checks": report_checks,
        "rule_receipts": receipts,
        "release_gate_matrix": matrix,
        "blocking_failures": blocking,
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
            "Exact final ZIP and local safe stubs only; no production compile, "
            "simulation, natural terminal, formal D, E3, E4 or E5 claim.",
    }
    paths["output"].parent.mkdir(parents=True, exist_ok=True)
    paths["output"].write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(paths["output"]),
        "sha256": sha(paths["output"]),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
    }, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
