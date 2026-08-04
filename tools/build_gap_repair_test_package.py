#!/usr/bin/env python3
"""Build the GAP v9 D-index plus GA RTL-repair server test ZIP."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_ga_rtl_repair import (  # noqa: E402
    DEFAULT_OUTPUT_REL as RTL_REPAIR_REL,
    validate_gap_ga_rtl_repair,
)
from resnet50_pipeline.gap_repair_workload import (  # noqa: E402
    DEFAULT_OUTPUT_REL as SOURCE_WORKLOAD_REL,
    RELEASE_GATE_REL,
    validate_gap_repair_workload,
)
from resnet50_pipeline.gap_repair_release import (  # noqa: E402
    validate_gap_repair_release_gate,
)
from tools.build_gap_probe_test_package import (  # noqa: E402
    MANIFEST_NAME,
    GapProbePackageError,
    _audit_zip,
    _github_reference_identity,
    _readme as _v7_readme,
    _records,
    _reference_server_identity,
    _sha256,
    _tree_sha256,
    _write_deterministic_zip,
    _write_lf,
)


SCHEMA = "resnet50-gap-repair-test-package-v9"
INSTALL_NAME = "gap_hwop0071_sum_repair_v9"
DEFAULT_OUTPUT_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages"
) / INSTALL_NAME


def _run_script(install_name: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
workload_root="${{package_root}}/workload"
patch_root="${{package_root}}/rtl_patch"
ndp_root="$(cd "$1" && pwd)"
tb="${{ndp_root}}/tb_NDP_Top_new_phy.sv"
cfg_root="${{ndp_root}}/install/cfg_pkg/{install_name}"
repair_run_dir="${{ndp_root}}/run_{install_name}"
evidence_root="${{ndp_root}}/probe_evidence_{install_name}"
backup_root="${{evidence_root}}/rtl_backups"
package_manifest="${{package_root}}/{MANIFEST_NAME}"
return_zip="${{ndp_root}}/{install_name}_return.zip"
return_sha="${{return_zip}}.sha256"
rtl_installed=0

restore_rtl_on_exit() {{
  if [ "${{rtl_installed}}" -eq 1 ]; then
    python3 "${{package_root}}/tb_probe/install_gap_ga_rtl_repair.py" \
      --action restore \
      --ndp-root "${{ndp_root}}" \
      --patch-root "${{patch_root}}" \
      --backup-root "${{backup_root}}" \
      --report "${{evidence_root}}/rtl_patch_restore_report.json" || true
  fi
}}
trap restore_rtl_on_exit EXIT

for required in \
  "${{tb}}" \
  "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy" \
  "${{ndp_root}}/rtl" \
  "${{patch_root}}/RTL_PATCH_MANIFEST.json"; do
  if [ ! -e "${{required}}" ]; then
    echo "Missing required server/package input: ${{required}}" >&2
    exit 3
  fi
done
if ! grep -Fq '$(VCS_EXTRA_OPTS)' "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy"; then
  echo "Server Makefile does not forward VCS_EXTRA_OPTS" >&2
  exit 3
fi
for fresh_target in \
  "${{cfg_root}}" \
  "${{repair_run_dir}}" \
  "${{evidence_root}}" \
  "${{ndp_root}}/{install_name}_return" \
  "${{return_zip}}" \
  "${{return_sha}}"; do
  if [ -e "${{fresh_target}}" ]; then
    echo "Fresh v9 target already exists; refusing reuse: ${{fresh_target}}" >&2
    exit 4
  fi
done

vcs_extra_opts="${{VCS_EXTRA_OPTS:-}}"
vcs_extra_opts="${{vcs_extra_opts}} +incdir+${{ndp_root}}"
server_command="make -f Makefile.tb_NDP_Top_new_phy compile sim DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=${{repair_run_dir}} VCS_EXTRA_OPTS=${{vcs_extra_opts# }} PLUSARGS='+SCA_CFG=install/cfg_pkg/{install_name}/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/{install_name}/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_FILE=${{evidence_root}}/return_observer.log +RETURN_OBS_SLICE=0 +RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 +RETURN_OBS_STALL_CYCLES=4096 +RETURN_OBS_HEARTBEAT_CYCLES=4096'"
mkdir "${{evidence_root}}"
printf '%s\\n' "${{server_command}}" > "${{evidence_root}}/server_command.txt"

python3 "${{package_root}}/tb_probe/capture_gap_probe_server_identity.py" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase pre_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_pre_install.json"

mkdir -p "${{ndp_root}}/install"
cp -a "${{workload_root}}/install/." "${{ndp_root}}/install/"
mkdir "${{cfg_root}}"
cp "${{workload_root}}/sca_cfg.json" "${{cfg_root}}/sca_cfg.json"
cp "${{workload_root}}/sca_cfg_D.json" "${{cfg_root}}/sca_cfg_D.json"

python3 "${{package_root}}/tb_probe/install_native_return_observer.py" \
  --tb "${{tb}}" \
  --observer "${{package_root}}/tb_probe/native_return_observer.svh" \
  --fix-run-time \
  > "${{evidence_root}}/observer_install_report.json"

installed_observer="${{ndp_root}}/native_return_observer.svh"
test -s "${{installed_observer}}"
cmp -s "${{package_root}}/tb_probe/native_return_observer.svh" "${{installed_observer}}"
grep -Fq '`include "native_return_observer.svh"' "${{tb}}"
grep -Fq "longint unsigned RUN_TIME = 64'd100000000000000;" "${{tb}}"

python3 "${{package_root}}/tb_probe/install_gap_ga_rtl_repair.py" \
  --action install \
  --ndp-root "${{ndp_root}}" \
  --patch-root "${{patch_root}}" \
  --backup-root "${{backup_root}}" \
  --report "${{evidence_root}}/rtl_patch_install_report.json"
rtl_installed=1

python3 "${{package_root}}/tb_probe/capture_gap_probe_server_identity.py" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_install.json"

cd "${{ndp_root}}"
set +e
make -f Makefile.tb_NDP_Top_new_phy compile sim \
  DUMP_VCD=0 \
  DUMP_FSDB=0 \
  TB_DUMP_FSDB=0 \
  RUN_DIR="${{repair_run_dir}}" \
  VCS_EXTRA_OPTS="${{vcs_extra_opts# }}" \
  PLUSARGS="+SCA_CFG=install/cfg_pkg/{install_name}/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/{install_name}/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_FILE=${{evidence_root}}/return_observer.log +RETURN_OBS_SLICE=0 +RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 +RETURN_OBS_STALL_CYCLES=4096 +RETURN_OBS_HEARTBEAT_CYCLES=4096"
run_status=$?
set -e
printf '%s\\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"

set +e
python3 "${{package_root}}/tb_probe/capture_gap_probe_server_identity.py" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_run \
  --server-command "${{server_command}}" \
  --exit-status "${{run_status}}" \
  --output "${{evidence_root}}/server_identity_post_run.json"
identity_status=$?

python3 "${{package_root}}/tb_probe/install_gap_ga_rtl_repair.py" \
  --action restore \
  --ndp-root "${{ndp_root}}" \
  --patch-root "${{patch_root}}" \
  --backup-root "${{backup_root}}" \
  --report "${{evidence_root}}/rtl_patch_restore_report.json"
restore_status=$?
if [ "${{restore_status}}" -eq 0 ]; then
  rtl_installed=0
fi

python3 "${{package_root}}/tb_probe/capture_gap_probe_server_identity.py" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_restore \
  --server-command "${{server_command}}" \
  --exit-status "${{run_status}}" \
  --output "${{evidence_root}}/server_identity_post_restore.json"
post_restore_identity_status=$?

python3 "${{package_root}}/tb_probe/build_gap_probe_return.py" \
  --ndp-root "${{ndp_root}}" \
  --run-dir "${{repair_run_dir}}" \
  --evidence-root "${{evidence_root}}" \
  --package-root "${{package_root}}" \
  --install-name "{install_name}" \
  --output-dir "${{ndp_root}}" \
  --run-status "${{run_status}}" \
  --server-command "${{server_command}}"
package_status=$?
set -e

if [ -f "${{return_zip}}" ] && [ -f "${{return_sha}}" ]; then
  echo "Return ZIP: ${{return_zip}}"
  echo "Return SHA256: ${{return_sha}}"
fi
if [ "${{run_status}}" -ne 0 ]; then exit "${{run_status}}"; fi
if [ "${{identity_status}}" -ne 0 ]; then exit "${{identity_status}}"; fi
if [ "${{restore_status}}" -ne 0 ]; then exit "${{restore_status}}"; fi
if [ "${{post_restore_identity_status}}" -ne 0 ]; then
  exit "${{post_restore_identity_status}}"
fi
exit "${{package_status}}"
"""


