# Conv node0004 v48 return → v49 LC9 actual-consumer compile-fix successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Route: serialized Conv correctness only
- Numeric/W3/workload/config/golden repeated: `false`
- Functional RTL / ISA / hardware modified: `false`
- Active ndp-sim modified: `false`
- Server action: `false`

## v48 formal return

The user-provided return is
`r5_n4_hw_v48_lc9_actual_return.zip`, bytes `57414`, SHA-256
`91cb18d7e0a1d687597503026ed0155af0c8cf2f491a1712318897122148a27a`.
The missing adjacent sidecar is accepted only as transport attestation.
Internal CRC, root/path, duplicate/symlink, manifest exact-set, allowlist,
per-file receipts, source binding, package/install preflight, runtime-D
absence and observer identity gates pass.

Production VCS exits `2`; the runner exits `125`. Simulation never starts,
there is no natural terminal, and formal D is `expected=320`, `present=0`,
`missing=320`, `mismatch=0`. The conjunction fails and E3/E4/E5 are false.

## First divergence and root cause

- LAST_PROVEN_GOOD:
  `PACKAGE_INSTALL_PREFLIGHT_AND_PRODUCTION_VCS_PARSE_REACHED_OBSERVER_ELABORATION`
- FIRST_DIVERGENCE:
  `OBSERVER_MSE3_PATH_SELECTS_NONEXISTENT_WR_MSE_GENERATE_BRANCH`

The v48 observer contains ten `WR_MSE` XMREs at lines 6306, 6307, 6309,
6310, 6311, 6313, 6314, 6316, 6317 and 6346. It selected logical MSE3 but
used `MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine`.

Current `Stream_Engine.sv`, bytes `51362`, SHA-256
`a8718b4c4b043ffbf8c2bd59842ac677f18861783d70ce5eaa3d809c79ac6365`,
generates `RD_MSE` at line 449 when
`MSE_IDX < MEMORY_RD_STREAM_ENGINE_NUM`; the WR branch begins at line 506.
MSE3 therefore resolves through
`MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine`. This is a confirmed
package-local observer scope error, not a Conv config or functional-RTL root
cause. Dynamic LC9, natural-terminal and formal-D adjudication was not
reached.

The old SA outbuffer occupancy claim remains
`INVALIDATED_NOT_RTL_BUG`.

## Audit escape

The v48 safe compile stub proved runner reachability and EXIT/TERM finalizer
behavior only. Its focused scope harness fabricated the expected WR branch,
so it did not prove production generate-branch name resolution. The old v48
claim of production elaboration readiness is withdrawn.

This is validator noncompliance with already-current
`CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001` and
`CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`, not a
missing public rule.

## v49 successor

`r5_n4_hw_v49_lc9_actual_compilefix` is a fresh
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, `candidate_release=false` identity.
It changes only:

1. fifteen MSE3 observer paths from the WR generate branch to the actual RD
   generate branch;
2. bounded, trigger-only LC9 causal snapshots;
3. package-local provenance/manifest/README for that exact change.

Runtime payload, numeric/W3/qparams/tail/workload/config/golden, timeout,
backpressure and functional RTL are frozen. The package contains zero RTL
entries and respects the user decision `HARDWARE_CHANGE_FORBIDDEN`.

## Release validation

- ZIP bytes/SHA:
  `5868790` /
  `2b7faeb4b838133f041432ff707792047d113bf65871aa8936e3f2f4c502e27c`
- sidecar bytes/SHA:
  `105` /
  `a434c2eed28fff7d94f4cc5698dbe07d374ffe818087e519de75750e5c6ea125`
- deterministic double build: PASS
- actual MSE3 path occurrences: RD `15`, WR `0`
- actual generate-branch negatives:
  wrong branch / missing branch / wrong sibling / RTL generate-name drift all
  fail closed
- focused compatible-front-end syntax: exit `0`
- declaration/task/consumer typo negatives: exits `6/1/1`
- trigger predicate trace: PASS
- safe compile runner exit: `74`
- TERM finalizer exit: `143`
- final release-gate matrix: 9 rows
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`
- final audit SHA-256:
  `99f1d01408c45a2a99083b1673bd6115a8160bd4008cbb81b38acdf6ccdb9cf8`

Unique command:

```bash
bash r5_n4_hw_v49_lc9_actual_compilefix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return:
`r5_n4_hw_v49_lc9_actual_compilefix_return.zip`.

## Blocker delta

- Closed locally:
  `B_CONV_NODE0004_V48_OBSERVER_MSE3_GENERATE_BRANCH_XMRE`
- Preserved for dynamic run:
  `B_CONV_NODE0004_LC9_TO_LC7_AND_MSE3_ACTUAL_BRANCH_ACCEPT_UNOBSERVED`,
  `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`,
  `B_CONV_NODE0004_FORMAL_D_320`
- Invalidated and not reopened:
  `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`

## Rule feedback

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT_VALIDATOR_NONCOMPLIANCE`.
The confirmation is limited to this package-local compile escape and v49
release audit. It does not claim DUT simulation, natural terminal, formal D,
E3, E4 or E5.

Machine reports:

- `outputs/conv_node0004_v48_return_analysis/report.json`
- `outputs/conv_node0004_v48_return_analysis/v49_successor_release.json`
- `outputs/conv_node0004_v49_package_validation/final_zip_audit.json`
