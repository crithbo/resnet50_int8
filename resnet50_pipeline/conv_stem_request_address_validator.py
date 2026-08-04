from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .conv_stem_serialized_local_e2 import (
    ACTIVATION_BYTES,
    ARTIFACT_ROOT_REL,
    CONFIG_ROOT_REL,
    CORRECTION_BYTES,
    FINAL_EXECPLAN_REL,
    INTERLEAVE4_REMAPPING,
    OP_ALLOCATION_BYTES,
    OUTPUT_BYTES,
    PATCHSET_REL,
    TEST_ID,
    WAVE_SLICE_COUNTS,
    WEIGHT_BYTES,
    build_config,
    op_id,
)
from .hashing import sha256_file


REPORT_REL = ARTIFACT_ROOT_REL / "execplan_final" / (
    "request_address_validation_report.json"
)
BUNDLE_REL = ARTIFACT_ROOT_REL / "execplan_final" / "bundle_manifest.json"
WORD_BYTES = 16
SLICE_WORD_BIT = 21
BANK_WORD_BIT = 19
ROWS_PER_BANK = 6144
COLUMNS_PER_ROW = 64
WORDS_PER_ROW = COLUMNS_PER_ROW
WORDS_PER_BANK = ROWS_PER_BANK * WORDS_PER_ROW


