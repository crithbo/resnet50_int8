# QLinearAdd node0007 first-request-chain v10

## RETURN_ANALYSIS

- Reused the frozen node0007 v4/v6 workload, final JSON, execplan, SCA/SCA_D,
  six qparams, W3 ordering, exact tail and golden without repeating numerical
  or workload analysis.
- The prior dynamic evidence proves `op_a_dequant` accepted the execution
  command and then accumulated 22 full stall windows with
  `req/rdata/wdata=0/0/0`, but it does not identify the first internal
  ready/handshake that stopped.
- Static audit found that the prior `EXEC_START` witness sampled
  `sem2iga_exec_start`, not an independently observed actual
  `slice_start_run`. It also sampled fixed LC0/LC2/LC_PE1 rather than the
  final mapped active LC2/LC4/LC6/LC13/LC18 chain.
- `Memory_AG_Idx_Queue` permits an initially empty queue to accept selected
  index work, so shared-LC fanout is not sufficient evidence for a
  combinational ready-cycle root cause.

## FIRST_DIVERGENCE / HANG_ROOT_CAUSE

```text
LAST_PROVEN_GOOD =
  op_a_dequant execution command accepted

FIRST_DIVERGENCE =
  actual slice_start_run -> first accepted MSE0 DRAM request

HANG_ROOT_CAUSE =
  UNRESOLVED_AFTER_EXHAUSTIVE_LOCAL_AUDIT_WITHIN_
  OP_A_DEQUANT_START_COMP_TO_FIRST_MSE_REQUEST
```

No configuration leaf was changed because the existing evidence cannot
distinguish slice-start propagation, mapped LC output handshakes, selected
MSE index match/queue write, address-generator accept, or request enqueue.

## PACKAGE_RELEASE

`r5_qadd_n7_first_request_chain_v10` is the only runnable successor:

- class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- status: `PACKAGE_READY_NOT_RUN`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_first_request_chain_v10.zip`
- SHA-256:
  `573121def027a04b33650122e82d6c32cb8fbc4c9162cfc6cc831237a01869cf`
- bytes: `38,033,628`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_first_request_chain_v10.zip.sha256`
- sidecar SHA-256:
  `c3a567adddf784e967c0bbf7106fb07535fdc92898ce00219d31422be7acd514`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  `r5_qadd_n7_first_request_chain_v10_return.zip` and adjacent sidecar.

v6/v7/v8 remain quarantined. v9 is additionally quarantined as
`QUARANTINED_NOT_RUN_EVENT_QUALIFICATION_SELF_AUDIT`: its
`slice_start_run` count lacked an explicit rising-edge witness. v10 fixes
only that observer qualification and does not change the workload,
configuration, timeout, ready/backpressure, formal D, or functional RTL.

## FINAL ZIP CURRENT-RULE SELF-AUDIT

Post-generation reread receipts:

- `.agents/rules/生成前必读索引.md`
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`
- `.agents/rules/QLinearAdd算子配置规则.md`
  `c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

Validator:

```text
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -B tools/validate_qlinearadd_node0007_first_request_chain_v10.py
exit_code=0
FINAL_ZIP_RULE_SELF_AUDIT_PASS=true
errors=0
negative_controls=18/18 fail closed
```

Directed tests:

```text
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -B -m unittest tests.test_qlinearadd_first_request_canonical_decision tests.test_qlinearadd_node0007_first_request_chain_v10 -v
exit_code=0
11/11 passed
```

Package-local observer preprocess binding:

```text
C:\iverilog\bin\iverilog.exe -g2012 -E -I NDP_copy01/rtl/includes -I artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_first_request_chain_v10/tb_probe -D NATIVE_RETURN_OBSERVER_ENABLE -o <temporary>/qadd_v10_observer_preprocessed.sv NDP_copy01/tb_NDP_Top_new_phy.sv
exit_code=0
FIRST_REQUEST_CHAIN markers=1
```

The local Icarus frontend cannot compile the complete production TB because
it rejects pre-existing constructs before the observer include; therefore
this check is limited to package-local preprocessing/include resolution.
The actual VCS compile remains a required server-side diagnostic gate.

Machine report:

- `artifacts/operator_config_validation/r5-qlinearadd-node0007-first-request-chain-v10/report.json`
- SHA-256:
  `7ede3635578b920a79b6971170518a5896160c0133a878b6ed97480c0e444c54`

## BLOCKER_DELTA

- Remains open:
  `B_QADD_NODE0007_OP_A_DEQUANT_FIRST_REQUEST_INTERNAL_READY`.
- Narrowed to a single ordered chain:
  actual slice-start edge → physical LC4 → LC2/LC6 → LC13/LC18 → selected
  MSE0 index inputs → match/queue write → AG accept → request enqueue/accept.
- E3/E4/E5 remain unclaimed.

## RULE_DELTA_PROPOSAL

None. Current
`CDA-QADD-FIRST-REQUEST-HANG-INTERNAL-READY-OBSERVABILITY-001` plus the
current server observer/event/canonical/final-ZIP rules fully cover this
diagnostic.
