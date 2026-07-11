from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .manifest import ArtifactRecord


class ArtifactManager:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"artifact path escapes root: {relative_path}")
        return target

    def write_bytes(self, relative_path: str, data: bytes) -> ArtifactRecord:
        target = self._target(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return ArtifactRecord(
            path=str(target.relative_to(self.root)).replace("\\", "/"),
            sha256=sha256_bytes(data),
            size_bytes=len(data),
        )

    def write_json(self, relative_path: str, value: Any) -> ArtifactRecord:
        return self.write_bytes(relative_path, canonical_json_bytes(value) + b"\n")

    def verify(self, record: ArtifactRecord) -> bool:
        target = self._target(record.path)
        return (
            target.is_file()
            and target.stat().st_size == record.size_bytes
            and sha256_file(target) == record.sha256
        )
