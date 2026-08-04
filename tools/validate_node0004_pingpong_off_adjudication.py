from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(root: Path, iverilog: str, vvp: str) -> dict[str, Any]:
    config_path = root / (
        "configs/native_ndp_sim/node0004_a_pingpong_fix_c0_v2/"
        "accumulate_waves/wave-0.json"
    )
    rtl_path = root / (
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_Inport/"
        "SA_Inport_Connect.sv"
    )
    buffer_path = root / (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Array_Request_Manager.sv"
    )
    tb_path = root / (
        "outputs/diagnostics/node0004_v14_return_v1/"
        "pingpong_off_terminal_counterexample_tb.sv"
    )
    vvp_path = tb_path.with_suffix(".validator.vvp")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rtl = rtl_path.read_text(encoding="utf-8")
    buffer_rtl = buffer_path.read_text(encoding="utf-8")
    checks = {
        "v14_stream0_pingpong_on": (
            config["stream_engine"]["stream0"]["ping_pong"] == 1
            and config["stream_engine"]["stream0"]["pingpong_last_index"] == 4
        ),
        "v14_sa_inport0_pingpong_on": (
            config["special_array"]["inport0"]["pingpong_en"] == 1
            and config["special_array"]["inport0"]["pingpong_last_index"] == 4
        ),
        "b_fixed_dual_producers": (
            config["stream_engine"]["stream1"]["target"] == "B"
            and config["stream_engine"]["stream1"]["ping_pong"] == 0
            and config["stream_engine"]["stream2"]["target"] == "B'"
            and config["stream_engine"]["stream2"]["ping_pong"] == 0
            and config["special_array"]["inport1"]["pingpong_en"] == 1
        ),
        "off_terminal_direct_source0": (
            ": sa_inport_group_in_tag[0]" in rtl
        ),
        "matched_terminal_source1_and_selector": (
            "sa_inport_group_in_tag[1]" in rtl
            and "sa_inport_last_bit_pingpong_masked" in rtl
            and "sa_inport_src_sel <= ~sa_inport_src_sel;" in rtl
        ),
        "single_buffer_clear_reuse_machinery": (
            "arm2buf_clear_unmask" in buffer_rtl
            and "array_life_cnt == buffer_life_time" in buffer_rtl
            and "buf2arm_valid_hold" in buffer_rtl
            and "arm_addr_update" in buffer_rtl
        ),
    }
    compile_command = [
        iverilog,
        "-g2012",
        f"-I{root / 'NDP_copy01/rtl/includes'}",
        "-s",
        "pingpong_off_terminal_counterexample_tb",
        "-o",
        str(vvp_path),
        str(rtl_path),
        str(tb_path),
    ]
    compile_run = subprocess.run(
        compile_command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    simulation = subprocess.run(
        [vvp, str(vvp_path)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    ) if compile_run.returncode == 0 else None
    checks["focused_tb_compile0"] = compile_run.returncode == 0
    checks["focused_tb_run0_and_pass"] = (
        simulation is not None
        and simulation.returncode == 0
        and "PASS node0004 ping-pong-off terminal counterexample"
        in simulation.stdout
    )
    valid = all(checks.values())
    return {
        "schema": "node0004-pingpong-off-adjudication-validation-v1",
        "valid": valid,
        "status": (
            "CURRENT_NODE0004_PINGPONG_OFF_NOT_EQUIVALENT"
            if valid
            else "PINGPONG_OFF_ADJUDICATION_VALIDATION_FAILED"
        ),
        "checks": checks,
        "identities": {
            "config": {
                "path": config_path.relative_to(root).as_posix(),
                "sha256": sha256_file(config_path),
            },
            "sa_inport_rtl": {
                "path": rtl_path.relative_to(root).as_posix(),
                "sha256": sha256_file(rtl_path),
            },
            "buffer_rtl": {
                "path": buffer_path.relative_to(root).as_posix(),
                "sha256": sha256_file(buffer_path),
            },
            "focused_tb": {
                "path": tb_path.relative_to(root).as_posix(),
                "sha256": sha256_file(tb_path),
            },
        },
        "focused_tb": {
            "compile_command": compile_command,
            "compile_exit_code": compile_run.returncode,
            "compile_stdout": compile_run.stdout,
            "compile_stderr": compile_run.stderr,
            "run_exit_code": (
                simulation.returncode if simulation is not None else None
            ),
            "run_stdout": simulation.stdout if simulation is not None else "",
            "run_stderr": simulation.stderr if simulation is not None else "",
        },
        "adjudication": {
            "architecturally_expressible": True,
            "current_node0004_equivalent": False,
            "currently_proven_correct": False,
            "package_generated_for_pingpong_question": False,
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--iverilog", required=True)
    parser.add_argument("--vvp", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(
        args.project_root.resolve(),
        args.iverilog,
        args.vvp,
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
