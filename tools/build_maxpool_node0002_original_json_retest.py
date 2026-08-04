"""Build a deterministic server retest package for the immutable MaxPool JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "maxpool_node0002_original_json_fresh_v3"
OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
OUTPUT_ZIP = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
OUTPUT_SIDECAR = OUTPUT_ROOT / f"{INSTALL_NAME}.zip.sha256"
VALIDATION_RECEIPT = OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
SOURCE_JSON = (
    ROOT / "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json"
)
SOURCE_JSON_SHA256 = (
    "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
)
RUNTIME_SOURCE = ROOT / "tools/maxpool_node0002_original_json_server_runtime.py"
PROFILE_RULE = "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.maxpool_node0002_original_json_server_runtime import (  # noqa: E402
    file_records,
    preflight_package,
)
from resnet50_pipeline.native_json_maxpool_package import (  # noqa: E402
    SOURCE_BLOB,
    SOURCE_COMMIT,
    SOURCE_REMOTE,
    generate_native_json_maxpool_package,
    validate_native_json_maxpool_package,
)


class MaxPoolPackageBuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def tree_sha256(items: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(items.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return digest.hexdigest()


def _read_receipt() -> dict[str, Any]:
    entries = []
    for path, role, mutable in (
        (ROOT / ".agents/plan.md", "active plan", True),
        (
            ROOT / ".agents/rules/生成前必读索引.md",
            "generation routing",
            False,
        ),
        (
            ROOT / ".agents/rules/服务器测试包生成规则.md",
            "server package rules",
            False,
        ),
        (
            ROOT / ".agents/rules/NDP硬件字段语义.md",
            "GA INT8 max hardware semantics",
            False,
        ),
        (
            ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
            "hardware simulation entry contract",
            False,
        ),
        (
            ROOT
            / ".agents/task_records/20260727_maxpool_node0002_mainline_adjudication.md",
            "MaxPool release boundary",
            False,
        ),
        (
            ROOT
            / ".agents/task_records/"
            "20260728_maxpool_int8_max_active_rtl_mainline_adjudication.md",
            "current active RTL INT8 max numeric adjudication",
            False,
        ),
        (
            ROOT / "contracts/ga_int8_pipeline_backpressure_defect_report_20260723.md",
            "known dynamic counterexample",
            False,
        ),
        (SOURCE_JSON, "immutable active ndp-sim original JSON", False),
    ):
        if not path.is_file():
            raise MaxPoolPackageBuildError(f"required receipt is missing: {path}")
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "role": role,
                "mutable_provenance_only": mutable,
            }
        )
    return {
        "schema": "maxpool-node0002-original-json-read-receipt-v1",
        "read_receipt": entries,
        "rule_ids": [
            PROFILE_RULE,
            "CDA-SERVER-WORKLOAD-PROVENANCE-001",
            "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "CDA-SERVER-ONE-COMMAND-001",
            "CDA-SCA-D-TB-READBACK-LENGTH-001",
            "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
            "CDA-SERVER-RETURN-RECEIPT-001",
            "CDA-GA-INT8-MAX-NUMERIC-001",
            "CDA-GA-INT8-MAX-PIPE-001",
        ],
        "known_counterexamples": [
            "GA int8_max pipeline0 downstream backpressure omits the INT8 branch",
        ],
        "int8_max_numeric_polarity": "CURRENT_ACTIVE_SOURCE_SELECTS_UNSIGNED_MAX",
        "int8_max_numeric_rule_status": (
            "CDA-GA-INT8-MAX-NUMERIC-001=LOCAL_SOURCE_PASS"
        ),
        "open_dynamic_gates": [
            "B_GA_INT8_MAX_FLOW",
            "B_MAXPOOL_SERVER_E4_E5",
        ],
        "server_roots_read_or_hashed": [],
        "server_source_preflight_performed": False,
    }


def _validate_source_workload(source_workload: Path) -> dict[str, Any]:
    if sha256(SOURCE_JSON) != SOURCE_JSON_SHA256:
        raise MaxPoolPackageBuildError("active original MaxPool JSON identity differs")
    validation = validate_native_json_maxpool_package(source_workload)
    source_manifest = json.loads(
        (source_workload / "manifest.json").read_text(encoding="utf-8")
    )
    actual_records = file_records(source_workload)
    actual_records.pop("manifest.json", None)
    expected_files = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in source_manifest.get("files", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    if expected_files != actual_records:
        raise MaxPoolPackageBuildError("frozen MaxPool workload exact files differ")
    if (
        validation.get("status") != "hardware_execplan_package_validated"
        or source_manifest.get("source_config_sha256") != SOURCE_JSON_SHA256
        or source_manifest.get("source_config_rewritten") is not False
    ):
        raise MaxPoolPackageBuildError("fresh MaxPool workload validation differs")
    frozen_copy = (
        source_workload
        / "source_config"
        / "maxpool_config_16_112_112_stride2_padding1.json.original"
    )
    if frozen_copy.read_bytes() != SOURCE_JSON.read_bytes():
        raise MaxPoolPackageBuildError(
            "frozen workload source JSON is not byte-identical to active original"
        )
    freeze = json.loads(
        (source_workload / "freeze_manifest.json").read_text(encoding="utf-8")
    )
    encoder = freeze.get("encoder")
    tensor_source = freeze.get("real_resnet_tensors")
    if not isinstance(encoder, dict) or not isinstance(tensor_source, dict):
        raise MaxPoolPackageBuildError("fresh source provenance receipt is missing")
    if (
        encoder.get("selected_seed") not in encoder.get("seed_order", [])
        or encoder.get("deterministic_repeat_count") != 2
        or encoder.get("semantic_mismatch_paths") != []
        or tensor_source.get("output_tensor_read") is not False
    ):
        raise MaxPoolPackageBuildError("fresh encoder or golden provenance differs")
    for run in encoder.get("runs", {}).values():
        receipt = run.get("receipt", {}) if isinstance(run, dict) else {}
        if (
            run.get("penalty") != 0
            or run.get("fallback_used") is not False
            or receipt.get("mapping_cache_initial_file_count") != 0
            or receipt.get("exact_mapping") is not True
        ):
            raise MaxPoolPackageBuildError("fresh empty-cache encoder receipt differs")

    forbidden_tokens = [
        "artifacts/w5/" + "native_json_maxpool",
        "maxpool_node0002_original_json_" + "retest_v2.zip",
        "maxpool_node0002_original_json_" + "retest.zip",
    ]
    implementation_paths = [
        ROOT / "resnet50_pipeline/native_json_maxpool_package.py",
        Path(__file__).resolve(),
        RUNTIME_SOURCE,
    ]
    forbidden_matches = []
    for implementation_path in implementation_paths:
        text = implementation_path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                forbidden_matches.append(
                    {
                        "path": implementation_path.relative_to(ROOT).as_posix(),
                        "token": token,
                    }
                )
    if forbidden_matches:
        raise MaxPoolPackageBuildError(
            f"fresh implementation references forbidden MaxPool assets: {forbidden_matches}"
        )
    records = file_records(source_workload)
    return {
        "validation": validation,
        "source_tree_file_count": len(records),
        "source_tree_sha256": tree_sha256(records),
        "source_manifest_sha256": sha256(source_workload / "manifest.json"),
        "source_json_byte_identical_to_active_original": True,
        "source_generation": "fresh empty-cache mapping/encoder plus active execplan toolchain",
        "forbidden_prior_materialized_asset_read_count": 0,
        "source_git": {
            "remote": SOURCE_REMOTE,
            "commit": SOURCE_COMMIT,
            "blob": SOURCE_BLOB,
        },
        "fresh_encoder": {
            "seed_order": encoder["seed_order"],
            "selected_seed": encoder["selected_seed"],
            "deterministic_repeat_count": encoder["deterministic_repeat_count"],
            "semantic_outputs_compared": encoder["semantic_outputs_compared"],
            "semantic_mismatch_paths": encoder["semantic_mismatch_paths"],
            "runs": encoder["runs"],
        },
        "formal_input_and_golden": tensor_source,
        "forbidden_asset_audit": {
            "policy": "no read, traversal, copy, hash, or reuse",
            "forbidden_tokens": forbidden_tokens,
            "implementation_files_scanned": [
                path.relative_to(ROOT).as_posix() for path in implementation_paths
            ],
            "match_count": 0,
            "matches": [],
            "prior_materialized_asset_read_count": 0,
        },
    }


def _prefix_sca_paths(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MaxPoolPackageBuildError(f"SCA root is not an object: {path}")
    changed: list[dict[str, str]] = []
    prefix = f"install/cfg_pkg/{INSTALL_NAME}/"
    for key, item in value.items():
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        old = item["path"]
        relative = PurePosixPath(old)
        if relative.is_absolute() or ".." in relative.parts:
            raise MaxPoolPackageBuildError(f"unsafe source SCA path: {old}")
        new = prefix + relative.as_posix()
        item["path"] = new
        changed.append({"key": key, "old": old, "new": new})
    write_json(path, value)
    return {
        "path": path.name,
        "changed_path_count": len(changed),
        "changes": changed,
    }


def _run_script() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root" >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *) echo "Server root path must be absolute: $1" >&2; exit 2 ;;
esac
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || {{
  echo "Server root is not an enterable directory: $1" >&2
  exit 2
}}

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd -P)"
runtime_tool="${{package_root}}/package_tools/maxpool_node0002_original_json_server_runtime.py"
install_name="{INSTALL_NAME}"
cfg_root="${{server_root}}/install/cfg_pkg/${{install_name}}"
run_dir="${{server_root}}/run_${{install_name}}"
evidence_root="${{server_root}}/evidence_${{install_name}}"
return_dir="${{server_root}}/${{install_name}}_return"
return_zip="${{return_dir}}.zip"
return_sha="${{return_zip}}.sha256"
server_command="bash PREPARE_AND_RUN.sh ${{server_root}}"

for command_name in python3 timeout make; do
  command -v "${{command_name}}" >/dev/null 2>&1 || {{
    echo "Missing command: ${{command_name}}" >&2
    exit 3
  }}
done
for fresh in "${{cfg_root}}" "${{run_dir}}" "${{evidence_root}}" \
  "${{return_dir}}" "${{return_zip}}" "${{return_sha}}"; do
  [ ! -e "${{fresh}}" ] || {{
    echo "Fresh namespace required: ${{fresh}}" >&2
    exit 4
  }}
done

mkdir -p "${{evidence_root}}"
printf '%s\n' "${{server_command}}" > "${{evidence_root}}/server_command.txt"
python3 - <<'PY' > "${{evidence_root}}/VERSION_UNBOUND_PROFILE.json"
import json
print(json.dumps({{
  "schema": "maxpool-original-json-version-unbound-profile-v1",
  "status": "VERSION_UNBOUND_DIAGNOSTIC_ONLY",
  "rule_id": "{PROFILE_RULE}",
  "server_source_identity_bound": False,
  "server_source_preflight_performed": False,
  "source_json_rewritten": False,
  "candidate_release": False,
  "counts_as_e4": False,
  "counts_as_e5": False
}}, indent=2))
PY

compile_status=125
sim_status=125
run_status=125
finalization_started=0
termination_signal=""

finalize_return() {{
  original_status="$1"
  [ "${{finalization_started}}" -eq 0 ] || exit "${{original_status}}"
  finalization_started=1
  trap - EXIT HUP INT TERM
  set +e
  [ -z "${{termination_signal}}" ] || \
    printf '%s\n' "${{termination_signal}}" > "${{evidence_root}}/termination_signal.txt"
  printf '%s\n' "${{compile_status}}" > "${{evidence_root}}/compile_exit_status.txt"
  printf '%s\n' "${{sim_status}}" > "${{evidence_root}}/sim_exit_status.txt"
  printf '%s\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"
  python3 "${{runtime_tool}}" analyze \
    --server-root "${{server_root}}" --package-root "${{package_root}}" \
    --install-name "${{install_name}}" --evidence-root "${{evidence_root}}" \
    --run-dir "${{run_dir}}" --compile-status "${{compile_status}}" \
    --sim-status "${{sim_status}}" \
    --output "${{evidence_root}}/SERVER_RESULT_GATE.json" >/dev/null
  analysis_status=$?
  python3 "${{runtime_tool}}" collect \
    --server-root "${{server_root}}" --package-root "${{package_root}}" \
    --install-name "${{install_name}}" --evidence-root "${{evidence_root}}" \
    --run-dir "${{run_dir}}" --run-status "${{run_status}}" \
    --server-command "${{server_command}}" >/dev/null
  collection_status=$?
  if [ -f "${{return_zip}}" ] && [ -f "${{return_sha}}" ]; then
    echo "Return ZIP: ${{return_zip}}"
    echo "Return SHA256: ${{return_sha}}"
  else
    echo "Return collection did not produce ZIP + sidecar." >&2
  fi
  final_status="${{original_status}}"
  for status in "${{analysis_status}}" "${{collection_status}}"; do
    if [ "${{final_status}}" -eq 0 ] && [ "${{status}}" -ne 0 ]; then
      final_status="${{status}}"
    fi
  done
  exit "${{final_status}}"
}}
trap 'finalize_return $?' EXIT
trap 'termination_signal=HUP; exit 129' HUP
trap 'termination_signal=INT; exit 130' INT
trap 'termination_signal=TERM; exit 143' TERM

python3 "${{runtime_tool}}" preflight-package \
  --package-root "${{package_root}}" --install-name "${{install_name}}" \
  --output "${{evidence_root}}/package_preflight.json" >/dev/null || exit 5
mkdir -p "${{cfg_root}}" "${{run_dir}}/sim_results"
cp -a "${{package_root}}/workload/runtime/." "${{cfg_root}}/"
python3 "${{runtime_tool}}" preflight-installed \
  --package-root "${{package_root}}" --server-root "${{server_root}}" \
  --install-name "${{install_name}}" \
  --output "${{evidence_root}}/installed_preflight.json" >/dev/null || exit 5

cd "${{server_root}}"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="${{run_dir}}" \
  > "${{run_dir}}/sim_results/compile_driver.log" 2>&1
compile_status=$?
if [ "${{compile_status}}" -eq 0 ]; then
  timeout --foreground --signal=TERM --kill-after=30s 12h \
    "${{run_dir}}/sim_results/simv" \
    -l "${{run_dir}}/sim_results/sim.log" +vcs+lic+wait \
    "+SCA_CFG=${{cfg_root}}/sca_cfg.json" \
    "+SCA_CFG_D=${{cfg_root}}/sca_cfg_D.json"
  sim_status=$?
else
  sim_status=125
fi
if [ "${{compile_status}}" -ne 0 ]; then
  run_status="${{compile_status}}"
else
  run_status="${{sim_status}}"
fi
set -e
exit "${{run_status}}"
"""


