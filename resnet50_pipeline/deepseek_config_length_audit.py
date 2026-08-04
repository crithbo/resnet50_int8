from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndp_config_length import (
    NdpConfigLengthError,
    analyze_config_length,
    parse_load_config_length,
)


CONTRACT_PATH = (
    "contracts/operator_config/deepseek_config_length_audit_v1.json"
)
RULE_PATH = ".agents/rules/DeepSeek_码流生命周期增量规则.md"
FAMILY_OUTPUTS = {
    "silu": (
        "artifacts/operator_config_validation/ds_silu_v6/"
        "a/t/model_execplan/output/ds_silu_v6"
    ),
    "rmsnorm": (
        "artifacts/operator_config_validation/ds_rms_v1/"
        "a/t/model_execplan/output/ds_rms_v1"
    ),
    "rope": (
        "artifacts/operator_config_validation/ds_rope_v1/"
        "a/t/model_execplan/output/ds_rope_v1"
    ),
    "softmax": (
        "artifacts/operator_config_validation/ds_softmax_v1/"
        "a/t/model_execplan/output/ds_softmax_v1"
    ),
    "gemm": (
        "artifacts/operator_config_validation/ds_gemm_ffn_gate_v1/"
        "a/t/model_execplan/output/ds_gemm_ffn_gate_v1"
    ),
    "gemv": (
        "artifacts/operator_config_validation/ds_gemv_ffn_gate_v1/"
        "a/t/model_execplan/output/ds_gemv_ffn_gate_v1"
    ),
}
EXPECTED_OPERATOR_COUNTS = {
    "silu": 1,
    "rmsnorm": 5,
    "rope": 3,
    "softmax": 5,
    "gemm": 1,
    "gemv": 1,
}
BLOCKER_IDS = {
    "rmsnorm": "B_DS_RMSNORM_CONFIG_LENGTH_SOURCE_DIVERGENCE",
    "rope": "B_DS_ROPE_CONFIG_LENGTH_SOURCE_DIVERGENCE",
    "softmax": "B_DS_SOFTMAX_CONFIG_LENGTH_SOURCE_DIVERGENCE",
    "gemm": "B_DS_GEMM_CONFIG_LENGTH_ORACLE_DIVERGENCE",
}


class DeepSeekConfigLengthAuditError(ValueError):
    pass


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekConfigLengthAuditError(
            f"required config-length evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _single(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise DeepSeekConfigLengthAuditError(
            f"expected one {pattern} under {directory}, found {len(matches)}"
        )
    return matches[0]


def _audit_family(
    root: Path, family: str, output_relative: str
) -> dict[str, Any]:
    output = root / output_relative
    explained = output / "instructions_explained.txt"
    config_root = output / "config"
    op_dirs = sorted(
        path
        for path in config_root.glob("op*")
        if path.is_dir()
    )
    expected_count = EXPECTED_OPERATOR_COUNTS[family]
    if len(op_dirs) != expected_count:
        raise DeepSeekConfigLengthAuditError(
            f"{family} expected {expected_count} config operators, "
            f"found {len(op_dirs)}"
        )
    operators: dict[str, Any] = {}
    for op_dir in op_dirs:
        op_id = op_dir.name
        bitstream_64b = _single(op_dir, "*bitstream_64b.bin")
        bitstream_128b = _single(op_dir, "*bitstream_128b.bin")
        try:
            programmed = parse_load_config_length(explained, op_id)
            analysis = analyze_config_length(
                bitstream_64b,
                bitstream_128b,
                programmed,
            )
        except NdpConfigLengthError as error:
            raise DeepSeekConfigLengthAuditError(
                f"{family}/{op_id} config-length audit failed: {error}"
            ) from error
        installed = output / "install/cfg_pkg" / bitstream_128b.name
        installed_present = installed.is_file()
        installed_matches = (
            installed.read_bytes() == bitstream_128b.read_bytes()
            if installed_present
            else None
        )
        if installed_present and not installed_matches:
            raise DeepSeekConfigLengthAuditError(
                f"{family}/{op_id} installed 128-bit config differs"
            )
        operators[op_id] = {
            "status": (
                "CLOSED"
                if analysis["matches_rtl_padding_contract"]
                else "OPEN"
            ),
            "programmed_minus_source_words": (
                programmed - analysis["source_64bit_word_count"]
            ),
            "analysis": analysis,
            "source_64b": _binding(
                root, bitstream_64b.relative_to(root).as_posix()
            ),
            "transport_128b": _binding(
                root, bitstream_128b.relative_to(root).as_posix()
            ),
            "installed_128b_present": installed_present,
            "installed_128b_matches_transport": installed_matches,
        }
    open_ops = [
        op_id
        for op_id, value in operators.items()
        if value["status"] == "OPEN"
    ]
    return {
        "status": "OPEN" if open_ops else "CLOSED",
        "output_root": output_relative,
        "instructions_explained": _binding(
            root, explained.relative_to(root).as_posix()
        ),
        "operator_count": len(operators),
        "open_operator_ids": open_ops,
        "operators": operators,
    }


