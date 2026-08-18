#!/usr/bin/env python3
"""Build serialized Conv v102 from exact local v101 with canonical procfs guard v3."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_hw_v101b_lcdup_guardprocfix"
NEW = "r5_n4_hw_v102b_lcdup_guardprocfs"
SOURCE_ZIP = ROOT / "outputs/conv_node0004_v101b_lcdup_guardprocfix_release1" / f"{OLD}.zip"
OUT = ROOT / "outputs/conv_node0004_v102b_lcdup_guardprocfs_release1"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
V100_ANALYSIS = ROOT / "outputs/conv_node0004_v100b_lcdup_guardv2_return_r1786935520909028428_3675469"
V101_RECEIPT = ROOT / "outputs/conv_node0004_v101b_lcdup_guardprocfix_release1/mainline_package_receipt.json"
ACTIVATION = ROOT / "outputs/observer_operational_guard_process_identity_runtime_budget_v3/CANONICAL_GUARD_PROCESS_IDENTITY_ACTIVATION_RECEIPT.json"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract() -> None:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"v101 source ZIP CRC failure: {bad}")
        infos = archive.infolist()
        roots = {PurePosixPath(item.filename).parts[0] for item in infos if PurePosixPath(item.filename).parts}
        if roots != {OLD}:
            raise RuntimeError(f"v101 source root differs: {sorted(roots)}")
        seen: set[str] = set()
        build_root = (OUT / "build").resolve()
        for item in infos:
            pure = PurePosixPath(item.filename)
            mode = (item.external_attr >> 16) & 0xFFFF
            if item.filename in seen or pure.is_absolute() or ".." in pure.parts or "\\" in item.filename or stat.S_ISLNK(mode):
                raise RuntimeError(f"unsafe v101 member: {item.filename}")
            seen.add(item.filename)
            target = (OUT / "build" / Path(NEW, *pure.parts[1:])).resolve()
            if target != build_root and build_root not in target.parents:
                raise RuntimeError(f"mapped member escapes build root: {item.filename}")
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def replace_identity() -> None:
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if OLD in text:
            path.write_text(text.replace(OLD, NEW), encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label} anchor count differs: {count}")
    return text.replace(old, new)


def install_canonical_assets() -> None:
    copies = {
        ROOT / "tools/server_observer_operational_guard_v2.py": TREE / "package_tools/server_observer_operational_guard_v2.py",
        ROOT / "tools/validate_server_observer_operational_guard_v2.py": TREE / "package_tools/validate_server_observer_operational_guard_v2.py",
        ROOT / "tools/server_observer_operational_attempt_boundary.py": TREE / "package_tools/server_observer_operational_attempt_boundary.py",
        ROOT / "schemas/server_observer_operational_guard_receipt_v2.schema.json": TREE / "schemas/server_observer_operational_guard_receipt_v2.schema.json",
        ROOT / "schemas/server_observer_operational_live_tree_policy_v2.schema.json": TREE / "schemas/server_observer_operational_live_tree_policy_v2.schema.json",
        ROOT / "schemas/server_observer_operational_failure_handoff_v1.schema.json": TREE / "schemas/server_observer_operational_failure_handoff_v1.schema.json",
        ROOT / "contracts/server_observer_operational_guard_live_tree_dispatch_v2.json": TREE / "contracts/server_observer_operational_guard_live_tree_dispatch_v2.json",
        ROOT / "fixtures/server_observer_operational_guard_live_tree_v2/positive_failure_handoff.json": TREE / "receipts/observer_operational_failure_handoff_positive_fixture.json",
        ACTIVATION: TREE / "receipts/CANONICAL_GUARD_PROCESS_IDENTITY_ACTIVATION_RECEIPT.json",
        ROOT / "contracts/server_package_build_gate_registry_v1.json": TREE / "receipts/server_package_build_gate_registry_v1.json",
    }
    for source, target in copies.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def harden_runner() -> None:
    path = TREE / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "operational_sidecar=\n",
        "operational_sidecar=\nfailure_handoff_receipt=\nfailure_handoff_validation_receipt=\n",
        "failure handoff variables",
    )
    handoff_function = r'''write_failure_handoff() {
  finalization_valid="$1"; durable_valid="$2"; cleanup_executed="$3"
  [ -f "$return_zip" ] || return 98
  python3 - "$return_zip" "$failure_handoff_receipt" "$package_id" "$return_tag" "$attempt" "$finalization_valid" "$durable_valid" "$cleanup_executed" <<'PY'
import hashlib,json,pathlib,sys
z,r=map(pathlib.Path,sys.argv[1:3]); pkg,exe,att=sys.argv[3:6]
def flag(value): return value.lower()=="true"
h=hashlib.sha256(); size=0
with z.open("rb") as stream:
  for block in iter(lambda:stream.read(1048576),b""): size+=len(block); h.update(block)
item={"path":z.name,"bytes":size,"sha256":h.hexdigest()}
value={
  "schema":"server-observer-operational-failure-handoff-v1",
  "package_id":pkg,"execution_id":exe,"attempt_id":att,
  "finalization_guard_receipt_valid":flag(sys.argv[6]),
  "published_returns":[item],"selected_formal_return":item,
  "same_basename_overwrite":False,"prior_published_returns_preserved":True,
  "durable_return_receipt_valid":flag(sys.argv[7]),
  "cleanup_executed":flag(sys.argv[8]),
  "claim_boundary":"Durable failure handoff and cleanup ordering only; no DUT result claim."
}
r.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
PY
  python3 "$package_root/package_tools/validate_server_observer_operational_guard_v2.py" validate-failure-handoff --handoff "$failure_handoff_receipt" --output "$failure_handoff_validation_receipt"
}

'''
    text = replace_once(text, "finalize() {\n", handoff_function + "finalize() {\n", "failure handoff writer")
    text = replace_once(
        text,
        '  if [ -z "$evidence_root" ] || [ ! -d "$evidence_root" ]; then publish_minimal_return; exit "$original"; fi',
        '  if [ -z "$evidence_root" ] || [ ! -d "$evidence_root" ]; then publish_minimal_return; write_failure_handoff false false false; exit "$original"; fi',
        "early failure handoff",
    )
    text = replace_once(text, "  cleanup_rc=98\n", "  cleanup_rc=98\n  durable_rc=98\n", "durable default")
    old_final = '  final="$original"; [ "$final" -ne 0 ] || [ "$core_rc" -eq 0 ] || final="$core_rc"; [ "$observer_rc" -eq 0 ] || final=97; [ "$source_bound_rc" -eq 0 ] || final=97; [ "$manifest_rc" -eq 0 ] || final=98; [ "$cleanup_rc" -eq 0 ] || final=99\n  printf \'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s cleanup=%s\\n\' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" "$cleanup_receipt" >&2'
    new_final = '''  durable_ok=false; [ "$durable_rc" -eq 0 ] && [ -f "$durable_return_receipt" ] && durable_ok=true
  cleanup_ok=false; [ "$cleanup_rc" -eq 0 ] && [ -f "$post_durable_cleanup_receipt" ] && cleanup_ok=true
  write_failure_handoff "$finalization_guard_ok" "$durable_ok" "$cleanup_ok"; handoff_rc=$?
  final="$original"; [ "$final" -ne 0 ] || [ "$core_rc" -eq 0 ] || final="$core_rc"; [ "$observer_rc" -eq 0 ] || final=97; [ "$source_bound_rc" -eq 0 ] || final=97; [ "$manifest_rc" -eq 0 ] || final=98; [ "$cleanup_rc" -eq 0 ] || final=99; [ "$handoff_rc" -eq 0 ] || final=99
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s cleanup=%s handoff=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" "$cleanup_receipt" "$failure_handoff_receipt" >&2'''
    text = replace_once(text, old_final, new_final, "failure handoff final status")
    old_assign = 'post_durable_cleanup_receipt="$result_root/${package_id}_${return_tag}_POST_DURABLE_CLEANUP_RECEIPT.json"; operational_sidecar="$return_zip.operational.json"'
    new_assign = old_assign + '; failure_handoff_receipt="$result_root/${package_id}_${return_tag}_FAILURE_HANDOFF_RECEIPT.json"; failure_handoff_validation_receipt="$result_root/${package_id}_${return_tag}_FAILURE_HANDOFF_VALIDATION.json"'
    text = replace_once(text, old_assign, new_assign, "failure handoff result identities")
    path.write_text(text, encoding="utf-8", newline="\n")


def update_contracts() -> None:
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    external = allow.setdefault("external_receipts", [])
    for item in (
        "{package_id}_{execution_id}_FAILURE_HANDOFF_RECEIPT.json",
        "{package_id}_{execution_id}_FAILURE_HANDOFF_VALIDATION.json",
    ):
        if item not in external:
            external.append(item)
    allow_path.write_bytes(canonical(allow))

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = NEW
    request_path.write_bytes(canonical(request))
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = json.loads(post_path.read_text(encoding="utf-8"))
    post["package_id"] = NEW
    post["request_sha256"] = sha_file(request_path)
    post_path.write_bytes(canonical(post))

    operational_path = TREE / "contracts/observer_operational_attempt_boundary.json"
    operational = json.loads(operational_path.read_text(encoding="utf-8"))
    operational["package_id"] = NEW
    operational["threshold_source"]["sha256"] = sha_file(TREE / operational["threshold_source"]["path"])
    operational["live_tree_policy"]["sha256"] = sha_file(TREE / operational["live_tree_policy"]["path"])
    operational_path.write_bytes(canonical(operational))

    runner_path = TREE / "contracts/server_runner_return_resilience.json"
    runner = json.loads(runner_path.read_text(encoding="utf-8"))
    runner["package_id"] = NEW
    runner["runner_sha256"] = sha_file(TREE / "PREPARE_AND_RUN.sh")
    runner_path.write_bytes(canonical(runner))


def regenerate_source_bound_observer() -> None:
    generated = OUT / "source_bound_regenerated"
    generated.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(ROOT / "tools/generate_server_source_bound_observer.py"), "materialize",
        "--catalog", str(TREE / "diagnostics/source_bound_probe_catalog.json"),
        "--plan", str(TREE / "diagnostics/source_bound_probe_plan.json"),
        "--output-dir", str(generated),
        "--report", str(generated / "source_bound_observer_generation_report.json"),
        "--cheap-check-output", str(generated / "cheap_prebuild.json"),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"source-bound regeneration failed: {completed.stderr[-4096:]}")
    destinations = {
        "source_bound_causal_observer.svh": ("diagnostics/source_bound_causal_observer.svh", "tb_probe/source_bound_causal_observer.svh"),
        "source_bound_causal_parser.py": ("diagnostics/source_bound_causal_parser.py", "package_tools/source_bound_causal_parser.py"),
        "source_bound_observer_focus.sv": ("diagnostics/source_bound_observer_focus.sv",),
        "source_bound_probe_binding.json": ("diagnostics/source_bound_probe_binding.json",),
        "source_bound_observer_generation_report.json": ("diagnostics/source_bound_observer_generation_report.json",),
    }
    for name, relatives in destinations.items():
        for relative in relatives:
            shutil.copyfile(generated / name, TREE / relative)


def file_map() -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(TREE).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def update_manifest_and_provenance() -> None:
    provenance = TREE / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    shutil.copy2(V100_ANALYSIS / "formal_return_analysis.json", provenance / "v100b_formal_return_analysis.json")
    shutil.copy2(V100_ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", provenance / "v100b_package_build_failure_rule_audit.json")
    shutil.copy2(V101_RECEIPT, provenance / "v101b_local_gate_receipt.json")
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "node0004-v102b-lcdup-guardprocfs-package-manifest-v1",
        "package_id": NEW,
        "source_package": OLD,
        "activation_epoch": "observer-guard-process-identity-v3",
        "observer_only_semantic_version": 5,
        "first_fresh_after_change": True,
        "first_fresh_semantic_version": 4,
        "canonical_guard_sha256": sha_file(ROOT / "tools/server_observer_operational_guard_v2.py"),
        "activation_receipt_sha256": sha_file(ACTIVATION),
        "build_gate_registry_sha256": sha_file(ROOT / "contracts/server_package_build_gate_registry_v1.json"),
        "observer_only_contract_sha256": sha_file(TREE / "contracts/observer_only_wide_causal_contract.json"),
        "previous_version_progress": "v101 locally fixed the transient ps self-enumerator, but canonical semantic-v5 re-audit rejected its transitional guard bytes before publication.",
        "current_purpose": "Dynamically test the frozen LC9-to-LC3 tuple10 target with the canonical childless-procfs PID+start_time guard and durable failure handoff.",
        "process_identity_model": {
            "snapshot_backend": "PROCFS_NO_CHILD_ENUMERATOR",
            "identity_fields": ["pid", "start_time_ticks"],
            "pid_reuse_protection": True,
            "real_descendants_preserved": True,
        },
        "failure_handoff": {
            "same_basename_overwrite": False,
            "prior_published_returns_preserved": True,
            "cleanup_requires_valid_finalization_and_durable_return": True,
        },
        "package_build_failure_rule_audit": "RULE_CONFIRMATION_NO_CHANGE__IMPLEMENTATION_AND_NEGATIVE_CONTROL_ESCAPE",
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "server_actions_performed": [],
    })
    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))
    (TREE / "README.md").write_text(
        "# Serialized Conv node0004 v102 canonical procfs guard\n\n"
        "Previous progress: v101 passed local gates but was rejected before publication because its transitional ps-backed guard bytes did not match canonical semantic-v5.\n\n"
        "Current purpose: preserve the exact LC9→LC3 mapper/config, workload and 52-signal tuple10/downstream/natural-terminal/Formal-D target while using canonical childless procfs PID+start_time ownership and durable failure handoff.\n\n"
        f"Future command after managed-storage publication and separate server authorization:\n\n`bash {NEW}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "This package has not been uploaded or run.\n",
        encoding="utf-8", newline="\n",
    )
    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))


def deterministic_zip() -> None:
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(f"{NEW}/{path.relative_to(TREE).as_posix()}", (2026, 8, 17, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def write_build_receipt() -> dict[str, Any]:
    receipt = {
        "schema": "node0004-v102b-lcdup-guardprocfs-build-v1",
        "package_id": NEW,
        "source_zip": {"path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size, "sha256": sha_file(SOURCE_ZIP)},
        "package_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha_file(ZIP)},
        "activation_receipt": {"path": ACTIVATION.relative_to(ROOT).as_posix(), "bytes": ACTIVATION.stat().st_size, "sha256": sha_file(ACTIVATION)},
        "changed_surface": [
            "fresh package identity",
            "canonical childless-procfs guard and PID+start_time identity",
            "PID reuse and real-descendant ownership binding",
            "machine-readable failure handoff with same-basename no-overwrite",
            "cleanup admission requiring valid finalization and durable return receipts",
        ],
        "frozen_surface": ["config", "numeric", "workload", "golden", "functional RTL", "LC9-to-LC3 mapper semantics", "52-signal tuple10 target", "observer-only dump settings"],
        "server_actions_performed": [],
        "storage_manager_called": False,
        "status": "LOCAL_BUILD_PENDING_GATES",
    }
    (OUT / "build_receipt.json").write_bytes(canonical(receipt))
    return receipt


def refresh_existing() -> int:
    if not TREE.is_dir():
        raise SystemExit(f"existing v102 tree absent: {TREE}")
    install_canonical_assets()
    update_contracts()
    regenerate_source_bound_observer()
    update_manifest_and_provenance()
    deterministic_zip()
    receipt = write_build_receipt()
    print(json.dumps(receipt, sort_keys=True))
    return 0


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    OUT.mkdir(parents=True)
    safe_extract()
    replace_identity()
    install_canonical_assets()
    harden_runner()
    update_contracts()
    regenerate_source_bound_observer()
    update_manifest_and_provenance()
    deterministic_zip()
    receipt = write_build_receipt()
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(refresh_existing() if "--refresh-existing" in sys.argv[1:] else main())
