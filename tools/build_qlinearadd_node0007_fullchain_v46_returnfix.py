"""Build the deterministic runner/return-evidence-only QAdd v46 successor."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_qadd_n7_fullchain_v45"
TARGET = "r5_qadd_n7_fullchain_returnfix_v46"
SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
SOURCE_SHA = (
    "913e6831d47b9673f4c50e0efe28ba95fce14a2b685278c9e19755c5797f113a"
)
OUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fullchain-v46-returnfix-package"
)
OUT_ZIP = OUT / f"{TARGET}.zip"
LIVENESS = ROOT / "tools/qlinearadd_process_liveness_snapshot_v46.py"
BASE_BUILDER = (
    ROOT / "tools/build_qlinearadd_node0007_fullchain_v38_server_package.py"
)

SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
INDEX_RULE = ROOT / ".agents/rules/生成前必读索引.md"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
TAIL_RULE = ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_extract(destination: Path) -> Path:
    if sha256(SOURCE) != SOURCE_SHA:
        raise BuildError("exact v45 source ZIP differs")
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise BuildError("source ZIP CRC failed")
        roots: set[str] = set()
        names: set[str] = set()
        for info in archive.infolist():
            name = info.filename
            value = PurePosixPath(name)
            if (
                value.is_absolute()
                or ".." in value.parts
                or "\\" in name
                or name in names
            ):
                raise BuildError(f"unsafe source member: {name}")
            names.add(name)
            roots.add(value.parts[0])
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise BuildError(f"source symlink forbidden: {name}")
        if roots != {SOURCE_NAME}:
            raise BuildError(f"source root differs: {sorted(roots)}")
        archive.extractall(destination)
    source_root = destination / SOURCE_NAME
    target_root = destination / TARGET
    source_root.rename(target_root)
    return target_root


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
            path.write_text(
                text.replace(SOURCE_NAME, TARGET),
                encoding="utf-8",
                newline="\n",
            )


def load_base_builder() -> Any:
    spec = importlib.util.spec_from_file_location("qadd_v45_builder", BASE_BUILDER)
    if spec is None or spec.loader is None:
        raise BuildError("cannot load v45 builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TARGET = TARGET
    return module


def corrected_runner() -> str:
    runner = load_base_builder().runner_text()
    runner = runner.replace(
        'attempt="a$$"\n',
        'attempt="a$$"\nrun_start_ns="$(date +%s%N)"\n',
        1,
    )
    new_sample = """sample_progress() {
  [ -n "$evidence_root" ] && [ -d "$evidence_root" ] || return 0
  host_ns="$(date +%s%N)"
  tail_line=NONE
  [ ! -s "$run_root/return_observer.log" ] || \\
    tail_line="$(tail -n 1 "$run_root/return_observer.log" | tr '\\t' ' ')"
  printf '%s\\t%s\\n' "$host_ns" "$tail_line" >>"$evidence_root/progress_samples.log"
  if [ "$sim_pid" -gt 0 ]; then
    python3 "$package_root/package_tools/qlinearadd_process_liveness_snapshot_v46.py" \\
      --root-pid "$sim_pid" --sim-log "$run_root/sim.log" \\
      --observer-log "$run_root/return_observer.log" \\
      >>"$evidence_root/process_liveness_samples.jsonl" 2>/dev/null || true
  fi
}"""
    sample_start = runner.find("sample_progress() {")
    sample_end = runner.find("progress_sampler() {", sample_start)
    if sample_start < 0 or sample_end < 0:
        raise BuildError("sample_progress source span differs")
    runner = runner[:sample_start] + new_sample + "\n" + runner[sample_end:]
    runner = runner.replace(
        """  set +e
  if [ "$sim_pid" -gt 0 ]""",
        """  set +e
  run_end_ns="$(date +%s%N)"
  if [ "$sim_pid" -gt 0 ]""",
        1,
    )
    runner = runner.replace(
        """    sample_progress
    printf '%s\\n' "$compile_status" >"$evidence_root/compile_exit_status.txt\"""",
        """    sample_progress
    printf 'run_start_ns=%s\\nrun_end_ns=%s\\n' "$run_start_ns" "$run_end_ns" \\
      >"$evidence_root/host_timing.txt"
    [ ! -f "$run_root/sim.log" ] || \\
      tail -c 16777216 "$run_root/sim.log" >"$evidence_root/sim_tail.log"
    [ ! -f "$run_root/return_observer.log" ] || \\
      tail -c 16777216 "$run_root/return_observer.log" \\
        >"$evidence_root/return_observer_tail.log"
    printf '%s\\n' "$compile_status" >"$evidence_root/compile_exit_status.txt\"""",
        1,
    )
    runner = runner.replace(
        """on_signal() {
  signal_name="$1"
  [ "$sim_pid" -le 0 ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}""",
        """on_signal() {
  signal_name="$1"
  [ "$simulation_status" -ne 125 ] || simulation_status="$2"
  [ "$sim_pid" -le 0 ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}""",
        1,
    )
    preflight_anchor = (
        'python3 "$runtime" preflight --package-root "$package_root"   '
        '>"$evidence_root/package_preflight.json" || exit 5\n'
    )
    if runner.count(preflight_anchor) != 1:
        raise BuildError("preflight insertion anchor differs")
    runner = runner.replace(
        preflight_anchor,
        preflight_anchor
        + 'cp "$package_root/TEST_PACKAGE_MANIFEST.json" '
        '"$evidence_root/PACKAGE_MANIFEST.json"\n',
        1,
    )
    feature_anchor = (
        "printf 'feature=QADD_FULLCHAIN_CAUSAL\\nargv_enabled=true\\n'   "
        '>"$evidence_root/feature_receipt.txt"\n'
    )
    if runner.count(feature_anchor) != 1:
        raise BuildError("feature insertion anchor differs")
    runner = runner.replace(
        feature_anchor,
        feature_anchor
        + "printf 'observer=tb_probe/native_return_observer.svh\\n"
        "macro=NATIVE_RETURN_OBSERVER_ENABLE\\nplusarg=RETURN_OBSERVER\\n' "
        '>"$evidence_root/observer_binding.txt"\n'
        + "printf 'timeout --foreground --signal=TERM --kill-after=30s 2h "
        "make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 "
        "DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=%s VCS_EXTRA_OPTS=%s\\n' "
        '"$compile_root" "+incdir+$package_root/tb_probe '
        '+define+NATIVE_RETURN_OBSERVER_ENABLE" '
        '>"$evidence_root/actual_compile_argv.txt"\n',
        1,
    )
    return runner


