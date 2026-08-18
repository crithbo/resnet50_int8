#!/usr/bin/env python3
"""Build serialized Conv v101 from the exact published v100 package."""

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
OLD = "r5_n4_hw_v100b_lcdup_guardv2"
NEW = "r5_n4_hw_v101b_lcdup_guardprocfix"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
OUT = ROOT / "outputs/conv_node0004_v101b_lcdup_guardprocfix_release1"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
V100_ANALYSIS = ROOT / "outputs/conv_node0004_v100b_lcdup_guardv2_return_r1786935520909028428_3675469"


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
            raise RuntimeError(f"v100 source ZIP CRC failure: {bad}")
        roots = {PurePosixPath(item.filename).parts[0] for item in archive.infolist() if PurePosixPath(item.filename).parts}
        if roots != {OLD}:
            raise RuntimeError(f"v100 source root differs: {sorted(roots)}")
        seen: set[str] = set()
        build_root = (OUT / "build").resolve()
        for item in archive.infolist():
            pure = PurePosixPath(item.filename)
            mode = (item.external_attr >> 16) & 0xFFFF
            if item.filename in seen or pure.is_absolute() or ".." in pure.parts or "\\" in item.filename or stat.S_ISLNK(mode):
                raise RuntimeError(f"unsafe v100 member: {item.filename}")
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


def install_fixed_guard() -> None:
    shutil.copy2(
        ROOT / "tools/server_observer_operational_guard_v2.py",
        TREE / "package_tools/server_observer_operational_guard_v2.py",
    )


def harden_runner() -> None:
    path = TREE / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old_fallback = '  if [ "$core_rc" -ne 0 ] || [ ! -f "$return_zip" ]; then rm -f "$return_zip" "$return_sha"; publish_minimal_return; core_rc=$?; fi'
    new_fallback = '''  if [ ! -f "$return_zip" ]; then
    publish_minimal_return
    core_rc=$?
  elif [ "$core_rc" -ne 0 ]; then
    # The first atomic publication is immutable.  A guard failure is reported
    # by the external receipts/status and must never replace that ZIP identity.
    printf 'RETURN_PRESERVED_AFTER_FINALIZATION_GUARD_FAILURE return=%s guard_exit=%s\\n' "$return_zip" "$core_rc" >&2
  fi'''
    text = replace_once(text, old_fallback, new_fallback, "no-overwrite finalization fallback")
    old_cleanup = '''  cleanup_rc=98
  if [ -f "$return_zip" ]; then
    # DURABLE_RETURN_RECEIPT must be verified before package-owned cleanup.
    python3 - "$return_zip" "$operational_sidecar" <<'PY'
import hashlib,json,pathlib,sys,zipfile
z,s=map(pathlib.Path,sys.argv[1:]); h=hashlib.sha256(); size=0
with z.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""): size+=len(b); h.update(b)
with zipfile.ZipFile(z) as a: names=a.namelist(); bad=a.testzip()
if bad is not None: raise SystemExit("return CRC failure")
s.write_text(json.dumps({"bytes":size,"sha256":h.hexdigest(),"members":names},indent=2,sort_keys=True)+"\\n")
PY
    python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" cleanup-after-durable-return --contract "$operational_contract" --attempt-root "$run_root" --return-zip "$return_zip" --sidecar "$operational_sidecar" --owned-leaf "evidence/observer" --receipt "$durable_return_receipt"
    durable_rc=$?
    [ "$durable_rc" -eq 0 ] && python3 "$package_root/package_tools/server_package_attempt_cleanup.py" --server-root "$server_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --run-root "$run_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip" --finalization-guard-receipt "$finalization_guard_receipt" --output "$post_durable_cleanup_receipt"
    cleanup_rc=$?
    [ -f "$post_durable_cleanup_receipt" ] && cp -f "$post_durable_cleanup_receipt" "$cleanup_receipt"
  fi'''
    new_cleanup = '''  cleanup_rc=98
  finalization_guard_ok=false
  if [ -f "$finalization_guard_receipt" ]; then
    finalization_guard_ok="$(python3 - "$finalization_guard_receipt" <<'PY'
import json,pathlib,sys
d=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(str(d.get("pass") is True and d.get("process_fully_reaped") is True and d.get("termination",{}).get("process_tree_reaped") is True and not d.get("termination",{}).get("owned_pids_remaining")).lower())
PY
)"
  fi
  if [ -f "$return_zip" ] && [ "$finalization_guard_ok" = true ]; then
    # DURABLE_RETURN_RECEIPT must be verified before package-owned cleanup.
    python3 - "$return_zip" "$operational_sidecar" <<'PY'
import hashlib,json,pathlib,sys,zipfile
z,s=map(pathlib.Path,sys.argv[1:]); h=hashlib.sha256(); size=0
with z.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""): size+=len(b); h.update(b)
with zipfile.ZipFile(z) as a: names=a.namelist(); bad=a.testzip()
if bad is not None: raise SystemExit("return CRC failure")
s.write_text(json.dumps({"bytes":size,"sha256":h.hexdigest(),"members":names},indent=2,sort_keys=True)+"\\n")
PY
    python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" cleanup-after-durable-return --contract "$operational_contract" --attempt-root "$run_root" --return-zip "$return_zip" --sidecar "$operational_sidecar" --owned-leaf "evidence/observer" --receipt "$durable_return_receipt"
    durable_rc=$?
    [ "$durable_rc" -eq 0 ] && python3 "$package_root/package_tools/server_package_attempt_cleanup.py" --server-root "$server_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --run-root "$run_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip" --finalization-guard-receipt "$finalization_guard_receipt" --output "$post_durable_cleanup_receipt"
    cleanup_rc=$?
    [ -f "$post_durable_cleanup_receipt" ] && cp -f "$post_durable_cleanup_receipt" "$cleanup_receipt"
  elif [ -f "$return_zip" ]; then
    printf 'CLEANUP_BLOCKED_INVALID_FINALIZATION_GUARD return=%s receipt=%s\\n' "$return_zip" "$finalization_guard_receipt" >&2
    cleanup_rc=122
  fi'''
    text = replace_once(text, old_cleanup, new_cleanup, "valid-finalization cleanup gate")
    path.write_text(text, encoding="utf-8", newline="\n")


