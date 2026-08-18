#!/usr/bin/env python3
"""Route the current first-fresh audit to serialized v101."""

import json
import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/audit_node0004_v100b_lcdup_guardv2_first_fresh.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v100b_lcdup_guardv2", "r5_n4_hw_v101b_lcdup_guardprocfix")
    source = source.replace("validate_node0004_v100b_lcdup_guardv2_hdl.py", "validate_node0004_v101b_lcdup_guardprocfix_hdl.py")
    source = source.replace("node0004-v100-firstfresh-", "node0004-v101-firstfresh-")
    namespace = {"__name__": "node0004_v101_first_fresh_routed", "__file__": str(ROOT / "tools/audit_node0004_v100b_lcdup_guardv2_first_fresh.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    result = int(namespace["main"]())
    output = Path(sys.argv[sys.argv.index("--output-dir") + 1]).resolve()
    package_zip = Path(sys.argv[sys.argv.index("--zip") + 1]).resolve()
    python_exe = Path(sys.argv[sys.argv.index("--python") + 1]).resolve()
    runner_receipt = output / "reports/runner_resilience_exact_zip.json"
    runner_call = subprocess.run(
        [
            str(python_exe), str(ROOT / "tools/validate_server_runner_return_resilience.py"),
            "validate-final-zip", "--zip", str(package_zip),
            "--contract-member", "r5_n4_hw_v101b_lcdup_guardprocfix/contracts/server_runner_return_resilience.json",
            "--output", str(runner_receipt),
        ],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    runner_value = json.loads(runner_receipt.read_text(encoding="utf-8")) if runner_receipt.is_file() else {"pass": False}
    actual_path = output / "reports/actual_runner_entry_and_input_open.json"
    actual = json.loads(actual_path.read_text(encoding="utf-8"))
    runner_pass = runner_call.returncode == 0 and runner_value.get("pass") is True
    actual["checks"]["runner_resilience_exact_zip"] = runner_pass
    actual["errors"] = [item for item in actual.get("errors", []) if item != "runner_resilience_exact_zip"]
    if not runner_pass:
        actual["errors"].append("runner_resilience_exact_zip")
    actual["pass"] = all(actual["checks"].values()) and not actual["errors"]
    actual["runner_resilience_receipt"] = {
        "path": runner_receipt.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(runner_receipt.read_bytes()).hexdigest() if runner_receipt.is_file() else None,
    }
    actual_path.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    contract_path = output / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["rule_change"]["epoch_id"] = "observer-operational-guard-live-tree-v2-self-enumerator-fix-local"
    matrix_path = output / "reports/candidate_discrimination_matrix.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    contract["candidate_discrimination"]["pairwise_distinguishable"] = bool(
        matrix.get("checks", {}).get("signatures_pairwise_distinguishable") is True
    )
    for item in contract["evidence_reports"]:
        if item["gate_id"] == "actual_runner_entry_and_input_open":
            item["sha256"] = hashlib.sha256(actual_path.read_bytes()).hexdigest()
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_paths = [output / item["path"].split("first_fresh_extra_audit/", 1)[-1] for item in contract["evidence_reports"]]
    local_pass = all(json.loads(path.read_text(encoding="utf-8")).get("pass") is True for path in report_paths)
    return 0 if local_pass and contract["candidate_discrimination"]["pairwise_distinguishable"] else result


if __name__ == "__main__":
    raise SystemExit(main())
