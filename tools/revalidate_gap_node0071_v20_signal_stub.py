from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_runner_guard_chain as common
from tools.gap_node0071_complete_server_runtime import file_records


ROOT_NAME = "r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix"
ZIP_SHA256 = (
    "a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3"
)
SIGNAL = "TERM"
EXPECTED_STATUS = 125


class RevalidationError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_mock_tools(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=False)
    bin_dir, _ = common.mock_tools(root)
    sim_started = root / "safe_sim_stub_started.txt"
    make_wrapper = bin_dir / "make"
    make_wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "run_dir=''\n"
        "for argument in \"$@\"; do\n"
        "  case \"$argument\" in RUN_DIR=*) run_dir=\"${argument#RUN_DIR=}\";; esac\n"
        "done\n"
        "[ -n \"$run_dir\" ] || exit 84\n"
        "simv=\"$run_dir/sim_results/simv\"\n"
        "cat >\"$simv\" <<'SAFE_SIM_STUB'\n"
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "sim_log=''\n"
        "observer_log=''\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -l) shift; sim_log=\"$1\";;\n"
        "    +RETURN_OBS_FILE=*) observer_log=\"${1#*=}\";;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "[ -n \"$sim_log\" ] || exit 82\n"
        "[ -n \"$observer_log\" ] || exit 83\n"
        "printf '%s\\n' '[RETURN_OBSERVER] enabled for slice 0' >\"$sim_log\"\n"
        "printf '%s\\n' \\\n"
        "  'Native NDP return observer accum_state=1 accum_limit=512 bp_factor=1 bp_factor_limit=512' \\\n"
        "  '0 | BP_PRE_FACTOR_COUNTS_V1 | flow=MSE0 q_rd=0 ob_wr=0 occupancy=0' \\\n"
        "  '0 | BP_PRE_FACTOR_STATE_V1 | flow=MSE0 factors=0' \\\n"
        "  '0 | BP_PRE_FACTOR_WITNESS_V1 | flow=MSE0 first=0 last=0' \\\n"
        "  >\"$observer_log\"\n"
        "printf 'SAFE_SIM_STUB_STARTED\\n' >\"$MOCK_SIM_STARTED\"\n"
        "trap 'exit 143' TERM INT\n"
        "while :; do sleep 1; done\n"
        "SAFE_SIM_STUB\n"
        "chmod +x \"$simv\"\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    make_wrapper.chmod(0o755)
    return bin_dir, sim_started


def run_signal_stub(
    package: Path,
    mock_server: Path,
    harness_root: Path,
    bash: Path,
) -> dict[str, Any]:
    bin_dir, sim_started = write_mock_tools(harness_root)
    stdout_path = harness_root / "runner.stdout"
    stderr_path = harness_root / "runner.stderr"
    status_path = harness_root / "runner.status"
    harness = (
        'export PATH="$1:/usr/bin:/bin:/c/Windows/System32"\n'
        'cd "$2"\n'
        'bash PREPARE_AND_RUN.sh "$3" >"$4" 2>"$5" &\n'
        'runner_pid=$!\n'
        'attempt=0\n'
        'while [ ! -f "$6" ] && [ "$attempt" -lt 400 ]; do\n'
        '  sleep 0.05\n'
        '  attempt=$((attempt + 1))\n'
        'done\n'
        'if [ ! -f "$6" ]; then\n'
        '  kill -TERM "$runner_pid" 2>/dev/null\n'
        '  wait "$runner_pid" 2>/dev/null\n'
        '  printf "124\\n" >"$7"\n'
        '  exit 0\n'
        'fi\n'
        'kill -TERM "$runner_pid"\n'
        'wait "$runner_pid"\n'
        'runner_status=$?\n'
        'printf "%s\\n" "$runner_status" >"$7"\n'
        'exit 0\n'
    )
    env = {
        **os.environ,
        "MOCK_SIM_STARTED": common.to_git_bash(sim_started),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    process = subprocess.run(
        [
            str(bash),
            "-c",
            harness,
            "gap-v20-signal-stub",
            common.to_git_bash(bin_dir),
            common.to_git_bash(package),
            common.to_git_bash(mock_server),
            common.to_git_bash(stdout_path),
            common.to_git_bash(stderr_path),
            common.to_git_bash(sim_started),
            common.to_git_bash(status_path),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )
    runner_status = (
        int(status_path.read_text(encoding="ascii").strip())
        if status_path.is_file()
        else None
    )
    stdout = (
        stdout_path.read_text(encoding="utf-8", errors="replace")
        if stdout_path.is_file()
        else ""
    )
    stderr = (
        stderr_path.read_text(encoding="utf-8", errors="replace")
        if stderr_path.is_file()
        else ""
    )
    return {
        "harness_exit_code": process.returncode,
        "harness_stdout": process.stdout,
        "harness_stderr": process.stderr,
        "runner_exit_code": runner_status,
        "runner_stdout": stdout,
        "runner_stderr": stderr,
        "runner_stdout_sha256": hashlib.sha256(
            stdout.encode("utf-8")
        ).hexdigest(),
        "runner_stderr_sha256": hashlib.sha256(
            stderr.encode("utf-8")
        ).hexdigest(),
        "safe_sim_stub_started": sim_started.is_file(),
    }


def read_return_zip(path: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        crc_bad = archive.testzip()
        if crc_bad is not None:
            raise RevalidationError(f"return CRC differs: {crc_bad}")
        root: str | None = None
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or len(pure.parts) < 2
            ):
                raise RevalidationError(
                    f"unsafe return member: {info.filename}"
                )
            if root is None:
                root = pure.parts[0]
            if pure.parts[0] != root:
                raise RevalidationError("return root differs")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in seen:
                raise RevalidationError(
                    f"duplicate return member: {relative}"
                )
            seen.add(relative)
            files[relative] = archive.read(info)
    manifest = json.loads(files["RETURN_MANIFEST.json"])
    return files, manifest


def validate_return(
    package: Path,
    mock_server: Path,
) -> dict[str, Any]:
    return_zip = mock_server / f"{ROOT_NAME}_return.zip"
    sidecar = Path(str(return_zip) + ".sha256")
    if not return_zip.is_file() or not sidecar.is_file():
        raise RevalidationError("signal finalizer return/sidecar absent")
    return_sha = sha256(return_zip)
    if sidecar.read_text(encoding="ascii") != (
        f"{return_sha}  {return_zip.name}\n"
    ):
        raise RevalidationError("signal return sidecar differs")
    files, return_manifest = read_return_zip(return_zip)
    declared = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in return_manifest["files"]
    }
    observed = {
        path: {
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for path, payload in files.items()
        if path != "RETURN_MANIFEST.json"
    }
    if observed != declared:
        raise RevalidationError("signal return exact-set/receipt differs")
    package_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    returned_package_manifest = json.loads(
        files["evidence/PACKAGE_MANIFEST.json"]
    )
    if returned_package_manifest != package_manifest:
        raise RevalidationError("returned package identity differs")
    allowlist = {
        item["target_path"]: item
        for item in package_manifest["return_allowlist"]
    }
    if not set(observed) <= set(allowlist):
        raise RevalidationError("return contains non-allowlisted target")
    expected_required_missing = sorted(
        target
        for target, item in allowlist.items()
        if item["required"] and target not in observed
    )
    if sorted(return_manifest["required_missing"]) != expected_required_missing:
        raise RevalidationError("required-missing accounting differs")
    critical = {
        "evidence/PACKAGE_MANIFEST.json",
        "evidence/installed_preflight.json",
        "evidence/compile_exit_status.txt",
        "evidence/simulation_exit_status.txt",
        "evidence/runner_exit_status.txt",
        "evidence/SERVER_RESULT_GATE.json",
        "evidence/observer_precompile.json",
        "evidence/progress_contract.json",
        "evidence/actual_simulator_argv.txt",
        "evidence/host_timing.txt",
        "evidence/signal_status.txt",
        "evidence/progress_samples.log",
        "evidence/observer_binding.txt",
        "evidence/actual_compile_argv.txt",
        "evidence/canonical_decision.json",
        "evidence/canonical_decision_self_test.json",
        "runs/return_observer.log",
        "config/sca_cfg.json",
        "config/sca_cfg_D.json",
    }
    if not critical <= set(observed):
        raise RevalidationError(
            f"critical partial return missing: {sorted(critical-set(observed))}"
        )
    signal_text = files["evidence/signal_status.txt"].decode("utf-8")
    signal_lines = dict(
        line.split("=", 1)
        for line in signal_text.splitlines()
        if "=" in line
    )
    canonical = json.loads(files["evidence/canonical_decision.json"])
    gate = json.loads(files["evidence/SERVER_RESULT_GATE.json"])
    host_timing = files["evidence/host_timing.txt"].decode("utf-8")
    final_epoch_count = host_timing.count("final_epoch_ns=")
    return {
        "return_zip": str(return_zip),
        "return_zip_size_bytes": return_zip.stat().st_size,
        "return_zip_sha256": return_sha,
        "return_sidecar_sha256": sha256(sidecar),
        "zip_crc_valid": True,
        "path_root_safe": True,
        "return_exact_set_valid": True,
        "allowlist_only": return_manifest["allowlist_only"] is True,
        "return_status": return_manifest["status"],
        "required_missing": return_manifest["required_missing"],
        "required_missing_exactly_accounted": True,
        "critical_partial_artifacts_complete": True,
        "returned_package_identity_exact": True,
        "signal_status": signal_lines,
        "single_finalizer_epoch": final_epoch_count == 1,
        "finalizer_epoch_count": final_epoch_count,
        "canonical_decision": canonical.get("decision"),
        "canonical_natural_terminal": canonical.get("natural_terminal"),
        "result_gate_status": gate.get("status"),
        "result_gate_all_terms_true": gate.get(
            "result_gate_conjunction", {}
        ).get("all_terms_true"),
        "result_gate_natural_completion": gate.get(
            "result_gate_conjunction", {}
        ).get("natural_completion"),
    }


def validate(
    target_zip: Path,
    bash: Path,
) -> dict[str, Any]:
    if sha256(target_zip) != ZIP_SHA256:
        raise RevalidationError("frozen v20 ZIP SHA differs")
    sidecar = Path(str(target_zip) + ".sha256")
    if sidecar.read_text(encoding="ascii") != (
        f"{ZIP_SHA256}  {target_zip.name}\n"
    ):
        raise RevalidationError("frozen v20 sidecar differs")
    with tempfile.TemporaryDirectory(
        prefix=".g71-v20-signal-",
        dir=ROOT,
        ignore_cleanup_errors=True,
    ) as temporary:
        root = Path(temporary)
        package = common.extract(
            target_zip, ROOT_NAME, root / "fresh_extract"
        )
        before = file_records(package, exclude_manifest=False)
        mock_server = root / "mock_server_root"
        mock_server.mkdir()
        run = run_signal_stub(
            package, mock_server, root / "safe_harness", bash
        )
        after = file_records(package, exclude_manifest=False)
        returned = validate_return(package, mock_server)
        signal = returned["signal_status"]
        checks = {
            "fresh_extract_package_tree_immutable": before == after,
            "safe_sim_stub_started": run["safe_sim_stub_started"],
            "runner_signal_exit_125":
                run["runner_exit_code"] == EXPECTED_STATUS,
            "runner_stderr_empty": run["runner_stderr"] == "",
            "harness_stderr_empty": run["harness_stderr"] == "",
            "signal_term_recorded": signal.get("signal") == SIGNAL,
            "compile_completed": signal.get("compile_status") == "0",
            "simulation_nonzero": signal.get("simulation_status") == "125",
            "runner_nonzero": signal.get("runner_status") == "125",
            "single_finalizer_epoch": returned["single_finalizer_epoch"],
            "critical_partial_artifacts_complete":
                returned["critical_partial_artifacts_complete"],
            "return_exact_set_valid":
                returned["return_exact_set_valid"],
            "returned_package_identity_exact":
                returned["returned_package_identity_exact"],
            "canonical_not_natural":
                returned["canonical_natural_terminal"] is False,
            "canonical_not_functional_complete":
                returned["canonical_decision"]
                != "FUNCTIONAL_EXECUTION_COMPLETED",
            "result_gate_failed":
                returned["result_gate_all_terms_true"] is False,
            "result_gate_not_natural":
                returned["result_gate_natural_completion"] is False,
        }
        if not all(checks.values()):
            raise RevalidationError(
                "safe signal-stub check differs: "
                + json.dumps(
                    {
                        key: value
                        for key, value in checks.items()
                        if not value
                    },
                    ensure_ascii=False,
                )
            )
        return {
            "schema":
                "gap-node0071-v20-safe-signal-stub-revalidation-v1",
            "status": "PASS",
            "rule_id":
                "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
            "target_zip": str(target_zip),
            "target_zip_size_bytes": target_zip.stat().st_size,
            "target_zip_sha256": ZIP_SHA256,
            "target_sidecar_sha256": sha256(sidecar),
            "signal": SIGNAL,
            "real_runner_from_fresh_extract": True,
            "real_server_or_vcs_used": False,
            "package_bytes_changed": False,
            "checks": checks,
            "runner": run,
            "return": returned,
            "package_file_count": len(before),
            "package_tree_before_sha256": hashlib.sha256(
                json.dumps(
                    before, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest(),
            "package_tree_after_sha256": hashlib.sha256(
                json.dumps(
                    after, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest(),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve(), args.bash.resolve())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as error:
        result = {
            "schema":
                "gap-node0071-v20-safe-signal-stub-revalidation-v1",
            "status": "FAIL",
            "error": str(error),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
