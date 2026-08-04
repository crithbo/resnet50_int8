#!/usr/bin/env python3
"""Build the minimal one-command stock-RTL Dequant node0077 E4 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.dequant_node0077_server_runtime import (  # noqa: E402
    MANIFEST_NAME,
    OBSERVER_TAIL_RELATIVE,
    expected_success_return_paths,
    preflight_package,
)


SCHEMA = "resnet50-dequant-node0077-stockrtl-e4-onecmd-package-v2"
INSTALL_NAME = "dequant_node0077_stockrtl_e4_onecmd_v2"
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
E2_ROOT = ROOT / "artifacts/operator_config_validation/r5-dequant-node0077-e2-v6"
TOOL_OUTPUT = E2_ROOT / "tool-a/model_execplan/output/dq77"
BITSTREAM_NAME = (
    "op0_resnet50_dequant_node0077_uint8_fp32_bitstream_128b.bin"
)
SOURCE_IDENTITIES = {
    "strict_config": {
        "path": "configs/native_ndp_sim/resnet50_dequant_node0077_uint8_fp32_strict_v6/config.json",
        "sha256": "72c871e3bb4583302961ead62cabefa8b125281be97b5df61b45a190f18998bb",
    },
    "generation_receipt": {
        "path": "contracts/operator_config/node0077_dequant_generation_receipt_v6.json",
        "sha256": "de360328c02ff5686a4418ff191b1417520e7a774edbc7f2835e089d0bdc3eee",
    },
    "semantic_contract": {
        "path": "contracts/operator_config/node0077_dequant_semantics_evidence_v6.json",
        "sha256": "77d87c3e662ac863a1cbf5469572e362365bb4df2dd2aff8ecc9d3f475c24a56",
    },
    "local_e2_report": {
        "path": "artifacts/operator_config_validation/r5-dequant-node0077-e2-v6/local_e2_report.json",
        "sha256": "6a024f7da99026b977a4356909c99e7ac1635733fd95173a4f6741795cb965ee",
    },
    "stage_manifest": {
        "path": "configs/stage_codegen/hwop-0077-00-dequant-v1/manifest.json",
        "sha256": "ee12ab9b5c85467fe9d141fc66cf6371f31de48fdb5a634d2d904f8800a1c120",
    },
    "atomic_v3_return_analysis": {
        "path": "server_returns/dq_node0077_atomic1_stock_v3_return_analysis_20260726.json",
        "sha256": "e4dda9f7c3c7fdb978b1d4df72f4200a6e7e57ef050436ee55e54ec7b5ba0132",
    },
    "atomic_v3_task_record": {
        "path": ".agents/task_records/20260726_dequant_atomic1_v3_return_analysis.md",
        "sha256": "a8cf20787a195e2b12328525d683b14b564f0c0e6c5961aaab5f0e3b4482e527",
    },
    "w3_output_npy": {
        "path": "artifacts/w3/golden_batch16/tensors/tensor-bff07c95eb9f8609.npy",
        "sha256": "2c6c5fabc1d41fceee35f06221efb4c64b94fabfe7a0b4680d2acf2186ca0894",
    },
}
BITSTREAM_SHA256 = "c8ff24957d847df9b5f191b257567fec123605e24d1083fd6fdedc5375e674d3"
EXECPLAN_SHA256 = "5caf5840264c8b93a28fb72f8fb3666a936b5df54b509928e919484ba608ddcd"
MANDATORY_READS = (
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    ".agents/rules/DequantizeLinear算子配置规则.md",
    ".agents/rules/DequantizeLinear原子动态合同规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/plan.md",
    "ndp-sim/model_execplan/README.md",
    "ndp-sim/model_execplan/README_op_json.md",
)
MANDATORY_READ_IDENTITIES = {
    ".agents/rules/生成前必读索引.md": "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7",
    ".agents/rules/服务器测试包生成规则.md": "67018547fbe4e485d3d8c2420821e0c8f65bfec0bab0ecc1099ad9de37e55eb7",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7",
    ".agents/rules/DequantizeLinear算子配置规则.md": "b6c6586422706287625c39792e33eda6b39dc4f8a4cbd24f363b921cbc526b09",
    ".agents/rules/DequantizeLinear原子动态合同规则.md": "cc9e5215d92e55b7440a07954503586c9a6d50f56fe505595341c0ba71358d85",
    ".agents/rules/算子配置规则.md": "a5fbe2f0fa2e26d8cd4ebfe8772d5a3c69516d6918cfaa5087198706a352427b",
    ".agents/rules/NDP硬件字段语义.md": "7f446adb1719658ce75c2614c6d619fc2c7cdcabf5e4fd34945482645539158f",
    ".agents/plan.md": "52510f22511ca52fd0f0131d67c88497aee6b97c69816d934e4a62e4382bcdeb",
    "ndp-sim/model_execplan/README.md": "992360e8cfc1a15d03abbbb70047de86548e07518e329248d17c61c130b9b11f",
    "ndp-sim/model_execplan/README_op_json.md": "261cd35b989dc44f9d783eaddef00744a9b0d2d7a3112f683ea3ed2502854107",
}
CONSUMER_READS = (
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/json_loader.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/control_registers.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/output_writer.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/pipeline.py",
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/instruction_generator.py",
    "ndp-sim-ref/bitstream/main.py",
    "ndp-sim-ref/bitstream/parse.py",
    "ndp-sim-ref/bitstream/config/mapper.py",
    "ndp-sim-ref/bitstream/config/general.py",
    "NDP_copy01/Makefile.tb_NDP_Top_new_phy",
    "NDP_copy01/tb_NDP_Top_new_phy.sv",
    "NDP_copy01/native_return_observer.svh",
)
RULE_IDS = (
    "CDA-SERVER-WORKLOAD-PROVENANCE-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SCA-D-TB-READBACK-LENGTH-001",
    "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
    "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
    "CDA-SERVER-RETURN-RECEIPT-001",
    "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
    "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
    "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
    "CDA-DEQUANT-ONNX-ORDER-001",
    "CDA-DEQUANT-NO-AFFINE-MAC-001",
    "CDA-DEQUANT-TWO-STAGE-GA-001",
    "CDA-DEQUANT-NORMAL-OUTBUFFER-001",
    "CDA-DEQUANT-LAYOUT-HIGH4-001",
    "CDA-DEQUANT-STREAM-LIFECYCLE-001",
    "CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001",
    "CDA-DEQUANT-TYPED-CONSTANT-001",
    "CDA-DEQUANT-MAPPING-BINDING-001",
    "CDA-DEQUANT-E2-001",
    "CDA-DEQUANT-E4-E5-001",
)


class DequantPackageError(RuntimeError):
    """Raised when a deterministic Dequant E4 package cannot be built."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _copy_lf(source: Path, target: Path) -> None:
    _write_lf(
        target,
        source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n"),
    )


