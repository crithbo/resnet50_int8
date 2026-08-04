#!/usr/bin/env python3
"""Build the one-command, stock-RTL GAP int32_mac server test package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_int32_mac_bypass import (  # noqa: E402
    W3_EXPECTED_PATH,
    W3_INPUT_PATH,
)
from resnet50_pipeline.hashing import sha256_file  # noqa: E402
from resnet50_pipeline.operator_config_validator import (  # noqa: E402
    OperatorConfigValidator,
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
from tools.gap_int32_mac_server_runtime import (  # noqa: E402
    preflight_package,
)


SCHEMA = "resnet50-gap-int32-mac-stock-rtl-onecmd-test-package-v5"
INSTALL_NAME = "gap_int32_mac_stock_rtl_onecmd_v5"
DEFAULT_OUTPUT_REL = (
    Path("artifacts/operator_config_validation/r5-server-test-packages")
    / INSTALL_NAME
)
SOURCE_CONFIG_ROOT = Path("configs/gap_int32_mac_bypass_v1")
SOURCE_E2 = Path(
    "artifacts/operator_config_validation/gap-int32-mac-bypass-v1/"
    "onecmd-v5-local-e2"
)
INSTALL_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}"
SLICE_SHIFT = 25
FINAL_D_BASE = 0xBC000
CONFIG_BASES = tuple(0x100000 + index * 0x10000 for index in range(6))
EXEC_BASE = 0x1A0000
MANDATORY_RULES = [
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/GAP_int32_mac_bypass_rules.md",
    ".agents/rules/GAP_probe_v7_validator_rules.md",
    ".agents/rules/GAP_repair_candidate_rules.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    ".agents/plan.md#0.3",
]
RULE_IDS = [
    "CDA-GAP-INT32MAC-NONTRANSOUT-001",
    "CDA-GAP-INT32MAC-DUAL-INPUT-001",
    "CDA-GAP-INT32MAC-NORMAL-FIFO-001",
    "CDA-GAP-INT32MAC-TREE-001",
    "CDA-GAP-INT32MAC-STAGE-MEMORY-001",
    "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
    "CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001",
    "CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001",
    "CDA-GAP-REPAIR-RETURN-RECEIPTS-001",
    "CDA-GAP-D-READBACK-COVERAGE-001",
    "CDA-GA-OUTBUFFER-OCCUPANCY-001",
    "CDA-GA-INVALID-SLOT-ISOLATION-001",
    "CDA-GA-CROSS-BLOCK-INIT-001",
    "CDA-MSE4-MONITOR-EVIDENCE-001",
    "CDA-SERVER-FOCUSED-IDENTITY-001",
]
REJECTED_PACKAGE = {
    "name": "gap_int32_mac_stock_rtl_atomic_v1",
    "sha256": "3ed9baf25f884d53eab7ccdb75d3dc3947f5091107ca3a242e9aff31a5bcf0f9",
    "reused": False,
    "reason": "replaced because it exposed multi-step server operation",
}
SUPERSEDED_LOCAL_DRAFTS = [
    {
        "name": "gap_int32_mac_stock_rtl_onecmd_v2",
        "released": False,
        "status": "local_validator_failed",
        "reason": "copied Windows CRLF 128-bit payloads",
    },
    {
        "name": "gap_int32_mac_stock_rtl_onecmd_v3",
        "released": False,
        "status": "local_review_failed",
        "reason": (
            "formal readback analysis enumerated lexicographically sorted "
            "SCA_D keys instead of parsing numeric slice identity"
        ),
    },
    {
        "name": "gap_int32_mac_stock_rtl_onecmd_v4",
        "released": False,
        "status": "local_tb_loader_contract_failed",
        "reason": (
            "SCA_D entries omitted the TB-required length field, so "
            "read_matrices_from_cfg would dump zero formal matrices"
        ),
    },
]


def _write_128bit_lines(path: Path, payload: bytes) -> None:
    if len(payload) % 16:
        raise GapProbePackageError(f"payload is not 128-bit aligned: {path}")
    _write_lf(
        path,
        "\n".join(
            f"{int.from_bytes(payload[index:index + 16], 'little'):0128b}"
            for index in range(0, len(payload), 16)
        )
        + "\n",
    )


def _run_script(install_name: str) -> str:
    return f"""#!/usr/bin/env bash
set -u

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *)
    echo "NDP_copy path must be absolute: $1" >&2
    exit 2
    ;;