def _readme(install_name: str) -> str:
    return f"""# GAP HWOP0071 D-index + GA control repair v9

This package tests two independently identified fixes:

1. the address-bound GAP config uses the exact four-field LC2 repair and the
   patched native flow fully regenerated planner, encoder, bitstream, execplan,
   and both SCA files. Static enumeration proves 256 distinct 32-byte
   transaction bases (512 distinct 128-bit write addresses) per active slice;
2. a hash-gated GA RTL repair resets outbuffer occupancy when both tags are
   invalidated, stalls INT32 feedback until the selected slot is valid, and
   forces invalid feedback tag/data to zero.

This is a server test candidate, not a released E4/E5 result. The package
temporarily installs two complete RTL files only after their
canonical preimage hashes match the v7 server identity. It saves exact backups,
recompiles in `run_{install_name}`, captures patched identities, then restores
the original bytes and captures a post-restore identity. An EXIT trap attempts
the same restore if the run stops early. The package never edits the local
`NDP_copy01` source reference.

## Run

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Both SCA paths are explicit, all waveform controls are zero, and the same
bounded GA state observer remains enabled. If an external SIGKILL prevents the
EXIT trap, restore manually before another run:

```bash
python3 tb_probe/install_gap_ga_rtl_repair.py \\
  --action restore \\
  --ndp-root /absolute/path/to/NDP_copyXX \\
  --patch-root rtl_patch \\
  --backup-root /absolute/path/to/NDP_copyXX/probe_evidence_{install_name}/rtl_backups \\
  --report /absolute/path/to/NDP_copyXX/probe_evidence_{install_name}/rtl_patch_restore_report.json
```

## Return

Return only:

```text
{install_name}_return.zip
{install_name}_return.zip.sha256
```

The allowlist contains identities, install/restore receipts, compact logs,
both SCA files, 16 formal D readbacks, and four optional slice-0 numeric logs.
No waveform or build tree is returned. Release still requires all 16x512
readback rows to match golden, all eight ordinary GA PEs to keep count in
0..2, zero invalid-slot reuse, correct cross-block C initialization, focused
identity stability, and a separate E5 repeat.
"""


