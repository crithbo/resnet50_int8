"""Build the isolated QAdd node0007 tail-round column-fix diagnostic package."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

from resnet50_pipeline.qlinearadd_node0007_full_e2 import (
    RECIPROCAL,
    load_physical_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_qadd_n7_tailround_flow_v49"
TARGET = "r5_qadd_n7_tailround_split_v50"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_flow_v49.zip"
SOURCE_SHA = "b5fe58fff8401fb60284951859be975931e8744e1e0235b60847973513abf071"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-v50-package"
OUT_ZIP = LOCAL / f"{TARGET}.zip"
PIPE = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild/execplan/pipeline_output"
BUILD_RECEIPT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild/build_receipt.json"
VALIDATION = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild/validation_report.json"
CANONICAL = ROOT / "tools/qlinearadd_node0007_tailround_split_canonical_v50.py"
RULES = {
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def records(package: Path) -> dict[str, Any]:
    result = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        rel = path.relative_to(package).as_posix()
        if rel != "TEST_PACKAGE_MANIFEST.json":
            result[rel] = {"size_bytes": path.stat().st_size, "sha256": sha(path)}
    return result


def extract(destination: Path) -> Path:
    if sha(SOURCE) != SOURCE_SHA:
        raise BuildError("frozen v49 source SHA differs")
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise BuildError("frozen v49 CRC failed")
        roots: set[str] = set(); seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename); mode = (info.external_attr >> 16) & 0xFFFF
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or info.filename in seen or stat.S_ISLNK(mode):
                raise BuildError(f"unsafe source member: {info.filename}")
            roots.add(pure.parts[0]); seen.add(info.filename)
        if roots != {SOURCE_ID}:
            raise BuildError(f"source root differs: {roots}")
        archive.extractall(destination)
    source = destination / SOURCE_ID
    target = destination / TARGET
    source.rename(target)
    return target


def replace_identity(package: Path) -> None:
    suffixes = {".json", ".txt", ".md", ".py", ".sh", ".sv", ".svh", ".v", ".vh"}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.suffix.lower() not in suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_ID in text:
            path.write_text(text.replace(SOURCE_ID, TARGET), encoding="utf-8", newline="\n")


def encode_128bit(path: Path, payload: bytes) -> None:
    if len(payload) % 16:
        raise BuildError("diagnostic payload is not 128-bit aligned")
    table = [format(value, "08b").encode("ascii") for value in range(256)]
    path.parent.mkdir(parents=True, exist_ok=True)
    view = memoryview(payload)
    with path.open("wb") as stream:
        for start in range(0, len(payload), 16 * 8192):
            block = view[start : start + 16 * 8192]
            rows = []
            for offset in range(0, len(block), 16):
                rows.append(b"".join(table[value] for value in block[offset : offset + 16]))
            stream.write(b"\n".join(rows) + b"\n")


def materialize_boundary_inputs(package: Path) -> dict[str, Any]:
    record, _, _, bundle = load_physical_bundle(ROOT)
    q = record["qparams"]
    entries = []
    install = package / "workload/runtime/install/op_tail_round"
    for slice_id in range(28):
        a = np.frombuffer(bundle.read("A", slice_id), dtype=np.uint8).astype(np.float32)
        b = np.frombuffer(bundle.read("B", slice_id), dtype=np.uint8).astype(np.float32)
        a_scaled = np.float32(np.float32(a + np.float32(-q["a_zero_point"]["value"])) * np.float32(q["a_scale"]["value"]))
        b_scaled = np.float32(np.float32(b + np.float32(-q["b_zero_point"]["value"])) * np.float32(q["b_scale"]["value"]))
        summed = np.float32(a_scaled + b_scaled)
        tail_mul = np.ascontiguousarray(np.float32(summed * RECIPROCAL), dtype="<f4")
        output = install / f"slice{slice_id:02d}/matrix_A_linearized_128bit.txt"
        encode_128bit(output, tail_mul.tobytes())
        entries.append({"slice_id": slice_id, "bytes": tail_mul.nbytes, "text_bytes": output.stat().st_size, "sha256": sha(output)})
    return {
        "mode": "DIAGNOSTIC_STIMULUS_NOT_PRODUCER_EVIDENCE",
        "host_precomputed_internal_tensor": True,
        "source": "frozen node0007 A/B physical bundle replayed through W3 FP32 dequant/add and exact frozen tail_mul multiplier",
        "producer_evidence_claimed": False,
        "dtype": "fp32", "layout": "28 physical slices, shape [1,75264,8] per slice",
        "injection_base_per_slice": "0x00A4C000 + slice_id*0x02000000",
        "entries": entries,
        "claim_boundary": "isolated tail_round input only; no tail_mul execution, cross-stage barrier/lifetime, full chain, E3, E4 or E5 claim",
    }


def patch_runtime(package: Path) -> None:
    old = package / "package_tools/qlinearadd_node0007_fullchain_runtime_v38.py"
    text = old.read_text(encoding="utf-8")
    substitutions = [
        ('"""Install-subtree runtime adapter for the node0007 six-stage full chain."""', '"""Install-subtree runtime adapter for isolated node0007 tail_round."""'),
        ('stages\n        != [\n            "op_a_dequant",\n            "op_b_dequant",\n            "op_relocation_pad",\n            "op_fp32_add",\n            "op_tail_mul",\n            "op_tail_round",\n        ]', 'stages != ["op_tail_round"]'),
        ('split.get("result_mode") != "FULL_NUMERIC_28D"', 'split.get("result_mode") != "STAGE_LOCAL_NUMERIC_DIAGNOSTIC_28D"'),
        ('raise RuntimeGateError("six-stage/full-28D contract differs")', 'raise RuntimeGateError("one-stage tail_round/28D diagnostic contract differs")'),
        ('if int(sca.get("Repeat_Num", -1)) != 6:', 'if int(sca.get("Repeat_Num", -1)) != 1:'),
        ('raise RuntimeGateError("SCA six-stage repeat differs")', 'raise RuntimeGateError("SCA one-stage repeat differs")'),
        ('if actual_stage_dirs != {\n        "op_a_dequant",\n        "op_b_dequant",\n        "op_relocation_pad",\n    }:', 'if actual_stage_dirs != {"op_tail_round"}:'),
        ('"schema": "qlinearadd-node0007-fullchain-preflight-v38"', '"schema": "qlinearadd-node0007-tailround-split-preflight-v50"'),
        ('"stage_count": 6', '"stage_count": 1'),
        ('"schema": "qlinearadd-node0007-fullchain-installed-preflight-v38"', '"schema": "qlinearadd-node0007-tailround-split-installed-preflight-v50"'),
        ('starts == 6 and finishes == 6', 'starts == 1 and finishes == 1'),
        ('"schema": "qlinearadd-node0007-fullchain-server-result-v38"', '"schema": "qlinearadd-node0007-tailround-split-server-result-v50"'),
        ('"QLINEARADD_NODE0007_SERVER_PASS"', '"QLINEARADD_NODE0007_TAILROUND_SPLIT_PASS"'),
        ('"QLINEARADD_NODE0007_SERVER_FAILURE"', '"QLINEARADD_NODE0007_TAILROUND_SPLIT_FAILURE"'),
        ('"Full six-stage natural terminal plus final UINT8 28D exact "\n            "golden comparison; E4/E5 requires returned production identity "\n            "and mainline acceptance."', '"Isolated tail_round natural terminal plus stage-local UINT8 28D exact golden comparison; no upstream producer/barrier/lifetime/full-chain/E3/E4/E5 claim."'),
    ]
    for before, after in substitutions:
        if text.count(before) != 1:
            raise BuildError(f"runtime patch anchor differs: {before[:70]!r} count={text.count(before)}")
        text = text.replace(before, after, 1)
    target = package / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
    target.write_text(text, encoding="utf-8", newline="\n")
    old.unlink()


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    replacements = {
        "qlinearadd_node0007_fullchain_runtime_v38.py": "qlinearadd_node0007_tailround_split_runtime_v50.py",
        "qlinearadd_node0007_tailround_flow_canonical_v47.py": "qlinearadd_node0007_tailround_split_canonical_v50.py",
        "feature=QADD_TAILROUND_FLOW_V47": "feature=QADD_TAILROUND_SPLIT_V50",
        "time0_marker=QADD_TAILROUND_FLOW_V47": "time0_marker=QADD_TAILROUND_SPLIT_V50",
        " 8h ": " 2h ",
    }
    for old, new in replacements.items():
        if old not in text:
            raise BuildError(f"runner patch anchor absent: {old}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_observer(package: Path) -> None:
    path = package / "tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh"
    text = path.read_text(encoding="utf-8")
    if text.count("q47_stage_index == 6") != 2 or text.count("stage=6") != 1:
        raise BuildError("tail observer stage-six anchors differ")
    text = text.replace("q47_stage_index == 6", "q47_stage_index == 1")
    text = text.replace("stage=6", "stage=1")
    path.write_text(text, encoding="utf-8", newline="\n")


def make_sca(package: Path) -> tuple[list[dict[str, Any]], int]:
    full_sca = json.loads((PIPE / "sca_cfg.json").read_text(encoding="utf-8"))
    full_d = json.loads((PIPE / "sca_cfg_D.json").read_text(encoding="utf-8"))
    execplan = PIPE / "install/execplan_op_tail_round.txt"
    install = package / "workload/runtime/install"
    for child in list(install.iterdir()):
        if child.name not in {"cfg_pkg", "op_tail_round"}:
            if child.is_dir(): shutil.rmtree(child)
            else: child.unlink()
    cfg_pkg = install / "cfg_pkg"
    for path in list(cfg_pkg.iterdir()):
        if "op_tail_round" not in path.name:
            path.unlink()
    shutil.copy2(execplan, install / "execplan.txt")
    for path in list(install.glob("execplan_op_*.txt")):
        path.unlink()
    shutil.copy2(execplan, install / "execplan_op_tail_round.txt")
    sca: dict[str, Any] = {
        "Exec_Base": full_sca["Exec_Base"], "Exec_Length": 29,
        "ExecutionPlan": {"base_addr": full_sca["ExecutionPlan"]["base_addr"], "path": f"install/cfg_pkg/{TARGET}/install/execplan.txt"},
        "Repeat_Num": 1,
        "op_tail_round_config": {"base_addr": full_sca["op_tail_round_config"]["base_addr"], "path": f"install/cfg_pkg/{TARGET}/install/cfg_pkg/{next(cfg_pkg.iterdir()).name}"},
    }
    for slice_id in range(28):
        sca[f"op_tail_round_matrixA_slice{slice_id}"] = {
            "base_addr": f"0x{0x00A4C000 + slice_id * 0x02000000:08X}",
            "path": f"install/cfg_pkg/{TARGET}/install/op_tail_round/slice{slice_id:02d}/matrix_A_linearized_128bit.txt",
        }
    selected = {key: value for key, value in full_d.items() if key.startswith("op_tail_round_matrixD_slice")}
    if len(selected) != 28:
        raise BuildError("tail_round D count differs")
    checks = []
    for key, value in sorted(selected.items(), key=lambda row: int(re.search(r"slice(\d+)$", row[0]).group(1))):
        slice_id = int(re.search(r"slice(\d+)$", key).group(1))
        runtime_path = f"op_tail_round/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        value["path"] = f"install/codex_runs/{TARGET}/{{attempt}}/{runtime_path}"
        checks.append({"sca_key": key, "slice_id": slice_id, "runtime_path": runtime_path, "line_count": int(value["length"]), "decoded_bytes": int(value["length"]) * 16, "golden_path": f"validation/golden/slice{slice_id:02d}_Y_128bit.txt"})
    write_json(package / "workload/runtime/sca_cfg.json", sca)
    write_json(package / "workload/runtime/sca_cfg_D.json", selected)
    return checks, len([v for v in sca.values() if isinstance(v, dict)])


def update_manifest(package: Path, boundary: dict[str, Any], checks: list[dict[str, Any]], preload_count: int) -> None:
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "qlinearadd-node0007-tailround-split-server-package-v50",
        "install_name": TARGET, "package_id": TARGET, "candidate_release": False,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", "diagnostic_only": True,
        "evidence_level": "E2_LOCAL_ONLY", "simulation_timeout": "2h",
        "split_segment_contract": {
            "segment_id": "TAIL_ROUND", "stage_names": ["op_tail_round"], "expected_stage_count": 1,
            "final_stage": "op_tail_round", "payload_stage_dirs": ["op_tail_round"],
            "execution_form": "INDEPENDENT_SINGLE_STAGE", "boundary_mode": boundary["mode"],
            "host_precomputed_internal_tensor": True, "producer_evidence_claimed": False,
            "result_mode": "STAGE_LOCAL_NUMERIC_DIAGNOSTIC_28D", "exec_length": 29,
            "expected_preload_count": preload_count, "expected_output_count": 28,
            "output_checks": checks, "claim_boundary": boundary["claim_boundary"],
        },
        "boundary_input_contract": boundary,
        "source_assets": {
            "v49_source_zip": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": SOURCE_SHA},
            "v49_return_analysis": {"path": "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v49-return-analysis/report.json", "sha256": "6673ad508cd7c7799ec525adabeadd4c428f18f9237f2fb2a64a50849a610b2d"},
            "v50_config_build_receipt": {"path": BUILD_RECEIPT.relative_to(ROOT).as_posix(), "sha256": sha(BUILD_RECEIPT)},
            "v50_config_validation": {"path": VALIDATION.relative_to(ROOT).as_posix(), "sha256": sha(VALIDATION)},
        },
        "frozen_semantics": {"numeric": True, "W3_order": True, "six_qparams": True, "exact_uint8_tail": True, "golden_values": True, "functional_rtl_modified": False, "numeric_analysis_repeated": False, "workload_analysis_repeated": False},
        "observer_contract": {**manifest["observer_contract"], "stage_scope": "single op_tail_round", "canonical_parser": "package_tools/qlinearadd_node0007_tailround_split_canonical_v50.py", "qualified_counter_clock": "clk_sg", "snapshot_clock": "clk_db", "level_is_progress": False},
        "rule_receipts": {name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "current_match": True} for name, path in RULES.items()},
        "successor": {"source": SOURCE_ID, "source_sha256": SOURCE_SHA, "changed_surface": ["identity", "single-stage execplan/SCA", "honest diagnostic boundary stimulus", "tail_round COL config", "stage-one observer predicate", "decimal-safe canonical parser", "2h timeout"]},
        "final_zip_rule_self_audit": {"required": True, "status": "PENDING_EXACT_ZIP_AUDIT"},
        "provenance": {"analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3", "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d", "generator": Path(__file__).relative_to(ROOT).as_posix()},
        "release_gate_matrix": {"package_bootstrap_path_runtime": "blocking", "runner_compile_finalizer": "blocking", "package_local_hdl_changed_observer": "blocking", "materialized_config_changed_tail_round": "blocking", "observer_canonical_changed": "blocking", "return_result_conjunction": "blocking", "frozen_numeric_W3_golden": "receipt_reuse"},
    })
    manifest["files"] = records(package)
    write_json(manifest_path, manifest)


def update_path_budget(package: Path) -> None:
    contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    attempt = "a" * int(contract["path_budget"]["attempt_max_chars"])
    candidates = []
    for mount in contract["payload_mounts"]:
        for path in package.rglob("*"):
            if path.is_file():
                member = path.relative_to(package).as_posix()
                if member.startswith(mount["source_prefix"]): candidates.append(mount["runtime_prefix"] + member[len(mount["source_prefix"]):])
    candidates += [value.replace("{attempt}", attempt) for value in contract["runtime_roots"].values()]
    candidates += [value.replace("{attempt}", attempt) for value in contract["path_budget"]["additional_projected_paths"]]
    longest = max(candidates, key=lambda value: (len(value), value))
    root_max = int(contract["path_budget"]["declared_target_root_max_chars"])
    contract["path_budget"]["max_projected_absolute_path_chars"] = root_max + 1 + len(longest)
    write_json(contract_path, contract)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["path_length_budget"] = {"declared_target_root_max_chars": root_max, "longest_projected_relative_path": longest, "longest_projected_relative_path_chars": len(longest), "max_projected_absolute_path_chars": root_max + 1 + len(longest), "absolute_path_limit_chars": int(contract["path_budget"]["absolute_path_limit_chars"])}
    manifest["files"] = records(package)
    write_json(manifest_path, manifest)


def build_package(destination: Path) -> Path:
    package = extract(destination)
    replace_identity(package)
    boundary = materialize_boundary_inputs(package)
    checks, preload_count = make_sca(package)
    patch_runtime(package)
    shutil.copy2(CANONICAL, package / "package_tools/qlinearadd_node0007_tailround_split_canonical_v50.py")
    old_canonical = package / "package_tools/qlinearadd_node0007_tailround_flow_canonical_v47.py"
    if old_canonical.exists(): old_canonical.unlink()
    patch_runner(package)
    patch_observer(package)
    write_json(package / "diagnostics/tailround_split_boundary_contract.json", boundary)
    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 isolated tail_round v50\n\n"
        "Run: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "This is a DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX single-stage workload. Its FP32 input is an explicitly host-precomputed frozen diagnostic stimulus; it does not claim tail_mul execution, cross-stage barrier/lifetime, full-chain correctness, E3, E4 or E5. A pass must be followed by the corrected six-stage 28D full chain.\n",
        encoding="utf-8", newline="\n")
    update_manifest(package, boundary, checks, preload_count)
    update_path_budget(package)
    manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    manifest["files"] = records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)
    return package


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(f"{TARGET}/{path.relative_to(package).as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.create_system = 3; info.external_attr = (0o100644 & 0xFFFF) << 16; info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> int:
    if OUT_ZIP.exists() or (LOCAL / "build_receipt.json").exists():
        raise BuildError("fresh v50 package output required")
    LOCAL.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="q50a-") as first, tempfile.TemporaryDirectory(prefix="q50b-") as second:
        a = build_package(Path(first)); b = build_package(Path(second))
        za = Path(first) / f"{TARGET}.zip"; zb = Path(second) / f"{TARGET}.zip"
        deterministic_zip(a, za); deterministic_zip(b, zb)
        if sha(za) != sha(zb) or za.read_bytes() != zb.read_bytes():
            raise BuildError("deterministic double build differs")
        shutil.copy2(za, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{sha(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    receipt = {"schema": "qlinearadd-node0007-tailround-split-build-v50", "status": "BUILT_PENDING_FINAL_AUDIT", "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": sha(OUT_ZIP)}, "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": sha(sidecar)}, "deterministic_double_build": True, "diagnostic_stimulus_not_producer_evidence": True, "numeric_analysis_repeated": False, "server_action": False}
    write_json(LOCAL / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
