# Conv node0004 v22 corrected successor v23 final-release diagnostic

## Scope and provenance

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- server action: none
- functional RTL, public rules and `.agents/plan.md`: unchanged

No node0004 numeric/W3/qparam/tail analysis was repeated. The frozen workload,
configuration, bitstream, execplan/SCA and golden were not rebuilt. Timeout and
backpressure behavior were not changed.

## Occupancy adjudication invalidation

The current correction receipts were consumed:

- correction task record SHA256:
  `0eaa10c0e7f97daf3c0765fdea83489733f9061a2749b548654bd65b3a781cb2`
- correction machine report SHA256:
  `2369d9eb4976b67d54a34b5eacfb1e24877b3a2a7000d29967ab082a3d960b8c`

The following are withdrawn and must not be revived:

- `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`
- `WAIT_RTL_FIX`
- `delta=4*initial_accept+1*alu_accept-1*output_read_accept`

Correct semantics: the initial write establishes four live psum/output slots;
`alu2ob_wr_ptr` replaces an existing live slot; a final output read retires one
slot. The old Python 4/4 occupancy model was not used as a positive control.

## Corrected v22 return boundary

The frozen v22 return evidence remains:

- compile/run exits: `0/0`
- natural terminal: false
- formal D: `0/320`, missing `320`
- A/B/C group accepts: `16/16/8`
- per-PE ALU accepts: `2048`
- `alu2ob` write cycles: `32`
- PE output, SA group output and Buffer5 write: `0/0/0`

Corrected adjudication:

- `LAST_PROVEN_GOOD=SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE`
- `FIRST_DIVERGENCE=SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID`
- open blocker:
  `B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED`
- RTL defect classification: `NOT_YET_PROVEN`

Static source evidence did not uniquely distinguish terminal/tag mismatch,
ping-pong/pointer misalignment and an RTL final-release leaf. A narrow
diagnostic successor was therefore required.

## v23 observer coverage

The package adds runtime-gated `RETURN_OBS_FINAL_RELEASE`, with a 256-record
limit. It returns:

- input last/index and matched/out;
- ALU last/matched and `alu2ob_wr_handshake`;
- `ob_out_rd_ready` set/clear;
- initial/ob2alu/alu2ob/outport ping-pong selectors;
- initial/ob2alu/alu2ob/output pointer changes and wrap;
- first PE output valid/accept;
- first SA group output accept and Buffer5 write edge.

`outbuffer_group_count` and `outbuffer_group_empty` are state-only
corroboration and never count as monotonic progress.

## Current-rule post-generation receipt

- `.agents/rules/生成前必读索引.md`
  SHA256 `f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8`
- `.agents/rules/服务器测试包生成规则.md`
  SHA256 `7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141`
- `.agents/rules/INT8_SA点积专项规则.md`
  SHA256 `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  SHA256 `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

The complete files were reread after package generation. All current matches
passed.

## Validation

- deterministic double build: PASS
- runner feature control validator: exit `0`
- safe compile/simulator stub runner exit: expected `74`
- safe TERM finalizer runner exit: expected `143`, partial evidence retained
- final ZIP validator: exit `0`
- unit tests: `3/3 PASS`, exit `0`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- audit errors: `0`

All package-binding and feature negatives failed closed with observed exit `1`:
source deletion, `+incdir` deletion, enable macro deletion, runtime enable
deletion, limit deletion, time-zero marker deletion, return-target deletion,
and wrong observer identity. Canonical decision negatives also passed:
summary-only append, conflicting decisions, missing reason, missing boundary
and level-only pseudo-progress.

## Package release

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v23_final_release_diag.zip`
- bytes: `5826256`
- SHA256:
  `9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27`
- sidecar SHA256:
  `6050f268a34b6902c011a159f94ae8a2299f607a1efc253bcb5151ec9b3706c7`
- status: `PACKAGE_READY_NOT_RUN`
- command:
  `bash r5_n4_hw_v23_final_release_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return: `r5_n4_hw_v23_final_release_diag_return.zip`

This is a diagnostic package, not a functional repair and not an E3/E4/E5
claim.

## Machine assets

- contract:
  `contracts/operator_config/node0004_v22_corrected_return_reanalysis_v23_final_release_diag_v1.json`
  SHA256 `bfd7696a88e8d8385c8e9371f76cfc02e021d91008aff4e9fbae9179e3821eaa`
- report:
  `outputs/conv_node0004_v22_corrected_successor_v23/report.json`
  bytes `6048`, SHA256
  `8a6316151404c32d58a24facfda7f89a29fa4c603e485be742e321e14a1014de`
- final ZIP audit:
  `artifacts/operator_config_validation/r5-node0004-v23-final-release-diagnostic/final_zip_rule_self_audit.json`
  SHA256 `efc93ac9d62727e9f95590c6242cf71ce2d4324928130603dfd09161db279cfe`
- runner controls:
  `artifacts/operator_config_validation/r5-node0004-v23-final-release-diagnostic/runner_feature_controls.json`
  SHA256 `89f2207af518b15fa3ae5e9111dc91673ca96a1b82a7708f605cb9f9cbc4e2d3`
