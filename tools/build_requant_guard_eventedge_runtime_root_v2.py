"""Build the version-unbound, user-supplied-root Requant event-edge package."""

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
from typing import Any

sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "rq_node0001_guardonly_sfu_eventedge_stock_v1"
TARGET_NAME = "rq_node0001_guardonly_sfu_eventedge_runtime_root_v2"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
TARGET_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{TARGET_NAME}.zip"
)
VALIDATION_RECEIPT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{TARGET_NAME}.validation.json"
)
SOURCE_SHA256 = (
    "31877dcf0f11a52a0822525e8f49312d25807f81884377f748425693c89b4a53"
)
SERVER_RULE_SHA256 = (
    "72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524"
)
REQUANT_RULE_SHA256 = (
    "44e8ee38d1361f15d78bf5d7918fa10e4648370153178ad10d044fd5c9d26265"
)
PLAN_SHA256 = (
    "581ee5b55d2d5b1df36d8cfc2937e3a3822c1108c835cbd8669c9d80820d22fe"
)
INDEX_SHA256 = (
    "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7"
)
PROFILE_RULE = "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001"
RUNTIME_SOURCE = ROOT / "tools/requant_runtime_root_v2_server_runtime.py"
COMMON_SOURCE = ROOT / "tools/requant_runtime_root_v2_common.py"
SEMANTIC_FREEZE = (
    "validation/semantic_freeze_numeric_v1_to_eventedge_v1.json"
)


class PackageBuildError(RuntimeError):
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


def records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "TEST_PACKAGE_MANIFEST.json":
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def tree_sha256(items: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(items.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return digest.hexdigest()


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> Path:
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise PackageBuildError("source ZIP contains duplicate paths")
    for name in names:
        relative = PurePosixPath(name)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative.parts[0] != SOURCE_NAME
        ):
            raise PackageBuildError(f"unsafe source ZIP path: {name}")
        target = destination.joinpath(*relative.parts).resolve()
        try:
            target.relative_to(destination.resolve())
        except ValueError as exc:
            raise PackageBuildError(f"source ZIP path escapes: {name}") from exc
    archive.extractall(destination)
    return destination / SOURCE_NAME


def shell_script() -> str:
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
runtime_tool="${{package_root}}/package_tools/requant_runtime_root_v2_server_runtime.py"
install_name="{TARGET_NAME}"
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
  "schema": "requant-runtime-root-v2-version-unbound-profile-v1",
  "status": "VERSION_UNBOUND_DIAGNOSTIC_ONLY",
  "rule_id": "{PROFILE_RULE}",
  "server_source_identity_bound": False,
  "server_source_preflight_performed": False,
  "candidate_release": False,
  "counts_as_node0001_e4": False,
  "counts_as_node0001_e5": False
}}, indent=2))
PY

run_status=125
compile_status=125
sim_status=125
probe_installed=0
finalization_started=0
termination_signal=""

restore_if_needed() {{
  if [ "${{probe_installed}}" -eq 1 ]; then
    python3 "${{runtime_tool}}" restore-probe \
      --server-root "${{server_root}}" --evidence-root "${{evidence_root}}" >/dev/null
    status=$?
    [ "${{status}}" -ne 0 ] || probe_installed=0
    return "${{status}}"
  fi
  return 0
}}

