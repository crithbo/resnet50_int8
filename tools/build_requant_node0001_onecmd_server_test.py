#!/usr/bin/env python3
"""Build the one-command stock-RTL Requant node0001 E4 package."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import lzma
import shutil
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.requant_node0001_server_runtime import (  # noqa: E402
    MANIFEST_NAME,
    preflight_package,
)


SCHEMA = "resnet50-requant-node0001-two-stage-stockrtl-e4-onecmd-package-v2"
INSTALL_NAME = "requant_node0001_two_stage_stockrtl_e4_onecmd_v2"
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "requant_node0001_e4_stockrtl_v2"
)
E2_ROOT = ROOT / "artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1"
NATIVE = E2_ROOT / "native_evidence"
INPUT_NPY = (
    ROOT
    / "artifacts/w3/subop_batch16/tensors/tensor-internal-node-0001-accumulate.npy"
)
OUTPUT_NPY = (
    ROOT / "artifacts/w3/golden_batch16/tensors/tensor-f6c1a8fb6fd529e8.npy"
)
READ_RECEIPT = (
    ROOT
    / ".agents/task_records/20260725_requant_node0001_e4_v2_package_read_receipt.json"
)
SOURCE_IDENTITIES = {
    "local_e2_report": (
        "artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/local_e2_report.json",
        "29b24ba2c0ca48348adb7e2c2b7a05508324474f506f0cabcadc1ded4f121990",
    ),
    "generation_receipt": (
        "artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/generation_receipt.json",
        "5993ccba612d8566ba470a66930263c8e5d26307955a22200cef82399f1a6cce",
    ),
    "e2_manifest": (
        "artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/manifest.json",
        "636491b767d17020f54443864dd3dc427a640a917f90010ac4db3cd3889c327f",
    ),
    "native_sca": (
        "artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/native_evidence/sca_cfg.json",
        "18316ac9ac3013b1859662a091ed99de9af4e59eb3eacb3fbc7efc1d29af2425",
    ),
    "native_sca_d": (
        "artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/native_evidence/sca_cfg_D.json",
        "fb28a93e879f0e51181ce2fbb1ae0d3da722702d3109f9b8737a5d781ac3c4cc",
    ),
    "native_execplan": (
        "artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/native_evidence/install/execplan.txt",
        "ec3d54e81677892b6e90ffa2d73a2107559039e79d6039c11f852db58a1ffd64",
    ),
    "stage_manifest": (
        "configs/stage_codegen/hwop-0001-01-requant-v1/manifest.json",
        "08613f1f42c7597f900ba93374c33bf5bc3d78a17bde3f98cb6326e6247051e3",
    ),
    "static_config_manifest": (
        "configs/native_ndp_sim/node0001_requant_two_stage_v1/manifest.json",
        "5a51a63464936240ed48bc23b1182e4be754adefbdac505c0f6e255917e6aad3",
    ),
    "input_npy": (
        "artifacts/w3/subop_batch16/tensors/tensor-internal-node-0001-accumulate.npy",
        "6af20386adf711089302791015f41cfc5ddfa89a92ddb042677b8db341d3d21c",
    ),
    "output_npy": (
        "artifacts/w3/golden_batch16/tensors/tensor-f6c1a8fb6fd529e8.npy",
        "db55178510d91ed87faf9a3884c5e0b79685f6dd2c97561dc53f00a40a1b376f",
    ),
}
RULE_IDS = (
    "CDA-SERVER-WORKLOAD-PROVENANCE-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SCA-D-TB-READBACK-LENGTH-001",
    "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
    "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
    "CDA-SERVER-RETURN-RECEIPT-001",
    "CDA-REQUANT-QPARAM-001",
    "CDA-REQUANT-INT32-GUARD-001",
    "CDA-REQUANT-SFU-LUT-001",
    "CDA-REQUANT-TWO-STAGE-001",
    "CDA-REQUANT-ROUND-MAGIC-001",
    "CDA-REQUANT-LAYOUT-HWC8-001",
    "CDA-REQUANT-MATERIALIZED-ROUNDTRIP-001",
    "CDA-REQUANT-E4-E5-001",
    "CDA-REQUANT-TRANSIENT-GUARD-E4-001",
)


class RequantPackageError(RuntimeError):
    """Raised when the deterministic E4 package cannot be built."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_lf(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _copy_lf(source: Path, target: Path) -> None:
    _write_lf(
        target,
        source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n"),
    )


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
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return digest.hexdigest()


