# Conv node0004 v47 return → v48 LC9 actual-consumer successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Route: serialized Conv correctness only
- Numeric/W3/workload/config/golden repeated: `false`
- Functional RTL modified: `false`
- Server action: `false`

## v47 return

The formal return ZIP is
`r5_n4_hw_v47_lc9_split_cloudrtl_return.zip`,
bytes `113874`, SHA-256
`d05cca4f9d823be3c9ff0b675b2a1601ce863f5075dc29ce057eac0371d3589c`.
The missing adjacent sidecar is accepted only under
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`.
Internal CRC, root/path, identity, manifest exact-set, allowlist, per-file
receipts, source-package binding, package/install preflight and diagnostic
feature binding pass.

Production compile and run both return 0 and simulation starts, but there is
no natural terminal. Formal D is `expected=320`, `present=0`, `missing=320`,
`mismatch=0`; therefore the conjunction gate fails, E3 is retained, and
E4/E5 remain false.

## Corrected causal boundary

- LAST_PROVEN_GOOD:
  `LC9_VALID_HELD_AND_NONBLOCKING_BRANCHES_CAPTURE_WHILE_GLOBAL_LC9_ADVANCE_REMAINS_ZERO`
- FIRST_DIVERGENCE:
  `LC9_ACTUAL_BACKPRESSURE_BITS_0_AND_26_DEASSERT_AT_LC7_SOURCE8_AND_MSE3_SOURCE5_INPUT2`

The final LC9 backpressure vector is `0x1fbfffffe`; only bits 0 and 26 are
low. Current 0cc RTL equations decode those bits to LC7 source slot 8 and
MSE3 source slot 5/input 2. v47 instead observed PE1 source 9, MSE4 input 1
and ROW4. Its `pe1_in2_accept` predicate counted `LC9 valid && one branch
ready`, so a held valid level produced 1,310,717 samples in 1,310,720 active
cycles while the qualified all-destination LC9 advance remained zero.

This uniquely proves a package-observer causal-consumer misbinding, not a
configuration or functional-RTL root cause. The old outbuffer occupancy
claim remains `INVALIDATED_NOT_RTL_BUG`.

## v48 successor

`r5_n4_hw_v48_lc9_actual` is a fresh
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX` identity. It retains frozen runtime
payload bytes and adds one low-cost feature that observes:

- qualified global LC9 all-destination advance;
- LC7 source-slot8 local masked capture and output accept;
- MSE3 source-slot5/input2 local masked capture and qualified queue push/pop;
- bit0/bit26 backpressure transitions and global LC9 last0.

Levels, full/empty and match state remain corroboration only. The package
does not change functional RTL, numeric data, W3, workload, config, golden,
timeout or backpressure.

## Release validation

- ZIP bytes/SHA:
  `5861832` /
  `cdb13ac9039cbaac88306669b8b6e6d9bdb3d3956a4f38425610c6b4f2b7971b`
- deterministic double build: PASS
- exact actual consumers: `22`, uncovered `0`
- focused HDL/scope positive: PASS
- declaration/use/update scope negatives: `3/3` fail closed
- predicate trace: PASS
- feature negatives: `4/4` fail closed
- safe compile runner exit: `74`
- TERM finalizer runner exit: `143`
- final release-gate matrix: 9 rows, all blocking applicable rows PASS
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`

Unique command:

```bash
bash r5_n4_hw_v48_lc9_actual/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `r5_n4_hw_v48_lc9_actual_return.zip`.

## Blocker delta

- Closed: `B_CONV_NODE0004_V47_PRODUCTION_COMPILE_AND_FEATURE_BINDING`
- Opened: `B_CONV_NODE0004_V47_LC9_OBSERVER_ACTUAL_CONSUMER_MISBIND`
- Refined to:
  `B_CONV_NODE0004_LC9_TO_LC7_AND_MSE3_ACTUAL_BRANCH_ACCEPT_UNOBSERVED`
- Preserved:
  `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`,
  `B_CONV_NODE0004_FORMAL_D_320`

## Rule feedback

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`.
`CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`,
`CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`,
`CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`,
`CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001` and
`CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001` directly catch the
v47 pseudo-progress/misbinding and close the v48 release audit. The
confirmation applies only to package-local observer/release validation; it
does not claim natural terminal, formal D, DUT root cause, E4 or E5.

Machine release:
`outputs/conv_node0004_v47_return_analysis/v48_successor_release.json`.
