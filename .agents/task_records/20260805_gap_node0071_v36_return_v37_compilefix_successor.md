# GAP node0071 v36 return → v37 compilefix successor

Date: 2026-08-05

Owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`  
Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## RETURN_ANALYSIS

The formal v36 return is receipt-valid under
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`: the absent adjacent
sidecar replaces only the external transport receipt. ZIP CRC, single root,
path safety, duplicate/symlink exclusion, RETURN_MANIFEST exact-set,
allowlist, per-file receipts, source binding, package/install/run/return
identities, preflight and runtime-D-absent checks all pass.

VCS exits `2` before simulator launch with `Error-[IND]` at package-local
`tb_probe/native_return_observer.svh:4614`. The consumer
`return_obs_rd_spatial_mon` is undeclared; the existing declared monitor is
`return_obs_rd_spatial_size_mon`. Simulation status is sentinel `125`, runner
is `2`, no natural terminal exists, and formal D is `0/48` present with all
48 missing. `mismatch=0` is unevaluable. E3/E4/E5 are all false.

- LAST_PROVEN_GOOD: source/return/package identities, installed preflight,
  runtime-D absence and actual VCS invocation; VCS entered the exact
  package-local observer.
- FIRST_DIVERGENCE:
  `PACKAGE_LOCAL_OBSERVER_IDENTIFIER_TYPO_RETURN_OBS_RD_SPATIAL_MON_BEFORE_SIMULATION`
- HANG_ROOT_CAUSE: `NOT_APPLICABLE_COMPILE_FAILED_BEFORE_SIMULATION`

Formal analysis report:
`artifacts/operator_config_validation/r5-gap-node0071-v36-return-analysis/report.json`

- bytes: `7144`
- SHA256:
  `2e5ec8fbbdb53e519818f6edea820e2f7d1c0e0ec0c6d23f81f8f75698f8603f`

## Successor

Fresh identity:
`r5_n71_gap_v37_dbclk_rdready_compilefix`

Class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`  
Candidate release: `false`  
Evidence ceiling: `E2_LOCAL_ONLY`  
Status: `PACKAGE_READY_NOT_RUN`

The only observer semantic correction is the single undeclared consumer token
to the existing declared identifier. The information-gain owner-clock
queue→WR→RD/prepared/data_vld diagnostic remains intact.

Frozen source:
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v36_dbclk_rdready_diag.zip`

- bytes: `1826295`
- SHA256:
  `8835bcad4b54f6c0ec5ad225976d71631492477430e73e77f838df1d76cbf1dd`

Final ZIP:
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v37_dbclk_rdready_compilefix.zip`

- bytes: `1828271`
- SHA256:
  `796312c5c4c5ed941a78fd4a0cf245bb580edac9b1b7ff5960b8e78c3eb8fa7b`

Sidecar:
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v37_dbclk_rdready_compilefix.zip.sha256`

- bytes: `110`
- SHA256:
  `93fc9c6b84f5983177ae2562056f83584a44ea21bb1366b52fc403b485c140c3`

Server command:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return:
`r5_n71_gap_v37_dbclk_rdready_compilefix_return.zip`

## Freeze and validation

- 73 numeric/workload files: byte-equal to v36.
- Numeric/sum/tail analysis: not repeated.
- Config/workload/golden: not rebuilt.
- Timeout/backpressure: unchanged.
- Functional RTL: unchanged.
- Two deterministic builds: byte-identical.
- Runner safe-compile positive and 5 negatives: exit `0`, all fail closed.
- TERM shared-finalizer: exit `0`, 18/18 checks true.
- Focused package-local HDL scope: exit `0`, five negatives fail closed.
- Validator: exit `0`, 81 negatives fail closed.
- Final-ZIP current-rule audit: exit `0`,
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`.

Final audit:
`artifacts/operator_config_validation/r5-gap-node0071-v37-final-zip-rule-self-audit/report.json`

- bytes: `10671`
- SHA256:
  `89be3c51cc3301bad5fd9e7a328b93f6885a197da4bc94bc6835bdb878b21640`

The public operator rule drift to
`8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497`
adds `CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001`. It is
content-neutral to this diagnostic-only compile correction: v37 does not
modify or claim a producer→consumer execplan barrier, does not integrate
node0075, and remains at E2 local evidence. The unchanged ZIP is externally
revalidated as `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`.

## BLOCKER_DELTA

Closed by package construction:
`B_GAP_NODE0071_V36_PACKAGE_OBSERVER_IDENTIFIER_TYPO`.

Held until a formal v37 return:

- `B_GAP_NODE0071_RD_DATA_READY_LOW_PENDING_PREPARED_DATA_SUPPLY_OR_OUTPUT_FULL_CLK_DB_QUALIFIED_LEAF`
- `B_GAP_NODE0071_DYNAMIC_NATURAL_TERMINAL`
- `B_GAP_NODE0071_FORMAL_D_48`

## RULE_DELTA_PROPOSAL

Proposed non-synonymous ID:
`CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`.

Positive scoped closure and misspelled-use negatives should be seeded from
each actual required consumer expression in the exact final HDL member, not
only from an expected identifier inventory or mock. Scope is limited to
changed and required package-local diagnostic identifiers; this does not
require full-design local elaboration.

Machine closure report:
`artifacts/operator_config_validation/r5-gap-node0071-v36-return-v37-successor-closure/report.json`

- bytes: `6427`
- SHA256:
  `e7a2760a619a273a1fee243c4a6c966d137c1fbf7699e86b5691456cb0c043f7`

No server upload/run/lease occurred. No plan, public rule, functional RTL or
other-family asset was modified.