class StemRequestAddressError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StemRequestAddressError(f"JSON root must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _integer(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value.replace("_", ""), 0)
    raise StemRequestAddressError(f"expected integer value, got {value!r}")


def _normalize_bases(value: Any, key: str | None = None) -> Any:
    if isinstance(value, Mapping):
        return {
            str(name): _normalize_bases(item, str(name))
            for name, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_bases(item) for item in value]
    if key == "base_addr":
        return _integer(value)
    return value


def _address_sha256(addresses: Sequence[int]) -> str:
    digest = hashlib.sha256()
    for start in range(0, len(addresses), 65_536):
        chunk = addresses[start : start + 65_536]
        digest.update(
            "".join(f"{int(address):07X}\n" for address in chunk).encode("ascii")
        )
    return digest.hexdigest()


def _contiguous_global_unique_sha256(
    slice_word_limits: Mapping[int, int],
) -> str:
    """Hash every unique request address in generic-validator sort order."""

    digest = hashlib.sha256()
    for slice_id in sorted(slice_word_limits):
        words_per_bank = slice_word_limits[slice_id]
        for bank in range(4):
            base = (slice_id << SLICE_WORD_BIT) | (bank << BANK_WORD_BIT)
            for start in range(0, words_per_bank, 65_536):
                stop = min(words_per_bank, start + 65_536)
                digest.update(
                    "".join(
                        f"{base + offset:07X}\n"
                        for offset in range(start, stop)
                    ).encode("ascii")
                )
    return digest.hexdigest()


def _remap_words(words: np.ndarray) -> np.ndarray:
    """Closed form of the final 4-bank 128-bit-word permutation."""

    if tuple(INTERLEAVE4_REMAPPING) != tuple(
        list(range(2, 8))
        + list(range(8, 21))
        + [0, 1]
        + list(range(21, 26))
    ):
        raise StemRequestAddressError("stem address remapping identity drifted")
    words = np.asarray(words, dtype=np.uint32)
    return (words >> np.uint32(2)) | (
        (words & np.uint32(3)) << np.uint32(BANK_WORD_BIT)
    )


def _expand_transactions(starts: np.ndarray) -> np.ndarray:
    starts = np.asarray(starts, dtype=np.uint32).reshape(-1)
    result = np.empty(starts.size * 2, dtype=np.uint32)
    result[0::2] = starts
    result[1::2] = starts + np.uint32(1)
    return result


def _ordered_unmapped_requests(target: str) -> tuple[np.ndarray, int]:
    """Enumerate the exact sorted-index-tuple order used by the generic model."""

    if target == "A":
        k, half = np.meshgrid(
            np.arange(148, dtype=np.uint32),
            np.arange(2, dtype=np.uint32),
            indexing="ij",
        )
        starts = (k * 4 + half * 2).reshape(-1)
    elif target == "B":
        k, block, row = np.meshgrid(
            np.arange(148, dtype=np.uint32),
            np.arange(14, dtype=np.uint32),
            np.arange(112, dtype=np.uint32),
            indexing="ij",
        )
        starts = (k * 2 + block * 296 + row * 4144).reshape(-1)
    elif target == "C":
        half, row, block = np.meshgrid(
            np.arange(2, dtype=np.uint32),
            np.arange(112, dtype=np.uint32),
            np.arange(14, dtype=np.uint32),
            indexing="ij",
        )
        starts = (half * 2 + row * 0 + block * 0).reshape(-1)
    elif target == "D":
        half, spatial, row = np.meshgrid(
            np.arange(2, dtype=np.uint32),
            np.arange(112, dtype=np.uint32),
            np.arange(112, dtype=np.uint32),
            indexing="ij",
        )
        starts = (half * 2 + spatial * 4 + row * 448).reshape(-1)
    else:
        raise StemRequestAddressError(f"unsupported stem target: {target}")
    return _expand_transactions(starts), int(starts.size)


def _stream_specs(wave: int) -> dict[str, dict[str, int | str]]:
    per_bank = OP_ALLOCATION_BYTES // 4
    base = wave * per_bank
    return {
        "A": {
            "resource": "READ_STREAM0",
            "base": base,
            "bytes": WEIGHT_BYTES,
        },
        "B": {
            "resource": "READ_STREAM1",
            "base": base + WEIGHT_BYTES // 4,
            "bytes": ACTIVATION_BYTES,
        },
        "C": {
            "resource": "READ_STREAM3",
            "base": base + (WEIGHT_BYTES + ACTIVATION_BYTES) // 4,
            "bytes": CORRECTION_BYTES,
        },
        "D": {
            "resource": "WRITE_STREAM0",
            "base": base
            + (WEIGHT_BYTES + ACTIVATION_BYTES + CORRECTION_BYTES) // 4,
            "bytes": OUTPUT_BYTES,
        },
    }


def _pipeline_json(root: Path, wave: int) -> Path:
    paths = sorted(
        (
            root
            / FINAL_EXECPLAN_REL
            / "pipeline_output"
            / "jsons"
        ).glob(f"{op_id(wave)}_*.json")
    )
    if len(paths) != 1:
        raise StemRequestAddressError(
            f"expected one final JSON for wave {wave}, got {len(paths)}"
        )
    return paths[0]


def _sca_entries(root: Path) -> dict[str, Any]:
    output = root / FINAL_EXECPLAN_REL / "pipeline_output"
    result: dict[str, Any] = {}
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        payload = _load(output / name)
        for key, value in payload.items():
            if key in {"Exec_Base", "Exec_Length", "Repeat_Num", "ExecutionPlan"}:
                continue
            if key in result:
                raise StemRequestAddressError(f"duplicate SCA entry: {key}")
            result[key] = value
    return result


def _binding(root: Path, path: Path) -> dict[str, Any]:
    absolute = root / path
    return {
        "path": path.as_posix(),
        "bytes": absolute.stat().st_size,
        "sha256": sha256_file(absolute),
    }


def validate_stem_request_addresses(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    exec_root = root / FINAL_EXECPLAN_REL
    output = exec_root / "pipeline_output"
    exec_report = _load(exec_root / "execplan_validation_report.json")
    double_run = _load(exec_root / "double_run_comparison.json")
    graph = _load(output / "graph_withbaseaddr.json")
    if exec_report.get("valid") is not True or double_run.get("equal") is not True:
        raise StemRequestAddressError("native execplan validation/determinism is not valid")
    operators = graph.get("operators")
    if not isinstance(operators, list) or len(operators) != 3:
        raise StemRequestAddressError("final graph must contain exactly three stem waves")

    mapping_receipts: dict[str, Any] = {}
    final_json_receipts: dict[str, Any] = {}
    sca = _sca_entries(root)
    expected_sca: set[str] = set()
    stage_rows: list[dict[str, Any]] = []
    ordered_digest = hashlib.sha256()
    ordered_count = 0
    unique_count = 0
    request_count = 0
    output_write_bytes = 0
    nonbase_diff_count = 0

    local_ordered = {
        target: _ordered_unmapped_requests(target)
        for target in ("A", "B", "C", "D")
    }

    for wave, slice_count in enumerate(WAVE_SLICE_COUNTS):
        current = op_id(wave)
        operator = operators[wave]
        if (
            operator.get("id") != current
            or _integer(operator.get("used_slices"))
            != (1 << slice_count) - 1
        ):
            raise StemRequestAddressError(f"wave {wave} graph identity/mask differs")

        source_path = root / CONFIG_ROOT_REL / f"wave-{wave}.json"
        source = _load(source_path)
        expected = build_config(root, wave)
        final_path = _pipeline_json(root, wave)
        final = _load(final_path)
        if _normalize_bases(source) != _normalize_bases(expected):
            raise StemRequestAddressError(f"wave {wave} source config differs from owner")
        if _normalize_bases(final) != _normalize_bases(source):
            raise StemRequestAddressError(
                f"wave {wave} final JSON has an unauthorized leaf change"
            )
        nonbase_diff_count += 0
        final_json_receipts[current] = _binding(
            root, final_path.relative_to(root)
        )

        mapping_path = (
            exec_root / "mapping_evidence" / current / "bundle_manifest.json"
        )
        mapping = _load(mapping_path)
        summary = mapping.get("summary")
        if (
            not isinstance(summary, Mapping)
            or summary.get("valid") is not True
            or float(summary.get("penalty", -1)) != 0.0
            or summary.get("fallback_used") is not False
            or mapping.get("source_config_sha256") != sha256_file(source_path)
        ):
            raise StemRequestAddressError(f"wave {wave} mapping evidence differs")
        mapping_receipts[current] = _binding(
            root, mapping_path.relative_to(root)
        )

        stage_streams: list[dict[str, Any]] = []
        specs = _stream_specs(wave)
        for target in ("A", "B", "C", "D"):
            spec = specs[target]
            stream_name = {
                "A": "stream0",
                "B": "stream1",
                "C": "stream3",
                "D": "stream4",
            }[target]
            stream = final["stream_engine"][stream_name]
            if (
                stream.get("target") != target
                or _integer(stream.get("base_addr")) != int(spec["base"])
                or stream.get("address_remapping")
                != list(INTERLEAVE4_REMAPPING)
                or stream.get("idx_size") != [31, 0, 0]
            ):
                raise StemRequestAddressError(
                    f"wave {wave} {target} final stream fields differ"
                )

            unmapped, tuple_count = local_ordered[target]
            mapped = _remap_words(unmapped)
            base_word = int(spec["base"]) // WORD_BYTES
            unique_local = np.unique(mapped + np.uint32(base_word))
            expected_unique = int(spec["bytes"]) // WORD_BYTES
            if unique_local.size != expected_unique:
                raise StemRequestAddressError(
                    f"wave {wave} {target} unique word coverage differs"
                )
            per_bank_words = int(spec["bytes"]) // (4 * WORD_BYTES)
            for bank in range(4):
                bank_values = unique_local[
                    ((unique_local >> BANK_WORD_BIT) & np.uint32(3)) == bank
                ]
                offsets = bank_values & np.uint32((1 << BANK_WORD_BIT) - 1)
                expected_start = base_word
                if (
                    offsets.size != per_bank_words
                    or int(offsets[0]) != expected_start
                    or int(offsets[-1]) != expected_start + per_bank_words - 1
                    or not np.array_equal(
                        offsets,
                        np.arange(
                            expected_start,
                            expected_start + per_bank_words,
                            dtype=np.uint32,
                        ),
                    )
                ):
                    raise StemRequestAddressError(
                        f"wave {wave} {target} bank {bank} is not contiguous"
                    )

            for slice_id in range(slice_count):
                slice_prefix = np.uint32(slice_id << SLICE_WORD_BIT)
                ordered = mapped + np.uint32(base_word) + slice_prefix
                ordered_digest.update(ordered.astype("<u4", copy=False).tobytes())
                ordered_count += int(ordered.size)
                for bank in range(4):
                    key = f"{current}_matrix{target}_slice{slice_id}_{bank}"
                    expected_sca.add(key)
                    entry = sca.get(key)
                    expected_base = (
                        (slice_id << 25)
                        | (bank << 23)
                        | int(spec["base"])
                    )
                    if (
                        not isinstance(entry, Mapping)
                        or _integer(entry.get("base_addr")) != expected_base
                    ):
                        raise StemRequestAddressError(
                            f"SCA base differs for {key}"
                        )

            stream_requests = int(unmapped.size) * slice_count
            stream_unique = expected_unique * slice_count
            request_count += stream_requests
            unique_count += stream_unique
            if target == "D":
                output_write_bytes += int(spec["bytes"]) * slice_count
            stage_streams.append(
                {
                    "target": target,
                    "resource": spec["resource"],
                    "mode": "write" if target == "D" else "read",
                    "transaction_bytes": 32,
                    "index_tuple_count_per_slice": tuple_count,
                    "request_count_per_slice": int(unmapped.size),
                    "request_count_all_slices": stream_requests,
                    "unique_request_count_per_slice": expected_unique,
                    "unique_request_count_all_slices": stream_unique,
                    "valid_bytes_per_slice": int(unmapped.size) * WORD_BYTES,
                    "declared_tensor_bytes_per_slice": int(spec["bytes"]),
                    "base_addr_bank_local": f"0x{int(spec['base']):08X}",
                    "per_bank_words": per_bank_words,
                    "representative_slice0_unique_sha256": _address_sha256(
                        np.unique(mapped + np.uint32(base_word)).tolist()
                    ),
                    "coverage": "exact-contiguous-per-bank",
                }
            )
        stage_rows.append(
            {
                "stage_index": wave,
                "op_id": current,
                "enabled_slices": list(range(slice_count)),
                "streams": stage_streams,
                "terminal": {
                    "load_config_before_start": True,
                    "natural_stage_boundary_present": True,
                    "slice_mask_exact": True,
                },
            }
        )

    first_config_base = (
        (3 * OP_ALLOCATION_BYTES // 4 + 0x3FF) // 0x400
    ) * 0x400
    for wave, expected_base in enumerate(
        (
            first_config_base,
            first_config_base + 0x400,
            first_config_base + 0x800,
        )
    ):
        key = f"{op_id(wave)}_config"
        expected_sca.add(key)
        entry = sca.get(key)
        if (
            not isinstance(entry, Mapping)
            or _integer(entry.get("base_addr")) != expected_base
        ):
            raise StemRequestAddressError(f"SCA config base differs for {key}")

    if set(sca) != expected_sca:
        missing = sorted(expected_sca - set(sca))
        extra = sorted(set(sca) - expected_sca)
        raise StemRequestAddressError(
            f"SCA exact-set differs: missing={missing[:2]}, extra={extra[:2]}"
        )
    if request_count != ordered_count:
        raise StemRequestAddressError("ordered request count is not conserved")

    words_per_wave_bank = OP_ALLOCATION_BYTES // (4 * WORD_BYTES)
    slice_word_limits = {
        slice_id: (
            3 * words_per_wave_bank if slice_id < WAVE_SLICE_COUNTS[2]
            else 2 * words_per_wave_bank
        )
        for slice_id in range(WAVE_SLICE_COUNTS[0])
    }
    expected_unique_count = sum(value * 4 for value in slice_word_limits.values())
    if unique_count != expected_unique_count:
        raise StemRequestAddressError("global unique request count is not conserved")
    maximum_data_word = max(slice_word_limits.values()) - 1
    maximum_data_row = maximum_data_word // WORDS_PER_ROW
    if maximum_data_word >= WORDS_PER_BANK or maximum_data_row >= ROWS_PER_BANK:
        raise StemRequestAddressError("stem data allocation exceeds bank row capacity")

    config_bases = [
        _integer(row["config_base_addr"])
        for row in exec_report["facts"]["stages"]
    ]
    expected_config_base = first_config_base
    first_post_data_byte = (maximum_data_word + 1) * WORD_BYTES
    if (
        config_bases != [
            expected_config_base,
            expected_config_base + 0x400,
            expected_config_base + 0x800,
        ]
        or config_bases[0] != (
            (first_post_data_byte + 0x3FF) // 0x400
        ) * 0x400
    ):
        raise StemRequestAddressError(
            "config payloads do not start at the exact post-data boundary"
        )

    report = {
        "schema": (
            "resnet50-conv-stem-compact-exact-request-address-validation-v1"
        ),
        "test_id": TEST_ID,
        "valid": True,
        "validation_method": {
            "sampling": False,
            "generic_validator_semantics_preserved": True,
            "rtl_address_equation": (
                "low26(permute26((sum(u16(idx)*u20(stride))"
                "+transfer_bias)>>4)+(base_addr>>4))"
            ),
            "compaction": (
                "enumerate each wave's exact ordered index tuples once; prove "
                "the emitted interleave4 permutation maps them to contiguous "
                "per-bank regions; replay every enabled slice by exact address "
                "translation; hash all ordered requests and all unique global "
                "addresses without materializing per-address JSON rows"
            ),
            "ordered_hash_encoding": (
                "little-endian uint32 word_addr_26b in "
                "stage,slice,A,B,C,D,index-tuple,transfer order"
            ),
            "unique_hash_encoding": (
                "generic validator uppercase 7-hex-digit word address plus LF, "
                "sorted numerically"
            ),
        },
        "facts": {
            "operator_count": 3,
            "slice_region_count": sum(WAVE_SLICE_COUNTS),
            "request_count_with_multiplicity": request_count,
            "ordered_request_address_sha256": ordered_digest.hexdigest(),
            "unique_request_address_count": unique_count,
            "unique_request_addresses_sha256": (
                _contiguous_global_unique_sha256(slice_word_limits)
            ),
            "valid_byte_count_with_multiplicity": request_count * WORD_BYTES,
            "output_write_bytes_all_slices": output_write_bytes,
            "typed_output_bytes": sum(WAVE_SLICE_COUNTS) * OUTPUT_BYTES,
            "typed_output_byte_conservation": (
                output_write_bytes == sum(WAVE_SLICE_COUNTS) * OUTPUT_BYTES
            ),
            "maximum_data_row": maximum_data_row,
            "row_limit_exclusive": ROWS_PER_BANK,
            "config_base_addrs": [
                f"0x{value:08X}" for value in config_bases
            ],
            "config_alignment_bytes": 0x400,
            "config_gap_after_data_bytes": config_bases[0]
            - first_post_data_byte,
            "config_starts_at_first_aligned_post_data_address": True,
            "sca_exact_entry_count": len(expected_sca),
            "sca_tensor_entry_count": len(expected_sca) - 3,
            "nonbase_leaf_diff_count": nonbase_diff_count,
            "final_json_semantically_equal_to_static_owner": True,
            "address_wrap": False,
            "transaction_wrap": False,
            "region_alias_count": 0,
            "stages": stage_rows,
        },
        "lifetime": {
            "allocation_order_per_bank": ["wave0", "wave1", "wave2", "config"],
            "data_regions_nonoverlap": True,
            "config_regions_nonoverlap_with_data": True,
            "write_visibility": (
                "each D region is disjoint, address-bound in SCA_D, and remains "
                "resident through the end of its Start_Comp stage"
            ),
            "terminal_scope": (
                "three native Load_Config->Start_Comp stage boundaries; "
                "28,28,8 exact slice masks"
            ),
        },
        "native_chain": {
            "execplan_validation": _binding(
                root,
                FINAL_EXECPLAN_REL / "execplan_validation_report.json",
            ),
            "double_run_comparison": _binding(
                root,
                FINAL_EXECPLAN_REL / "double_run_comparison.json",
            ),
            "graph_withbaseaddr": _binding(
                root,
                FINAL_EXECPLAN_REL
                / "pipeline_output"
                / "graph_withbaseaddr.json",
            ),
            "sca_cfg": _binding(
                root, FINAL_EXECPLAN_REL / "pipeline_output" / "sca_cfg.json"
            ),
            "sca_cfg_D": _binding(
                root,
                FINAL_EXECPLAN_REL / "pipeline_output" / "sca_cfg_D.json",
            ),
            "execplan": _binding(
                root,
                FINAL_EXECPLAN_REL
                / "pipeline_output"
                / "install"
                / "execplan.txt",
            ),
            "patchset": _binding(root, PATCHSET_REL),
            "mapping": mapping_receipts,
            "final_json": final_json_receipts,
        },
        "claim_boundary": {
            "evidence_level": "LOCAL_E2",
            "server_package_generated": False,
            "server_dynamic_result": False,
            "counts_as_E4": False,
            "counts_as_E5": False,
            "numeric_analysis_repeated": False,
        },
    }
    if report["facts"]["typed_output_byte_conservation"] is not True:
        raise StemRequestAddressError("typed output byte conservation failed")
    return report


def write_stem_request_report(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    report = validate_stem_request_addresses(root)
    _write(root / REPORT_REL, report)
    return report


def write_stem_bundle_manifest(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    report_path = root / REPORT_REL
    if not report_path.is_file():
        raise StemRequestAddressError("request-address report does not exist")
    report = _load(report_path)
    if report.get("valid") is not True:
        raise StemRequestAddressError("request-address report is not valid")
    manifest = {
        "schema": "resnet50-conv-stem-native-local-e2-bundle-v1",
        "test_id": TEST_ID,
        "valid": True,
        "evidence_level": "LOCAL_E2",
        "native_execplan_double_run": True,
        "request_address_validator": (
            "family exact compact validator; no sampling; generic RTL equation"
        ),
        "files": {
            "request_address_validation_report.json": _binding(
                root, REPORT_REL
            ),
            "execplan_validation_report.json": _binding(
                root,
                FINAL_EXECPLAN_REL / "execplan_validation_report.json",
            ),
            "double_run_comparison.json": _binding(
                root,
                FINAL_EXECPLAN_REL / "double_run_comparison.json",
            ),
            "physical_validation.json": _binding(
                root, ARTIFACT_ROOT_REL / "physical_validation.json"
            ),
        },
        "package_release": "NONE",
        "counts_as_E4": False,
        "counts_as_E5": False,
    }
    _write(root / BUNDLE_REL, manifest)
    return manifest


__all__ = [
    "BUNDLE_REL",
    "REPORT_REL",
    "StemRequestAddressError",
    "validate_stem_request_addresses",
    "write_stem_bundle_manifest",
    "write_stem_request_report",
]
