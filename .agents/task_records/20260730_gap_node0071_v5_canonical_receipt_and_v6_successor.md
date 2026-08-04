# GAP node0071 v5 canonical receipt 复核与 v6 successor

日期：2026-07-30

唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RECEIPT_ONLY_AUDIT

复核对象：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v5_obsbind.zip
SHA256=159bebac586be3a40ae937736b0368593ced34c7b8128fde7858930b53ebef8d
```

ZIP identity 与 CRC 通过，但不满足
`CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`：

1. `diagnostics/progress_contract.json` 的 monotonic list 混入
   `buf4/5 wr/rd`、若干 deep 状态和 `sg_ga_input/output`。
2. observer source 证明 `buf4/5` 计数直接按持续 enable 逐周期递增，
   `sg_ga_input/output` 直接按 valid level 逐周期递增；它们不是 qualified
   transaction。
3. 包内无唯一完整 canonical decision generator/parser，无
   `reason/boundary/sample-window/counter snapshot-delta/digest` 联合记录，无对应
   return allowlist target，也无规定的负控收据。

因此：

```text
CANONICAL_DECISION_RULE_VALIDATED=false
v5_status=QUARANTINED_DO_NOT_RUN
v5_zip_modified=false
```

隔离收据：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v5_obsbind.quarantine.json
```

## SUCCESSOR

唯一 successor：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v6_canonical.zip
bytes=1787987
SHA256=aeb92c6f6442fa6e04f9207b791ccc4bab32b5ac1584b425c4cc3945f2dbdc38
status=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN
```

只修改 package-side 诊断层；73 个冻结 numeric workload 文件逐字节相等，
sum/tail/golden/config 未重建、未重跑，功能 RTL 未修改。

## CANONICAL DECISION

唯一机器记录 schema：

```text
gap-node0071-canonical-diagnostic-decision-v1
```

完整字段：

```text
schema/version
decision
reason
boundary
sample_range
window_range
qualified_counter_snapshot(start/end/delta)
content_digest(observer/sim/decision payload)
```

monotonic progress 只包含：

```text
gexec_fire
request_handshake
read_data_handshake
write_data_handshake
mse4_request_handshake_ch0/ch1
mse4_write_data_handshake_ch0/ch1
```

`ready`、enable、未握手 valid、buffer occupancy、buf4/5、GA level 和 deep
level samples 全部显式排除。stall 门比较 `active_cycles`，不把 simulation
`$time` ps 与 cycle window 混用。

负控：

```text
continuous_high_level: fail closed, qualified delta=0
summary_only_append_with_canonical_prefix: PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS
conflicting_double_decision: PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS
missing_reason: PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS
missing_boundary: PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS
nonprefixed_summary_append: does not override canonical record
```

正控：

```text
two qualified progressing windows -> STILL_PROGRESSING_NOT_FINISHED
flat qualified counters for full active-cycle stall window
  -> LONG_RUNNING_HANG_AT_<boundary>
```

最终 ZIP 独立 validator：

```text
status=CANONICAL_DECISION_RULE_VALIDATED
observer_four_way=PASS
fresh_extract_self_test=PASS
all_negative_controls_fail_closed=true
bash_n=PASS
deterministic_repeat_zip_equal=true
fresh_extract_preflight_tree_unchanged=true
```

## DEFAULT PROGRESS DIAGNOSTICS

v6 manifest 显式绑定
`CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`，默认启用低开销、只读、限流、
可部分回传的 actual compile/simulator argv、time-0 marker、qualified progress、
host wall-clock、simulation time、stall window、signal trap、canonical decision
与 allowlist return；不改变 DUT input、ready/backpressure、时序或 timeout。

服务器规则完整读取：

```text
SHA256=ed3990f13c62ce67e5081458b0dfdcf6ca257908fe138fcc05a7000482afd2f8
```

plan 仅 mutable provenance：

```text
SHA256=21dec7853cf9dc1610e51ede1366550b390bfc301d8dc8d5bf6c560d5ecae545
```

## PACKAGE_RELEASE

服务器单命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

```text
r5_n71_gap_v6_canonical_return.zip
r5_n71_gap_v6_canonical_return.zip.sha256
```

未检查、上传或运行服务器；未取得 lease；未修改 plan、公共 rules 或功能 RTL。
本轮没有重复 GAP sum/tail 数值分析，没有重建 workload；消费冻结 v5 package 与
node0071 complete local E2。
