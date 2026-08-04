# QLinearAdd node0007 B-control v24 return analysis

## Provenance

- analysis owner:
  `019fa2c0-b647-7a91-93bf-d21a173487e3`
- unique return/mainline target:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`
- analyzer:
  `tools/analyze_qlinearadd_node0007_bctrl_v24_return.py`
- analyzer bytes/SHA256:
  `18569` /
  `88f8d9eb2adf9388e6dae7921e78c8fa39fff0723107c42ff8e0366cd08a34cd`
- machine report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-bctrl-v24-return-analysis/report.json`
- machine report bytes/SHA256:
  `32568` /
  `7e7fdf69485c3e53decd1b01976cd05d144e214a141eb39d13d61c29f4970497`
- numeric/W3/qparams/tail/workload/config/golden repeated: `false`
- functional RTL modified: `false`
- server uploaded/run/inspected by owner: `false`

## Transport and identity

The user-returned ZIP is accepted under the user-attested no-sidecar
transport rule. The absent adjacent sidecar replaces only the external
transport receipt.

- return bytes/SHA256:
  `708276` /
  `6cd544733c51c8f7626abe66d221321a1b3a524b41d278fa46c51530b41571b0`
- internal root:
  `r5_qadd_n7_bctrl_v24_return`
- frozen source ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_bctrl_v24.zip`
- source bytes/SHA256:
  `38032104` /
  `71e14695c3025340987dba2fc0ffedd23e8e61d9bcb6eaec704de74c8e6928da`

ZIP CRC, single-root, path safety, duplicate/symlink absence,
`RETURN_MANIFEST` exact-set/size/SHA, return allowlist membership and the
returned source manifest byte binding all pass.

## Dynamic result

This return is not a timeout and not a hang:

- compile exit: `0`
- simulation exit: `0`
- signal: `NONE`
- natural simulation terminal: `true`
- host simulation wall time: `6137.602946413 s` (`1.7049 h`)
- simulated terminal: `20407565625 ps`
- VCS CPU time: `6131.8 s`
- stage starts: `1`
- stage completions: `1`
- completed stage: `op_b_dequant`
- completion: `543212` active cycles

The canonical record has a valid content digest and an ordered one-stage
scope. It reports:

- decision: `B_DEQUANT_CONTROL_COMPLETED`
- boundary: `OP_B_DEQUANT_COMP_FINISH`
- heartbeat samples: `33`
- advancing qualified windows: `32`
- qualified monotonic: `true`
- level counted as progress: `false`

Therefore:

- `LAST_PROVEN_GOOD` =
  `OP_B_DEQUANT_NATURAL_COMP_FINISH_WITH_32_QUALIFIED_ADVANCING_WINDOWS`
- `HANG_ROOT_CAUSE` = `NOT_A_HANG`

The control also resolves the old/new package question: the same frozen
B-dequant configuration completes when the v18 base observer is restored.
The v20 B-stage failure was introduced by its package-local observer path,
not by the frozen B configuration or functional RTL.

## Formal D and conjunction

All 28 formal-D paths exist, but every file is an X-valued dump from the
unexecuted full-chain tail:

- expected/present/missing/extra: `28/28/0/0`
- valid 128-bit payload files: `0`
- invalid 128-bit payload files: `28`
- invalid lines: `1053696`
- mismatch evaluable: `false`

The unchanged full-chain analyzer correctly cannot decode these payloads
and exits before writing `evidence/SERVER_RESULT_GATE.json`.
`RETURN_MANIFEST.required_missing` contains that one file. The first
post-stage divergence is therefore:

`POST_SIM_PACKAGE_ANALYZE_DECODE_128BIT_ON_UNEXECUTED_FULL_CHAIN_D`.

This does not invalidate the B-only dynamic claim, but it forbids a full
QLinearAdd numeric claim:

- `SERVER_RESULT_GATE=false`
- `E3=false`
- `E4=false`
- `E5=false`

Future stage-local diagnostic packages must bind a stage-local
terminal/output contract and must not invoke the 28-D full-chain decoder.
The final D/full-chain package retains the six-stage plus 28-D conjunction.

## BLOCKER_DELTA

Closed:

- `B_QADD_V20_PACKAGE_LOCAL_FP32_OBSERVER_EVENT_STORM_SUSPECT`
- `B_QADD_NODE0007_OP_B_DEQUANT_DYNAMIC_COMPLETION_UNPROVEN`

Opened:

- `B_QADD_V24_B_ONLY_FULL_CHAIN_RESULT_GATE_SCOPE_MISMATCH`

Kept open:

- `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`
- `B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN`

## RULE_CONFIRMATION

`CURRENT_RULES_CONFIRMED_EFFECTIVE`.

Ordered-stage qualified evidence proves only B-dequant, and the server
result conjunction correctly prevents E3/E4/E5 when the formal numeric
gate is absent and the D payloads are undecodable. No public-rule delta is
required by this return.

## Continuous successor

Continue the already-authorized true split:

- A: independent `op_a_dequant + op_b_dequant`
- B: independent `op_relocation_pad`
- C: cumulative prefix through `op_fp32_add`
- D: frozen six-stage full chain with 28 formal D

This return-analysis step generates no package. Split package
materialization continues in the same owner task.
