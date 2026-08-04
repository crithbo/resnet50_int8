from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, write_json


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_qadd_n7_bctrl_v24"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "71e14695c3025340987dba2fc0ffedd23e8e61d9bcb6eaec704de74c8e6928da"
RUNTIME_SOURCE = ROOT / "tools/qlinearadd_node0007_split_server_runtime_v25.py"
CANONICAL_SOURCE = ROOT / "tools/qlinearadd_node0007_split_canonical_v25.py"
CONTRACT = ROOT / "contracts/operator_config/qlinearadd_node0007_split_workload_v25.json"

RULES = {
    "generation_index": (
        ROOT / ".agents/rules/生成前必读索引.md",
        "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5",
    ),
    "common_operator": (
        ROOT / ".agents/rules/算子配置规则.md",
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ),
    "hardware_fields": (
        ROOT / ".agents/rules/NDP硬件字段语义.md",
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ),
    "server_package": (
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48",
    ),
    "qlinearadd": (
        ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
        "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f",
    ),
    "exact_tail": (
        ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    ),
}

SEGMENTS = {
    "A": {
        "install_name": "r5_qadd_n7_split_a_dequants_v26",
        "pipeline": ROOT
        / (
            "artifacts/operator_config_validation/"
            "r5-qlinearadd-node0007-split-workloads-v25-native2/"
            "segment_A/execplan/pipeline_output"
        ),
        "stages": ["op_a_dequant", "op_b_dequant"],
        "payload_dirs": ["op_a_dequant", "op_b_dequant"],
        "final_stage": "op_b_dequant",
        "execution_form": "INDEPENDENT_TWO_PRODUCER_PREFIX",
        "boundary_mode": "ORIGINAL_TYPED_EXTERNAL_INPUT",
        "timeout": "4h",
        "result_mode": "STAGE_LOCAL_STRUCTURAL",
    },
    "B": {
        "install_name": "r5_qadd_n7_split_b_reloc_v26",
        "pipeline": ROOT
        / (
            "artifacts/operator_config_validation/"
            "r5-qlinearadd-node0007-split-workloads-v25-native-b/"
            "execplan/pipeline_output"
        ),
        "stages": ["op_relocation_pad"],
        "payload_dirs": ["op_relocation_pad"],
        "final_stage": "op_relocation_pad",
        "execution_form": "INDEPENDENT_SINGLE_STAGE",
        "boundary_mode": "FROZEN_NONCOMPUTATIONAL_CONSTANT",
        "timeout": "2h",
        "result_mode": "STAGE_LOCAL_STRUCTURAL",
    },
    "C": {
        "install_name": "r5_qadd_n7_split_c_fp32_prefix_v26",
        "pipeline": ROOT
        / "artifacts/operator_config_validation/qn7v25cd/c/execplan/pipeline_output",
        "stages": [
            "op_a_dequant",
            "op_b_dequant",
            "op_relocation_pad",
            "op_fp32_add",
        ],
        "payload_dirs": [
            "op_a_dequant",
            "op_b_dequant",
            "op_relocation_pad",
        ],
        "final_stage": "op_fp32_add",
        "execution_form": "CUMULATIVE_PREFIX",
        "boundary_mode": "NO_INTERNAL_REPLAY_PREFIX_FALLBACK",
        "timeout": "8h",
        "result_mode": "STAGE_LOCAL_STRUCTURAL",
    },
    "D": {
        "install_name": "r5_qadd_n7_split_d_full_v26",
        "pipeline": ROOT
        / (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "r5_qadd_n7_dbuf_colpair_v18/workload/runtime"
        ),
        "stages": [
            "op_a_dequant",
            "op_b_dequant",
            "op_relocation_pad",
            "op_fp32_add",
            "op_tail_mul",
            "op_tail_round",
        ],
        "payload_dirs": [
            "op_a_dequant",
            "op_b_dequant",
            "op_relocation_pad",
        ],
        "final_stage": "op_tail_round",
        "execution_form": "FULL_CHAIN_FALLBACK",
        "boundary_mode": "ORIGINAL_TYPED_INPUT_FULL_CHAIN",
        "timeout": "12h",
        "result_mode": "FULL_NUMERIC_28D",
    },
}


