from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


DW01_ADD = r"""
module DW01_add #(parameter width = 48) (
    output [width-1:0] SUM,
    output CO,
    input [width-1:0] A,
    input [width-1:0] B,
    input CI
);
assign {CO, SUM} = A + B + CI;
endmodule
"""


TESTBENCH = r"""
module tb;
reg [31:0] a_data;
reg [31:0] b_data;
wire [31:0] result;
wire [74:0] unused_result;
wire unused_cout;
integer a;
integer b;
integer checks;
reg [7:0] max_ab;
reg [7:0] max_ba;

GA_PE_Float_CSA dut(
    .o_Result(unused_result),
    .o_Cout(unused_cout),
    .o_IntResult(result),
    .i_AddDataA(75'b0),
    .i_AddDataB(75'b0),
    .i_AddDataA_uint8(a_data),
    .i_AddDataB_uint8(b_data),
    .i_is_int8(1'b1),
    .i_Sub(1'b0),
    .i_Stall(1'b0),
    .i_Mode(1'b0),
    .clk(1'b0)
);

initial begin
    checks = 0;
    for (a = 0; a < 256; a = a + 1) begin
        for (b = 0; b < 256; b = b + 1) begin
            a_data = {a[7:0], b[7:0], a[7:0], b[7:0]};
            b_data = {b[7:0], a[7:0], b[7:0], a[7:0]};
            #1;
            max_ab = (a >= b) ? a[7:0] : b[7:0];
            max_ba = (b >= a) ? b[7:0] : a[7:0];
            if (result !== {max_ab, max_ba, max_ab, max_ba}) begin
                $display("FAIL a=%0d b=%0d result=%08x expected=%02x%02x%02x%02x",
                    a, b, result, max_ab, max_ba, max_ab, max_ba);
                $finish(1);
            end
            checks = checks + 4;
        end
    end
    $display("PASS input_pairs=65536 byte_lane_checks=%0d", checks);
    $finish(0);
end
endmodule
"""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tool(name: str, fallback: Path) -> Path:
    found = shutil.which(name)
    candidate = Path(found) if found else fallback
    if not candidate.is_file():
        raise RuntimeError(f"required RTL tool is unavailable: {name}")
    return candidate.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exhaustively prove the active RTL int8_max byte comparison is unsigned"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/w5/hwop-0002-00/maxpool_v1/rtl_uint8_kernel_proof.json"),
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else project_root / args.output
    if output.exists():
        raise RuntimeError(f"refusing to overwrite RTL proof report: {output}")
    rtl = (
        project_root
        / "NDP_copy01"
        / "rtl"
        / "Slice"
        / "General_Array"
        / "GA_PE_Group"
        / "GA_ALU"
        / "GA_PE_Float_CSA.v"
    )
    if not rtl.is_file():
        raise RuntimeError(f"active RTL arithmetic source is missing: {rtl}")
    iverilog = _tool("iverilog", Path(r"C:\iverilog\bin\iverilog.exe"))
    vvp = _tool("vvp", Path(r"C:\iverilog\bin\vvp.exe"))
    with tempfile.TemporaryDirectory(prefix="maxpool-rtl-uint8-") as temp_text:
        temp = Path(temp_text)
        stub = temp / "DW01_add.v"
        testbench = temp / "tb.sv"
        executable = temp / "maxpool_uint8.vvp"
        stub.write_text(DW01_ADD, encoding="utf-8")
        testbench.write_text(TESTBENCH, encoding="utf-8")
        compile_command = [
            str(iverilog),
            "-g2012",
            "-s",
            "tb",
            "-o",
            str(executable),
            str(stub),
            str(rtl),
            str(testbench),
        ]
        compiled = subprocess.run(
            compile_command, capture_output=True, text=True, check=False, timeout=30
        )
        if compiled.returncode:
            raise RuntimeError(f"Icarus compile failed: {compiled.stderr}")
        simulated = subprocess.run(
            [str(vvp), str(executable)],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if simulated.returncode or "PASS input_pairs=65536 byte_lane_checks=262144" not in simulated.stdout:
            raise RuntimeError(
                "RTL UINT8 exhaustive test failed: "
                + (simulated.stderr or simulated.stdout)
            )
    version = subprocess.run(
        [str(iverilog), "-V"], capture_output=True, text=True, check=False, timeout=10
    )
    report = {
        "schema_version": "0.1",
        "kind": "rtl_arithmetic_kernel_proof",
        "status": "passed",
        "operator": "MaxPoolUint8",
        "scope": {
            "proved": "GA_PE_Float_CSA int8 path selects unsigned max independently on four byte lanes",
            "input_pairs": 65536,
            "byte_lane_checks": 262144,
            "full_operator_target_execution": False,
            "g6_validated": False,
        },
        "rtl_source": {
            "path": str(rtl.relative_to(project_root)).replace("\\", "/"),
            "sha256": _sha256(rtl),
        },
        "simulation": {
            "compiler": str(iverilog),
            "compiler_version_first_line": (version.stdout or version.stderr).splitlines()[0],
            "stdout": simulated.stdout.strip(),
            "stdout_sha256": hashlib.sha256(simulated.stdout.encode("utf-8")).hexdigest(),
            "designware_model": "behavioral DW01_add width-preserving addition used only for isolated kernel proof",
        },
        "limitations": [
            "This does not elaborate the complete RTL target.",
            "This does not execute stream engines, loop controllers, buffers, slice control, or multi-slice completion.",
            "It is supporting arithmetic evidence, not the third leg of the required end-to-end comparison.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "passed", "output": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
