#!/usr/bin/env python3
"""Finalize fresh s3 after all exact gates pass."""

import json

import finalize_node0004_fsdb_smoke_s1_release as base


base.PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s3"
base.SCHEMA_TAG = "s3"
base.OUT = base.ROOT / "outputs/conv_node0004_fsdb_smoke_s3_release1"
base.ZIP = base.OUT / f"{base.PACKAGE_ID}.zip"
base.GATES = {
    "fsdb_v3_final_zip": base.OUT / "gates/fsdb_v3_final_zip.json",
    "post_sim_final_zip": base.OUT / "gates/post_sim_final_zip.json",
    "runner_resilience": base.OUT / "gates/runner_resilience.json",
    "probe_sv_lexical": base.OUT / "gates/probe_sv_lexical.json",
    "operator_command": base.OUT / "gates/operator_command.json",
    "frozen_surface": base.OUT / "gates/frozen_surface.json",
    "runtime_harness": base.OUT / "gates/runtime_harness_family.json",
    "runtime_layout": base.OUT / "gates/runtime_layout_validation.json",
    "first_fresh": base.OUT / "gates/first_fresh_validation.json",
}


def enrich() -> None:
    release_path = base.OUT / f"{base.PACKAGE_ID}.release_receipt.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release.update({
        "previous_version_progress": "FSDB smoke s1 formally failed production compile on the package-local reserved identifier 'sequence'; the unrun s2 candidate repaired the identifier but its self-described operator root omitted NDP_copy01 and was not released as pickup.",
        "current_version_purpose": "Fresh smoke s3 preserves the exact probe repair and FSDB v3 contract while binding the unique operator command to /home/panqs/ndp/NDP_copy01.",
        "source_return_analysis": "outputs/conv_node0004_fsdb_smoke_s1_return1_analysis/report.json",
        "formal_serialized_successor": False,
    })
    base.write_json(release_path, release)
    task_path = base.OUT / f"{base.PACKAGE_ID}.task_record.md"
    task_path.write_text(f"""# Serialized Conv FSDB authoritative smoke s3

## Previous-version progress

v88b passed production compile/elaboration and closed the retired ACK allegation as an observer/source-identity semantic false positive. FSDB smoke s1 reached production VCS parsing but failed before simulation because its package-local probe declared the reserved SystemVerilog keyword `sequence`. The unrun s2 candidate repaired that identifier, but final delivery review found its self-described operator root omitted `NDP_copy01`; s2 was therefore not retained as pickup.

## Current-version purpose

`{base.PACKAGE_ID}` is a fresh diagnostic smoke identity, not a formal serialized Conv successor. It preserves the s1 compiler repair (`event_seq_id` with registered log key `sequence=` unchanged), the full FSDB v3 profile, and binds the exact operator command to `/home/panqs/ndp/NDP_copy01`.

## Result

- State: `PACKAGE_READY_NOT_RUN`; no upload, lease, connection or server execution occurred.
- Config, numeric, workload, golden and functional RTL remain frozen; the retired ACK comparator is absent.
- Exact dump profile remains `DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0`.
- Authoritative attempt-local `wave.fsdb` plus every shard remains an unbounded return surface.
- Raw/core return survives query failure; missing FSDB/query/time-progress evidence remains fail-closed.
- All exact final-ZIP, FSDB v3, post-sim, runner, probe syntax, operator command, runtime layout, two-run local repeat, first-fresh and frozen-surface gates pass.

## Pickup and future command

- Package: `{base.ZIP.relative_to(base.ROOT).as_posix()}`
- Release receipt: `{release_path.relative_to(base.ROOT).as_posix()}`
- Formal return contract: `{base.PACKAGE_ID}/contracts/server_post_sim_return_request.json`
- Future operator command: `bash {base.PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

## Claim boundary

PACKAGE_READY_NOT_RUN only. Production compile success, simulation time > 0, FSDB validity/completeness, registered query completeness, repeat reset and distinct first/second formal returns remain unproven until two sequential production executions are returned. All formal family packages remain frozen.
""", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    status = base.main()
    if status == 0:
        enrich()
    raise SystemExit(status)
