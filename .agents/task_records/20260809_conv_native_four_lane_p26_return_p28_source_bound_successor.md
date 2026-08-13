# Conv native four-lane p26 formal return → p28 source-bound successor

## Scope and identity

- Owner: native/four-lane Conv node0004 only; serialized Conv and functional RTL remained untouched.
- Formal p26 return: `C:/Users/15383/Downloads/r5_n4_0cc_p26_memag_r1786210539149535582_21324_return.zip`, 2,049,486 bytes, SHA256 `7e8ff498b52821d5f1bd9300bc232a18a93dd10d77916f3b144e635eff4c0937`.
- Exact p26 source: SHA256 `844360af973a6687fe9b0e202e169cfe176df42000859fbd88a15b559b3cce25`.
- Current RTL provenance remains cloud commit `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`, tree SHA256 `c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093`.
- Formal machine analysis: `outputs/conv_native_four_lane_0ccae916_p26_return_analysis/report.json`, SHA256 `6514f27334e059c12f952475f05640d3906288936fca78d0ba113c88e0dd72b5`.

## p26 RETURN_ANALYSIS

- CRC/root/path/exact-set/allowlist/source/execution/preflight/install receipts: PASS.
- Production compile exited 0; simulation started; return was signal `INT`, run exit 125. This is a qualified partial diagnostic return, not a natural terminal.
- LPG: the sole qualified PE7/source13 index-8 public acceptance was followed by the actual `Memory_AG` matching queue write, queue read, then `Buffer_AG` downstream acceptance.
- FD: after that actual delivery and before Buffer5 released the selected occupied row for further SA writes.
- HANG_ROOT_CAUSE remains `ROOT_NOT_YET_UNIQUE_BUFFER5_ROW_RELEASE_CHAIN`; current class is `BUFFER5_OCCUPIED_ROW_WITH_NO_MEMORY_REQUEST_MANAGER_READ_VISIBLE`.
- Closed blockers: actual Memory_AG queue-write absent, queue-read absent, and Buffer_AG downstream-accept absent.
- Open blocker: `B_CONV_NATIVE_BUFFER5_SELECTED_ROW_RELEASE_CHAIN_UNRESOLVED`.
- p26 has no formal-D payload by design. `c0_natural_terminal=false`; 27-run natural, 320D, E3, E4, E5 and dynamic performance remain unclaimed.

## p27 local hold and p28 correction

p27 passed initial generation/regeneration and six-state runner checks, but a final multi-instance parser trace found a blocking result-trust escape: generated `count_nonzero` reads only the last `SUMMARY` stored for a boundary. Because one generated module is bound to multiple Buffer/MRM instances, a later zero-count sibling can erase an earlier target-instance count and alter the unique diagnosis. p27 was never run and is preserved under `superseded`; hold receipt SHA256 `3c8d781fbca245ef3dcd8d62a2aeeda65e152b4970159840b437747abf048232`.

p28 keeps the same source-bound symbol-id causal cone and changes only the generated decision metrics to sticky `class_seen`. Its exact parser trace appends trailing zero-count sibling summaries and still distinguishes all three candidates. The 87 installed payload members, SCA semantics, numeric/W3/workload/config/mapping/bitstream/execplan/golden, legacy observer and functional RTL are frozen.

## p28 release receipts

- Pickup ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p28_b5release.zip`
- Bytes: 5,910,425
- SHA256: `3b15bf1cebf18b95d07e4c290ccf246d7cd6f89e6b2bd6c9665b05186b2e0066`
- Deterministic double build: PASS.
- Source-bound generation: PASS/errors0, SHA256 `579ef37cbaca67570bfb816e65899743e0b80d6d94d499a48b3709f748b9bdeb`.
- Exact final-ZIP regeneration: PASS/errors0, SHA256 `e3fcdb05432c1e800deddf954c18b006eb7a80346f9128ec0b76783380eaf6de`.
- Family audit: PASS/errors0, SHA256 `2c4581a7d52bea7aac515ba0f7f4fff06f001e652654ab1da52cae9fa81fa4f6`.
- Build profile: PASS/errors0; one record-only optional-title warning, SHA256 `2cde627de844999ad22fc0fb983418f7df8fc2075f3607c4e37b01a53eb52a33`.
- Final ZIP audit: `PACKAGE_READY_NOT_RUN`, SHA256 `b4dd5fec2484279cb183e0be91b69e5fa764d34bf6b135a56d06e6326a32b12d`.
- Runtime scenarios: normal=0, preflight-fail=5, compile-fail=42, HUP=129, INT=130, TERM=143; all reached finalizer, published fixed-result return, and preserved NDP-root direct exact-set. Harness SHA256 `c6ded4f72313035e32b43a3804a650dec14d9d261bb823614a1660e09ebfee4f`; shared validator PASS/errors0 SHA256 `148fcf081ef1c43d8fc57578258283798f324a75d96a62899233a85c0f971b0f`.
- Storage index PASS SHA256 `1242c0e8bf260d0f4dabd1f35b4637fc9b0c191d3787ef85bc176f6979697e24`; native family has exactly one pending identity: p28.

Server command:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected unique return:

`/home/panqs/ndp/simresult/r5_n4_0cc_p28_b5release_r<epoch-ns>_<pid>_return.zip`

## Static performance receipt and claim boundary

- Compute occurrences: 205,520,896 serialized → 51,380,224 native (4.0× reduction).
- Weight bytes: 262,144 → 65,536 (4.0× reduction).
- Activation bytes: 51,380,224 serialized single-B → 12,845,056 per native producer (4.0×); two physical native producers total 25,690,112 (2.0× total-physical reduction).
- Maximum useful lane utilization: 25% → 100%.
- These are unchanged config-derived inversion receipts. Until a natural terminal plus formal 320D return closes, they are not an E5 runtime-performance claim.

## Rule feedback

`RULE_CONFIRMATION`: source-bound generation/exact regeneration, install-only V2, fixed simresult, NDP-root direct exact-set, and storage rotation gates were applied and passed.

`RULE_DELTA_PROPOSAL`: generated-parser validation should exercise two same-boundary instances in both summary orders and reject `count_nonzero` decisions unless the plan proves a single bound instance or the parser aggregates counts across instances. This is non-synonymous with current single-instance trace coverage and is evidenced by the p27 hold.
