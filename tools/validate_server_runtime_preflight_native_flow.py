#!/usr/bin/env python3
"""Aggregate final-runner checks for prelaunch server-environment overreach.

The validator is intentionally lexical and cheap.  It scans only the portion
of the exact runner before the unique production-launch marker.  Post-launch
return collection may inspect outputs; prelaunch code may not probe whether
server-owned files, tools, libraries, RTL or module providers exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPORT_SCHEMA = "server-runtime-preflight-native-flow-validation-v1"


FORBIDDEN: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "shell_file_type_or_readability_test",
        re.compile(r"(?:^|[;&|]\s*)(?:test|\[\[?|/usr/bin/test)\s+!?\s*-[efdLrxs]\b"),
    ),
    (
        "stat_find_readlink_realpath_inventory",
        re.compile(r"(?:^|[;&|]\s*)(?:stat|find|readlink|realpath)\b"),
    ),
    (
        "hash_or_tree_identity_of_server_owned_content",
        re.compile(r"(?:^|[;&|]\s*)(?:sha(?:1|224|256|384|512)sum|md5sum|cksum)\b"),
    ),
    (
        "git_server_source_identity",
        re.compile(r"(?:^|[;&|]\s*)git\b[^\n]*(?:rev-parse|status|diff|ls-files|show)\b"),
    ),
    (
        "command_v_or_which_tool_availability",
        re.compile(r"(?:\bcommand\s+-v\b|(?:^|[;&|]\s*)which\s+\S+)"),
    ),
    (
        "make_dry_run_or_just_print",
        re.compile(r"\b(?:make|gmake)\b[^\n]*(?:--just-print|--dry-run|--recon|(?:^|\s)-n(?:\s|$))"),
    ),
    (
        "module_or_provider_lookup_probe",
        re.compile(r"(?:server_compile_environment_gate|module[_ -]?lookup[_ -]?probe|provider[_ -]?probe)", re.I),
    ),
    (
        "separate_runtime_preflight_or_attestation_subcommand",
        re.compile(r"\b(?:python(?:3)?|bash|sh)\b[^\n]*(?:\bpreflight\b|\battest(?:ation)?\b)", re.I),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(runner: Path, dispatch: dict[str, Any]) -> dict[str, Any]:
    marker = dispatch.get("production_launch_marker")
    errors: list[str] = []
    if not isinstance(marker, str) or not marker:
        marker = "# CODEX_PRODUCTION_LAUNCH"
        errors.append("dispatch production_launch_marker is absent or invalid")

    text = runner.read_text(encoding="utf-8", errors="strict")
    lines = text.splitlines()
    marker_lines = [idx for idx, line in enumerate(lines) if line.strip() == marker]
    if len(marker_lines) != 1:
        errors.append(f"production launch marker must occur exactly once, found {len(marker_lines)}")
        boundary = len(lines)
    else:
        boundary = marker_lines[0]

    findings: list[dict[str, Any]] = []
    for idx, line in enumerate(lines[:boundary], start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for mechanism, pattern in FORBIDDEN:
            if pattern.search(line):
                findings.append({"line": idx, "mechanism": mechanism, "text": stripped})

    if findings:
        errors.append(
            f"{len(findings)} forbidden prelaunch server-environment check(s) found"
        )

    policy = dispatch.get("policy", {})
    if policy.get("server_environment_adjudicator") != "ACTUAL_PRODUCTION_COMMAND_ONLY":
        errors.append("dispatch does not bind actual production command as the sole environment adjudicator")

    retired = set(dispatch.get("retired_from_current_blocking", []))
    required_retired = {
        "CDA-SERVER-COMPILE-MODULE-PROVIDER-CLOSURE-001",
        "compile_environment_attestation",
    }
    if not required_retired.issubset(retired):
        errors.append("dispatch does not retire the legacy provider prelaunch gate")

    native = dispatch.get("native_failure_differential", {})
    refs = native.get("required_reference_paths")
    fields = native.get("required_attempt_fields")
    if not isinstance(refs, list) or not refs:
        errors.append("native failure differential has no reference paths")
        refs = []
    if not isinstance(fields, list) or not fields:
        errors.append("native failure differential has no required attempt fields")
        fields = []

    return {
        "schema": REPORT_SCHEMA,
        "pass": not errors,
        "runner_path": runner.as_posix(),
        "runner_sha256": sha256_file(runner),
        "production_launch_marker": marker,
        "production_launch_marker_count": len(marker_lines),
        "prelaunch_line_count": boundary,
        "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY",
        "forbidden_prelaunch_findings": findings,
        "all_findings_collected": True,
        "native_failure_differential": {
            "timing": native.get("timing"),
            "unknown_semantics": native.get("unknown_semantics"),
            "reference_paths": refs,
            "required_attempt_fields": fields,
        },
        "errors": errors,
        "claim_boundary": dispatch.get("claim_boundary", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument(
        "--dispatch",
        type=Path,
        default=Path("contracts/server_runtime_preflight_native_flow_dispatch_v1.json"),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = validate(args.runner, load_json(args.dispatch))
    write_json(args.output, report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
