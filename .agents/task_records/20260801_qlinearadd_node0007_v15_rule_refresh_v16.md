# QLinearAdd node0007 v15 current-rule refresh / v16 release

## RETURN_ANALYSIS

- `r5_qadd_n7_dbuf_v15.zip` remains byte-identical:
  `3beef62deeea914abff9120714f8a8fcbad13e9cc40cd0b2a6f68db74c0eac3a`,
  38032365 bytes.
- v15 is `QUARANTINED_CURRENT_QADD_RULE_CONTRACT_DRIFT`.
- Content-neutral external receipt is not allowed. Its final manifest binds the
  old QLinearAdd rule SHA and its exact applicable-rule list omits
  `CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`; both are
  package-internal machine contracts.
- No numeric, W3, workload, config-numeric, golden or RTL analysis was repeated.

## Fresh successor

- package:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_rule_v16.zip`
- bytes: 38034209
- SHA256:
  `a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_rule_v16.zip.sha256`
- sidecar SHA256:
  `1e8ed70a31908ce377b110018be21f809e9606c5eee96f267a8b520f2f3ef76c`
- expected return: `r5_qadd_n7_dbuf_rule_v16_return.zip`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- status: `PACKAGE_READY_NOT_RUN`

The exact rebuild delta is limited to install namespace, README rule receipt,
and manifest identity/provenance/current-rule contract. After namespace
normalization, all 133 other package files are byte-identical to v15.

## Current post-generation rule receipts

- `.agents/rules/生成前必读索引.md`:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`:
  `fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025`
- `.agents/rules/QLinearAdd算子配置规则.md`:
  `a1faa3319c267b6d6b7f3e9d2b74c45a52b9a347888dc42de0dfb8599ced5964`
- applied new rule:
  `CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`

All three files were reread in full after the final ZIP was generated; their
hashes remained current.

## FINAL_ZIP_RULE_SELF_AUDIT

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=[]`
- `error_count=0`
- `all_required_negative_controls_fail_closed=true`
- report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-rule-v16/final_zip_self_audit.json`
- report SHA256:
  `00a4cb5ddae9259e7c0e34fd4ca7852d8e4f76fd03479889be5ff7df4c84f5f0`
- build receipt:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_rule_v16.validation.json`
- build receipt SHA256:
  `c40cbb97a87c2870778daf71e02f73787719c2eff1364813afcf92c69c470966`

The validator directly checked the final JSON equation, mapped physical
`ROW_LC4`, decoded bitstream dump (`ROW_LC.end=2`,
`buffer5.buf_end_row_addr=1`), and the RTL consumer equation for
`op_relocation_pad`, `op_tail_mul`, and `op_tail_round`. Each stage proves
32-byte transaction = 2 rows × 16 bytes.

New formal negative controls all fail closed with exit code 1:

- delete one row
- restore old `ROW_LC.end`
- restore old `buf_end_row_addr`
- tamper transaction length
- delete the formal rule ID

Existing final-ZIP controls also pass, including real runner to safe compile
stub (runner exit 86, compile reached) and wrong-identity precompile negative
(runner exit 5, compile not reached).

Commands and results:

```text
python tools/build_qlinearadd_node0007_d_buffer_rule_v16_server_package.py
exit=0

python tools/validate_qlinearadd_node0007_d_buffer_rule_v16_server_package.py
exit=0

python -m unittest \
  tests.test_qlinearadd_node0007_d_buffer_rule_v16_server_package \
  tests.test_qlinearadd_node0007_d_buffer_supply_v15 \
  tests.test_qlinearadd_node0007_d_buffer_supply_v15_server_package -v
exit=0; 9/9 passed
```

## BLOCKER_DELTA

- Closed: current QLinearAdd rule SHA / formal-ID package-contract drift.
- Open dynamic blocker: v16 has not been run on the server; E4/E5 remain
  unclaimed.

## RULE_DELTA_PROPOSAL

None. The published conservation rule is sufficient and is now enforced by
the final-ZIP validator.

## PACKAGE_RELEASE

`r5_qadd_n7_dbuf_rule_v16.zip` is the sole runnable identity and is
`PACKAGE_READY_NOT_RUN`. v15 stays quarantined and must not be uploaded or
run.
