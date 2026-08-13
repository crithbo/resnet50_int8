# Native Conv p43 formal-return tested storage lifecycle

Date: 2026-08-12 (Asia/Shanghai)

## Ownership and authorization

- `role_id`: `family.conv.native`
- `owner_thread_id`: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- `owner_epoch`: `2`
- `registry_epoch`: `6`
- `current_mainline_thread_id`: `019ff027-e7db-72a3-b282-cfad8708da05`
- dispatch: `MAINLINE_STORAGE_LIFECYCLE_CORRECTION / NATIVE P43 FORMAL RETURN CONSUMED`
- operation scope: storage lifecycle only.
- server action: none; no upload, run, lease, or server connection occurred.
- no successor was built, no shared tool was patched, and no plan/rule/registry/config/numeric/workload/golden/functional-RTL file was changed.

## Previous progress and current purpose

Previous-version progress: p41 proved production compile beyond the Datahub public-surface repair. p42 corrected the package-local two-bit valid/ready scalar-comparison false negative while retaining the MSE4 wdata/slice-finish target.

Current-version purpose: p43 preserved that corrected diagnostic and attempted same-run raw VPD, direct VCD, and complete source-bound query/event evidence. Its consumed formal return proves a shared portable-method time-0 runtime escape and remains `DIAGNOSTIC_EVIDENCE_INCOMPLETE` for the MSE4 target.

## Atomic lifecycle operation

The family storage manager was invoked with:

- command: `retire-pending`
- family: `conv_native_four_lane`
- package base: `r5_n4_0cc_p43_portablevq`
- disposition: `tested`
- reason: `FORMAL_RETURN_CONSUMED_SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE_DIAGNOSTIC_EVIDENCE_INCOMPLETE_SUCCESSOR_HOLD`
- evidence: `outputs/conv_native_four_lane_0ccae916_p43_return_analysis/report.json`

Read-only prechecks proved:

- p43 was the exact and only `conv_native_four_lane` pending package;
- the pending ZIP and receipt directory existed;
- neither tested nor superseded contained the p43 package identity;
- the formal return analysis was present and identity-valid;
- the pre-rotation global storage audit passed.

The manager moved the flat pending ZIP and all 19 pending receipts as one non-overwriting package set into:

`artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p43_portablevq/`

The old pending ZIP and pending receipt directory are absent after the move. No package or receipt bytes were rewritten or deleted; all 20 files are recoverably preserved in the tested archive.

## Preserved exact identities