def _write_128bit_text(path: Path, payload: bytes) -> None:
    if not payload or len(payload) % 16:
        raise DequantPackageError(f"payload is not 128-bit aligned: {path}")
    _write_lf(
        path,
        "\n".join(
            f"{int.from_bytes(payload[index:index + 16], 'little'):0128b}"
            for index in range(0, len(payload), 16)
        )
        + "\n",
    )


def _canonical_128bit_words_sha256(path: Path) -> str:
    raw = path.read_bytes()
    lines = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").splitlines()
    if not lines or any(len(line) != 128 or set(line) - {48, 49} for line in lines):
        raise DequantPackageError(f"invalid 128-bit source text: {path}")
    return hashlib.sha256(b"\n".join(lines) + b"\n").hexdigest()


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return result


def _tree_sha256(records: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(records.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _verify_sources() -> dict[str, Any]:
    verified: dict[str, Any] = {}
    for name, expected in SOURCE_IDENTITIES.items():
        path = ROOT / expected["path"]
        if not path.is_file():
            raise DequantPackageError(f"missing frozen v6 source: {path}")
        actual = _sha256(path)
        if actual != expected["sha256"]:
            raise DequantPackageError(
                f"frozen v6 source identity differs: {expected['path']}"
            )
        verified[name] = {
            "path": expected["path"],
            "size_bytes": path.stat().st_size,
            "sha256": actual,
        }
    bitstream = TOOL_OUTPUT / f"install/cfg_pkg/{BITSTREAM_NAME}"
    execplan = TOOL_OUTPUT / "install/execplan.txt"
    if _sha256(bitstream) != BITSTREAM_SHA256:
        raise DequantPackageError("frozen v6 bitstream identity differs")
    if _sha256(execplan) != EXECPLAN_SHA256:
        raise DequantPackageError("frozen v6 execplan identity differs")
    mandatory_reads: list[dict[str, Any]] = []
    for relative in MANDATORY_READS:
        path = ROOT / relative
        expected = MANDATORY_READ_IDENTITIES.get(relative)
        if (
            not path.is_file()
            or expected is None
            or _sha256(path) != expected
        ):
            raise DequantPackageError(
                f"mandatory read identity differs; reread before generation: {relative}"
            )
        mandatory_reads.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": expected,
                "read_scope": "complete_file",
            }
        )
    consumers: list[dict[str, Any]] = []
    for relative in CONSUMER_READS:
        path = ROOT / relative
        if not path.is_file():
            raise DequantPackageError(f"actual consumer is missing: {relative}")
        consumers.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "read_scope": "actual_consumed_file",
            }
        )
    return {
        **verified,
        "bitstream": {
            "path": bitstream.relative_to(ROOT).as_posix(),
            "size_bytes": bitstream.stat().st_size,
            "sha256": BITSTREAM_SHA256,
        },
        "execplan": {
            "path": execplan.relative_to(ROOT).as_posix(),
            "size_bytes": execplan.stat().st_size,
            "sha256": EXECPLAN_SHA256,
        },
        "generation_read_receipt": {
            "schema": "dequant-node0077-full-e4-generation-read-receipt-v2",
            "status": "complete",
            "read_session_date": "2026-07-26",
            "mandatory_files": mandatory_reads,
            "actual_consumers": consumers,
            "rule_ids": list(RULE_IDS),
        },
    }


def _local_reference_identity() -> dict[str, Any]:
    rtl_root = ROOT / "NDP_copy01/rtl"
    records = _records(rtl_root)
    focus = {}
    for relative in (
        "Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv",
        "Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv",
        "Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv",
        "Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE.sv",
        "Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Postprocess.sv",
    ):
        path = rtl_root / relative
        focus[f"rtl/{relative}"] = {
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "sha256": _sha256(path) if path.is_file() else None,
        }
    return {
        "informational_only": True,
        "absolute_match_not_required": True,
        "rtl_tree": {
            "file_count": len(records),
            "size_bytes": sum(item["size_bytes"] for item in records.values()),
            "tree_sha256": _tree_sha256(records),
        },
        "focused_rtl": focus,
        "support_files": {
            relative: {
                "size_bytes": (ROOT / "NDP_copy01" / relative).stat().st_size,
                "sha256": _sha256(ROOT / "NDP_copy01" / relative),
            }
            for relative in (
                "tb_NDP_Top_new_phy.sv",
                "native_return_observer.svh",
                "Makefile.tb_NDP_Top_new_phy",
                "rtl/filelists/NDP_Top_phy_filelist.f",
            )
        },
    }