def allow(
    source_root: str,
    source_path: str,
    target_path: str,
    max_bytes: int = 1 << 20,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "source_root": source_root,
        "source_path": source_path,
        "target_path": target_path,
        "required": required,
        "max_bytes": max_bytes,
    }


def return_allowlist() -> list[dict[str, Any]]:
    rows = [
        allow("evidence", "package_preflight.json", "evidence/package_preflight.json"),
        allow(
            "evidence",
            "installed_preflight.json",
            "evidence/installed_preflight.json",
        ),
        allow("evidence", "PACKAGE_MANIFEST.json", "evidence/PACKAGE_MANIFEST.json", 1 << 20),
        allow("evidence", "compile_exit_status.txt", "evidence/compile_exit_status.txt"),
        allow(
            "evidence",
            "simulation_exit_status.txt",
            "evidence/simulation_exit_status.txt",
        ),
        allow("evidence", "signal_status.txt", "evidence/signal_status.txt"),
        allow("evidence", "host_timing.txt", "evidence/host_timing.txt"),
        allow("evidence", "actual_compile_argv.txt", "evidence/actual_compile_argv.txt"),
        allow(
            "evidence",
            "actual_simulator_argv.txt",
            "evidence/actual_simulator_argv.txt",
        ),
        allow("evidence", "observer_binding.txt", "evidence/observer_binding.txt"),
        allow("evidence", "feature_receipt.txt", "evidence/feature_receipt.txt"),
        allow("evidence", "progress_contract.json", "evidence/progress_contract.json"),
        allow(
            "evidence",
            "progress_samples.log",
            "evidence/progress_samples.log",
            8 << 20,
        ),
        allow(
            "evidence",
            "process_liveness_samples.jsonl",
            "evidence/process_liveness_samples.jsonl",
            8 << 20,
        ),
        allow(
            "evidence",
            "CANONICAL_PROGRESS_DECISION.json",
            "evidence/CANONICAL_PROGRESS_DECISION.json",
            8 << 20,
        ),
        allow(
            "evidence",
            "canonical_decision_exit_status.txt",
            "evidence/canonical_decision_exit_status.txt",
        ),
        allow(
            "evidence",
            "SERVER_RESULT_GATE.json",
            "evidence/SERVER_RESULT_GATE.json",
            8 << 20,
        ),
        allow(
            "evidence",
            "runtime_layout_receipt.json",
            "evidence/runtime_layout_receipt.json",
        ),
        allow(
            "evidence",
            "ndp_root_toplevel_pre.json",
            "evidence/ndp_root_toplevel_pre.json",
        ),
        allow(
            "evidence",
            "ndp_root_toplevel_post.json",
            "evidence/ndp_root_toplevel_post.json",
        ),
        allow(
            "evidence",
            "fixed_result_preflight.json",
            "evidence/fixed_result_preflight.json",
        ),
        allow(
            "evidence", "sim_tail.log", "runs/sim_tail.log", 16 << 20
        ),
        allow(
            "evidence",
            "return_observer_tail.log",
            "runs/return_observer_tail.log",
            16 << 20,
        ),
        allow(
            "run",
            "compile/sim_results/compile_driver.log",
            "runs/compile_driver.log",
            16 << 20,
        ),
        allow("run", "sim.log", "runs/sim.log", 64 << 20),
        allow(
            "run",
            "return_observer.log",
            "runs/return_observer.log",
            16 << 20,
        ),
        allow(
            "run",
            "compile/sim_results/compile.log",
            "runs/compile.log",
            16 << 20,
            required=False,
        ),
    ]
    for index in range(28):
        relative = (
            f"op_tail_round/slice{index:02d}/"
            "matrix_D_linearized_128bit.txt"
        )
        rows.append(
            allow(
                "run",
                relative,
                f"readbacks/{relative}",
                20 << 20,
            )
        )
    return rows


