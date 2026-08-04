# Requant hash-bound 报告随 E4 v2 总账刷新

日期：2026-07-25

## 裁决

Requant E4 v2 包扩展回归中的两项失败，仅来自
`contracts/resnet50_r5_lowering_bundle.json` 的当前 hash-bound 身份变化。
公式、W3 数值、64 通道放置、node0001 本地 E2、冻结 JSON/bitstream/execplan/SCA
和 v2 包内容均未改变。

按当前必读索引刷新读取范围后，使用权威生成器完整重建：

- `contracts/operator_config/node0004_requant_semantics_evidence_v1.json`
- `artifacts/operator_config_validation/r5-requant-family-classification-v1/generation_receipt.json`
- `artifacts/operator_config_validation/r5-requant-family-classification-v1/report.json`
- `contracts/operator_config/requant_family_classification_v1.json`

没有手工替换 SHA。family generation receipt 重新绑定当前 `.agents/plan.md`、公共
规则、硬件字段语义、Requant 专项规则、typed contract、lowering bundle、W3 和
node0001 E2 身份。

## 结论不变量

- node0004 W3 mismatch：0；
- node0004 channel coverage：64/64；
- Requant family：54/54 标准公式逐元素对 golden；
- guard-compatible/contradicted：33/21；
- node0001 仍是唯一物化 E2 与唯一可 emission candidate；
- formal target/E4/E5：0/0/0；
- `B_REQUANT_SERVER_E4_E5` 未解除。

重建后原失败两项及相关 Requant 集合通过。未生成算子 JSON、mapping、bitstream、
execplan、SCA/SCA_D 或服务器包，未修改任何 `rtl/` 文件。
