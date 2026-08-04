# Conv 单乘积序列化纯配置基线主线授权

日期：2026-07-27

用户本轮明确选择：

```text
暂时以纯配置正确性路线作为“先让 ResNet Conv 数值跑通”的基线方案。
```

## 授权范围

首个代表实例固定为 ResNet50 `node0004` 的 `ConvInt32Accumulate`。允许 Conv/SA 算子族
在项目资产范围内：

- 生成全新身份的 serialized-one-product 配置；
- 修改本族 generator、validator、config、contract、artifact 和 task record；
- 生成本地 mapping、bitstream、execplan/SCA 与 config-bound simulator 输入；
- 完成 INT32 accumulate 的本地物理 E2。

serialized 语义固定为：

```text
each SA occurrence has at most one nonzero s8(weight) * u8(activation) lane
int32_result = initial_psum + Σ(single_product_occurrence) mod 2^32
initial_psum = bias - x_zero_point * Σ(weight), when x_zero_point is nonzero
```

## 本轮验收门

1. 最终 materialized JSON 反解后，每个 SA occurrence 至多一个非零乘积 lane；
2. occurrence 扩张、K-tail、padding、bias、x-zero-point 修正和 multi-wave psum
   与 W3 INT32 golden bit-exact；
3. read/Buffer/SA/write transaction、地址、bank、lifetime、terminal 守恒；
4. 最终 JSON→mapping→bitstream→execplan/SCA 完整回环；
5. config-bound simulator 必须消费上述最终物理资产并还原逻辑 INT32 tensor；
6. stock four-lane negative control 继续失败，serialized model 继续作为独立正确性基线；
7. 只在本地 accumulate E2 闭合后，主线才决定是否进入完整 node0004
   bias/psum/tiling 以及后继 requant 串联。

## 未授权范围

- 不修改任何 `rtl/**`；
- 不生成、上传或运行服务器包；
- 不检查服务器文件、目录名称或当前 RTL identity；
- 不把约 25% product-lane 利用率的基线称为 production/performance release；
- 不把 INT32 accumulate E2 自动外推为完整 QLinearConv UINT8 节点通过；
- 不关闭 shared quant-tail、服务器 E4/E5 或兼容 RTL blocker。

