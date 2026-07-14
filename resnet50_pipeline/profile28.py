"""Logical batch/profile scheduling contracts for the 28-slice W4 design.

This module deliberately contains no physical slice identifiers or HIGH/LOW
ring maps.  Operator layouts combine these logical assignments with the
separate ``topology28`` contract when physical routing is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from .errors import ContractError


BATCH_SIZE: Final = 16
GROUP_COUNT: Final = 7
GROUP_SAMPLE_COUNTS: Final = (3, 3, 2, 2, 2, 2, 2)

# The two IDs below describe reversible software layout alternatives.  They are
# intentionally retained for W4 regression and cost comparison, but they are
# no longer competing network-wide hardware profiles.

GROUP4X7_BATCH_CHANNEL28_PROFILE: Final = (
    "w4_group4x7_batch_channel28_candidate_v1"
)
GLOBAL_RING28_PROFILE: Final = "w4_global_ring28_candidate_v1"
DEFAULT_PROFILE: Final = GROUP4X7_BATCH_CHANNEL28_PROFILE
SUPPORTED_PROFILES: Final = frozenset(
    {GROUP4X7_BATCH_CHANNEL28_PROFILE, GLOBAL_RING28_PROFILE}
)

# The approved network policy inherits the completed DeepSeek bring-up method:
# one 28-bit all-slice launch can execute seven independent HIGH rings, while
# LOW-28 remains an operator-scoped transport rather than a second whole-network
# layout.  ResNet50 currently needs no LOW-28 family binding.
DEEPSEEK_HYBRID28_PROFILE: Final = "w4_deepseek_hybrid28_resnet50_v1"
DEFAULT_NETWORK_PROFILE: Final = DEEPSEEK_HYBRID28_PROFILE
SUPPORTED_NETWORK_PROFILES: Final = frozenset({DEEPSEEK_HYBRID28_PROFILE})
FULL_SLICE_MASK28: Final = (1 << 28) - 1
OPERATOR_COMMUNICATION_DOMAINS: Final = {
    "simple": "local",
    "view": "local",
    "conv": "high4",
    "maxpool": "local",
    "add": "local",
    "global_average_pool": "local",
    "matmul": "high4",
}
SUPPORTED_COMMUNICATION_DOMAINS: Final = frozenset({"local", "high4", "low28"})

GAP_OPERATOR: Final = "QLinearGlobalAveragePool"
MATMUL_OPERATOR: Final = "QLinearMatMul"


def _require_plain_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{field_name} must be an integer, got {value!r}")
    return value


def _validate_batch_size(batch_size: object) -> int:
    value = _require_plain_int(batch_size, "batch_size")
    if value != BATCH_SIZE:
        raise ContractError(
            f"profile28 supports batch_size={BATCH_SIZE}, got {value}"
        )
    return value


def _group_bounds(group_id: int) -> tuple[int, int]:
    start = sum(GROUP_SAMPLE_COUNTS[:group_id])
    return start, start + GROUP_SAMPLE_COUNTS[group_id]


def _validate_group_id(group_id: object) -> int:
    value = _require_plain_int(group_id, "group_id")
    if not 0 <= value < GROUP_COUNT:
        raise ContractError(
            f"group_id must be in [0, {GROUP_COUNT}), got {value}"
        )
    return value


def _validate_sample_id(sample_id: object) -> int:
    value = _require_plain_int(sample_id, "sample_id")
    if not 0 <= value < BATCH_SIZE:
        raise ContractError(
            f"sample_id must be in [0, {BATCH_SIZE}), got {value}"
        )
    return value


def validate_profile_name(profile: object) -> str:
    """Return a supported candidate name or fail the scheduling contract."""

    if not isinstance(profile, str) or profile not in SUPPORTED_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_PROFILES))
        raise ContractError(
            f"unsupported profile28 candidate {profile!r}; expected one of {supported}"
        )
    return profile


def validate_network_profile(profile: object) -> str:
    """Return the one approved network-wide RTL28 profile or fail closed."""

    if not isinstance(profile, str) or profile not in SUPPORTED_NETWORK_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_NETWORK_PROFILES))
        raise ContractError(
            f"unsupported network profile {profile!r}; expected one of {supported}"
        )
    return profile


def operator_communication_domain(operator_family: object) -> str:
    """Return the approved DeepSeek-compatible transport scope for a family."""

    if not isinstance(operator_family, str) or operator_family not in OPERATOR_COMMUNICATION_DOMAINS:
        raise ContractError(f"unsupported operator family {operator_family!r}")
    domain = OPERATOR_COMMUNICATION_DOMAINS[operator_family]
    if domain not in SUPPORTED_COMMUNICATION_DOMAINS:
        raise AssertionError("frozen operator communication domain is invalid")
    return domain


@dataclass(frozen=True, slots=True)
class GroupSampleRange:
    """The auditable half-open sample interval owned by one logical group."""

    group_id: int
    start: int
    stop: int

    def __post_init__(self) -> None:
        group_id = _validate_group_id(self.group_id)
        expected = _group_bounds(group_id)
        if (self.start, self.stop) != expected:
            raise ContractError(
                f"group {group_id} must own N[{expected[0]}:{expected[1]}], "
                f"got N[{self.start}:{self.stop}]"
            )

    @property
    def sample_count(self) -> int:
        return self.stop - self.start

    @property
    def sample_ids(self) -> tuple[int, ...]:
        return tuple(range(self.start, self.stop))

    def contains(self, sample_id: object) -> bool:
        sample = _validate_sample_id(sample_id)
        return self.start <= sample < self.stop


@dataclass(frozen=True, slots=True)
class SampleGroupSlot:
    """The logical group and zero-based local slot for one batch sample."""

    sample_id: int
    group_id: int
    local_slot: int

    def __post_init__(self) -> None:
        sample = _validate_sample_id(self.sample_id)
        group_id = _validate_group_id(self.group_id)
        local_slot = _require_plain_int(self.local_slot, "local_slot")
        start, stop = _group_bounds(group_id)
        if not start <= sample < stop or local_slot != sample - start:
            raise ContractError(
                f"sample {sample} must map to its fixed group/local_slot, got "
                f"group={group_id}, local_slot={local_slot}"
            )


@dataclass(frozen=True, slots=True)
class BatchGroupSchedule:
    """Fixed batch=16 allocation across seven logical execution groups."""

    batch_size: int = BATCH_SIZE
    group_sample_counts: tuple[int, ...] = GROUP_SAMPLE_COUNTS

    def __post_init__(self) -> None:
        _validate_batch_size(self.batch_size)
        try:
            counts = tuple(self.group_sample_counts)
        except TypeError as exc:
            raise ContractError("group_sample_counts must be an integer sequence") from exc
        object.__setattr__(self, "group_sample_counts", counts)
        if counts != GROUP_SAMPLE_COUNTS:
            raise ContractError(
                f"batch=16 requires group allocation {GROUP_SAMPLE_COUNTS}, got {counts}"
            )

    def validate(self) -> BatchGroupSchedule:
        _validate_batch_size(self.batch_size)
        if self.group_sample_counts != GROUP_SAMPLE_COUNTS:
            raise ContractError("profile28 group allocation was mutated or is invalid")
        return self

    def group_to_sample_range(self, group_id: object) -> GroupSampleRange:
        group = _validate_group_id(group_id)
        start, stop = _group_bounds(group)
        return GroupSampleRange(group_id=group, start=start, stop=stop)

    def sample_to_group(self, sample_id: object) -> SampleGroupSlot:
        sample = _validate_sample_id(sample_id)
        for group_id in range(GROUP_COUNT):
            start, stop = _group_bounds(group_id)
            if start <= sample < stop:
                return SampleGroupSlot(
                    sample_id=sample,
                    group_id=group_id,
                    local_slot=sample - start,
                )
        raise AssertionError("validated sample was not assigned to a group")

    def group_ranges(self) -> tuple[GroupSampleRange, ...]:
        return tuple(self.group_to_sample_range(group) for group in range(GROUP_COUNT))

    def sample_assignments(self) -> tuple[SampleGroupSlot, ...]:
        return tuple(self.sample_to_group(sample) for sample in range(BATCH_SIZE))


BATCH16_GROUP_SCHEDULE: Final = BatchGroupSchedule()


def group_to_sample_range(
    group_id: object, batch_size: object = BATCH_SIZE
) -> GroupSampleRange:
    """Map a group to its fixed half-open sample interval."""

    _validate_batch_size(batch_size)
    return BATCH16_GROUP_SCHEDULE.group_to_sample_range(group_id)


def sample_to_group(
    sample_id: object, batch_size: object = BATCH_SIZE
) -> SampleGroupSlot:
    """Map a sample to its fixed group and local slot."""

    _validate_batch_size(batch_size)
    return BATCH16_GROUP_SCHEDULE.sample_to_group(sample_id)


@dataclass(frozen=True, slots=True)
class TransitionBoundary:
    """Logical operator boundary at which a conversion is requested."""

    after_operator: str
    before_operator: str
    inside_residual_block: bool = False
    residual_block_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.after_operator, str) or not self.after_operator:
            raise ContractError("after_operator must be a non-empty string")
        if not isinstance(self.before_operator, str) or not self.before_operator:
            raise ContractError("before_operator must be a non-empty string")
        if not isinstance(self.inside_residual_block, bool):
            raise ContractError("inside_residual_block must be a boolean")
        if self.residual_block_id is not None and (
            not isinstance(self.residual_block_id, str) or not self.residual_block_id
        ):
            raise ContractError("residual_block_id must be None or a non-empty string")

    @classmethod
    def after_gap_before_matmul(cls) -> TransitionBoundary:
        return cls(after_operator=GAP_OPERATOR, before_operator=MATMUL_OPERATOR)


@dataclass(frozen=True, slots=True)
class ProfileTransition:
    """One explicit logical conversion between the two W4 candidates."""

    source_profile: str
    target_profile: str
    boundary: TransitionBoundary

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> ProfileTransition:
        source = validate_profile_name(self.source_profile)
        target = validate_profile_name(self.target_profile)
        if not isinstance(self.boundary, TransitionBoundary):
            raise ContractError("profile transition requires a TransitionBoundary")
        if (
            self.boundary.inside_residual_block
            or self.boundary.residual_block_id is not None
        ):
            block = self.boundary.residual_block_id or "unspecified residual block"
            raise ContractError(f"profile conversion inside {block} is forbidden")
        if (source, target) != (
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
            GLOBAL_RING28_PROFILE,
        ):
            raise ContractError(
                "the first profile28 policy only permits small-rings to global-ring "
                "conversion"
            )
        if (
            self.boundary.after_operator,
            self.boundary.before_operator,
        ) != (GAP_OPERATOR, MATMUL_OPERATOR):
            raise ContractError(
                "the first profile28 policy only permits conversion after GAP and "
                "before MatMul"
            )
        return self


@dataclass(frozen=True, slots=True)
class Profile28Schedule:
    """Network-level batch allocation and explicit profile conversion plan."""

    batch_groups: BatchGroupSchedule = field(default_factory=BatchGroupSchedule)
    default_profile: str = DEFAULT_PROFILE
    transitions: tuple[ProfileTransition, ...] = ()

    def __post_init__(self) -> None:
        try:
            transitions = tuple(self.transitions)
        except TypeError as exc:
            raise ContractError("transitions must be a sequence") from exc
        object.__setattr__(self, "transitions", transitions)
        self.validate()

    def validate(self) -> Profile28Schedule:
        if not isinstance(self.batch_groups, BatchGroupSchedule):
            raise ContractError("batch_groups must be a BatchGroupSchedule")
        self.batch_groups.validate()
        profile = validate_profile_name(self.default_profile)
        if profile != GROUP4X7_BATCH_CHANNEL28_PROFILE:
            raise ContractError(
                "the first profile28 policy requires seven small rings as the default"
            )
        if len(self.transitions) > 1:
            raise ContractError(
                "the first profile28 policy permits at most one explicit conversion"
            )
        for transition in self.transitions:
            if not isinstance(transition, ProfileTransition):
                raise ContractError("all transitions must be ProfileTransition records")
            transition.validate()
            if transition.source_profile != profile:
                raise ContractError("transition source must match the default profile")
        return self


DEFAULT_PROFILE28_SCHEDULE: Final = Profile28Schedule()


__all__ = [
    "BATCH_SIZE",
    "GROUP_COUNT",
    "GROUP_SAMPLE_COUNTS",
    "GROUP4X7_BATCH_CHANNEL28_PROFILE",
    "GLOBAL_RING28_PROFILE",
    "DEFAULT_PROFILE",
    "SUPPORTED_PROFILES",
    "DEEPSEEK_HYBRID28_PROFILE",
    "DEFAULT_NETWORK_PROFILE",
    "SUPPORTED_NETWORK_PROFILES",
    "FULL_SLICE_MASK28",
    "OPERATOR_COMMUNICATION_DOMAINS",
    "SUPPORTED_COMMUNICATION_DOMAINS",
    "GAP_OPERATOR",
    "MATMUL_OPERATOR",
    "GroupSampleRange",
    "SampleGroupSlot",
    "BatchGroupSchedule",
    "BATCH16_GROUP_SCHEDULE",
    "TransitionBoundary",
    "ProfileTransition",
    "Profile28Schedule",
    "DEFAULT_PROFILE28_SCHEDULE",
    "validate_profile_name",
    "validate_network_profile",
    "operator_communication_domain",
    "group_to_sample_range",
    "sample_to_group",
]
