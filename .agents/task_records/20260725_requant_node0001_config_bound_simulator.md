# Requant node0001 config-bound simulator 中间腿

日期：2026-07-25

## 结论

`r5:hwop-0001-01` 已完成本地 config-bound simulator 中间腿：

```text
48 final address-bound JSON
  + 24 occurrence / 48-stage graph
  + SCA / 317-line execplan
  + HWC8 slice/sample/channel layout
  -> project equivalent config-bound executor
  -> physical D
  -> shared HWC8 inverse
  -> logical NCHW UINT8
```

执行结果：

- 12,845,056 个 UINT8 元素对 W3 golden bit-exact；
- 24 occurrence、48 stage 全覆盖；
- 128 个 active slice execution 与 128 个唯一 final D region；
- 28 个 guard alias region；
- 每个 logical sample/channel 恰好覆盖一次；
- NDPFuncModel `ActivationUnit.sse2_round_to_int` 交叉检查 0 mismatch；
- CGRA_SIM `qnn_round.sse2_round_to_int` 公式参考 0 mismatch。

## 证据边界

当前 `NDPFuncModel` 没有可直接执行 node0001 两级 guard→round JSON 的完整
`GeneralPEA`。本轮没有伪称原生模型已支持该路径，而是在项目侧实现等价配置绑定执行器：
它从最终 JSON 提取 GA opcode、conversion flag、lane multiplier、magic/subtract
常量和 stream 地址，并消费最终 occurrence/layout/lifecycle。

三方报告状态：

- golden↔config-bound simulator：`PASS`；
- golden↔stock-RTL hardware：`EVIDENCE_MISSING`；
- config-bound simulator↔stock-RTL hardware：`EVIDENCE_MISSING`。

因此状态仍为 `E2_LOCAL_ONLY`、`candidate_release=false`、
`formal_target_instance_allowed=false`，唯一动态 blocker 仍是
`B_REQUANT_SERVER_E4_E5`。

## 规则与实现

新增规则：

- `CDA-REQUANT-CONFIG-BOUND-SIMULATOR-001`

新增文件：

- `resnet50_pipeline/requant_config_bound_simulator.py`
- `tools/build_requant_node0001_config_bound_simulator.py`
- `tests/test_requant_node0001_config_bound_simulator.py`
- `contracts/operator_config/requant_node0001_config_bound_simulator_v1.json`
- `artifacts/operator_config_validation/r5-requant-node0001-config-bound-sim-v1/three_way_report.json`

另移除了 Requant 数值分类对非语义 `.agents/plan.md` 哈希的依赖；以后修改活动计划不会
机械触发 54-stage 数值分类重建。算子规则、typed/W3 或执行器身份变化仍会 fail-closed。

## 验证

- Requant config-bound、node0001、RTL 语义与全族定向测试：19/19 通过；
- plan 只更新当前进度和下一步；
- 未修改 `NDPFuncModel`、`CGRA_SIM`、`ndp-sim` 或任何 `rtl/` 文件；
- 未生成服务器包；
- 按效率策略，没有重建不影响本次结论的全项目闭环资产。

下一步是物化一个默认 `single-occurrence-two-stage` 组合动态合同；只有组合测试出现明确
首分歧时，才按需启用 guard-only、round-only 或额外 alias 诊断。
