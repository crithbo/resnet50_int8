# node0004 历史本地资产不可信与全新重建主线覆盖裁决

日期：2026-07-28

## 覆盖裁决

用户明确声明 node0004 的本地全部资料不可信、测试全部失败。该指示覆盖此前任何
node0004 accumulate local E2、serialized materialization 或 config-only baseline 裁决。

以下资产只保留为负面历史，不得被新生成器、validator、config-bound simulator 或
测试包消费：

- node0004 历史 operator JSON 与 patched/address-bound JSON；
- mapping、parsed/64b/128b bitstream、execplan、SCA/SCA_D；
- physical input/output、local simulator result、comparison report；
- server package、package manifest、return 或测试收据；
- `20260727_conv_node0004_serialized_one_product_local_e2.md` 及其主线裁决中的通过结论。

全网计数同步撤销：

- 精确物化 JSON：`6/133 → 5/133`；
- `CONFIG_ONLY_CORRECTNESS_BASELINE`：`4 → 3`；
- 完整 ONNX 节点 local E2 与正式三方计数不变。

## 允许的新来源

全新 node0004 只能消费：

- 锁定 typed lowering/request；
- 正式 W3/model tensor 与 initializer；
- 活动生成前索引、公共规则、硬件字段和 Conv/Requant/tail 专项规则；
- C0 两份独立本地代码审计；
- 本轮明确授权且哈希绑定的原生静态模板与工具源码。

## 条件路径

```text
if RTL defect confirmed and no exact alternative:
    fresh serialized config bypass
else if RTL is correct or an exact alternative exists:
    fresh normal/alternative path
else:
    stop before configuration generation
```

无论选择哪条路径，都必须从 operator JSON 重新生成到完整 node0004 UINT8 local E2，
随后本地生成全新测试包并停在 `PACKAGE_READY_NOT_RUN`。

本裁决不授权 RTL 修改、服务器文件检查、上传或运行。
