class PipelineError(RuntimeError):
    """Base error for an expected pipeline failure."""


class ContractError(PipelineError):
    """A contract is missing, malformed, or not approved for the action."""


class CapabilityError(PipelineError):
    """A backend cannot execute the requested operation."""


class ManifestVersionError(PipelineError):
    """A manifest schema version is unsupported and cannot be migrated."""


class ArtifactError(PipelineError):
    """An artifact is missing or fails integrity validation."""
