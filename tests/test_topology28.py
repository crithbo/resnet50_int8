from __future__ import annotations

import unittest

from resnet50_pipeline.topology28 import (
    Direction,
    HIGH_RING_OWNERS,
    LOW_RING_OWNERS,
    RingKind,
    TOPOLOGY28,
)


class Topology28Tests(unittest.TestCase):
    def test_high_exact_forward_reverse_and_group_slice_queries(self) -> None:
        for group, expected in enumerate(HIGH_RING_OWNERS):
            ring = TOPOLOGY28.high_ring_for_group(group)
            self.assertEqual(ring.owners, expected)
            for owner, next_owner in zip(expected, expected[1:] + expected[:1]):
                self.assertEqual(TOPOLOGY28.group_for_slice(owner), group)
                self.assertIs(TOPOLOGY28.high_ring_for_slice(owner), ring)
                self.assertIs(TOPOLOGY28.ring_for_slice(owner, RingKind.HIGH), ring)
                self.assertEqual(TOPOLOGY28.next(owner, RingKind.HIGH), next_owner)
                self.assertEqual(TOPOLOGY28.prev(next_owner, RingKind.HIGH), owner)

    def test_high_rings_are_mutually_exclusive_and_cover_all_slices(self) -> None:
        owners = [owner for ring in TOPOLOGY28.high_rings for owner in ring.owners]
        self.assertEqual(len(owners), 28)
        self.assertEqual(len(set(owners)), 28)
        self.assertEqual(set(owners), set(range(28)))

    def test_low_ring_is_exact_permutation_with_inverse_maps(self) -> None:
        ring = TOPOLOGY28.low_ring
        self.assertEqual(ring.owners, LOW_RING_OWNERS)
        self.assertEqual(len(ring.owners), 28)
        self.assertEqual(set(ring.owners), set(range(28)))
        for owner, next_owner in zip(
            LOW_RING_OWNERS, LOW_RING_OWNERS[1:] + LOW_RING_OWNERS[:1]
        ):
            self.assertIs(TOPOLOGY28.ring_for_slice(owner, RingKind.LOW), ring)
            self.assertEqual(TOPOLOGY28.next(owner, RingKind.LOW), next_owner)
            self.assertEqual(TOPOLOGY28.prev(next_owner, RingKind.LOW), owner)

    def test_walk_and_complete_traversal_have_physical_ring_lengths(self) -> None:
        for ring in TOPOLOGY28.high_rings:
            owner = ring.owners[0]
            self.assertEqual(
                TOPOLOGY28.traverse(owner, RingKind.HIGH, Direction.NEXT), ring.owners
            )
            self.assertEqual(
                TOPOLOGY28.traverse(owner, RingKind.HIGH, Direction.PREV),
                (ring.owners[0],) + tuple(reversed(ring.owners[1:])),
            )
            self.assertEqual(len(TOPOLOGY28.traverse(owner, RingKind.HIGH)), 4)
            self.assertEqual(
                TOPOLOGY28.walk(owner, RingKind.HIGH, Direction.NEXT, 4), owner
            )
            self.assertEqual(
                TOPOLOGY28.walk(owner, RingKind.HIGH, Direction.PREV, 4), owner
            )

        low_owner = LOW_RING_OWNERS[0]
        self.assertEqual(
            TOPOLOGY28.traverse(low_owner, RingKind.LOW, Direction.NEXT), LOW_RING_OWNERS
        )
        self.assertEqual(len(TOPOLOGY28.traverse(low_owner, RingKind.LOW)), 28)
        self.assertEqual(
            TOPOLOGY28.walk(low_owner, RingKind.LOW, Direction.NEXT, 28), low_owner
        )
        self.assertEqual(
            TOPOLOGY28.walk(low_owner, RingKind.LOW, Direction.PREV, 28), low_owner
        )

    def test_invalid_group_slice_direction_step_and_kind_fail(self) -> None:
        for group in (-1, 7):
            with self.assertRaisesRegex(ValueError, "HIGH group"):
                TOPOLOGY28.high_ring_for_group(group)
        for group in (True, 1.0, "0"):
            with self.assertRaisesRegex(TypeError, "group must be an integer"):
                TOPOLOGY28.high_ring_for_group(group)  # type: ignore[arg-type]

        for slice_id in (-1, 28):
            with self.assertRaisesRegex(ValueError, "slice_id must be"):
                TOPOLOGY28.group_for_slice(slice_id)
        for slice_id in (False, 1.0, "0"):
            with self.assertRaisesRegex(TypeError, "slice_id must be an integer"):
                TOPOLOGY28.group_for_slice(slice_id)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, "unsupported direction"):
            TOPOLOGY28.walk(0, RingKind.HIGH, "clockwise", 1)
        with self.assertRaisesRegex(TypeError, "direction must be"):
            TOPOLOGY28.walk(0, RingKind.HIGH, 1, 1)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "steps must be non-negative"):
            TOPOLOGY28.walk(0, RingKind.HIGH, Direction.NEXT, -1)
        for steps in (True, 1.5, "1"):
            with self.assertRaisesRegex(TypeError, "steps must be an integer"):
                TOPOLOGY28.walk(0, RingKind.HIGH, Direction.NEXT, steps)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, "unsupported ring kind"):
            TOPOLOGY28.next(0, "middle")
        with self.assertRaisesRegex(TypeError, "ring kind must be"):
            TOPOLOGY28.next(0, 0)  # type: ignore[arg-type]

    def test_validation_report_confirms_complete_topology(self) -> None:
        report = TOPOLOGY28.validate()
        self.assertEqual(report.slice_count, 28)
        self.assertEqual(report.high_group_count, 7)
        self.assertEqual(report.high_ring_lengths, (4, 4, 4, 4, 4, 4, 4))
        self.assertEqual(report.low_ring_length, 28)


if __name__ == "__main__":
    unittest.main()