def _observer_tail() -> str:
    return r"""
// Dequant node0077 full-v6 E4 raw MSE4 observer v2.
// Read-only, plusarg-gated, and deliberately does not pair request with wdata.
    bit dequant_full_e4_probe_enabled;
    integer dequant_full_e4_probe_fd [0:27];
    logic dequant_full_e4_exec_d [0:27];
    logic dequant_full_e4_finish_d [0:27];
    integer dequant_full_e4_req_count [0:27][0:1];
    integer dequant_full_e4_wdata_count [0:27][0:1];
    longint unsigned dequant_full_e4_probe_cycle;
    integer dequant_full_e4_probe_mkdir_status;

    initial begin : dequant_full_e4_probe_init
        dequant_full_e4_probe_enabled =
            $test$plusargs("DEQUANT_FULL_E4_PROBE");
        dequant_full_e4_probe_cycle = 0;
        for (int sid = 0; sid < 28; sid++) begin
            dequant_full_e4_probe_fd[sid] = 0;
            dequant_full_e4_exec_d[sid] = 1'b0;
            dequant_full_e4_finish_d[sid] = 1'b0;
            for (int ch = 0; ch < 2; ch++) begin
                dequant_full_e4_req_count[sid][ch] = 0;
                dequant_full_e4_wdata_count[sid][ch] = 0;
            end
        end
        if (dequant_full_e4_probe_enabled) begin
            dequant_full_e4_probe_mkdir_status =
                $system("mkdir -p sim_results/dequant_full_e4_probe");
            for (int sid = 0; sid < 28; sid++) begin
                dequant_full_e4_probe_fd[sid] = $fopen(
                    $sformatf(
                        "sim_results/dequant_full_e4_probe/slice%02d.log",
                        sid
                    ),
                    "w"
                );
                if (dequant_full_e4_probe_fd[sid] == 0)
                    $error(
                        "DEQUANT_FULL_E4_PROBE cannot open slice%0d log",
                        sid
                    );
                else begin
                    $fdisplay(
                        dequant_full_e4_probe_fd[sid],
                        "# Dequant node0077 full-v6 raw decoupled MSE4 observer"
                    );
                    $fdisplay(
                        dequant_full_e4_probe_fd[sid],
                        "# address_domains: slice-local expected, global-linear expected, raw post-remap observed"
                    );
                    $fdisplay(
                        dequant_full_e4_probe_fd[sid],
                        "# request and write-data are counted independently; no FIFO pairing"
                    );
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin : dequant_full_e4_probe_sample
        if (!u_NDP_Top_new.rst_n_sg) begin
            dequant_full_e4_probe_cycle = 0;
            for (int sid = 0; sid < 28; sid++) begin
                dequant_full_e4_exec_d[sid] = 1'b0;
                dequant_full_e4_finish_d[sid] = 1'b0;
                for (int ch = 0; ch < 2; ch++) begin
                    dequant_full_e4_req_count[sid][ch] = 0;
                    dequant_full_e4_wdata_count[sid][ch] = 0;
                end
            end
        end
        else if (dequant_full_e4_probe_enabled) begin
            dequant_full_e4_probe_cycle++;
            for (int group = 0; group < `SLICE_GROUP_SIZE; group++) begin
                for (int local_slice = 0;
                     local_slice < `SLICE_GROUP_NUM;
                     local_slice++) begin
                    int sid;
                    longint unsigned stream_base_word;
                    longint unsigned global_linear_base_word;
                    sid = group * `SLICE_GROUP_NUM + local_slice;
                    stream_base_word = sid << 21;
                    global_linear_base_word = stream_base_word + 26'h00002f;
                    if (
                        return_obs_sem_exec_start_mon[group][local_slice] &&
                        !dequant_full_e4_exec_d[sid]
                    )
                        $fdisplay(
                            dequant_full_e4_probe_fd[sid],
                            "%0t | STAGE_START | cycle=%0d slice=%0d group=%0d local_slice=%0d",
                            $time, dequant_full_e4_probe_cycle,
                            sid, group, local_slice
                        );
                    for (int ch = 0; ch < 2; ch++) begin
                        if (local_req_hs[group][local_slice][4][ch]) begin
                            dequant_full_e4_req_count[sid][ch]++;
                            $fdisplay(
                                dequant_full_e4_probe_fd[sid],
                                "%0t | RAW_MSE4_REQ | cycle=%0d slice=%0d group=%0d local_slice=%0d ch=%0d domain=post_remap raw_addr=0x%0h expected_slice_local_base=0x2f expected_global_linear_base=0x%0h",
                                $time, dequant_full_e4_probe_cycle,
                                sid, group, local_slice, ch,
                                return_obs_mse4_local_req_addr_mon
                                    [group][local_slice][ch],
                                global_linear_base_word
                            );
                        end
                        if (local_wdata_hs[group][local_slice][4][ch]) begin
                            dequant_full_e4_wdata_count[sid][ch]++;
                            $fdisplay(
                                dequant_full_e4_probe_fd[sid],
                                "%0t | RAW_MSE4_WDATA | cycle=%0d slice=%0d group=%0d local_slice=%0d ch=%0d data=0x%032h",
                                $time, dequant_full_e4_probe_cycle,
                                sid, group, local_slice, ch,
                                return_obs_mse4_local_wdata_mon
                                    [group][local_slice][ch]
                            );
                        end
                    end
                    if (
                        return_obs_slice_finish_mon[group][local_slice] &&
                        !dequant_full_e4_finish_d[sid]
                    ) begin
                        $fdisplay(
                            dequant_full_e4_probe_fd[sid],
                            "%0t | STAGE_FINISH | cycle=%0d slice=%0d req_total=%0d wdata_total=%0d req_ch0=%0d req_ch1=%0d wdata_ch0=%0d wdata_ch1=%0d",
                            $time, dequant_full_e4_probe_cycle, sid,
                            dequant_full_e4_req_count[sid][0] +
                                dequant_full_e4_req_count[sid][1],
                            dequant_full_e4_wdata_count[sid][0] +
                                dequant_full_e4_wdata_count[sid][1],
                            dequant_full_e4_req_count[sid][0],
                            dequant_full_e4_req_count[sid][1],
                            dequant_full_e4_wdata_count[sid][0],
                            dequant_full_e4_wdata_count[sid][1]
                        );
                        $fflush(dequant_full_e4_probe_fd[sid]);
                    end
                    dequant_full_e4_exec_d[sid] =
                        return_obs_sem_exec_start_mon[group][local_slice];
                    dequant_full_e4_finish_d[sid] =
                        return_obs_slice_finish_mon[group][local_slice];
                end
            end
        end
    end

    final begin : dequant_full_e4_probe_final
        for (int sid = 0; sid < 28; sid++)
            if (dequant_full_e4_probe_fd[sid] != 0)
                $fclose(dequant_full_e4_probe_fd[sid]);
    end
"""


def _run_script() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *) echo "NDP_copy path must be absolute: $1" >&2; exit 2 ;;
esac

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
runtime_tool="${{package_root}}/package_tools/dequant_node0077_server_runtime.py"
package_manifest="${{package_root}}/{MANIFEST_NAME}"
ndp_root="$(cd "$1" && pwd)"
install_name="{INSTALL_NAME}"
cfg_root="${{ndp_root}}/install/cfg_pkg/${{install_name}}"
run_dir="${{ndp_root}}/run_${{install_name}}"
evidence_root="${{ndp_root}}/evidence_${{install_name}}"
return_dir="${{ndp_root}}/${{install_name}}_return"
return_zip="${{return_dir}}.zip"
return_sha="${{return_zip}}.sha256"
server_command="bash PREPARE_AND_RUN.sh ${{ndp_root}}"

for required in \
  "${{ndp_root}}/tb_NDP_Top_new_phy.sv" \
  "${{ndp_root}}/native_return_observer.svh" \
  "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy" \
  "${{ndp_root}}/rtl/filelists/NDP_Top_phy_filelist.f"; do
  if [ ! -f "${{required}}" ]; then
    echo "Missing required stock-RTL server input: ${{required}}" >&2
    exit 3
  fi
done
for command_name in python3 timeout make; do
  command -v "${{command_name}}" >/dev/null 2>&1 || exit 3
done
for fresh in \
  "${{cfg_root}}" "${{run_dir}}" "${{evidence_root}}" \
  "${{return_dir}}" "${{return_zip}}" "${{return_sha}}"; do
  if [ -e "${{fresh}}" ]; then
    echo "Fresh identity required; target already exists: ${{fresh}}" >&2
    exit 4
  fi
done

mkdir -p "${{evidence_root}}"
printf '%s\\n' "${{server_command}}" > "${{evidence_root}}/server_command.txt"
run_status=125
compile_status=125
sim_status=125
probe_installed=0
finalization_started=0
termination_signal=""

restore_if_needed() {{
  if [ "${{probe_installed}}" -eq 1 ]; then
    python3 "${{runtime_tool}}" restore-probe \
      --ndp-root "${{ndp_root}}" --evidence-root "${{evidence_root}}" >/dev/null
    restore_status=$?
    if [ "${{restore_status}}" -eq 0 ]; then probe_installed=0; fi
    return "${{restore_status}}"
  fi
  return 0
}}

