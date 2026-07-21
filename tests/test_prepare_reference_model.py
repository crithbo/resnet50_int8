from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.prepare_reference_model import (
    CONTRACT_PATH,
    ROOT,
    _build_input,
    sha256_file,
)


class ReferenceModelPreparationTests(unittest.TestCase):
    def test_preprocessing_reproduces_the_frozen_batch16_input(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        run = contract["reference_run"]
        value = _build_input(ROOT / run["image_path"])
        self.assertEqual(list(value.shape), run["input_shape"])
        self.assertEqual(value.dtype, np.dtype("float32"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input_batch16.npy"
            with path.open("wb") as stream:
                np.save(stream, value, allow_pickle=False)
            self.assertEqual(sha256_file(path), run["input_sha256"])


if __name__ == "__main__":
    unittest.main()