def _build_directory(destination: Path) -> Path:
    receipt = _read_receipt()
    if (destination / INSTALL_NAME).exists():
        raise MaxPoolPackageBuildError(
            f"fresh build destination required: {destination / INSTALL_NAME}"
        )
    package = destination / INSTALL_NAME
    runtime = package / "workload/runtime"
    validation = package / "validation"
    package_tools = package / "package_tools"
    runtime.parent.mkdir(parents=True)
    validation.mkdir()
    package_tools.mkdir()
    generate_native_json_maxpool_package(ROOT, runtime)
    source_facts = _validate_source_workload(runtime)

    frozen_manifest = runtime / "manifest.json"
    shutil.move(frozen_manifest, validation / "frozen_source_workload_manifest.json")
    source_sca_hashes = {
        name: sha256(runtime / name) for name in ("sca_cfg.json", "sca_cfg_D.json")
    }
    adaptations = [
        _prefix_sca_paths(runtime / "sca_cfg.json"),
        _prefix_sca_paths(runtime / "sca_cfg_D.json"),
    ]
    adaptation_receipt = {
        "schema": "maxpool-node0002-original-json-sca-adaptation-v1",
        "status": "pass",
        "source_workload": {
            "path": "workload/runtime",
            "provenance": "generated from authorized sources inside this fresh build",
            **source_facts,
        },
        "allowed_changed_files": ["sca_cfg.json", "sca_cfg_D.json"],
        "source_sca_sha256": source_sca_hashes,
        "adaptations": adaptations,
        "operator_json_changed": False,
        "source_json_path": SOURCE_JSON.relative_to(ROOT).as_posix(),
        "source_json_sha256": SOURCE_JSON_SHA256,
        "source_json_rewritten": False,
        "runtime_semantics_change": (
            "SCA payload paths only: prefix fresh install namespace; "
            "config bitstream, execplan, addresses, lengths, data and golden unchanged"
        ),
    }
    write_json(validation / "sca_namespace_adaptation_receipt.json", adaptation_receipt)
    write_json(validation / "read_receipt.json", receipt)
    shutil.copyfile(
        RUNTIME_SOURCE,
        package_tools / "maxpool_node0002_original_json_server_runtime.py",
    )
    (package / "PREPARE_AND_RUN.sh").write_text(
        _run_script(), encoding="utf-8", newline="\n"
    )
    os.chmod(package / "PREPARE_AND_RUN.sh", 0o755)
    (package / "README.md").write_text(
        "# MaxPool node0002 immutable-original-JSON retest\n\n"
        "Run exactly one command from the extracted package directory:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/server_root\n"
        "```\n\n"
        "The package uses the byte-exact active `ndp-sim/jsons/"
        "maxpool_config_16_112_112_stride2_padding1.json` identity "
        f"`{SOURCE_JSON_SHA256}`. The operator JSON is not edited. Mapping, bitstream, "
        "execplan, SCA, input and golden are regenerated from authorized sources; "
        "only SCA payload paths are then prefixed with this package's fresh install "
        "namespace. No RTL, TB "
        "or observer file is installed or modified. Server source identity is "
        "intentionally not inspected, so the result is diagnostic only and never "
        "counts as E4/E5.\n",
        encoding="utf-8",
        newline="\n",
    )
    payload = file_records(package)
    manifest = {
        "schema": "maxpool-node0002-original-json-server-package-v1",
        "install_name": INSTALL_NAME,
        "test_id": "r5_maxpool_node0002_original_json_fresh_v3",
        "operator": {
            "node_id": "node-0002",
            "hwop_id": "r5:hwop-0002-00",
            "family": "MaxPoolUint8",
            "scope": "two real ResNet tiles on slices 0 and 1",
        },
        "source_json": {
            "path": SOURCE_JSON.relative_to(ROOT).as_posix(),
            "size_bytes": SOURCE_JSON.stat().st_size,
            "sha256": SOURCE_JSON_SHA256,
            "git_remote": source_facts["source_git"]["remote"],
            "git_commit": source_facts["source_git"]["commit"],
            "git_blob": source_facts["source_git"]["blob"],
            "packaged_copy": (
                "workload/runtime/source_config/"
                "maxpool_config_16_112_112_stride2_padding1.json.original"
            ),
            "byte_identical_to_active_original": True,
            "rewritten": False,
        },
        "run_kind": "FIRST_DYNAMIC_RETEST",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "candidate_release": False,
        "counts_as_e4": False,
        "counts_as_e5": False,
        "functional_rtl_file_count": 0,
        "tb_or_observer_file_count": 0,
        "server_source_identity_bound": False,
        "server_source_preflight_performed": False,
        "rule_ids": receipt["rule_ids"],
        "known_counterexamples": receipt["known_counterexamples"],
        "int8_max_numeric_polarity": receipt["int8_max_numeric_polarity"],
        "int8_max_numeric_rule_status": receipt["int8_max_numeric_rule_status"],
        "open_dynamic_gates": receipt["open_dynamic_gates"],
        "workload": {
            "source_tree_sha256": source_facts["source_tree_sha256"],
            "source_tree_file_count": source_facts["source_tree_file_count"],
            "generation": source_facts["source_generation"],
            "forbidden_prior_materialized_asset_read_count": 0,
            "runtime_operator_count": 2,
            "execplan_128bit_lines": 5,
            "sca_preload_reference_count": 11,
            "sca_d_reference_count": 4,
            "formal_output_bytes": 2 * 50176,
            "golden_preloaded": False,
            "fresh_encoder": source_facts["fresh_encoder"],
            "formal_input_and_golden": source_facts["formal_input_and_golden"],
            "forbidden_asset_audit": source_facts["forbidden_asset_audit"],
        },
        "only_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/server_root",
        "expected_return": {
            "zip": f"{INSTALL_NAME}_return.zip",
            "sidecar": f"{INSTALL_NAME}_return.zip.sha256",
        },
        "payload_tree_sha256": tree_sha256(payload),
        "files": payload,
    }
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)
    preflight_package(package, INSTALL_NAME)
    return package