def validate_package(project_root: Path, output: Path) -> dict:
    root = project_root.resolve()
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    manifest_path = package / MANIFEST_NAME
    for required in (package, zip_path, sha_path, manifest_path):
        if not required.exists():
            raise GapProbePackageError(f"v9 package input missing: {required}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("status") != "server_repair_test_package_ready"
        or manifest.get("install_name") != INSTALL_NAME
        or package.name != INSTALL_NAME
    ):
        raise GapProbePackageError("v9 package identity differs")
    workload = validate_gap_repair_workload(root, package / "workload")
    source_workload = validate_gap_repair_workload(root, root / SOURCE_WORKLOAD_REL)
    if workload != source_workload:
        raise GapProbePackageError("v9 copied workload differs")
    source_repair = validate_gap_ga_rtl_repair(root, root / RTL_REPAIR_REL)
    repair = source_repair
    package_repair_files = _records(package / "rtl_patch", exclude_manifest=False)
    source_repair_files = _records(root / RTL_REPAIR_REL, exclude_manifest=False)
    if package_repair_files != source_repair_files:
        raise GapProbePackageError("v9 copied RTL repair differs")
    gate_path = root / RELEASE_GATE_REL
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    validate_gap_repair_release_gate(root, gate)
    copied_gate = json.loads(
        (package / "validation" / "GAP_REPAIR_RELEASE_GATE.json").read_text(
            encoding="utf-8"
        )
    )
    if copied_gate != gate:
        raise GapProbePackageError("v9 copied GAP release gate differs")
    records = _records(package, exclude_manifest=True)
    if (
        manifest.get("files") != records
        or manifest.get("payload_file_count") != len(records)
        or manifest.get("payload_tree_sha256") != _tree_sha256(records)
    ):
        raise GapProbePackageError("v9 package tree receipt differs")
    rtl_files = sorted(
        relative
        for relative in records
        if Path(relative).suffix.lower() in {".v", ".sv"}
    )
    expected_rtl = sorted(
        f"rtl_patch/{relative}"
        for relative in source_repair["files"]
    )
    if rtl_files != expected_rtl:
        raise GapProbePackageError("v9 functional RTL allowlist differs")
    if any(
        Path(relative).suffix.lower()
        in {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar"}
        for relative in records
    ):
        raise GapProbePackageError("v9 package contains nested archive")
    if (
        (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        != _run_script(INSTALL_NAME)
        or (package / "README.md").read_text(encoding="utf-8")
        != _readme(INSTALL_NAME)
    ):
        raise GapProbePackageError("v9 generated control text differs")
    policy = manifest.get("repair_policy", {})
    if (
        policy.get("functional_rtl_v_or_sv_included") is not True
        or policy.get("functional_rtl_file_count") != 2
        or policy.get("server_install_hash_gated") is not True
        or policy.get("server_restore_required") is not True
        or policy.get("post_restore_identity_required") is not True
        or policy.get("waveforms_explicitly_disabled")
        != {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0}
    ):
        raise GapProbePackageError("v9 repair policy differs")
    if (
        manifest.get("candidate_release") is not False
        or manifest.get("rules", {}).get("release_gate_sha256") != _sha256(gate_path)
        or manifest.get("rules", {}).get("dynamic_release_pending")
        != gate["remaining_blockers"]
    ):
        raise GapProbePackageError("v9 dynamic release policy differs")
    audit = _audit_zip(package, zip_path)
    zip_sha256 = _sha256(zip_path)
    if sha_path.read_text(encoding="ascii") != f"{zip_sha256}  {zip_path.name}\n":
        raise GapProbePackageError("v9 sidecar differs")
    return {
        "schema": SCHEMA,
        "status": "server_repair_test_package_validated",
        "directory": package.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "payload_file_count": len(records),
        "payload_tree_sha256": _tree_sha256(records),
        "functional_rtl_file_count": len(rtl_files),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha256,
        "zip_audit": audit,
        "expected_return_zip": f"{INSTALL_NAME}_return.zip",
        "expected_return_sha256": f"{INSTALL_NAME}_return.zip.sha256",
    }


def build_package(project_root: Path, output: Path) -> dict:
    root = project_root.resolve()
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    for target in (package, zip_path, sha_path):
        if target.exists():
            raise GapProbePackageError(f"v9 output must be fresh: {target}")
    workload = validate_gap_repair_workload(root, root / SOURCE_WORKLOAD_REL)
    repair = validate_gap_ga_rtl_repair(root, root / RTL_REPAIR_REL)
    package.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / SOURCE_WORKLOAD_REL, package / "workload")
    shutil.copytree(root / RTL_REPAIR_REL, package / "rtl_patch")
    gate_path = root / RELEASE_GATE_REL
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    validate_gap_repair_release_gate(root, gate)
    _write_lf(
        package / "validation" / "GAP_REPAIR_RELEASE_GATE.json",
        gate_path.read_text(encoding="utf-8"),
    )
    for relative in (
        Path("NDP_copy01/native_return_observer.svh"),
        Path("tools/install_native_return_observer.py"),
        Path("tools/install_gap_ga_rtl_repair.py"),
        Path("tools/capture_gap_probe_server_identity.py"),
        Path("tools/build_gap_probe_return.py"),
    ):
        destination = package / "tb_probe" / relative.name
        _write_lf(destination, (root / relative).read_text(encoding="utf-8"))
    _write_lf(package / "PREPARE_AND_RUN.sh", _run_script(INSTALL_NAME))
    _write_lf(package / "README.md", _readme(INSTALL_NAME))
    records = _records(package, exclude_manifest=True)
    manifest = {
        "schema": SCHEMA,
        "status": "server_repair_test_package_ready",
        "candidate_release": False,
        "install_name": INSTALL_NAME,
        "source_workload": {
            "path": SOURCE_WORKLOAD_REL.as_posix(),
            "file_count": workload["file_count"],
            "tree_sha256": workload["tree_sha256"],
            "manifest_sha256": _sha256(
                root / SOURCE_WORKLOAD_REL / "gap_package_manifest.json"
            ),
            "full_rebuild_execplan_evidence": workload["full_rebuild"][
                "source_execplan_evidence"
            ],
            "planner_encoder_bitstream_execplan_sca_regenerated": True,
            "lc2_exact_four_field_diff": workload["d_index_config"][
                "lc2_exact_four_field_diff"
            ],
            "d_index_transaction_bases_per_slice": 256,
            "expected_unique_128bit_write_addresses_per_slice": 512,
        },
        "rtl_repair": {
            "path": RTL_REPAIR_REL.as_posix(),
            "repair_id": repair["repair_id"],
            "manifest_sha256": _sha256(
                root / RTL_REPAIR_REL / "RTL_PATCH_MANIFEST.json"
            ),
            "files": repair["files"],
        },
        "repair_policy": {
            "functional_rtl_v_or_sv_included": True,
            "functional_rtl_file_count": 2,
            "functional_rtl_scope": sorted(repair["files"]),
            "server_install_hash_gated": True,
            "server_exact_backup_before_install": True,
            "server_restore_required": True,
            "exit_trap_restore_enabled": True,
            "post_restore_identity_required": True,
            "source_reference_modified": False,
            "observer_is_read_only": True,
            "ga_accumulator_event_limit": 512,
            "waveforms_explicitly_disabled": {
                "DUMP_VCD": 0,
                "DUMP_FSDB": 0,
                "TB_DUMP_FSDB": 0,
            },
        },
        "identity_policy": {
            "capture_phases": [
                "pre_install",
                "post_install",
                "post_run",
                "post_restore",
            ],
            "functional_rtl_tree_hashed": True,
            "focused_rtl_canonical_text_hashes": True,
            "testbench_before_after_hashed": True,
        },
        "rules": {
            "release_gate_path": RELEASE_GATE_REL.as_posix(),
            "release_gate_sha256": _sha256(gate_path),
            "rule_ids": gate["rule_ids"],
            "dynamic_release_pending": gate["remaining_blockers"],
            "generic_validator_is_semantic_release": False,
            "server_result_required_for_e4_e5": True,
        },
        "return_policy": {
            "direct_zip_and_sha256": True,
            "allowlist_only": True,
            "zip_limit_bytes": 16 * 1024 * 1024,
            "extracted_limit_bytes": 32 * 1024 * 1024,
            "individual_text_limit_bytes": 8 * 1024 * 1024,
            "waveforms_forbidden": True,
            "build_trees_forbidden": True,
            "nested_archives_forbidden": True,
        },
        "reference_server_identity": _reference_server_identity(root),
        "github_reference_identity": _github_reference_identity(root),
        "run_entry": "PREPARE_AND_RUN.sh",
        "payload_file_count": len(records),
        "payload_tree_sha256": _tree_sha256(records),
        "files": records,
    }
    _write_lf(
        package / MANIFEST_NAME,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    _write_deterministic_zip(package, zip_path)
    audit = _audit_zip(package, zip_path)
    zip_sha256 = _sha256(zip_path)
    _write_lf(sha_path, f"{zip_sha256}  {zip_path.name}\n")
    return {
        **manifest,
        "directory": package.as_posix(),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha256,
        "zip_audit": audit,
        "sha256_file": sha_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        report = (
            validate_package(ROOT, output)
            if args.validate_only
            else build_package(ROOT, output)
        )
    except Exception as error:
        print(f"GAP v9 repair package failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