def _verify_sources() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, (relative, expected) in SOURCE_IDENTITIES.items():
        path = ROOT / relative
        if not path.is_file() or _sha256(path) != expected:
            raise RequantPackageError(f"frozen source identity differs: {relative}")
        result[name] = {
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": expected,
        }
    return result


def _read_npy_raw(
    path: Path, expected_descr: str, expected_shape: tuple[int, ...]
) -> bytes:
    raw = path.read_bytes()
    if raw[:6] != b"\x93NUMPY":
        raise RequantPackageError(f"not an NPY file: {path}")
    version = tuple(raw[6:8])
    if version == (1, 0):
        header_length = struct.unpack_from("<H", raw, 8)[0]
        offset = 10
    elif version in {(2, 0), (3, 0)}:
        header_length = struct.unpack_from("<I", raw, 8)[0]
        offset = 12
    else:
        raise RequantPackageError(f"unsupported NPY version: {version}")
    header = ast.literal_eval(
        raw[offset : offset + header_length].decode(
            "latin1" if version != (3, 0) else "utf-8"
        )
    )
    if (
        header.get("descr") != expected_descr
        or tuple(header.get("shape", ())) != expected_shape
        or header.get("fortran_order") is not False
    ):
        raise RequantPackageError(f"NPY dtype/shape/order differs: {path}")
    payload = raw[offset + header_length :]
    item_size = 4 if expected_descr == "<i4" else 1
    expected_size = item_size
    for dimension in expected_shape:
        expected_size *= dimension
    if len(payload) != expected_size:
        raise RequantPackageError(f"NPY payload size differs: {path}")
    return payload


def _occurrence_name(wave: int, shard: int) -> str:
    return f"op_w{wave}_s{shard:02d}"


def _address_range(
    *,
    name: str,
    role: str,
    slice_id: int,
    base_addr: str,
    length_128bit: int,
) -> dict[str, Any]:
    address = int(base_addr.replace("_", ""), 16)
    local_address = address - (slice_id << 25)
    if local_address < 0 or length_128bit <= 0:
        raise RequantPackageError(f"invalid address range: {name}")
    start_row = (local_address >> 10) & 0x1FFF
    end_row = ((local_address + length_128bit * 16 - 1) >> 10) & 0x1FFF
    if end_row < start_row:
        raise RequantPackageError(f"address row wrapped within slice: {name}")
    return {
        "name": name,
        "role": role,
        "slice_id": slice_id,
        "base_addr": base_addr,
        "length_128bit": length_128bit,
        "start_row": start_row,
        "end_row": end_row,
    }


