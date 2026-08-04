# QLinearAdd node0007 B-control v24 rulefix release

## Provenance

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return/mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- machine report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-b-dequant-control-rulefix-v24/release_report.json`
- machine report bytes/SHA256:
  `7165` /
  `cbe9f237f3f209a74772a16c6cc6c30aaa8b9d3b4a9f1eb7e76dd1f9d1f6195d`
- numeric/W3/qparams/tail/workload/config/golden repeated: `false`
- functional RTL modified: `false`
- server uploaded/run/inspected: `false`

## Mainline rejection accepted

v22 is quarantined. Its B-only control construction and the v20 return
analysis remain valid, but its release audit overclaimed:

1. the final audit did not contain
   `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`
   evidence for its two package-local HDL members;
2. the safe compile-stub path emitted three missing-file `grep` diagnostics
   on stderr.

The intermediate v23 added finalizer existence guards and the HDL gate.
It is also quarantined because its compile-stub return still declared
`sim.log`, simulator argv and observer log missing in addition to the
expected 28 formal D targets.

## Fresh v24 correction

v24 preserves the B-only execution, v18 base observer, original B input,
hardware-produced B scratch, heartbeat, timeout and all numeric/config/RTL
bytes. Package changes are limited to:

- finalizer existence guards inherited from v23;
- fail-closed canonical output when the observer log does not yet exist;
- explicit pre-compile `NOT_STARTED_COMPILE_NOT_PASSED` receipts for
  `sim.log`, simulator argv and observer log. A real simulation overwrites
  these paths.

## Package-local HDL gate

`package_local_hdl_gate.valid=true`.

Exact final-ZIP members:

- `tb_probe/native_return_observer.svh`, bytes `111892`,
  SHA256
  `1ce787ad557dca670c4f13a0c56b659fc1b35527f6d6f1f911e07f0df2a95562`;
- `tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh`,
  bytes `27805`, SHA256
  `97be2ee75e4b183960329d45a827799939c7205d7aa7dbd3b0cd047eceec3da8`.

Icarus Verilog `12.0 (devel)`:

- exact-member include preprocessing exit: `0`;
- focused syntax/scope/name-resolution exit: `0`;
- `return_obs_` declaration/use closure: `120/120`, unresolved `0`;
- `qadd_fr_` declaration/use closure: `34/34`, unresolved `0`;
- delete declaration negative exit: `1`;
- misspell consumer use negative exit: `1`;
- delete qualified update negative exit: `1`.

The focused claim covers the required base request counter and
first-request enqueue state leaves. Production VCS remains the final
full-design elaboration evidence.

## Runner/finalizer controls

- safe compile-stub reached compile and returned expected exit `86`;
- stderr is exactly empty;
- all required finalizer evidence is present;
- return ZIP and sidecar are present;
- `RETURN_MANIFEST.required_missing` contains exactly the 28 formal D
  readbacks and nothing else;
- wrong-identity negative exits `5` before compile;
- safe EXIT and TERM simulation-stub controls both return expected `125`,
  collect the return, and have empty stderr.

## PACKAGE_RELEASE

`PACKAGE_READY_NOT_RUN`,
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`,
`candidate_release=false`, `E2_LOCAL_ONLY`.

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_bctrl_v24.zip`
- bytes/SHA256:
  `38032104` /
  `71e14695c3025340987dba2fc0ffedd23e8e61d9bcb6eaec704de74c8e6928da`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_bctrl_v24.zip.sha256`
- sidecar bytes/SHA256:
  `91` /
  `93ad51474ee5e566249ae3b3aab8f4f1baa1f80f5e360a663558f20948936300`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  `r5_qadd_n7_bctrl_v24_return.zip`

Two deterministic builds produced the same ZIP SHA.

Final audit:

- path:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-b-dequant-control-rulefix-v24/final_zip_self_audit.json`
- bytes/SHA256:
  `18388` /
  `9d2603782314be5eb1fe8d4be43c45ecb783c3d9b1897abd135bb978be353a96`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`

Build receipt:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_bctrl_v24.validation.json`
- bytes/SHA256:
  `1193` /
  `13261c91897083cd7681681c0771d8c8b86c298ae76a78a924d6803174da7cca`

## BLOCKER_DELTA

Closed:

- `B_QADD_V22_FINAL_ZIP_HDL_GATE_MISSING`;
- `B_QADD_V22_COMPILE_STUB_FINALIZER_STDERR_DIAGNOSTICS`;
- `B_QADD_V23_COMPILE_STUB_RETURN_REQUIRED_PLACEHOLDERS_ABSENT`.

Kept open:

- `B_QADD_V20_PACKAGE_LOCAL_FP32_OBSERVER_EVENT_STORM_SUSPECT`;
- `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`.

## RULE_CONFIRMATION

`CURRENT_RULES_CONFIRMED_EFFECTIVE`.

The v22 escape was correctly rejected by:

- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`;
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`.

V24 now supplies the exact positive/negative evidence those rules require;
no public-rule delta is proposed.