def update_contracts() -> None:
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    operational_receipts = {
        f"{NEW}_return/evidence/DURABLE_RETURN_RECEIPT.json",
        f"{NEW}_return/evidence/POST_DURABLE_CLEANUP_RECEIPT.json",
    }
    for member in sorted(operational_receipts):
        if member not in allow["required"]:
            allow["required"].append(member)
    allow["external_receipts"] = [
        "{return_zip}.sha256",
        "{return_zip}.operational.json",
        "{package_id}_{execution_id}_DURABLE_RETURN_RECEIPT.json",
        "{return_zip}.cleanup.json",
    ]
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

    runner_contract_path = TREE / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["package_id"] = NEW
    runner_contract.pop("compile_log_normalizer_arity_contract", None)
    runner_contract["runner_sha256"] = sha_file(TREE / "PREPARE_AND_RUN.sh")
    runner_contract_path.write_bytes(canonical(runner_contract))


def regenerate_source_bound_observer() -> None:
    generated = OUT / "source_bound_regenerated"
    generated.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "tools/generate_server_source_bound_observer.py"),
        "materialize",
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
        "source_bound_causal_observer.svh": (
            "diagnostics/source_bound_causal_observer.svh",
            "tb_probe/source_bound_causal_observer.svh",
        ),
        "source_bound_causal_parser.py": (
            "diagnostics/source_bound_causal_parser.py",
            "package_tools/source_bound_causal_parser.py",
        ),
        "source_bound_observer_focus.sv": ("diagnostics/source_bound_observer_focus.sv",),
        "source_bound_probe_binding.json": ("diagnostics/source_bound_probe_binding.json",),
        "source_bound_observer_generation_report.json": ("diagnostics/source_bound_observer_generation_report.json",),
    }
    for name, relatives in destinations.items():
        for relative in relatives:
            shutil.copyfile(generated / name, TREE / relative)


