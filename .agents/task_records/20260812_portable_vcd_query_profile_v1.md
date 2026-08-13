# 2026-08-12 — Portable VCD and registered signal-query profile v1

## Outcome

Implemented the shared next-fresh method under the existing unique rule `CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001`. No synonymous rule was created.

The profile preserves the authoritative full unbounded raw VPD and the existing post-return `vpd2vcd` method. It introduces a distinct `DUMP_PORTABLE_VCD=1` contract; existing `DUMP_VCD=1` remains explicitly bound to VPD and is not renamed or reinterpreted.

For the first fresh package under this profile, direct standard VCD from the same original attempt is mandatory. A later query-only release is legal only when the registered event receipt proves the exact ordered candidate catalog, instance, width, timescale, every 0/1/X/Z transition, contiguous sequence, end-state coverage, unbounded capture and source-generation identity. Free-form text is not accepted.

## Shared surfaces

- `tools/server_waveform_portable_query.py`
- `schemas/server_waveform_portable_profile_v1.schema.json`
- `schemas/server_waveform_signal_query_receipt_v1.schema.json`
- `schemas/server_waveform_portable_runtime_receipt_v1.schema.json`
- `contracts/server_waveform_portable_query_profile_v1.json`
- `tests/test_server_waveform_portable_query.py`
- `fixtures/server_waveform_portable_query_v1/`
- `outputs/whole_network_waveform_portable_query_v1/`
- machine report: `artifacts/operator_config_validation/r5-whole-network-waveform-portable-query-profile-v1/report.json`

The runtime validator binds actual simulator argv, exact dump Tcl, source-bound top/depth receipt, package/execution/attempt identity, the mandatory raw-VPD runtime receipt, VCD bytes/SHA/header/timescale/catalog/completeness, registered query bytes/SHA/catalog/events/end states, and return allowlist membership.

## Failure semantics

Direct conversion/dump/query failure yields `DIAGNOSTIC_EVIDENCE_INCOMPLETE`, but `return_must_publish` remains true. Raw VPD and compile/sim/signal/return core evidence remain mandatory and are never suppressed by portable-evidence failure.

## Validation

- portable profile focused tests: 11/11 PASS
- combined mandatory VPD + post-return converter + portable profile regression: 31/31 PASS
- `py_compile`: PASS
- JSON parse: PASS
- scoped `git diff --check`: PASS
- fixture registry: 5 positive controls and 11 negative controls

The controls cover the misleading legacy `DUMP_VCD=1 -> VPD` naming, direct VCD, exact attempt binding, incomplete query catalog, wrong instance/width, event sequence gaps, X/Z preservation, hard caps, sampling/truncation, allowlist omission, asset identity drift, free-form query rejection and failure isolation.

## User next-round direction and VPD disposition

The user requested that the next-round test packages contain VCD and allowed VPD cancellation if it becomes unnecessary. The first fresh should retain VPD and add VCD plus the registered query receipt. VPD cancellation is not yet justified because direct dual-format VCS behavior has not produced a real receipt and the active rule still requires authoritative raw VPD. After one successful VCD return proves completeness/local decodability and measures runtime/size overhead, mainline may adjudicate whether later packages can make VPD optional.

This optimizer does not own family package generation. Family/mainline dispatch occurs only after shared-method current-disk publication.

## Frozen current state and claim boundary

Current v87b still requires `vpd2vcd` or a same-workload future run. Current pending/tested packages remain unchanged and are not retrospectively held, rebuilt or rotated.

No DUT simulation, family diagnosis, package build, upload/run/lease, public-rule/plan/current-package/RTL/config/numeric modification, natural-terminal, formal-D, E4 or E5 claim was made.