finalize_return() {{
  original_status="$1"
  [ "${{finalization_started}}" -eq 0 ] || exit "${{original_status}}"
  finalization_started=1
  trap - EXIT HUP INT TERM
  set +e
  restore_if_needed
  restore_status=$?
  [ "${{restore_status}}" -eq 0 ] || original_status="${{restore_status}}"
  [ -z "${{termination_signal}}" ] || \
    printf '%s\n' "${{termination_signal}}" > "${{evidence_root}}/termination_signal.txt"
  printf '%s\n' "${{compile_status}}" > "${{evidence_root}}/compile_exit_status.txt"
  printf '%s\n' "${{sim_status}}" > "${{evidence_root}}/sim_exit_status.txt"
  printf '%s\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"
  python3 "${{runtime_tool}}" analyze \
    --package-root "${{package_root}}" --install-name "${{install_name}}" \
    --evidence-root "${{evidence_root}}" --run-dir "${{run_dir}}" \
    --run-status "${{run_status}}" \
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
  for status in "${{restore_status}}" "${{analysis_status}}" "${{collection_status}}"; do
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
python3 "${{runtime_tool}}" install-probe \
  --server-root "${{server_root}}" --package-root "${{package_root}}" \
  --evidence-root "${{evidence_root}}" >/dev/null || exit 5
probe_installed=1
python3 "${{runtime_tool}}" verify-probe \
  --server-root "${{server_root}}" --evidence-root "${{evidence_root}}" \
  --output "${{evidence_root}}/tb_probe_precompile_receipt.json" >/dev/null || exit 5

cd "${{server_root}}"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 \
  RUN_DIR="${{run_dir}}" VCS_EXTRA_OPTS="+incdir+${{server_root}}" \
  > "${{run_dir}}/sim_results/compile_driver.log" 2>&1
compile_status=$?
restore_if_needed
restore_status=$?
if [ "${{restore_status}}" -ne 0 ]; then
  run_status="${{restore_status}}"
  exit "${{run_status}}"
fi
if [ "${{compile_status}}" -eq 0 ]; then
  (
    cd "${{run_dir}}"
    timeout --foreground --signal=TERM --kill-after=30s 12h \
      ./sim_results/simv -l sim_results/sim.log +vcs+lic+wait \
      +REQUANT_GUARD_SFU_EVENTEDGE_PROBE \
      "+SCA_CFG=../install/cfg_pkg/${{install_name}}/sca_cfg.json" \
      "+SCA_CFG_D=../install/cfg_pkg/${{install_name}}/sca_cfg_D.json"
  )
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


def read_receipt() -> dict[str, Any]:
    entries = []
    for path, expected, role in (
        (ROOT / ".agents/plan.md", PLAN_SHA256, "active plan"),
        (
            ROOT / ".agents/rules/生成前必读索引.md",
            INDEX_SHA256,
            "generation routing",
        ),
        (
            ROOT / ".agents/rules/服务器测试包生成规则.md",
            SERVER_RULE_SHA256,
            "server package rule",
        ),
        (
            ROOT / ".agents/rules/RequantizeUint8算子配置规则.md",
            REQUANT_RULE_SHA256,
            "Requant rule",
        ),
        (SOURCE_ZIP, SOURCE_SHA256, "frozen source package"),
    ):
        observed = sha256(path)
        if observed != expected:
            raise PackageBuildError(
                f"required receipt identity differs: {path}: {observed}"
            )
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": observed,
                "role": role,
            }
        )
    return {
        "schema": "requant-runtime-root-v2-read-receipt-v1",
        "rule_ids": [PROFILE_RULE],
        "read_receipt": entries,
        "server_roots_read_or_hashed": [],
        "local_ndp_copy_read": False,
    }


