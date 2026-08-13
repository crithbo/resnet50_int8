"""Analyze the formal QLinearAdd node0007 full-chain v45 return.

This analyzer is deliberately return-bound.  It does not replay numeric,
workload, configuration, or golden generation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN = Path(
    r"C:\Users\15383\Downloads\r5_qadd_n7_fullchain_v45_return.zip"
)
SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_qadd_n7_fullchain_v45.zip"
)
OUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-v45-return-analysis"
)
EXTRACT = OUT / "extracted_return"
REPORT = OUT / "report.json"

EXPECTED_RETURN_SHA = (
    "3e0404ee7a88429859fc19bc275866d070a1a11c16faf9a21162be08a3f322f3"
)
EXPECTED_SOURCE_SHA = (
    "913e6831d47b9673f4c50e0efe28ba95fce14a2b685278c9e19755c5797f113a"
)
EXPECTED_INSTALL = "r5_qadd_n7_fullchain_v45"

RULE_FILES = {
    "agent": ".agents/agent.md",
    "plan_mutable": ".agents/plan.md",
    "generation_index": ".agents/rules/生成前必读索引.md",
    "server": ".agents/rules/服务器测试包生成规则.md",
    "common_config": ".agents/rules/算子配置规则.md",
    "ndp_fields": ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ".agents/rules/精确UINT8量化尾专项规则.md",
    "server_readme": "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def safe_name(name: str) -> bool:
    value = PurePosixPath(name)
    return (
        bool(value.parts)
        and not value.is_absolute()
        and ".." not in value.parts
        and "\\" not in name
        and not name.startswith("/")
    )


def zip_inventory(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    names: set[str] = set()
    roots: set[str] = set()
    duplicates: list[str] = []
    unsafe: list[str] = []
    symlinks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        for info in archive.infolist():
            name = info.filename
            if name in names:
                duplicates.append(name)
            names.add(name)
            if not safe_name(name):
                unsafe.append(name)
            roots.add(PurePosixPath(name).parts[0])
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(name)
            payload = archive.read(info)
            rows.append(
                {
                    "path": name,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "crc32": f"{info.CRC:08x}",
                }
            )
    return {
        "crc_pass": bad_crc is None,
        "bad_crc_member": bad_crc,
        "entry_count": len(rows),
        "roots": sorted(roots),
        "duplicates": duplicates,
        "unsafe_paths": unsafe,
        "symlinks": symlinks,
        "entries": rows,
    }


def load_return() -> tuple[zipfile.ZipFile, str]:
    archive = zipfile.ZipFile(RETURN)
    roots = {PurePosixPath(name).parts[0] for name in archive.namelist()}
    if len(roots) != 1:
        raise ValueError(f"return root count differs: {sorted(roots)}")
    return archive, next(iter(roots)) + "/"


def read_json(archive: zipfile.ZipFile, root: str, relative: str) -> Any:
    return json.loads(archive.read(root + relative).decode("utf-8"))


def source_manifest() -> tuple[dict[str, Any], str]:
    with zipfile.ZipFile(SOURCE) as archive:
        root = archive.namelist()[0].split("/", 1)[0] + "/"
        raw = archive.read(root + "TEST_PACKAGE_MANIFEST.json")
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def main() -> int:
    global RETURN, SOURCE, OUT, EXTRACT, REPORT
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=RETURN)
    parser.add_argument("--source-zip", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    RETURN = args.return_zip.resolve()
    SOURCE = args.source_zip.resolve()
    OUT = args.out.resolve()
    EXTRACT = OUT / "extracted_return"
    REPORT = OUT / "report.json"

    OUT.mkdir(parents=True, exist_ok=True)
    if EXTRACT.exists():
        shutil.rmtree(EXTRACT)
    EXTRACT.mkdir(parents=True)

    return_inventory = zip_inventory(RETURN)
    source_inventory = zip_inventory(SOURCE)
    return_sha = sha256(RETURN)
    source_sha = sha256(SOURCE)

    archive, root = load_return()
    with archive:
        archive.extractall(EXTRACT)
        manifest = read_json(archive, root, "RETURN_MANIFEST.json")
        canonical = read_json(
            archive, root, "evidence/CANONICAL_PROGRESS_DECISION.json"
        )
        gate = read_json(archive, root, "evidence/SERVER_RESULT_GATE.json")
        package_preflight = read_json(
            archive, root, "evidence/package_preflight.json"
        )
        installed_preflight = read_json(
            archive, root, "evidence/installed_preflight.json"
        )
        runtime_layout = read_json(
            archive, root, "evidence/runtime_layout_receipt.json"
        )
        progress_lines = (
            archive.read(root + "evidence/progress_samples.log")
            .decode("utf-8", errors="replace")
            .splitlines()
        )
        compile_status = int(
            archive.read(root + "evidence/compile_exit_status.txt").strip()
        )
        simulation_status = int(
            archive.read(root + "evidence/simulation_exit_status.txt").strip()
        )
        signal = (
            archive.read(root + "evidence/signal_status.txt")
            .decode("ascii")
            .strip()
        )
        actual_argv = (
            archive.read(root + "evidence/actual_simulator_argv.txt")
            .decode("utf-8")
            .strip()
        )

        returned_files = {
            row["path"]: row
            for row in manifest.get("files", [])
            if isinstance(row, dict) and isinstance(row.get("path"), str)
        }
        actual_relative = {
            name.removeprefix(root)
            for name in archive.namelist()
            if name != root + "RETURN_MANIFEST.json"
        }
        per_file_errors: list[str] = []
        for relative, row in returned_files.items():
            member = root + relative
            if member not in archive.namelist():
                per_file_errors.append(f"missing member: {relative}")
                continue
            payload = archive.read(member)
            if len(payload) != int(row["size_bytes"]):
                per_file_errors.append(f"size mismatch: {relative}")
            if hashlib.sha256(payload).hexdigest() != row["sha256"]:
                per_file_errors.append(f"sha mismatch: {relative}")
        exact_set = actual_relative == set(returned_files)

    source, source_manifest_sha = source_manifest()
    source_allowlist = source["return_allowlist"]
    missing_required = list(manifest.get("required_missing", []))
    stale_paths = {
        "compile_driver": {
            "declared": "run/sim_results/compile_driver.log",
            "actual_runner": "compile/sim_results/compile_driver.log",
        },
        "simulation_log": {
            "declared": "run/sim_results/sim.log",
            "actual_runner": "run/sim.log",
        },
        "observer_log": {
            "declared": "run/sim_results/return_observer/return_observer.log",
            "actual_runner": "run/return_observer.log",
        },
        "formal_D": {
            "declared": "cfg/install/op_fp32_add/sliceNN/...",
            "actual_contract": "run/op_tail_round/sliceNN/...",
        },
    }

    numeric_timestamps: list[int] = []
    deep_timestamps: list[int] = []
    deep_sim_times: list[int] = []
    for line in progress_lines:
        first, _, rest = line.partition("\t")
        if first.isdigit():
            numeric_timestamps.append(int(first))
            if "DEEP_MSE4_INDEX" in rest:
                deep_timestamps.append(int(first))
                token = rest.split("|", 1)[0].strip()
                if token.isdigit():
                    deep_sim_times.append(int(token))
    wall_seconds = (
        (numeric_timestamps[-1] - numeric_timestamps[0]) / 1e9
        if len(numeric_timestamps) >= 2
        else None
    )
    frozen_deep_seconds = (
        (deep_timestamps[-1] - deep_timestamps[0]) / 1e9
        if len(deep_timestamps) >= 2
        else None
    )

    rule_receipts = {}
    for key, relative in RULE_FILES.items():
        path = ROOT / relative
        rule_receipts[key] = {
            "path": relative,
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path) if path.is_file() else None,
        }

    source_binding = {
        "expected_source_zip_sha256": EXPECTED_SOURCE_SHA,
        "actual_source_zip_sha256": source_sha,
        "source_zip_match": source_sha == EXPECTED_SOURCE_SHA,
        "source_zip_crc_pass": source_inventory["crc_pass"],
        "source_manifest_sha256": source_manifest_sha,
        "source_install_name": source.get("install_name"),
        "return_install_name": manifest.get("install_name"),
        "actual_argv_install_name_match": EXPECTED_INSTALL in actual_argv,
        "install_identity_match": (
            source.get("install_name")
            == manifest.get("install_name")
            == EXPECTED_INSTALL
        ),
        "byte_binding_return_receipt_present": (
            "evidence/PACKAGE_MANIFEST.json" in returned_files
        ),
        "byte_binding_status": (
            "PROVEN"
            if "evidence/PACKAGE_MANIFEST.json" in returned_files
            else "UNPROVEN_IN_PARTIAL_RETURN"
        ),
    }

    report = {
        "schema": "qlinearadd-node0007-v45-return-analysis-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "status": "PARTIAL_INTERRUPTED_EXTERNAL_HUP_WITH_PACKAGE_RETURN_CONTRACT_DEFECT",
        "numeric_analysis_repeated": False,
        "workload_config_golden_repeated": False,
        "return": {
            "path": str(RETURN),
            "bytes": RETURN.stat().st_size,
            "sha256": return_sha,
            "expected_sha256": EXPECTED_RETURN_SHA,
            "hash_match": return_sha == EXPECTED_RETURN_SHA,
            "adjacent_sidecar_present": Path(str(RETURN) + ".sha256").is_file(),
            "transport_policy": (
                "USER_ATTESTED_NO_SIDECAR; external sidecar only is waived"
            ),
            "inventory": return_inventory,
            "internal_root": root.rstrip("/"),
            "manifest_exact_set": exact_set,
            "manifest_per_file_errors": per_file_errors,
            "allowlist_only": manifest.get("allowlist_only"),
            "manifest_status": manifest.get("status"),
            "required_missing_count": len(missing_required),
            "required_missing": missing_required,
        },
        "source_binding": source_binding,
        "package_preflight": package_preflight,
        "installed_preflight": installed_preflight,
        "runtime_layout": {
            "root_exact_set_unchanged": runtime_layout.get(
                "root_exact_set_unchanged"
            ),
            "unknown_items_deleted_or_overwritten": runtime_layout.get(
                "unknown_items_deleted_or_overwritten"
            ),
            "attempt": runtime_layout.get("attempt"),
            "run_root": runtime_layout.get("run_root"),
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "signal": signal,
            "natural_terminal": False,
            "actual_simulator_argv": actual_argv,
            "ordered_expected_stage_count": 6,
            "observed_start_count": canonical["ordered_final_scope"][
                "observed_start_count"
            ],
            "observed_finish_count": canonical["ordered_final_scope"][
                "observed_finish_count"
            ],
            "wall_sample_count": len(progress_lines),
            "wall_sample_span_seconds": wall_seconds,
            "deep_repeated_level_sample_count": len(deep_timestamps),
            "deep_repeated_level_span_seconds": frozen_deep_seconds,
            "deep_sim_time_unique": sorted(set(deep_sim_times)),
            "qualified_progress_evaluable": False,
            "qualified_progress_reason": (
                "return omitted raw observer log; repeated DEEP_MSE4_INDEX is "
                "a level sample and cannot count as progress"
            ),
            "canonical_decision": canonical,
        },
        "formal_D": {
            "expected": gate.get("expected_readback_count"),
            "present": gate.get("observed_readback_count"),
            "missing": gate.get("missing_count"),
            "invalid": gate.get("invalid_count"),
            "mismatch_byte_count": gate.get("mismatch_byte_count"),
            "mismatch_evaluable": gate.get("mismatch_evaluable"),
            "result_conjunction_all_terms_true": gate[
                "result_gate_conjunction"
            ]["all_terms_true"],
        },
        "last_proven_good": (
            "PACKAGE_AND_INSTALLED_PREFLIGHT_PASS__COMPILE_EXIT_0__"
            "SIMULATOR_ARGV_LAUNCHED__OP_A_DEQUANT_EXEC_START"
        ),
        "first_divergence": (
            "AFTER_OP_A_DEQUANT_EXEC_START_BEFORE_FIRST_PROVEN_"
            "QUALIFIED_PROGRESS_OR_COMP_FINISH__EXTERNAL_HUP"
        ),
        "hang_root_cause": {
            "status": "NOT_UNIQUELY_PROVEN",
            "bounded_interval": (
                "op_a_dequant EXEC_START -> first qualified internal progress/"
                "COMP_FINISH"
            ),
            "facts": [
                "compile succeeded",
                "simulation was launched",
                "one stage start and zero stage finishes were observed",
                "host sampler ran for about 80 minutes",
                "the last about 43 minutes repeated one unchanged MSE4 level",
                "HUP ended the run before natural terminal",
            ],
            "not_proven": [
                "DUT/config/RTL failure",
                "continued qualified progress",
                "simulator process liveness during the frozen samples",
                "exact first stalled handshake",
            ],
        },
        "package_contract_defect": {
            "proven": True,
            "classification": (
                "PACKAGE_RETURN_ALLOWLIST_AND_EARLY_FINALIZER_SOURCE_PATH_DRIFT"
            ),
            "source_allowlist_count": len(source_allowlist),
            "stale_path_examples": stale_paths,
            "never_generated_required_receipts": [
                "evidence/PACKAGE_MANIFEST.json",
                "evidence/host_timing.txt",
                "evidence/observer_binding.txt",
                "evidence/actual_compile_argv.txt",
                "evidence/split_feature_receipt.txt",
            ],
            "impact": (
                "The partial return cannot byte-bind the source package, "
                "localize qualified progress, or ever collect the declared "
                "final op_tail_round 28D exact set. This is independent of "
                "the unproven DUT hang root cause."
            ),
        },
        "evidence_levels": {
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": (
                "HUP/non-natural terminal, incomplete return, formal D 0/28"
            ),
        },
        "blocker_delta": {
            "open": [
                "B_QADD_V45_EXTERNAL_HUP_BEFORE_NATURAL_TERMINAL",
                "B_QADD_V45_FIRST_STAGE_QUALIFIED_PROGRESS_UNOBSERVED",
            ],
            "newly_proven_package_blocker": (
                "B_QADD_V45_RETURN_ALLOWLIST_SOURCE_PATH_DRIFT"
            ),
            "not_opened": [
                "numeric mismatch",
                "configuration failure",
                "functional RTL failure",
            ],
        },
        "successor": {
            "required": True,
            "scope": "RUNNER_AND_RETURN_EVIDENCE_ONLY",
            "frozen": (
                "full six-stage config/workload/numeric/W3/qparams/tail/"
                "golden/observer/timeout/functional RTL"
            ),
            "required_corrections": [
                "exact source/package byte binding in partial and full return",
                "correct compile/sim/observer source paths",
                "final op_tail_round 28D source paths",
                "host timing and simulator child liveness/CPU/log-growth receipt",
                "trap-safe HUP/INT/TERM collection of bounded logs and canonical",
            ],
        },
        "rule_confirmation": {
            "status": "CONFIRMED",
            "statement": (
                "User-attested transport only waives the adjacent sidecar; "
                "partial return and result conjunction correctly remain "
                "fail-closed. Continuous closure requires a fresh evidence-"
                "correct successor without changing frozen QAdd semantics."
            ),
        },
        "rule_receipts": rule_receipts,
    }

    if report["return"]["hash_match"] is not True:
        raise ValueError("return SHA differs")
    if source_binding["source_zip_match"] is not True:
        raise ValueError("source SHA differs")
    if not (
        return_inventory["crc_pass"]
        and not return_inventory["duplicates"]
        and not return_inventory["unsafe_paths"]
        and not return_inventory["symlinks"]
        and exact_set
        and not per_file_errors
    ):
        raise ValueError("return integrity gate failed")
    if compile_status != 0 or signal != "HUP" or simulation_status != 125:
        raise ValueError("unexpected execution tuple")

    REPORT.write_bytes(json_bytes(report))
    print(
        json.dumps(
            {
                "report": str(REPORT.relative_to(ROOT)),
                "bytes": REPORT.stat().st_size,
                "sha256": sha256(REPORT),
                "status": report["status"],
                "required_missing": len(missing_required),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