esac

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
workload_root="${{package_root}}/workload"
runtime_tool="${{package_root}}/package_tools/gap_int32_mac_server_runtime.py"
identity_tool="${{package_root}}/package_tools/capture_gap_probe_server_identity.py"
identity_verify_tool="${{package_root}}/package_tools/verify_gap_stock_rtl_identity.py"
package_manifest="${{package_root}}/{MANIFEST_NAME}"
ndp_root="$(cd "$1" && pwd)"
cfg_root="${{ndp_root}}/install/cfg_pkg/{install_name}"
run_dir="${{ndp_root}}/run_{install_name}"
evidence_root="${{ndp_root}}/evidence_{install_name}"
return_dir="${{ndp_root}}/{install_name}_return"
return_zip="${{ndp_root}}/{install_name}_return.zip"
return_sha="${{return_zip}}.sha256"

for required in \
  "${{ndp_root}}/tb_NDP_Top_new_phy.sv" \
  "${{ndp_root}}/native_return_observer.svh" \
  "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy" \
  "${{ndp_root}}/rtl/filelists/NDP_Top_phy_filelist.f"; do
  if [ ! -f "${{required}}" ]; then
    echo "Missing required stock-RTL server input: ${{required}}" >&2
    exit 3
  fi
done

if ! command -v timeout >/dev/null 2>&1; then
  echo "Missing required GNU timeout command" >&2
  exit 3
fi

for fresh_target in \
  "${{cfg_root}}" \
  "${{run_dir}}" \
  "${{evidence_root}}" \
  "${{return_dir}}" \
  "${{return_zip}}" \
  "${{return_sha}}"; do
  if [ -e "${{fresh_target}}" ]; then
    echo "Fresh one-command target already exists; refusing reuse: ${{fresh_target}}" >&2
    exit 4
  fi
done

python3 "${{runtime_tool}}" preflight-package \
  --package-root "${{package_root}}" \
  --install-name "{install_name}" >/dev/null || exit 5

mkdir "${{evidence_root}}"
python3 "${{runtime_tool}}" preflight-package \
  --package-root "${{package_root}}" \
  --install-name "{install_name}" \
  --output "${{evidence_root}}/package_preflight.json" >/dev/null || exit 5
python3 "${{runtime_tool}}" observer-check \
  --ndp-root "${{ndp_root}}" \
  --output "${{evidence_root}}/observer_preflight.json" >/dev/null || exit 5

vcs_extra_opts="+incdir+${{ndp_root}}"
server_command="timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=${{run_dir}} VCS_EXTRA_OPTS=${{vcs_extra_opts}} && timeout --foreground --signal=TERM --kill-after=30s 12h ${{run_dir}}/sim_results/simv -l ${{run_dir}}/sim_results/sim.log +vcs+lic+wait +sim_time=100ms +BITSTREAM=install/bitstream.txt +SCA_CFG={INSTALL_PREFIX}/sca_cfg.json +SCA_CFG_D={INSTALL_PREFIX}/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_FILE=${{evidence_root}}/return_observer.log +RETURN_OBS_SLICE=0 +RETURN_OBS_DEEP +RETURN_OBS_DEEP_LIMIT=512 +RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=4096 +RETURN_OBS_STALL_CYCLES=4096 +RETURN_OBS_HEARTBEAT_CYCLES=4096"
printf '%s\\n' "${{server_command}}" > "${{evidence_root}}/server_command.txt"

python3 "${{identity_tool}}" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase pre_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_pre_install.json" >/dev/null || exit 5

mkdir -p "${{ndp_root}}/install/cfg_pkg"
mkdir "${{cfg_root}}"
cp -a "${{workload_root}}/." "${{cfg_root}}/"
for slice_id in $(seq -w 0 15); do
  mkdir -p "${{cfg_root}}/readback/slice${{slice_id}}"
done

python3 "${{runtime_tool}}" preflight-installed \
  --package-root "${{package_root}}" \
  --ndp-root "${{ndp_root}}" \
  --install-name "{install_name}" \
  --output "${{evidence_root}}/installed_preflight.json" >/dev/null || exit 5

python3 "${{identity_tool}}" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_install.json" >/dev/null || exit 5