def build_directory(destination: Path) -> Path:
    receipt = read_receipt()
    if destination.exists():
        raise PackageBuildError(f"fresh build destination required: {destination}")
    destination.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source = safe_extract(archive, destination)
    package = destination / TARGET_NAME
    source.rename(package)

    for relative in (
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "package_tools/requant_node0001_server_runtime.py",
    ):
        (package / relative).unlink()
    shutil.copyfile(
        RUNTIME_SOURCE,
        package / "package_tools/requant_runtime_root_v2_server_runtime.py",
    )
    shutil.copyfile(
        COMMON_SOURCE,
        package / "package_tools/requant_node0001_server_runtime.py",
    )
    base_path = package / "package_tools/requant_atomic_server_runtime_base.py"
    base_text = base_path.read_text(encoding="utf-8")
    identity_start = base_text.index(
        '    identity_path = evidence / "stock_rtl_identity_receipt.json"\n'
    )
    simulation_start = base_text.index(
        "    simulation = _simulation_gate", identity_start
    )
    base_text = (
        base_text[:identity_start]
        + "    # Server source identity is intentionally unbound in runtime-root v2.\n"
        + "    identity_pass = True\n"
        + base_text[simulation_start:]
    )
    base_text = base_text.replace("        and identity_pass\n", "")
    old_gate = '''            "stock_rtl_and_transactional_observer_identity": {
                "status": "pass" if identity_pass else "fail",
                "functional_rtl_unchanged": identity_pass,
            },
'''
    if old_gate not in base_text:
        raise PackageBuildError("source base identity gate text drifted")
    base_text = base_text.replace(
        old_gate,
        '''            "server_source_compatibility_profile": {
                "status": "intentionally_unbound",
                "rule_id": "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
            },
''',
    )
    collect_start = base_text.index("\ndef _copy_tail(")
    base_text = base_text[:collect_start].rstrip() + "\n"
    base_path.write_text(base_text, encoding="utf-8", newline="\n")
    (package / "PREPARE_AND_RUN.sh").write_text(
        shell_script(), encoding="utf-8", newline="\n"
    )
    os.chmod(package / "PREPARE_AND_RUN.sh", 0o755)
    (package / "README.md").write_text(
        "# Requant node0001 guard-only SFU event-edge runtime-root v2\n\n"
        "Run exactly one command from the extracted package directory:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/server_root\n"
        "```\n\n"
        "The root basename is unrestricted. This package intentionally performs no "
        "server source preflight or identity capture. It transactionally appends and "
        "restores only `native_return_observer.svh`. Results are "
        "`VERSION_UNBOUND_DIAGNOSTIC_ONLY`, never E4/E5.\n",
        encoding="utf-8",
        newline="\n",
    )

    sca_path = package / "workload/runtime/sca_cfg.json"
    source_sca = sca_path.read_text(encoding="utf-8")
    target_sca = source_sca.replace(SOURCE_NAME, TARGET_NAME)
    if target_sca == source_sca or SOURCE_NAME in target_sca:
        raise PackageBuildError("SCA namespace adaptation was not exact")
    sca_path.write_text(target_sca, encoding="utf-8", newline="\n")

    freeze = json.loads((package / SEMANTIC_FREEZE).read_text(encoding="utf-8"))
    frozen_files = freeze["files"]
    for relative, expected in frozen_files.items():
        path = package / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected["size_bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise PackageBuildError(f"frozen semantic payload differs: {relative}")
    if tree_sha256(frozen_files) != freeze["target_tree_sha256"]:
        raise PackageBuildError("frozen semantic tree receipt differs")

    write_json(package / "validation/runtime_root_v2_read_receipt.json", receipt)
    adaptation = {
        "schema": "requant-eventedge-runtime-root-adaptation-v2",
        "status": "pass",
        "source_package": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "size_bytes": SOURCE_ZIP.stat().st_size,
            "sha256": SOURCE_SHA256,
        },
        "target_install_name": TARGET_NAME,
        "rule_id": PROFILE_RULE,
        "semantic_file_count": len(frozen_files),
        "semantic_tree_sha256": freeze["target_tree_sha256"],
        "semantic_path_size_sha_equal_to_source_v1": True,
        "sca_change_boundary": (
            "only install namespace text changed; SCA_D, execplan, addresses, "
            "Repeat_Num, Exec_Length, workload and golden are frozen"
        ),
        "server_source_preflight_performed": False,
        "server_source_identity_captured": False,
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
    }
    write_json(
        package / "validation/runtime_root_v2_adaptation_receipt.json",
        adaptation,
    )

    payload = records(package, exclude_manifest=True)
    manifest = {
        "schema": "requant-node0001-guard-eventedge-runtime-root-package-v2",
        "install_name": TARGET_NAME,
        "source_package_name": SOURCE_NAME,
        "source_package_zip_sha256": SOURCE_SHA256,
        "run_kind": "FIRST_DYNAMIC_DIAGNOSTIC",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "functional_rtl_file_count": 0,
        "tb_or_rtl_driver_modification": False,
        "observer_mode": "transactional_read_only_non_rtl_tail",
        "rule_ids": [
            PROFILE_RULE,
            "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "CDA-SERVER-ONE-COMMAND-001",
            "CDA-SERVER-RETURN-RECEIPT-001",
            "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
            "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
            "CDA-REQUANT-GUARD-CHECKPOINT-ROUTING-001",
        ],
        "current_rule_receipts": {
            "plan_sha256": PLAN_SHA256,
            "generation_index_sha256": INDEX_SHA256,
            "server_rule_sha256": SERVER_RULE_SHA256,
            "requant_rule_sha256": REQUANT_RULE_SHA256,
        },
        "version_unbound_compatibility": {
            "server_source_identity_bound": False,
            "server_source_preflight_performed": False,
            "accepted_root_basename": "any",
            "only_preexisting_server_file_touched": "native_return_observer.svh",
            "functional_rtl_modified": False,
            "counts_as_e4": False,
            "counts_as_e5": False,
        },
        "frozen_semantic_identity": {
            "file_count": len(frozen_files),
            "tree_sha256": freeze["target_tree_sha256"],
            "exact_path_size_sha_equal_to_source_v1": True,
        },
        "payload_tree_sha256": tree_sha256(payload),
        "expected_return": {
            "zip": f"{TARGET_NAME}_return.zip",
            "sidecar": f"{TARGET_NAME}_return.zip.sha256",
        },
        "files": payload,
    }
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)
    return package