class BuildError(ValueError):
    pass


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rule_ids(path: Path) -> list[str]:
    return sorted(set(re.findall(r"CDA-[A-Z0-9-]+", path.read_text(encoding="utf-8"))))


def normalize_runtime_path(value: str) -> str:
    pure = Path(value.replace("\\", "/"))
    parts = pure.parts
    if len(parts) >= 4 and parts[0:2] == ("install", "cfg_pkg"):
        return "/".join(parts[3:])
    return value


def namespace_sca(value: dict[str, Any], install_name: str) -> dict[str, Any]:
    prefix = f"install/cfg_pkg/{install_name}/"
    result = json.loads(json.dumps(value))
    for item in result.values():
        if (
            isinstance(item, dict)
            and isinstance(item.get("path"), str)
            and item["path"].startswith("install/")
        ):
            item["path"] = prefix + normalize_runtime_path(item["path"])
    return result


def output_checks(
    sca_d: dict[str, Any], final_stage: str, result_mode: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected = {
        key: value
        for key, value in sca_d.items()
        if key.startswith(final_stage + "_matrixD_slice")
    }
    if len(selected) != 28:
        raise BuildError(f"final stage output count differs: {final_stage}")
    checks: list[dict[str, Any]] = []
    for key, value in sorted(
        selected.items(), key=lambda item: int(re.search(r"slice(\d+)$", item[0]).group(1))
    ):
        runtime_path = normalize_runtime_path(str(value["path"]))
        check: dict[str, Any] = {
            "sca_key": key,
            "slice_id": int(re.search(r"slice(\d+)$", key).group(1)),
            "runtime_path": runtime_path,
            "line_count": int(value["length"]),
            "decoded_bytes": int(value["length"]) * 16,
        }
        if result_mode == "FULL_NUMERIC_28D":
            check["golden_path"] = (
                f"validation/golden/slice{check['slice_id']:02d}_Y_128bit.txt"
            )
        checks.append(check)
    return selected, checks


def patch_runner(package: Path, install_name: str, segment_id: str) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    replacements = {
        'runtime="$package_root/package_tools/qlinearadd_node0007_server_runtime.py"': (
            'runtime="$package_root/package_tools/'
            'qlinearadd_node0007_split_server_runtime_v25.py"'
        ),
        'decision_runtime="$package_root/package_tools/qlinearadd_progress_canonical_decision.py"': (
            'decision_runtime="$package_root/package_tools/'
            'qlinearadd_node0007_split_canonical_v25.py"'
        ),
        "feature=B_DEQUANT_BASE_OBSERVER_CONTROL": f"feature=QADD_SPLIT_{segment_id}",
        (
            'install_name="$(python3 "$runtime" manifest-value --package-root '
            '"$package_root" --key install_name)" || exit 5'
        ): (
            'install_name="$(python3 "$runtime" manifest-value --package-root '
            '"$package_root" --key install_name)" || exit 5\n'
            'simulation_timeout="$(python3 "$runtime" manifest-value '
            '--package-root "$package_root" --key simulation_timeout)" || exit 5'
        ),
        "printf 'timeout --foreground --signal=TERM --kill-after=30s 2h %q' \"$simv\"": (
            "printf 'timeout --foreground --signal=TERM --kill-after=30s %q %q' "
            '"$simulation_timeout" "$simv"'
        ),
        'timeout --foreground --signal=TERM --kill-after=30s 2h "$simv" "${sim_args[@]}" &': (
            'timeout --foreground --signal=TERM --kill-after=30s '
            '"$simulation_timeout" "$simv" "${sim_args[@]}" &'
        ),
        (
            "printf '# SIMULATION_NOT_STARTED_COMPILE_NOT_PASSED\\n' "
            '>"$run_root/sim_results/sim.log"'
        ): (
            "printf '# COMPILE_NOT_STARTED_OR_DRIVER_LOG_UNAVAILABLE\\n' "
            '>"$run_root/sim_results/compile.log"\n'
            "printf '# SIMULATION_NOT_STARTED_COMPILE_NOT_PASSED\\n' "
            '>"$run_root/sim_results/sim.log"'
        ),
    }
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise BuildError(f"runner preimage count differs for {old!r}: {text.count(old)}")
        text = text.replace(old, new)
    if SOURCE_NAME in text:
        text = text.replace(SOURCE_NAME, install_name)
    path.write_text(text, encoding="utf-8", newline="\n")


def return_allowlist(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = [
        ("evidence", "package_preflight.json", "evidence/package_preflight.json", True, 1 << 20),
        ("evidence", "installed_preflight.json", "evidence/installed_preflight.json", True, 1 << 20),
        ("evidence", "compile_exit_status.txt", "evidence/compile_exit_status.txt", True, 1 << 20),
        ("evidence", "simulation_exit_status.txt", "evidence/simulation_exit_status.txt", True, 1 << 20),
        ("evidence", "PACKAGE_MANIFEST.json", "evidence/PACKAGE_MANIFEST.json", True, 1 << 20),
        ("run", "sim_results/compile_driver.log", "runs/compile_driver.log", True, 16 << 20),
        ("run", "sim_results/compile.log", "runs/compile.log", True, 16 << 20),
        ("run", "sim_results/sim.log", "runs/sim.log", True, 64 << 20),
        ("evidence", "SERVER_RESULT_GATE.json", "evidence/SERVER_RESULT_GATE.json", True, 8 << 20),
        ("evidence", "progress_contract.json", "evidence/progress_contract.json", True, 1 << 20),
        ("evidence", "actual_simulator_argv.txt", "evidence/actual_simulator_argv.txt", True, 1 << 20),
        ("evidence", "host_timing.txt", "evidence/host_timing.txt", True, 1 << 20),
        ("evidence", "signal_status.txt", "evidence/signal_status.txt", True, 1 << 20),
        ("evidence", "progress_samples.log", "evidence/progress_samples.log", True, 8 << 20),
        ("evidence", "observer_binding.txt", "evidence/observer_binding.txt", True, 1 << 20),
        ("run", "sim_results/return_observer/return_observer.log", "runs/return_observer.log", True, 16 << 20),
        ("evidence", "actual_compile_argv.txt", "evidence/actual_compile_argv.txt", True, 1 << 20),
        ("evidence", "CANONICAL_PROGRESS_DECISION.json", "evidence/CANONICAL_PROGRESS_DECISION.json", True, 8 << 20),
        ("evidence", "canonical_decision_exit_status.txt", "evidence/canonical_decision_exit_status.txt", True, 1 << 20),
        ("evidence", "fp32_ingress_feature_receipt.txt", "evidence/split_feature_receipt.txt", True, 1 << 20),
    ]
    result = [
        {
            "source_root": source_root,
            "source_path": source_path,
            "target_path": target_path,
            "required": required,
            "max_bytes": max_bytes,
        }
        for source_root, source_path, target_path, required, max_bytes in entries
    ]
    for item in checks:
        result.append(
            {
                "source_root": "cfg",
                "source_path": item["runtime_path"],
                "target_path": "readbacks/" + item["runtime_path"],
                "required": True,
                "max_bytes": int(item["line_count"]) * 129 + 1024,
            }
        )
    return result


def build_directory(destination: Path, segment_id: str) -> Path:
    spec = SEGMENTS[segment_id]
    install_name = str(spec["install_name"])
    package = destination / install_name
    if package.exists():
        raise BuildError(f"destination exists: {package}")
    shutil.copytree(SOURCE_DIR, package)

    for child in (package / "workload").iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    runtime_root = package / "workload/runtime"
    install = runtime_root / "install"
    cfg_pkg = install / "cfg_pkg"
    cfg_pkg.mkdir(parents=True)
    for stage in spec["payload_dirs"]:
        shutil.copytree(
            SOURCE_DIR / "workload/runtime/install" / stage,
            install / stage,
        )
    pipeline = Path(spec["pipeline"])
    shutil.copy2(pipeline / "install/execplan.txt", install / "execplan.txt")
    for stage in spec["stages"]:
        shutil.copy2(
            pipeline / "install" / f"execplan_{stage}.txt",
            install / f"execplan_{stage}.txt",
        )
        bitstream = (
            pipeline
            / "install/cfg_pkg"
            / f"{stage}_resnet50_qadd_node0007_{stage.removeprefix('op_')}_bitstream_128b.bin"
        )
        if not bitstream.is_file():
            candidates = list(
                (pipeline / "install/cfg_pkg").glob(f"{stage}_*_bitstream_128b.bin")
            )
            if len(candidates) != 1:
                raise BuildError(f"bitstream not unique for {segment_id}/{stage}")
            bitstream = candidates[0]
        shutil.copy2(bitstream, cfg_pkg / bitstream.name)

    sca = json.loads((pipeline / "sca_cfg.json").read_text(encoding="utf-8"))
    if segment_id == "C":
        sca = {
            key: value
            for key, value in sca.items()
            if not key.startswith("op_fp32_add_matrix")
        }
    sca_d_raw = json.loads((pipeline / "sca_cfg_D.json").read_text(encoding="utf-8"))
    selected_d, checks = output_checks(
        sca_d_raw, str(spec["final_stage"]), str(spec["result_mode"])
    )
    write_json(runtime_root / "sca_cfg.json", namespace_sca(sca, install_name))
    write_json(runtime_root / "sca_cfg_D.json", namespace_sca(selected_d, install_name))

    validation = package / "validation"
    if segment_id != "D":
        shutil.rmtree(validation)

    tools_dir = package / "package_tools"
    for child in tools_dir.iterdir():
        child.unlink()
    shutil.copy2(RUNTIME_SOURCE, tools_dir / RUNTIME_SOURCE.name)
    shutil.copy2(CANONICAL_SOURCE, tools_dir / CANONICAL_SOURCE.name)
    patch_runner(package, install_name, segment_id)

    progress = {
        "schema": "qlinearadd-node0007-split-progress-contract-v25",
        "segment_id": segment_id,
        "stage_names": spec["stages"],
        "stage_count": len(spec["stages"]),
        "stall_window_cycles": 1_048_576,
        "heartbeat_cycles": 16_384,
        "host_sample_period_seconds": 60,
        "snapshot_clock": "clk_db",
        "counter_source_clock": "clk_sg",
        "qualified_internal_counters": [
            "base_req_accept",
            "base_rdata_accept",
            "base_wdata_accept",
            "base_buffer_write_read",
            "base_gexec_gconfig",
        ],
        "level_is_progress": False,
        "enabled_by_default": True,
        "feature_plusarg": "+RETURN_OBSERVER +RETURN_OBS_DEEP",
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
    }
    write_json(package / "diagnostics/progress_contract.json", progress)
    package.joinpath("README.md").write_text(
        f"# QLinearAdd node0007 split segment {segment_id} v25\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        f"Stages: {', '.join(spec['stages'])}. "
        f"Execution form: {spec['execution_form']}. "
        "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. A split result is localization "
        "evidence only and cannot close upstream production, cross-segment "
        "barrier/lifetime, E3, E4 or E5. Segment D retains the full six-stage "
        "plus 28-D numeric conjunction.\n",
        encoding="utf-8",
        newline="\n",
    )

    split_contract = {
        "segment_id": segment_id,
        "stage_names": spec["stages"],
        "expected_stage_count": len(spec["stages"]),
        "final_stage": spec["final_stage"],
        "payload_stage_dirs": spec["payload_dirs"],
        "execution_form": spec["execution_form"],
        "boundary_mode": spec["boundary_mode"],
        "host_precomputed_internal_tensor": False,
        "producer_evidence_claimed": False,
        "result_mode": spec["result_mode"],
        "exec_length": int(sca["Exec_Length"]),
        "expected_preload_count": len(sca) - 3,
        "expected_output_count": len(checks),
        "output_checks": checks,
        "claim_boundary": (
            "stage-local structural readback only"
            if spec["result_mode"] == "STAGE_LOCAL_STRUCTURAL"
            else "full six-stage plus 28-D numeric conjunction"
        ),
    }
    manifest = {
        "schema": "qlinearadd-node0007-split-server-package-v26",
        "install_name": install_name,
        "candidate_release": False,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "evidence_level": "E2_LOCAL_ONLY",
        "simulation_timeout": spec["timeout"],
        "split_segment_contract": split_contract,
        "source_assets": {
            "v24_source_zip": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_SHA,
                "immutable": True,
            },
            "split_contract": {
                "path": CONTRACT.relative_to(ROOT).as_posix(),
                "sha256": sha(CONTRACT),
            },
            "pipeline_output": {
                "path": pipeline.relative_to(ROOT).as_posix(),
                "execplan_sha256": sha(pipeline / "install/execplan.txt"),
            },
        },
        "frozen_semantics": {
            "numeric": True,
            "W3_order": True,
            "six_qparams": True,
            "exact_uint8_tail": True,
            "workload_values": True,
            "golden_values": True,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
        },
        "observer_contract": {
            "source": "tb_probe/native_return_observer.svh",
            "include_dir": "tb_probe",
            "enable_macro": "NATIVE_RETURN_OBSERVER_ENABLE",
            "runtime_plusargs": ["+RETURN_OBSERVER", "+RETURN_OBS_DEEP"],
            "time0_marker": "[RETURN_OBSERVER] enabled for slice",
            "return_target": "runs/return_observer.log",
            "snapshot_clock": "clk_db",
            "qualified_counter_clock": "clk_sg",
            "level_is_progress": False,
        },
        "return_allowlist": return_allowlist(checks),
        "budgets": {
            "return_zip_max_bytes": 512 << 20,
            "return_extracted_max_bytes": 1024 << 20,
        },
        "rule_receipts": {
            key: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": digest,
                "current_match": True,
                "applicable_rule_ids": rule_ids(path),
            }
            for key, (path, digest) in RULES.items()
        },
        "final_zip_rule_self_audit": {
            "required": True,
            "validator": (
                "tools/validate_qlinearadd_node0007_split_workloads_v25_server_packages.py"
            ),
            "report": (
                "artifacts/operator_config_validation/"
                f"r5-qlinearadd-node0007-split-{segment_id.lower()}-v26/"
                "final_zip_self_audit.json"
            ),
        },
        "provenance": {
            "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
            "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "generator": Path(__file__).relative_to(ROOT).as_posix(),
        },
    }
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)
    return package


