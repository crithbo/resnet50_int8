# QLinearAdd node0007 v36 hold → v37 root-clean runner-only release

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target/mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- result: `PACKAGE_READY_NOT_RUN`, `candidate_release=false`, `E2_LOCAL_ONLY`
- no server upload/run/lease; no plan/public-rule/functional-RTL modification

## Decision

The frozen v36 semantic package is held because its exact runner creates
`run_*`, `evidence_*` and return entries directly under the `NDP_copy0x`
root.  v37 is a fresh runner-only identity.  Config, workload, numeric,
golden, observer, 8-hour production timeout and functional RTL are frozen.

The v37 runner writes all private runtime state below the pre-existing
`install/` direct child, captures the root direct-child name/type exact set
before writes, compares it in the shared finalizer, and publishes the unique
return atomically to `/home/panqs/ndp/simresult`.

## Local blockers resolved

1. The first shortened projection was 242 characters against the 240-character
   local gate.  It was preserved as a failed candidate and the private
   namespace was shortened to `.qa.<pid>`, closing at the declared budget.
2. The first rebuilt v37 synchronized the SCA paths but retained the old
   package-local runtime prefix check.  That candidate was quarantined
   non-destructively.  The final v37 changes only the corresponding package
   validator namespace leaf.
3. A Windows/MSYS harness path bridge and signal-domain issue was isolated
   from production bytes.  Final controls use a bounded same-shell-PID normal
   EXIT unit, real runner compile-failure publication, and serial HUP/INT/TERM
   controls.  This avoids unbounded local waiting and cross-case signal
   contamination.

## Final immutable identities

- ZIP before storage rotation:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-v37-rootclean-package/r5_qadd_n7_cout32_rootclean_v37.zip`
  - bytes `26178383`
  - SHA256 `699696dcf59e1453669aa0af12c599963d05ed176f417858ddf2095fee4fcf87`
- sidecar SHA256:
  `271ed5d8551a44d3a2662183a8d8d412855f77a8b44d9131b4f6c9d0794017eb`
- final audit:
  - bytes `101371`
  - SHA256 `62a7352ec351f7f7df08e5879b295d9e5143d9e5d20afbf9b3fda005e618df68`
  - `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
  - `errors=0`
- HDL scope receipt:
  - bytes `45577`
  - SHA256 `b7c2e250e0292c8ae5cbeb3c59aa752695743a150ca2be85484d894946acae63`
  - compatible frontend exit `0`, actual consumers `26`, equivalence classes
    `12`, uncovered `0`, all declaration/use/update negatives fail closed
- deterministic build receipt:
  - bytes `1423`
  - SHA256 `4abe57dc17a9103c3e054efdc229f76f172518c13814c0fab789975db5f3572f`
- release machine report:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007/r5_qadd_n7_cout32_rootclean_v37/r5_qadd_n7_cout32_rootclean_v37_release_report.json`
  - bytes `6225`
  - SHA256 `902082a11322e39917f9cddf1ce3b5b2bcca5a7458969f72d74e3770a39f576e`

## Runner/finalizer controls

- bounded normal EXIT same-shell-PID unit: exit `0`, limit `5s`
- exact runner compile failure: exit `17`, return+sidecar+root receipt complete
- exact runner HUP/INT/TERM: exit `125` each, return+sidecar+root receipt complete
- fixed-result target conflict negative: exit `10`
- missing pre-existing `install/` parent negative: exit `12`
- root-level directory/file and ignored-drift direct guard negatives fail closed
- finalizer stderr has no shell diagnostics

The normal-control claim is deliberately narrow: it proves the exact runner
trap text has same-shell-PID EXIT semantics.  Exact package finalizer artifact
publication is exercised by compile-failure and each safe signal path.  The
production runner and 8-hour timeout remain unchanged.

## Server handoff

- pickup after rotation:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_cout32_rootclean_v37.zip`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected ZIP:
  `/home/panqs/ndp/simresult/r5_qadd_n7_cout32_rootclean_v37_return.zip`
- expected sidecar:
  `/home/panqs/ndp/simresult/r5_qadd_n7_cout32_rootclean_v37_return.zip.sha256`

Storage rotation completed without overwrite:

- QAdd pending exact set: `r5_qadd_n7_cout32_rootclean_v37`
- v36 pending absent and archived under
  `superseded/qlinearadd_node0007/r5_qadd_n7_cout32_v36/`
- `PACKAGE_STORAGE_INDEX.json`: bytes `116303`, SHA256
  `acb3df67213f96b690de683abdaf5eddf4c127156d4c91521100f14304fef46c`,
  `pass=true`

## Rule confirmation

No non-synonymous rule delta is needed.  The current root-top-level,
fixed-simresult atomic publication, final-ZIP self-audit and storage rotation
rules all fail closed at the intended boundaries.
