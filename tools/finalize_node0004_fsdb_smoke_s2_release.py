#!/usr/bin/env python3
"""Finalize the fresh s2 FSDB smoke after all exact gates pass."""

import json

import finalize_node0004_fsdb_smoke_s1_release as base


base.PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s2"
base.SCHEMA_TAG = "s2"
base.OUT = base.ROOT / "outputs/conv_node0004_fsdb_smoke_s2_release1"
base.ZIP = base.OUT / f"{base.PACKAGE_ID}.zip"
base.GATES = {
    "fsdb_v3_final_zip": base.OUT / "gates/fsdb_v3_final_zip.json",
    "post_sim_final_zip": base.OUT / "gates/post_sim_final_zip.json",
    "runner_resilience": base.OUT / "gates/runner_resilience.json",
    "probe_sv_lexical": base.OUT / "gates/probe_sv_lexical.json",
    "frozen_surface": base.OUT / "gates/frozen_surface.json",
    "runtime_harness": base.OUT / "gates/runtime_harness_family.json",
    "runtime_layout": base.OUT / "gates/runtime_layout_validation.json",
    "first_fresh": base.OUT / "gates/first_fresh_validation.json",
}


def enrich() -> None:
    release_path = base.OUT / f"{base.PACKAGE_ID}.release_receipt.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release.update({
        "previous_version_progress": "FSDB smoke s1 reached production VCS parsing but compile exited 2 before simulation because its package-local probe declared the reserved SystemVerilog keyword 'sequence'.",
        "current_version_purpose": "Fresh smoke s2 renames only that package-local probe identifier, preserves the FSDB v3 profile, and adds an exact-final-ZIP reserved-identifier gate before the required two sequential production executions.",
        "source_return_analysis": "outputs/conv_node0004_fsdb_smoke_s1_return1_analysis/report.json",
        "formal_serialized_successor": False,
    })
    base.write_json(release_path, release)
    task_path = base.OUT / f"{base.PACKAGE_ID}.task_record.md"
    task_path.write_text(f"""# Serialized Conv FSDB authoritative smoke s2

## Previous-version progress

v88b passed production compile/elaboration and closed the retired ACK allegation as an observer/source-identity semantic false positive. FSDB smoke s1 then reached production VCS parsing but failed before simulation: the shipped package-local probe declared `integer sequence;`, and `sequence` is a reserved SystemVerilog keyword. Therefore s1 proved no time advance, FSDB, registered query, repeat reset or distinct second return.

## Current-version purpose

`{base.PACKAGE_ID}` is a fresh diagnostic smoke identity, not a formal serialized Conv successor. It renames only the package-local probe identifier to `event_seq_id`, preserves the registered log field `sequence=`, preserves `DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0`, and adds an exact-final-ZIP reserved-identifier gate with a deliberate negative control.

## Result

- State: `PACKAGE_READY_NOT_RUN`; no upload, lease, connection or server execution occurred.
- Config, numeric, workload, golden and functional RTL remain frozen; the retired ACK comparator is absent.
- The authoritative attempt-local `wave.fsdb` plus all shards remain unbounded return members.
- Raw/core return survives query failure; missing or incomplete FSDB/query/time-progress evidence remains fail-closed.
- The established runtime harness still proves repeat-safe exact-owned reset, foreign-sibling preservation, unique non-overwriting returns, six exit paths and local safe-stub evidence plumbing.
- The new lexical gate catches the exact s1 keyword class, rejects its negative control, and is explicitly not a substitute for production VCS.

## Pickup and future command

- Package: `{base.ZIP.relative_to(base.ROOT).as_posix()}`
- Release receipt: `{release_path.relative_to(base.ROOT).as_posix()}`
- Formal return contract: `{base.PACKAGE_ID}/contracts/server_post_sim_return_request.json`
- Future operator command: `bash {base.PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp`

## Claim boundary

PACKAGE_READY_NOT_RUN only. Production compile success, simulation time > 0, FSDB validity/completeness, registered query completeness, repeat reset and distinct first/second returns remain unproven until two formal production executions are returned. All formal family packages remain frozen.
""", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    status = base.main()
    if status == 0:
        enrich()
    raise SystemExit(status)