finalization_complete=0
run_status=125
finalize_partial_return() {{
  shell_status="$1"
  if [ "${{finalization_complete}}" -eq 1 ]; then
    return
  fi
  finalization_complete=1
  set +e
  if [ ! -f "${{evidence_root}}/run_exit_status.txt" ]; then
    if [ "${{run_status}}" -eq 125 ] && [ "${{shell_status}}" -ne 0 ]; then
      run_status="${{shell_status}}"
    fi
    printf '%s\\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"
  fi
  if [ ! -f "${{evidence_root}}/compile_exit_status.txt" ]; then
    printf '%s\\n' "125" > "${{evidence_root}}/compile_exit_status.txt"
  fi
  if [ ! -f "${{evidence_root}}/sim_exit_status.txt" ]; then
    printf '%s\\n' "125" > "${{evidence_root}}/sim_exit_status.txt"
  fi
  python3 "${{identity_tool}}" \
    --ndp-root "${{ndp_root}}" \
    --package-manifest "${{package_manifest}}" \
    --install-name "{install_name}" \
    --phase post_run \
    --server-command "${{server_command}}" \
    --exit-status "${{run_status}}" \
    --output "${{evidence_root}}/server_identity_post_run.json" >/dev/null
  python3 "${{identity_tool}}" \
    --ndp-root "${{ndp_root}}" \
    --package-manifest "${{package_manifest}}" \
    --install-name "{install_name}" \
    --phase post_restore \
    --server-command "${{server_command}}" \
    --exit-status "${{run_status}}" \
    --output "${{evidence_root}}/server_identity_post_restore.json" >/dev/null
  python3 "${{identity_verify_tool}}" \
    --pre-install "${{evidence_root}}/server_identity_pre_install.json" \
    --post-install "${{evidence_root}}/server_identity_post_install.json" \
    --post-run "${{evidence_root}}/server_identity_post_run.json" \
    --post-restore "${{evidence_root}}/server_identity_post_restore.json" \
    --output "${{evidence_root}}/stock_rtl_identity_receipt.json" >/dev/null
  python3 "${{runtime_tool}}" analyze \
    --ndp-root "${{ndp_root}}" \
    --package-root "${{package_root}}" \
    --install-name "{install_name}" \
    --evidence-root "${{evidence_root}}" \
    --run-status "${{run_status}}" \
    --output "${{evidence_root}}/SERVER_RESULT_GATE.json" >/dev/null
  python3 "${{runtime_tool}}" collect \
    --ndp-root "${{ndp_root}}" \
    --package-root "${{package_root}}" \
    --install-name "{install_name}" \
    --evidence-root "${{evidence_root}}" \
    --run-dir "${{run_dir}}" \
    --output-dir "${{ndp_root}}" \
    --run-status "${{run_status}}" \
    --server-command "${{server_command}}" >/dev/null
}}
trap 'finalize_partial_return $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

cd "${{ndp_root}}"
date +%s > "${{evidence_root}}/run_started_epoch.txt"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 \
  DUMP_FSDB=0 \
  TB_DUMP_FSDB=0 \
  RUN_DIR="${{run_dir}}" \
  VCS_EXTRA_OPTS="${{vcs_extra_opts}}"
compile_status=$?
printf '%s\\n' "${{compile_status}}" > "${{evidence_root}}/compile_exit_status.txt"
if [ "${{compile_status}}" -eq 0 ]; then
  timeout --foreground --signal=TERM --kill-after=30s 12h \
    "${{run_dir}}/sim_results/simv" \
    -l "${{run_dir}}/sim_results/sim.log" \
    +vcs+lic+wait \
    +sim_time=100ms \
    +BITSTREAM=install/bitstream.txt \
    "+SCA_CFG={INSTALL_PREFIX}/sca_cfg.json" \
    "+SCA_CFG_D={INSTALL_PREFIX}/sca_cfg_D.json" \
    +RETURN_OBSERVER \
    "+RETURN_OBS_FILE=${{evidence_root}}/return_observer.log" \
    +RETURN_OBS_SLICE=0 \
    +RETURN_OBS_DEEP \
    +RETURN_OBS_DEEP_LIMIT=512 \
    +RETURN_OBS_ACCUM_STATE \
    +RETURN_OBS_ACCUM_LIMIT=4096 \
    +RETURN_OBS_STALL_CYCLES=4096 \
    +RETURN_OBS_HEARTBEAT_CYCLES=4096
  sim_status=$?
else
  sim_status=125
fi
printf '%s\\n' "${{sim_status}}" > "${{evidence_root}}/sim_exit_status.txt"
if [ "${{compile_status}}" -ne 0 ]; then
  run_status="${{compile_status}}"
else
  run_status="${{sim_status}}"
fi
printf '%s\\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"

python3 "${{identity_tool}}" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_run \
  --server-command "${{server_command}}" \
  --exit-status "${{run_status}}" \
  --output "${{evidence_root}}/server_identity_post_run.json" >/dev/null
post_run_identity_status=$?

# This package performs no RTL action.  The common post_restore phase is a
# no-op final identity capture proving the stock functional RTL stayed stable.
python3 "${{identity_tool}}" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_restore \
  --server-command "${{server_command}}" \
  --exit-status "${{run_status}}" \
  --output "${{evidence_root}}/server_identity_post_restore.json" >/dev/null
post_restore_identity_status=$?

python3 "${{identity_verify_tool}}" \
  --pre-install "${{evidence_root}}/server_identity_pre_install.json" \
  --post-install "${{evidence_root}}/server_identity_post_install.json" \
  --post-run "${{evidence_root}}/server_identity_post_run.json" \
  --post-restore "${{evidence_root}}/server_identity_post_restore.json" \
  --output "${{evidence_root}}/stock_rtl_identity_receipt.json" >/dev/null
identity_status=$?