def update_manifest_and_provenance() -> None:
    provenance = TREE / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    shutil.copy2(V100_ANALYSIS / "formal_return_analysis.json", provenance / "v100b_formal_return_analysis.json")
    shutil.copy2(V100_ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", provenance / "v100b_package_build_failure_rule_audit.json")
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "node0004-v101b-lcdup-guardprocfix-package-manifest-v1",
        "package_id": NEW,
        "source_package": OLD,
        "previous_version_progress": "v100 production compile/elaboration/link completed, but guard-v2 self-enumerated its transient ps helper as an owned surviving PID and returned 122 before simulation.",
        "current_purpose": "Dynamically test the frozen LC9-to-LC3 tuple10 target after excluding the exact guard process enumerator and hardening no-overwrite/durable-cleanup behavior.",
        "guard_process_fix": "EXCLUDE_EXACT_PS_ENUMERATOR_PID",
        "return_publication_fix": "PRESERVE_FIRST_ATOMIC_PUBLICATION_ON_FINALIZATION_GUARD_FAILURE",
        "cleanup_fix": "REQUIRE_VALID_FULLY_REAPED_FINALIZATION_GUARD_RECEIPT",
        "package_build_failure_rule_audit": "RULE_CONFIRMATION_NO_CHANGE__IMPLEMENTATION_AND_NEGATIVE_CONTROL_ESCAPE",
        "activation_epoch": "observer-operational-guard-live-tree-v2",
        "first_fresh_after_change": True,
        "first_fresh_semantic_version": 4,
        "observer_only_contract_sha256": sha_file(TREE / "contracts/observer_only_wide_causal_contract.json"),
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_status": "STORAGE_WAIT_OPTIMIZER_MAINLINE_SHARED_AUDIT",
        "server_actions_performed": [],
    })
    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))
    readme = TREE / "README.md"
    readme.write_text(
        "# Serialized Conv node0004 v101 guard process fix\n\n"
        "Previous progress: v100 completed production compile/elaboration/link, but guard-v2 counted its own transient ps enumerator as an unreaped child and blocked simulation.\n\n"
        "Current purpose: keep the exact LC9→LC3 mapper/config, 52-signal observer and tuple10/downstream/natural-terminal/Formal-D target while fixing only process enumeration, immutable return publication and cleanup admission.\n\n"
        "Future command after storage publication and separate server authorization:\n\n"
        f"`bash {NEW}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "This package has not been uploaded or run.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))


def file_map() -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(TREE).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def deterministic_zip() -> None:
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(f"{NEW}/{path.relative_to(TREE).as_posix()}", (2026, 8, 17, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def write_build_receipt(status: str) -> dict[str, Any]:
    receipt = {
        "schema": "node0004-v101b-lcdup-guardprocfix-build-v1",
        "package_id": NEW,
        "source_zip": {"path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size, "sha256": sha_file(SOURCE_ZIP)},
        "package_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha_file(ZIP)},
        "changed_surface": [
            "fresh package identity",
            "exact ps enumerator PID exclusion",
            "immutable first return publication on finalization-guard failure",
            "valid fully-reaped finalization receipt required before cleanup",
            "external durable/cleanup receipt publication explicitly distinguished from return allowlist contract names",
        ],
        "frozen_surface": ["config", "numeric", "workload", "golden", "functional RTL", "LC9-to-LC3 mapper semantics", "52-signal tuple10 target", "observer-only dump settings"],
        "shared_adjudication_status": "WAIT_OPTIMIZER_MAINLINE_SHARED_AUDIT",
        "server_actions_performed": [],
        "storage_manager_called": False,
        "status": status,
    }
    (OUT / "build_receipt.json").write_bytes(canonical(receipt))
    return receipt


def refresh_existing() -> int:
    if not TREE.is_dir():
        raise SystemExit(f"existing v101 tree absent: {TREE}")
    install_fixed_guard()
    update_contracts()
    regenerate_source_bound_observer()
    update_manifest_and_provenance()
    deterministic_zip()
    print(json.dumps(write_build_receipt("LOCAL_BUILD_PENDING_GATES"), sort_keys=True))
    return 0


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    OUT.mkdir(parents=True)
    safe_extract()
    replace_identity()
    install_fixed_guard()
    harden_runner()
    update_contracts()
    regenerate_source_bound_observer()
    update_manifest_and_provenance()
    deterministic_zip()
    receipt = write_build_receipt("LOCAL_BUILD_PENDING_GATES")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(refresh_existing() if "--refresh-existing" in sys.argv[1:] else main())
