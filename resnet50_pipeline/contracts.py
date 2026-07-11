from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ContractError
from .hashing import combined_hash, sha256_file

ALLOWED_CONTRACT_STATUSES = {
    "candidate",
    "provisionally_approved",
    "approved",
    "approved_for_w0_only",
}


@dataclass(frozen=True)
class ContractSet:
    documents: dict[str, dict[str, Any]]
    hashes: dict[str, str]

    @property
    def digest(self) -> str:
        return combined_hash(f"{name}:{self.hashes[name]}" for name in sorted(self.hashes))


def load_contracts(root: Path) -> ContractSet:
    required = ("architecture", "quantization", "backend")
    documents: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for name in required:
        path = root / f"{name}.json"
        if not path.is_file():
            raise ContractError(f"missing required contract: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != "0.1":
            raise ContractError(f"unsupported contract schema in {path}")
        if value.get("contract_type") != name:
            raise ContractError(f"contract_type mismatch in {path}")
        if value.get("status") not in ALLOWED_CONTRACT_STATUSES:
            raise ContractError(f"invalid contract status in {path}")
        documents[name] = value
        hashes[name] = sha256_file(path)
    return ContractSet(documents=documents, hashes=hashes)