| Relative path under tested package directory | Bytes | SHA-256 |
| --- | ---: | --- |
| `r5_n4_0cc_p43_portablevq.build.json` | 2726 | `e75ad08c581e014f6aac90e979c4713ee0bc882bf18412727cc4f1531f325760` |
| `r5_n4_0cc_p43_portablevq.compile_core_harness.json` | 2518 | `b119388b5ef71222c8d2b7c643d7059a7d60c7aeede2b7be2d6b3aca272f4aa5` |
| `r5_n4_0cc_p43_portablevq.compile_core_layout.json` | 543 | `461b3ee804d26fd51da8daec9f6082ddc1ffa0b1d6f6d3991f4f8ad6b407612d` |
| `r5_n4_0cc_p43_portablevq.final_zip_audit.json` | 6211 | `7b1f3e2712bc79276eabf169a45d0aba7bfc502127d26459155c34a3cf7c24c8` |
| `r5_n4_0cc_p43_portablevq.first_fresh_contract.json` | 2994 | `3ea60cbeebc88efbc43967d146a7e9777ef3bab7e975be13666a160480920e60` |
| `r5_n4_0cc_p43_portablevq.first_fresh_validation.json` | 2460 | `9dc56d787bdbced4957688c2e4e09a86fc36bcd1f7d0443138c805be6a9a4d06` |
| `r5_n4_0cc_p43_portablevq.observer_public_surface.json` | 1888 | `8309b7f0aecf760b34998528219eae4405d5066e2a7a90836d889e00da925a51` |
| `r5_n4_0cc_p43_portablevq.portable_query.json` | 598 | `e0bb4c057e0391d0e5c3e0048a155495837016333537cabda85206361ca28c86` |
| `r5_n4_0cc_p43_portablevq.portable_runtime_fixture.json` | 1631 | `d0dfeb8abae5e951770ad4c19854b999dbb688cb2f809dc32f7cf24109e0160b` |
| `r5_n4_0cc_p43_portablevq.post_sim.json` | 3033 | `db4b6fe434bdc4528bda9cc390f617b490ff5c45dba203305a9c318789aebd08` |
| `r5_n4_0cc_p43_portablevq.runner_harness.json` | 9647 | `22ba6cc0b9635637c7c6c91c67c57b2d4773f8c98405592c5a77bc6432f2c24b` |
| `r5_n4_0cc_p43_portablevq.runner_harness.progress.json` | 75 | `879e843e12604677075552b4dd1957aea6db10b3acf89bf810a9c85837c9b8a6` |
| `r5_n4_0cc_p43_portablevq.runner_harness.stack.txt` | 7869 | `da6457ccd302ee3716e7575b38bb731f2e8533fb4b804d2dfb9a3432fbf1cb2c` |
| `r5_n4_0cc_p43_portablevq.runner_return_resilience.json` | 1841 | `09956cc52d9b4305a213fdc7dfaa7dfa4aee8c9e8e3dc32591b60bff360899e1` |
| `r5_n4_0cc_p43_portablevq.shared_layout.json` | 27447 | `a30f36f5963f36204a293810f6c48ec6d5ea260dc7b259604d0bc1d2d837e9cd` |
| `r5_n4_0cc_p43_portablevq.source_bound_final_zip.json` | 120331 | `30f51fe46bdfdb3111461e5431fb2a0176446e175716f1768f7b585b722c8d4c` |
| `r5_n4_0cc_p43_portablevq.vector_join_predicate.json` | 547 | `25d389fcc56746a21654f8ab3070a8101e4f2df09b1c8541eda464b7f749da68` |
| `r5_n4_0cc_p43_portablevq.waveform.json` | 410 | `ddc0edf63ecb1fc60ca0e179d18f2025b8c988774e663a447cc0698849c7c28a` |
| `r5_n4_0cc_p43_portablevq.zip` | 6016442 | `657767774ef6762f4e93c3c0b23da71895c7ec699837ca443b0210457d55c11c` |
| `r5_n4_0cc_p43_portablevq.zip.sha256` | 95 | `8d6f61f6c252888c73ca2dfe18171d1a586286e284380d91992e009a47501ab6` |

## Formal runtime-escape binding

- formal return preserved unchanged:
  - path: `C:/Users/15383/Downloads/r5_n4_0cc_p43_portablevq_r1786512367639483307_1421638_return.zip`
  - bytes: `8098284`
  - SHA-256: `c26fdc4c191cbaa2fec244fe8fd9c1629d77fc1807186e7089324529ebccb095`
- formal analysis bound by the storage index:
  - path: `outputs/conv_native_four_lane_0ccae916_p43_return_analysis/report.json`
  - bytes: `28801`
  - SHA-256: `6728e8dc817941e6c329232fded8c2b98e1d9deea45bf80d3381eae58b34d85f`
  - status: `RETURN_ANALYSIS_COMPLETE_SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE_SUCCESSOR_HOLD`
- task record for that analysis:
  - path: `.agents/task_records/20260812_conv_native_four_lane_p43_return_shared_portable_runtime_escape_hold.md`
  - bytes: `9042`
  - SHA-256: `75ec4984a2c652f611b1f126023e8052a39231f38f4c07cabe2deeab51dd3e4e`

The tested index entry binds the formal analysis path and SHA-256 above and records the runtime-escape reason. This storage move does not upgrade the result: production compile passed, but the shared direct-VCD Tcl failed at time 0, direct VCD/query evidence was incomplete, natural terminal/formal-D/E3/E4/E5 remain false, and the MSE4 root remains unresolved.

## Corrected global storage audit

An independent post-rotation `manage_server_test_package_storage.py audit` completed with exit code 0 and:

- `pass=true`
- pending: `0`
- tested: `120`
- superseded: `48`
- `pending_by_family={}`
- p43 disposition: `tested`
- p43 archived file count: `20`
- pending p43 ZIP exists: `false`
- pending p43 receipt directory exists: `false`
- storage index:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
  - bytes: `458119`
  - SHA-256: `53ea7098c37ce5022ab3bdad97cbbdaa76fb14ec0fa537a3a59d5e49e14fd8de`

## Terminal state and next action

Final status: `STORAGE_LIFECYCLE_COMPLETE`.

Native Conv now intentionally has no pending package. Do not build a successor until exact activation of `CURRENT_DISK_PORTABLE_METHOD_RUNTIME_FIX_READY`. The first permitted family action after that activation is to reread the corrected shared method/rule/dispatch/gates and build the narrowest fresh p43-equivalent identity while preserving the frozen target and all non-waveform surfaces.
