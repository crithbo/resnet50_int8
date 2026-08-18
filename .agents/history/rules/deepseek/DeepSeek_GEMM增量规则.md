# DeepSeek GEMM 增量规则

最后更新：2026-07-25

适用范围：crop-derived DeepSeek prefill FFN gate
`prefill_gemm_ring_4slice`。公共身份、生成门、码流长度和证据等级不在本文重复。

## CDA-DEEPSEEK-GEMM-NUMERIC-PAYLOAD-001

当前代表的逻辑方程为：

```text
A: fp16[K=896,M=32]
B: fp16[K=896,N=1792]
acc_fp32[m,n] = sum_k(fp16(A[k,m]) * fp16(B[k,n]))
D: fp16[N=1792,M=32] = fp16(transpose(acc_fp32))
```

本地独立 payload 可以使用确定性合成值，但必须同时保存完整逻辑 A/B/D 和 28 slice
的物理 A/B/D；合成 payload 只关闭算子公式、分片与 relayout 的本地 E2，不得声明为
ONNX 原始权重、服务器 readback 或硬件精度 E4。

## CDA-DEEPSEEK-GEMM-RING-PARTIAL-COVERAGE-001

必须逐输出 slice 验证全部 28 个 K-chunk partial 均参与最终和；仅验证最终矩阵 shape
或 N2N `mem_loop=28` 不足。每个输出 slice 的 32×64 结果必须等于其 28 个
`A_chunk.T @ B_chunk` 之和。

物理 payload 必须调用并反验原生消费者定义的：

- A：`L8,K2,L4`；
- B：ring reorder 后的 `N8,K2,N4`；
- D：`L8,N8,L4,N4`；
- logical→physical slice mapping 和 28-slice ring order。

任一物理文件为空、logical/physical 映射不双射、ring partial 缺项或最终 D 与独立
FP32 累加不一致时 fail closed。

