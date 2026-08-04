from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_execplan_validator import (
    OperatorConfigExecPlanValidator,
)


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r3-mapping-evidence"
    / "decode_summac-seed42-v1"
)
MASK = (1 << 28) - 1


def _clock(mask: int = MASK) -> int:
    return (0xF << 31) | (mask << 3) | 0b001


def _load(*, length: int = 36, address: int = 1, mask: int = MASK) -> int:
    return (length << 56) | (address << 34) | (mask << 3)


def _start(mask: int = MASK) -> int:
    return (mask << 3) | 0b101


def _write_execplan(path: Path, words: list[int]) -> None:
    lines: list[str] = []
    for index in range(0, len(words), 2):
        low = words[index]
        high = words[index + 1] if index + 1 < len(words) else 0
        lines.append(f"{high:064b}{low:064b}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_explanations(path: Path, words: list[int], *, load_op: str = "op0") -> None:
    rows = [
        f"0000  <{words[0]:064b}>    Clock_Enable (global, once per run): slice_mask_bin={MASK:028b}",
        f"0001  <{words[1]:064b}>    Load_Config for operator {load_op} (decode_summac_fp32N_fp32N): config_length_bin=00100100, ddr_config_addr_bin={1:022b}, config_sfu_bin=0, slice_mask_bin={MASK:028b}",
        f"0002  <{words[2]:064b}>    Start_Comp for operator op0 (decode_summac_fp32N_fp32N): slice_mask_bin={MASK:028b}",
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _codes(report: object) -> set[str]:
    return {issue.code for issue in report.issues}


class OperatorConfigExecPlanValidatorTests(unittest.TestCase):
    def _fixture(self, root: Path, *, load_address: int = 1, load_op: str = "op0") -> tuple[Path, Path]:
        artifact_dir = root / "validated" / "op0"
        shutil.copytree(BUNDLE, artifact_dir)
        local_config = root / "config" / "op0"
        local_config.mkdir(parents=True, exist_ok=True)
        for name in (
            "mapping_review.json",
            "parsed_bitstream.txt",
            "modules_dump_64b.bin",
            "modules_dump_128b.bin",
        ):
            shutil.copy2(artifact_dir / name, local_config / name)
        generated_json = root / "jsons" / "op0_decode_summac_fp32N_fp32N.json"
        generated_json.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact_dir / "source_config.json", generated_json)
        cfg = root / "install" / "cfg_pkg" / "op0_decode_summac_fp32N_fp32N_bitstream_128b.bin"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact_dir / "modules_dump_128b.bin", cfg)
        graph = root / "graph_withbaseaddr.json"
        graph.write_text(
            json.dumps(
                {
                    "operators": [
                        {
                            "id": "op0",
                            "type": "decode_summac_fp32N_fp32N",
                            "used_slices": f"0b{MASK:028b}",
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        sca = {
            "Exec_Base": "0x00000800",
            "Exec_Length": 2,
            "op0_config": {
                "base_addr": "0x00000400",
                "path": "install/cfg_pkg/op0_decode_summac_fp32N_fp32N_bitstream_128b.bin",
            },
        }
        (root / "sca_cfg.json").write_text(json.dumps(sca, indent=2) + "\n", encoding="utf-8")
        words = [_clock(), _load(address=load_address), _start()]
        _write_execplan(root / "install" / "execplan.txt", words)
        _write_explanations(root / "instructions_explained.txt", words, load_op=load_op)
        return graph, artifact_dir

    def _validate(self, root: Path, graph: Path, artifact_dir: Path):
        evidence = json.loads((artifact_dir / "mapping_evidence.json").read_text(encoding="utf-8"))
        return OperatorConfigExecPlanValidator().validate(
            root,
            graph_path=graph,
            source_configs={"op0": artifact_dir / "source_config.json"},
            mapping_evidence={"op0": evidence},
            artifact_dirs={"op0": artifact_dir},
        )

    def test_real_format_load_config_is_bound_to_source_and_bitstream(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-config-execplan-") as temp_text:
            root = Path(temp_text)
            graph, artifact_dir = self._fixture(root)
            report = self._validate(root, graph, artifact_dir)
        self.assertTrue(report.valid, report.to_dict())
        stage = report.facts["stages"][0]
        self.assertEqual(stage["config_base_addr"], "0x00000400")
        self.assertEqual(stage["config_length_64bit_words"], 36)
        self.assertIsNotNone(stage["next_config_state"]["IGA"])
        self.assertIsNotNone(stage["next_config_state"]["LSU"])
        self.assertIsNone(stage["next_config_state"]["SA"])
        self.assertIsNotNone(stage["next_config_state"]["GA"])

    def test_load_config_address_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-config-execplan-") as temp_text:
            root = Path(temp_text)
            graph, artifact_dir = self._fixture(root, load_address=2)
            report = self._validate(root, graph, artifact_dir)
        self.assertIn("EXECPLAN.CONFIG_ADDRESS", _codes(report))

    def test_sca_payload_must_equal_independently_validated_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-config-execplan-") as temp_text:
            root = Path(temp_text)
            graph, artifact_dir = self._fixture(root)
            cfg = root / "install" / "cfg_pkg" / "op0_decode_summac_fp32N_fp32N_bitstream_128b.bin"
            lines = cfg.read_text(encoding="utf-8").splitlines()
            lines[0] = ("1" if lines[0][0] == "0" else "0") + lines[0][1:]
            cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
            report = self._validate(root, graph, artifact_dir)
        self.assertIn("EXECPLAN.CONFIG_ARTIFACT_BINDING", _codes(report))

    def test_explanation_operator_binding_is_not_trusted_without_match(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-config-execplan-") as temp_text:
            root = Path(temp_text)
            graph, artifact_dir = self._fixture(root, load_op="wrong-op")
            report = self._validate(root, graph, artifact_dir)
        self.assertIn("EXECPLAN.OPERATOR_BINDING", _codes(report))

    def test_hash_bound_source_config_cannot_be_swapped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-config-execplan-") as temp_text:
            root = Path(temp_text)
            graph, artifact_dir = self._fixture(root)
            source = artifact_dir / "source_config.json"
            config = json.loads(source.read_text(encoding="utf-8"))
            config["gemm_shape"] = {"M": 1, "N": 1, "K": 1}
            source.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            report = self._validate(root, graph, artifact_dir)
        self.assertIn("EXECPLAN.ARTIFACT_INVALID", _codes(report))

    def test_planner_local_mapping_cannot_be_swapped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-config-execplan-") as temp_text:
            root = Path(temp_text)
            graph, artifact_dir = self._fixture(root)
            local = root / "config" / "op0" / "mapping_review.json"
            local.write_text("{}\n", encoding="utf-8")
            report = self._validate(root, graph, artifact_dir)
        self.assertIn("EXECPLAN.PIPELINE_ARTIFACT", _codes(report))


if __name__ == "__main__":
    unittest.main()