finalize_return() {{
  original_status="$1"
  if [ "${{finalization_started}}" -eq 1 ]; then
    exit "${{original_status}}"
  fi
  finalization_started=1
  trap - EXIT HUP INT TERM
  set +e
  restore_if_needed
  restore_status=$?
  if [ "${{restore_status}}" -ne 0 ]; then original_status="${{restore_status}}"; fi
  if [ -n "${{termination_signal}}" ]; then
    printf '%s\\n' "${{termination_signal}}" > "${{evidence_root}}/termination_signal.txt"
  fi
  if [ "${{run_status}}" -eq 125 ] && [ "${{original_status}}" -ne 0 ]; then
    run_status="${{original_status}}"
  fi
  printf '%s\\n' "${{compile_status}}" > "${{evidence_root}}/compile_exit_status.txt"
  printf '%s\\n' "${{sim_status}}" > "${{evidence_root}}/sim_exit_status.txt"
  printf '%s\\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"
  python3 "${{runtime_tool}}" capture-identity \
    --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
    --install-name "${{install_name}}" --phase post_run \
    --server-command "${{server_command}}" --exit-status "${{run_status}}" \
    --output "${{evidence_root}}/server_identity_post_run.json" >/dev/null
  post_run_status=$?
  restore_if_needed
  final_restore_status=$?
  python3 "${{runtime_tool}}" capture-identity \
    --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
    --install-name "${{install_name}}" --phase post_restore \
    --server-command "${{server_command}}" --exit-status "${{run_status}}" \
    --output "${{evidence_root}}/server_identity_post_restore.json" >/dev/null
  post_restore_status=$?
  identity_status=1
  if [ -f "${{evidence_root}}/server_identity_pre_install.json" ] &&
     [ -f "${{evidence_root}}/server_identity_post_probe_install.json" ] &&
     [ -f "${{evidence_root}}/server_identity_post_compile.json" ] &&
     [ -f "${{evidence_root}}/server_identity_post_run.json" ] &&
     [ -f "${{evidence_root}}/server_identity_post_restore.json" ]; then
    python3 "${{runtime_tool}}" verify-identity \
      --pre-install "${{evidence_root}}/server_identity_pre_install.json" \
      --post-probe-install "${{evidence_root}}/server_identity_post_probe_install.json" \
      --post-compile "${{evidence_root}}/server_identity_post_compile.json" \
      --post-run "${{evidence_root}}/server_identity_post_run.json" \
      --post-restore "${{evidence_root}}/server_identity_post_restore.json" \
      --probe-receipt "${{evidence_root}}/tb_probe_install_receipt.json" \
      --precompile-receipt "${{evidence_root}}/tb_probe_precompile_receipt.json" \
      --output "${{evidence_root}}/stock_rtl_identity_receipt.json" >/dev/null
    identity_status=$?
  fi
  python3 "${{runtime_tool}}" analyze \
    --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" \
    --install-name "${{install_name}}" --evidence-root "${{evidence_root}}" \
    --run-dir "${{run_dir}}" --run-status "${{run_status}}" \
    --output "${{evidence_root}}/SERVER_RESULT_GATE.json" >/dev/null
  analysis_status=$?
  python3 "${{runtime_tool}}" collect \
    --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" \
    --install-name "${{install_name}}" --evidence-root "${{evidence_root}}" \
    --run-dir "${{run_dir}}" --run-status "${{run_status}}" \
    --server-command "${{server_command}}" >/dev/null
  collection_status=$?
  if [ -f "${{return_zip}}" ] && [ -f "${{return_sha}}" ]; then
    echo "Return ZIP: ${{return_zip}}"
    echo "Return SHA256: ${{return_sha}}"
  else
    echo "Return collection did not produce ZIP + sidecar." >&2
  fi
  final_status="${{original_status}}"
  if [ "${{final_status}}" -eq 0 ]; then final_status="${{post_run_status}}"; fi
  if [ "${{final_status}}" -eq 0 ]; then final_status="${{final_restore_status}}"; fi
  if [ "${{final_status}}" -eq 0 ]; then final_status="${{post_restore_status}}"; fi
  if [ "${{final_status}}" -eq 0 ]; then final_status="${{identity_status}}"; fi
  if [ "${{final_status}}" -eq 0 ]; then final_status="${{analysis_status}}"; fi
  if [ "${{final_status}}" -eq 0 ]; then final_status="${{collection_status}}"; fi
  exit "${{final_status}}"
}}
trap 'finalize_return $?' EXIT
trap 'termination_signal=HUP; exit 129' HUP
trap 'termination_signal=INT; exit 130' INT
trap 'termination_signal=TERM; exit 143' TERM

python3 "${{runtime_tool}}" preflight-package \
  --package-root "${{package_root}}" --install-name "${{install_name}}" \
  --output "${{evidence_root}}/package_preflight.json" >/dev/null || exit 5
python3 "${{runtime_tool}}" capture-identity \
  --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
  --install-name "${{install_name}}" --phase pre_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_pre_install.json" >/dev/null || exit 5

mkdir -p "${{cfg_root}}" "${{run_dir}}/sim_results"
cp -a "${{package_root}}/workload/runtime/." "${{cfg_root}}/"
python3 "${{runtime_tool}}" preflight-installed \
  --package-root "${{package_root}}" --ndp-root "${{ndp_root}}" \
  --install-name "${{install_name}}" \
  --output "${{evidence_root}}/installed_preflight.json" >/dev/null || exit 5
python3 "${{runtime_tool}}" install-probe \
  --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" \
  --evidence-root "${{evidence_root}}" >/dev/null || exit 5
probe_installed=1
python3 "${{runtime_tool}}" capture-identity \
  --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
  --install-name "${{install_name}}" --phase post_probe_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_probe_install.json" >/dev/null || exit 5
python3 "${{runtime_tool}}" verify-probe-installed \
  --ndp-root "${{ndp_root}}" --evidence-root "${{evidence_root}}" \
  --output "${{evidence_root}}/tb_probe_precompile_receipt.json" >/dev/null || exit 5

cd "${{ndp_root}}"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 \
  RUN_DIR="${{run_dir}}" VCS_EXTRA_OPTS="+incdir+${{ndp_root}}" \
  > "${{run_dir}}/sim_results/compile_driver.log" 2>&1
compile_status=$?
restore_if_needed
restore_status=$?
if [ "${{restore_status}}" -ne 0 ]; then
  run_status="${{restore_status}}"
  exit "${{run_status}}"
fi
python3 "${{runtime_tool}}" capture-identity \
  --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
  --install-name "${{install_name}}" --phase post_compile \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_compile.json" >/dev/null
post_compile_status=$?
if [ "${{compile_status}}" -eq 0 ] && [ "${{post_compile_status}}" -eq 0 ]; then
  (
    cd "${{run_dir}}"
    timeout --foreground --signal=TERM --kill-after=30s 4h \
      ./sim_results/simv \
      -l sim_results/sim.log \
      +vcs+lic+wait \
      +DEQUANT_FULL_E4_PROBE \
      "+SCA_CFG=../install/cfg_pkg/${{install_name}}/sca_cfg.json" \
      "+SCA_CFG_D=../install/cfg_pkg/${{install_name}}/sca_cfg_D.json"
  )
  sim_status=$?