python3 "${{runtime_tool}}" analyze \
  --ndp-root "${{ndp_root}}" \
  --package-root "${{package_root}}" \
  --install-name "{install_name}" \
  --evidence-root "${{evidence_root}}" \
  --run-status "${{run_status}}" \
  --output "${{evidence_root}}/SERVER_RESULT_GATE.json" >/dev/null
analysis_status=$?

python3 "${{runtime_tool}}" collect \
  --ndp-root "${{ndp_root}}" \
  --package-root "${{package_root}}" \
  --install-name "{install_name}" \
  --evidence-root "${{evidence_root}}" \
  --run-dir "${{run_dir}}" \
  --output-dir "${{ndp_root}}" \
  --run-status "${{run_status}}" \
  --server-command "${{server_command}}" >/dev/null
collection_status=$?
finalization_complete=1
trap - EXIT HUP INT TERM
set -e

if [ -f "${{return_zip}}" ] && [ -f "${{return_sha}}" ]; then
  echo "Return ZIP: ${{return_zip}}"
  echo "Return SHA256: ${{return_sha}}"
else
  echo "Return collection did not produce both expected files." >&2
fi

if [ "${{run_status}}" -ne 0 ]; then exit "${{run_status}}"; fi
if [ "${{post_run_identity_status}}" -ne 0 ]; then exit "${{post_run_identity_status}}"; fi
if [ "${{post_restore_identity_status}}" -ne 0 ]; then exit "${{post_restore_identity_status}}"; fi
if [ "${{identity_status}}" -ne 0 ]; then exit "${{identity_status}}"; fi
if [ "${{analysis_status}}" -ne 0 ]; then exit "${{analysis_status}}"; fi
exit "${{collection_status}}"
"""


def _readme(install_name: str) -> str:
    return f"""# GAP int32_mac stock-RTL one-command v5

This package keeps the complete six-stage semantic test and makes only the
server operation simple.  It contains no RTL file and never writes functional
RTL.  It uses the server's existing stock RTL and existing read-only TB
observer.

Evidence level at delivery is `E2_LOCAL_ONLY`; `candidate_release=false`.

## The only server command

Run from the extracted package directory:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

The script automatically performs package preflight, unique-namespace
installation, stock-RTL identity capture, isolated compilation/run, both SCA
bindings, 16x512 formal D comparison, dual-MSE analysis, lifecycle/FIFO
analysis, and allowlist-only return packaging.  VCD/FSDB are disabled.  It
does not invoke the Makefile archive target, so no large archive is created by
this test flow.

The target NDP_copy must already contain `native_return_observer.svh` and the
corresponding TB include.  The package checks this precondition but does not
install or modify any TB/RTL source.

## Return

Return exactly:

```text
{install_name}_return.zip
{install_name}_return.zip.sha256
```

