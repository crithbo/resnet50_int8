# Conv node0004 v21 diagnostic-feature rule revalidation and v22 successor

## Control boundary

- Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`.
- Current server rule:
  `fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025`.
- New rule:
  `CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`.
- `numeric_analysis_repeated=false`.
- `node0004_workload_rebuilt=false`.
- `configuration_rebuilt_in_this_successor=false`.
- No plan, public rule, functional RTL, frozen configuration, bitstream,
  execplan, SCA, matrix, golden, or other operator-family asset was changed.
- No server inspection, upload, lease, or execution was performed.

## V21 applicability adjudication

V21 was inspected directly from the final ZIP:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v21_bufkeep_fix.zip`
- SHA256:
  `bd9fadb9bdd18c1678461ae055fea7e15be5d414957b76de48f761833e345131`

The new rule is applicable. V21 relies on three independently runtime-gated
diagnostic features:

1. `RETURN_OBS_DEEP`, limit `RETURN_OBS_DEEP_LIMIT=256`;
2. `RETURN_OBS_ABPE`, bounded by
   `RETURN_HANG_DIAG_MAX_CYCLES=8388608`;
3. `RETURN_HANG_DIAG`, with sample cycles `262144`, stall windows `4`, and
   maximum cycles `8388608`.

The actual v21 runner already passed the enable and limit arguments, but its
manifest and returned contract only bound the generic observer marker. It did
not provide all of:

- a per-feature time-zero `enabled=true` marker with effective limits;
- a feature-specific returned binding receipt;
- an explicit receipt target in the return exact-set;
- the four feature-specific negative controls.

Consequently v21 cannot receive a content-neutral receipt. Its status is:

`QUARANTINED_RULE_DRIFT_FEATURE_BINDING_INCOMPLETE`.

## Minimal fresh successor

Only package-local diagnostic delivery changed:

- package-local observer emits one
  `DIAGNOSTIC_FEATURE_ENABLE_V1` time-zero marker for each feature;
- runtime binds actual simulator argv to those markers;
- finalizer always writes
  `evidence/diagnostic_feature_binding.json`;
- collector includes that receipt in `RETURN_ALLOWLIST.json`;
- result gate embeds the same binding receipt;
- manifest declares each feature, enable argument, limits/budget, marker,
  expected record schema, and return target.

The complete `workload/runtime` tree is byte-identical to v21 after only
normalizing the install-root identity from v22 back to v21. The 128-bit
bitstream remains:

`6996170d1c1c3c6b02b9a1980c612c2b207255f2bb1f7fe5e202709acf3ea55b`.

## Positive controls

Compile-chain positive control:

- validator exit: `0`;
- safe compile-stub unique exit: `73`;
- compile invocation count: `1`;
- package/install/observer guard: PASS;
- report:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v22_featurebind.runner_positive_control.json`;
- report SHA256:
  `281bc90c570ea73730f6bde1a42f5031e7886827f27b8f6d35510e46d7bfcec1`.

Feature end-to-end positive control:

- validator exit: `0`;
- safe simulator-stub unique exit: `74`;
- actual simulator argv contained every feature enable and effective limit;
- all three time-zero markers were observed exactly once;
- `diagnostic_feature_binding.json` reported all three features valid;
- simulator argv, observer record, feature receipt, result gate, and local
  return sidecar were all returned through the exact allowlist;
- report:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v22_featurebind.feature_positive_control.json`;
- report SHA256:
  `454577f9d9c6b28450cc02b6f420cc939371f0e284d1718083bfd842f23eddc5`.

## Final ZIP self-audit

Post-generation rules were read completely and current-matched:

- index:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`;
- server rule:
  `fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025`;
- INT8-SA:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`;
- hardware entry:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`.

Final validator:

- `tools/validate_node0004_v22_final_zip.py`;
- SHA256:
  `6dcbb72069f327ae2aaef22d47d75760edba652355bb5972dbd711fb9de42686`;
- exit: `0`;
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`;
- `errors=0`.

Required feature negative controls all failed closed with expected/observed
exit `1/1`:

1. delete feature enable;
2. delete or tamper feature limit;
3. delete time-zero marker contract;
4. delete feature return target.

Final audit report:

- `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v22_featurebind.final_zip_rule_self_audit.json`;
- SHA256:
  `54ea04d3ee63b523c018da2dec184c83683921a7daf12e2478370b01d883e1a7`.

## PACKAGE_RELEASE

- status: `PACKAGE_READY_NOT_RUN`;
- unique identity:
  `r5_n4_hw_v22_featurebind.zip`;
- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v22_featurebind.zip`;
- bytes: `5821119`;
- SHA256:
  `caf96850ceb5dcf66233dd736757bb2e0b3fbb3b63b066dc9c0194022f1ac68b`;
- sidecar SHA256:
  `de6fd640cbad1d82c31b84a6b3d4d4c71c465f318c1204ecf742adb3068b7275`;
- command:
  `bash r5_n4_hw_v22_featurebind/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`;
- expected return:
  `r5_n4_hw_v22_featurebind_return.zip`.

The server runner still creates a local return sidecar. User upload of that
return sidecar is optional under the current transport rule.

## BLOCKER_DELTA

- Closed locally: package-side per-feature runtime enable/limit/marker/receipt
  and return binding.
- Still open: v22 has not run on the server; natural terminal and 320-item
  exact formal D remain required before E3/E4/E5.

## RULE_DELTA_PROPOSAL

`NONE`.
