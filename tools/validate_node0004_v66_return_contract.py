from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


PACKAGE = "r5_n4_hw_v66_epoch_owner_diag"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--family-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    family = json.loads(args.family_report.read_text(encoding="utf-8"))
    with zipfile.ZipFile(args.zip) as archive:
        runtime = archive.read(
            f"{PACKAGE}/package_tools/"
            "node0004_hang_localization_runtime.py"
        ).decode("utf-8")
        runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode("utf-8")
        manifest = json.loads(
            archive.read(f"{PACKAGE}/package_manifest.json").decode("utf-8")
        )

    required_runtime = (
        "SERVER_RESULT_GATE.json",
        "formal_readback_claimed",
        "natural_terminal_observed",
        "compile_exit_status",
        "run_exit_status",
        "signal_status",
        "RETURN_MANIFEST.json",
    )
    controls = family.get("controls", {})
    checks = {
        "family_runner_control_valid": family.get("valid") is True,
        "result_conjunction_fields": all(
            token in runtime for token in required_runtime
        ),
        "collector_allowlist_bound": (
            "SERVER_RESULT_GATE.json" in json.dumps(manifest)
            and "RETURN_MANIFEST.json" in runtime
        ),
        "normal_compile_run_finalized": (
            controls.get("normal", {}).get("runner_exit") == 0
            and controls.get("normal", {}).get("compile_started") is True
            and controls.get("normal", {}).get("simulation_started") is True
            and controls.get("normal", {}).get("finalizer_reached") is True
        ),
        "failure_and_signal_finalizers": all(
            controls.get(name, {}).get("finalizer_reached") is True
            and controls.get(name, {}).get("fixed_result_return_published")
            is True
            for name in ("preflight_fail", "compile_fail", "HUP", "INT", "TERM")
        ),
        "runner_unique_return_binding": (
            "--return-zip \"$return_zip\"" in runner
            and "${install_name}_${return_tag}_return.zip" in runner
        ),
    }
    errors = [key for key, value in checks.items() if not value]
    report = {
        "schema": "node0004-v66-return-result-contract-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "zip_sha256": hashlib.sha256(args.zip.read_bytes()).hexdigest(),
        "claim_boundary": (
            "Local collector/result-conjunction and normal/failure/signal "
            "finalizer controls only; no DUT natural terminal, formal 320D, "
            "E4, or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"valid": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