The return contains compact identities, verdicts, logs, runtime SCA files,
16 formal readbacks, and only the representative slice0 dual-MSE raw logs.
Waveforms, compiler build trees, archives, and nested ZIPs are excluded.
"""


def _release_gate(local_report: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "resnet50-gap-int32-mac-onecmd-release-gate-v1",
        "status": "package_ready_server_dynamic_gates_pending",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "install_name": INSTALL_NAME,
        "server_operation": {
            "entry_count": 1,
            "entry": "PREPARE_AND_RUN.sh",
            "argument_count": 1,
            "automatic_install_validate_run_analyze_collect": True,
        },
        "functional_rtl": {
            "mode": "server_stock_unmodified",
            "included_file_count": 0,
            "write_requested": False,
            "patch_present": False,
        },
        "local_e2": {
            "status": local_report["status"],
            "server_package_allowed": local_report["server_package_allowed"],
            "start_comp_count": local_report["start_comp_count"],
            "completion_barrier_count": local_report["completion_barrier_count"],
            "golden_equal": local_report["numeric_e2"]["golden_equal"],
            "unique_128bit_lines_per_slice": local_report["numeric_e2"][
                "unique_128bit_lines_per_slice"
            ],
        },
        "dynamic_gates_in_package": {
            "formal_d": "16 slices x 512 rows exact independent golden",
            "dual_mse": (
                "all slices; six stage counts and ordered C-minus-A address pairing"
            ),
            "normal_fifo": (
                "bounded accepted-input state plus violation detection; "
                "all-cycle coverage remains a release blocker"
            ),
            "stage_lifecycle": "six EXEC_START and six COMP_FINISH",
            "stock_rtl_identity": "pre/post/post-run/noop-final byte stability",
        },
        "remaining_release_gates": [
            "server result not yet returned",
            "normal FIFO all-cycle occupancy proof",
            "forced skew/stall/resume if natural run does not cover it",
            "independent repeated E5",
        ],
        "historical_blocker_boundary": {
            "B_GAP_GA_ACCUM_STATE": (
                "not cleared; this package bypasses the int32_sum transout route"
            ),
            "original_repair_v9_assets": "frozen and not reused",
        },
        "rule_ids": RULE_IDS,
    }


def _build_provenance(root: Path, local_e2: Path) -> dict[str, object]:
    stages = []
    local_report = json.loads(
        (local_e2 / "LOCAL_E2_REPORT.json").read_text(encoding="utf-8")
    )
    for stage in range(1, 7):
        source = root / SOURCE_CONFIG_ROOT / f"stage-{stage}"
        runtime_stage = local_report["runtime"]["runtime_operators"][stage - 1]
        stages.append(
            {
                "stage": stage,
                "config": {
                    "path": (SOURCE_CONFIG_ROOT / f"stage-{stage}/config.json").as_posix(),
                    "sha256": _sha256(source / "config.json"),
                    "validator_error_count": 0,
                },
                "mapping": {
                    "path": (
                        SOURCE_CONFIG_ROOT
                        / f"stage-{stage}/encoded/mapping_review.json"
                    ).as_posix(),
                    "sha256": _sha256(source / "encoded/mapping_review.json"),
                    "read_A": "READ_STREAM0",
                    "read_C": "READ_STREAM3",
                    "write_D": "WRITE_STREAM0",
                },
                "parsed_bitstream": {
                    "path": (
                        SOURCE_CONFIG_ROOT
                        / f"stage-{stage}/encoded/parsed_bitstream.txt"
                    ).as_posix(),
                    "sha256": _sha256(source / "encoded/parsed_bitstream.txt"),
                },
                "bitstream_128b": {
                    "path": (
                        SOURCE_CONFIG_ROOT
                        / f"stage-{stage}/encoded/modules_dump_128b.bin"
                    ).as_posix(),
                    "sha256": _sha256(source / "encoded/modules_dump_128b.bin"),
                    "local_e2_installed_sha256": runtime_stage["config"][
                        "installed_bitstream_sha256"
                    ],
                },
            }
        )
    return {
        "schema": "resnet50-gap-int32-mac-onecmd-build-provenance-v1",
        "install_name": INSTALL_NAME,
        "semantic_source": "configs/gap_int32_mac_bypass_v1/stage-{1..6}",
        "semantic_change_from_closed_local_e2": False,
        "explicit_reuse_authority": (
            "the delegated task explicitly allows the closed six stage JSON, "
            "mapping, bitstream, and local E2 evidence"
        ),
        "current_round_execplan_rebuild": {
            "tool": "tools/build_gap_int32_mac_local_e2.py",
            "output": SOURCE_E2.as_posix(),
            "report_sha256": _sha256(local_e2 / "LOCAL_E2_REPORT.json"),
            "execplan_sha256": local_report["execplan"]["sha256"],
            "load_config_count": local_report["load_config_count"],
            "start_comp_count": local_report["start_comp_count"],
            "barrier_count": local_report["completion_barrier_count"],
        },
        "current_round_sca_and_payload_build": {
            "tool": "tools/build_gap_int32_mac_onecmd_server_test.py",
            "install_name": INSTALL_NAME,
            "sca_pretty_json": True,
            "sca_d_pretty_json": True,
        },
        "stage_chain": stages,
        "rejected_package": REJECTED_PACKAGE,
        "superseded_local_drafts": SUPERSEDED_LOCAL_DRAFTS,
        "functional_rtl_modified": False,
        "rtl_patch_present": False,
    }


def _build_workload(root: Path, package: Path, local_e2: Path) -> dict[str, object]:
    workload = package / "workload"
    (workload / "install/cfg_pkg").mkdir(parents=True)
    _write_lf(
        workload / "install/execplan.txt",
        (local_e2 / "install/execplan.txt").read_text(encoding="ascii"),
    )
    _write_lf(
        workload / "install/instructions_explained.txt",
        (local_e2 / "instructions_explained.txt").read_text(encoding="utf-8"),
    )
    for stage in range(1, 7):
        source = root / SOURCE_CONFIG_ROOT / f"stage-{stage}"
        _write_lf(
            workload / f"install/cfg_pkg/gap_int32_mac_stage{stage}_128b.bin",
            (
                local_e2
                / f"install/cfg_pkg/gap_int32_mac_stage{stage}_128b.bin"
            ).read_text(encoding="ascii"),
        )
        destination = workload / f"config/stage-{stage}"
        destination.mkdir(parents=True)
        for relative in (
            "config.json",
            "encoded/mapping_review.json",
            "encoded/parsed_bitstream.txt",
        ):
            source_file = source / relative
            destination_file = destination / Path(relative).name
            _write_lf(
                destination_file,
                source_file.read_text(encoding="utf-8"),
            )
    _write_lf(
        workload / "config/six_stage_manifest.json",
        (root / SOURCE_CONFIG_ROOT / "manifest.json").read_text(encoding="utf-8"),
    )

    tensor = np.load(root / W3_INPUT_PATH, allow_pickle=False)
    expected = np.load(root / W3_EXPECTED_PATH, allow_pickle=False).reshape(16, 2048)
    matrix = tensor.reshape(16, 2048, 49).reshape(16, 256, 8, 49).transpose(0, 1, 3, 2)
    sca: dict[str, object] = {
        "Exec_Base": f"0x{EXEC_BASE:08X}",
        "Exec_Length": sum(
            bool(line.strip())
            for line in (workload / "install/execplan.txt")
            .read_text(encoding="ascii")
            .splitlines()
        ),
        "Repeat_Num": 6,
        "ExecutionPlan": {
            "base_addr": f"0x{EXEC_BASE:08X}",
            "path": f"{INSTALL_PREFIX}/install/execplan.txt",
        },
    }
    for stage, base in enumerate(CONFIG_BASES, start=1):
        sca[f"gap_mac_s{stage}_config"] = {
            "base_addr": f"0x{base:08X}",
            "path": (
                f"{INSTALL_PREFIX}/install/cfg_pkg/"
                f"gap_int32_mac_stage{stage}_128b.bin"
            ),
        }
    sca_d: dict[str, object] = {}
    for slice_id in range(16):
        a = np.zeros((256, 32, 16), dtype=np.uint8)
        c = np.zeros((256, 32, 16), dtype=np.uint8)
        for output_index in range(32):
            left = output_index * 2
            right = left + 1
            if left < 49:
                a[:, output_index, :8] = matrix[slice_id, :, left, :]
            if right < 49:
                c[:, output_index, :8] = matrix[slice_id, :, right, :]
        a_rel = Path(f"install/input/slice{slice_id:02d}/matrix_A_128bit.txt")
        c_rel = Path(f"install/input/slice{slice_id:02d}/matrix_C_128bit.txt")
        golden_rel = Path(f"golden/slice{slice_id:02d}/matrix_D_128bit.txt")
        _write_128bit_lines(workload / a_rel, a.tobytes())
        _write_128bit_lines(workload / c_rel, c.tobytes())
        _write_128bit_lines(
            workload / golden_rel,
            expected[slice_id].astype("<i4", copy=False).tobytes(),
        )
        prefix = slice_id << SLICE_SHIFT
        sca[f"gap_mac_s1_matrixA_slice{slice_id}"] = {
            "base_addr": f"0x{prefix:08X}",
            "path": f"{INSTALL_PREFIX}/{a_rel.as_posix()}",
        }
        sca[f"gap_mac_s1_matrixC_slice{slice_id}"] = {
            "base_addr": f"0x{prefix | 0x20000:08X}",
            "path": f"{INSTALL_PREFIX}/{c_rel.as_posix()}",
        }
        sca_d[f"gap_mac_s6_matrixD_slice{slice_id}"] = {
            "base_addr": f"0x{prefix | FINAL_D_BASE:08X}",
            "path": (
                f"{INSTALL_PREFIX}/readback/slice{slice_id:02d}/"
                "matrix_D_128bit.txt"
            ),
            "length": 512,
        }
    _write_lf(
        workload / "sca_cfg.json",
        json.dumps(sca, ensure_ascii=False, indent=2) + "\n",
    )
    _write_lf(
        workload / "sca_cfg_D.json",
        json.dumps(sca_d, ensure_ascii=False, indent=2) + "\n",
    )
    return {
        "sca_entry_count": len(sca),
        "sca_d_entry_count": len(sca_d),
        "exec_length": sca["Exec_Length"],
        "repeat_num": sca["Repeat_Num"],
        "golden_sha256": sha256_file(root / W3_EXPECTED_PATH),
    }


def validate_package(project_root: Path, output: Path) -> dict[str, object]:
    root = project_root.resolve()
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    manifest_path = package / MANIFEST_NAME
    for required in (package, zip_path, sha_path, manifest_path):
        if not required.exists():
            raise GapProbePackageError(f"one-command package input missing: {required}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("status") != "one_command_server_test_package_ready"
        or manifest.get("install_name") != INSTALL_NAME
        or package.name != INSTALL_NAME
        or manifest.get("candidate_release") is not False
        or manifest.get("evidence_level") != "E2_LOCAL_ONLY"
    ):
        raise GapProbePackageError("one-command package identity differs")
    runtime_report = preflight_package(package, INSTALL_NAME)
    if runtime_report["status"] != "package_preflight_passed":
        raise GapProbePackageError("server-equivalent package preflight failed")
    records = _records(package, exclude_manifest=True)
    if (
        manifest.get("files") != records
        or manifest.get("payload_file_count") != len(records)
        or manifest.get("payload_tree_sha256") != _tree_sha256(records)
    ):
        raise GapProbePackageError("package exact tree receipt differs")
    forbidden_rtl = [
        relative
        for relative in records
        if Path(relative).suffix.lower() in {".v", ".sv", ".vh", ".svh"}
    ]
    if forbidden_rtl:
        raise GapProbePackageError(f"package contains RTL: {forbidden_rtl}")
    for stage in range(1, 7):
        config_path = package / f"workload/config/stage-{stage}/config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        validation = OperatorConfigValidator().validate(
            config,
            source=config_path.as_posix(),
            development_mode=True,
        )
        errors = [issue for issue in validation.issues if issue.severity == "error"]
        if errors:
            raise GapProbePackageError(
                f"stage {stage} config validator errors: "
                + "; ".join(f"{issue.code}:{issue.path}" for issue in errors)
            )
        mapping = json.loads(
            (
                package / f"workload/config/stage-{stage}/mapping_review.json"
            ).read_text(encoding="utf-8")
        )
        mapped = {
            item["node"]: item["resource"] for item in mapping["node_to_resource"]
        }
        expected_mapping = {
            "STREAM.stream0": "READ_STREAM0",
            "STREAM.stream1": "READ_STREAM3",
            "STREAM.stream2": "WRITE_STREAM0",
        }
        if any(mapped.get(key) != value for key, value in expected_mapping.items()):
            raise GapProbePackageError(f"stage {stage} dual-stream mapping differs")
    script = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    if script != _run_script(INSTALL_NAME):
        raise GapProbePackageError("generated one-command script differs")
    for token in (
        "DUMP_VCD=0",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        "timeout --foreground --signal=TERM --kill-after=30s 2h",
        "timeout --foreground --signal=TERM --kill-after=30s 12h",
        "trap 'finalize_partial_return $?' EXIT",
        f"+SCA_CFG={INSTALL_PREFIX}/sca_cfg.json",
        f"+SCA_CFG_D={INSTALL_PREFIX}/sca_cfg_D.json",
        "gap_int32_mac_server_runtime.py",
    ):
        if token not in script:
            raise GapProbePackageError(f"server entry is missing token: {token}")
    for forbidden in (
        "install_native_return_observer.py",
        "install_gap_ga_rtl_repair.py",
        "--action install",
        "--action restore",
        "make -f Makefile.tb_NDP_Top_new_phy compile sim",
    ):
        if forbidden in script:
            raise GapProbePackageError(
                f"server entry contains forbidden operation: {forbidden}"
            )
    if (package / "README.md").read_text(encoding="utf-8") != _readme(INSTALL_NAME):
        raise GapProbePackageError("generated README differs")
    release_gate = json.loads(
        (package / "validation/RELEASE_GATE.json").read_text(encoding="utf-8")
    )
    if (
        release_gate.get("candidate_release") is not False
        or release_gate.get("evidence_level") != "E2_LOCAL_ONLY"
        or release_gate.get("server_operation", {}).get("entry_count") != 1
    ):
        raise GapProbePackageError("release gate claim or operation boundary differs")
    sca_d = json.loads(
        (package / "workload/sca_cfg_D.json").read_text(encoding="utf-8")
    )
    for entry_name, entry in sca_d.items():
        if (
            not isinstance(entry, dict)
            or set(entry) != {"base_addr", "path", "length"}
            or entry.get("length") != 512
        ):
            raise GapProbePackageError(
                f"SCA_D readback contract differs for {entry_name}"
            )
    audit = _audit_zip(package, zip_path)
    digest = _sha256(zip_path)
    if sha_path.read_text(encoding="ascii") != f"{digest}  {zip_path.name}\n":
        raise GapProbePackageError("ZIP sidecar differs")
    return {
        "schema": SCHEMA,
        "status": "one_command_server_test_package_validated",
        "directory": package.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "payload_file_count": len(records),
        "payload_tree_sha256": _tree_sha256(records),
        "functional_rtl_file_count": 0,
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "zip_audit": audit,
        "sidecar": sha_path.as_posix(),
        "server_command": (
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        ),
        "expected_return": [
            f"{INSTALL_NAME}_return.zip",
            f"{INSTALL_NAME}_return.zip.sha256",
        ],
    }


def build_package(project_root: Path, output: Path) -> dict[str, object]:
    root = project_root.resolve()
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    for target in (package, zip_path, sha_path):
        if target.exists():
            raise GapProbePackageError(f"one-command output must be fresh: {target}")
    local_e2 = root / SOURCE_E2
    local_report_path = local_e2 / "LOCAL_E2_REPORT.json"
    if not local_report_path.is_file():
        raise GapProbePackageError(
            f"current-round local E2 is missing; run its builder first: {local_e2}"
        )
    local_report = json.loads(local_report_path.read_text(encoding="utf-8"))
    if (
        local_report.get("status") != "pass_local_e2"
        or local_report.get("server_package_allowed") is not True
        or local_report.get("rtl_patch_present") is not False
        or local_report.get("start_comp_count") != 6
        or local_report.get("completion_barrier_count") != 6
    ):
        raise GapProbePackageError("current-round local E2 gate is not open")

    package.parent.mkdir(parents=True, exist_ok=True)
    workload_report = _build_workload(root, package, local_e2)
    (package / "validation").mkdir(parents=True, exist_ok=True)
    _write_lf(
        package / "validation/LOCAL_E2_REPORT.json",
        local_report_path.read_text(encoding="utf-8"),
    )
    provenance = _build_provenance(root, local_e2)
    release_gate = _release_gate(local_report)
    _write_lf(
        package / "validation/BUILD_PROVENANCE.json",
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
    )
    _write_lf(
        package / "validation/RELEASE_GATE.json",
        json.dumps(release_gate, ensure_ascii=False, indent=2) + "\n",
    )
    for relative in (
        Path("tools/gap_int32_mac_server_runtime.py"),
        Path("tools/capture_gap_probe_server_identity.py"),
        Path("tools/verify_gap_stock_rtl_identity.py"),
    ):
        _write_lf(
            package / "package_tools" / relative.name,
            (root / relative).read_text(encoding="utf-8"),
        )
    _write_lf(package / "PREPARE_AND_RUN.sh", _run_script(INSTALL_NAME))
    _write_lf(package / "README.md", _readme(INSTALL_NAME))

    records = _records(package, exclude_manifest=True)
    manifest = {
        "schema": SCHEMA,
        "status": "one_command_server_test_package_ready",
        "install_name": INSTALL_NAME,
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "single_hypothesis": (
            "six-stage stock-RTL int32_mac(A,1,C) explicit addition tree"
        ),
        "server_operation": {
            "only_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
            ),
            "automatic_install": True,
            "automatic_validation": True,
            "automatic_run": True,
            "automatic_result_analysis": True,
            "automatic_return_collection": True,
            "manual_parameters_beyond_ndp_root": 0,
        },
        "source_workload": {
            "config_root": SOURCE_CONFIG_ROOT.as_posix(),
            "current_round_local_e2": SOURCE_E2.as_posix(),
            "local_e2_report_sha256": _sha256(local_report_path),
            "execplan_sha256": local_report["execplan"]["sha256"],
            "config_semantics_changed_after_local_e2": False,
            "old_repair_or_v10_derived_artifacts_reused": False,
            "rejected_atomic_v1_reused": False,
            **workload_report,
        },
        "rtl_policy": {
            "mode": "server_original_unmodified",
            "functional_rtl_file_count": 0,
            "functional_rtl_v_or_sv_included": False,
            "rtl_or_tb_source_file_included": False,
            "functional_rtl_write_requested": False,
            "rtl_patch_present": False,
            "observer_install_requested": False,
            "preexisting_server_tb_observer_required": True,
            "stock_rtl_identity_receipt_required": True,
            "waveforms_explicitly_disabled": {
                "DUMP_VCD": 0,
                "DUMP_FSDB": 0,
                "TB_DUMP_FSDB": 0,
            },
        },
        "runtime_policy": {
            "unique_config_namespace": f"install/cfg_pkg/{INSTALL_NAME}",
            "unique_run_dir": f"run_{INSTALL_NAME}",
            "unique_evidence_dir": f"evidence_{INSTALL_NAME}",
            "unique_return_name": f"{INSTALL_NAME}_return",
            "fresh_targets_required": True,
            "make_archive_target_used": False,
            "sca_and_sca_d_explicit": True,
            "repeat_num": 6,
            "start_comp_count": 6,
        },
        "dynamic_gate_policy": release_gate["dynamic_gates_in_package"],
        "return_policy": {
            "allowlist_only": True,
            "direct_zip_and_sidecar": True,
            "waveforms_forbidden": True,
            "build_trees_forbidden": True,
            "nested_archives_forbidden": True,
            "zip_limit_bytes": 16 * 1024 * 1024,
            "extracted_limit_bytes": 32 * 1024 * 1024,
            "individual_file_limit_bytes": 8 * 1024 * 1024,
        },
        "rules": {
            "mandatory_files_read": MANDATORY_RULES,
            "rule_ids": RULE_IDS,
            "generic_validator_is_semantic_release": False,
            "gap_specialized_and_dynamic_gates_required": True,
        },
        "rejected_package": REJECTED_PACKAGE,
        "superseded_local_drafts": SUPERSEDED_LOCAL_DRAFTS,
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
    digest = _sha256(zip_path)
    _write_lf(sha_path, f"{digest}  {zip_path.name}\n")
    return {
        **manifest,
        "directory": package.as_posix(),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
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
        print(f"GAP int32_mac one-command package failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