def write_zip(package: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{TARGET_NAME}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def validate_zip(path: Path) -> dict[str, Any]:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise PackageBuildError("frozen source ZIP identity differs")
    with tempfile.TemporaryDirectory(prefix="rq-runtime-root-v2-validate-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise PackageBuildError("target ZIP duplicate path")
            if any(
                PurePosixPath(name).is_absolute()
                or ".." in PurePosixPath(name).parts
                or PurePosixPath(name).parts[0] != TARGET_NAME
                for name in names
            ):
                raise PackageBuildError("target ZIP unsafe path")
            archive.extractall(root)
        package = root / TARGET_NAME
        manifest = json.loads(
            (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
        )
        if manifest["files"] != records(package, exclude_manifest=True):
            raise PackageBuildError("final ZIP exact set differs")
        if any("rtl" in {part.lower() for part in path.parts} for path in map(PurePosixPath, manifest["files"])):
            raise PackageBuildError("final ZIP contains rtl entry")
        text_scope = "\n".join(
            [
                (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8"),
                (package / "README.md").read_text(encoding="utf-8"),
                (package / "TEST_PACKAGE_MANIFEST.json").read_text(
                    encoding="utf-8"
                ),
                *[
                    script.read_text(encoding="utf-8")
                    for script in sorted(
                        (package / "package_tools").glob("*.py")
                    )
                ],
            ]
        )
        forbidden = (
            "NDP_copy01",
            "NDP_copy02",
            "NDP_copy03",
            "capture-identity",
            "verify-identity",
            "focused_rtl",
            "rtl_tree",
            "_git_identity",
            "server_identity_pre_install",
            "stock_rtl_identity_receipt",
        )
        hit = [token for token in forbidden if token in text_scope]
        if hit:
            raise PackageBuildError(f"forbidden fixed-root/identity token: {hit}")
        if SERVER_RULE_SHA256 not in text_scope:
            raise PackageBuildError("current server rule receipt is absent")
        if "2897fb6a99381f096510650b7de8914604b68c30df895fbd5a0c8f9181cb738a" in text_scope:
            raise PackageBuildError("superseded server rule receipt leaked")
        return {
            "schema": "requant-runtime-root-v2-zip-validation-v1",
            "status": "pass",
            "zip_size_bytes": path.stat().st_size,
            "zip_sha256": sha256(path),
            "entry_count": len(names),
            "rtl_entry_count": 0,
            "package_exact_set": True,
            "server_source_preflight_tokens_absent": True,
            "fixed_root_basename_tokens_absent": True,
            "current_server_rule_receipt_only": True,
        }


def run_runtime(
    runtime: Path, arguments: list[str], *, expected_status: int = 0
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(runtime), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )
    if result.returncode != expected_status:
        raise PackageBuildError(
            "packaged runtime command status differs: "
            f"{arguments[0]}: {result.returncode} != {expected_status}: "
            f"{result.stderr[-1000:]}"
        )
    return result


def self_check(path: Path) -> dict[str, Any]:
    validation = validate_zip(path)
    with tempfile.TemporaryDirectory(prefix="rq-runtime-root-v2-selfcheck-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(path) as archive:
            archive.extractall(root)
        package = root / TARGET_NAME
        before = records(package)
        runtime = (
            package
            / "package_tools/requant_runtime_root_v2_server_runtime.py"
        )
        server_root = root / "custom_server_root_name"
        server_root.mkdir()
        observer = server_root / "native_return_observer.svh"
        preimage = (
            "// local self-check preimage; no server source was inspected\n"
        ).encode("ascii")
        observer.write_bytes(preimage)
        evidence = server_root / f"evidence_{TARGET_NAME}"
        run_dir = server_root / f"run_{TARGET_NAME}"
        install = server_root / "install/cfg_pkg" / TARGET_NAME
        evidence.mkdir()
        (run_dir / "sim_results").mkdir(parents=True)

        run_runtime(
            runtime,
            [
                "preflight-package",
                "--package-root",
                str(package),
                "--install-name",
                TARGET_NAME,
                "--output",
                str(evidence / "package_preflight.json"),
            ],
        )
        shutil.copytree(package / "workload/runtime", install)
        run_runtime(
            runtime,
            [
                "preflight-installed",
                "--package-root",
                str(package),
                "--server-root",
                str(server_root),
                "--install-name",
                TARGET_NAME,
                "--output",
                str(evidence / "installed_preflight.json"),
            ],
        )
        run_runtime(
            runtime,
            [
                "install-probe",
                "--server-root",
                str(server_root),
                "--package-root",
                str(package),
                "--evidence-root",
                str(evidence),
            ],
        )
        installed_bytes = observer.read_bytes()
        run_runtime(
            runtime,
            [
                "verify-probe",
                "--server-root",
                str(server_root),
                "--evidence-root",
                str(evidence),
                "--output",
                str(evidence / "tb_probe_precompile_receipt.json"),
            ],
        )
        observer.write_bytes(installed_bytes + b"tamper\n")
        run_runtime(
            runtime,
            [
                "restore-probe",
                "--server-root",
                str(server_root),
                "--evidence-root",
                str(evidence),
            ],
            expected_status=1,
        )
        if observer.read_bytes() == preimage:
            raise PackageBuildError(
                "restore failure test unexpectedly overwrote the target"
            )
        observer.write_bytes(installed_bytes)
        run_runtime(
            runtime,
            [
                "restore-probe",
                "--server-root",
                str(server_root),
                "--evidence-root",
                str(evidence),
            ],
        )
        if observer.read_bytes() != preimage:
            raise PackageBuildError("observer was not restored byte-exact")

        write_json(
            evidence / "VERSION_UNBOUND_PROFILE.json",
            {
                "schema": "requant-runtime-root-v2-version-unbound-profile-v1",
                "status": "VERSION_UNBOUND_DIAGNOSTIC_ONLY",
                "rule_id": PROFILE_RULE,
                "server_source_identity_bound": False,
                "server_source_preflight_performed": False,
                "candidate_release": False,
                "counts_as_node0001_e4": False,
                "counts_as_node0001_e5": False,
            },
        )
        for name, value in (
            ("server_command.txt", f"bash PREPARE_AND_RUN.sh {server_root}\n"),
            ("compile_exit_status.txt", "2\n"),
            ("sim_exit_status.txt", "125\n"),
            ("run_exit_status.txt", "2\n"),
        ):
            (evidence / name).write_text(
                value, encoding="utf-8", newline="\n"
            )
        run_runtime(
            runtime,
            [
                "analyze",
                "--package-root",
                str(package),
                "--install-name",
                TARGET_NAME,
                "--evidence-root",
                str(evidence),
                "--run-dir",
                str(run_dir),
                "--run-status",
                "2",
                "--output",
                str(evidence / "SERVER_RESULT_GATE.json"),
            ],
        )
        run_runtime(
            runtime,
            [
                "collect",
                "--server-root",
                str(server_root),
                "--package-root",
                str(package),
                "--install-name",
                TARGET_NAME,
                "--evidence-root",
                str(evidence),
                "--run-dir",
                str(run_dir),
                "--run-status",
                "2",
                "--server-command",
                f"bash PREPARE_AND_RUN.sh {server_root}",
            ],
        )
        return_zip = server_root / f"{TARGET_NAME}_return.zip"
        return_sidecar = return_zip.with_suffix(".zip.sha256")
        if not return_zip.is_file() or not return_sidecar.is_file():
            raise PackageBuildError("bounded compile-failure return is missing")
        expected_sidecar = (
            f"{sha256(return_zip)}  {return_zip.name}\n"
        )
        if return_sidecar.read_text(encoding="ascii") != expected_sidecar:
            raise PackageBuildError("return sidecar differs")
        with zipfile.ZipFile(return_zip) as archive:
            receipt_name = (
                f"{TARGET_NAME}_return/RETURN_RECEIPT.json"
            )
            receipt = json.loads(archive.read(receipt_name))
        if (
            receipt["classification"] != "VERSION_UNBOUND_DIAGNOSTIC_ONLY"
            or receipt["candidate_release"] is not False
            or receipt["counts_as_node0001_e4"] is not False
            or receipt["counts_as_node0001_e5"] is not False
            or receipt["server_source_preflight_performed"] is not False
        ):
            raise PackageBuildError("version-unbound return boundary differs")
        after = records(package)
        if before != after:
            raise PackageBuildError("package tree changed during self-check")
        pycache = [
            path
            for path in package.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        ]
        if pycache:
            raise PackageBuildError("self-check created Python bytecode")
        return {
            **validation,
            "schema": "requant-runtime-root-v2-final-selfcheck-v1",
            "status": "pass",
            "arbitrary_root_basename_accepted": True,
            "server_source_preflight_performed": False,
            "server_source_identity_captured": False,
            "observer_only_preexisting_file_touched": True,
            "observer_restore_failure_fail_closed": True,
            "observer_restored_byte_exact": True,
            "compile_entry_absence_returned_bounded_logs": True,
            "version_unbound_return_zip_and_sidecar": True,
            "package_tree_unchanged": True,
            "pycache_created": False,
        }


def build(output: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rq-runtime-root-v2-build-a-") as a, tempfile.TemporaryDirectory(prefix="rq-runtime-root-v2-build-b-") as b:
        root_a = Path(a)
        root_b = Path(b)
        package_a = build_directory(root_a / "fresh")
        package_b = build_directory(root_b / "fresh")
        zip_a = root_a / f"{TARGET_NAME}.zip"
        zip_b = root_b / f"{TARGET_NAME}.zip"
        write_zip(package_a, zip_a)
        write_zip(package_b, zip_b)
        if zip_a.read_bytes() != zip_b.read_bytes():
            raise PackageBuildError("two fresh deterministic builds differ")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(zip_a, output)
    validation = validate_zip(output)
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(
        f"{sha256(output)}  {output.name}\n", encoding="ascii", newline="\n"
    )
    return {
        **validation,
        "sidecar": sidecar.as_posix(),
        "deterministic_fresh_build_count": 2,
        "deterministic_zip_byte_identity": True,
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "server_lease": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TARGET_ZIP)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.self_check:
        report = self_check(output)
        write_json(VALIDATION_RECEIPT, report)
    else:
        report = validate_zip(output) if args.validate_only else build(output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
