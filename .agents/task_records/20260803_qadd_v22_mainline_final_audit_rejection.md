# QLinearAdd node0007 v22 主线 final-audit 驳回裁决

- mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- date: `2026-08-03`
- functional RTL modified: `false`
- server upload/run/lease: `false`

## Current read receipts

| Path | SHA256 | Reason |
|---|---|---|
| `.agents/agent.md` | `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721` | control boundary |
| `.agents/plan.md` before update | `29c98580925a2932c6db62ec679272cad644bc1bc16a7f43bba22c46ce82c0e2` | current state |
| `.agents/rules/生成前必读索引.md` | `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5` | routing |
| `.agents/rules/服务器测试包生成规则.md` | `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48` | final-ZIP/HDL/runner gates |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` | frozen config boundary |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` | B-stage hardware field semantics |
| `.agents/rules/QLinearAdd算子配置规则.md` | `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f` | QAdd dynamic/config boundary |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` | frozen tail boundary |
| `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` | `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7` | hardware simulation entry |
| `.agents/task_records/20260803_qlinearadd_node0007_v20_return_v22_split_control.md` | `7948a7502a699625f3465b8000239c1570291550d101b2472dd00950cf45062e` | owner completion record |

## Mechanically verified identities

- v22 ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_b_dequant_control_v22.zip`,
  bytes `38034925`, SHA256
  `4a51be0ab59b0ff8c0754de68f11d7f3d1328b6fe012b3945468b787d2b11fd5`.
- sidecar bytes `103`, file SHA256
  `80d31fee787b7149bbf58b9202df7689babe588b940cf33f5fb87967c74ddf4f`;
  content binds the exact ZIP SHA.
- owner final audit:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-b-dequant-control-v22/final_zip_self_audit.json`,
  bytes `7581`, SHA256
  `a747d41b18ed51cc3120ab97c04bb966814e2b7d81e023a23aa127e36412451f`.
- release report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-b-dequant-control-v22/release_report.json`,
  bytes `7150`, SHA256
  `55baaa8746100f43ce00232a6e619f1bfe7e8e4157d4c372589290159b3510f4`.

## Evidence retained

The v20 return analysis is accepted:

- receipt/source/preflight integrity passed;
- compile/simulation/signal=`0/125/INT`, no natural terminal, formal D
  `0/28`, E3/E4/E5=false;
- `LAST_PROVEN_GOOD=OP_A_DEQUANT_COMP_FINISH_AND_OP_B_DEQUANT_QUALIFIED_PROGRESS`;
- `FIRST_DIVERGENCE=V20_OP_B_DEQUANT_VCS_INFL_DELTA_AT_17020861875PS_ABOUT_154000_ACTIVE_CYCLES`;
- the v18→v20 frozen-payload comparison makes package-local observer
  amplification the leading, not yet dynamically confirmed cause;
- the B-only split/control design is the correct next diagnostic.

## Final-audit escape

The v22 exact ZIP contains package-local HDL:

- `tb_probe/native_return_observer.svh`;
- `tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh`.

The owner audit contains no compatible frontend invocation, exact-member
syntax/scope/name-resolution receipt, required-evidence identifier/state
declaration/use/update closure, or the three required negative controls.
It therefore does not satisfy
`CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`.

The same audit records three `grep: ... No such file or directory`
diagnostics in
`runner_control_flow.safe_compile_stub_positive_control.stderr_tail`, but
still reports the control as passed. This violates
`CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`, which requires
the safe control to complete finalization without shell diagnostics.

## Mainline adjudication

- reject v22 `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true` as an overclaim;
- revoke `PACKAGE_READY_NOT_RUN`;
- set v22 to
  `QUARANTINED_FINAL_AUDIT_NONCOMPLIANT_DO_NOT_RUN`;
- classify the open package gates as
  `PACKAGE_LOCAL_HDL_SYNTAX_SCOPE_UNPROVEN` and
  `PACKAGE_RUNNER_PREFLIGHT_TO_COMPILE_CHAIN_UNPROVEN`;
- preserve `B_QADD_V20_PACKAGE_LOCAL_FP32_OBSERVER_EVENT_STORM_SUSPECT` and
  `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`;
- require a fresh identity because runner bytes must change.

The original owner has been notified to keep the B-only semantic design and
all numeric/W3/qparam/tail/workload/config/golden/functional-RTL assets
frozen, fix only runner/finalizer and validator/HDL gates, rebuild
deterministically, and proactively return the fresh release to this mainline.

## Rule-feedback adjudication

The statement `CURRENT_RULES_SUFFICIENT` is accepted only as a rule
confirmation: current ordered-stage, qualified-event, default diagnostics,
continuous closure, package-local HDL and runner positive-control rules are
sufficient to reject both the v20 canonical misclassification and the v22
delivery escape. No synonymous public rule is added.

The owner package-release claim is rejected because its validator did not
execute those already-current gates. This adjudication does not claim a
QAdd B-stage config or functional RTL fault.
