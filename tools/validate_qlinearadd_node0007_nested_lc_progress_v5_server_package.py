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


INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_v5"
V4_INSTALL_NAME = "r5_qadd_n7_nested_lc_v4"
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
ZIP_PATH = PACKAGE_ROOT.with_suffix(".zip")
SIDECAR_PATH = ZIP_PATH.with_suffix(".zip.sha256")
REPORT_PATH = PACKAGE_ROOT.with_suffix(".validation.json")
CONTRACT_PATH = (
    ROOT
    / "contracts/operator_config/"
    "qlinearadd_node0007_nested_lc_progress_diagnostic_v5.json"
)
V4_PACKAGE_ROOT = PACKAGE_ROOT.parent / V4_INSTALL_NAME
V4_ZIP_PATH = V4_PACKAGE_ROOT.with_suffix(".zip")
V4_ZIP_SHA256 = (
    "dfe6ab0e11482d9af7954ba3e87911b770f8d80efa4148352b63d27bf7df2361"
)
IMMUTABLE_RULES = {
    ".agents/rules/服务器测试包生成规则.md": (
        "2e5cf649cd721f4444b0caca2d1ea6670823c02d9d86784d6d228351ea8c7227"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
    ),
    ".agents/rules/QLinearAdd算子配置规则.md": (
        "fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba"
    ),
}
PROGRESS_TARGETS = {
    "evidence/progress_contract.json",
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


def package_files(package_root: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for path in sorted(value for value in package_root.rglob("*") if value.is_file()):
        relative = path.relative_to(package_root).as_posix()
        if relative == "TEST_PACKAGE_MANIFEST.json":
            continue
        records[relative] = {
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
    return records


def normalized_v4_workload_equal() -> tuple[bool, list[str]]:
    v5_root = PACKAGE_ROOT / "workload"
    v4_root = V4_PACKAGE_ROOT / "workload"
    mismatches: list[str] = []
    v5_paths = {
        path.relative_to(v5_root).as_posix()
        for path in v5_root.rglob("*")
        if path.is_file()
    }
    v4_paths = {
        path.relative_to(v4_root).as_posix()
        for path in v4_root.rglob("*")
        if path.is_file()
    }
    if v5_paths != v4_paths:
        return False, sorted(v5_paths.symmetric_difference(v4_paths))
    old = V4_INSTALL_NAME.encode()
    new = INSTALL_NAME.encode()
    for relative in sorted(v5_paths):
        v5_data = (v5_root / relative).read_bytes()
        v4_data = (v4_root / relative).read_bytes()
        if v5_data.replace(new, old) != v4_data:
            mismatches.append(relative)
    return not mismatches, mismatches


def validate(root: Path = ROOT) -> dict[str, object]:
    del root
    errors: list[str] = []
    warnings: list[str] = []

    for path in (PACKAGE_ROOT, ZIP_PATH, SIDECAR_PATH, CONTRACT_PATH, V4_ZIP_PATH):
        if not path.exists():
            errors.append(f"missing: {path.relative_to(ROOT)}")
    if errors:
        return {
            "schema": "qlinearadd-node0007-progress-package-validation-v5",
            "valid": False,
            "errors": errors,
            "warnings": warnings,
        }

    zip_sha = sha256(ZIP_PATH)
    sidecar_tokens = SIDECAR_PATH.read_text(encoding="utf-8").split()
    if len(sidecar_tokens) != 2:
        errors.append("sidecar must contain exactly SHA256 and basename")
    else:
        if sidecar_tokens[0] != zip_sha:
            errors.append("sidecar SHA256 mismatch")
        if sidecar_tokens[1] != ZIP_PATH.name:
            errors.append("sidecar basename mismatch")

    if sha256(V4_ZIP_PATH) != V4_ZIP_SHA256:
        errors.append("frozen v4 source package SHA256 mismatch")

    manifest = load_json(PACKAGE_ROOT / "TEST_PACKAGE_MANIFEST.json")
    if manifest.get("install_name") != INSTALL_NAME:
        errors.append("manifest install_name mismatch")
    if manifest.get("claim") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("manifest diagnostic claim mismatch")
    if manifest.get("package_class") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("manifest package_class mismatch")
    if manifest.get("functional_fix") is not False:
        errors.append("diagnostic package must not claim a functional fix")
    if manifest.get("server_rtl_entries") != 0:
        errors.append("server RTL entries must be zero")
    if manifest.get("server_tb_or_observer_entries") != 0:
        errors.append("server TB/observer entries must be zero")

    if manifest.get("files") != package_files(PACKAGE_ROOT):
        errors.append("manifest package file records are not exact")

    actual_paths = {
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
    }
    forbidden = sorted(
        path
        for path in actual_paths
        if "/rtl/" in f"/{path.lower()}/"
        or Path(path).suffix.lower() in {".sv", ".svh", ".v", ".vh"}
    )
    if forbidden:
        errors.append(f"forbidden RTL/TB entries: {forbidden}")

    d_targets = sorted(
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in (PACKAGE_ROOT / "workload/runtime").rglob(
            "matrix_D_linearized_128bit.txt"
        )
    )
    if d_targets:
        errors.append(f"preloaded runtime D targets present: {d_targets}")

    with zipfile.ZipFile(ZIP_PATH) as archive:
        corrupt = archive.testzip()
        if corrupt is not None:
            errors.append(f"ZIP CRC failed at {corrupt}")
        names = archive.namelist()
        if len(names) != len(set(names)):
            errors.append("ZIP contains duplicate member names")
        unsafe = [
            name
            for name in names
            if name.startswith(("/", "\\"))
            or ".." in Path(name.replace("\\", "/")).parts
        ]
        if unsafe:
            errors.append(f"ZIP unsafe paths: {unsafe}")
        expected_zip = {f"{INSTALL_NAME}/{path}" for path in actual_paths}
        if set(names) != expected_zip:
            errors.append("ZIP member exact-set mismatch")

    progress = manifest.get("progress_localization", {})
    if progress.get("enabled_by_default") is not True:
        errors.append("progress localization is not enabled by default")
    if progress.get("read_only") is not True:
        errors.append("progress localization must be read-only")
    if progress.get("heartbeat_cycles") != 262_144:
        errors.append("heartbeat cycle declaration mismatch")
    if progress.get("stall_window_cycles") != 1_048_576:
        errors.append("stall-window cycle declaration mismatch")
    if progress.get("host_sample_period_seconds") != 60:
        errors.append("host sampling period mismatch")

    allowlist = manifest.get("return_allowlist", [])
    targets = {record.get("target_path") for record in allowlist}
    if not PROGRESS_TARGETS.issubset(targets):
        errors.append("progress return allowlist is incomplete")
    for record in allowlist:
        if record.get("target_path") in PROGRESS_TARGETS:
            if record.get("required") is not True:
                errors.append(
                    f"progress target is not required: {record.get('target_path')}"
                )
    if len(allowlist) != 45:
        errors.append(f"return allowlist cardinality is {len(allowlist)}, expected 45")
    if len(targets) != len(allowlist):
        errors.append("return allowlist target paths are not unique")

    runner = (PACKAGE_ROOT / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    required_tokens = (
        "+RETURN_OBSERVER",
        "+RETURN_OBS_SLICE=0",
        "+RETURN_OBS_STALL_CYCLES=1048576",
        "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
        "+RETURN_OBS_DEEP",
        "+RETURN_OBS_DEEP_LIMIT=64",
        '"+RETURN_OBS_FILE=$observer_log"',
        'VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE"',
        "progress_sampler &",
        "sleep 60",
        "timeout --foreground --signal=TERM --kill-after=30s 12h",
    )
    for token in required_tokens:
        if token not in runner:
            errors.append(f"runner missing required progress token: {token}")
    if "RETURN_OBS_FILE=sim_results/" in runner:
        errors.append("observer output is not bound to the declared run root")
    if "timeout --foreground --signal=TERM --kill-after=30s 12h" not in runner:
        errors.append("simulation timeout differs from frozen v4 timeout")

    workload_equal, workload_mismatches = normalized_v4_workload_equal()
    if not workload_equal:
        errors.append(
            f"diagnostic workload differs from v4 beyond namespace: "
            f"{workload_mismatches[:10]}"
        )

    try:
        preflight = runtime_preflight(PACKAGE_ROOT)
    except Exception as exc:  # pragma: no cover - surfaced as a report error
        preflight = {"valid": False, "exception": str(exc)}
        errors.append(f"runtime preflight failed: {exc}")
    else:
        if preflight.get("valid") is not True:
            errors.append("runtime preflight did not close")

    contract = load_json(CONTRACT_PATH)
    release = contract.get("package_release", {})
    if release.get("status") != "PACKAGE_READY_NOT_RUN":
        errors.append("contract package status mismatch")
    if release.get("zip_sha256") != zip_sha:
        errors.append("contract package SHA256 mismatch")
    if contract.get("functional_fix") is not False:
        errors.append("contract must deny functional fix")
    if contract.get("frozen_workload", {}).get("numeric_analysis_repeated") is not False:
        errors.append("contract numeric analysis receipt mismatch")
    if contract.get("source_package", {}).get("sha256") != V4_ZIP_SHA256:
        errors.append("contract frozen v4 source binding mismatch")

    for relative, expected_sha in IMMUTABLE_RULES.items():
        if sha256(ROOT / relative) != expected_sha:
            errors.append(f"immutable rule SHA drifted: {relative}")
    plan_receipt = contract.get("provenance", {}).get("plan", {})
    if plan_receipt.get("policy") != "mutable_provenance":
        errors.append("plan provenance is not explicitly mutable")
    elif sha256(ROOT / ".agents/plan.md") != plan_receipt.get("sha256"):
        warnings.append("mutable read receipt drift: .agents/plan.md")

    return {
        "schema": "qlinearadd-node0007-progress-package-validation-v5",
        "valid": not errors,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "PACKAGE_BLOCKED",
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "functional_fix": False,
        "errors": errors,
        "warnings": warnings,
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": zip_sha,
        "sidecar": SIDECAR_PATH.relative_to(ROOT).as_posix(),
        "source_v4_zip_sha256": sha256(V4_ZIP_PATH),
        "package_file_count": len(actual_paths),
        "zip_member_count": len(actual_paths),
        "return_allowlist_count": len(allowlist),
        "progress_allowlist_exact_required": PROGRESS_TARGETS.issubset(targets),
        "preloaded_runtime_readback_target_count": len(d_targets),
        "workload_equal_to_v4_except_install_namespace": workload_equal,
        "workload_mismatches": workload_mismatches,
        "numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "server_action": False,
        "runtime_preflight": preflight,
    }


def main() -> int:
    report = validate()
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