def _build_layout_contract(
    report: dict[str, Any], sca: dict[str, Any], sca_d: dict[str, Any]
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    input_bindings: list[dict[str, Any]] = []
    address_ranges: list[dict[str, Any]] = []
    stage_masks: list[str] = []
    for occurrence_index, source in enumerate(
        report["materialized_roundtrip"]["records"]
    ):
        wave = source["wave_index"]
        shard = source["shard_index"]
        prefix = _occurrence_name(wave, shard)
        active = [
            slice_id
            for slice_id in range(28)
            if int(source["used_slices"][2:], 2) & (1 << slice_id)
        ]
        if len(active) != len(source["sample_ids"]):
            raise RequantPackageError("slice/sample cardinality differs")
        slice_to_sample = {
            str(slice_id): sample
            for slice_id, sample in zip(active, source["sample_ids"])
        }
        guard_key = f"{prefix}_guard"
        round_key = f"{prefix}_round"
        record = {
            "occurrence_index": occurrence_index,
            "occurrence_name": prefix,
            "wave_index": wave,
            "shard_index": shard,
            "channels": source["channels"],
            "active_slices": active,
            "slice_to_sample": slice_to_sample,
            "used_slices": source["used_slices"],
            "guard_name": guard_key,
            "round_name": round_key,
            "guard_base_addr": source["producer_output_base_addr"],
            "round_input_base_addr": source["consumer_input_base_addr"],
            "same_slice_same_address": source["same_slice_same_address"],
        }
        records.append(record)
        stage_masks.extend([source["used_slices"], source["used_slices"]])
        for slice_id in active:
            sca_key = f"{guard_key}_matrixA_slice{slice_id}"
            entry = sca.get(sca_key)
            if not isinstance(entry, dict):
                raise RequantPackageError(f"missing native input binding: {sca_key}")
            address_ranges.append(
                _address_range(
                    name=sca_key,
                    role="guard_input_int32",
                    slice_id=slice_id,
                    base_addr=entry["base_addr"],
                    length_128bit=25088,
                )
            )
            input_bindings.append(
                {
                    "sca_key": sca_key,
                    "occurrence_index": occurrence_index,
                    "sample_id": slice_to_sample[str(slice_id)],
                    "slice_id": slice_id,
                    "channels": source["channels"],
                    "base_addr": entry["base_addr"],
                    "installed_relative_path": (
                        f"payloads/inputs/{guard_key}/slice{slice_id:02d}/"
                        "matrix_A_linearized_128bit.txt"
                    ),
                }
            )
    if len(records) != 24 or len(input_bindings) != 128:
        raise RequantPackageError("24 occurrence / 128 input layout differs")
    if report["lifecycle"]["consumer_sca_sanitization"][
        "runtime_consumer_preload_key_count"
    ] != 0:
        raise RequantPackageError("consumer intermediate preload differs")
    for name, entry in sca_d.items():
        parsed = re_match_readback(name)
        if parsed is None:
            raise RequantPackageError(f"unexpected frozen SCA_D key: {name}")
        _, role, slice_id = parsed
        address_ranges.append(
            _address_range(
                name=name,
                role=(
                    "guard_intermediate_int32"
                    if role == "guard"
                    else "round_final_uint8"
                ),
                slice_id=slice_id,
                base_addr=entry["base_addr"],
                length_128bit=int(entry["length"]),
            )
        )
    maximum_address_row = max(
        item["end_row"] for item in address_ranges
    )
    if maximum_address_row >= 6144:
        raise RequantPackageError("address range reaches reserved row 6144")
    return {
        "schema": "requant-node0001-e4-runtime-layout-v1",
        "occurrence_count": 24,
        "stage_count": 48,
        "records": records,
        "stage_masks": stage_masks,
        "input_bindings": input_bindings,
        "address_ranges": address_ranges,
        "maximum_address_row": maximum_address_row,
        "producer_consumer_same_address_count": sum(
            len(record["active_slices"])
            for record in records
            if record["same_slice_same_address"]
            and record["guard_base_addr"] == record["round_input_base_addr"]
        ),
        "consumer_intermediate_preload_count": 0,
        "shared_requant_guard_load_count": 1,
        "guard_alias_contract": {
            "historical_occurrence_evidence": "TRANSIENT_GUARD_WRITE_OBSERVER",
            "end_of_run_unique_resident_evidence": "LAST_RESIDENT_GUARD_FORMAL_D",
            "duplicate_alias_sca_d_is_formal_history": False,
        },
    }


def _rewrite_sca(
    source: dict[str, Any], layout: dict[str, Any], install_name: str
) -> dict[str, Any]:
    prefix = f"../install/cfg_pkg/{install_name}"
    result: dict[str, Any] = {}
    binding_paths = {
        item["sca_key"]: item["installed_relative_path"]
        for item in layout["input_bindings"]
    }
    for name, value in source.items():
        if not isinstance(value, dict) or "path" not in value:
            result[name] = value
            continue
        entry = dict(value)
        if name in binding_paths:
            entry["path"] = f"{prefix}/{binding_paths[name]}"
        elif name == "ExecutionPlan":
            entry["path"] = f"{prefix}/payloads/execplan.txt"
        else:
            filename = PurePathCompat(value["path"]).name
            entry["path"] = f"{prefix}/payloads/cfg_pkg/{filename}"
        result[name] = entry
    return result


class PurePathCompat:
    """Tiny slash-agnostic basename helper for frozen JSON paths."""

    def __init__(self, value: str):
        self.value = value

    @property
    def name(self) -> str:
        return self.value.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _build_sca_d(
    source: dict[str, Any], layout: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_prefix = {item["occurrence_name"]: item for item in layout["records"]}
    result: dict[str, Any] = {}
    resident_guard: dict[int, tuple[int, str]] = {}
    round_count = 0
    for name, entry in source.items():
        match = re_match_readback(name)
        if match is None:
            raise RequantPackageError(f"unexpected frozen SCA_D key: {name}")
        prefix, role, slice_id = match
        occurrence = by_prefix[prefix]["occurrence_index"]
        if role == "round":
            copied = dict(entry)
            copied["path"] = f"sim_results/formal_readback/{name}.txt"
            result[name] = copied
            round_count += 1
        else:
            previous = resident_guard.get(slice_id)
            if previous is None or occurrence > previous[0]:
                resident_guard[slice_id] = (occurrence, name)
    for slice_id in range(28):
        if slice_id not in resident_guard:
            raise RequantPackageError(f"slice{slice_id} has no resident guard")
        _, name = resident_guard[slice_id]
        copied = dict(source[name])
        copied["path"] = f"sim_results/formal_readback/{name}.txt"
        result[name] = copied
    if round_count != 128 or len(resident_guard) != 28 or len(result) != 156:
        raise RequantPackageError("alias-aware SCA_D exact set differs")
    return result, {
        "round_final_count": round_count,
        "resident_guard_count": len(resident_guard),
        "historical_guard_observer_count": 128,
        "resident_guard_keys": {
            str(slice_id): name
            for slice_id, (_, name) in sorted(resident_guard.items())
        },
    }


def re_match_readback(name: str) -> tuple[str, str, int] | None:
    import re

    match = re.fullmatch(
        r"(op_w\d+_s\d+)_(guard|round)_matrixD_slice(\d+)", name
    )
    return (
        (match.group(1), match.group(2), int(match.group(3)))
        if match is not None
        else None
    )


def _coverage_contract(report: dict[str, Any]) -> dict[str, Any]:
    numeric = report["numeric_evidence"]
    return {
        "schema": "requant-node0001-w3-dynamic-coverage-v1",
        "source": "frozen full W3 batch16 node0001 accumulator/output",
        "element_count": numeric["element_count"],
        "counts": {
            "negative": numeric["negative_element_count"],
            "minus_one": numeric["minus_one_element_count"],
            "zero": numeric["zero_element_count"],
            "positive": (
                numeric["element_count"]
                - numeric["negative_element_count"]
                - numeric["zero_element_count"]
            ),
            "round_half_even_tie": 16,
            "lower_saturation": (
                numeric["negative_element_count"] + numeric["zero_element_count"]
            ),
            "upper_saturation": 0,
        },
        "tie_channels": [63],
        "all_64_channel_multipliers_covered": True,
        "multiplier_sha256": numeric["qparams"]["multiplier_sha256"],
        "full_w3_golden_sha256": numeric["golden_sha256"],
        "claim_boundary": {
            "e4_covers_lower_saturation": True,
            "e4_covers_upper_255_saturation": False,
            "upper_255_saturation_reserved_for_fresh_identity_e5": True,
        },
    }


def _probe_tail() -> str:
    return r"""
// ============================================================================
// Requant node0001 E4 transient guard observer.
// Read-only: no assign/force/deposit/release and no DUT/TB driver.
// Enabled only by +REQUANT_GUARD_PROBE.  A record is emitted only on the
// accepted MSE4 local_wdata valid&&ready handshake in the same clk_sg cycle.
// The accepted interface has no byte-strobe signal; every accepted channel
// beat is a full 128-bit transfer, recorded explicitly as strobe=0xffff.
// ============================================================================
    bit requant_guard_probe_enabled;
    integer requant_guard_probe_fd [0:27];
    integer requant_guard_probe_stage [0:27];
    logic requant_guard_probe_exec_d [0:27];
    logic requant_guard_probe_finish_d [0:27];
    logic [`MSE_TSA_ADDR_WIDTH-1:0]
        requant_guard_probe_addr_q [0:27][0:`MSE_REQ_CHL_NUM-1][$];
    longint unsigned requant_guard_probe_cycle;
    integer requant_guard_probe_mkdir_status;

    initial begin : requant_guard_probe_init
        requant_guard_probe_enabled =
            $test$plusargs("REQUANT_GUARD_PROBE");
        requant_guard_probe_cycle = 0;
        for (int sid = 0; sid < 28; sid++) begin
            requant_guard_probe_fd[sid] = 0;
            requant_guard_probe_stage[sid] = -1;
            requant_guard_probe_exec_d[sid] = 1'b0;
            requant_guard_probe_finish_d[sid] = 1'b0;
            for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                requant_guard_probe_addr_q[sid][ch].delete();
        end
        if (requant_guard_probe_enabled) begin
            requant_guard_probe_mkdir_status =
                $system("mkdir -p sim_results/requant_guard_probe");
            for (int sid = 0; sid < 28; sid++) begin
                requant_guard_probe_fd[sid] = $fopen(
                    $sformatf(
                        "sim_results/requant_guard_probe/slice%02d.log", sid
                    ),
                    "w"
                );
                if (requant_guard_probe_fd[sid] == 0)
                    $error("REQUANT_GUARD_PROBE cannot open slice%0d log", sid);
                else begin
                    $fdisplay(
                        requant_guard_probe_fd[sid],
                        "# Requant node0001 transient guard MSE4 observer v1"
                    );
                    $fdisplay(
                        requant_guard_probe_fd[sid],
                        "# accepted boundary: local_wdata_valid && local_wdata_ready"
                    );
                    $fdisplay(
                        requant_guard_probe_fd[sid],
                        "# no interface byte strobe: accepted 128-bit beat strobe=0xffff"
                    );
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin : requant_guard_probe_sample
        if (!u_NDP_Top_new.rst_n_sg) begin
            requant_guard_probe_cycle = 0;
            for (int sid = 0; sid < 28; sid++) begin
                requant_guard_probe_stage[sid] = -1;
                requant_guard_probe_exec_d[sid] = 1'b0;
                requant_guard_probe_finish_d[sid] = 1'b0;
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                    requant_guard_probe_addr_q[sid][ch].delete();
            end
        end
        else if (requant_guard_probe_enabled) begin
            requant_guard_probe_cycle++;
            for (int sid = 0; sid < 28; sid++) begin
                int gid;
                int lid;
                gid = sid / `SLICE_GROUP_NUM;
                lid = sid % `SLICE_GROUP_NUM;
                if (return_obs_sem_exec_start_mon[gid][lid] &&
                    !requant_guard_probe_exec_d[sid]) begin
                    requant_guard_probe_stage[sid]++;
                    for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                        if (requant_guard_probe_addr_q[sid][ch].size() != 0)
                            $fdisplay(
                                requant_guard_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d local_stage=%0d ch=%0d stale_addr_count=%0d",
                                $time, requant_guard_probe_cycle, sid,
                                requant_guard_probe_stage[sid], ch,
                                requant_guard_probe_addr_q[sid][ch].size()
                            );
                        requant_guard_probe_addr_q[sid][ch].delete();
                    end
                    $fdisplay(
                        requant_guard_probe_fd[sid],
                        "%0t | STAGE_START | cycle=%0d slice=%0d local_stage=%0d role=%s",
                        $time, requant_guard_probe_cycle, sid,
                        requant_guard_probe_stage[sid],
                        ((requant_guard_probe_stage[sid] % 2) == 0) ?
                            "guard" : "round"
                    );
                end
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                    if (local_req_hs[gid][lid][4][ch]) begin
                        requant_guard_probe_addr_q[sid][ch].push_back(
                            return_obs_mse4_local_req_addr_mon[gid][lid][ch]
                        );
                    end
                    if (local_wdata_hs[gid][lid][4][ch]) begin
                        logic [`MSE_TSA_ADDR_WIDTH-1:0] paired_addr;
                        if (requant_guard_probe_addr_q[sid][ch].size() == 0) begin
                            $fdisplay(
                                requant_guard_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d local_stage=%0d ch=%0d accepted_wdata_without_address=1 strobe=0xffff data=0x%032h",
                                $time, requant_guard_probe_cycle, sid,
                                requant_guard_probe_stage[sid], ch,
                                return_obs_mse4_local_wdata_mon[gid][lid][ch]
                            );
                        end
                        else begin
                            paired_addr =
                                requant_guard_probe_addr_q[sid][ch].pop_front();
                            if ((requant_guard_probe_stage[sid] % 2) == 0)
                                $fdisplay(
                                    requant_guard_probe_fd[sid],
                                    "%0t | GUARD_WRITE | cycle=%0d slice=%0d local_stage=%0d occurrence_local=%0d ch=%0d accepted=1 valid=1 ready=1 strobe=0xffff addr=0x%0h data=0x%032h",
                                    $time, requant_guard_probe_cycle, sid,
                                    requant_guard_probe_stage[sid],
                                    requant_guard_probe_stage[sid] / 2, ch,
                                    paired_addr,
                                    return_obs_mse4_local_wdata_mon[gid][lid][ch]
                                );
                        end
                    end
                end
                if (return_obs_slice_finish_mon[gid][lid] &&
                    !requant_guard_probe_finish_d[sid]) begin
                    for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                        if (requant_guard_probe_addr_q[sid][ch].size() != 0)
                            $fdisplay(
                                requant_guard_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d local_stage=%0d ch=%0d finish_outstanding_addr_count=%0d",
                                $time, requant_guard_probe_cycle, sid,
                                requant_guard_probe_stage[sid], ch,
                                requant_guard_probe_addr_q[sid][ch].size()
                            );
                    $fdisplay(
                        requant_guard_probe_fd[sid],
                        "%0t | STAGE_FINISH | cycle=%0d slice=%0d local_stage=%0d",
                        $time, requant_guard_probe_cycle, sid,
                        requant_guard_probe_stage[sid]
                    );
                    $fflush(requant_guard_probe_fd[sid]);
                end
                requant_guard_probe_exec_d[sid] =
                    return_obs_sem_exec_start_mon[gid][lid];
                requant_guard_probe_finish_d[sid] =
                    return_obs_slice_finish_mon[gid][lid];
            end
        end
    end

    final begin : requant_guard_probe_final
        for (int sid = 0; sid < 28; sid++)
            if (requant_guard_probe_fd[sid] != 0) begin
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                    if (requant_guard_probe_addr_q[sid][ch].size() != 0)
                        $fdisplay(
                            requant_guard_probe_fd[sid],
                            "%0t | PROBE_ERROR | final_outstanding ch=%0d count=%0d",
                            $time, ch,
                            requant_guard_probe_addr_q[sid][ch].size()
                        );
                $fclose(requant_guard_probe_fd[sid]);
            end
    end
"""


def _run_script() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *) echo "NDP_copy path must be absolute: $1" >&2; exit 2 ;;
esac

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
runtime_tool="${{package_root}}/package_tools/requant_node0001_server_runtime.py"
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
  if ! command -v "${{command_name}}" >/dev/null 2>&1; then
    echo "Missing command: ${{command_name}}" >&2
    exit 3
  fi
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
    if [ "${{restore_status}}" -eq 0 ]; then
      probe_installed=0
    else
      return "${{restore_status}}"
    fi
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
    [ -f "${{evidence_root}}/server_identity_post_restore.json" ] &&
    [ -f "${{evidence_root}}/tb_probe_install_receipt.json" ] &&
    [ -f "${{evidence_root}}/tb_probe_precompile_receipt.json" ]; then
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
  for status in "${{post_run_status}}" "${{final_restore_status}}" "${{post_restore_status}}" "${{identity_status}}" "${{analysis_status}}" "${{collection_status}}"; do
    if [ "${{final_status}}" -eq 0 ] && [ "${{status}}" -ne 0 ]; then
      final_status="${{status}}"
    fi
  done
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
python3 "${{runtime_tool}}" materialize-installed \
  --package-root "${{package_root}}" --ndp-root "${{ndp_root}}" \
  --install-name "${{install_name}}" \
  --output "${{evidence_root}}/input_materialization_receipt.json" >/dev/null || exit 5
python3 "${{runtime_tool}}" preflight-installed \
  --package-root "${{package_root}}" --ndp-root "${{ndp_root}}" \
  --install-name "${{install_name}}" \
  --materialization-receipt "${{evidence_root}}/input_materialization_receipt.json" \
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
restore_identity_status=$?
if [ "${{compile_status}}" -eq 0 ] && [ "${{restore_identity_status}}" -eq 0 ]; then
  (
    cd "${{run_dir}}"
    timeout --foreground --signal=TERM --kill-after=30s 12h \
      ./sim_results/simv \
      -l sim_results/sim.log \
      +vcs+lic+wait \
      +REQUANT_GUARD_PROBE \
      "+SCA_CFG=../install/cfg_pkg/${{install_name}}/sca_cfg.json" \
      "+SCA_CFG_D=../install/cfg_pkg/${{install_name}}/sca_cfg_D.json"
  )
  sim_status=$?
else
  sim_status=125
fi
if [ "${{compile_status}}" -ne 0 ]; then
  run_status="${{compile_status}}"
elif [ "${{restore_identity_status}}" -ne 0 ]; then
  run_status="${{restore_identity_status}}"
else
  run_status="${{sim_status}}"
fi
set -e
exit "${{run_status}}"
"""


def _readme() -> str:
    return f"""# ResNet50 RequantizeUint8 node0001 stock-RTL E4

在解压后的目录只运行一条命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

脚本会验证包、安装唯一命名空间、从压缩的冻结 W3 数据确定性物化 128
份 TB preload、事务式安装只读 observer、重新编译后立即逐字节恢复 observer，
再在唯一 RUN_DIR 中执行 24 occurrence / 48 stage。所有 waveform 均关闭。

三类动态证据严格分开：

1. `TRANSIENT_GUARD_WRITE_OBSERVER`：same-clock accepted MSE4 write handshake，
   覆盖 128 份历史 guard shard；
2. `FINAL_UINT8_FORMAL_SCA_D`：128 份最终 UINT8 shard 正式回读；
3. `LAST_RESIDENT_GUARD_FORMAL_D`：28 个 slice 的最后驻留 guard 正式回读。

guard 地址的历史 alias 不会冒充终态 formal readback。约 350 MiB 原始文本证据保留
在服务器隔离 RUN_DIR；回传 ZIP 仅含逐项哈希、行数、首个分歧、身份和结果门，避免
无效大回传。该包只允许 E4；即使通过，也仍需全新身份 E5。
"""


def _build_workload(package: Path) -> dict[str, Any]:
    report = json.loads(
        (E2_ROOT / "local_e2_report.json").read_text(encoding="utf-8")
    )
    source_sca = json.loads((NATIVE / "sca_cfg.json").read_text(encoding="utf-8"))
    source_sca_d = json.loads(
        (NATIVE / "sca_cfg_D.json").read_text(encoding="utf-8")
    )
    runtime = package / "workload/runtime"
    payloads = runtime / "payloads"
    layout = _build_layout_contract(report, source_sca, source_sca_d)
    sca = _rewrite_sca(source_sca, layout, INSTALL_NAME)
    sca_d, readback_contract = _build_sca_d(source_sca_d, layout)
    _write_json(runtime / "sca_cfg.json", sca)
    _write_json(runtime / "sca_cfg_D.json", sca_d)
    _write_json(runtime / "layout_contract.json", layout)
    _copy_lf(NATIVE / "install/execplan.txt", payloads / "execplan.txt")
    for source in sorted((NATIVE / "install/cfg_pkg").glob("*")):
        if source.is_file():
            _copy_lf(source, payloads / "cfg_pkg" / source.name)

    input_raw = _read_npy_raw(INPUT_NPY, "<i4", (16, 64, 112, 112))
    output_raw = _read_npy_raw(OUTPUT_NPY, "|u1", (16, 64, 112, 112))
    input_relative = "compact/input_nchw_int32.raw.xz"
    output_relative = "workload/golden/output_nchw_uint8.raw.xz"
    input_target = runtime / input_relative
    output_target = package / output_relative
    input_target.parent.mkdir(parents=True, exist_ok=True)
    output_target.parent.mkdir(parents=True, exist_ok=True)
    input_target.write_bytes(
        lzma.compress(
            input_raw, format=lzma.FORMAT_XZ, preset=9 | lzma.PRESET_EXTREME
        )
    )
    output_target.write_bytes(
        lzma.compress(
            output_raw, format=lzma.FORMAT_XZ, preset=9 | lzma.PRESET_EXTREME
        )
    )
    _write_json(
        package / "validation/coverage_contract.json",
        _coverage_contract(report),
    )
    _copy_lf(
        NATIVE / "instructions_explained.txt",
        package / "validation/instructions_explained.txt",
    )
    _copy_lf(
        E2_ROOT / "local_e2_report.json",
        package / "validation/local_e2_report.json",
    )
    return {
        "layout": layout,
        "readback": readback_contract,
        "compact_data": {
            "input": {
                "path": input_relative,
                "raw_size_bytes": len(input_raw),
                "raw_sha256": _sha256_bytes(input_raw),
                "compressed_size_bytes": input_target.stat().st_size,
                "compressed_sha256": _sha256(input_target),
                "source_npy_sha256": SOURCE_IDENTITIES["input_npy"][1],
            },
            "golden": {
                "path": output_relative,
                "raw_size_bytes": len(output_raw),
                "raw_sha256": _sha256_bytes(output_raw),
                "compressed_size_bytes": output_target.stat().st_size,
                "compressed_sha256": _sha256(output_target),
                "source_npy_sha256": SOURCE_IDENTITIES["output_npy"][1],
            },
        },
    }


def _zip_tree(package: Path) -> tuple[Path, str]:
    zip_path = package.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    digest = _sha256(zip_path)
    zip_path.with_suffix(".zip.sha256").write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return zip_path, digest


def build_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    package = output.resolve()
    if package.exists() or package.with_suffix(".zip").exists():
        raise RequantPackageError(f"fresh package identity required: {package}")
    sources = _verify_sources()
    package.mkdir(parents=True)
    workload = _build_workload(package)
    _write_lf(package / "PREPARE_AND_RUN.sh", _run_script())
    _write_lf(package / "README.md", _readme())
    _copy_lf(
        ROOT / "tools/requant_node0001_server_runtime.py",
        package / "package_tools/requant_node0001_server_runtime.py",
    )
    _write_lf(
        package / "tb_probe/requant_mse4_guard_observer_tail.svh",
        _probe_tail().lstrip(),
    )
    _copy_lf(
        READ_RECEIPT,
        package / "validation/generation_read_receipt.json",
    )
    files = _records(package)
    manifest = {
        "schema": SCHEMA,
        "package_name": package.name,
        "install_name": INSTALL_NAME,
        "target": "r5:hwop-0001-01 RequantizeUint8",
        "run_kind": "stock_rtl_e4_first_dynamic",
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "evidence_level_before_run": "E2_LOCAL_ONLY",
        "server_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "source_identities": sources,
        "compact_data": workload["compact_data"],
        "execution_contract": {
            "occurrence_count": 24,
            "stage_count": 48,
            "start_comp_count": 48,
            "same_mask_completion_fence_count": 48,
            "shared_requant_guard_load_count": 1,
            "consumer_intermediate_preload_count": 0,
            "maximum_address_row": workload["layout"]["maximum_address_row"],
        },
        "dynamic_evidence_columns": {
            "TRANSIENT_GUARD_WRITE_OBSERVER": 128,
            "FINAL_UINT8_FORMAL_SCA_D": 128,
            "LAST_RESIDENT_GUARD_FORMAL_D": 28,
        },
        "alias_claim_boundary": {
            "guard_lifetime_reuse_is_barrier_bound": True,
            "historical_alias_sca_d_treated_as_formal_readback": False,
            "historical_guard_evidence": "same-clock accepted MSE4 write observer",
        },
        "rtl_policy": {
            "functional_rtl_modified": False,
            "rtl_directory_write_allowed": False,
            "rtl_patch_included": False,
            "read_only_tb_probe_included": True,
            "tb_probe_transactional_restore_required": True,
        },
        "compile_integration_repair": {
            "replaces_package": "requant_node0001_e4_stockrtl_v1",
            "v1_failure_classification": "FIRST_DYNAMIC_FAILURE",
            "v1_earliest_failure": (
                "VCS SFCOR: native_return_observer.svh unresolved before simulation"
            ),
            "explicit_vcs_include_directory_via_make": True,
            "precompile_observer_byte_identity_gate": True,
            "workload_semantics_changed": False,
            "functional_rtl_modified": False,
        },
        "return_policy": {
            "allowlist_only": True,
            "raw_large_evidence_in_return": False,
            "waveforms": False,
            "build_tree": False,
            "nested_archives": False,
            "return_zip_limit_bytes": 6 * 1024 * 1024,
        },
        "rule_ids": list(RULE_IDS),
        "release_gate": {
            "e4_only": True,
            "e5_generation_allowed_before_accepted_e4": False,
            "remaining_blocker_before_run": "B_REQUANT_SERVER_E4_E5",
        },
        "files": files,
        "payload_tree_sha256": _tree_sha256(files),
    }
    _write_json(package / MANIFEST_NAME, manifest)
    preflight = preflight_package(package, INSTALL_NAME)
    zip_path, zip_sha = _zip_tree(package)
    return {
        "package": package.as_posix(),
        "manifest": (package / MANIFEST_NAME).as_posix(),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "sidecar": zip_path.with_suffix(".zip.sha256").as_posix(),
        "payload_tree_sha256": manifest["payload_tree_sha256"],
        "preflight": preflight,
    }


def validate_package(package: Path) -> dict[str, Any]:
    root = package.resolve()
    report = preflight_package(root, INSTALL_NAME)
    zip_path = root.with_suffix(".zip")
    sidecar = zip_path.with_suffix(".zip.sha256")
    if not zip_path.is_file() or not sidecar.is_file():
        raise RequantPackageError("ZIP or sidecar is missing")
    digest = _sha256(zip_path)
    if sidecar.read_text(encoding="ascii") != f"{digest}  {zip_path.name}\n":
        raise RequantPackageError("ZIP sidecar differs")
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        expected = [
            f"{root.name}/{path.relative_to(root).as_posix()}"
            for path in sorted(item for item in root.rglob("*") if item.is_file())
        ]
        if names != expected:
            raise RequantPackageError("ZIP exact file set/order differs")
        for name, expected_name in zip(names, expected):
            if name != expected_name:
                raise RequantPackageError("ZIP entry differs")
            local = root / PurePathCompat(name[len(root.name) + 1 :]).value
            if archive.read(name) != local.read_bytes():
                raise RequantPackageError(f"ZIP payload differs: {name}")
    return {
        **report,
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": sidecar.as_posix(),
        "zip_exact_set": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        report = (
            validate_package(args.output)
            if args.validate_only
            else build_package(args.output)
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Requant node0001 package build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
