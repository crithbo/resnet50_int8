# QLinearAdd node0007 v19 FP32 双输入入口窄诊断包交付记录

## Provenance

- analysis owner thread: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-ingress-diag-v19/report.json`
- machine report SHA256: `f8aee42cd063a495bc5a5afa025cd6cfc5c8894066abcb0813a389ac2edc1c6b`
- numeric analysis repeated: `false`
- W3/qparam/tail/workload/config/golden repeated: `false`
- functional RTL modified: `false`
- server uploaded or run: `false`

## Frozen evidence and current receipts

- v18 source: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_colpair_v18.zip`
- v18 source SHA256: `570abd6f483f47f144ae9cb9320418e4acd423e2cf011e1f44a0f5b2537edd1a`
- v18 status: `QUARANTINED_DYNAMIC_FP32_ADD_HANG`
- v18 analysis task record SHA256: `0469bce83c9782b554075356af578b1930a517bafac0fc4f24b6b8dad81a3801`
- v18 analysis report SHA256: `a32a6023b930de3c25c1072d6692e11b36b012cbebed721b8f6fa890be66fdf8`
- last proven good: `OP_RELOCATION_PAD_COMP_FINISH`
- first divergence: `OP_FP32_ADD_AFTER_FINITE_READ_ACTIVITY_BEFORE_GA_INPUT_ACCEPT`
- agent SHA256: `aae402d48b82d026c5512c8a6a5d4c9ff9db4bcc6a94576cd618c168f3fd188e`
- mutable plan start receipt: `450d175e178a9166056614635e319bb2f2e80a5823dbdcb73d8eefd4aba9c525`
- generation index SHA256: `f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8`
- server-package rule SHA256: `7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141`
- QLinearAdd rule SHA256: `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- exact UINT8 tail rule SHA256: `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- post-generation full reread: `true`

## Read-only root-cause adjudication

The frozen final JSON, mapping review, execplan, SCA and direct RTL consumers consistently route:

- `READ_STREAM0 -> MSE0 -> Buffer0 -> GA group0/inport0`
- `READ_STREAM1 -> MSE1 -> Buffer2 -> GA group1/inport1`

Both GA PE inputs are enabled. The v18 return proves finite read-side activity but does not contain qualified MSE1, Buffer2, GA operand-pair capture, consumer-accept or first-output evidence. Therefore no single configuration or RTL leaf can be proved as the unique first blocker.

Adjudication: `STATIC_CHAIN_VALID_BUT_DYNAMIC_DUAL_INGRESS_EVIDENCE_INSUFFICIENT`.

The successor is consequently `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`; it does not change the frozen workload/configuration, extend timeout, add per-cycle logging, or claim a functional fix.

## v19 diagnostic scope

Source-domain qualified counters use `clk_sg`; low-rate snapshots use the continuously alive `clk_db`. The ordered final-stage canonical decision uses only paired frontiers, so one-sided MSE activity and level states cannot count as progress.

Observed chain:

1. MSE0 and MSE1 request accept
2. MSE0 and MSE1 rdata accept
3. MSE0/MSE1 to Buffer0/Buffer2 accept
4. Buffer0/Buffer2 write accept and row-valid state
5. Buffer0/Buffer2 ARM read accept and array delivery
6. GA operand0 and operand1 capture
7. GA paired tag/mask match
8. GA consumer accept
9. GA first output

Runtime feature enable, time0 marker, returned feature receipt, stage events, signal trap, EXIT/TERM finalizer and canonical decision are bound end to end.

## Package release

- status: `PACKAGE_READY_NOT_RUN`
- class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- candidate release: `false`
- evidence: `E2_LOCAL_ONLY`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_fp32_ingress_diag_v19.zip`
- ZIP bytes: `38038498`
- ZIP SHA256: `f32abc4b2b91bf5e854ab113aa98fd1f7925e68a3bd8958f2454762a524709ba`
- sidecar: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_fp32_ingress_diag_v19.zip.sha256`
- sidecar bytes: `103`
- sidecar SHA256: `4ac64a4f224d5c23b45bfd1e7c4355630a044d35fe70052cd529f0b1268df741`
- server command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return: `r5_qadd_n7_fp32_ingress_diag_v19_return.zip`

Two independent deterministic builds produced the same final ZIP SHA256.

## Final ZIP current-rule audit

Validator command:

```text
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools\validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package.py
```

Validator exit code: `0`.

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- errors: `0`
- all required negative controls fail closed: `true`
- final audit: `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-ingress-diag-v19/final_zip_self_audit.json`
- final audit bytes: `7887`
- final audit SHA256: `82876de5bfb32367a9441f496c052df94f2bc11e358e180c1a1baf3b08808fef`
- build receipt: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_fp32_ingress_diag_v19.validation.json`
- build receipt bytes: `1386`
- build receipt SHA256: `deb1be92a773e6f55be5dccb6dfa72474a7905470dbea0899ca8e0e745067b38`
- final manifest SHA256: `516a8dd95e4926b7f2a93d189e35d5098ac129c24de7c525e3975b8daea942dd`

The current audit and build receipt above were produced by a post-report,
read-only revalidation. That revalidation did not modify the package or
sidecar bytes, did not generate a new identity, and left the authoritative
package SHA256 at
`f32abc4b2b91bf5e854ab113aa98fd1f7925e68a3bd8958f2454762a524709ba`.

Positive controls:

- real runner to safe compile stub reached compile; exit `86`; package unchanged
- safe simulation EXIT finalizer returned outer exit `125` and collected canonical decision, feature receipt and return ZIP
- safe TERM finalizer returned outer exit `125`, recorded `TERM`, and collected the same required records

Negative controls:

- wrong identity failed before compile: exit `5`
- source include, `+incdir`, macro, feature plusarg, time0 marker, return receipt and stage event deletion: each exit `1`
- earlier-stage finish overriding later hang, individual-MSE-only progress, missing feature marker and missing canonical reason: each exit `1`

## Blocker and rule delta

- closed: `B_QADD_NODE0007_RELOCATION_D_BUFFER_ROW_ONLY`
- open: `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`
- next return decision: identify the first non-advancing paired frontier from MSE0/MSE1 request acceptance through GA first output
- `RULE_DELTA_PROPOSAL=NONE_CURRENT_RULES_SUFFICIENT`
