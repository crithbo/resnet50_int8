# family.conv.native current-package binding: p46 native flow

Date: 2026-08-13 (Asia/Shanghai)

## Pointer identity

- family storage key: `conv_native_four_lane`
- role_id: `family.conv.native`
- owner_epoch: `2`
- registry_epoch: `6`
- exact package base: `r5_n4_0cc_p46_nativeflow`
- status: `PACKAGE_READY_NOT_RUN`
- activation epoch: `runtime-preflight-native-flow-v1`

This native-owned record exists to bind the exact current pending package to the
`*conv_native_four_lane*.md` discovery contract used by
`current-family-pointer-v1`. The complete construction, gate, storage, command,
and claim-boundary record remains:

`.agents/task_records/20260813_conv_native_p46_nativeflow_package_ready_not_run.md`

## Exact package and release evidence

- pending ZIP:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p46_nativeflow.zip`
  - bytes: `5979948`
  - SHA-256: `6a648613492d66b244564a0acc8f7d59709a971cf2c84d47c4922fe040f61478`
- final ZIP audit:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/r5_n4_0cc_p46_nativeflow.final_zip_audit.json`
  - bytes: `6326`
  - SHA-256: `a801c8525f02e4313457aedfcd764efdff9d649410281cc4a76231208ae66fc0`

The exact identities above were rechecked after QAdd v62 publication. Corrected
global storage audit is PASS and identifies exactly one native pending package:
`pending_by_family.conv_native_four_lane = ["r5_n4_0cc_p46_nativeflow"]`.

## Previous progress and current purpose

Previous-version progress: p41 passed production compile beyond the Datahub
repair; p42 fixed the two-bit vector valid/ready scalar false-negative; p45
attempted broad observer-only localization but production compile failed at
unresolved `DW_ecc`, `DW_sync`, `DW_lod`, and `DW_fifo_s1_sf` before simulation.

Current-version purpose: p46 preserves the corrected p42-equivalent MSE4
wdata/slice-finish diagnostic, enters the native production path without
provider preflight, and returns exact native-flow compile/simulation/observer
evidence including actual compile argv, observer `SIM_EXIT`, `COMPILE_CORE`, and
the exact core manifest.

## Frozen surface and authority boundary

- frozen: config, numeric, workload, golden, functional RTL, and target diagnostic;
- dump values: `DUMP_VCD=0`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0`;
- tested p45 and pending p46 package bytes are unchanged by this pointer repair;
- no package/storage/plan/rule/registry mutation is performed by this record;
- no upload, run, lease, connection, or other server action occurred.

The only future package command, if separately authorized, remains:

`bash r5_n4_0cc_p46_nativeflow/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

Claim boundary: this is a current-family-pointer task-record binding only. It
does not add any production compile, DUT simulation, natural terminal, formal D,
E3, E4, or E5 claim.