def _write_zip(package: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _safe_extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise MaxPoolPackageBuildError("ZIP contains duplicate paths")
        for name in names:
            relative = PurePosixPath(name)
            if (
                relative.is_absolute()
                or not relative.parts
                or any(part in {"", ".", ".."} for part in relative.parts)
                or relative.parts[0] != INSTALL_NAME
            ):
                raise MaxPoolPackageBuildError(f"unsafe ZIP path: {name}")
        archive.extractall(destination)
    return destination / INSTALL_NAME


def validate_zip(zip_path: Path) -> dict[str, Any]:
    if not zip_path.is_file():
        raise MaxPoolPackageBuildError(f"missing package ZIP: {zip_path}")
    with tempfile.TemporaryDirectory() as temp_text:
        package = _safe_extract(zip_path, Path(temp_text))
        manifest = json.loads(
            (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        actual = file_records(package, exclude_manifest=True)
        if manifest.get("files") != actual:
            raise MaxPoolPackageBuildError("ZIP manifest exact file set differs")
        if manifest.get("payload_tree_sha256") != tree_sha256(actual):
            raise MaxPoolPackageBuildError("ZIP payload tree identity differs")
        original = (
            package
            / "workload/runtime/source_config/"
            "maxpool_config_16_112_112_stride2_padding1.json.original"
        )
        if sha256(original) != SOURCE_JSON_SHA256:
            raise MaxPoolPackageBuildError("ZIP original JSON differs")
        paths = set(actual)
        if any(
            "rtl/" in relative.lower()
            or relative.lower().startswith("rtl/")
            or "/tb_probe/" in relative.lower()
            for relative in paths
        ):
            raise MaxPoolPackageBuildError("ZIP contains RTL/TB observer payload")
        script = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        if (
            "/absolute/path/to/server_root" not in script
            or "Makefile.tb_NDP_Top_new_phy compile" not in script
            or "SCA_CFG_D" not in script
            or "find " in script
            or "rglob" in script
        ):
            raise MaxPoolPackageBuildError("runner entry or no-scan boundary differs")
        before = file_records(package)
        output = Path(temp_text) / "local_preflight.json"
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(
                    package
                    / "package_tools/maxpool_node0002_original_json_server_runtime.py"
                ),
                "preflight-package",
                "--package-root",
                str(package),
                "--install-name",
                INSTALL_NAME,
                "--output",
                str(output),
            ],
            cwd=package,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise MaxPoolPackageBuildError(
                f"extracted package preflight failed: {result.stderr}"
            )
        after = file_records(package)
        if before != after:
            raise MaxPoolPackageBuildError(
                "package tree changed during bootstrap preflight"
            )
        preflight = json.loads(output.read_text(encoding="utf-8"))
        return {
            "schema": "maxpool-node0002-original-json-package-validation-v1",
            "status": "pass",
            "zip_path": zip_path.relative_to(ROOT).as_posix(),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": sha256(zip_path),
            "zip_entry_count": len(actual) + 1,
            "payload_tree_sha256": tree_sha256(actual),
            "source_json_sha256": SOURCE_JSON_SHA256,
            "source_json_rewritten": False,
            "rtl_entry_count": 0,
            "tb_or_observer_entry_count": 0,
            "server_source_preflight_performed": False,
            "bootstrap_tree_immutable": True,
            "local_extracted_preflight": preflight,
            "candidate_release": False,
            "counts_as_e4": False,
            "counts_as_e5": False,
        }


def build() -> dict[str, Any]:
    for target in (OUTPUT_ZIP, OUTPUT_SIDECAR, VALIDATION_RECEIPT):
        if target.exists():
            raise MaxPoolPackageBuildError(f"fresh output required: {target}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as first_text, tempfile.TemporaryDirectory() as second_text:
        first_root = Path(first_text)
        second_root = Path(second_text)
        first_package = _build_directory(first_root)
        second_package = _build_directory(second_root)
        first_zip = first_root / f"{INSTALL_NAME}.zip"
        second_zip = second_root / f"{INSTALL_NAME}.zip"
        _write_zip(first_package, first_zip)
        _write_zip(second_package, second_zip)
        if first_zip.read_bytes() != second_zip.read_bytes():
            raise MaxPoolPackageBuildError(
                "two independent package builds are not byte-identical"
            )
        shutil.copyfile(first_zip, OUTPUT_ZIP)
    validation = validate_zip(OUTPUT_ZIP)
    validation["deterministic_double_build"] = True
    write_json(VALIDATION_RECEIPT, validation)
    OUTPUT_SIDECAR.write_text(
        f"{sha256(OUTPUT_ZIP)}  {OUTPUT_ZIP.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return {
        **validation,
        "validation_receipt": VALIDATION_RECEIPT.relative_to(ROOT).as_posix(),
        "sidecar": OUTPUT_SIDECAR.relative_to(ROOT).as_posix(),
        "only_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/server_root",
        "expected_return": [
            f"{INSTALL_NAME}_return.zip",
            f"{INSTALL_NAME}_return.zip.sha256",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        report = validate_zip(OUTPUT_ZIP) if args.check else build()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"MaxPool package build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
