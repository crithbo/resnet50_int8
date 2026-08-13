# QLinearAdd node0007 v36 formal return analysis

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PARTIAL_INTERRUPTED_EXTERNAL_SIGHUP_BEFORE_TARGET_STAGE`
- numeric/W3/qparams/tail/workload/config/golden repeated: `false`
- package/config/functional RTL changed: `false`

## Receipt and identity

The submitted return is:

`C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_qadd_n7_cout32_v36_return.zip`

- bytes: `161996`
- SHA256:
  `ec11d21241650ecf61e5aab6125ba622a9d49f65e989bace5e709358c2ed6136`
- adjacent sidecar: absent, accepted only under
  `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`

The frozen source remains:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_cout32_v36.zip`

- bytes: `26181302`
- SHA256:
  `b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382`

Return CRC, single root, path safety, duplicate/symlink checks, manifest
exact-set and all per-file size/SHA checks pass. The returned
`PACKAGE_MANIFEST.json` is byte-equal to the source ZIP's
`TEST_PACKAGE_MANIFEST.json`:

- bytes: `81514`
- SHA256:
  `7b39bc965034f8dd0db52e624e650b2b85b29827710a248f8ba2b03b6921a97d`

Package/install preflight pass and all 28 runtime D targets were absent before
simulation.

## Execution classification

Production VCS compile/elaboration passed:

- compile exit: `0`
- VCS: `V-2023.12-SP2`
- elaboration: `0 errors`, `1 warning`

Simulation did not reach natural terminal:

- simulation/runner exit: `125/125`
- signal: `HUP`
- configured timeout: `8h`
- simulation wall time: `5297.817287134 s` (`01:28:17.817`)
- timeout reached: `false`

The simulator log explicitly records `Received SIGHUP (signal 1), exiting`.
The common finalizer still produced a valid partial allowlist return. This is
an external interruption, not a natural DUT terminal and not a runner timeout.

## Qualified progress and target scope

The ordered split-C prefix is:

1. `op_a_dequant`
2. `op_b_dequant`
3. `op_relocation_pad`
4. `op_fp32_add`

Only the first stage was reached. It produced `CFG_START`, `CFG_FINISH`,
`EXEC_START`, slice start, and qualified request/data/GA/MSE activity. Returned
limited counts include 64 GA input events, 64 GA output events, 128 selected
MSE4 requests and 128 selected MSE4 write-data events.

`LAST_PROVEN_GOOD` is
`OP_A_DEQUANT_STAGE0_QUALIFIED_MSE4_WDATA_ACTIVITY`.

The target `op_fp32_add` stage was not reached. Therefore the observed
stage-0 GA/MSE activity must not be rebound to the v36 changed target:
8-lane/32-byte `op_fp32_add` GA output, Buffer5 accepted row and selected MSE
write-data remain dynamically unevaluated.

The deep observer reached its declared event limit before its first heartbeat
or a complete `1048576`-cycle stall window. The canonical record therefore
reports `PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE` with
`expected stage_seq=4, observed None`. That proves only that the final target
stage was not observed; it does not prove a DUT hang. At the external HUP
boundary, neither continuing progress nor a qualified stall is mechanically
decidable.

## Result gate

- natural terminal: `false`
- target split-C terminal: not reached
- formal D expected/present/missing: `28/0/28`
- invalid: `0`
- reported mismatch bytes: `0`
- mismatch evaluable: `false`
- `SERVER_RESULT_GATE`: `false`
- E3/E4/E5: `false/false/false`

Missing D and reported mismatch zero are consequences of interruption before
the target stage and are not a numeric, configuration or functional RTL
failure.

`FIRST_DIVERGENCE` is
`EXTERNAL_SIGHUP_BEFORE_OP_A_DEQUANT_COMP_FINISH_AND_BEFORE_OP_FP32_ADD`.

`HANG_ROOT_CAUSE` is
`NOT_ESTABLISHED_EXTERNAL_SIGHUP_BEFORE_STALL_WINDOW_EVALUABLE`.

## Blocker and release

Closed:

- return transport/source/package/install identity;
- production compile and actual observer runtime binding.

Unchanged:

- v36 `op_fp32_add` 32-byte dynamic acceptance;
- split-C natural terminal;
- 28-D exact readback.

No config, functional RTL or numeric mismatch blocker is opened.

The evidence-preserving action is to rerun the exact frozen v36 package from a
fresh server namespace:

```text
bash PREPARE_AND_RUN.sh /absolute/path/to/fresh/NDP_copyXX
```

Expected return remains `r5_qadd_n7_cout32_v36_return.zip`.

`PACKAGE_RELEASE=PACKAGE_RERUN_READY_SAME_FROZEN_IDENTITY`. The ZIP remains
byte-for-byte unchanged and is still the single QLinearAdd ZIP in the flat
pending pickup directory. No fresh successor was released, so storage
rotation is not triggered yet. Any later fresh successor must publish its
return atomically under `/home/panqs/ndp/simresult` and satisfy
`CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`; that rule is not
retroactive to frozen v36. This is a server-runtime-only absolute path. The
local analysis did not create, map or write it; local future-package audit may
only validate exact-runner logic through an isolated harness namespace.

## Rule feedback

`RULE_CONFIRMATION`: the current no-sidecar transport, interruption-first
classification, qualified progress, result conjunction, cloud-RTL
nonblocking identity and storage-rotation rules correctly prevent this
partial return from being misclassified as a configuration, RTL or numeric
failure. No non-synonymous QAdd rule delta is supported by this return.

Machine report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-v36-return-analysis/report.json`.

- bytes: `12188`
- SHA256:
  `0ad6298494854d4ece3761fe847e1918575fd80207270c0a54c56507d99b50c1`
