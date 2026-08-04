from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from resnet50_pipeline.operator_config_package_validator import (
    OperatorConfigPackageValidator,
)
from resnet50_pipeline.operator_config_validator import TargetProfile


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _codes(report: object) -> set[str]:
    return {issue.code for issue in report.issues}


class OperatorConfigPackageValidatorTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, dict]:
        graph = root / "graph_withbaseaddr.json"
        graph.write_text(
            json.dumps(
                {
                    "used_slices": 1,
                    "operators": [
                        {
                            "id": "op0",
                            "type": "decode_summac_fp32N_fp32N",
                            "used_slices": "0b1",
                            "inputs": {
                                "A": {
                                    "shape": [1, 1, 4],
                                    "dtype": "fp32",
                                    "source": {"type": "external"},
                                    "base_addr": "0x00000000",
                                }
                            },
                            "output": {
                                "shape": [1, 1, 1],
                                "dtype": "fp32",
                                "base_addr": "0x00000010",
                            },
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        files = {
            "install/op0/slice00/matrix_A_linearized_128bit.txt": "0" * 128 + "\n",
            "install/op0/slice00/matrix_D_linearized_128bit.txt": "0" * 128 + "\n",
            "install/cfg_pkg/op0.bin": "0" * 128 + "\n",
            "install/execplan.txt": "0" * 128 + "\n",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (root / "sca_cfg.json").write_text(
            json.dumps(
                {
                    "Exec_Base": "0x0000_0800",
                    "Exec_Length": 1,
                    "ExecutionPlan": {"base_addr": "0x00000800", "path": "install/execplan.txt"},
                    "op0_matrixA_slice0": {
                        "base_addr": "0x00000000",
                        "path": "install/op0/slice00/matrix_A_linearized_128bit.txt",
                    },
                    "op0_config": {"base_addr": "0x00000400", "path": "install/cfg_pkg/op0.bin"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "sca_cfg_D.json").write_text(
            json.dumps(
                {
                    "op0_matrixD_slice0": {
                        "base_addr": "0x00000010",
                        "path": "install/op0/slice00/matrix_D_linearized_128bit.txt",
                        "length": 1,
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        contract = {
            "schema": "operator-config-semantic-contract-v1",
            "graph_sha256": _sha(graph),
            "target_profile": asdict(TargetProfile()),
            "operators": {
                "op0": {
                    "op_type": "decode_summac_fp32N_fp32N",
                    "layouts": {"A": "KMN/native", "D": "KMN/native"},
                    "qparams": {"policy": "not-applicable"},
                    "stage": {"role": "sum-of-squares", "dependencies": []},
                    "tail": {"policy": "exact"},
                    "provenance": {
                        "source_config": {
                            "artifact": "graph_withbaseaddr.json",
                            "sha256": _sha(graph),
                        },
                        "mapping_evidence": {
                            "artifact": "sca_cfg.json",
                            "sha256": _sha(root / "sca_cfg.json"),
                        },
                    },
                }
            },
        }
        return graph, contract

    def test_valid_package_binds_addresses_files_and_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-package-") as temp_text:
            root = Path(temp_text)
            graph, contract = self._fixture(root)
            report = OperatorConfigPackageValidator().validate(
                root, graph_path=graph, semantic_contract=contract
            )
        self.assertTrue(report.valid, report.to_dict())
        self.assertEqual(report.facts["memory_region_count"], 4)
        self.assertEqual(report.facts["missing_matrix_files"], [])

    def test_row_equal_to_6144_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-package-") as temp_text:
            root = Path(temp_text)
            graph, contract = self._fixture(root)
            sca_path = root / "sca_cfg.json"
            sca = json.loads(sca_path.read_text(encoding="utf-8"))
            illegal = 6144 << 10
            sca["op0_matrixA_slice0"]["base_addr"] = f"0x{illegal:08X}"
            sca_path.write_text(json.dumps(sca, indent=2) + "\n", encoding="utf-8")
            graph_payload = json.loads(graph.read_text(encoding="utf-8"))
            graph_payload["operators"][0]["inputs"]["A"]["base_addr"] = f"0x{illegal:08X}"
            graph.write_text(json.dumps(graph_payload, indent=2) + "\n", encoding="utf-8")
            contract["graph_sha256"] = _sha(graph)
            report = OperatorConfigPackageValidator().validate(
                root, graph_path=graph, semantic_contract=contract
            )
        self.assertIn("SCA.ROW_LIMIT", _codes(report))
        self.assertIn("SCA.CAPACITY", _codes(report))

    def test_missing_independent_b_prime_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-package-") as temp_text:
            root = Path(temp_text)
            graph, contract = self._fixture(root)
            payload = json.loads(graph.read_text(encoding="utf-8"))
            op = payload["operators"][0]
            op["type"] = "decode_gemv_local"
            op["inputs"]["B"] = {
                "shape": [1, 1, 4], "dtype": "fp32", "source": {"type": "external"}, "base_addr": "0x20"
            }
            op["inputs"]["B'"] = {
                "shape": [1, 1, 4], "dtype": "fp32", "source": {"type": "external"}, "base_addr": "0x30"
            }
            graph.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            item = contract["operators"]["op0"]
            item["op_type"] = "decode_gemv_local"
            item["layouts"].update({"B": "KMN/native", "B'": "KMN/native"})
            contract["graph_sha256"] = _sha(graph)
            report = OperatorConfigPackageValidator().validate(
                root, graph_path=graph, semantic_contract=contract
            )
        self.assertIn("SCA.B_PRIME_MISSING", _codes(report))

    def test_undeclared_overlap_and_missing_qparam_contract_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-package-") as temp_text:
            root = Path(temp_text)
            graph, contract = self._fixture(root)
            sca_d_path = root / "sca_cfg_D.json"
            sca_d = json.loads(sca_d_path.read_text(encoding="utf-8"))
            sca_d["op0_matrixD_slice0"]["base_addr"] = "0x00000000"
            sca_d_path.write_text(json.dumps(sca_d, indent=2) + "\n", encoding="utf-8")
            graph_payload = json.loads(graph.read_text(encoding="utf-8"))
            graph_payload["operators"][0]["output"]["base_addr"] = "0x00000000"
            graph_payload["operators"][0]["output"]["dtype"] = "int8"
            graph.write_text(json.dumps(graph_payload, indent=2) + "\n", encoding="utf-8")
            contract["graph_sha256"] = _sha(graph)
            report = OperatorConfigPackageValidator().validate(
                root, graph_path=graph, semantic_contract=contract
            )
        self.assertIn("SCA.REGION_OVERLAP", _codes(report))
        self.assertIn("CONTRACT.QPARAM", _codes(report))

    def test_per_channel_qparam_tensor_is_hash_bound_without_scalar_collapse(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-package-") as temp_text:
            root = Path(temp_text)
            graph, contract = self._fixture(root)
            payload = json.loads(graph.read_text(encoding="utf-8"))
            payload["operators"][0]["inputs"]["A"].update(
                {"shape": [1, 1, 16], "dtype": "int8"}
            )
            graph.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            contract["graph_sha256"] = _sha(graph)
            contract["operators"]["op0"]["provenance"]["source_config"][
                "sha256"
            ] = _sha(graph)
            contract["operators"]["op0"]["qparams"] = {
                "policy": "explicit",
                "bindings": {
                    "A": {
                        "scale": {
                            "value_kind": "per_channel",
                            "dtype": "float32",
                            "shape": [16],
                            "axis": 0,
                            "element_count": 16,
                            "minimum": 0.001,
                            "maximum": 0.125,
                            "value_sha256": "a" * 64,
                        },
                        "zero_point": {
                            "value_kind": "per_channel",
                            "dtype": "int8",
                            "shape": [16],
                            "axis": 0,
                            "element_count": 16,
                            "minimum": 0,
                            "maximum": 0,
                            "value_sha256": "b" * 64,
                        },
                        "source": "locked typed-lowering request",
                    }
                },
            }
            report = OperatorConfigPackageValidator().validate(
                root, graph_path=graph, semantic_contract=contract
            )
        self.assertTrue(report.valid, report.to_dict())

    def test_per_channel_qparam_without_value_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-package-") as temp_text:
            root = Path(temp_text)
            graph, contract = self._fixture(root)
            payload = json.loads(graph.read_text(encoding="utf-8"))
            payload["operators"][0]["inputs"]["A"].update(
                {"shape": [1, 1, 16], "dtype": "int8"}
            )
            graph.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            contract["graph_sha256"] = _sha(graph)
            contract["operators"]["op0"]["provenance"]["source_config"][
                "sha256"
            ] = _sha(graph)
            contract["operators"]["op0"]["qparams"] = {
                "policy": "explicit",
                "bindings": {
                    "A": {
                        "scale": {
                            "value_kind": "per_channel",
                            "dtype": "float32",
                            "shape": [16],
                            "axis": 0,
                            "element_count": 16,
                            "minimum": 0.001,
                            "maximum": 0.125,
                        },
                        "zero_point": 0,
                        "source": "unbound vector",
                    }
                },
            }
            report = OperatorConfigPackageValidator().validate(
                root, graph_path=graph, semantic_contract=contract
            )
        self.assertIn("CONTRACT.QPARAM", _codes(report))

    def test_tail_block_overflow_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="operator-package-") as temp_text:
            root = Path(temp_text)
            graph, contract = self._fixture(root)
            contract["operators"]["op0"]["tail"] = {
                "policy": "explicit",
                "bindings": {
                    "A": {"block_elements": 4, "valid_last": 5},
                    "D": {"block_elements": 4, "valid_last": 1},
                },
            }
            report = OperatorConfigPackageValidator().validate(
                root, graph_path=graph, semantic_contract=contract
            )
        self.assertIn("CONTRACT.TAIL_RANGE", _codes(report))


if __name__ == "__main__":
    unittest.main()
