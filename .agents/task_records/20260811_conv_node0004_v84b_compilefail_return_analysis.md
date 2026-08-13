# Conv node0004 v84b compile-fail RETURN_ANALYSIS

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- scope: serialized Conv v84b formal return analysis only
- user boundary: no successor, no storage rotation, no RTL/config/numeric/workload/golden/plan/rules modification, no server action

## Identity and structural result

Return:
`C:/Users/15383/Downloads/r5_n4_hw_v84b_ack_inline_realtime_diag_r1786436071113419680_1052700_return.zip`,
41307 bytes, SHA256
`43f1a99877de60e40b273aa05f8d5a57e8159dd4a5229809e0f09a620b544a8d`.
Source v84b ZIP remains 5264811 bytes, SHA256
`0ccb7e46856b814df4e0849129a765df7026ea7f52b76c73502c369c15c14ac4`.

CRC, root/path safety, duplicate and symlink checks, exact 11-member core set,
request allowlist, core per-file receipts, package/execution/return basename, and
byte-equal returned `package_manifest.json` binding all pass. The core return
was published successfully despite the required plugin failure.

## First divergence and result gates

`LAST_PROVEN_GOOD=SOURCE_PACKAGE_AND_EXECUTION_IDENTITY_BOUND_CORE_RETURN_PUBLISHED_AFTER_COMPILE_FAILURE`.

`FIRST_DIVERGENCE=PRODUCTION_COMPILE_EXIT_2_BEFORE_SIMULATION_START`.
The exact receipts are compile=2, run=125, signal=NONE, sim_started=false, and
natural_terminal=false. This is not a hang and is not a DUT/config/numeric
result. Formal D is present/missing/mismatch = 0/320/not-evaluated; all-missing
is not PASS. E3/E4/E5 are false.

The required plugin failed because `c0/sim.log` does not exist. This is a
consequence of simulation never starting, not the primary root cause.

## Root-cause boundary

The production runner redirects the actual compile output to
`compile/sim_results/compile_driver.log`, but the package's core-return request
does not archive that file or a bounded first-error excerpt. Consequently the
return proves the compile boundary but cannot distinguish package-local
observer compilation, server RTL compilation, or compiler/environment failure.

Root status:
`UNRESOLVED_COMPILE_FAILURE_CAUSE_BECAUSE_COMPILE_DRIVER_LOG_NOT_RETURNED`.
Package-local evidence defect:
`COMPILEFAIL_CORE_RETURN_OMITS_BOUNDED_COMPILE_DRIVER_LOG`.

Frozen repair surface only: add compile-fail core entries for a bounded
compile-driver/first-error record, actual compile argv, and compiled source
identity. No repair package is built in this turn.

## 本轮进展

Relative to v83b, target-function progress is zero and target-causal progress
is zero. Dynamic reachability regressed: v83b compiled and ran and returned 65
phase events; v84b stopped at compile. There is only package/runner causal
progress: this return uniquely proves compile exit 2 and sim-not-started.

## Blocker and rule feedback

Opened:
- `B_CONV_NODE0004_V84B_PRODUCTION_COMPILE_EXIT_2`
- `B_CONV_NODE0004_COMPILEFAIL_RETURN_OMITS_DRIVER_LOG`

Retained:
- ACK output versus inline RHS dynamic mismatch unresolved
- natural terminal
- formal D 320

The old outbuffer occupancy blocker remains `INVALIDATED_NOT_RTL_BUG`.

`RULE_DELTA_PROPOSAL=CDA-SERVER-COMPILEFAIL-CORE-RETURN-FIRST-ERROR-001`:
for nonzero production compile, independent core return should include bounded
compile log/first-error, actual compile argv, and source identity; omission must
remain `COMPILE_FAILURE_ROOT_UNOBSERVED` and must not promote missing `sim.log`
to root cause.

Machine report:
`outputs/conv_node0004_v84b_return_analysis/report.json`, 6116 bytes, SHA256
`69f43187921d74160b232c6161596bab2f57ba8dffc8d2731bafcbdf349a748e`.
