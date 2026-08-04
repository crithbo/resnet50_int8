#!/usr/bin/env python3
"""Build the GAP v10 corrected-config plus stock-RTL decision test ZIP."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_repair_release import (  # noqa: E402
    validate_gap_repair_release_gate,
)
from resnet50_pipeline.gap_repair_workload import (  # noqa: E402
    DEFAULT_OUTPUT_REL as SOURCE_WORKLOAD_REL,
    RELEASE_GATE_REL,
    validate_gap_repair_workload,
)
from tools.build_gap_probe_test_package import (  # noqa: E402
    MANIFEST_NAME,
    GapProbePackageError,
    _audit_zip,
    _github_reference_identity,
    _records,
    _reference_server_identity,
    _sha256,
    _tree_sha256,
    _write_deterministic_zip,
    _write_lf,
)


SCHEMA = "resnet50-gap-stock-rtl-decision-test-package-v10"
DECISION_GATE_SCHEMA = "resnet50-gap-stock-rtl-decision-gate-v1"
INSTALL_NAME = "gap_hwop0071_sum_configfix_stockrtl_v10"
DEFAULT_OUTPUT_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages"
) / INSTALL_NAME
MANDATORY_RULES = [
    ".agents/rules/算子配置规则.md",
    ".agents/rules/GAP_probe_v7_validator_rules.md",
    ".agents/rules/GAP_repair_candidate_rules.md",
    ".agents/rules/服务器测试包生成规则.md",
    "ndp-sim-ref/model_execplan/readme.md",
]
DECISION_GATE_NAME = "GAP_STOCK_RTL_DECISION_GATE.json"


def _run_script(install_name: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
workload_root="${{package_root}}/workload"
ndp_root="$(cd "$1" && pwd)"
tb="${{ndp_root}}/tb_NDP_Top_new_phy.sv"
cfg_root="${{ndp_root}}/install/cfg_pkg/{install_name}"
decision_run_dir="${{ndp_root}}/run_{install_name}"
evidence_root="${{ndp_root}}/probe_evidence_{install_name}"
package_manifest="${{package_root}}/{MANIFEST_NAME}"
return_zip="${{ndp_root}}/{install_name}_return.zip"
return_sha="${{return_zip}}.sha256"

for required in \
  "${{tb}}" \
  "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy" \
  "${{ndp_root}}/rtl"; do
  if [ ! -e "${{required}}" ]; then
    echo "Missing required server input: ${{required}}" >&2
    exit 3
  fi
done
if ! grep -Fq '$(VCS_EXTRA_OPTS)' "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy"; then
  echo "Server Makefile does not forward VCS_EXTRA_OPTS" >&2
  exit 3
fi
for fresh_target in \
  "${{cfg_root}}" \
  "${{decision_run_dir}}" \
  "${{evidence_root}}" \
  "${{ndp_root}}/{install_name}_return" \
  "${{return_zip}}" \
  "${{return_sha}}"; do
  if [ -e "${{fresh_target}}" ]; then
    echo "Fresh v10 target already exists; refusing reuse: ${{fresh_target}}" >&2
    exit 4
  fi
done

vcs_extra_opts="${{VCS_EXTRA_OPTS:-}}"
vcs_extra_opts="${{vcs_extra_opts}} +incdir+${{ndp_root}}"
server_command="make -f Makefile.tb_NDP_Top_new_phy compile sim DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=${{decision_run_dir}} VCS_EXTRA_OPTS=${{vcs_extra_opts# }} PLUSARGS='+SCA_CFG=install/cfg_pkg/{install_name}/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/{install_name}/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_FILE=${{evidence_root}}/return_observer.log +RETURN_OBS_SLICE=0 +RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 +RETURN_OBS_STALL_CYCLES=4096 +RETURN_OBS_HEARTBEAT_CYCLES=4096'"
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
  RUN_DIR="${{decision_run_dir}}" \
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
post_run_identity_status=$?

# No functional RTL action occurs in this package.  The phase name is retained
# so the common GAP return contract can prove the final bytes still equal the
# pre-run bytes without treating a missing repair receipt as an implicit pass.
python3 "${{package_root}}/tb_probe/capture_gap_probe_server_identity.py" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_restore \
  --server-command "${{server_command}}" \
  --exit-status "${{run_status}}" \
  --output "${{evidence_root}}/server_identity_post_restore.json"
post_restore_identity_status=$?

python3 "${{package_root}}/tb_probe/verify_gap_stock_rtl_identity.py" \
  --pre-install "${{evidence_root}}/server_identity_pre_install.json" \
  --post-install "${{evidence_root}}/server_identity_post_install.json" \
  --post-run "${{evidence_root}}/server_identity_post_run.json" \
  --post-restore "${{evidence_root}}/server_identity_post_restore.json" \
  --output "${{evidence_root}}/stock_rtl_identity_receipt.json"
stock_rtl_identity_status=$?

python3 "${{package_root}}/tb_probe/build_gap_probe_return.py" \
  --ndp-root "${{ndp_root}}" \
  --run-dir "${{decision_run_dir}}" \
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
if [ "${{post_run_identity_status}}" -ne 0 ]; then
  exit "${{post_run_identity_status}}"
fi
if [ "${{post_restore_identity_status}}" -ne 0 ]; then
  exit "${{post_restore_identity_status}}"
fi
if [ "${{stock_rtl_identity_status}}" -ne 0 ]; then
  exit "${{stock_rtl_identity_status}}"
fi
exit "${{package_status}}"
"""


