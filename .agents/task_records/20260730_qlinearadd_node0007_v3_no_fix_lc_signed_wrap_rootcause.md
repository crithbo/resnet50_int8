# QLinearAdd node0007 v3 no-fix and LC signed-wrap root cause

Date: 2026-07-30

Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

The v2 return remains bound to source package
`r5_qadd_n7_relocated_v2.zip`, SHA-256
`60534faad0894a8b6507687159d43c824dd968f6c6a3386fa7877fc2007bf0bc`.
Its adjacent return sidecar is absent, so the formal receipt remains
fail-closed independently of the execution diagnosis.

Dynamic execution compiled successfully, completed all `85/85` preloads,
accepted `Exec_Base=0x00d2c800, Exec_Length=182`, printed `Reg Started.` and
the first `INFO: slice start`, but never printed the first completion,
terminated naturally, or emitted any of the 28 formal D readbacks. Simulation
exit status is `124`; zero mismatches with all outputs missing is not
evaluable.

Per user direction, a watchdog-only revision is not treated as a fix. v3
changes the simulation watchdog and install namespace only. It retains the
same arithmetic/config/bitstream/execplan/SCA payload and therefore retains
the hang.

`numeric_analysis_repeated=false`. Frozen 17-instance semantics, W3 numeric
order, six qparams, exact UINT8 tail, mapping, address/lifetime and golden
assets were consumed without recomputation.

## FIRST_DIVERGENCE

Code: `QADD_DRAM_LC_SIGNED_FEEDBACK_WRAP_HANG`

First affected stage: `op_a_dequant`, first `Start_Comp`.

Both `LC1` and `LC3` are materialized with `start=0, stride=1, end=37632`.
The bound RTL declares `IGA_LC_PORT_DATA_WIDTH=16`. Its recurrence:

1. computes the next count from
   `signed'(iga_lc_outbuf_cnt_rd_data)`;
2. stores the 17-bit counter back into the 16-bit LC outbuffer; and
3. asserts last only at `count >= end - stride`, here `37631`.

After producing `+32768`, the outbuffer stores `16'h8000`. On the next
feedback step this is sign-extended as `-32768`; the sequence therefore
cannot reach `37631`. The LC last tag is unreachable, the write MSE cannot
produce the terminal last-data event, and `slice_cmpt_finish` cannot release
the first stage. This exactly explains the observed first-start/no-first-
completion timeout and is independent of workload size.

The same invalid geometry occurs seven times in the six-stage workload:
stage0 LC1/LC3, stage1 LC1/LC3, and stage3 LC1/LC2/LC3.

The earlier missing-explicit-barrier suspicion is rejected as the first root
cause: for the common full-slice mask, `Start_Comp` holds
`slice2gexec_ready=0` until `slice_cmpt_finish`; no later stage can overtake
the hung first stage.

`Repeat_Num=6` is also rejected as a root cause. In the stock TB it is the
number of start/finish pairs to observe, not a request to execute the complete
execplan six times.

## BLOCKER_DELTA

- Closed:
  `B_QADD_NODE0007_POST_SLICE_START_NO_PROGRESS_ROOT_CAUSE_UNRESOLVED`.
- Opened:
  `B_QADD_NODE0007_DRAM_LC_SIGNED_FEEDBACK_WRAP`.
- Scope:
  package/config geometry under the bound RTL semantics; this is not a claim
  of a general RTL deadlock.
- Required correction:
  factor every inner `end=37632` into safe nested loops. A concrete
  config-only geometry is:
  - dequant stages: `LC0 end 1 -> 2`, `LC1/LC3 end 37632 -> 18816`,
    input outer stride `602112 -> 301056`, output outer stride
    `0 -> 1204224`;
  - FP32 add: `LC0 end 4 -> 8`, `LC1/LC2/LC3 end 37632 -> 18816`,
    all stream outer strides `602112 -> 301056`.
- The correction must be rematerialized from an empty mapping state and
  reprove exact occurrence count, ordered addresses, non-aliasing,
  coverage, lifetime/barriers, mapping/bitstream/execplan/SCA and
  config-bound golden. It has not been materialized in this diagnosis.

## RULE_DELTA_PROPOSAL

Add a QLinearAdd/operator-config pre-encoding gate:

`CDA-IGA-LC-SIGNED-FEEDBACK-END-BOUND-001`

For a positive-stride DRAM LC whose recurrence passes through the current
16-bit signed feedback outbuffer, require `end <= 32768`. Larger logical
occurrence counts must be factored into nested LCs/tiles, with address and
coverage equivalence re-proved from final serialized JSON. A validator must
bind the RTL width and signed recurrence rather than relying only on the
17-bit configuration field width.

## PACKAGE_RELEASE

`PACKAGE_RELEASE=NONE`.

Existing v3:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_relocated_v3.zip`
- SHA-256:
  `265188700bca6c45d6d0894326f71b4e9c991cbaf3847f384785504ed7b2fc5c`
- disposition:
  `QUARANTINED_NOT_RUN_NO_FUNCTIONAL_FIX`

Do not run v3 as a fix. No v4 was generated, no server files were inspected,
and no upload, server execution, lease, plan/rule edit, or RTL edit occurred.
