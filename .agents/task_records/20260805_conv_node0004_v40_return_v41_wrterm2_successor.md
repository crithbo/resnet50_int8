# Conv node0004 v40 return → v41 WRTERM2 successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Scope: serialized Conv correctness only
- Result: `PACKAGE_READY_NOT_RUN`
- Package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: `false`

## RETURN_ANALYSIS

The formal v40 return ZIP SHA256 is
`2d0851dd41db8c3c5c7d14eb986a1b1696438397a3f21ae7b452cf40398a777d`;
the frozen source v40 ZIP SHA256 is
`f1695ec3232e1e651a3242603e299c5ce0b4a46762ec9a23401e0bf7a5523d9e`.
Internal CRC/path/root, exact return set, allowlist, per-file receipts,
source binding, package/install preflight, runtime-D-absent, observer
compile/runtime/feature binding, compile and run gates all pass. Compile and
run exit zero and the diagnostic run reaches `$finish`, but the DUT does not
reach natural terminal. Formal D has `0/320` present, `320` missing and zero
mismatches; missing-all is not a pass. E3/E4/E5 remain false.

This is not a regression. v40 preserves the qualified raw edge chronology and
proves 32 descriptor pops plus 32 data groups reaching DataHub.

## Qualified boundary

- LAST_PROVEN_GOOD:
  `UNIQUE_FINAL_DESCRIPTOR_POP_AFTER_32_DESCRIPTORS_AND_32_DATA_GROUPS_REACH_DATAHUB`
- FIRST_DIVERGENCE:
  `FIRST_CYCLE_AFTER_TRUE_FINAL_DESCRIPTOR_POP_HAS_TAG_PUSH_TAG_POP_AND_PREPARED_WRITE_WITH_NO_ADDRESS_OR_DESCRIPTOR_PROGRESS`

The v40 observer used `wt_desc_pop && fifo_counter==1`. During steady-state
simultaneous push/pop, the pre-state count is also one, so this predicate armed
on 31 non-final pops. The correct final event is
`wt_desc_pop && !wt_desc_push && pre_count==1`, with post-terminal accounting
starting on the following cycle.

The raw evidence is still consumable: after the one true final pop, address and
descriptor progress remain zero, while two tags enqueue, one tag/data group is
accepted into prepared storage, and the following data group raises hold. This
leaves three DUT-side candidates: excess upstream data/tag schedule,
stale/replayed lifetime, or descriptor-unaware prefetch. No functional RTL
defect or configuration repair is claimed.

## Successor

The fresh successor is:

- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v41_wrterm2_diag.zip`
- ZIP bytes: `5851563`
- ZIP SHA256:
  `e314dfb65b1bc7b8ad0403aa559a79508073092988a45e20b8637f21917933b0`
- Sidecar bytes: `96`
- Sidecar file SHA256:
  `1799552f2ceb86b44df6eab7327732913ae71dd45dc61ecc4019d3a6d04b84f0`
- Command:
  `bash r5_n4_hw_v41_wrterm2_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- Expected return: `r5_n4_hw_v41_wrterm2_diag_return.zip`

v41 corrects only the package-local observer terminal predicate and observes,
in one run, the Memory_AG accept/replay state, Buffer_AG source queue,
RD_Buffer_AG tag lifetime, descriptor lifetime, prepared-write/hold and
prefetch-without-descriptor boundaries. Numeric analysis, workload, final
configuration, golden, timeout, backpressure and functional RTL are unchanged.

## Final self-audit

Deterministic double build is byte-identical. The final ZIP audit passes all
25 checks with zero errors. Exact final compiled observer HDL contains 81 XMR
occurrences and 38 unique consumers; all 38 are classified and uncovered is
zero. The focused compatible frontend positive exits zero. Five declaration,
scope and actual-consumer negatives exit `1/5/6/1/1`. Safe compile runner
reachability exits the expected stub code 74; TERM preservation returns runner
143 with harness zero. Canonical-decision, feature-binding and path-budget
negatives all fail closed. The plan changed only as mutable provenance after
the build; active rule identities remain current-match and the ZIP bytes did
not change.

Receipts:

- Return report:
  `outputs/conv_node0004_v40_return_analysis/report.json`
  SHA256 `07ba09ab6490771b2e4a645d9ff905706619bdb09b447ca31b744f22419d3bbd`
- Observer scope:
  `outputs/conv_node0004_v41_package_validation/observer_scope.json`
  SHA256 `aa145c0867dd9f07cc307242aefeec2f47f09f40609799211b60f1e2a071ee39`
- Runner controls:
  `outputs/conv_node0004_v41_package_validation/runner_controls.json`
  SHA256 `11ca088d5919426594edb2bb846bd47adf7279b234ac6716c6d512807d2f80c3`
- Final ZIP audit:
  `outputs/conv_node0004_v41_package_validation/final_zip_audit.json`
  SHA256 `a2902498d5f7ad7e28ae4fe2870f8d43d228272ca77499f58b6b20462d901784`

## BLOCKER_DELTA and rule feedback

- Closed: `B_CONV_NODE0004_WRTERM_RAW_EDGE_CHRONOLOGY_UNAVAILABLE`
- Opened:
  `B_CONV_NODE0004_WRTERM_FINAL_DESCRIPTOR_PREDICATE_AND_POST_TERMINAL_OWNER_UNRESOLVED`
- Preserved: dynamic natural terminal and formal D 320 blockers
- Not reopened:
  `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`. The active time-to-root-cause,
actual-consumer HDL scope-negative, continuous-closure and final-ZIP audit
rules already cover the escape and the successor evidence. No non-synonymous
public rule delta is required.
