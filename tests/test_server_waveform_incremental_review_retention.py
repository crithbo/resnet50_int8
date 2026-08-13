from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from tools.server_waveform_incremental_review_retention import (
    ReviewError,
    add_review_chunk,
    finalize_inconclusive,
    hash_file,
    init_review,
    mark_consumed,
    read_json,
    register_return,
    retention_plan,
    retire_return,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/server_waveform_incremental_review_retention_v1"
REVIEW_SCHEMA = ROOT / "schemas/server_waveform_incremental_review_v1.schema.json"
RETENTION_SCHEMA = ROOT / "schemas/server_waveform_return_retention_v1.schema.json"
DISPATCH = ROOT / "contracts/server_waveform_incremental_review_retention_dispatch_v1.json"


class IncrementalWaveformReviewRetentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.storage = self.root / "returns"
        self.storage.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_return(self, return_id: str, *, wave: bytes = b"FSDB" * 32) -> Path:
        target = self.storage / f"{return_id}_return.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{return_id}/core/SIM_EXIT_RECEIPT.json", '{"exit": 0}\n')
            archive.writestr(f"{return_id}/logs/sim.log", "time=120 root found\n")
            archive.writestr(f"{return_id}/waveforms/run/wave.fsdb", wave)
        return target

    def init(self, return_id: str, candidates: list[str] | None = None) -> tuple[Path, Path, dict]:
        return_zip = self.make_return(return_id)
        review_dir = self.root / "review" / return_id
        index = init_review(
            family="synthetic",
            track="unit",
            return_id=return_id,
            return_zip=return_zip,
            review_dir=review_dir,
            candidates=candidates or ["source_missing", "consumer_disabled", "parser_loss"],
        )
        return return_zip, review_dir, index

    def root_chunk(self, return_zip: Path, review_dir: Path) -> dict:
        chunk = json.loads((FIXTURES / "root_cause_chunk.json").read_text(encoding="utf-8"))
        chunk["return_zip_sha256"] = hash_file(return_zip)[1]
        identity = read_json(review_dir / "return_identity.json")
        chunk["waveform_sha256"] = identity["return_zip"]["waveforms"][0]["sha256"]
        return chunk

    def write_chunk(self, name: str, value: dict) -> Path:
        target = self.root / f"{name}.json"
        target.write_text(json.dumps(value), encoding="utf-8")
        return target

    def consume(self, index_path: Path, return_id: str) -> None:
        family = self.root / f"{return_id}.family.json"
        mainline = self.root / f"{return_id}.mainline.json"
        family.write_text('{"consumed": true}\n', encoding="utf-8")
        mainline.write_text('{"consumed": true}\n', encoding="utf-8")
        mark_consumed(index_path, return_id, family, mainline, [])

    def test_init_binds_full_return_and_waveform(self) -> None:
        return_zip, review_dir, index = self.init("r1")
        identity = read_json(review_dir / "return_identity.json")
        self.assertEqual(identity["return_zip"]["sha256"], hash_file(return_zip)[1])
        self.assertEqual(len(identity["return_zip"]["waveforms"]), 1)
        self.assertEqual(index["review_revision"], 0)
        if jsonschema is not None:
            schema = json.loads(REVIEW_SCHEMA.read_text(encoding="utf-8"))
            jsonschema.validate(identity, schema)
            jsonschema.validate(index, schema)

    def test_init_is_idempotent_for_exact_identity(self) -> None:
        return_zip, review_dir, index = self.init("r1")
        repeated = init_review(
            family="synthetic",
            track="unit",
            return_id="r1",
            return_zip=return_zip,
            review_dir=review_dir,
            candidates=["different-memory-only-list"],
        )
        self.assertEqual(repeated, index)

    def test_root_chunk_writes_immutable_chunk_and_stops(self) -> None:
        return_zip, review_dir, _ = self.init("r1")
        chunk_path = self.write_chunk("root", self.root_chunk(return_zip, review_dir))
        index = add_review_chunk(review_dir, chunk_path)
        self.assertEqual(index["status"], "ROOT_CAUSE_UNIQUE_STOP")
        self.assertTrue((review_dir / "chunks/000001.json").is_file())
        self.assertTrue((review_dir / "final_adjudication.json").is_file())
        with self.assertRaises(ReviewError):
            add_review_chunk(review_dir, chunk_path)

    def test_identity_drift_fails_closed(self) -> None:
        return_zip, review_dir, _ = self.init("r1")
        chunk = self.root_chunk(return_zip, review_dir)
        chunk["return_zip_sha256"] = "0" * 64
        with self.assertRaisesRegex(ReviewError, "identity mismatch"):
            add_review_chunk(review_dir, self.write_chunk("drift", chunk))

    def test_revision_conflict_fails_closed(self) -> None:
        return_zip, review_dir, _ = self.init("r1")
        chunk = self.root_chunk(return_zip, review_dir)
        chunk["expected_review_revision"] = 7
        with self.assertRaisesRegex(ReviewError, "revision conflict"):
            add_review_chunk(review_dir, self.write_chunk("revision", chunk))

    def test_sampling_or_truncation_fails_closed(self) -> None:
        return_zip, review_dir, _ = self.init("r1")
        chunk = json.loads((FIXTURES / "sampled_chunk_negative.json").read_text(encoding="utf-8"))
        chunk["return_zip_sha256"] = hash_file(return_zip)[1]
        identity = read_json(review_dir / "return_identity.json")
        chunk["waveform_sha256"] = identity["return_zip"]["waveforms"][0]["sha256"]
        with self.assertRaisesRegex(ReviewError, "every transition"):
            add_review_chunk(review_dir, self.write_chunk("sampled", chunk))

    def test_unique_root_requires_closed_alternatives(self) -> None:
        return_zip, review_dir, _ = self.init("r1")
        chunk = self.root_chunk(return_zip, review_dir)
        chunk["candidate_updates"]["closed"] = []
        with self.assertRaisesRegex(ReviewError, "closed alternatives"):
            add_review_chunk(review_dir, self.write_chunk("no_closed", chunk))

    def test_candidate_update_cannot_silently_drop_an_alternative(self) -> None:
        return_zip, review_dir, _ = self.init("r1")
        chunk = self.root_chunk(return_zip, review_dir)
        chunk["candidate_updates"]["closed"] = ["source_missing"]
        with self.assertRaisesRegex(ReviewError, "account for every"):
            add_review_chunk(review_dir, self.write_chunk("candidate_drop", chunk))

    def test_inconclusive_final_requires_prior_chunk(self) -> None:
        _, review_dir, _ = self.init("r1")
        with self.assertRaisesRegex(ReviewError, "without an evidence chunk"):
            finalize_inconclusive(review_dir, "decoder unavailable", ["all signal transitions"])

    def terminal_review(self, return_id: str, role: str, index_path: Path) -> tuple[Path, Path]:
        return_zip, review_dir, _ = self.init(return_id)
        add_review_chunk(review_dir, self.write_chunk(f"{return_id}_root", self.root_chunk(return_zip, review_dir)))
        register_return(
            index_path=index_path,
            storage_root=self.storage,
            family="synthetic",
            track="unit",
            return_id=return_id,
            return_zip=return_zip,
            review_dir=review_dir,
            role=role,
        )
        return return_zip, review_dir

    def test_retention_selects_oldest_consumed_unprotected(self) -> None:
        index_path = self.root / "retention.json"
        self.terminal_review("old", "OTHER", index_path)
        self.consume(index_path, "old")
        self.terminal_review("base", "BASELINE", index_path)
        self.terminal_review("causal", "CAUSAL", index_path)
        self.terminal_review("current", "CURRENT", index_path)
        plan = retention_plan(read_json(index_path))
        self.assertTrue(plan["pass"], plan["errors"])
        self.assertEqual(plan["raw_count"], 4)
        self.assertEqual(plan["selected_return_ids"], ["old"])
        if jsonschema is not None:
            schema = json.loads(RETENTION_SCHEMA.read_text(encoding="utf-8"))
            jsonschema.validate(read_json(index_path), schema)
            jsonschema.validate(plan, schema)

    def test_retention_fails_when_every_entry_is_protected(self) -> None:
        index_path = self.root / "retention.json"
        # Only three named anchor roles may exist; the fourth remains OTHER but
        # carries an explicit protection reason after consumption.
        self.terminal_review("base", "BASELINE", index_path)
        self.terminal_review("causal", "CAUSAL", index_path)
        self.terminal_review("current", "CURRENT", index_path)
        self.terminal_review("other", "OTHER", index_path)
        family = self.root / "other.family.json"
        mainline = self.root / "other.mainline.json"
        family.write_text("{}", encoding="utf-8")
        mainline.write_text("{}", encoding="utf-8")
        mark_consumed(index_path, "other", family, mainline, ["only independent repeat"])
        plan = retention_plan(read_json(index_path))
        self.assertFalse(plan["pass"])
        self.assertEqual(plan["selected_return_ids"], [])

    def test_unconsumed_old_return_is_not_retireable(self) -> None:
        index_path = self.root / "retention.json"
        self.terminal_review("old", "OTHER", index_path)
        self.terminal_review("base", "BASELINE", index_path)
        self.terminal_review("causal", "CAUSAL", index_path)
        self.terminal_review("current", "CURRENT", index_path)
        plan = retention_plan(read_json(index_path))
        self.assertFalse(plan["pass"])
        self.assertEqual(plan["selected_return_ids"], [])

    def test_registration_rejects_storage_root_escape(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        return_zip = outside / "escape_return.zip"
        with zipfile.ZipFile(return_zip, "w") as archive:
            archive.writestr("escape/wave.fsdb", b"raw")
        review_dir = self.root / "review_escape"
        init_review(
            family="synthetic",
            track="unit",
            return_id="escape",
            return_zip=return_zip,
            review_dir=review_dir,
            candidates=["x"],
        )
        with self.assertRaisesRegex(ReviewError, "escapes declared storage root"):
            register_return(
                index_path=self.root / "retention.json",
                storage_root=self.storage,
                family="synthetic",
                track="unit",
                return_id="escape",
                return_zip=return_zip,
                review_dir=review_dir,
                role="OTHER",
            )

    def test_retire_preserves_core_and_removes_only_exact_heavy_zip(self) -> None:
        index_path = self.root / "retention.json"
        old_zip, _ = self.terminal_review("old", "OTHER", index_path)
        self.consume(index_path, "old")
        self.terminal_review("base", "BASELINE", index_path)
        self.terminal_review("causal", "CAUSAL", index_path)
        self.terminal_review("current", "CURRENT", index_path)
        receipt = retire_return(index_path, "old", self.root / "retired")
        self.assertTrue(receipt["deleted"])
        self.assertFalse(old_zip.exists())
        core = Path(receipt["core_return_zip"]["path"])
        self.assertTrue(core.is_file())
        with zipfile.ZipFile(core) as archive:
            names = archive.namelist()
            self.assertTrue(any(name.endswith("SIM_EXIT_RECEIPT.json") for name in names))
            self.assertTrue(any(name.endswith("sim.log") for name in names))
            self.assertTrue(any(name.endswith("RAW_WAVEFORM_RETIREMENT_MANIFEST.json") for name in names))
            self.assertFalse(any(name.endswith(".fsdb") for name in names))
        entry = next(item for item in read_json(index_path)["entries"] if item["return_id"] == "old")
        self.assertEqual(entry["status"], "RAW_EVIDENCE_RETIRED")

    def test_identity_drift_prevents_retirement(self) -> None:
        index_path = self.root / "retention.json"
        old_zip, _ = self.terminal_review("old", "OTHER", index_path)
        self.consume(index_path, "old")
        self.terminal_review("base", "BASELINE", index_path)
        self.terminal_review("causal", "CAUSAL", index_path)
        self.terminal_review("current", "CURRENT", index_path)
        old_zip.write_bytes(old_zip.read_bytes() + b"drift")
        with self.assertRaisesRegex(ReviewError, "identity drifted"):
            retire_return(index_path, "old", self.root / "retired")
        self.assertTrue(old_zip.exists())

    def test_dispatch_has_phase_boundary_and_three_slots(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(dispatch["heavy_raw_slots_per_family_track"]["maximum"], 3)
        self.assertIn("collection", dispatch["phase_boundary"])
        self.assertEqual(
            set(dispatch["heavy_raw_slots_per_family_track"]["protected_roles"]),
            {"CURRENT", "BASELINE", "CAUSAL"},
        )


if __name__ == "__main__":
    unittest.main()
