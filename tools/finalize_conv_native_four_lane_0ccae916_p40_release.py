#!/usr/bin/env python3
"""Finalize exact-ZIP evidence for p40 without server action."""

import json
from pathlib import Path

import finalize_conv_native_four_lane_0ccae916_p39_release as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p40_dhpubfix"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p40_dhpubfix"
BUILD = BASE / "build"


def main() -> int:
    prior.PACKAGE = PACKAGE
    prior.BASE = BASE
    prior.BUILD = BUILD
    prior.ZIP = BUILD / f"{PACKAGE}.zip"
    prior.OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"
    prior.FILES = {
        "build": BUILD / f"{PACKAGE}.build.json",
        "profile": BASE / "server_package_build_profile_v2.json",
        "runner_resilience": BUILD / f"{PACKAGE}.runner_return_resilience.json",
        "source_bound": BUILD / f"{PACKAGE}.source_bound_final_zip.json",
        "post_sim": BUILD / f"{PACKAGE}.post_sim.json",
        "compile_core_waveform": BUILD / f"{PACKAGE}.compile_core_harness.json",
        "six_state_runner": BUILD / f"{PACKAGE}.runner_harness.json",
        "runtime_layout": BUILD / f"{PACKAGE}.shared_layout.json",
        "observer_public_surface": BUILD / f"{PACKAGE}.observer_public_surface.json",
        "first_fresh": BASE / "first_fresh_audit/first_fresh_validation.json",
        "first_fresh_contract": BASE / "first_fresh_audit/contract.json",
    }
    status = prior.main()
    output = prior.OUTPUT
    value = json.loads(output.read_text(encoding="utf-8"))
    public = json.loads(prior.FILES["observer_public_surface"].read_text(encoding="utf-8"))
    value["schema"] = "conv-native-four-lane-p40-dhpubfix-final-zip-audit-v1"
    value["checks"]["observer_public_surface"] = public.get("pass") is True and public.get("errors") == []
    value["checks"]["structured_first_error"] = public.get("semantic_controls", {}).get("structured_first_error_selected") is True and public.get("semantic_controls", {}).get("platform_warning_false_positive_rejected") is True
    valid = all(value["checks"].values())
    value["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = valid
    value["valid"] = valid
    value["status"] = "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD"
    value["errors"] = [name for name, passed in value["checks"].items() if not passed]
    value["claim_boundary"] = (
        "p40 is an unrun package-local observer/compile-evidence successor. It replaces the p39 private-XMR "
        "failure with module-surface observations and preserves config/numeric/workload/functional RTL. "
        "Actual production compile and all DUT/result claims remain unproven until a formal p40 return."
    )
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "status": value["status"], "output": str(output), "zip_sha256": prior.sha(prior.ZIP)}, sort_keys=True))
    return 0 if valid else (status or 1)


if __name__ == "__main__":
    raise SystemExit(main())
