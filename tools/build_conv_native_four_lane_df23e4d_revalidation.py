from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/conv_native_four_lane_df23e4d_revalidation"
RAW_REACHABILITY = OUTPUT / "all53_raw_reachability.json"
REPORT = OUTPUT / "report.json"
TESTBENCH = (
    ROOT / "tests/rtl_audit/conv_native_four_lane_df23e4d_boundary_tb.sv"
)
VVP = OUTPUT / "boundary.vvp"
COMPILE_LOG = OUTPUT / "boundary_compile.log"
SIM_LOG = OUTPUT / "boundary_sim.log"

COMMIT = "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727"
SYNC_REPORT = (
    ROOT / "artifacts/rtl_sync/trassic_master_df23e4d_20260804/report.json"
)
SYNC_REPORT_SHA256 = (
    "6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5"
)
SYNC_RECORD = (
    ROOT
    / ".agents/task_records/"
    "20260804_trassic_master_df23e4d_active_rtl_sync_and_revalidation.md"
)
SYNC_RECORD_SHA256 = (
    "15192baf2abc9c08e87b0ea129de5ba1c0cb6b50964fce9263be638deae43bee"
)

SOURCES = (
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
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v"
    ),
    Path("tests/rtl_audit/conv_native_four_lane_df23e4d_boundary_tb.sv"),
)
LEAVES = {
    "SA_PE_Float_CSA.v": (
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_CSA.v"
        ),
        "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3",
    ),
    "SA_PE_Float_Control.v": (
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Float_Control.v"
        ),
        "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb",
    ),
    "SA_PE_Mul_Array.v": (
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_PE_Mul_Array.v"
        ),
        "135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a",
    ),
    "SA_ALU.v": (
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
            "SA_PE_ALU/SA_ALU.v"
        ),
        "c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06",
    ),
}


