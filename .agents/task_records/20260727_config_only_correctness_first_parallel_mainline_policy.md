# ResNet50 纯配置正确性优先并行主线策略

日期：2026-07-27

用户本轮明确要求：

```text
先不采用任何更改 RTL 的方案。
所有方案以能跑通为准，配置上能绕行就绕行，但必须标注绕行原因。
主线主要负责统筹任务，算子族并行完成。
```

## 全局策略

1. `rtl/**` 功能修改、RTL repair package 和依赖功能 RTL 变化的路线全部冻结；
2. 正确性优先于吞吐和资源效率；允许多 stage、显式 scratch、串行 occurrence、
   重放、额外 barrier 或低利用率配置绕行；
3. 绕行必须对完整合法输入域或目标实例冻结域给出 bit-exact/容差等价证明，不能靠
   最终饱和、抽样或单一反例通过；
4. 每份 config-only bypass 合同必须保存：

   ```text
   bypass_reason
   contradicted_or_missing_native_path
   exact_equivalence_scope
   materialized_configuration_mechanism
   performance_and_resource_cost
   unresolved_production_blocker
   claim_boundary
   ```

5. 绕行资产只能称 `CONFIG_ONLY_CORRECTNESS_BASELINE`，除非另有性能与正式动态证据，
   不得称 production/performance release；
6. 本轮优先完成本地最终物化 E2；没有用户实际上机授权时不生成或运行服务器包，
   不检查服务器文件、名称或当前身份。

## 并行工作分解

- Conv/MatMul accumulate：单乘积序列化；
- Quantize/shared tail：多 PE/多 stage 或显式中间值配置绕行，保持精确舍入顺序；
- Requant：按 33 zp0、16 even nonzero-zp、5 odd nonzero-zp 分组选择精确配置绕行；
- QLinearAdd：优先 two-stage explicit FP32 scratch；
- Dequant node0072：复用 node0077 的两级 GA 配置并做实例适配；
- MaxPool：复用目标模板，闭合 mapper/flow；
- GAP：优先 pure-config sum→requant 两级路线，RTL repair 继续冻结；
- Flatten：zero-copy physical view，闭合 alias/offset/lifetime。

每个算子族独立维护本族 generator/validator/config/contract/artifact/task record，只向主线
回传结构化状态；主线唯一维护 plan、公共规则、全局 blocker、依赖顺序和服务器 lease。

## 本轮并行任务

| 算子族 | Codex 任务 | 本轮边界 |
|---|---|---|
| Conv/SA | `019fa2c1-17df-7122-bcbd-a727aaf173f5` | node0004 单乘积序列化 accumulate local E2 |
| Quantize/shared tail | `019fa2c0-572b-7f21-ac5a-96e773dde534` | GA 舍入判别与顺序保持的多 PE/多 stage 绕行 |
| Requant | `019fa2bf-95cd-7502-82c8-6a48cf12d648` | 33/16/5 三组精确绕行 |
| QLinearAdd | `019fa2c0-b647-7a91-93bf-d21a173487e3` | two-stage FP32 scratch stage0 与 tail 依赖接口 |
| Dequant | `019fa2bf-f9a5-7a73-ada3-b2b910721de3` | node0072 复用 node0077/v6 的实例适配 |
| MaxPool | `019fa366-be0a-7db2-82ff-558fbd3bce68` | 模板复用后的 target flow/materialization |
| GAP | `019fa366-cb1f-7ae2-880c-f527be0680cd` | pure-config sum stage 与 exact tail 接口 |
| Flatten/View | `019fa366-d218-7122-839c-0b52d83faf13` | node0073 zero-copy 地址/lifetime 闭环 |

以上任务均使用 `reasoning=high`，直接共享当前工作区；均无服务器 lease。