def main() -> int:
    expected = {
        SOURCE_ZIP: SOURCE_SHA,
        **{path: digest for path, digest in RULES.values()},
    }
    drift = {
        str(path): {"expected": digest, "actual": sha(path) if path.is_file() else None}
        for path, digest in expected.items()
        if not path.is_file() or sha(path) != digest
    }
    if drift:
        print(f"immutable receipt drift: {drift}", file=sys.stderr)
        return 1
    receipts = {}
    try:
        for segment_id, spec in SEGMENTS.items():
            install_name = str(spec["install_name"])
            package = PACKAGE_ROOT / install_name
            output = PACKAGE_ROOT / f"{install_name}.zip"
            sidecar = Path(str(output) + ".sha256")
            validation = PACKAGE_ROOT / f"{install_name}.validation.json"
            for path in (package, output, sidecar, validation):
                if path.exists():
                    raise BuildError(f"refusing to overwrite: {path}")
            package = build_directory(PACKAGE_ROOT, segment_id)
            deterministic_zip(package, output)
            with tempfile.TemporaryDirectory(prefix=f"qadd-split-{segment_id}-") as raw:
                repeat_package = build_directory(Path(raw), segment_id)
                repeat_zip = Path(raw) / f"{install_name}.zip"
                deterministic_zip(repeat_package, repeat_zip)
                repeat_sha = sha(repeat_zip)
            digest = sha(output)
            if digest != repeat_sha:
                raise BuildError(f"deterministic rebuild differs: {segment_id}")
            sidecar.write_text(
                f"{digest}  {output.name}\n", encoding="ascii", newline="\n"
            )
            receipt = {
        "schema": "qlinearadd-node0007-split-build-v26",
                "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
                "segment_id": segment_id,
                "package": package.relative_to(ROOT).as_posix(),
                "zip": output.relative_to(ROOT).as_posix(),
                "zip_bytes": output.stat().st_size,
                "zip_sha256": digest,
                "sidecar": sidecar.relative_to(ROOT).as_posix(),
                "sidecar_sha256": sha(sidecar),
                "deterministic_rebuild_sha256": repeat_sha,
                "source_zip_sha256": SOURCE_SHA,
            }
            write_json(validation, receipt)
            receipts[segment_id] = receipt
    except Exception as exc:
        print(f"split package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
