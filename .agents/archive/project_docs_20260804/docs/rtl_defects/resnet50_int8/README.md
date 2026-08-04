# ResNet50 INT8 必经 RTL 功能缺陷报告

本文档集面向负责 RTL 修复与验证的工程人员。文件地址均以云端仓库
`xlsjdjdk/Trassic2.0_RTL` 的仓库根目录为基准，参考源码版本：

```text
e3bdebba95dec36ee8eba43caa92a326a88392cd
```

报告仅讨论当前 ResNet50 INT8 推理必经计算所触发的功能 RTL 缺陷，不使用项目内部
节点编号、blocker、配置生成或服务器测试命名。

## 报告清单

1. [SA INT8 模式丢弃 DataC/partial sum](01_sa_int8_datac_psum_zero.md)
2. [SA INT8 carry 被重复左移](02_sa_int8_duplicate_carry_shift.md)
3. [SA INT8 四乘积归约位宽不足且丢弃 cout](03_sa_int8_reduction_width_and_cout.md)
4. [GA signed INT32 转 FP32 的负数转换错误](04_ga_int32_to_fp32_negative_conversion.md)
5. [GA INT8 pipeline0 缺少 ready 分支](05_ga_int8_pipeline0_ready_missing.md)
6. [GAP transout outbuffer occupancy 下溢](06_gap_outbuffer_occupancy_underflow.md)
7. [GAP 无效 outbuffer 槽的 stale DataC 复用](07_gap_invalid_slot_stale_c.md)
8. [GAP 跨 reduction block 的 feedback 初始化错误](08_gap_cross_block_feedback_initialization.md)

## 影响范围概览

| 报告 | 主要影响的 ResNet50 计算 |
|---|---|
| 1～3 | 全部 INT8 Convolution 和最终 INT8 Matrix Multiplication 的点积累加 |
| 4 | 卷积/矩阵乘 accumulator 到 UINT8 输出量化前的 signed INT32→FP32 |
| 5 | 首层 MaxPool 的连续 UINT8 最大值归约 |
| 6～8 | Global Average Pooling 的 49 项空间求和 |

这八项均应分别修复和验收。修复其中一项不能自动证明同一模块中的其他缺陷已经消失。