def _readme(install_name: str) -> str:
    return f"""# GAP HWOP0071 corrected-config + stock-RTL decision v10

This package isolates one question: after the exact LC2 correction and the
full planner/encoder/mapping/bitstream/execplan/SCA rebuild, does the original
server RTL still reproduce the v7 GA accumulator failure?

No functional RTL file is included, installed, replaced, backed up, or
restored. In particular, the package never writes:

```text
rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv
rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv
```

The only source installation is the read-only TB observer outside `rtl/`.
Server identities are captured before preparation, after preparation, after
the run, and once more as the common final/post-restore phase. A dedicated
receipt requires the complete RTL tree and every focused RTL file to remain
byte-stable across all four phases. Absolute equality with local or GitHub RTL
is recorded but is not required.

This remains `candidate_release=false / E2_LOCAL_ONLY` until the server return
is analyzed.

## Run

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

The run explicitly binds both SCA files, disables VCD/FSDB generation, and
captures the same bounded GA state observer used by v7.

## Decision boundary

- If `count=3`, invalid-slot C reuse, or cross-block stale C reappears, the
  corrected configuration did not remove the RTL-control blocker.
- If all 8 PE traces remain legal and all 16x512 formal D readback rows match
  independent golden, the result is evidence that an RTL patch is unnecessary
  for this corrected workload. Under the current orthogonal-defects rule, that
  clean result must still be reviewed before formally removing the historical
  RTL blocker.

## Return

Return only:

```text
{install_name}_return.zip
{install_name}_return.zip.sha256
```

The return builder is allowlist-only. It excludes waveforms, compiler build
trees, nested archives, and the copied workload. It includes compact identity
receipts, logs, both runtime SCA files, and the 16 formal D readbacks.
"""


def _decision_gate(
    *,
    project_root: Path,
    workload: dict,
    source_gate: dict,
) -> dict:
    gate_path = project_root / RELEASE_GATE_REL
    return {
        "schema": DECISION_GATE_SCHEMA,
        "status": "local_preconditions_passed_server_stock_rtl_decision_pending",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "install_name": INSTALL_NAME,
        "objective": (
            "test corrected LC2 configuration with the server original "
            "functional RTL and no RTL patch installation"
        ),
        "rules_read_before_package_generation": MANDATORY_RULES,
        "rule_ids": source_gate["rule_ids"],
        "source_release_gate": {
            "path": RELEASE_GATE_REL.as_posix(),
            "sha256": _sha256(gate_path),
            "candidate_release": source_gate["candidate_release"],
            "evidence_level": source_gate["evidence_level"],
        },
        "source_workload": {
            "path": SOURCE_WORKLOAD_REL.as_posix(),
            "schema": workload["schema"],
            "tree_sha256": workload["tree_sha256"],
            "file_count": workload["file_count"],
        },
        "config_semantics": {
            "lc2_exact_four_field_diff": workload["d_index_config"][
                "lc2_exact_four_field_diff"
            ],
            "full_rebuild_reused_without_semantic_change": True,
            "planner_encoder_mapping_bitstream_execplan_sca_regenerated": True,
            "transaction_bases_32byte_per_slice": 256,
            "unique_write_addresses_128bit_per_slice": 512,
        },
        "functional_rtl": {
            "mode": "server_original_unmodified",
            "functional_rtl_files_in_package": 0,
            "functional_rtl_write_requested": False,
            "rtl_patch_install": "FORBIDDEN",
            "identity_phases": [
                "pre_install",
                "post_install",
                "post_run",
                "post_restore",
            ],
            "all_phase_byte_stability_required": True,
        },
        "server_decision": {
            "failure_reproduced_if_any": [
                "outbuffer_count_outside_0_to_2",
                "invalid_slot_reused_as_input_c",
                "new_block_c_nonzero_before_new_partial",
                "formal_d_readback_golden_mismatch",
            ],
            "clean_workload_evidence_requires_all": [
                "16_slices_x_512_formal_d_rows_match_golden",
                "8_ordinary_pes_never_count_3",
                "invalid_slot_reuse_count_zero",
                "cross_block_initial_c_zero",
                "focused_rtl_identity_stable_all_phases",
            ],
            "clean_run_does_not_auto_override_current_rule": (
                "CDA-GAP-ORTHOGONAL-DEFECTS-001"
            ),
        },
        "remaining_blockers": source_gate["remaining_blockers"],
    }