else
  sim_status=125
fi
if [ "${{compile_status}}" -ne 0 ]; then
  run_status="${{compile_status}}"
elif [ "${{post_compile_status}}" -ne 0 ]; then
  run_status="${{post_compile_status}}"
else
  run_status="${{sim_status}}"
fi
set -e
exit "${{run_status}}"
"""


def _readme() -> str:
    return f"""# ResNet50 DequantizeLinear node0077 — stock RTL E4

This package is the full 28-slice E4 run for the frozen v6 DequantizeLinear
workload. It contains no functional RTL or TB replacement and never writes
`rtl/**`. A read-only observer tail is transactionally appended outside
`rtl/**` for compilation, verified, and restored byte-exact before simulation.

Run exactly one command from the extracted package directory:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

The script validates and installs a unique namespace, compiles with all dumps
disabled, runs in an isolated directory, checks all 28 per-slice lifecycle logs,
compares every formal D readback (28 × 188 128-bit lines) against the v6 golden,
checks the two zero-tail FP32 words per slice, reconstructs the logical
16 × 1000 output through the frozen layout inverse, compares it to the
independent W3 golden, records raw MSE4 request/write-data handshakes without
pairing them, verifies five-phase stock identity and a complete return receipt,
and directly creates:

```text
{INSTALL_NAME}_return.zip
{INSTALL_NAME}_return.zip.sha256
```