class RevalidationError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RevalidationError(f"JSON root must be object: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_rtl() -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    command = [
        "iverilog",
        "-g2012",
        "-s",
        "conv_native_four_lane_df23e4d_boundary_tb",
        "-o",
        str(VVP),
        *[str(ROOT / path) for path in SOURCES],
    ]
    compile_result = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    COMPILE_LOG.write_text(
        compile_result.stdout + compile_result.stderr,
        encoding="utf-8",
        newline="\n",
    )
    if compile_result.returncode != 0:
        raise RevalidationError(
            f"focused current-source compile failed: {compile_result.returncode}"
        )
    sim_result = subprocess.run(
        ["vvp", str(VVP)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    SIM_LOG.write_text(
        sim_result.stdout + sim_result.stderr,
        encoding="utf-8",
        newline="\n",
    )
    required = (
        "CASE=NODE0003_NEG5_PLUS5",
        "RESULT=00000000 EXPECTED=00000000",
        "CASE=INT32_MIN_PLUS_ZERO",
        "CASE=DOT4_SIGNED18_MIN",
        "CASE=DOT4_SIGNED18_MAX",
        "CASE=INT32_MAX_PLUS_ONE_WRAP",
        "CASE=INT32_MIN_MINUS_ONE_WRAP",
        "RTL_REPAIR_DIRECTED_PASS",
    )
    if sim_result.returncode != 0 or any(
        token not in sim_result.stdout for token in required
    ):
        raise RevalidationError(
            f"focused current-source simulation failed: {sim_result.returncode}"
        )
    manifest_payload = "\n".join(
        f"{path.as_posix()} {sha256(ROOT / path)}" for path in SOURCES
    ).encode("utf-8")
    return {
        "tool": "Icarus Verilog and VVP",
        "top": "conv_native_four_lane_df23e4d_boundary_tb",
        "testbench": {
            "path": TESTBENCH.relative_to(ROOT).as_posix(),
            "sha256": sha256(TESTBENCH),
        },
        "source_count": len(SOURCES),
        "ordered_source_manifest_sha256": hashlib.sha256(
            manifest_payload
        ).hexdigest(),
        "compile_exit": compile_result.returncode,
        "simulation_exit": sim_result.returncode,
        "compile_log": {
            "path": COMPILE_LOG.relative_to(ROOT).as_posix(),
            "sha256": sha256(COMPILE_LOG),
        },
        "simulation_log": {
            "path": SIM_LOG.relative_to(ROOT).as_posix(),
            "sha256": sha256(SIM_LOG),
        },
        "vvp": {
            "path": VVP.relative_to(ROOT).as_posix(),
            "sha256": sha256(VVP),
        },
        "covered": [
            "-6+5=-1 adjacent control",
            "frozen node0003 -5+5=0",
            "INT32_MIN+0=INT32_MIN",
            "signed18 extrema [-130560,129540]",
            "INT32 modulo wrap in both directions",
        ],
        "marker": "RTL_REPAIR_DIRECTED_PASS",
    }


def summarize_reachability() -> dict[str, Any]:
    raw = load(RAW_REACHABILITY)
    records = raw.get("records")
    if (
        not isinstance(records, list)
        or len(records) != 53
        or raw.get("scope", {}).get("all_selected_scanned") is not True
    ):
        raise RevalidationError("all-53 reachability report is incomplete")
    hit_records: list[dict[str, Any]] = []
    neg5_total = 0
    intmin_total = 0
    for record in records:
        counts = record["exact_occurrence_scan"]["counterexample_hit_counts"]
        neg5 = int(counts["NEG5_PLUS5"])
        intmin = int(counts["INT32_MIN_PLUS0"])
        neg5_total += neg5
        intmin_total += intmin
        if neg5 or intmin:
            hit_records.append(
                {
                    "hw_op_id": record["identity"]["hw_op_id"],
                    "node_id": record["identity"]["node_id"],
                    "NEG5_PLUS5": neg5,
                    "INT32_MIN_PLUS0": intmin,
                }
            )
    if (
        neg5_total != 528
        or intmin_total != 0
        or len(hit_records) != 19
        or raw["result"]["enumerated_occurrence_count"]
        != 15_426_912_256
        or raw["result"]["planned_occurrence_count_scanned_records"]
        != 15_426_912_256
    ):
        raise RevalidationError("all-53 reachability census differs")
    return {
        "raw_report": {
            "path": RAW_REACHABILITY.relative_to(ROOT).as_posix(),
            "sha256": sha256(RAW_REACHABILITY),
            "raw_status": raw["status"],
            "raw_status_semantics": (
                "legacy scanner treats reachability as a blocker because it "
                "predates the df23e4d full-width RTL repair"
            ),
        },
        "typed_conv_count": 53,
        "scanned_count": 53,
        "all_selected_scanned": True,
        "enumerated_occurrence_count": 15_426_912_256,
        "reachable_occurrences": {
            "NEG5_PLUS5": neg5_total,
            "INT32_MIN_PLUS0": intmin_total,
            "total": neg5_total + intmin_total,
            "instance_count": len(hit_records),
            "instances": hit_records,
        },
        "adjudication": (
            "all reachable named counterexamples are within the independently "
            "passing current RTL directed set"
        ),
    }


def build_report() -> dict[str, Any]:
    if sha256(SYNC_REPORT) != SYNC_REPORT_SHA256:
        raise RevalidationError("sync report identity differs")
    if sha256(SYNC_RECORD) != SYNC_RECORD_SHA256:
        raise RevalidationError("sync task record identity differs")
    leaves: dict[str, Any] = {}
    for name, (relative, expected) in LEAVES.items():
        observed = sha256(ROOT / relative)
        if observed != expected:
            raise RevalidationError(f"current RTL leaf differs: {name}")
        leaves[name] = {
            "path": relative.as_posix(),
            "sha256": observed,
        }
    rtl = run_rtl()
    reachability = summarize_reachability()
    return {
        "schema": "resnet50-conv-native-four-lane-df23e4d-revalidation-v1",
        "status": "RTL_AND_ALL53_REACHABILITY_REVALIDATION_PASS",
        "candidate_release": False,
        "package_release": "NONE",
        "current_rtl_identity": {
            "repository": "xlsjdjdk/Trassic2.0_RTL",
            "branch": "master",
            "commit": COMMIT,
            "sync_report": {
                "path": SYNC_REPORT.relative_to(ROOT).as_posix(),
                "sha256": SYNC_REPORT_SHA256,
            },
            "sync_task_record": {
                "path": SYNC_RECORD.relative_to(ROOT).as_posix(),
                "sha256": SYNC_RECORD_SHA256,
            },
            "leaves": leaves,
            "live_semantics": {
                "SA_PE_Float_CSA.v:47": (
                    "full-width o_IntResult assignment uses "
                    "i_SignC ? ~c_Result0_wire+1 : c_Result0_wire"
                ),
                "adjudication": (
                    "df23e4d closes the prior split-bit exact-cancellation "
                    "failure for the bound leaf identity"
                ),
            },
        },
        "independent_rtl_recheck": rtl,
        "real_W3_reachability": reachability,
        "blocker_delta": {
            "close": [
                "B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE",
                "SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION",
            ],
            "keep": [
                "B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING"
            ],
        },
        "claim_boundary": (
            "focused current-source Icarus/VVP plus exact all-53 frozen W3 "
            "reachability only; no E2, server dynamic, natural-terminal, "
            "formal-D, performance, E4 or E5 claim"
        ),
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SA-INT8-RTL-COMPATIBILITY-001",
                "CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001",
                "reachable boundary requires current-leaf RTL coverage before E2",
            ],
            "rule_delta_proposal": [],
        },
        "functional_rtl_modified": False,
        "serialized_assets_modified": False,
        "server_action": False,
    }


def main() -> int:
    try:
        report = build_report()
        write(REPORT, report)
    except Exception as error:
        print(f"df23e4d revalidation failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "report": str(REPORT.relative_to(ROOT)),
                "sha256": sha256(REPORT),
                "status": report["status"],
                "rtl_marker": report["independent_rtl_recheck"]["marker"],
                "reachable_occurrences": report["real_W3_reachability"][
                    "reachable_occurrences"
                ]["total"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
