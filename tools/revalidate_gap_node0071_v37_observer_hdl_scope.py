from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v35_observer_hdl_scope as prior


INSTALL_NAME = "r5_n71_gap_v37_dbclk_rdready_compilefix"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
BAD = "return_obs_rd_spatial_mon"
GOOD = "return_obs_rd_spatial_size_mon"
CRITICAL_UPDATE = "return_obs_dbrr_queue_enqueue[dbrr_flow]++;"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], cwd: Path) -> dict[str, Any]:
    process = subprocess.run(
        argv, cwd=cwd, text=True, capture_output=True, check=False
    )
    return {
        "argv": argv,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "stdout_sha256": sha256_bytes(process.stdout.encode()),
        "stderr_sha256": sha256_bytes(process.stderr.encode()),
    }


def exact_closure(observer: str) -> dict[str, Any]:
    declaration_pattern = re.compile(
        r"\[1:0\]\[7:0\]\s+"
        r"return_obs_rd_prep_count_mon,\s*"
        r"return_obs_rd_queue_tsf_size_mon,\s*"
        rf"{GOOD};",
        re.MULTILINE,
    )
    consumer = (
        f"{GOOD}[return_obs_group_id]"
        "[return_obs_local_slice_id][dbrr_flow]"
    )
    sampler = prior.section(
        observer, prior.SAMPLER_ANCHOR, prior.SAMPLER_END
    )
    checks = {
        "v36_bad_identifier_absent": BAD not in observer,
        "exact_declaration_resolves":
            len(declaration_pattern.findall(observer)) == 1,
        "two_external_monitor_assignments":
            observer.count(f"assign {GOOD}[") == 2,
        "actual_required_consumer_exactly_once":
            observer.count(consumer) == 1,
        "consumer_inside_dbclk_sampler": consumer in sampler,
        "owner_clock":
            "always @(posedge u_NDP_Top_new.clk)" in sampler
            and "clk_sg" not in sampler,
        "critical_qualified_update": CRITICAL_UPDATE in sampler,
    }
    return {
        "checks": checks,
        "valid": all(checks.values()),
        "bad_identifier_hits": observer.count(BAD),
        "good_identifier_hits": observer.count(GOOD),
        "assignment_hits": observer.count(f"assign {GOOD}["),
        "actual_consumer_hits": observer.count(consumer),
    }


def focused_evaluate(
    observer: str,
    iverilog: Path,
    temp: Path,
    stem: str,
) -> dict[str, Any]:
    closure = exact_closure(observer)
    prior.SIGNALS = prior.SIGNALS.replace(
        "  logic [7:0] return_obs_rd_spatial_mon[0:0][0:0][0:1];",
        "  logic [7:0] return_obs_rd_spatial_size_mon[0:0][0:0][0:1];",
    )
    projected = prior.projection(observer)
    source = temp / f"{stem}.sv"
    source.write_text(projected, encoding="utf-8", newline="\n")
    compile_result = run(
        [
            str(iverilog),
            "-g2012",
            "-tnull",
            "-s",
            "v35_dbrr_focus",
            str(source),
        ],
        temp,
    )
    return {
        "valid":
            closure["valid"] and compile_result["exit_code"] == 0,
        "exact_closure": closure,
        "focused_compile": compile_result,
        "projection_sha256": sha256_bytes(projected.encode()),
    }


