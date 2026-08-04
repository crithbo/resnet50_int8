from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUALIFIED = {
    "gexec_fire",
    "request_handshake",
    "read_data_handshake",
    "write_data_handshake",
    "mse4_request_handshake_ch0",
    "mse4_request_handshake_ch1",
    "mse4_write_data_handshake_ch0",
    "mse4_write_data_handshake_ch1",
}
RETURN_TARGETS = {
    "evidence/canonical_decision.json",
    "evidence/canonical_decision_self_test.json",
}


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_zip(path: Path) -> tuple[str, dict[str, bytes]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValidationError("ZIP CRC differs")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in files
                or (mode and stat.S_ISLNK(mode))
            ):
                raise ValidationError(f"unsafe member: {info.filename}")
            if not info.is_dir():
                files[info.filename] = archive.read(info)
                roots.add(pure.parts[0])
    if len(roots) != 1:
        raise ValidationError("ZIP root differs")
    return next(iter(roots)), files


def validate(path: Path) -> dict[str, Any]:
    root, files = read_zip(path)
    prefix = f"{root}/"
    manifest = json.loads(
        files[prefix + "TEST_PACKAGE_MANIFEST.json"].decode("utf-8")
    )
    contract = json.loads(
        files[prefix + "diagnostics/progress_contract.json"].decode("utf-8")
    )
    runner = files[prefix + "PREPARE_AND_RUN.sh"].decode("utf-8")
    tool_member = (
        prefix
        + "package_tools/gap_node0071_canonical_decision.py"
    )
    tool_payload = files.get(tool_member)
    tool_matches = [
        name
        for name in files
        if name.endswith("/gap_node0071_canonical_decision.py")
    ]
    records = manifest.get("files", {})
    tool_record = records.get(
        "package_tools/gap_node0071_canonical_decision.py", {}
    )
    source_pass = (
        len(tool_matches) == 1
        and tool_payload is not None
        and len(tool_payload) == tool_record.get("size_bytes")
        and sha256_bytes(tool_payload) == tool_record.get("sha256")
    )
    monotonic = set(contract.get("monotonic_counters", []))
    qualified_pass = monotonic == QUALIFIED
    excluded = set(contract.get("raw_state_excluded_from_progress", []))
    excluded_pass = {
        "ready",
        "enable",
        "valid_without_handshake",
        "buffer_occupancy",
    } <= excluded
    allowlist = manifest.get("return_allowlist", [])
    targets = {
        item.get("target_path")
        for item in allowlist
        if isinstance(item, dict)
    }
    runner_terms = (
        'canonical_tool="$package_root/package_tools/'
        'gap_node0071_canonical_decision.py"',
        '"$canonical_tool" self-test',
        '"$canonical_tool" observe',
        "--observer-log",
        "--sim-log",
        "--signal",
        "--simulation-status",
        "--stall-window-cycles",
        "--heartbeat-cycles",
        "--output",
        "canonical_decision.json",
        "trap 'finalize $?' EXIT",
        "trap 'signal_name=INT",
    )
    runner_pass = all(term in runner for term in runner_terms)
    allowlist_pass = RETURN_TARGETS <= targets
    manifest_contract = manifest.get("canonical_decision_contract")
    contract_pass = (
        isinstance(manifest_contract, dict)
        and manifest_contract.get("rule_id")
        == "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001"
        and set(manifest_contract.get("qualified_counters", []))
        == QUALIFIED
    )
    default_progress = manifest.get("default_progress_diagnostics")
    default_progress_pass = (
        isinstance(default_progress, dict)
        and default_progress.get("rule_id")
        == "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001"
        and default_progress.get("enabled_by_default") is True
        and default_progress.get("read_only") is True
        and default_progress.get("rate_limited") is True
        and default_progress.get("partial_return") is True
        and default_progress.get("qualified_progress") is True
        and default_progress.get("canonical_decision") is True
        and default_progress.get("return_allowlist") is True
        and default_progress.get("changes_dut_input_or_backpressure")
        is False
    )

    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-canonical-final-zip-"
    ) as temporary:
        extracted = Path(temporary)
        with zipfile.ZipFile(path) as archive:
            archive.extractall(extracted)
        package_tool = (
            extracted
            / root
            / "package_tools/gap_node0071_canonical_decision.py"
        )
        process = subprocess.run(
            [sys.executable, str(package_tool), "self-test"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        try:
            self_test = json.loads(process.stdout)
        except json.JSONDecodeError as error:
            raise ValidationError("package self-test JSON differs") from error
        self_test_pass = (
            process.returncode == 0
            and self_test.get("status") == "PASS"
            and all(
                value.get("failed_closed", value.get("pass", False))
                for value in self_test.get(
                    "negative_controls", {}
                ).values()
            )
        )
    checks = {
        "canonical_source_unique_manifest_bound": source_pass,
        "qualified_only_monotonic_counters": qualified_pass,
        "raw_level_state_explicitly_excluded": excluded_pass,
        "runner_trap_generation_binding": runner_pass,
        "return_allowlist_binding": allowlist_pass,
        "manifest_canonical_contract": contract_pass,
        "default_progress_diagnostics_contract": default_progress_pass,
        "fresh_extract_negative_controls": self_test_pass,
    }
    if not all(checks.values()):
        raise ValidationError(
            "canonical package checks differ: "
            + ", ".join(key for key, value in checks.items() if not value)
        )
    return {
        "schema": "gap-node0071-canonical-package-validation-v1",
        "status": "CANONICAL_DECISION_RULE_VALIDATED",
        "zip": str(path.resolve()),
        "zip_sha256": sha256_bytes(path.read_bytes()),
        "checks": checks,
        "qualified_counters": sorted(QUALIFIED),
        "return_targets": sorted(RETURN_TARGETS),
        "negative_controls": self_test["negative_controls"],
        "all_negative_controls_fail_closed": True,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.zip.resolve())
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
