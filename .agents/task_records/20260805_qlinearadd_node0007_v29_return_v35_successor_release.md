# QLinearAdd node0007 split-C v29 return → v35 successor

## Provenance

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- numeric/W3/qparam/tail/workload/golden repeated: `false`
- functional RTL modified: `false`
- server uploaded/run: `false`

## RETURN_ANALYSIS

The v29 return passed internal CRC/root/path/exact-set/allowlist/source binding and
compiled successfully, but simulation timed out after eight hours. It did not
reach a natural terminal and produced none of the 28 formal D targets, so
`mismatch=0` is unevaluable and E3/E4/E5 remain false.

- `LAST_PROVEN_GOOD=FP32_ADD_MSE0_MSE1_16B_BUFFER_WRITE_ACCEPTED`
- `FIRST_DIVERGENCE=FP32_ADD_BUFFER0_BUFFER2_ARM_READ_ACCEPT_REMAINS_ZERO`
- `HANG_ROOT_CAUSE=UNIQUE_CONFIG_INPUT_BUFFER_TRANSACTION_SUPPLY_MISMATCH_16B_PRODUCED_VS_32B_MASKED_ROW_REQUIRED`

Qualified counters prove one accepted 16-byte write on each operand side, while
Buffer0 and Buffer2 use all eight 4-byte banks. The required 32-byte ARM row
therefore cannot become ready from only `[0,16)`.

Return report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-pairmatrix-v29-return-analysis/report.json`,
SHA-256 `6bfc521f1ec22b2e29ed7ec0679e52d5f9e1db91ea832ae998734bdef0b168c9`.

## Config correction and package audit

The fresh mapping changes only `op_fp32_add` transaction grouping:

- stream transaction: `16 → 32` bytes;
- Buffer0/2 producer windows: `[0,16)` and `[16,32)`;
- inner occurrence: `18816 → 9408`;
- preserved coverage: `8 × 9408 × 32 = 2,408,448` bytes per slice.

The final validator independently binds the final ZIP bitstream to the fresh
mapping receipt and checks both operands, the active RTL ready equation,
occurrence/coverage, SCA inputs, 28 absent runtime-D targets, observer/HDL,
runner/finalizer, return contract, path budget and all directed negative
controls.

Intermediate v30–v34 identities are quarantined. They exposed stale rule aliases,
two missing `install/`/`cfg_pkg/` SCA path components, and a path-guard stdout
contract issue before server delivery. They are not runnable identities.

## PACKAGE_RELEASE

- status: `PACKAGE_READY_NOT_RUN`
- evidence: `E2_LOCAL_ONLY`
- candidate release: `false`
- identity: `r5_qadd_n7_crow32_v35`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_crow32_v35.zip`
- bytes: `26180881`
- SHA-256: `45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829`
- sidecar SHA-256:
  `03f3067b57c82be83b27cb402e4e2c7884fbc49d820621f22a66820e23cecedc`
- command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02`
- expected return: `r5_qadd_n7_crow32_v35_return.zip`

Final audit:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-server-package/final_zip_self_audit.json`,
SHA-256 `b4d6f11b204c613cb12a04ace2da1dcc17a430eb15b19d4ee78cee2941a3a110`,
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`.

HDL receipt:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-server-package/hdl_scope_revalidation.json`,
SHA-256 `cea2f15dd2a8f9f2619259608b5fd21c2917efd10f11c7cc54bece99b59428ee`.

Machine release report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-server-package/release_report.json`,
bytes `8446`, SHA-256
`7aed286f090327324aa01214923dbd9d3f3a456e1fb1d20318d2b3a4c8c88a82`.

## BLOCKER_DELTA

Closed:

- unresolved split-C FP32 ingress root cause;
- 16-byte producer supply versus 32-byte masked Buffer0/2 row;
- package-local SCA preload installed-tree path mismatch.

Open:

- server return must prove ARM read accept, paired GA ingress and FP32 output;
- split-C success cannot claim full-chain 28D/E3/E4/E5.

## RULE_CONFIRMATION

The return and final audit positively confirm:

- `CDA-QADD-A-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`;
- `CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001`;
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`;
- `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`;
- `CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001`.

Claim boundary is QLinearAdd node0007 split-C plus package-local execution
integrity only.
