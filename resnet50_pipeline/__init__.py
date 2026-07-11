"""Root integration layer for the ResNet50 INT8 validation workflow."""

from .manifest import MANIFEST_SCHEMA_VERSION, RunManifest, StageAttempt

__all__ = ["MANIFEST_SCHEMA_VERSION", "RunManifest", "StageAttempt"]
__version__ = "0.1.0"