This is E4 only. Even when E4 passes, `candidate_release` remains false until a
new-identity E5 package is generated and independently passes the same gates.
"""


def _build_workload(package: Path) -> dict[str, Any]:
    runtime = package / "workload/runtime"
    golden_root = package / "workload/golden"
    payload_root = runtime / "payloads"
    execplan_source = TOOL_OUTPUT / "install/execplan.txt"
    bitstream_source = TOOL_OUTPUT / f"install/cfg_pkg/{BITSTREAM_NAME}"
    _copy_lf(execplan_source, payload_root / "execplan.txt")
    _copy_lf(bitstream_source, payload_root / "cfg_pkg" / BITSTREAM_NAME)
    prefix = f"../install/cfg_pkg/{INSTALL_NAME}"
    sca: dict[str, Any] = {
        "Exec_Base": "0x0000_1400",
        "Exec_Length": 29,
        "Repeat_Num": 1,
        "ExecutionPlan": {
            "base_addr": "0x00001400",
            "path": f"{prefix}/payloads/execplan.txt",
        },
    }
    sca_d: dict[str, Any] = {}
    layout = json.loads((E2_ROOT / "layout_evidence.json").read_text(encoding="utf-8"))
    by_slice = {item["slice_id"]: item for item in layout["slices"]}
    for slice_id in range(28):
        item = by_slice[slice_id]
        a_source = E2_ROOT / item["a_path"]
        d_source = E2_ROOT / item["d_golden_path"]
        if _sha256(a_source) != item["a_sha256"]:
            raise DequantPackageError(f"slice{slice_id:02d} A identity differs")
        if _sha256(d_source) != item["d_golden_sha256"]:
            raise DequantPackageError(f"slice{slice_id:02d} D identity differs")
        a_target = (
            payload_root
            / f"op0/slice{slice_id:02d}/matrix_A_linearized_128bit.txt"
        )
        d_target = (
            golden_root
            / f"slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        )
        _write_128bit_text(a_target, a_source.read_bytes())
        _write_128bit_text(d_target, d_source.read_bytes())
        slice_base = slice_id << 25
        sca[f"op0_matrixA_slice{slice_id}"] = {
            "base_addr": f"0x{slice_base:08X}",
            "path": (
                f"{prefix}/payloads/op0/slice{slice_id:02d}/"
                "matrix_A_linearized_128bit.txt"
            ),
        }
        sca_d[f"op0_matrixD_slice{slice_id}"] = {
            "base_addr": f"0x{slice_base + 0x2F0:08X}",
            "path": (
                f"sim_results/formal_readback/slice{slice_id:02d}/"
                "matrix_D_linearized_128bit.txt"
            ),
            "length": 188,
        }
    full_output_source = ROOT / SOURCE_IDENTITIES["w3_output_npy"]["path"]
    full_output = np.load(full_output_source, allow_pickle=False)
    if full_output.dtype != np.float32 or full_output.shape != (16, 1000):
        raise DequantPackageError("independent W3 output signature differs")
    full_output_raw = np.ascontiguousarray(
        full_output.astype("<f4", copy=False)
    ).tobytes(order="C")
    full_output_target = golden_root / "full_output_fp32.bin"
    full_output_target.parent.mkdir(parents=True, exist_ok=True)
    full_output_target.write_bytes(full_output_raw)
    inverse_contract = {
        "schema": "dequant-node0077-full-output-layout-inverse-v1",
        "rule_id": "CDA-DEQUANT-LAYOUT-HIGH4-001",
        "profile_id": layout["profile_id"],
        "logical_shape": [16, 1000],
        "logical_dtype": "float32",
        "feature_tile": 250,
        "storage_sample_count": 3,
        "slice_count": 28,
        "physical_prefix_fp32_words_per_slice": 750,
        "hardware_fp32_words_per_slice": 752,
        "full_output_raw_path": "workload/golden/full_output_fp32.bin",
        "full_output_raw_sha256": hashlib.sha256(full_output_raw).hexdigest(),
        "source_w3_npy": {
            "path": SOURCE_IDENTITIES["w3_output_npy"]["path"],
            "sha256": SOURCE_IDENTITIES["w3_output_npy"]["sha256"],
        },
        "inverse": (
            "for each slice, physical[local_sample,local_feature] maps to "
            "logical[sample_start+local_sample,feature_start+local_feature]"
        ),
        "slices": [
            {
                key: item[key]
                for key in (
                    "slice_id",
                    "group_id",
                    "owner_step",
                    "sample_start",
                    "sample_count",
                    "feature_start",
                    "feature_count",
                    "d_golden_sha256",
                )
            }
            for item in sorted(layout["slices"], key=lambda value: value["slice_id"])
        ],
    }
    _write_lf(
        package / "validation/layout_inverse_contract.json",
        json.dumps(inverse_contract, ensure_ascii=False, indent=2) + "\n",
    )
    sca["op0_config"] = {
        "base_addr": "0x00001000",
        "path": f"{prefix}/payloads/cfg_pkg/{BITSTREAM_NAME}",
    }
    _write_lf(
        runtime / "sca_cfg.json",
        json.dumps(sca, ensure_ascii=False, indent=2) + "\n",
    )
    _write_lf(
        runtime / "sca_cfg_D.json",
        json.dumps(sca_d, ensure_ascii=False, indent=2) + "\n",
    )
    return {
        "source_execplan_sha256": EXECPLAN_SHA256,
        "source_bitstream_sha256": BITSTREAM_SHA256,
        "packaged_transport": {
            "bridge": "line-preserving CRLF-to-LF canonicalization",
            "semantic_change": False,
            "source_and_package_128bit_words_identical": (
                _canonical_128bit_words_sha256(execplan_source)
                == _sha256(payload_root / "execplan.txt")
                and _canonical_128bit_words_sha256(bitstream_source)
                == _sha256(payload_root / "cfg_pkg" / BITSTREAM_NAME)
            ),
            "execplan_lf_sha256": _sha256(payload_root / "execplan.txt"),
            "bitstream_lf_sha256": _sha256(
                payload_root / "cfg_pkg" / BITSTREAM_NAME
            ),
        },
        "slice_count": 28,
        "a_bytes_per_slice": 752,
        "d_bytes_per_slice": 3008,
        "d_128bit_lines_per_slice": 188,
        "total_formal_d_128bit_lines": 5264,
        "full_output_raw_sha256": hashlib.sha256(full_output_raw).hexdigest(),
        "layout_inverse_contract": (
            "validation/layout_inverse_contract.json"
        ),
        "sca_preload_count": 30,
        "sca_d_readback_count": 28,
    }


def _copy_validation(package: Path, source_report: dict[str, Any]) -> None:
    targets = {
        "strict_config": "strict_config.json",
        "generation_receipt": "generation_receipt_v6.json",
        "semantic_contract": "semantic_contract_v6.json",
        "local_e2_report": "local_e2_report_v6.json",
        "stage_manifest": "stage_manifest_v1.json",
        "atomic_v3_return_analysis": "atomic_v3_return_analysis.json",
        "atomic_v3_task_record": "atomic_v3_task_record.md",
    }
    for name, target in targets.items():
        _copy_lf(ROOT / SOURCE_IDENTITIES[name]["path"], package / "validation" / target)
    for source, target in (
        (
            ROOT / "configs/stage_codegen/hwop-0077-00-dequant-v1/schedule_ir.json",
            package / "validation/stage_schedule_ir.json",
        ),
        (
            TOOL_OUTPUT / "config/op0/mapping_review.json",
            package / "validation/mapping_review.json",
        ),
        (
            TOOL_OUTPUT / "instructions_explained.txt",
            package / "validation/instructions_explained.txt",
        ),
        (
            E2_ROOT / "layout_evidence.json",
            package / "validation/layout_evidence.json",
        ),
        (
            E2_ROOT / "numeric_evidence.json",
            package / "validation/numeric_evidence.json",
        ),
    ):
        _copy_lf(source, target)
    _write_lf(
        package / "validation/SOURCE_V6_IDENTITY.json",
        json.dumps(source_report, ensure_ascii=False, indent=2) + "\n",
    )
    _write_lf(
        package / "validation/GENERATION_READ_RECEIPT.json",
        json.dumps(
            source_report["generation_read_receipt"],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _write_lf(
        package / "validation/EXPECTED_RETURN_EXACT_SET.json",
        json.dumps(
            {
                "schema": "dequant-node0077-full-e4-expected-return-exact-set-v1",
                "status": "success_path_exact_set",
                "install_name": INSTALL_NAME,
                "path_count": len(expected_success_return_paths()),
                "paths": expected_success_return_paths(),
                "partial_return_policy": (
                    "allowlist subset plus RETURN_RECEIPT required_missing"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _write_lf(
        package / "validation/RELEASE_GATE.json",
        json.dumps(
            {
                "schema": "resnet50-dequant-node0077-server-release-gate-v1",
                "status": "E4_PACKAGE_READY_NOT_RUN_V6_FULL_28_SLICE",
                "classification": "NO_DYNAMIC_BASELINE",
                "candidate_release": False,
                "release_gate_passed": False,
                "completed_evidence": ["E2_LOCAL_ONLY"],
                "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
                "e4_required": (
                    "28 natural slice completions, no hang/timeout/OOB, "
                    "28x188 formal D lines bit-exact, zero tails, 16x1000 "
                    "layout inverse bit-exact, natural exit, complete exact-set "
                    "return receipt, stable stock RTL/transactional observer identity"
                ),
                "e5_required": (
                    "new install/run/return identity after independent E4 acceptance"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )


def _write_deterministic_zip(package: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _audit_zip(package: Path, zip_path: Path) -> dict[str, Any]:
    expected = {
        f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}": path.read_bytes()
        for path in sorted(item for item in package.rglob("*") if item.is_file())
    }
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if names != list(expected):
            raise DequantPackageError("ZIP exact set or order differs")
        for name, raw in expected.items():
            if archive.read(name) != raw:
                raise DequantPackageError(f"ZIP payload differs: {name}")
    return {
        "entry_count": len(expected),
        "exact_set": True,
        "payloads_byte_exact": True,
        "deterministic_timestamp": "1980-01-01T00:00:00",
    }


def _build_tree(output: Path) -> dict[str, Any]:
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sidecar = Path(f"{zip_path}.sha256")
    for target in (package, zip_path, sidecar):
        if target.exists():
            raise DequantPackageError(f"output must be fresh: {target}")
    package.parent.mkdir(parents=True, exist_ok=True)
    source_report = _verify_sources()
    workload_report = _build_workload(package)
    _copy_validation(package, source_report)
    _copy_lf(
        ROOT / "tools/dequant_node0077_server_runtime.py",
        package / "package_tools/dequant_node0077_server_runtime.py",
    )
    _write_lf(package / OBSERVER_TAIL_RELATIVE, _observer_tail())
    _write_lf(package / "PREPARE_AND_RUN.sh", _run_script())
    _write_lf(package / "README.md", _readme())
    records = _records(package, exclude_manifest=True)
    manifest = {
        "schema": SCHEMA,
        "status": "E4_ONE_COMMAND_PACKAGE_READY",
        "classification": "NO_DYNAMIC_BASELINE",
        "install_name": INSTALL_NAME,
        "candidate_release": False,
        "release_gate_passed": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "remaining_blockers": ["B_DEQUANT_SERVER_E4_E5"],
        "single_hypothesis": (
            "frozen full-v6 DequantizeLinear node0077 completes on stock RTL; "
            "all 28 formal D readbacks and the 16x1000 inverse are bit-exact"
        ),
        "semantic_contract": {
            "equation": "y=(float32(uint8(x))-60.0f)*scale",
            "zero_point": 60,
            "scale_fp32_bits": "0x3e01622d",
            "slice_count": 28,
            "valid_outputs_per_slice": 750,
            "zero_tail_outputs_per_slice": 2,
        },
        "server_operation": {
            "only_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
            "command_line_count": 1,
            "automatic_install_validate_compile_run_analyze_collect": True,
        },
        "source_v6": {
            **workload_report,
            "identity_receipt": source_report,
            "reuse_policy": (
                "frozen v6 128-bit word sequence with original two-isolated-"
                "toolchain full-rebuild "
                "provenance; only the mandatory CRLF-to-LF text-ABI bridge is "
                "applied; no planner/mapper/encoder rerun in this package build"
            ),
        },
        "rtl_policy": {
            "mode": "server_original_unmodified",
            "functional_rtl_file_count": 0,
            "rtl_or_tb_source_file_included": True,
            "functional_rtl_or_tb_replacement_included": False,
            "rtl_patch_included": False,
            "functional_rtl_write_requested": False,
            "read_only_observer_tail_included": True,
            "observer_tail_path": OBSERVER_TAIL_RELATIVE,
            "observer_installed_outside_rtl_transactionally": True,
            "observer_restored_before_simulation": True,
            "phase_stability_required": [
                "pre_install",
                "post_probe_install",
                "post_compile",
                "post_run",
                "post_restore",
            ],
            "dumps": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
        },
        "runtime_policy": {
            "unique_namespace": f"install/cfg_pkg/{INSTALL_NAME}",
            "unique_run_dir": f"run_{INSTALL_NAME}",
            "unique_return_identity": f"{INSTALL_NAME}_return",
            "fresh_targets_required": True,
            "sca_and_sca_d_explicit": True,
            "repeat_num": 1,
            "start_comp_count": 1,
            "compile_timeout": "2h",
            "simulation_timeout": "4h",
            "signal_safe_partial_return": True,
            "python_dont_write_bytecode": True,
        },
        "dynamic_e4_gates": {
            "all_slice_lifecycle": (
                "28 ordered Start Cfg/Cfg Finish/Start Comp/Comp Finish logs"
            ),
            "formal_d": (
                "28 slices x 188 128-bit lines; first 750 fp32 words bit-exact "
                "and last two words positive zero"
            ),
            "layout_inverse": (
                "all formal slices reconstruct one fully covered, non-overlapping "
                "16x1000 fp32 tensor bit-exact to independent W3 golden"
            ),
            "observer_temporal": (
                "raw MSE4 request and raw wdata counted independently per "
                "physical slice/channel; no request/wdata pairing; post-remap "
                "address kept separate from slice-local/global-linear domains"
            ),
            "natural_exit": "zero process status and one TB success marker",
            "fault_absence": "no timeout, fatal, explicit error, OOB, or APB SLVERR",
            "stock_rtl_identity": "pre/post/post-run/noop-final phase stability",
        },
        "e5_boundary": (
            "E5 is not bundled or claimed; generate a fresh install/run/return "
            "identity only after E4 return acceptance"
        ),
        "return_policy": {
            "allowlist_only": True,
            "direct_zip_and_sidecar": True,
            "formal_readbacks_included": 28,
            "lifecycle_logs_included": 28,
            "observer_logs_included": 28,
            "full_compile_or_sim_log_included": False,
            "bounded_log_tails_only": True,
            "waveforms_forbidden": True,
            "build_trees_forbidden": True,
            "nested_archives_forbidden": True,
            "zip_limit_bytes": 4 * 1024 * 1024,
        },
        "rules": {
            "mandatory_files_read": list(MANDATORY_READS),
            "actual_consumers_read": list(CONSUMER_READS),
            "generation_read_receipt": (
                "validation/GENERATION_READ_RECEIPT.json"
            ),
            "rule_ids": list(RULE_IDS),
        },
        "reference_server_identity": _local_reference_identity(),
        "run_entry": "PREPARE_AND_RUN.sh",
        "payload_file_count": len(records),
        "payload_tree_sha256": _tree_sha256(records),
        "files": records,
    }
    _write_lf(
        package / MANIFEST_NAME,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    preflight_package(package, INSTALL_NAME)
    _write_deterministic_zip(package, zip_path)
    digest = _sha256(zip_path)
    _write_lf(sidecar, f"{digest}  {zip_path.name}\n")
    return {
        "schema": SCHEMA,
        "status": "built",
        "directory": package.as_posix(),
        "manifest_sha256": _sha256(package / MANIFEST_NAME),
        "payload_file_count": len(records),
        "payload_tree_sha256": manifest["payload_tree_sha256"],
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": sidecar.as_posix(),
        "server_command": manifest["server_operation"]["only_command"],
    }


def _validate_bootstrap_immutability(package: Path) -> dict[str, Any]:
    zip_path = package.with_suffix(".zip")
    with tempfile.TemporaryDirectory(prefix="dq-full-e4-bootstrap-") as temporary:
        extract_root = Path(temporary) / "fresh_extract"
        extract_root.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        fresh_package = extract_root / INSTALL_NAME
        before = _records(fresh_package)
        before_size = sum(item["size_bytes"] for item in before.values())
        output = Path(temporary) / "package_preflight.json"
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        command = [
            sys.executable,
            str(
                fresh_package
                / "package_tools/dequant_node0077_server_runtime.py"
            ),
            "preflight-package",
            "--package-root",
            str(fresh_package),
            "--install-name",
            INSTALL_NAME,
            "--output",
            str(output),
        ]
        completed = subprocess.run(
            command,
            cwd=fresh_package,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        after = _records(fresh_package)
        after_size = sum(item["size_bytes"] for item in after.values())
        if completed.returncode != 0:
            raise DequantPackageError(
                "fresh-extracted packaged runtime preflight failed: "
                + completed.stderr.strip()
            )
        if before != after or before_size != after_size:
            raise DequantPackageError(
                "fresh-extracted package tree changed during runtime bootstrap"
            )
        forbidden = [
            relative
            for relative in after
            if "__pycache__" in {
                part.lower() for part in relative.split("/")
            }
            or Path(*relative.split("/")).suffix.lower() in {".pyc", ".pyo"}
        ]
        if forbidden:
            raise DequantPackageError(
                f"runtime bootstrap materialized Python bytecode: {forbidden[:4]}"
            )
        report = json.loads(output.read_text(encoding="utf-8"))
        if report.get("status") != "package_preflight_passed":
            raise DequantPackageError("fresh-extracted runtime preflight did not pass")
        return {
            "schema": "dequant-full-e4-bootstrap-immutability-receipt-v1",
            "rule_id": "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "status": "pass",
            "fresh_zip_extraction": True,
            "preflight_output_outside_package": True,
            "python_dont_write_bytecode_environment": True,
            "python_dont_write_bytecode_runtime": True,
            "package_file_count_before": len(before),
            "package_file_count_after": len(after),
            "package_size_bytes_before": before_size,
            "package_size_bytes_after": after_size,
            "package_tree_sha256_before": _tree_sha256(before),
            "package_tree_sha256_after": _tree_sha256(after),
            "exact_path_size_sha_unchanged": True,
        }


def _validate_probe_transaction(package: Path) -> dict[str, Any]:
    zip_path = package.with_suffix(".zip")
    with tempfile.TemporaryDirectory(prefix="dq-full-e4-probe-") as temporary:
        root = Path(temporary)
        extract_root = root / "extract"
        extract_root.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        fresh_package = extract_root / INSTALL_NAME
        package_before = _records(fresh_package)
        ndp_root = root / "NDP_copy_mock"
        evidence = root / "evidence"
        ndp_root.mkdir()
        evidence.mkdir()
        observer = ndp_root / "native_return_observer.svh"
        shutil.copyfile(ROOT / "NDP_copy01/native_return_observer.svh", observer)
        observer_preimage = observer.read_bytes()
        runtime = (
            fresh_package / "package_tools/dequant_node0077_server_runtime.py"
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        def run(*arguments: str) -> None:
            completed = subprocess.run(
                [sys.executable, str(runtime), *arguments],
                cwd=fresh_package,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                raise DequantPackageError(
                    "fresh-extracted probe transaction failed: "
                    f"{arguments[0]}: {completed.stderr.strip()}"
                )

        run(
            "install-probe",
            "--ndp-root",
            str(ndp_root),
            "--package-root",
            str(fresh_package),
            "--evidence-root",
            str(evidence),
        )
        install_receipt = json.loads(
            (evidence / "tb_probe_install_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        run(
            "verify-probe-installed",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
            "--output",
            str(evidence / "tb_probe_precompile_receipt.json"),
        )
        precompile_receipt = json.loads(
            (evidence / "tb_probe_precompile_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        run(
            "restore-probe",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
        )
        final_receipt = json.loads(
            (evidence / "tb_probe_install_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        if observer.read_bytes() != observer_preimage:
            raise DequantPackageError(
                "probe transaction did not restore observer byte-exact"
            )
        package_after = _records(fresh_package)
        if package_before != package_after:
            raise DequantPackageError(
                "probe transaction changed fresh-extracted package tree"
            )
        return {
            "schema": "dequant-full-e4-probe-transaction-receipt-v1",
            "status": "pass",
            "fresh_zip_extraction": True,
            "install_receipt_status": install_receipt.get("status"),
            "precompile_receipt_status": precompile_receipt.get("status"),
            "xmr_elaboration_gate": precompile_receipt[
                "xmr_elaboration_gate"
            ],
            "final_receipt_status": final_receipt.get("status"),
            "restored_byte_exact": True,
            "package_tree_unchanged": True,
        }


def build_package(output: Path) -> dict[str, Any]:
    package = output.resolve()
    if package.name != INSTALL_NAME:
        raise DequantPackageError(
            f"output directory name must preserve ZIP identity: {INSTALL_NAME}"
        )
    zip_path = package.with_suffix(".zip")
    sidecar = Path(f"{zip_path}.sha256")
    for target in (package, zip_path, sidecar):
        if target.exists():
            raise DequantPackageError(f"output must be fresh: {target}")
    with tempfile.TemporaryDirectory(
        prefix="dq-full-e4-a-"
    ) as left_parent, tempfile.TemporaryDirectory(
        prefix="dq-full-e4-b-"
    ) as right_parent:
        left = Path(left_parent) / INSTALL_NAME
        right = Path(right_parent) / INSTALL_NAME
        left_report = _build_tree(left)
        right_report = _build_tree(right)
        left_zip = left.with_suffix(".zip")
        right_zip = right.with_suffix(".zip")
        if (
            left_report["zip_sha256"] != right_report["zip_sha256"]
            or left_zip.read_bytes() != right_zip.read_bytes()
            or _records(left) != _records(right)
        ):
            raise DequantPackageError(
                "two fresh package builds are not byte-identical"
            )
        package.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(right, package)
        shutil.copyfile(right_zip, zip_path)
        shutil.copyfile(Path(f"{right_zip}.sha256"), sidecar)
    validation = validate_package(package)
    return {
        **right_report,
        "directory": package.as_posix(),
        "zip": zip_path.as_posix(),
        "sidecar": sidecar.as_posix(),
        "deterministic_package_build_count": 2,
        "deterministic_zip_byte_identical": True,
        "bootstrap_immutability": validation["bootstrap_immutability"],
        "probe_transaction": validation["probe_transaction"],
        "complete_package_self_check_count": 1,
    }


def validate_package(output: Path) -> dict[str, Any]:
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sidecar = Path(f"{zip_path}.sha256")
    manifest = json.loads((package / MANIFEST_NAME).read_text(encoding="utf-8"))
    records = _records(package, exclude_manifest=True)
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("install_name") != INSTALL_NAME
        or manifest.get("files") != records
        or manifest.get("payload_tree_sha256") != _tree_sha256(records)
    ):
        raise DequantPackageError("manifest exact-set identity differs")
    if manifest["rtl_policy"]["functional_rtl_file_count"] != 0:
        raise DequantPackageError("functional RTL count is not zero")
    forbidden_rtl_entries = [
        relative
        for relative in records
        if "rtl" in {part.lower() for part in relative.split("/")}
    ]
    if forbidden_rtl_entries:
        raise DequantPackageError(
            f"package contains rtl path entries: {forbidden_rtl_entries[:4]}"
        )
    script = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    export_at = script.find("export PYTHONDONTWRITEBYTECODE=1")
    first_python = script.find("python3 ")
    if export_at < 0 or first_python < 0 or export_at > first_python:
        raise DequantPackageError("no-bytecode export does not precede Python")
    required_tokens = (
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0",
        "+DEQUANT_FULL_E4_PROBE",
        f"+SCA_CFG=../install/cfg_pkg/${{install_name}}/sca_cfg.json",
        f"+SCA_CFG_D=../install/cfg_pkg/${{install_name}}/sca_cfg_D.json",
        '"${runtime_tool}" install-probe',
        '"${runtime_tool}" verify-probe-installed',
        '"${runtime_tool}" restore-probe',
        "trap 'finalize_return $?' EXIT",
        "timeout --foreground --signal=TERM --kill-after=30s 4h",
    )
    for token in required_tokens:
        if token not in script:
            raise DequantPackageError(f"runner token missing: {token}")
    preflight = preflight_package(package, INSTALL_NAME)
    zip_audit = _audit_zip(package, zip_path)
    digest = _sha256(zip_path)
    if sidecar.read_text(encoding="ascii") != f"{digest}  {zip_path.name}\n":
        raise DequantPackageError("ZIP sidecar differs")
    bootstrap = _validate_bootstrap_immutability(package)
    probe_transaction = _validate_probe_transaction(package)
    return {
        "schema": SCHEMA,
        "status": "validated",
        "directory": package.as_posix(),
        "manifest_sha256": _sha256(package / MANIFEST_NAME),
        "payload_file_count": len(records),
        "payload_tree_sha256": _tree_sha256(records),
        "functional_rtl_file_count": 0,
        "rtl_path_entry_count": 0,
        "preflight": preflight,
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "zip_audit": zip_audit,
        "bootstrap_immutability": bootstrap,
        "probe_transaction": probe_transaction,
        "sidecar": sidecar.as_posix(),
        "server_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": [
            f"{INSTALL_NAME}_return.zip",
            f"{INSTALL_NAME}_return.zip.sha256",
        ],
        "expected_return_exact_set": expected_success_return_paths(),
        "release_gate": "candidate_release=false; E4 and E5 not yet closed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        report = (
            validate_package(output)
            if args.validate_only
            else build_package(output)
        )
    except Exception as exc:
        print(f"Dequant node0077 package failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
