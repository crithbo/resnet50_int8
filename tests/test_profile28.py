from __future__ import annotations

import unittest

from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.profile28 import (
    BATCH16_GROUP_SCHEDULE,
    DEEPSEEK_HYBRID28_PROFILE,
    FULL_SLICE_MASK28,
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    GROUP_SAMPLE_COUNTS,
    MATMUL_OPERATOR,
    OPERATOR_COMMUNICATION_DOMAINS,
    BatchGroupSchedule,
    Profile28Schedule,
    ProfileTransition,
    TransitionBoundary,
    group_to_sample_range,
    operator_communication_domain,
    sample_to_group,
    validate_network_profile,
    validate_profile_name,
)


def _allowed_transition() -> ProfileTransition:
    return ProfileTransition(
        source_profile=GROUP4X7_BATCH_CHANNEL28_PROFILE,
        target_profile=GLOBAL_RING28_PROFILE,
        boundary=TransitionBoundary.after_gap_before_matmul(),
    )


class Profile28SchedulingTests(unittest.TestCase):
    def test_deepseek_network_profile_uses_full_mask_and_family_scoped_domains(self) -> None:
        self.assertEqual(
            validate_network_profile(DEEPSEEK_HYBRID28_PROFILE),
            DEEPSEEK_HYBRID28_PROFILE,
        )
        self.assertEqual(FULL_SLICE_MASK28, 0x0FFFFFFF)
        self.assertEqual(
            {
                family: operator_communication_domain(family)
                for family in OPERATOR_COMMUNICATION_DOMAINS
            },
            OPERATOR_COMMUNICATION_DOMAINS,
        )
        self.assertEqual(
            {family for family, domain in OPERATOR_COMMUNICATION_DOMAINS.items() if domain == "high4"},
            {"conv", "matmul"},
        )
        self.assertNotIn("low28", OPERATOR_COMMUNICATION_DOMAINS.values())
        with self.assertRaises(ContractError):
            validate_network_profile(GLOBAL_RING28_PROFILE)

    def test_all_16_samples_are_covered_exactly_once_and_reverse_map(self) -> None:
        ranges = BATCH16_GROUP_SCHEDULE.group_ranges()
        flattened = [sample for item in ranges for sample in item.sample_ids]
        self.assertEqual(flattened, list(range(16)))
        self.assertEqual(len(flattened), len(set(flattened)))

        for assignment in BATCH16_GROUP_SCHEDULE.sample_assignments():
            owned = group_to_sample_range(assignment.group_id)
            self.assertTrue(owned.contains(assignment.sample_id))
            self.assertEqual(
                owned.start + assignment.local_slot, assignment.sample_id
            )

    def test_three_and_two_sample_group_boundaries_are_fixed(self) -> None:
        intervals = [
            (item.start, item.stop)
            for item in BATCH16_GROUP_SCHEDULE.group_ranges()
        ]
        self.assertEqual(
            intervals,
            [(0, 3), (3, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16)],
        )
        self.assertEqual(
            tuple(item.sample_count for item in BATCH16_GROUP_SCHEDULE.group_ranges()),
            GROUP_SAMPLE_COUNTS,
        )
        self.assertEqual(
            (sample_to_group(2).group_id, sample_to_group(2).local_slot), (0, 2)
        )
        self.assertEqual(
            (sample_to_group(3).group_id, sample_to_group(3).local_slot), (1, 0)
        )
        self.assertEqual(
            (sample_to_group(6).group_id, sample_to_group(6).local_slot), (2, 0)
        )
        self.assertEqual(
            (sample_to_group(15).group_id, sample_to_group(15).local_slot), (6, 1)
        )

    def test_invalid_batch_group_and_sample_fail(self) -> None:
        with self.assertRaises(ContractError):
            BatchGroupSchedule(batch_size=15)
        with self.assertRaises(ContractError):
            BatchGroupSchedule(group_sample_counts=(3, 3, 2, 2, 2, 2, 1))
        for invalid_group in (-1, 7, True):
            with self.subTest(group=invalid_group), self.assertRaises(ContractError):
                group_to_sample_range(invalid_group)
        for invalid_sample in (-1, 16, False):
            with self.subTest(sample=invalid_sample), self.assertRaises(ContractError):
                sample_to_group(invalid_sample)
        with self.assertRaises(ContractError):
            sample_to_group(0, batch_size=32)

    def test_residual_block_transition_is_rejected(self) -> None:
        boundary = TransitionBoundary(
            after_operator="QLinearConv",
            before_operator="QLinearAdd",
            inside_residual_block=True,
            residual_block_id="resnetv17_stage1_block1",
        )
        with self.assertRaisesRegex(ContractError, "inside.*forbidden"):
            ProfileTransition(
                source_profile=GROUP4X7_BATCH_CHANNEL28_PROFILE,
                target_profile=GLOBAL_RING28_PROFILE,
                boundary=boundary,
            )

    def test_repeated_transition_is_rejected(self) -> None:
        transition = _allowed_transition()
        with self.assertRaisesRegex(ContractError, "at most one"):
            Profile28Schedule(transitions=(transition, transition))

    def test_wrong_profile_and_other_conversion_boundaries_fail(self) -> None:
        with self.assertRaises(ContractError):
            validate_profile_name("w4_unknown_profile")
        with self.assertRaises(ContractError):
            Profile28Schedule(default_profile=GLOBAL_RING28_PROFILE)
        with self.assertRaisesRegex(ContractError, "only permits conversion"):
            ProfileTransition(
                source_profile=GROUP4X7_BATCH_CHANNEL28_PROFILE,
                target_profile=GLOBAL_RING28_PROFILE,
                boundary=TransitionBoundary(
                    after_operator="QLinearConv",
                    before_operator=MATMUL_OPERATOR,
                ),
            )
        with self.assertRaisesRegex(ContractError, "small-rings to global-ring"):
            ProfileTransition(
                source_profile=GLOBAL_RING28_PROFILE,
                target_profile=GROUP4X7_BATCH_CHANNEL28_PROFILE,
                boundary=TransitionBoundary.after_gap_before_matmul(),
            )

    def test_default_and_single_preferred_transition_are_valid(self) -> None:
        self.assertEqual(
            Profile28Schedule().default_profile,
            GROUP4X7_BATCH_CHANNEL28_PROFILE,
        )
        schedule = Profile28Schedule(transitions=(_allowed_transition(),))
        self.assertIs(schedule.validate(), schedule)
        self.assertEqual(schedule.transitions[0].target_profile, GLOBAL_RING28_PROFILE)


if __name__ == "__main__":
    unittest.main()
    OPERATOR_COMMUNICATION_DOMAINS,
