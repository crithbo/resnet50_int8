#!/usr/bin/env python3
"""Independent current-rule audit of the exact GAP v51 final ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v51_ga_ob_mode_factor_diag"
RULES = {
    ".agents/agent.md":
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ".agents/rules/生成前必读索引.md":
        "d4ff32f162538574a0dd48402e299fa25a11fb95074352c19fcfb007ebb77603",
    ".agents/rules/服务器测试包生成规则.md":
        "7cf2cb4511cba04cb8a14d06473d67061deae64f602988d27053d8289c964b13",
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
    ap.add_argument("--runner-report", type=Path, required=True)
    ap.add_argument("--shared-harness", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ns = ap.parse_args()
    za, zb = ns.zip_a.resolve(), ns.zip_b.resolve()
    family, shared = load(ns.family_report), load(ns.shared_report)
    runner, harness = load(ns.runner_report), load(ns.shared_harness)
    errors: list[str] = []
    receipts = {}
    for relative, expected in RULES.items():
        path = ROOT / relative
        actual = sha(path)
        receipts[relative] = {
            "bytes": path.stat().st_size,
            "sha256": actual,
            "expected_sha256": expected,
            "current_match": actual == expected,
        }
        if actual != expected:
            errors.append(f"rule_drift:{relative}")
    plan = ROOT / ".agents/plan.md"
    receipts[".agents/plan.md"] = {
        "bytes": plan.stat().st_size,
        "sha256": sha(plan),
        "mutable_provenance_only": True,
    }
    zsha = sha(za)
    with zipfile.ZipFile(za) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        manifest = json.loads(
            archive.read(f"{NAME}/TEST_PACKAGE_MANIFEST.json")
        )
        expected = {
            f"{NAME}/{relative}": (row["size_bytes"], row["sha256"])
            for relative, row in manifest["files"].items()
        }
        actual = {
            info.filename: (
                info.file_size,
                hashlib.sha256(archive.read(info)).hexdigest(),
            )
            for info in infos
            if not info.is_dir()
            and info.filename != f"{NAME}/TEST_PACKAGE_MANIFEST.json"
        }
        crc = archive.testzip() is None
    zip_checks = {
        "double_build_byte_equal": za.read_bytes() == zb.read_bytes(),
        "crc": crc,
        "single_root": roots == {NAME},
        "path_safe": all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
            for name in names
        ),
        "duplicate_free": len(names) == len(set(names)),
        "symlink_free": all(
            ((info.external_attr >> 16) & 0o170000) != 0o120000
            for info in infos
        ),
        "manifest_exact_set": actual == expected,
        "sidecar": ns.sidecar.read_text(encoding="ascii").split()
            == [zsha, za.name],
        "identity": manifest.get("install_name") == NAME,
        "current_rule_receipts":
            manifest["rule_receipts"]["server_package_rule_sha256"]
            == RULES[".agents/rules/服务器测试包生成规则.md"]
            and manifest["rule_receipts"]["generation_index_sha256"]
            == RULES[".agents/rules/生成前必读索引.md"],
    }
    errors.extend(f"zip:{name}" for name, ok in zip_checks.items() if not ok)
    scenarios = runner.get("scenarios", {})
    expected_exits = {
        "normal": 0, "preflight_fail": 5, "compile_fail": 73,
        "HUP": 129, "INT": 130, "TERM": 143,
    }
    six_flows = all(
        scenarios.get(name, {}).get("runner_exit") == code
        and scenarios[name].get("finalizer_reached") is True
        and scenarios[name].get("fixed_result_return_published") is True
        and scenarios[name].get("sidecar_valid") is True
        and scenarios[name].get("root_exact_set_unchanged") is True
        for name, code in expected_exits.items()
    )
    report_checks = {
        "family": family.get("valid") is True and family.get("errors") == [],
        "family_zip": family.get("target_zip_sha256") == zsha,
        "shared": shared.get("pass") is True and shared.get("errors") == [],
        "shared_zip": shared.get("zip", {}).get("sha256") == zsha,
        "runner": runner.get("valid") is True and runner.get("errors") == [],
        "harness_zip": harness.get("derived_from_zip_sha256") == zsha,
        "six_control_flows": six_flows,
        "fixed_simresult":
            harness.get("fixed_result_root") == "/home/panqs/ndp/simresult",
        "parser_path_positive":
            runner["checks"]["normal_all_decision_parsers_exit_zero"]
            and runner["checks"]["normal_decision_parser_stderr_empty"],
    }
    errors.extend(
        f"report:{name}" for name, ok in report_checks.items() if not ok
    )
    hdl_checks = family["hdl_scope"]["checks"]
    xmr = family["xmr_proof"]
    predicate = family["predicate_trace"]
    negative_controls = {
        "preflight_fail": scenarios["preflight_fail"]["runner_exit"] == 5,
        "compile_fail": scenarios["compile_fail"]["runner_exit"] == 73,
        "HUP": scenarios["HUP"]["runner_exit"] == 129,
        "INT": scenarios["INT"]["runner_exit"] == 130,
        "TERM": scenarios["TERM"]["runner_exit"] == 143,
        "hdl_delete_declaration":
            hdl_checks["delete_declaration_exit_nonzero"],
        "hdl_typo_use": hdl_checks["typo_use_exit_nonzero"],
        "xmr_leaf_rename": xmr["leaf_rename_negative_fail_closed"],
        "xmr_wrong_sibling": xmr["wrong_sibling_negative_fail_closed"],
        "stable_level_not_progress":
            predicate["payload"]["checks"]["stable_level_not_progress"],
        "normal_mode_blocked_boundary":
            predicate["payload"]["checks"]["normal_bp_boundary"],
    }
    errors.extend(
        f"negative:{name}"
        for name, ok in negative_controls.items() if not ok
    )
    matrix = {
        "package_bootstrap_path_runtime_D": {
            "applicability": "blocking_applicable",
            "pass": report_checks["shared"] and six_flows,
        },
        "runner_compile_finalizer": {
            "applicability": "blocking_applicable",
            "pass": report_checks["parser_path_positive"] and six_flows,
        },
        "package_local_hdl": {
            "applicability": "blocking_applicable",
            "pass": hdl_checks["positive_exit_zero"]
                and xmr["all_actual_leaves_bound"],
        },
        "materialized_config": {
            "applicability": "not_applicable_receipt_reuse",
            "pass": family["freeze_checks"][
                "numeric_workload_config_golden_byte_equal"
            ] and family["freeze_checks"]["timeout_unchanged"],
        },
        "diagnostic_semantics": {
            "applicability": "blocking_applicable",
            "pass": predicate["all_checks_true"]
                and all(family["observer_semantics"].values()),
        },
        "return_result_conjunction": {
            "applicability": "blocking_applicable",
            "pass": len(manifest["readback_checks"]) == 48
                and report_checks["shared"],
        },
        "repeat_execution_unique_return": {
            "applicability": "blocking_applicable",
            "pass": manifest["repeat_execution_contract"][
                "return_name_policy"
            ] == "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS"
                and six_flows,
        },
        "report_style": {
            "applicability": "record_only",
            "pass": True,
        },
    }
    blocking = [
        name for name, row in matrix.items()
        if row["applicability"] == "blocking_applicable"
        and row["pass"] is not True
    ]
    errors.extend(f"release_gate:{name}" for name in blocking)
    result = {
        "schema": "gap-node0071-v51-final-zip-rule-self-audit-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "evidence_ceiling": "E2_LOCAL_ONLY",
        "target_zip": str(za.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": za.stat().st_size,
        "target_zip_sha256": zsha,
        "target_sidecar": str(ns.sidecar.resolve().relative_to(ROOT)).replace(
            "\\", "/"
        ),
        "target_sidecar_bytes": ns.sidecar.stat().st_size,
        "target_sidecar_sha256": sha(ns.sidecar),
        "zip_checks": zip_checks,
        "report_checks": report_checks,
        "negative_controls": negative_controls,
        "rule_receipts": receipts,
        "release_gate_matrix": matrix,
        "blocking_failures": blocking,
        "errors": errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "package_release": "PACKAGE_READY_NOT_RUN" if not errors else "NONE",
        "server_command":
            f"bash {NAME}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_return_template":
            f"/home/panqs/ndp/simresult/{NAME}_r<epoch-ns>_<pid>_return.zip",
        "claim_boundary": (
            "Exact final ZIP and isolated safe controls only; no server/DUT "
            "run, natural terminal, formal D, E3, E4, or E5 claim."
        ),
    }
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "output": str(ns.output),
        "sha256": sha(ns.output),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
    }))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
