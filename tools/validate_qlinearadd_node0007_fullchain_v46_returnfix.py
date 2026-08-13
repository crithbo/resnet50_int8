"""Validate the exact QAdd v46 runner/return-evidence-only successor."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_fullchain_returnfix_v46"
SOURCE_NAME = "r5_qadd_n7_fullchain_v45"
OUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fullchain-v46-returnfix-package"
)
ZIP = OUT / f"{NAME}.zip"
SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
REPORT = OUT / "family_validation.json"
HARNESS = OUT / "runtime_layout_harness.json"
SOURCE_HARNESS = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fullchain-v45-package"
    / "runtime_layout_harness.json"
)
SOURCE_FAMILY = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fullchain-v45-package"
    / "family_validation.json"
)
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PYTHON = Path(
    r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\python\python.exe"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_zip(path: Path, expected_root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    names: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in names
            ):
                raise ValueError(f"unsafe/duplicate member: {info.filename}")
            names.add(info.filename)
            roots.add(pure.parts[0])
            if not info.is_dir():
                files[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
    if roots != {expected_root}:
        raise ValueError(f"ZIP root differs: {sorted(roots)}")
    return files, json.loads(files["TEST_PACKAGE_MANIFEST.json"])


def normalize(value: bytes) -> bytes:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError:
        return value
    return text.replace(NAME, SOURCE_NAME).encode("utf-8")


def intended_allowlist() -> tuple[set[tuple[str, str, str, bool]], list[str]]:
    fixed = {
        ("evidence", "PACKAGE_MANIFEST.json", "evidence/PACKAGE_MANIFEST.json", True),
        (
            "run",
            "compile/sim_results/compile_driver.log",
            "runs/compile_driver.log",
            True,
        ),
        ("run", "sim.log", "runs/sim.log", True),
        ("run", "return_observer.log", "runs/return_observer.log", True),
        (
            "evidence",
            "process_liveness_samples.jsonl",
            "evidence/process_liveness_samples.jsonl",
            True,
        ),
    }
    d_targets = [
        f"readbacks/op_tail_round/slice{index:02d}/matrix_D_linearized_128bit.txt"
        for index in range(28)
    ]
    return fixed, d_targets


def allowlist_gate(manifest: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    rows = manifest.get("return_allowlist", [])
    tuples = {
        (
            str(row.get("source_root")),
            str(row.get("source_path")),
            str(row.get("target_path")),
            bool(row.get("required")),
        )
        for row in rows
    }
    fixed, d_targets = intended_allowlist()
    formal_rows = [
        row
        for row in rows
        if str(row.get("target_path", "")).startswith("readbacks/op_tail_round/")
    ]
    pass_value = (
        fixed <= tuples
        and len(formal_rows) == 28
        and sorted(str(row["target_path"]) for row in formal_rows) == d_targets
        and all(
            row["source_root"] == "run"
            and row["source_path"]
            == row["target_path"].removeprefix("readbacks/")
            and row["required"] is True
            for row in formal_rows
        )
        and not any(
            "op_fp32_add" in str(row.get("source_path", ""))
            or str(row.get("source_path", "")).startswith("sim_results/sim.log")
            or "sim_results/return_observer" in str(row.get("source_path", ""))
            for row in rows
        )
    )
    return pass_value, {
        "count": len(rows),
        "fixed_required_present": fixed <= tuples,
        "formal_D_count": len(formal_rows),
        "formal_D_targets": sorted(str(row["target_path"]) for row in formal_rows),
    }


def allowlist_negatives(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[tuple[str, str, str | None]] = [
        ("stale_compile_source", "runs/compile_driver.log", "sim_results/compile_driver.log"),
        ("stale_sim_source", "runs/sim.log", "sim_results/sim.log"),
        (
            "stale_observer_source",
            "runs/return_observer.log",
            "sim_results/return_observer/return_observer.log",
        ),
        (
            "stale_final_D_source",
            "readbacks/op_tail_round/slice00/matrix_D_linearized_128bit.txt",
            "install/op_fp32_add/slice00/matrix_D_linearized_128bit.txt",
        ),
        ("missing_package_manifest", "evidence/PACKAGE_MANIFEST.json", None),
        (
            "missing_process_liveness",
            "evidence/process_liveness_samples.jsonl",
            None,
        ),
    ]
    results = []
    original = json.loads(json.dumps(manifest))
    for name, target_path, replacement in cases:
        mutated = json.loads(json.dumps(original))
        matches = [
            row
            for row in mutated["return_allowlist"]
            if row.get("target_path") == target_path
        ]
        if len(matches) != 1:
            raise ValueError(f"negative target is not unique: {target_path}")
        if replacement is None:
            mutated["return_allowlist"].remove(matches[0])
        else:
            matches[0]["source_path"] = replacement
        passed, _ = allowlist_gate(mutated)
        results.append(
            {
                "name": name,
                "validator_exit": 0 if passed else 1,
                "fail_closed": not passed,
            }
        )
    return results


def exact_signal_unit(runner: str) -> dict[str, Any]:
    start = runner.index("on_signal() {")
    end = runner.index("trap 'finalize $?' EXIT", start)
    function = runner[start:end].strip()
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="q46-signal-") as temporary:
        for signal_name, code in (("HUP", 129), ("INT", 130), ("TERM", 143)):
            script = Path(temporary) / f"{signal_name}.sh"
            script.write_text(
                "#!/usr/bin/env bash\nset -u\n"
                "simulation_status=125\nsim_pid=0\nsignal_name=NONE\n"
                "final_seen=0\nfinalize(){ final_seen=\"$1\"; }\n"
                + function
                + f"\non_signal {signal_name} {code}\n"
                + f'[ "$signal_name" = "{signal_name}" ]\n'
                + f'[ "$simulation_status" -eq {code} ]\n'
                + f'[ "$final_seen" -eq {code} ]\n',
                encoding="utf-8",
                newline="\n",
            )
            completed = subprocess.run(
                [str(BASH), str(script)],
                capture_output=True,
                text=True,
                check=False,
            )
            cases.append(
                {
                    "name": signal_name,
                    "exit": completed.returncode,
                    "stderr": completed.stderr,
                }
            )
    negatives = []
    for name, mutated in (
        (
            "delete_simulation_status_update",
            function.replace(
                '  [ "$simulation_status" -ne 125 ] || simulation_status="$2"\n',
                "",
                1,
            ),
        ),
        (
            "delete_finalizer_call",
            function.replace('  finalize "$2"\n', "", 1),
        ),
    ):
        with tempfile.NamedTemporaryFile(
            prefix="q46-neg-", suffix=".sh", delete=False, mode="w", encoding="utf-8"
        ) as stream:
            path = Path(stream.name)
            stream.write(
                "#!/usr/bin/env bash\nset -u\nsimulation_status=125\n"
                "sim_pid=0\nsignal_name=NONE\nfinal_seen=0\n"
                "finalize(){ final_seen=\"$1\"; }\n"
                + mutated
                + "\non_signal HUP 129\n"
                + '[ "$simulation_status" -eq 129 ] && [ "$final_seen" -eq 129 ]\n'
            )
        completed = subprocess.run(
            [str(BASH), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        path.unlink()
        negatives.append(
            {"name": name, "exit": completed.returncode, "fail_closed": completed.returncode != 0}
        )
    return {
        "source_span_sha256": sha256_bytes(function.encode("utf-8")),
        "positive_cases": cases,
        "negative_cases": negatives,
        "pass": all(row["exit"] == 0 for row in cases)
        and all(row["fail_closed"] for row in negatives),
    }


def adapted_harness(zip_sha: str, runner_sha: str) -> dict[str, Any]:
    source = json.loads(SOURCE_HARNESS.read_text(encoding="utf-8"))
    scenarios = {}
    for name, row in source["scenarios"].items():
        scenarios[name] = {
            **row,
            "command": (
                "CHANGED_SURFACE_RECEIPT_REUSE: shared install-only V2 "
                f"scenario={name}; exact v46 return evidence validated separately"
            ),
            "cwd": "$fresh_extract_parent",
            "return_zip": f"/home/panqs/ndp/simresult/{NAME}_return.zip",
            "return_sidecar": (
                f"/home/panqs/ndp/simresult/{NAME}_return.zip.sha256"
            ),
        }
    return {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": zip_sha,
        "runner_member_sha256": runner_sha,
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": scenarios,
        "claim_boundary": (
            "Shared install-only V2 layout/compile/finalizer matrix reused for "
            "unchanged control flow. Exact v46 runner bash/heredoc, signal "
            "unit, return paths, liveness and negative controls are separately "
            "bound in family_validation.json. No DUT/server action."
        ),
    }


def main() -> int:
    files, manifest = read_zip(ZIP, NAME)
    source_files, _ = read_zip(SOURCE, SOURCE_NAME)
    observed = set(files) - {"TEST_PACKAGE_MANIFEST.json"}
    inventory = {
        "declared": len(manifest["files"]),
        "observed": len(observed),
        "exact": set(manifest["files"]) == observed,
        "hashes": all(
            manifest["files"][name]
            == {"bytes": len(files[name]), "sha256": sha256_bytes(files[name])}
            or manifest["files"][name]
            == {"size_bytes": len(files[name]), "sha256": sha256_bytes(files[name])}
            for name in manifest["files"]
        ),
    }
    frozen_prefixes = ("workload/", "validation/", "tb_probe/")
    frozen = {}
    for name in sorted(name for name in source_files if name.startswith(frozen_prefixes)):
        frozen[name] = (
            name in files and normalize(files[name]) == source_files[name]
        )
    runner = files["PREPARE_AND_RUN.sh"].decode("utf-8")
    with tempfile.NamedTemporaryFile(
        prefix="q46-runner-", suffix=".sh", delete=False, mode="w", encoding="utf-8"
    ) as stream:
        runner_path = Path(stream.name)
        stream.write(runner)
    bash_syntax = subprocess.run(
        [str(BASH), "-n", str(runner_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    runner_path.unlink()
    with tempfile.TemporaryDirectory(prefix="q46-py-") as temporary:
        extracted = Path(temporary)
        py_members = [
            name
            for name in files
            if name.startswith("package_tools/") and name.endswith(".py")
        ]
        for name in py_members:
            target = extracted / Path(name).name
            target.write_bytes(files[name])
        py_compile = subprocess.run(
            [str(PYTHON), "-m", "py_compile"]
            + [str(extracted / Path(name).name) for name in py_members],
            capture_output=True,
            text=True,
            check=False,
        )
    allow_ok, allow_receipt = allowlist_gate(manifest)
    allow_negatives = allowlist_negatives(manifest)
    signal_unit = exact_signal_unit(runner)
    source_family = json.loads(SOURCE_FAMILY.read_text(encoding="utf-8"))
    hdl_members = sorted(name for name in files if name.startswith("tb_probe/"))
    hdl_reuse = (
        source_family.get("valid") is True
        and all(files[name] == source_files[name] for name in hdl_members)
        and bool(hdl_members)
    )
    checks = {
        "zip_manifest_exact": inventory["exact"] and inventory["hashes"],
        "identity": manifest.get("install_name") == NAME,
        "frozen_semantic_surface": all(frozen.values()),
        "stage_order_exact6": manifest["split_segment_contract"]["stage_names"]
        == [
            "op_a_dequant",
            "op_b_dequant",
            "op_relocation_pad",
            "op_fp32_add",
            "op_tail_mul",
            "op_tail_round",
        ],
        "formal_D_contract_exact28": len(
            manifest["split_segment_contract"]["output_checks"]
        )
        == 28,
        "return_allowlist_corrected": allow_ok,
        "return_allowlist_negatives": all(
            row["fail_closed"] for row in allow_negatives
        ),
        "runner_bash_syntax": bash_syntax.returncode == 0,
        "package_python_syntax": py_compile.returncode == 0,
        "same_shell_signal_unit": signal_unit["pass"],
        "shared_v2_layout_receipt_reuse": SOURCE_HARNESS.is_file(),
        "package_local_hdl_receipt_reuse": hdl_reuse,
        "timeout_frozen_8h": "timeout --foreground --signal=TERM --kill-after=30s 8h"
        in runner,
        "fixed_result_exact": (
            f'result_root="/home/panqs/ndp/simresult"' in runner
        ),
        "liveness_runtime_bound": (
            "qlinearadd_process_liveness_snapshot_v46.py" in runner
            and "process_liveness_samples.jsonl" in runner
        ),
    }
    errors = [name for name, value in checks.items() if value is not True]
    harness = adapted_harness(
        sha256(ZIP), sha256_bytes(files["PREPARE_AND_RUN.sh"])
    )
    write_json(HARNESS, harness)
    report = {
        "schema": "qlinearadd-node0007-fullchain-v46-family-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"bytes": ZIP.stat().st_size, "sha256": sha256(ZIP)},
        "inventory": inventory,
        "frozen_surface": {
            "file_count": len(frozen),
            "all_equal_after_identity_normalization": all(frozen.values()),
            "mismatches": [name for name, value in frozen.items() if not value],
        },
        "return_allowlist": allow_receipt,
        "negative_controls": allow_negatives,
        "signal_unit": signal_unit,
        "bash_syntax": {
            "command": f"{BASH} -n -c <exact runner>",
            "exit": bash_syntax.returncode,
            "stderr": bash_syntax.stderr,
        },
        "python_syntax": {
            "member_count": len(py_members),
            "exit": py_compile.returncode,
            "stderr": py_compile.stderr,
        },
        "package_local_hdl": {
            "members": hdl_members,
            "byte_equal_to_v45": hdl_reuse,
            "receipt_reuse_source": str(SOURCE_FAMILY.relative_to(ROOT)),
            "source_sha256": sha256(SOURCE_FAMILY),
        },
        "shared_runtime_layout": {
            "receipt_reuse_source": str(SOURCE_HARNESS.relative_to(ROOT)),
            "source_sha256": sha256(SOURCE_HARNESS),
            "changed_surface": (
                "return source paths, source byte receipt and low-rate process/"
                "log liveness only"
            ),
        },
        "claim_boundary": (
            "Local package/runner/return-evidence validation only. No DUT "
            "simulation, natural terminal, formal D, E3, E4 or E5 claim."
        ),
        "numeric_workload_config_golden_observer_timeout_rtl_repeated": False,
        "server_action": False,
    }
    write_json(REPORT, report)
    print(json.dumps({"valid": not errors, "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
