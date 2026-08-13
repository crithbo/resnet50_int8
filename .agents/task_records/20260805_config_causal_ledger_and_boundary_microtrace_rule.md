# 2026-08-05 config causal ledger and boundary microtrace rule

## 结论

`RULE_DELTA_ACCEPTED_AND_PUBLISHED`。

公共配置规则已有物化回环、地址、transaction与供给守恒原则，但缺少统一、可缓存且只覆盖
changed causal slice的机器收据。各算子因此把同一类检查混入完整final-ZIP validator：
服务器相关检查重复执行，真正的threshold/byte-set/lifetime边界却依赖专项脚本是否恰好实现。

新增：

- `CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`
- `CDA-CONFIG-BOUNDARY-MICROTRACE-001`

修改：`.agents/rules/算子配置规则.md`。

## 本地实证

### Conv node0004 transout

复用既有活动RTL方程与冻结物化报告：

- accepted terminal：index4×64、index5×192；
- 旧threshold2：256/256进入ignore；
- 新threshold5：index4进入out、index5进入matched，256/256 release；
- targeted metadata-only复验exit0。

### QLinearAdd node0007 split-C

从frozen v35 final ZIP调用既有rowpair contract核心：

- 13/13物化检查通过；
- `accepted_supply_i=[0,16) U [16,32)=[0,32)=required_arm_bytes_i`；
- 删除/重复window、gap、overlap、wrong transaction、wrong occurrence、narrow mask
  七类负控全部fail closed；
- targeted复验exit0，约2.1秒。

同一v35完整final-package validator在本地主线60秒预算内超时；它还重复runner、HDL、
path、return等未变化表面。该对比证明后续应由服务器包`release_gate_matrix`只消费
`materialized_config`专项收据，而不是为了验证配置重跑完整包审计。

机器报告：
`artifacts/operator_config_validation/r5-config-causal-ledger-microtrace-rule-v1/report.json`。

发布收据：

- previous config rule SHA256：
  `8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497`
- published config rule SHA256：
  `d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0`
- machine report SHA256：
  `1511e86b2387dffe0d2cd324d24bae9d3976aba6881f95f4031118c18f4e4c5d`

## 适用边界

- 新算子首次物化或changed config必须生成ledger和适用microtrace；
- exact config/causal slice未变时按SHA/current receipt复用，不重复；
- numeric/W3/golden、runner、HDL、path和return分别由其owner门负责，配置门不得代跑；
- 跨时钟或无法本地可靠建模的真实动态状态标记`DYNAMIC_ONLY_BOUNDARY`，只生成最小服务器
  observer，不伪造本地通过；
- 本规则不提高E2，不替代production compile、natural terminal、formal D或E4/E5。
