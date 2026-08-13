from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


PACKAGE = "r5_n4_hw_v76_sourcebound_boundfix"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--family-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    family = json.loads(args.family_report.read_text(encoding="utf-8"))
    with zipfile.ZipFile(args.zip) as archive:
        runtime = archive.read(
            f"{PACKAGE}/package_tools/node0004_hang_localization_runtime.py"
        ).decode("utf-8")
        runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode("utf-8")
        request = json.loads(
            archive.read(
                f"{PACKAGE}/contracts/server_post_sim_return_request.json"
            ).decode("utf-8")
        )

    required_runtime = (
        "SERVER_RESULT_GATE.json",
        "formal_readback_claimed",
        "natural_terminal_observed",
        "compile_exit_status",
        "run_exit_status",
        "signal_status",
    )
    controls = family.get("controls", {})
    checks = {
        "family_runner_control_valid": family.get("valid") is True,
        "result_conjunction_fields": all(token in runtime for token in required_runtime),
        "post_sim_request_identity": (
            request.get("package_id") == PACKAGE
            and request.get("return_basename_template")
            == "{package_id}_{execution_id}_return.zip"
            and request.get("result_root") == "/home/panqs/ndp/simresult"
        ),
        "required_source_bound_plugin": any(
            item.get("plugin_id") == "node0004_source_bound_collect"
            and item.get("required_for_adjudication") is True
            for item in request.get("plugins", [])
        ),
        "runner_invokes_post_sim_core": (
            'server_post_sim_return.py" finalize --request' in runner
            and "RUNNER_FINAL_STATUS" in runner
        ),
        "normal_compile_run_finalized": (
            controls.get("normal", {}).get("runner_exit") == 0
            and controls.get("normal", {}).get("compile_started") is True
            and controls.get("normal", {}).get("simulation_started") is True
            and controls.get("normal", {}).get("finalizer_reached") is True
            and controls.get("normal", {}).get("fixed_result_return_published") is True
        ),
        "failure_and_signal_finalizers": all(
            controls.get(name, {}).get("finalizer_reached") is True
            and controls.get(name, {}).get("fixed_result_return_published") is True
            for name in ("preflight_fail", "compile_fail", "HUP", "INT", "TERM")
        ),
    }
    errors = [name for name, value in checks.items() if not value]
    report = {
        "schema": "node0004-v76-post-sim-return-result-contract-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "zip_sha256": hashlib.sha256(args.zip.read_bytes()).hexdigest(),
        "claim_boundary": (
            "Local post-sim core/result-conjunction and normal/failure/signal finalizer "
            "controls only; no DUT natural terminal, formal 320D, E4, or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"valid": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
