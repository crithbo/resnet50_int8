#!/usr/bin/env python3
"""Build fresh native-Conv p48 by repairing p47's dump-only XMRE scope."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_TOOL = ROOT / "tools/build_conv_native_four_lane_0ccae916_p47_tbvcdcone_package.py"
PACKAGE_ID = "r5_n4_0cc_p48_xmrscopefix"
P47_ID = "r5_n4_0cc_p47_tbvcdcone"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release"


def load_base():
    spec = importlib.util.spec_from_file_location("conv_native_p47_builder_base", BASE_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load p47 builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    builder = load_base()
    builder.PACKAGE_ID = PACKAGE_ID
    builder.OUT = OUT
    builder.TREE = OUT / "build" / PACKAGE_ID
    builder.ZIP = OUT / f"{PACKAGE_ID}.zip"
    builder.SOURCE_ZIP = builder.STORAGE / "superseded/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/r5_n4_0cc_p46_nativeflow.zip"

    original_tb_source = builder.tb_source

    def fixed_tb_source() -> str:
        source = original_tb_source()
        forbidden = (
            ".MSE_INST[5].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish",
            ".MSE_INST[6].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish",
            ".MSE_INST[7].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish",
        )
        kept = [line for line in source.splitlines() if not any(token in line for token in forbidden)]
        repaired = "\n".join(kept) + "\n"
        if any(token in repaired for token in forbidden):
            raise RuntimeError("p47 invalid dump scope survived p48 repair")
        if ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine" not in repaired:
            raise RuntimeError("selected MSE4 scope was lost")
        return repaired

    builder.tb_source = fixed_tb_source

    original_update_manifest = builder.update_manifest

    def update_manifest(contract_path: Path, selector_path: Path, runner_path: Path) -> None:
        original_update_manifest(contract_path, selector_path, runner_path)
        path = builder.TREE / "package_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["source_package"] = P47_ID
        manifest["previous_version_progress"] = (
            "p41 proved production compile beyond the Datahub repair; p42 corrected the two-bit vector predicate; "
            "p46 proved descriptor/buffer/MemAG/wdata accepts; p47 then failed production compile only at three "
            "dump-only MSE_INST[5..7] XMRE sites before simulation."
        )
        manifest["current_version_purpose"] = (
            "Delete only p47's three nonexistent dump scopes while preserving selected MSE4, the parent aggregate, "
            "the frozen p42 predicate and the full FIFO/outstanding/last/FSM/drain/clear/finish causal target."
        )
        manifest["formal_return_rootcause_receipt"] = "diagnostics/p47_formal_return_rootcause.json"
        path.write_bytes(builder.canonical(manifest))

    builder.update_manifest = update_manifest

    original_zip = builder.deterministic_zip
    prepared = False

    def deterministic_zip(target: Path) -> None:
        nonlocal prepared
        if not prepared:
            builder.write_json("diagnostics/p47_formal_return_rootcause.json", {
                "schema": "conv-native-p47-formal-return-rootcause-v1",
                "source_package": P47_ID,
                "formal_return": "r5_n4_0cc_p47_tbvcdcone_r1786698137747571521_2253824_return.zip",
                "compile_exit": 2,
                "simulation_started": False,
                "classification": "PACKAGE_LOCAL_TB_SCOPE_XMR_NONEXISTENT_MSE_INSTANCES",
                "sites": [
                    {"line": 85, "scope": "MSE_INST[5]"},
                    {"line": 86, "scope": "MSE_INST[6]"},
                    {"line": 87, "scope": "MSE_INST[7]"},
                ],
                "repair": "delete only the three dump-only references; selected MSE4 and parent aggregate scopes remain",
                "functional_rtl_modified": False,
                "pass": True,
            })
            builder.write("README.md", (
                f"# {PACKAGE_ID}\n\n"
                "Previous progress: p41 proved production compile beyond the Datahub repair; p42 fixed the two-bit vector "
                "valid/ready false-negative; p46 proved descriptor/buffer/MemAG/wdata accepts; p47 stopped before simulation "
                "at three package-local dump-only MSE_INST[5..7] XMRE sites.\n\n"
                "Current purpose: preserve the selected MSE4 bounded full causal cone and remove only those three nonexistent "
                "dump scopes so production compile can reach the p46-unobserved FIFO/outstanding/last/FSM/drain/clear/finish chain.\n\n"
                f"Only after separate server authorization: `bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
                "The Make dump variables remain zero. The package-local TB is the only VCD producer. Decimal 100000000 bytes "
                "is warning-only; 8GB VCD and 10GB return are operational stop projections, never truncation or size deletion.\n"
            ).encode("utf-8"))
            builder.update_manifest(
                builder.TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json",
                builder.TREE / "contracts/server_diagnostic_mode_selector.json",
                builder.TREE / "PREPARE_AND_RUN.sh",
            )
            prepared = True
        original_zip(target)

    builder.deterministic_zip = deterministic_zip
    builder.build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
