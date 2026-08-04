# Conv node0004 v30 return → v32 MSE4 index successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Route: serialized Conv correctness only
- Numeric/W3/workload/config analysis repeated: `false`
- Functional RTL modified: `false`
- Server action / lease: `false`

## RETURN_ANALYSIS

The v30 return identity, CRC/root/path, duplicate/symlink closure, exact allowlist,
per-file receipts, source binding, package/install/observer preflights and
runtime-D-absent gate all pass. Compile and runner exit status are zero and the
signal is `NONE`, but natural terminal is absent. Formal D is `0/320` present,
`320` missing and `0` mismatch; therefore E3/E4/E5 are all false.

Qualified v30 evidence proves:

- WR data prepared groups: `16`
- generated descriptor handshake / FIFO push / FIFO pop: `14 / 14 / 14`
- memory request 0 / 1: `14 / 14`
- prepared reads: `14`
- alternating output-buffer writes and reads: `7+7 / 7+7`
- final descriptor FIFO: empty, count zero

Thus all 14 descriptors that were generated were conserved through FIFO,
both memory request paths and both output buffers. The missing two descriptors
were not lost or prematurely popped after generation.

`LAST_PROVEN_GOOD`:
`MSE4_ALL_14_GENERATED_DESCRIPTORS_PUSHED_POPPED_AND_CONSERVED_THROUGH_BOTH_MEMORY_REQUESTS_AND_ALTERNATING_OUTPUT_BUFFERS`

`FIRST_DIVERGENCE`:
`MSE4_MEMORY_INDEX_MATCH_QUEUE_TO_WR_MEMORY_AG_GENERATION_OF_FINAL_TWO_DESCRIPTORS_FOR_ALREADY_PREPARED_GROUPS`

`HANG_ROOT_CAUSE` remains
`UNRESOLVED_AFTER_EXHAUSTIVE_V30_BOUNDARY`. The unique missing dynamic boundary
is Memory_AG_Idx_Queue per-input accept/match/push/pop through WR_Memory_AG
bias/transaction/finish/descriptor generation. The frozen LC9/LC15 shared
fanout and AND-backpressure is a static candidate, not yet a functional-RTL
defect claim.

The former SA PE outbuffer ALU-write occupancy blocker remains
`INVALIDATED_NOT_RTL_BUG` and is not reopened.

## BLOCKER_DELTA

- Closed: `B_CONV_NODE0004_MSE4_DESCRIPTOR_TO_WR_DATA_FINAL_TWO_GROUPS_UNOBSERVED`
- Opened: `B_CONV_NODE0004_MSE4_MEMORY_INDEX_TO_DESCRIPTOR_FINAL_TWO_GROUPS_UNOBSERVED`
- Preserved: dynamic natural terminal and formal D 320 blockers

## Successor

v31 was quarantined because the final-ZIP audit found missing current common/NDP
rule receipts. No v31 identity is releasable.

Fresh v32 adds only the low-cost, runtime-gated `RETURN_OBS_MSE4_INDEX` boundary:
per-input accepted events, all-input match, queue push/pop, WR AG bias capture,
transaction capture/finish, descriptor handshake and prepared write. Raw
valid/backpressure/queue count/full/empty are state corroboration only.

- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: `false`
- Status: `PACKAGE_READY_NOT_RUN`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v32_mse4_index_diag.zip`
- ZIP SHA256: `87a3e3474c3c1fbd28a8a4220919a8249c310c915da87bba58c28a7e6d8eb835`
- Sidecar SHA256: `88cb94a4fb4cdc246f0ce4d6afea3ee282591667a2b5ec8db0871b1ba9730ba7`
- Command: `bash r5_n4_hw_v32_mse4_index_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- Expected return: `r5_n4_hw_v32_mse4_index_diag_return.zip`
- Local RTL analysis identity: `d0aa87f682880a260fb792aaac88f70a23aba414`

Deterministic double build matched. Focused compatible-front-end compile and
identifier declaration/update/use closure passed. Typo, deleted declaration,
syntax damage and deleted qualified update negatives all failed closed.
Runner safe-compile, EXIT/TERM finalizer, identity, feature binding, marker,
stage/terminal/progress and canonical-decision controls passed.

Final ZIP self-audit:

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- all negative controls fail closed
- report SHA256: `d223e77f76676a0658d0d41c1dc7700f5a89dc201134cbc53a8cf66ef6e64e63`

## RULE_CONFIRMATION

Current rules are sufficient and executable. In particular, the no-sidecar
transport rule did not relax internal gates; the conjunctive result gate rejected
all-missing D despite mismatch zero; hang-first/progress localization narrowed
the boundary; feature binding and HDL scope controls rejected their negatives;
and final-ZIP self-audit quarantined v31 and admitted only fresh v32.

No non-synonymous public rule delta is proposed.

## Evidence

- Return report: `outputs/conv_node0004_v30_return_analysis/report.json`,
  SHA256 `dc4737391a41ec4bb020431a0cf847a7fbbc94c3e69daecf8074444a46579319`
- Runner controls: `outputs/conv_node0004_v30_return_analysis/v32_runner_controls.json`,
  SHA256 `3b3793b53cb370a0c5552381da892dfc94d3e2cc0ba958d300c9b18eb89862a7`
- Observer scope: `outputs/conv_node0004_v30_return_analysis/v32_mse4_index_observer_scope.json`,
  SHA256 `0f37a63346ff3f59e2c57dcfed4e9f63a0ac339cf6ca571dd4ad6510afe6070f`
- Final ZIP audit: `outputs/conv_node0004_v30_return_analysis/v32_final_zip_audit.json`,
  SHA256 `d223e77f76676a0658d0d41c1dc7700f5a89dc201134cbc53a8cf66ef6e64e63`
- Machine release: `outputs/conv_node0004_v30_return_analysis/successor_release.json`
