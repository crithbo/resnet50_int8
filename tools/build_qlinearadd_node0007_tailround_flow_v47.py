"""Build the deterministic QAdd v47 tail-round flow diagnostic successor."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_qadd_n7_fullchain_returnfix_v46"
TARGET = "r5_qadd_n7_tailround_flow_v47"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_fullchain_returnfix_v46.zip"
SOURCE_SHA = "8c015af623b5b12f924c2ce9e85b5bff708d97e6372d68af565890b498b4fab1"
FUNCTIONAL_SHA = "58f5204886fef6015501dedc7e4443936c8ba118be248d12c102b46bf5afa3c5"
ANALYSIS = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-v46-recovered-return-analysis/report.json"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v47-package"
OUT_ZIP = OUT / f"{TARGET}.zip"
TAIL = ROOT / "tools/qlinearadd_node0007_tailround_flow_tail_v47.svh"
CANONICAL = ROOT / "tools/qlinearadd_node0007_tailround_flow_canonical_v47.py"
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def safe_extract(destination: Path) -> Path:
    if sha256(SOURCE) != SOURCE_SHA:
        raise BuildError("exact repeatable v46 source differs")
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise BuildError("source CRC failed")
        names: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or info.filename in names or stat.S_ISLNK(mode):
                raise BuildError(f"unsafe source member: {info.filename}")
            names.add(info.filename)
            roots.add(pure.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"source root differs: {sorted(roots)}")
        archive.extractall(destination)
    source = destination / SOURCE_NAME
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
        if SOURCE_NAME in text:
            path.write_text(text.replace(SOURCE_NAME, TARGET), encoding="utf-8", newline="\n")


def patch_wrapper(package: Path) -> None:
    path = package / "package_tools/qlinearadd_node0007_fullchain_runtime_v38.py"
    text = path.read_text(encoding="utf-8")
    anchor = '    collect.add_argument("--run-root", type=Path, required=True)\n'
    if text.count(anchor) != 1:
        raise BuildError("collect parser anchor differs")
    text = text.replace(anchor, anchor + '    collect.add_argument("--cfg-root", type=Path, required=True)\n    collect.add_argument("--return-zip", type=Path, required=True)\n', 1)
    old = """                        args.run_root,
                        args.run_root,
                    )"""
    new = """                        args.run_root,
                        args.cfg_root,
                        args.return_zip,
                    )"""
    if text.count(old) != 1:
        raise BuildError("base.collect argument anchor differs")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def patch_observer(package: Path) -> None:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    marker = '$fdisplay(\n                        return_obs_fd,\n                        "# Native NDP return observer v4"\n                    );'
    if text.count(marker) != 1:
        raise BuildError("observer time0 marker anchor differs")
    text = text.replace(marker, marker + '\n                    $fdisplay(return_obs_fd, "# QADD_TAILROUND_FLOW_V47");', 1)
    include = '`include "qlinearadd_node0007_tailround_flow_tail_v47.svh"'
    if include in text:
        raise BuildError("v47 include already present")
    text = text.rstrip() + "\n\n" + include + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    shutil.copy2(TAIL, package / "tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh")


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old = 'python3 "$package_root/package_tools/qlinearadd_node0007_split_canonical_v25.py"       --observer-log "$run_root/return_observer.log"       --progress-contract "$evidence_root/progress_contract.json"       --output "$evidence_root/CANONICAL_PROGRESS_DECISION.json"'
    new = 'python3 "$package_root/package_tools/qlinearadd_node0007_tailround_flow_canonical_v47.py"       --observer-log "$run_root/return_observer.log"       --output "$evidence_root/CANONICAL_PROGRESS_DECISION.json"'
    if text.count(old) != 1:
        raise BuildError("canonical invocation anchor differs")
    text = text.replace(old, new, 1)
    old_collect = '--evidence-root "$evidence_root" --run-root "$run_root" --return-zip "$return_zip"'
    new_collect = '--evidence-root "$evidence_root" --run-root "$run_root" --cfg-root "$cfg_root" --return-zip "$return_zip"'
    if text.count(old_collect) != 1:
        raise BuildError("collector invocation anchor differs")
    text = text.replace(old_collect, new_collect, 1)
    feature = "printf 'feature=QADD_FULLCHAIN_CAUSAL\\nargv_enabled=true\\n'"
    replacement = "printf 'feature=QADD_TAILROUND_FLOW_V47\\nargv_enabled=true\\ntime0_marker=QADD_TAILROUND_FLOW_V47\\n'"
    if text.count(feature) != 1:
        raise BuildError("feature receipt anchor differs")
    text = text.replace(feature, replacement, 1)
    observer = "printf 'observer=tb_probe/native_return_observer.svh\\nmacro=NATIVE_RETURN_OBSERVER_ENABLE\\nplusarg=RETURN_OBSERVER\\n'"
    replacement_observer = "printf 'observer=tb_probe/native_return_observer.svh\\ntail=tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh\\nmacro=NATIVE_RETURN_OBSERVER_ENABLE\\nplusarg=RETURN_OBSERVER\\n'"
    if text.count(observer) != 1:
        raise BuildError("observer binding anchor differs")
    path.write_text(text.replace(observer, replacement_observer, 1), encoding="utf-8", newline="\n")


def file_records(package: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        relative = path.relative_to(package).as_posix()
        if relative != "TEST_PACKAGE_MANIFEST.json":
            rows[relative] = {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
    return rows


def update_package(package: Path) -> None:
    replace_identity(package)
    patch_wrapper(package)
    patch_observer(package)
    patch_runner(package)
    shutil.copy2(CANONICAL, package / "package_tools/qlinearadd_node0007_tailround_flow_canonical_v47.py")
    matrix = json.loads(ANALYSIS.read_text(encoding="utf-8"))["SUCCESSOR_PROPOSAL"]["candidate_observation_matrix"]
    write_json(package / "diagnostics/tailround_candidate_observation_matrix.json", {"schema": "qadd-tailround-candidate-observation-matrix-v47", "rows": matrix})
    write_json(package / "diagnostics/progress_contract.json", {"schema": "qadd-tailround-progress-contract-v47", "stage_names": ["op_a_dequant", "op_b_dequant", "op_relocation_pad", "op_fp32_add", "op_tail_mul", "op_tail_round"], "stall_window_cycles": 1048576, "qualified_source_clock": "clk_sg", "snapshot_clock": "clk_db", "level_is_progress": False, "triggered_causal_observability": True})
    readme = package / "README.md"
    readme.write_text("# QLinearAdd node0007 tail-round flow v47\n\nDIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX successor. Six-stage config, workload, numeric/W3/qparams/tail/golden, 8h timeout and functional RTL are byte-frozen from repeatable v46. It corrects the collector recovery interface and replaces level-derived progress with stage-local qualified tail-round flow counters.\n\nRun: `bash r5_qadd_n7_tailround_flow_v47/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\nFixed return root: `/home/panqs/ndp/simresult`.\n", encoding="utf-8", newline="\n")
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET
    manifest["candidate_release"] = False
    manifest["evidence_level"] = "E2_LOCAL_ONLY"
    manifest["diagnostic_only"] = True
    manifest["successor"] = {"source": SOURCE_NAME, "source_sha256": SOURCE_SHA, "frozen_functional_source_sha256": FUNCTIONAL_SHA, "return_analysis": ANALYSIS.relative_to(ROOT).as_posix(), "return_analysis_sha256": sha256(ANALYSIS), "functional_assets_frozen": True, "changed_surface": ["package-local observer tail", "canonical predicate", "collector wrapper interface", "identity/manifest/README"]}
    manifest["observer_contract"]["tailround_flow_v47"] = {"source_clock": "clk_sg", "snapshot_clock": "clk_db", "qualified_event_budget_separate_from_state": True, "stable_level_is_progress": False, "candidate_matrix": "diagnostics/tailround_candidate_observation_matrix.json"}
    manifest["rule_receipts"] = {name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for name, path in RULES.items()}
    manifest["final_zip_rule_self_audit"] = {"required": True, "status": "PENDING_EXACT_ZIP_AUDIT"}
    manifest["provenance"]["generator"] = Path(__file__).relative_to(ROOT).as_posix()
    manifest["provenance"]["analysis_owner_thread"] = "019fa2c0-b647-7a91-93bf-d21a173487e3"
    manifest["provenance"]["return_target_thread"] = "019fbec2-fe93-7e03-9314-cff6f222f33d"
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{TARGET}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> int:
    if OUT_ZIP.exists() or (OUT / "build_receipt.json").exists():
        raise BuildError(f"fresh output exists: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="q47a-") as first, tempfile.TemporaryDirectory(prefix="q47b-") as second:
        a = safe_extract(Path(first)); b = safe_extract(Path(second))
        update_package(a); update_package(b)
        za = Path(first) / f"{TARGET}.zip"; zb = Path(second) / f"{TARGET}.zip"
        deterministic_zip(a, za); deterministic_zip(b, zb)
        if za.read_bytes() != zb.read_bytes():
            raise BuildError("deterministic double build differs")
        shutil.copy2(za, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{sha256(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    receipt = {"schema": "qadd-tailround-flow-v47-build-v1", "status": "BUILT_PENDING_FINAL_AUDIT", "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": sha256(OUT_ZIP)}, "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": sha256(sidecar)}, "source_sha256": SOURCE_SHA, "frozen_functional_source_sha256": FUNCTIONAL_SHA, "deterministic_double_build": True, "numeric_workload_config_golden_repeated": False, "server_action": False}
    write_json(OUT / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
