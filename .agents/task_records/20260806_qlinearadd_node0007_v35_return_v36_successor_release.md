# QLinearAdd node0007 v35 return -> v36 successor release

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN`
- evidence: `E2_LOCAL_ONLY`
- claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- candidate release: `false`
- server action: `false`

## Minimal correction

Only `op_fp32_add` GA output population changes. `PE10`, `PE12`, `PE30`, and
`PE32` are added from the trusted native FP32-add config so eight unique
4-byte lanes provide exactly one 32-byte Buffer5 row. The input row-pair
configuration, addresses, workload, observer, timeout, numeric/W3/qparams,
exact tail, golden, and functional RTL remain frozen.

The changed-slice causal ledger proves producer byte-set `[0,32)` equals the
eight-bank Buffer5 required set. Boundary microtrace accepts only 32 bytes;
seven delete/duplicate/narrow-bank/16-byte-stream controls fail closed. Fresh
mapping and execplan were built from empty state. The 61 meaningful 64-bit
config words occupy 31 128-bit transport rows with one classified high-half
padding slot.

## Package identity

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_cout32_v36.zip`
- bytes: `26181302`
- SHA256: `b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_cout32_v36.zip.sha256`
- sidecar SHA256:
  `6c432813261067470a7e12587ddb72f0fc051d44fc0538126cc16c22eb624b59`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return: `r5_qadd_n7_cout32_v36_return.zip`

## Final direct-ZIP gates

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- errors: `0`
- final audit:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-output32-v36-server-package/final_zip_self_audit.json`
- final audit bytes/SHA256:
  `91226` /
  `948041a8b453e4da46d0f5be7dee77cc5cc653062e6f0a727f061394aa9ea535`
- exact-ZIP HDL receipt:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-output32-v36-server-package/hdl_scope_revalidation.json`
- HDL receipt bytes/SHA256:
  `45150` /
  `fec9a0d0d99f46a0fc4dc3279e3505565acb2eccf12052bfa340dc16e2ea89a4`

The exact final observer passed compatible-front-end syntax/name resolution,
26/26 actual consumer expression coverage with uncovered=0, plus declaration,
actual-use misspell, and qualified-update negatives. The final audit also
passes real runner to safe compile stub, EXIT/TERM finalizer, wrong identity,
feature/observer/parser, path-budget, runtime-D-absent, return exact-set, and
result-conjunction gates.

Release report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-output32-v36-server-package/release_report.json`.
Release report bytes/SHA256:
`7434` /
`6fd52c0bb1a6a9db36f4b29daf8e88e505540010a2c2f0aaee9e3bbadfcf08fd`.

## Rule feedback

`RULE_CONFIRMATION`: current changed-surface applicability, causal-ledger,
boundary-microtrace, cloud-RTL nonblocking identity, and completion-notify
rules behaved as intended.

`RULE_DELTA_PROPOSAL`:
`CDA-QADD-FP32-ADD-OUTPUT-BUFFER-ROW-SUPPLY-CONSERVATION-001` should require
the enabled GA lane byte-set to equal the selected output Buffer bank byte-set,
and bind it through accepted Buffer write and selected MSE write-data events.
GA event count or a partial output level is not an accepted Buffer row.
