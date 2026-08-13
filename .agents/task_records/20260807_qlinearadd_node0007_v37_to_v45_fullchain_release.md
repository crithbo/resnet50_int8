# QLinearAdd node0007 v37 PASS → v45 six-stage full-chain release

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target/mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- result: `PACKAGE_READY_NOT_RUN`
- classification: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- candidate release: `false`
- evidence: `E2_LOCAL_ONLY`
- server upload/run/lease: none
- plan/public rules/functional RTL/other family: unchanged

## Semantic scope

The fresh package is the six-stage node0007 chain:

1. `op_a_dequant`
2. `op_b_dequant`
3. `op_relocation_pad`
4. `op_fp32_add`
5. `op_tail_mul`
6. `op_tail_round`

It requires one natural six-stage terminal and the exact final UINT8 28-D
readback conjunction:

`compile0 AND simulation0 AND loader-exact AND ordered6 AND natural-terminal
exact-once AND D-exact-set28 AND missing0 AND invalid0 AND mismatch0`.

The v37-proven 32-byte Buffer5 supply, numeric/W3/six-qparam/tail/workload/
config/golden semantics, DP/topology and Requant strict dependency were
frozen. Numeric analysis was not repeated and split-C was not rerun.

## Construction and local gate

The local full-chain composition receipt is
`artifacts/q38/build_receipt.json`, SHA256
`4e86a6ed2e2bae3f1fe8b39a881d6044706e61c3863be5ffd3bec8a0ac2df10e`.
It binds six stages, 182 execplan commands, 91 external/config preloads and
28 final UINT8 outputs.

The first v44 candidate was never released. The shared exact-ZIP validator
correctly rejected it because `SERVER_RUNTIME_LAYOUT_CONTRACT.json` lacked the
required `claim_boundary`. Its production runner was not changed. The field
was added to the contract and a fresh identity, v45, was deterministically
built twice.

The host MSYS full-runner harness did not finish within the bounded local
limit and was terminated. It was not rerun and is not production evidence.
No host workaround entered the production runner. The runtime-layout and
early-finalizer scenarios instead use the accepted shared install-only V2
14/14 changed-surface receipt, while the exact v45 runner independently binds
layout preparation, compile/simulation markers, early EXIT/HUP/INT/TERM traps
and same-shell `on_signal→finalize`.

Package-local observer HDL is byte-equal to the accepted v37 HDL scope:

- v37 HDL receipt SHA256
  `b7c2e250e0292c8ae5cbeb3c59aa752695743a150ca2be85484d894946acae63`;
- 5 HDL members byte-equal;
- declaration/use/update negatives are receipt-reused.

The six-stage canonical predicate is a changed surface. Direct trace checks
proved ordered-six complete and made earlier-stage-only and
individual-stage-only fail closed; stable level is not transaction progress.

## Exact released identity

Pickup:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_fullchain_v45.zip`

- bytes: `38,055,269`
- SHA256:
  `913e6831d47b9673f4c50e0efe28ba95fce14a2b685278c9e19755c5797f113a`
- sidecar is internal under `pending_receipts`; sidecar SHA256:
  `6fa7e545f8611940b990c0da149bf13d44ba9a1158f9a74e725748ffc786ffd2`

Receipts under
`artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007/r5_qadd_n7_fullchain_v45/`:

- deterministic build: 683 bytes, SHA256
  `beca9f15c80617c0a866296dd97420cc3246601e839c98ddfe9dd56cc0b42148`;
- family validation: 22,362 bytes, SHA256
  `c3505d39a2e9c320eee3296c8db892fa76c7184e95b9cd1e1fe9f8f4dd028f6e`,
  `valid=true`, `errors=0`;
- runtime-layout harness receipt: 9,470 bytes, SHA256
  `3fe89ceb0cedccf189a5ccb25f2e0a2f049f172a0f0e803c9ad0b381a17a5456`;
- shared exact-ZIP validation: 18,983 bytes, SHA256
  `d9744e68a64495b3fdf7a0c78dd6afacff6224caa1f184c96b2a0ce3ba794fa5`,
  `pass=true`, `errors=0`, invoked once for exact v45;
- final ZIP audit: 10,337 bytes, SHA256
  `85cad2d50befaa36894bae2cc033ff8c53dbf41b8963580bbc414419be1d4982`,
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`;
- release report: 4,825 bytes, SHA256
  `51f7748f24040c6d35f6f2b6c5a800b8107739199c2fc6df4389376b37541666`.

Negative-control mechanisms closed:

- wrong package identity;
- deleted required feature member;
- earlier-stage finish;
- individual-stage-only progress;
- shared V2 file/symlink collision, path escape, nonfresh leaf, unknown
  overwrite/delete and new root-direct-entry classes;
- frozen observer declaration/use/update classes.

## Runtime layout and server handoff

Only `$server_root/install` must pre-exist as a real, non-symlink directory.
The package safely/idempotently creates absent `install/cfg_pkg` and
`install/codex_runs`, then fresh package/attempt leaves. The NDP root direct
name/type exact-set must remain unchanged.

After extracting the pickup ZIP, run:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02
```

Fixed results:

- `/home/panqs/ndp/simresult/r5_qadd_n7_fullchain_v45_return.zip`
- `/home/panqs/ndp/simresult/r5_qadd_n7_fullchain_v45_return.zip.sha256`

## Storage rotation

The formally consumed v37 package moved to
`tested/qlinearadd_node0007/r5_qadd_n7_cout32_rootclean_v37/`.
The QAdd pending exact set is now only `r5_qadd_n7_fullchain_v45`.

`PACKAGE_STORAGE_INDEX.json`:

- bytes: `136,052`
- SHA256:
  `f798f97ef23dfb9751b6a4a70c120942521a86c52dec5ffd34852cab55a2e432`
- `pass=true`

## Commands and exits

- deterministic build:
  `python tools/build_qlinearadd_node0007_fullchain_v38_server_package.py`,
  exit `0`;
- family validation:
  `python tools/validate_qlinearadd_node0007_fullchain_v45_server_package.py`,
  exit `0`;
- shared exact-ZIP validation:
  `python tools/validate_server_package_runtime_layout.py ...`, exit `0`;
- final audit:
  `python tools/audit_qlinearadd_node0007_fullchain_v45_final_zip.py`,
  exit `0`;
- storage pre-audit, rotate and post-audit: exit `0`.

## Blocker delta and rule feedback

Closed:

`B_QADD_NODE0007_SPLIT_C_32B_BUFFER5_SUPPLY_AND_STAGE_LOCAL_28D`.

Open until a formal server return:

`B_QADD_NODE0007_FULLCHAIN_PRODUCTION_NATURAL_TERMINAL_AND_UINT8_28D`.

`RULE_CONFIRMATION`: current install-subtree V2, fixed-simresult,
NDP-root-top-level, final-ZIP self-audit, QLinearAdd and storage-rotation
rules are sufficient. No non-synonymous public or family rule delta is
proposed.

Claim boundary: local package/bootstrap/layout/frozen observer delivery,
six-stage contract and final UINT8 28-D result gate construction only. No
production compile, DUT simulation, natural terminal, returned 28-D, E3, E4
or E5 claim.
