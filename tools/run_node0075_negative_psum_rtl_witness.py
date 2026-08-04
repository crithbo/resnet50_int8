from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


DEFAULT_OUTPUT = Path(
    "outputs/node0075_negative_psum_reachability/current_rtl_witness.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    rtl = root / "NDP_copy01/rtl"
    sources = [
        Path("NDP_copy01/rtl/utils/DW02_mult/DW02_mult.v"),
        Path("NDP_copy01/rtl/utils/DW01_add/DW01_add.v"),
        Path("NDP_copy01/rtl/utils/CSA/CSA_4to2.v"),
        Path("NDP_copy01/rtl/utils/CSA/CSA_3to2.v"),
        Path("NDP_copy01/rtl/utils/CLA/CLA_4bit.v"),
        Path("NDP_copy01/rtl/utils/CLA/CLA.v"),
        Path("NDP_copy01/rtl/utils/FCTLZ/f_ctlz.v"),
        Path("NDP_copy01/rtl/utils/FADDONE/f_addone.v"),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_Control.v"
        ),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_Expdiff.v"
        ),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Mul_Array.v"
        ),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_CSA.v"
        ),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_LZA.v"
        ),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_SHT.v"
        ),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_Expadj.v"
        ),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_Last.v"
        ),
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_ALU.v"
        ),
        Path("tests/rtl/node0075_negative_psum_witness_tb.sv"),
    ]
    missing = [item.as_posix() for item in sources if not (root / item).is_file()]
    if missing:
        raise SystemExit(f"missing sources: {missing}")

    iverilog = Path(r"C:\iverilog\bin\iverilog.exe")
    vvp = Path(r"C:\iverilog\bin\vvp.exe")
    if not iverilog.is_file() or not vvp.is_file():
        raise SystemExit("Icarus executable pair is unavailable")

    with tempfile.TemporaryDirectory(prefix="node0075-rtl-witness-") as tmp:
        binary = Path(tmp) / "witness.vvp"
        compile_argv = [
            str(iverilog),
            "-g2012",
            "-s",
            "node0075_negative_psum_witness_tb",
            "-o",
            str(binary),
            *[str(root / item) for item in sources],
        ]
        compile_run = subprocess.run(
            compile_argv,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        simulation_run = None
        if compile_run.returncode == 0:
            simulation_run = subprocess.run(
                [str(vvp), str(binary)],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

    sim_stdout = "" if simulation_run is None else simulation_run.stdout
    match = re.search(
        r"NODE0075_WITNESS PSUM=-19 DOT4=19 "
        r"RESULT=([0-9a-fA-F]{8}) EXPECTED_MATH=00000000",
        sim_stdout,
    )
    observed = None if match is None else f"0x{match.group(1).lower()}"
    compile_exit = compile_run.returncode
    simulation_exit = (
        None if simulation_run is None else simulation_run.returncode
    )
    reproduced = (
        compile_exit == 0
        and simulation_exit == 0
        and observed == "0x80000000"
        and "TB_PASS CURRENT_RTL_NEGATIVE_PSUM_SPLIT_REPRODUCED"
        in sim_stdout
    )
    receipt = {
        "schema": "node0075-current-rtl-negative-psum-witness-v1",
        "status": (
            "CURRENT_RTL_NODE0075_BOUNDARY_REPRODUCED"
            if reproduced
            else "RTL_WITNESS_FAILED"
        ),
        "compile_exit": compile_exit,
        "simulation_exit": simulation_exit,
        "observed_result_bits": observed,
        "expected_math_bits": "0x00000000",
        "current_rtl_mismatch_reproduced": reproduced,
        "witness": {
            "m": 0,
            "n": 65,
            "k_group": 3,
            "a_u8_lanes": [28, 13, 1, 0],
            "b_s8_lanes": [1, -2, 17, -2],
            "lane_products": [28, -26, 17, 0],
            "psum_in_s32": -19,
            "dot4_s32": 19,
        },
        "tool": {
            "iverilog_path": str(iverilog),
            "vvp_path": str(vvp),
            "compile_top": "node0075_negative_psum_witness_tb",
            "compile_flags": ["-g2012"],
        },
        "source_receipts": {
            item.as_posix(): sha256_file(root / item) for item in sources
        },
        "stdout": sim_stdout,
        "stdout_sha256": hashlib.sha256(sim_stdout.encode()).hexdigest(),
        "compile_stderr": compile_run.stderr,
        "simulation_stderr": (
            "" if simulation_run is None else simulation_run.stderr
        ),
        "claim_boundary": (
            "One frozen node0075 exact-cancellation occurrence against "
            "current active RTL; no RTL modification or family-wide repair."
        ),
    }
    output = args.output
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output)
    print(sha256_file(output))
    return 0 if reproduced else 1


if __name__ == "__main__":
    raise SystemExit(main())
