from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.qlinearadd_node0007_server_runtime import preflight as runtime_preflight


INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_bind_v6"
SOURCE_INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_v5"
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
ZIP_PATH = PACKAGE_ROOT.with_suffix(".zip")
SIDECAR_PATH = ZIP_PATH.with_suffix(".zip.sha256")
REPORT_PATH = PACKAGE_ROOT.with_suffix(".validation.json")
SOURCE_ROOT = PACKAGE_ROOT.parent / SOURCE_INSTALL_NAME
SOURCE_ZIP = SOURCE_ROOT.with_suffix(".zip")
SOURCE_ZIP_SHA256 = (
    "f184410ced99830d4737bea58ccd0590e87ae0525c77d95265b0ef756a184a8e"
)
CONTRACT_PATH = (
    ROOT
    / "contracts/operator_config/"
    "qlinearadd_node0007_nested_lc_progress_bind_diagnostic_v6.json"
)
OBSERVER_REL = Path("tb_probe/native_return_observer.svh")
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
IMMUTABLE_RULES = {
    ".agents/rules/服务器测试包生成规则.md": (
        "06ec5cde2920f6aa0f11e4a2ec23d9cec2621015afe706ab8ec83e3d4603089c"
    ),
    ".agents/rules/QLinearAdd算子配置规则.md": (
        "fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
    ),
}
PROGRESS_TARGETS = {
    "evidence/progress_contract.json",
    "evidence/actual_compile_argv.txt",
    "evidence/actual_simulator_argv.txt",
    "evidence/host_timing.txt",
    "evidence/signal_status.txt",
    "evidence/progress_samples.log",
    "evidence/observer_binding.txt",
    "runs/return_observer.log",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def package_files() -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for path in sorted(value for value in PACKAGE_ROOT.rglob("*") if value.is_file()):
        relative = path.relative_to(PACKAGE_ROOT).as_posix()
        if relative == "TEST_PACKAGE_MANIFEST.json":
            continue
        records[relative] = {
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
    return records


def normalized_workload_equal() -> tuple[bool, list[str]]:
    current = PACKAGE_ROOT / "workload"
    source = SOURCE_ROOT / "workload"
    current_paths = {
        path.relative_to(current).as_posix()
        for path in current.rglob("*")
        if path.is_file()
    }
    source_paths = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file()
    }
    if current_paths != source_paths:
        return False, sorted(current_paths.symmetric_difference(source_paths))
    new = INSTALL_NAME.encode()
    old = SOURCE_INSTALL_NAME.encode()
    mismatches = [
        relative
        for relative in sorted(current_paths)
        if (current / relative).read_bytes().replace(new, old)
        != (source / relative).read_bytes()
    ]
    return not mismatches, mismatches


def validate() -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    for path in (
        PACKAGE_ROOT,
        ZIP_PATH,
        SIDECAR_PATH,
        SOURCE_ZIP,
        CONTRACT_PATH,
        PACKAGE_ROOT / OBSERVER_REL,
    ):
        if not path.exists():
            errors.append(f"missing: {path}")
    if errors:
        return {
            "schema": "qlinearadd-node0007-progress-bind-package-validation-v6",
            "valid": False,
            "errors": errors,
            "warnings": warnings,
        }

    zip_sha = sha256(ZIP_PATH)
    fields = SIDECAR_PATH.read_text(encoding="ascii").split()
    if fields != [zip_sha, ZIP_PATH.name]:
        errors.append("ZIP sidecar mismatch")
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        errors.append("frozen v5 source package SHA256 mismatch")

    manifest = load_json(PACKAGE_ROOT / "TEST_PACKAGE_MANIFEST.json")
    if manifest.get("install_name") != INSTALL_NAME:
        errors.append("install identity mismatch")
    if manifest.get("claim") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("diagnostic claim mismatch")
    if manifest.get("functional_fix") is not False:
        errors.append("package must deny functional fix")
    if manifest.get("server_rtl_entries") != 0:
        errors.append("functional RTL entry count must be zero")
    if manifest.get("server_tb_or_observer_entries") != 1:
        errors.append("package-local observer entry count must be one")
    if manifest.get("files") != package_files():
        errors.append("manifest package file records differ")

    binding = manifest.get("observer_binding_fix", {})
    if binding.get("source_path") != OBSERVER_REL.as_posix():
        errors.append("observer package path mismatch")
    if binding.get("sha256") != OBSERVER_SHA256:
        errors.append("observer manifest SHA256 mismatch")
    if binding.get("installation_mode") != "PACKAGE_LOCAL_INCLUDE_ONLY":
        errors.append("observer installation mode is not package-local")
    if binding.get("server_source_modified") is not False:
        errors.append("observer binding must not modify server source")
    if binding.get("read_only") is not True or binding.get("drives_dut") is not False:
        errors.append("observer read-only declaration differs")
    if sha256(PACKAGE_ROOT / OBSERVER_REL) != OBSERVER_SHA256:
        errors.append("packaged observer source SHA256 mismatch")

    observer = (PACKAGE_ROOT / OBSERVER_REL).read_text(encoding="utf-8")
    forbidden_observer_tokens = ("force ", "release ", "$finish", "$fatal")
    found_forbidden = [
        token for token in forbidden_observer_tokens if token in observer
    ]
    if found_forbidden:
        errors.append(f"observer contains driving/terminal tokens: {found_forbidden}")
    if "for (genvar return_obs_slice" not in observer:
        errors.append("observer XMR slice index is not generate-time bound")
    if "for (genvar return_obs_row" not in observer:
        errors.append("observer XMR GA row index is not generate-time bound")

    runner = (PACKAGE_ROOT / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    required_runner_tokens = (
        'observer_source="$package_root/tb_probe/native_return_observer.svh"',
        'VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe '
        '+define+NATIVE_RETURN_OBSERVER_ENABLE"',
        '>"$evidence_root/actual_compile_argv.txt"',
        "+RETURN_OBSERVER",
        "+RETURN_OBS_STALL_CYCLES=1048576",
        "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
        '"+RETURN_OBS_FILE=$observer_log"',
        "timeout --foreground --signal=TERM --kill-after=30s 12h",
    )
    for token in required_runner_tokens:
        if token not in runner:
            errors.append(f"runner missing binding token: {token}")
    forbidden_runner_tokens = (
        "cp \"$observer_source\" \"$server_root",
        "tb_NDP_Top_new_phy.sv",
        "patch_server_tb",
        "install_native_return_observer",
    )
    for token in forbidden_runner_tokens:
        if token in runner:
            errors.append(f"runner attempts server source handling: {token}")

    allowlist = manifest.get("return_allowlist", [])
    allow_targets = {record.get("target_path") for record in allowlist}
    if len(allowlist) != 46 or len(allow_targets) != 46:
        errors.append("return allowlist must contain 46 unique entries")
    if not PROGRESS_TARGETS.issubset(allow_targets):
        errors.append("required progress return targets are incomplete")
    for record in allowlist:
        if (
            record.get("target_path") in PROGRESS_TARGETS
            and record.get("required") is not True
        ):
            errors.append(f"progress target not required: {record.get('target_path')}")
    progress = manifest.get("progress_localization", {})
    if progress.get("return_allowlist_entry_count") != 8:
        errors.append("progress return allowlist declaration must be eight")

    actual_paths = {
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
    }
    d_targets = sorted(
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in (PACKAGE_ROOT / "workload/runtime").rglob(
            "matrix_D_linearized_128bit.txt"
        )
    )
    if d_targets:
        errors.append("runtime D target is preloaded")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            errors.append("ZIP CRC failed")
        names = archive.namelist()
        if len(names) != len(set(names)):
            errors.append("ZIP contains duplicate members")
        if set(names) != {f"{INSTALL_NAME}/{path}" for path in actual_paths}:
            errors.append("ZIP exact-set mismatch")

    workload_equal, workload_mismatches = normalized_workload_equal()
    if not workload_equal:
        errors.append(
            f"workload changed beyond install namespace: "
            f"{workload_mismatches[:10]}"
        )
    try:
        preflight = runtime_preflight(PACKAGE_ROOT)
    except Exception as exc:  # pragma: no cover
        preflight = {"valid": False, "exception": str(exc)}
        errors.append(f"runtime preflight failed: {exc}")
    else:
        if preflight.get("valid") is not True:
            errors.append("runtime preflight did not close")

    contract = load_json(CONTRACT_PATH)
    release = contract.get("package_release", {})
    if release.get("status") != "PACKAGE_READY_NOT_RUN":
        errors.append("contract release status mismatch")
    if release.get("zip_sha256") != zip_sha:
        errors.append("contract ZIP identity mismatch")
    if contract.get("functional_fix") is not False:
        errors.append("contract must deny functional fix")
    if contract.get("source_package", {}).get("sha256") != SOURCE_ZIP_SHA256:
        errors.append("contract source v5 binding mismatch")
    if contract.get("frozen_workload", {}).get("numeric_analysis_repeated") is not False:
        errors.append("contract numeric-analysis receipt mismatch")

    for relative, expected in IMMUTABLE_RULES.items():
        if sha256(ROOT / relative) != expected:
            errors.append(f"immutable rule SHA drifted: {relative}")
    plan = contract.get("provenance", {}).get("plan", {})
    if plan.get("policy") != "mutable_provenance":
        errors.append("plan provenance is not mutable")
    elif sha256(ROOT / ".agents/plan.md") != plan.get("sha256"):
        warnings.append("mutable read receipt drift: .agents/plan.md")

    return {
        "schema": "qlinearadd-node0007-progress-bind-package-validation-v6",
        "valid": not errors,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "PACKAGE_BLOCKED",
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "functional_fix": False,
        "errors": errors,
        "warnings": warnings,
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": zip_sha,
        "sidecar": SIDECAR_PATH.relative_to(ROOT).as_posix(),
        "source_v5_zip_sha256": sha256(SOURCE_ZIP),
        "package_file_count": len(actual_paths),
        "return_allowlist_count": len(allowlist),
        "progress_allowlist_exact_required": PROGRESS_TARGETS.issubset(
            allow_targets
        ),
        "server_rtl_entries": manifest.get("server_rtl_entries"),
        "server_tb_or_observer_entries": manifest.get(
            "server_tb_or_observer_entries"
        ),
        "observer_source_sha256": sha256(PACKAGE_ROOT / OBSERVER_REL),
        "observer_package_local_include_bound": True,
        "observer_enable_macro_bound": True,
        "preloaded_runtime_readback_target_count": len(d_targets),
        "workload_equal_to_v5_except_install_namespace": workload_equal,
        "workload_mismatches": workload_mismatches,
        "numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "server_action": False,
        "runtime_preflight": preflight,
    }


def main() -> int:
    report = validate()
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
