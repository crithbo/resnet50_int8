from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class OperatorPaddingContractError(ValueError):
    pass


def validate_operator_padding_contract(
    project_root: Path, contract_path: Path
) -> dict[str, Any]:
    try:
        value = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OperatorPaddingContractError(
            f"cannot parse operator padding contract: {contract_path}"
        ) from error
    if not isinstance(value, dict):
        raise OperatorPaddingContractError(
            "operator padding contract root must be an object"
        )
    schema = value.get("schema")
    if schema == "maxpool-uint8-zero-padding-contract-v1":
        from .maxpool_padding_contract import (
            validate_maxpool_zero_padding_contract,
        )

        return validate_maxpool_zero_padding_contract(
            project_root, contract_path
        )
    if schema == "gap-sum-uint8-zero-padding-contract-v1":
        from .gap_sum_padding_contract import (
            validate_gap_sum_zero_padding_contract,
        )

        return validate_gap_sum_zero_padding_contract(
            project_root, contract_path
        )
    raise OperatorPaddingContractError(
        f"unsupported operator padding contract schema: {schema}"
    )


__all__ = [
    "OperatorPaddingContractError",
    "validate_operator_padding_contract",
]
