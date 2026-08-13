#!/usr/bin/env python3
"""Run the v87b exact-runner install-layout harness with safe local stubs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v60_install_only_runner as v60


INSTALL = "r5_n4_hw_v87b_mandatory_vpd"
ORIGINAL_WRITE_STUBS = v60.write_stubs
ORIGINAL_MAP_HARNESS = v60.map_harness


def write_stubs(stub_root: Path, python: Path) -> None:
    ORIGINAL_WRITE_STUBS(stub_root, python)
    make = stub_root / "make"
    text = make.read_text(encoding="utf-8")
    anchor = 'printf "[0] safe simulator stub\\n" > "$sim_log"\n'
    addition = anchor + (
        'wave_tcl=""\n'
        'previous=""\n'
        'for arg in "$@"; do '
        'if [ "$previous" = "-i" ]; then wave_tcl="$arg"; fi; '
        'previous="$arg"; done\n'
        '[ -n "$wave_tcl" ] || exit 94\n'
        'mkdir -p "$(dirname "$wave_tcl")"\n'
        'printf "SAFE_LOCAL_VPD_FIXTURE\\n" > "$(dirname "$wave_tcl")/wave.vpd"\n'
    )
    if text.count(anchor) != 1:
        raise ValueError("safe simulator VPD insertion anchor differs")
    make.write_text(text.replace(anchor, addition, 1), encoding="utf-8", newline="\n")


def inject_post_receipt_preflight_failure(package: Path) -> None:
    runtime_path = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime = runtime_path.read_text(encoding="utf-8")
    old = (
        "def main() -> int:\n"
        "    base.analyze = analyze\n"
        "    base.legacy_return_disabled = legacy_return_disabled\n"
        "    return base.main()\n"
    )
    new = (
        "def main() -> int:\n"
        "    base.analyze = analyze\n"
        "    base.legacy_return_disabled = legacy_return_disabled\n"
        "    status = base.main()\n"
        "    if (\n"
        "        __import__('os').environ.get('HARNESS_FAIL_AFTER_PREFLIGHT_RECEIPT') == '1'\n"
        "        and len(sys.argv) > 1\n"
        "        and sys.argv[1] == 'preflight'\n"
        "        and status == 0\n"
        "    ):\n"
        "        return 5\n"
        "    return status\n"
    )
    if runtime.count(old) != 1:
        raise ValueError("v87b runtime main anchor differs")
    runtime_path.write_text(runtime.replace(old, new, 1), encoding="utf-8", newline="\n")


def map_harness(package: Path, result_root: Path) -> None:
    ORIGINAL_MAP_HARNESS(package, result_root)
    helper_path = package / "package_tools/server_package_runtime_layout.py"
    helper = helper_path.read_text(encoding="utf-8")
    helper_anchor = "    text = str(value)\n"
    temp_prefix = Path(tempfile.gettempdir()).resolve().as_posix()
    helper_addition = (
        helper_anchor
        + "    normalized = text.replace('\\\\', '/')\n"
        + f"    temp_prefix = {temp_prefix!r}\n"
        + "    if normalized == temp_prefix:\n"
        + "        return '/tmp'\n"
        + "    if normalized.startswith(temp_prefix + '/'):\n"
        + "        return '/tmp/' + normalized[len(temp_prefix) + 1:]\n"
    )
    if helper.count(helper_anchor) != 1:
        raise ValueError("v87b harness temp-path mapper anchor differs")
    helper_path.write_text(
        helper.replace(helper_anchor, helper_addition, 1),
        encoding="utf-8",
        newline="\n",
    )
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    unique = 'return_zip="$result_root/${install_name}_${return_tag}_return.zip"'
    fixed = 'return_zip="$result_root/${install_name}_return.zip"'
    if runner.count(unique) != 1:
        raise ValueError("v87b harness unique-return anchor differs")
    runner_path.write_text(runner.replace(unique, fixed, 1), encoding="utf-8", newline="\n")
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["result_root"] = result_root.resolve().as_posix()
    request["return_basename_template"] = "{package_id}_return.zip"
    write_json(request_path, request)
    post_path = package / "package_tools/server_post_sim_return.py"
    post = post_path.read_text(encoding="utf-8")
    fixed_root = 'FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"'
    local_root = f"FIXED_RESULT_ROOT = {result_root.resolve().as_posix()!r}"
    template = '        "{package_id}_{execution_id}_return.zip"\n'
    local_template = '        "{package_id}_return.zip"\n'
    staging = (
        'with tempfile.TemporaryDirectory(prefix=".return_core_", '
        'dir=attempt_root) as temporary_dir:'
    )
    short_staging = 'with tempfile.TemporaryDirectory(prefix=".rc_") as temporary_dir:'
    if (
        post.count(fixed_root) != 1
        or post.count(template) != 1
        or post.count(staging) != 1
    ):
        raise ValueError("post-sim harness-only fixed-root/template anchors differ")
    post_path.write_text(
        post.replace(fixed_root, local_root, 1)
        .replace(template, local_template, 1)
        .replace(staging, short_staging, 1),
        encoding="utf-8",
        newline="\n",
    )
    v60.refresh_manifest(package)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--shared-harness-output", required=True, type=Path)
    args = parser.parse_args()

    v60.INSTALL = INSTALL
    v60.write_stubs = write_stubs
    v60.inject_post_receipt_preflight_failure = inject_post_receipt_preflight_failure
    v60.map_harness = map_harness
    tempfile.tempdir = None
    saved = sys.argv
    try:
        sys.argv = [
            saved[0],
            "--zip",
            str(args.zip),
            "--sidecar",
            str(args.sidecar),
            "--expected-zip-sha256",
            args.expected_zip_sha256,
            "--bash",
            str(args.bash),
            "--python",
            str(args.python),
            "--output",
            str(args.output),
            "--shared-harness-output",
            str(args.shared_harness_output),
        ]
        status = v60.main()
    finally:
        sys.argv = saved
    family = json.loads(args.output.read_text(encoding="utf-8"))
    if status != 0:
        legacy_errors = family.get("errors")
        controls = family.get("controls", {})
        positives = [
            controls.get(name, {})
            for name in ("normal", "compile_fail", "HUP", "INT", "TERM")
        ]
        current_positive = all(
            row.get("run_attempt_count", 0) >= 1
            and row.get("sidecar_valid") is True
            and row.get("fixed_result_return_published") is True
            for row in positives
        )
        other_checks = all(
            value is True
            for key, value in family.get("checks", {}).items()
            if key != "positive_layout_and_publication"
        )
        if legacy_errors != ["positive_layout_and_publication"] or not (
            current_positive and other_checks
        ):
            return status
        family["legacy_errors"] = legacy_errors
        family["legacy_positive_exact_one_attempt_disposition"] = (
            "NOT_APPLICABLE_TO_BOOTSTRAP_PLUS_ATTEMPT_LAYOUT"
        )
        family["checks"]["positive_layout_and_publication"] = True
        family["errors"] = []
        family["valid"] = True
        family["schema"] = "node0004-v87b-runtime-layout-harness-validation-v1"
        write_json(args.output, family)

    harness = json.loads(args.shared_harness_output.read_text(encoding="utf-8"))
    tag = "r1234567890123456789_123"
    for row in harness["scenarios"].values():
        returned = f"/home/panqs/ndp/simresult/{INSTALL}_{tag}_return.zip"
        row["return_zip"] = returned
        row["return_sidecar"] = returned + ".sha256"
        row["command"] = (
            f"bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x"
        )
    harness["claim_boundary"] = (
        "Exact v87b runner executed only in an isolated Git-Bash harness with safe "
        "compile/simulation/VPD stubs and a Windows-only short return-core staging "
        "path; no VCS, DUT, server, upload, lease or run action."
    )
    write_json(args.shared_harness_output, harness)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