def build_deepseek_config_length_audit(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    families = {
        family: _audit_family(root, family, output)
        for family, output in FAMILY_OUTPUTS.items()
    }
    blockers = []
    for family, value in families.items():
        if value["status"] == "CLOSED":
            continue
        blocker_id = BLOCKER_IDS.get(family)
        if blocker_id is None:
            raise DeepSeekConfigLengthAuditError(
                f"unexpected config-length blocker family: {family}"
            )
        blockers.append(
            {
                "id": blocker_id,
                "class": "EXECPLAN_LIFECYCLE",
                "status": "OPEN",
                "family": family,
                "operator_ids": value["open_operator_ids"],
                "reason": (
                    "execplan Load_Config uses physical 128-bit transport "
                    "slots instead of the generated 64-bit source-word count"
                ),
            }
        )
    operator_count = sum(
        value["operator_count"] for value in families.values()
    )
    open_operator_count = sum(
        len(value["open_operator_ids"]) for value in families.values()
    )
    payload: dict[str, Any] = {
        "schema": "deepseek-config-length-audit-v1",
        "status": (
            "LOCAL_E2_CONFIG_LENGTH_PARTIALLY_BLOCKED"
            if blockers
            else "LOCAL_E2_CONFIG_LENGTH_CLOSED"
        ),
        "candidate_release": False,
        "formal_target_config": False,
        "server_package_generated": False,
        "identity_boundary": {
            "onnx_repository_classification": "SEMANTIC_MODEL_MATCH",
            "original_source_identity": False,
            "direct_onnx_shape_equals_stage": False,
            "crop_contract_required": True,
        },
        "rule": _binding(root, RULE_PATH),
        "consumer_equations": {
            "generator": (
                "bitstream/parse.py writes the continuous bit string "
                "independently as 64-bit words and reordered 128-bit rows"
            ),
            "execplan": (
                "Load_Config.config_length is measured in 64-bit words"
            ),
            "rtl": (
                "global_config_manager suppresses the final high half only "
                "when the programmed 64-bit length is odd"
            ),
            "acceptance": (
                "programmed length == 64-bit source line count and exact "
                "64b-to-128b reordered repacking"
            ),
        },
        "summary": {
            "family_count": len(families),
            "operator_count": operator_count,
            "closed_operator_count": operator_count - open_operator_count,
            "open_operator_count": open_operator_count,
            "closed_families": sorted(
                name
                for name, value in families.items()
                if value["status"] == "CLOSED"
            ),
            "open_families": sorted(
                name
                for name, value in families.items()
                if value["status"] == "OPEN"
            ),
        },
        "families": families,
        "blockers": blockers,
        "rule_ids": [
            "CDA-DEEPSEEK-CONFIG-LENGTH-PADDING-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_deepseek_config_length_audit(
    value: Mapping[str, Any], project_root: Path
) -> None:
    rebuilt = build_deepseek_config_length_audit(project_root)
    if value != rebuilt:
        raise DeepSeekConfigLengthAuditError(
            "DeepSeek config-length audit differs from current evidence"
        )


def load_deepseek_config_length_audit(
    project_root: Path,
) -> dict[str, Any]:
    path = project_root.resolve() / CONTRACT_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekConfigLengthAuditError(
            f"cannot load DeepSeek config-length audit: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekConfigLengthAuditError(
            "DeepSeek config-length audit must be a JSON object"
        )
    return value


__all__ = [
    "CONTRACT_PATH",
    "DeepSeekConfigLengthAuditError",
    "build_deepseek_config_length_audit",
    "load_deepseek_config_length_audit",
    "validate_deepseek_config_length_audit",
]