def validate_package(project_root: Path, output: Path) -> dict:
    root = project_root.resolve()
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    manifest_path = package / MANIFEST_NAME
    for required in (package, zip_path, sha_path, manifest_path):
        if not required.exists():
            raise GapProbePackageError(f"v10 package input missing: {required}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("status")
        != "server_stock_rtl_decision_test_package_ready"
        or manifest.get("install_name") != INSTALL_NAME
        or package.name != INSTALL_NAME
    ):
        raise GapProbePackageError("v10 package identity differs")

    workload = validate_gap_repair_workload(root, package / "workload")
    source_workload = validate_gap_repair_workload(
        root, root / SOURCE_WORKLOAD_REL
    )
    if workload != source_workload:
        raise GapProbePackageError("v10 copied workload differs")

    source_gate_path = root / RELEASE_GATE_REL
    source_gate = json.loads(source_gate_path.read_text(encoding="utf-8"))
    validate_gap_repair_release_gate(root, source_gate)
    expected_decision_gate = _decision_gate(
        project_root=root,
        workload=source_workload,
        source_gate=source_gate,
    )
    copied_decision_gate = json.loads(
        (package / "validation" / DECISION_GATE_NAME).read_text(
            encoding="utf-8"
        )
    )
    if copied_decision_gate != expected_decision_gate:
        raise GapProbePackageError("v10 decision gate differs")

    records = _records(package, exclude_manifest=True)
    if (
        manifest.get("files") != records
        or manifest.get("payload_file_count") != len(records)
        or manifest.get("payload_tree_sha256") != _tree_sha256(records)
    ):
        raise GapProbePackageError("v10 package tree receipt differs")
    if (package / "rtl_patch").exists():
        raise GapProbePackageError("v10 must not contain an RTL patch directory")
    functional_rtl = sorted(
        relative
        for relative in records
        if Path(relative).suffix.lower() in {".v", ".sv"}
    )
    if functional_rtl:
        raise GapProbePackageError(
            f"v10 contains functional RTL files: {functional_rtl}"
        )
    if "tb_probe/native_return_observer.svh" not in records:
        raise GapProbePackageError("v10 observer include is missing")
    if any(
        Path(relative).suffix.lower()
        in {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z", ".rar"}
        for relative in records
    ):
        raise GapProbePackageError("v10 package contains nested archive")
    if (
        (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        != _run_script(INSTALL_NAME)
        or (package / "README.md").read_text(encoding="utf-8")
        != _readme(INSTALL_NAME)
    ):
        raise GapProbePackageError("v10 generated control text differs")
    script = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    forbidden_script_tokens = (
        "install_gap_ga_rtl_repair.py",
        "--action install",
        "--action restore",
        "rtl_patch",
    )
    if any(token in script for token in forbidden_script_tokens):
        raise GapProbePackageError("v10 run script contains an RTL repair action")

    policy = manifest.get("rtl_policy", {})
    if (
        policy.get("mode") != "server_original_unmodified"
        or policy.get("functional_rtl_v_or_sv_included") is not False
        or policy.get("functional_rtl_file_count") != 0
        or policy.get("functional_rtl_write_requested") is not False
        or policy.get("stock_rtl_identity_receipt_required") is not True
        or policy.get("waveforms_explicitly_disabled")
        != {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0}
    ):
        raise GapProbePackageError("v10 stock RTL policy differs")
    if (
        manifest.get("candidate_release") is not False
        or manifest.get("evidence_level") != "E2_LOCAL_ONLY"
        or manifest.get("rules", {}).get("mandatory_files_read")
        != MANDATORY_RULES
        or manifest.get("rules", {}).get("dynamic_release_pending")
        != source_gate["remaining_blockers"]
    ):
        raise GapProbePackageError("v10 release claim boundary differs")

    audit = _audit_zip(package, zip_path)
    zip_sha256 = _sha256(zip_path)
    if sha_path.read_text(encoding="ascii") != f"{zip_sha256}  {zip_path.name}\n":
        raise GapProbePackageError("v10 sidecar differs")
    return {
        "schema": SCHEMA,
        "status": "server_stock_rtl_decision_test_package_validated",
        "directory": package.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "payload_file_count": len(records),
        "payload_tree_sha256": _tree_sha256(records),
        "functional_rtl_file_count": len(functional_rtl),
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
            raise GapProbePackageError(f"v10 output must be fresh: {target}")

    workload = validate_gap_repair_workload(root, root / SOURCE_WORKLOAD_REL)
    source_gate_path = root / RELEASE_GATE_REL
    source_gate = json.loads(source_gate_path.read_text(encoding="utf-8"))
    validate_gap_repair_release_gate(root, source_gate)
    decision_gate = _decision_gate(
        project_root=root,
        workload=workload,
        source_gate=source_gate,
    )

    package.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / SOURCE_WORKLOAD_REL, package / "workload")
    _write_lf(
        package / "validation" / DECISION_GATE_NAME,
        json.dumps(decision_gate, ensure_ascii=False, indent=2) + "\n",
    )
    for relative in (
        Path("NDP_copy01/native_return_observer.svh"),
        Path("tools/install_native_return_observer.py"),
        Path("tools/capture_gap_probe_server_identity.py"),
        Path("tools/verify_gap_stock_rtl_identity.py"),
        Path("tools/build_gap_probe_return.py"),
    ):
        destination = package / "tb_probe" / relative.name
        _write_lf(destination, (root / relative).read_text(encoding="utf-8"))
    _write_lf(package / "PREPARE_AND_RUN.sh", _run_script(INSTALL_NAME))
    _write_lf(package / "README.md", _readme(INSTALL_NAME))

    records = _records(package, exclude_manifest=True)
    manifest = {
        "schema": SCHEMA,
        "status": "server_stock_rtl_decision_test_package_ready",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "install_name": INSTALL_NAME,
        "source_workload": {
            "path": SOURCE_WORKLOAD_REL.as_posix(),
            "schema": workload["schema"],
            "file_count": workload["file_count"],
            "tree_sha256": workload["tree_sha256"],
            "manifest_sha256": _sha256(
                root / SOURCE_WORKLOAD_REL / "gap_package_manifest.json"
            ),
            "config_semantics_changed_from_v9": False,
            "full_rebuild_execplan_evidence": workload["full_rebuild"][
                "source_execplan_evidence"
            ],
            "planner_encoder_mapping_bitstream_execplan_sca_regenerated": True,
            "lc2_exact_four_field_diff": workload["d_index_config"][
                "lc2_exact_four_field_diff"
            ],
            "d_index_transaction_bases_per_slice": 256,
            "expected_unique_128bit_write_addresses_per_slice": 512,
        },
        "rtl_policy": {
            "mode": "server_original_unmodified",
            "functional_rtl_v_or_sv_included": False,
            "functional_rtl_file_count": 0,
            "functional_rtl_write_requested": False,
            "rtl_patch_directory_included": False,
            "rtl_patch_install_forbidden": True,
            "compile_uses_server_original_rtl": True,
            "stock_rtl_identity_receipt_required": True,
            "source_reference_modified": False,
            "observer_is_tb_only": True,
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
            "post_restore_phase_is_noop_final_capture": True,
            "functional_rtl_tree_stable_across_all_phases_required": True,
            "focused_rtl_stable_across_all_phases_required": True,
            "absolute_server_local_github_match_required": False,
            "testbench_stable_after_observer_prepare_required": True,
        },
        "decision_policy": {
            "single_variable": "corrected_config_on_server_original_rtl",
            "v7_ga_failure_reproduction_is_decisive": True,
            "clean_run_requires_dynamic_gate_analysis": True,
            "clean_run_auto_clears_orthogonal_rule": False,
        },
        "rules": {
            "mandatory_files_read": MANDATORY_RULES,
            "source_release_gate_path": RELEASE_GATE_REL.as_posix(),
            "source_release_gate_sha256": _sha256(source_gate_path),
            "rule_ids": source_gate["rule_ids"],
            "dynamic_release_pending": source_gate["remaining_blockers"],
            "generic_validator_is_semantic_release": False,
            "server_result_required_for_e4_e5": True,
        },
        "return_policy": {
            "direct_zip_and_sha256": True,
            "allowlist_only": True,
            "stock_rtl_identity_receipt_required": True,
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
        print(f"GAP v10 stock RTL decision package failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
