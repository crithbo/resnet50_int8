from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .errors import ManifestVersionError
from .records import ObjectManifest

MANIFEST_SCHEMA_VERSION = "0.1"
RUN_STATUSES = {"pending", "running", "succeeded", "failed", "blocked"}
STAGE_STATUSES = RUN_STATUSES | {"skipped"}


@dataclass
class ArtifactRecord:
    path: str
    sha256: str
    size_bytes: int


@dataclass
class StageAttempt:
    name: str
    attempt: int = 1
    status: str = "pending"
    started_at: str | None = None
    finished_at: str | None = None
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    error: str | None = None

    def validate(self) -> None:
        if self.status not in STAGE_STATUSES:
            raise ValueError(f"invalid stage status: {self.status}")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")


@dataclass
class RunManifest:
    run_id: str
    created_at: str
    status: str
    cache_key: str
    environment: dict[str, Any]
    inputs: dict[str, Any]
    contracts: dict[str, Any]
    repositories: dict[str, Any]
    objects: ObjectManifest
    stages: list[StageAttempt]
    schema_version: str = MANIFEST_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise ManifestVersionError(
                f"unsupported manifest schema {self.schema_version!r}; "
                f"expected {MANIFEST_SCHEMA_VERSION!r}"
            )
        if self.status not in RUN_STATUSES:
            raise ValueError(f"invalid run status: {self.status}")
        if len(self.cache_key) != 64:
            raise ValueError("cache_key must be a SHA-256 hex digest")
        names = [stage.name for stage in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("stage names must be unique within one attempt")
        for stage in self.stages:
            stage.validate()
        self.objects.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["objects"] = self.objects.to_dict()
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RunManifest":
        version = value.get("schema_version")
        if version != MANIFEST_SCHEMA_VERSION:
            raise ManifestVersionError(
                f"no migration registered from schema {version!r} "
                f"to {MANIFEST_SCHEMA_VERSION!r}"
            )
        decoded = dict(value)
        decoded["objects"] = ObjectManifest.from_dict(value["objects"])
        decoded["stages"] = [
            StageAttempt(
                **{
                    **stage,
                    "artifacts": [ArtifactRecord(**item) for item in stage["artifacts"]],
                }
            )
            for stage in value["stages"]
        ]
        manifest = cls(**decoded)
        manifest.validate()
        return manifest

    @classmethod
    def load(cls, path: Path) -> "RunManifest":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