def file_records(package: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        relative = path.relative_to(package).as_posix()
        if relative == "TEST_PACKAGE_MANIFEST.json":
            continue
        rows[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return rows


def refresh_path_budget(package: Path, manifest: dict[str, Any]) -> None:
    contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    attempt = "a" * int(contract["path_budget"]["attempt_max_chars"])
    candidates = {
        f"install/cfg_pkg/{TARGET}/"
        + path.relative_to(package / "workload/runtime").as_posix()
        for path in (package / "workload/runtime").rglob("*")
        if path.is_file()
    }
    candidates.update(
        path.replace("{attempt}", attempt)
        for path in contract["path_budget"]["additional_projected_paths"]
    )
    candidates.update(
        path.replace("{attempt}", attempt)
        for path in contract["runtime_roots"].values()
    )
    longest = max(candidates, key=lambda value: (len(value), value))
    projected = (
        int(contract["path_budget"]["declared_target_root_max_chars"])
        + 1
        + len(longest)
    )
    contract["path_budget"]["max_projected_absolute_path_chars"] = projected
    write_json(contract_path, contract)
    manifest["path_length_budget"] = {
        "declared_target_root_max_chars": contract["path_budget"][
            "declared_target_root_max_chars"
        ],
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": projected,
        "absolute_path_limit_chars": contract["path_budget"][
            "absolute_path_limit_chars"
        ],
        "pass": projected <= int(
            contract["path_budget"]["absolute_path_limit_chars"]
        ),
    }
    if manifest["path_length_budget"]["pass"] is not True:
        raise BuildError(
            f"v46 projected path budget failed: {projected} > "
            f"{contract['path_budget']['absolute_path_limit_chars']}"
        )


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["install_name"] = TARGET
    value["return_allowlist"] = return_allowlist()
    value["candidate_release"] = False
    value["evidence_level"] = "E2_LOCAL_ONLY"
    value["runner_only_successor"] = {
        "source": SOURCE_NAME,
        "source_sha256": SOURCE_SHA,
        "config_workload_numeric_golden_observer_timeout_rtl_frozen": True,
        "changed": [
            "identity",
            "runner partial-return evidence generation",
            "return allowlist source paths",
            "process/log liveness snapshots",
        ],
    }
    value["return_contract_correction"] = {
        "source_report": (
            "artifacts/operator_config_validation/"
            "r5-qlinearadd-node0007-v45-return-analysis/report.json"
        ),
        "source_report_sha256": sha256(
            ROOT
            / "artifacts/operator_config_validation/"
            "r5-qlinearadd-node0007-v45-return-analysis/report.json"
        ),
        "corrected_compile_source": "run/compile/sim_results/compile_driver.log",
        "corrected_sim_source": "run/sim.log",
        "corrected_observer_source": "run/return_observer.log",
        "corrected_formal_D_source": "run/op_tail_round/sliceNN",
        "partial_signal_process_liveness": True,
    }
    value["provenance"]["generator"] = Path(__file__).relative_to(ROOT).as_posix()
    value["provenance"]["successor_reason"] = (
        "v45 formal HUP return proved stale split-C return allowlist paths and "
        "omitted source/log/liveness receipts; full-chain semantics are frozen"
    )
    value["rule_receipts"]["server"] = {
        "path": SERVER_RULE.relative_to(ROOT).as_posix(),
        "sha256": sha256(SERVER_RULE),
    }
    value["rule_receipts"]["generation_index"] = {
        "path": INDEX_RULE.relative_to(ROOT).as_posix(),
        "sha256": sha256(INDEX_RULE),
    }
    value["rule_receipts"]["qlinearadd"] = {
        "path": QADD_RULE.relative_to(ROOT).as_posix(),
        "sha256": sha256(QADD_RULE),
    }
    value["rule_receipts"]["exact_uint8_tail"] = {
        "path": TAIL_RULE.relative_to(ROOT).as_posix(),
        "sha256": sha256(TAIL_RULE),
    }
    value["final_zip_rule_self_audit"] = {
        "required": True,
        "status": "PENDING_EXACT_ZIP_AUDIT",
        "claim_boundary": "set by post-build audit only",
    }
    refresh_path_budget(package, value)
    value["files"] = file_records(package)
    write_json(path, value)


def update_package(package: Path) -> None:
    replace_identity(package)
    shutil.copy2(
        LIVENESS,
        package / "package_tools/qlinearadd_process_liveness_snapshot_v46.py",
    )
    (package / "PREPARE_AND_RUN.sh").write_text(
        corrected_runner(), encoding="utf-8", newline="\n"
    )
    readme = package / "README.md"
    readme.write_text(
        "# QLinearAdd node0007 full-chain return-fix v46\n\n"
        "Fresh runner/return-evidence-only successor to v45. Six-stage "
        "configuration, workload, numeric order, qparams, exact tail, golden, "
        "observer, 8h timeout and functional RTL are frozen.\n\n"
        f"Run: `bash {TARGET}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        f"Return: `/home/panqs/ndp/simresult/{TARGET}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package)


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = (
                f"{TARGET}/{path.relative_to(package).as_posix()}"
            )
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> int:
    if OUT_ZIP.exists() or (OUT / "build_receipt.json").exists():
        raise BuildError(f"fresh output exists: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="q46a-") as first, tempfile.TemporaryDirectory(
        prefix="q46b-"
    ) as second:
        package_a = safe_extract(Path(first))
        package_b = safe_extract(Path(second))
        update_package(package_a)
        update_package(package_b)
        zip_a = Path(first) / f"{TARGET}.zip"
        zip_b = Path(second) / f"{TARGET}.zip"
        deterministic_zip(package_a, zip_a)
        deterministic_zip(package_b, zip_b)
        if zip_a.read_bytes() != zip_b.read_bytes():
            raise BuildError("deterministic double build differs")
        shutil.copy2(zip_a, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    digest = sha256(OUT_ZIP)
    sidecar.write_text(
        f"{digest}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "qlinearadd-node0007-fullchain-v46-returnfix-build-v1",
        "status": "BUILT_PENDING_FINAL_AUDIT",
        "zip": {
            "path": OUT_ZIP.relative_to(ROOT).as_posix(),
            "bytes": OUT_ZIP.stat().st_size,
            "sha256": digest,
        },
        "sidecar_sha256": sha256(sidecar),
        "source_v45_sha256": SOURCE_SHA,
        "deterministic_double_build": True,
        "numeric_workload_config_golden_observer_timeout_rtl_repeated": False,
        "server_action": False,
    }
    write_json(OUT / "build_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
