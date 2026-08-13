# QLinearAdd node0007 v35 actual-consumer current-rule revalidation

Date: 2026-08-05

## Provenance

- analysis owner thread:
  `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target/mainline:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`
- action:
  read-only, content-neutral post-generation revalidation of the exact final
  v35 ZIP
- numeric/W3/qparam/tail/workload/config/golden repeated: `false`
- package bytes modified: `false`
- functional RTL modified: `false`
- server upload/run/lease: `false`

## Current receipts

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` (mutable provenance):
  `f2a671834e3f847829558d1c73b848a908c0546d577ebe662bc0eb690a970e8b`
- `.agents/rules/生成前必读索引.md`:
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- `.agents/rules/服务器测试包生成规则.md`:
  `da0e2dc8dab9a64d4eaca3f15ee0634b3af6b299dfa505e192d6b6bf30ff12b8`
- `.agents/rules/QLinearAdd算子配置规则.md`:
  `28bb859c5f9b8cb5ce5e7ac0dfd81bc06c8b24835d1d3fa4a6062c7c23c0800b`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

Applied rule IDs:

- `CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`
- `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001`
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`

## Exact package identity

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_crow32_v35.zip`
- bytes: `26180881`
- SHA-256 before and after:
  `45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_crow32_v35.zip.sha256`
- sidecar file SHA-256:
  `03f3067b57c82be83b27cb402e4e2c7884fbc49d820621f22a66820e23cecedc`
- package scope:
  split-C cumulative prefix
  (`A dequant -> B dequant -> relocation -> FP32 add`), not the complete
  QLinearAdd six-stage/output-quant chain

## Actual-consumer result

The validator fresh-read the exact final ZIP and derived the compiled
QLinearAdd include order from `tb_probe/native_return_observer.svh`. For
`qlinearadd_node0007_mse_pair_matrix_tail_v29.svh` it enumerated:

- actual consumer expressions: `26`
- same-declaration/owner/resolution equivalence classes: `12`
- covered expressions: `26`
- uncovered expressions: `0`
- declaration/initialization-or-reset/qualified-update/consumer ownership:
  closed

Compatible frontend:

```text
C:\iverilog\bin\iverilog.exe -g2012 -s qadd_actual_consumer_focus ...
```

- positive exit: `0`
- delete actual declaration exit: `27` (fail closed)
- delete key qualified update: frontend exit `0`, semantic closure exit `1`
  (fail closed)
- actual-source-span misspell exits by class:
  `1,2,2,1,1,1,2,2,1,2,1,2`; all fail closed

The misspell mutations were copied from actual final member consumer spans and
changed only the selected package-local identifier token. The focused unit
specializes only runtime packed-array indices to zero for Icarus 12.0; no
`qadd_pair_*` declaration, update, or consumer is added by the harness.
Production VCS remains the full-design elaboration boundary.

## New-rule applicability

`CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001` is `record_only` and
non-blocking for this receipt. v35 changed the materialized 32-byte row-pair
configuration, not the observer. The exact pair-matrix member SHA
`ce63cfa88ffd63a554e9e4568d01afe004ba98400f37f18734a3af3495c10b0d`
is byte-equal to frozen v29. The rule explicitly does not retroactively hold a
pre-publication frozen package by format alone.

`CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001` is also `record_only` here:
no observer/parser/canonical predicate bytes changed in this content-neutral
receipt. A future fresh successor that changes such logic must run the trace
unit gate.

The external report publishes a release-gate applicability matrix. The new
matrix format is not written into the frozen ZIP; the previously existing
actual-consumer hold is discharged by this exact-ZIP external receipt.

## Command and result

```text
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/revalidate_qlinearadd_node0007_v35_actual_consumer_scope.py --zip artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_crow32_v35.zip --iverilog C:\iverilog\bin\iverilog.exe --output artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-actual-consumer-revalidation/report.json
```

Final exit: `0`.

The final validator was run twice from the same exact ZIP. Both exits were
`0` and both report SHA-256 values were
`d3f51193099dcd21e6dfc7a0f9e5f622f6ad917141bcaaf78e89651d7a4e2302`.

Machine report:

- path:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-actual-consumer-revalidation/report.json`
- bytes: `44825`
- SHA-256:
  `d3f51193099dcd21e6dfc7a0f9e5f622f6ad917141bcaaf78e89651d7a4e2302`

Validator:

- path:
  `tools/revalidate_qlinearadd_node0007_v35_actual_consumer_scope.py`
- bytes: `23896`
- SHA-256:
  `9a2967a5ee81c6624e9240816031a90186ef2f698c4e780fb5e0accf935426a2`

## Adjudication

```text
RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS
PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN
FINAL_ZIP_BYTES_UNCHANGED=true
ACTUAL_CONSUMER_TOTAL=26
ACTUAL_CONSUMER_UNCOVERED=0
```

The prior `PACKAGE_HELD_ACTUAL_CONSUMER_REVALIDATION_REQUIRED` hold is
discharged. No new package identity is created.

## Rule confirmation

`RULE_CONFIRMATION`: the actual-consumer rule correctly rejects synthetic
expected-inventory closure while permitting mechanically proved
same-declaration/owner/resolution equivalence classes. The applicability and
public-surface rules correctly avoid a content-neutral rebuild when observer
bytes are frozen and unchanged. Claim boundary is local package HDL
syntax/scope/name resolution only; it does not claim server production
elaboration, split-C dynamic completion, full-chain formal D, E3, E4, or E5.
