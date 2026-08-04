# QLinearAdd 规则依赖与读取收据刷新

日期：2026-07-27

## RETURN_ANALYSIS

主线已发布 QLinearAdd 专项规则与共享 exact UINT8 quant-tail 规则。本轮只刷新 P1-A
预设计合同依赖，不改变数值、DAG、lifetime、stage feasibility、blocker 或 materialization
裁决。

current-match 语义依赖：

```text
c4c355d8f4a2ba4b2b0b34310b46b8696a87514a78c4a798c91262f2addee74e  .agents/rules/QLinearAdd算子配置规则.md
5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0  .agents/rules/精确UINT8量化尾专项规则.md
```

validator 除 SHA current-match 外，还检查 QLinearAdd 的 5 个 rule ID 与共享 tail 的 4 个
rule ID 均真实存在。生成前索引作为 routing current-match 输入：

```text
6ae4c7fe09fcdb39a48357cfef645c272f67e7a81d09b5547ebd9a929e6ce1a4  .agents/rules/生成前必读索引.md
```

plan 只保留 mutable read receipt：

```text
d42a3ac6208f4198fdcd17cc569a156fbc7906661618dca59e3d43147f887e35  .agents/plan.md
```

plan 后续漂移只产生 warning 并请求主线复核 scope；不会覆盖两条 current-match 专项规则
及 typed/qparam/lifetime/oracle/P0-A 机器合同的严格语义哈希门。

P1-A 结论保持：

- `NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`;
- single-stage fused `REMAINS_UNDECIDABLE`;
- two-stage explicit scratch
  `REMAINS_STRUCTURALLY_FEASIBLE_NUMERIC_TAIL_UNCLOSED`;
- `materialization_allowed=false`;
- blocker close none。

本轮未修改 plan/rules/RTL；未生成目标 JSON、mapping、bitstream、execplan、SCA、package；
未检查或运行服务器。
