# GAP node0071 v12 formal return adjudication and v13 narrow diagnostic release

## Scope and receipts

- Family: QLinearGlobalAveragePool node0071.
- Source package:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v12_minruntime.zip`
  SHA256
  `a1e149e7e4a20cd254e84a8fd7199607beeafb11fd71cfe4d548226825b06d06`.
- Return:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n71_gap_v12_minruntime_return.zip`,
  bytes `77578`, SHA256
  `a820abcbbb99dd468de1cdc42f4389780cb5c0fdc9ecf0f16a0f713c46b65c2d`.
- Direct adjacent `.zip.sha256` is absent. Formal file receipt is fail-closed;
  internal ZIP evidence was still parsed read-only.
- Current rule receipts:
  index `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`;
  common operator `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`;
  NDP fields `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`;
  server `507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`;
  GAP int32 `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`;
  GAP dynamic `4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf`;
  exact tail `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`.
- Plan SHA
  `0e3ec9d2346f9ff9561456cc1c9fb2653385214009a2eaeea46f731c85fc5183`
  is mutable provenance only.

## RETURN_ANALYSIS

The ZIP has valid CRC/path safety, one root, 23 exact allowlisted entries, no
duplicate, missing, extra, size or hash mismatch. Returned package manifest
and SCA/SCA_D copies bind exactly to source v12. Package/install/observer
preflight and observer four-way binding pass.

Compile completed with status 0. Simulation and runner exited 125 under
`SIGINT`; no natural terminal occurred. Observer output continued growing
until 16.142 seconds before interruption, and simulation time advanced to
26,774,045,625 ps, so this is not an observer-silent or simulation-time-frozen
case. Qualified functional progress nevertheless remained flat for
20,447,232 cycles, exactly 19.5 configured stall windows. The unique complete
canonical decision is `LONG_RUNNING_HANG_AT_ANY_MSE_READ_DATA_ACCEPTED`.

All 48 formal D targets are missing. `mismatch=0` is unevaluable. The result
conjunction fails; E3, E4 and E5 are all false.

## FIRST_DIVERGENCE and HANG_ROOT_CAUSE

Formal receipt first divergence:
`DIRECT_ADJACENT_RETURN_SIDECAR_ABSENT`.

The internally coherent qualified data refines the functional boundary:

```text
MSE0 -> Buffer0 accepted once
MSE3 -> Buffer4 accepted once
-> GA operand0 capture = 0
-> GA operand2 capture = 0
-> GA joint accept/output/MSE4 write-data/terminal/formal D absent
```

Therefore the last good boundary is
`MSE0_TO_BUFFER0_ACCEPTED_AND_MSE3_TO_BUFFER4_ACCEPTED`; the first absent
boundary is `ANY_GA_OPERAND0_OR_OPERAND2_INBUFFER_CAPTURE`.

No deterministic package, configuration, or functional RTL error can be
assigned from v12 because the intermediate Buffer ARM read, GA group ingress,
and PE operand-tag boundaries are not separately returned. Root-cause status
is
`LONG_RUNNING_HANG_AT_BUFFER_TO_GA_INGRESS_PENDING_NARROW_BOUNDARY`.
The prior exhaustive local static audit was consumed, not rerun:
`outputs/gap_node0071_v9_local_reaudit/local_exhaustive_reaudit_report.json`,
SHA256
`bf86b2f11041c3d758ae7ee8f8f0e5893fd27f1b968648be0ca1f042df6b3d6b`.

## BLOCKER_DELTA

- Closed: `READ_STREAM3_PATH_UNOBSERVED`.
- Refined:
  `LONG_RUNNING_HANG_AT_ANY_MSE_READ_DATA_ACCEPTED` to
  `BOTH_PRODUCER_TO_BUFFER_ACCEPTED_TO_ANY_GA_INBUFFER_CAPTURE_ABSENT`.
- Open:
  `DIRECT_ADJACENT_RETURN_SIDECAR_ABSENT`,
  `BUFFER0_4_ARM_READ_ACCEPT_TO_GA_GROUP0_2_INGRESS_ACCEPT_TO_PE_OPERAND_TAG_VISIBILITY`,
  `NATURAL_TERMINAL_ABSENT`, and `FORMAL_D_48_OF_48_MISSING`.

## RULE_DELTA_PROPOSAL

Proposal-only:
`CDA-GAP-BUFFER-TO-GA-INGRESS-BOUNDARY-OBSERVABILITY-001`.
After both producer-to-buffer acceptances are proven while GA operand
captures remain zero, return qualified Buffer ARM read accepts and qualified
GA group ingress accepts separately, plus raw PE operand-tag/backpressure
state. Raw levels remain state only. Source-clock counters must be snapshotted
from the independent observer clock together with source edge and last-change
witnesses.

No public rule was modified by this task.

## PACKAGE_RELEASE

One narrow successor was generated because v12 lacks exactly the necessary
Buffer-to-GA boundary:

- Identity: `r5_n71_gap_v13_buffer_to_ga_diag`.
- Claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.
- Status: `PACKAGE_READY_NOT_RUN`.
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v13_buffer_to_ga_diag.zip`.
- ZIP bytes: `1796539`.
- ZIP SHA256:
  `88715902dd818b488990521bcdfa9d9be24f3195e0371c9c25a664a17fc76131`.
- Sidecar SHA256:
  `edd5766863f4cfc156a36ca4714693c66ae681ee7afaa190696c5be48ff9b387`.
- Observer SHA256:
  `c6ae0bbd7f2cbe40c5ba47608b8ffb2c4123f58c5ce7ebe9e92f3dce8fb87c59`.
- Final self-audit:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v13_buffer_to_ga_diag.final_zip_rule_self_audit.json`,
  SHA256
  `096f410a38d32455cc9a3509029a7f1fda523c6b902daea41c0f6c11a93779e7`.
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors `0`.
- All validator and negative-control commands exited 0 at the audit layer;
  the safe compile stub positive control reached make and exited 86;
  wrong-identity full-run control exited 5 before compile.
- Server command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`.
- Expected return:
  `r5_n71_gap_v13_buffer_to_ga_diag_return.zip` and its directly adjacent
  `.zip.sha256`.

The 73 frozen numeric workload files are byte-identical to v12. Sum/tail
numeric analysis, workload, configuration and golden were not repeated or
rebuilt. Functional RTL was not modified; no server inspection, upload, run
or lease occurred.

Machine report:
`artifacts/operator_config_validation/r5-gap-node0071-v12-return-analysis/report.json`,
SHA256
`a129f6c03cb469bc29d916247c83273d001d313184d19b3fb1f9d63b87a8e619`.
