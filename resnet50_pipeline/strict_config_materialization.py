from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_adjudication import (
    normalize_known_legacy_expressions,
    normalization_adjudication,
    run_native_changed_field_probe,
)
from .operator_config_validator import OperatorConfigValidator, TargetProfile


SCHEMA = "operator-config-strict-materialization-v1"


class StrictConfigMaterializationError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StrictConfigMaterializationError(f"JSON root must be an object: {path}")
    return value


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def materialize_strict_config(
    *,
    project_root: Path,
    ndp_sim_root: Path,
    source_path: Path,
    output_root: Path,
    python_executable: Path,
    expected_source_sha256: str,
    operator_padding_contract_path: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    source = source_path.resolve()
    output = output_root.resolve()
    if output.exists():
        raise StrictConfigMaterializationError(f"output must be a fresh path: {output}")
    if not source.is_file():
        raise StrictConfigMaterializationError(f"source config is missing: {source}")
    source_sha256 = sha256_file(source)
    if source_sha256 != expected_source_sha256:
        raise StrictConfigMaterializationError(
            f"source config hash differs: {source_sha256} != {expected_source_sha256}"
        )
    original = _load(source)
    normalized, changes = normalize_known_legacy_expressions(original)
    if not changes:
        raise StrictConfigMaterializationError("source config needs no approved normalization")
    report = OperatorConfigValidator().validate(normalized, source=str(source))
    if not report.valid:
        first = report.issues[0]
        raise StrictConfigMaterializationError(
            f"normalized config remains invalid: {first.code} at {first.path}"
        )

    output.mkdir(parents=True)
    normalized_path = output / "config.json"
    normalized_path.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    probe = run_native_changed_field_probe(
        ndp_sim_root=ndp_sim_root,
        original_path=source,
        normalized_path=normalized_path,
        changes=changes,
        python_executable=python_executable,
    )
    field_equivalent = bool(
        probe.returncode == 0
        and isinstance(probe.proof, Mapping)
        and probe.proof.get("all_equivalent") is True
    )
    padding_contract: dict[str, Any] | None = None
    if any(change.kind == "explicit_zero_padding" for change in changes):
        if operator_padding_contract_path is None:
            raise StrictConfigMaterializationError(
                "explicit zero padding requires a hash-bound operator padding contract"
            )
        from .operator_padding_contract import (
            validate_operator_padding_contract,
        )

        contract_path = operator_padding_contract_path.resolve()
        padding_contract = validate_operator_padding_contract(
            root, contract_path
        )
        authorization = padding_contract["authorization"]
        if (
            authorization.get("source_sha256") != source_sha256
            or authorization.get("normalized_canonical_sha256")
            != sha256_bytes(canonical_json_bytes(normalized))
            or authorization.get("json_path")
            != "$.stream_engine.stream0.padding_reg_value"
            or authorization.get("after") != 0
        ):
            raise StrictConfigMaterializationError(
                "operator padding contract does not authorize this normalization"
            )
    decision = normalization_adjudication(
        changes,
        field_encoding_equivalent=field_equivalent,
        padding_contract_validated=padding_contract is not None,
    )
    if not decision["normalization_decision"].startswith("approved-"):
        raise StrictConfigMaterializationError(
            "normalization is not approved: " + decision["normalization_decision"]
        )

    change_records = [asdict(change) for change in changes]
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "strict_config_materialized_from_bit_equivalent_cleanup",
        "source": {
            "path": _relative_or_absolute(source, root),
            "sha256": source_sha256,
            "read_only": True,
        },
        "normalized": {
            "path": "config.json",
            "sha256": sha256_file(normalized_path),
            "canonical_sha256": sha256_bytes(canonical_json_bytes(normalized)),
        },
        "changes": change_records,
        "change_set_sha256": sha256_bytes(canonical_json_bytes(change_records)),
        "strict_validation": {
            "valid": True,
            "issue_count": 0,
            "target_profile": asdict(TargetProfile()),
        },
        "native_field_probe": {
            "returncode": probe.returncode,
            "command": probe.command,
            "stdout_sha256": probe.stdout_sha256,
            "stderr_sha256": probe.stderr_sha256,
            "proof_sha256": probe.proof_sha256,
            "proof": probe.proof,
            "all_equivalent": field_equivalent,
        },
        "adjudication": decision,
        "operator_padding_contract": (
            {
                "path": _relative_or_absolute(
                    operator_padding_contract_path.resolve(), root
                ),
                "sha256": sha256_file(operator_padding_contract_path.resolve()),
                "contract_sha256": padding_contract["contract_sha256"],
            }
            if padding_contract is not None
            and operator_padding_contract_path is not None
            else None
        ),
        "source_rewrite_performed": False,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    validate_materialized_strict_config(output)
    return manifest


def validate_materialized_strict_config(output_root: Path) -> dict[str, Any]:
    output = output_root.resolve()
    manifest = _load(output / "manifest.json")
    config = _load(output / "config.json")
    if manifest.get("schema") != SCHEMA:
        raise StrictConfigMaterializationError("strict materialization schema differs")
    normalized = manifest.get("normalized")
    if (
        not isinstance(normalized, Mapping)
        or normalized.get("path") != "config.json"
        or normalized.get("sha256") != sha256_file(output / "config.json")
        or normalized.get("canonical_sha256")
        != sha256_bytes(canonical_json_bytes(config))
    ):
        raise StrictConfigMaterializationError("normalized config identity differs")
    report = OperatorConfigValidator().validate(config, source=str(output / "config.json"))
    if not report.valid:
        first = report.issues[0]
        raise StrictConfigMaterializationError(
            f"materialized config is invalid: {first.code} at {first.path}"
        )
    changes = manifest.get("changes")
    probe = manifest.get("native_field_probe")
    adjudication = manifest.get("adjudication")
    contract_binding = manifest.get("operator_padding_contract")
    padding_changes = [
        item for item in changes or [] if item.get("kind") == "explicit_zero_padding"
    ]
    if padding_changes:
        if not isinstance(contract_binding, Mapping):
            raise StrictConfigMaterializationError(
                "strict padding materialization lacks its operator contract"
            )
        from .operator_padding_contract import (
            validate_operator_padding_contract,
        )

        project_root = Path(__file__).resolve().parents[1]
        contract_path = project_root / str(contract_binding.get("path"))
        contract = validate_operator_padding_contract(
            project_root, contract_path
        )
        if (
            contract_binding.get("sha256") != sha256_file(contract_path)
            or contract_binding.get("contract_sha256")
            != contract.get("contract_sha256")
            or contract["authorization"].get("normalized_canonical_sha256")
            != sha256_bytes(canonical_json_bytes(config))
        ):
            raise StrictConfigMaterializationError(
                "strict padding materialization contract identity differs"
            )
    elif contract_binding is not None:
        raise StrictConfigMaterializationError(
            "non-padding strict materialization must not bind a padding contract"
        )
    if (
        not isinstance(changes, list)
        or not changes
        or manifest.get("change_set_sha256")
        != sha256_bytes(canonical_json_bytes(changes))
        or not isinstance(probe, Mapping)
        or probe.get("returncode") != 0
        or probe.get("all_equivalent") is not True
        or not isinstance(probe.get("proof"), Mapping)
        or probe["proof"].get("all_equivalent") is not True
        or not isinstance(adjudication, Mapping)
        or not str(adjudication.get("normalization_decision", "")).startswith(
            "approved-"
        )
        or manifest.get("source_rewrite_performed") is not False
    ):
        raise StrictConfigMaterializationError(
            "strict materialization equivalence/adjudication differs"
        )
    return manifest


__all__ = [
    "SCHEMA",
    "StrictConfigMaterializationError",
    "materialize_strict_config",
    "validate_materialized_strict_config",
]