def mutate_sampler(observer: str, old: str, new: str) -> str:
    left, right = observer.split(prior.SAMPLER_ANCHOR, 1)
    return (
        left
        + prior.SAMPLER_ANCHOR
        + right.replace(old, new, 1)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--iverilog",
        type=Path,
        default=Path(r"C:\iverilog\bin\iverilog.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        target = args.target_zip.resolve()
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP CRC differs")
            payload = archive.read(
                f"{INSTALL_NAME}/{OBSERVER_RELATIVE}"
            )
        observer = payload.decode("utf-8")
        tool = args.iverilog.resolve()
        version = run([str(tool), "-V"], Path.cwd())
        with tempfile.TemporaryDirectory(
            prefix="gap-v37-hdl-"
        ) as temporary:
            temp = Path(temporary)
            positive = focused_evaluate(
                observer, tool, temp, "positive"
            )
            declaration = (
                "                      "
                "return_obs_rd_spatial_size_mon;"
            )
            consumer = (
                f"{GOOD}[return_obs_group_id]"
                "[return_obs_local_slice_id][dbrr_flow]"
            )
            mutations = [
                (
                    "actual_monitor_declaration_removed",
                    observer.replace(
                        declaration,
                        "                      "
                        "return_obs_rd_spatial_size_removed;",
                        1,
                    ),
                ),
                (
                    "actual_required_consumer_misspelled",
                    mutate_sampler(
                        observer, consumer,
                        "return_obs_rd_spatial_typo"
                        "[return_obs_group_id]"
                        "[return_obs_local_slice_id][dbrr_flow]",
                    ),
                ),
                (
                    "critical_qualified_update_removed",
                    observer.replace(
                        CRITICAL_UPDATE, "/* update removed */", 1
                    ),
                ),
                (
                    "production_v36_bad_identifier_reintroduced",
                    mutate_sampler(observer, consumer, consumer.replace(
                        GOOD, BAD
                    )),
                ),
                (
                    "owner_clock_reverted",
                    mutate_sampler(
                        observer,
                        "always @(posedge u_NDP_Top_new.clk)",
                        "always @(posedge u_NDP_Top_new.clk_sg)",
                    ),
                ),
            ]
            controls = []
            for name, mutated in mutations:
                checked = focused_evaluate(
                    mutated, tool, temp, name
                )
                controls.append(
                    {
                        "name": name,
                        "failed_closed": not checked["valid"],
                        "compile_exit_code":
                            checked["focused_compile"]["exit_code"],
                        "closure_valid":
                            checked["exact_closure"]["valid"],
                    }
                )
        passed = (
            version["exit_code"] == 0
            and positive["valid"]
            and all(item["failed_closed"] for item in controls)
        )
        result = {
            "schema":
                "gap-node0071-v37-focused-observer-hdl-scope-v1",
            "status": "PASS" if passed else "FAIL",
            "pass": passed,
            "target_zip": str(target),
            "target_zip_size_bytes": target.stat().st_size,
            "target_zip_sha256": sha256_path(target),
            "observer_member":
                f"{INSTALL_NAME}/{OBSERVER_RELATIVE}",
            "observer_sha256": sha256_bytes(payload),
            "frontend": {
                "name": "Icarus Verilog",
                "path": str(tool),
                "version_exit_code": version["exit_code"],
                "version_stdout": version["stdout"],
                "version_stderr": version["stderr"],
                "coverage": "focused",
            },
            "positive": positive,
            "negative_controls": controls,
            "all_negative_controls_fail_closed": all(
                item["failed_closed"] for item in controls
            ),
            "full_design_elaboration_claimed": False,
            "specializations": [
                {
                    "scope": "external DUT/XMR hierarchy",
                    "reason": (
                        "Windows lacks production VCS and complete vendor DUT "
                        "dependencies; focused mocks do not declare or replace "
                        "the package-local corrected monitor consumer."
                    ),
                }
            ],
            "claim_boundary": (
                "Exact final v37 package-local corrected identifier "
                "declaration/assignment/required consumer and clk_db sampler "
                "syntax/name resolution; production full-design elaboration "
                "remains server evidence."
            ),
        }
        exit_code = 0 if passed else 1
    except Exception as error:
        result = {
            "schema":
                "gap-node0071-v37-focused-observer-hdl-scope-v1",
            "status": "FAIL",
            "pass": False,
            "error": str(error),
        }
        exit_code = 1
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
