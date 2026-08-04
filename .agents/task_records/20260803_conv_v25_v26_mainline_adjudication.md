# Conv node0004 v25→v26 主线裁决

- mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- date: `2026-08-03`
- action: receipt verification, rule-feedback adjudication, active plan/history update
- functional RTL modified: `false`
- server upload/run/lease: `false`

## Current read receipts

| Path | SHA256 | Reason |
|---|---|---|
| `.agents/agent.md` | `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721` | stable control boundary |
| `.agents/plan.md` before update | `ea465e54afb96968fdcb5c8d373f585ad94747a00a95796bbe860ddbc0246cb6` | current state before adjudication |
| `.agents/rules/生成前必读索引.md` | `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5` | routing |
| `.agents/rules/服务器测试包生成规则.md` | `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48` | return, successor, result and completion gates |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` | one-leaf config rebuild/provenance |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` | SA transout field semantics |
| `.agents/rules/INT8_SA点积专项规则.md` | `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce` | Conv/SA scope |
| `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` | `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7` | server entry boundary |
| `.agents/task_records/20260803_conv_node0004_v25_return_v26_transout_threshold_fix.md` | `ff4c10d82dee100c805d315958aef76f44b77d826314739d8a024dee8861d613` | owner completion record |

## Mechanical receipt verification

- v26 ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v26_transout_threshold_fix.zip`,
  bytes `5830794`, SHA256
  `94beb61460e033fbf8ec7afd4cd64e38cd23681fb894df9960bd3cb4be962ddb`.
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v26_transout_threshold_fix.zip.sha256`,
  bytes `106`, file SHA256
  `4118f7bbc45aa0bca3131c9d69cea550a50f00c7431f040927fa459592b50c50`;
  sidecar content binds the exact ZIP SHA.
- return report:
  `outputs/conv_node0004_v25_return_analysis/report.json`, bytes `15583`,
  SHA256 `75a8e0a798b02b566247fa7bf52b19bf12ca3a284854347eb7290b6e051fd6e0`.
- structured release:
  `outputs/conv_node0004_v25_return_analysis/successor_release.json`, bytes `10767`,
  SHA256 `42189ce6a2f17a3e16b419d7f5a2d5181e7ea8002d369f3f256e96ddf56b0651`.
- final audit:
  `outputs/conv_node0004_v25_return_analysis/v26_final_zip_self_audit.json`,
  bytes `6300`, SHA256
  `22e9cee015da907b3c6e36a4565ae7f786e4fb0fc66a0a427baaf0382a267f1c`;
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors=`0`, all required negatives
  fail closed.
- focused HDL receipt SHA256=
  `5b0db9d43356985cb95ecd123c92e0a4d46b62f92914b8193ab59a5c34674383`;
  runner receipt SHA256=
  `250c3122ec30d2432f820d12ffa8a2a5c60a6aca859cf5d6da3b4dc32bc3930c`.

## Mainline adjudication

The owner evidence is internally consistent with the current SA transout
semantics. Accepted terminal indices 4/5 against threshold 2 are positive
non-zero differences and are therefore ignored. The one-leaf change to
threshold 5 makes index 5 matched and index 4 out, so both release. This is a
configuration root cause and config-only repair; it does not authorize or
require functional RTL modification.

Blocker adjudication:

- close `B_CONV_NODE0004_RAW_TERMINAL_TO_QUALIFIED_TRANSOUT_MATCH_UNOBSERVED`;
- record `B_CONV_NODE0004_TRANSOUT_THRESHOLD_BELOW_ACCEPTED_TERMINAL` as
  identified and locally fixed;
- retain `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL` and
  `B_CONV_NODE0004_FORMAL_D_320` until the formal v26 return;
- keep `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED` invalidated.

## Rule-feedback adjudication

`RULE_CONFIRMATION` is accepted. No public or specialized rule text changes
are needed:

- `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001` correctly prevented
  diagnostic finish/no-D from being treated as success and routed analysis to
  a deterministic config root cause.
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001` correctly kept all-missing formal D
  fail closed despite mismatch=`0`.
- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001` correctly required
  the same owner to build the fresh one-leaf fix.
- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001` is
  satisfied within its focused package-local claim boundary.
- `CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001`
  is directly confirmed by the proactive structured owner notification.

Claim boundary: this adjudication places v26 in `PACKAGE_READY_NOT_RUN`; it
does not claim server VCS, DUT natural terminal, formal D, E3, E4 or E5.
