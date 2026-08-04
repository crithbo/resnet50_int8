# DeepSeek 码流生命周期增量规则

最后更新：2026-07-25

本文件只保存 DeepSeek ONNX→Stage 本地验证中，由 GEMM/GEMV 代表项新发现且已经通过
可信 JSON、原生消费者或 RTL 方程确认的增量门。公共规则不在此重复；后续相关代表项
在物化前必须把本文件加入读取收据。证据上限仍为本地 E2，不授权服务器包或 RTL 修改。

## 1. layout hint 必须有语义 owner

规则 ID：`CDA-DEEPSEEK-LAYOUT-HINT-OWNER-001`

`write_reg_hint` 不是优化注释，而是会改变 Buffer COL loop 与
`buf_spatial_stride` 的配置语义。ONNX shape 或 Stage shape 不能单独推出该字段。

- Stage producer、实际 relayout consumer 和可信 package 三方必须给出同一 layout；
- 若上游 raw Stage 缺字段，必须由独立、哈希绑定的活动 Stage producer 根据本规则
  显式输出；不得在 family materializer 内临时从 oracle 补值，也不得改写上游 raw
  Stage 证据；
- 未覆盖的新 shape/layout 不得套用旧 hint。

当前正例：FFN gate GEMM 的 A 使用
`reorder(m8,n2)->(n2,m8)`，B 使用
`reorder(n8,m2)->(m2,n8)`。上游 raw prefill op37 与原生 fragment 均缺这两个
字段；活动 producer
`layer0_prefill.rule_normalized.json` 必须把它们作为两个已登记叶子输出，并禁止
其他未登记变化。该 producer、最终 JSON、码流和可信 package 全部一致后，
`B_DS_GEMM_LAYOUT_HINT_STAGE_GAP` 对项目活动链路关闭；上游 raw 缺字段只作为
provenance 边界保留，不再作为活动链路 blocker。

## 2. GEMV B/B′ 分配必须按 operator family 判定

规则 ID：`CDA-DEEPSEEK-BP-ALLOCATION-001`

不得按端口同名或 shape 相同统一处理 B/B′：

- `decode_gemv_ring`、`decode_gemv_local` 中，B 与 B′ 是同一线性化权重的两个独立半流；
  address planner 必须分别按 `N/2` 分配互不重叠地址；
- 非独立 family 才允许 B′ 复用 B 的逻辑 allocation；是否另加 stream 内偏移必须继续
  由该 operator 的 control-register consumer 决定；
- SCA、relayout、address-bound graph 和最终 stream base 必须同时证明，没有四方一致
  不得放行。

当前 decode FFN gate GEMV 每片 A/B/B′/D 字节数分别为
`64/57344/57344/128`，基址为
`0x0/0x40/0xE040/0x1C040`。

## 3. Load_Config 长度由 64-bit 源码流拥有

规则 ID：`CDA-DEEPSEEK-CONFIG-LENGTH-PADDING-001`

`Load_Config.config_length` 是要向 slice 发送的有效 64-bit 配置字数。对当前原生
`bitstream/parse.py`，唯一通用、无歧义的计数依据是同轮生成的
`*_bitstream_64b.bin` 非空行数；不得机械使用 `128-bit 文件行数 × 2`，也不得只看
128-bit 末行是否为零来反推。

RTL `global_config_manager.sv` 的约束为：

```text
gconfig_len_sent = gexec2gconfig_len - 1
ARLEN             = (gexec2gconfig_len - 1) >> 1
odd length        => 最后一拍只写 low half，丢弃 high half
slice last        => cfg_sent_count == gconfig_len_sent
```

`parse.py` 先形成连续二进制串，分别向上补齐到 64/128 bit，再把每对 64-bit 字按
`second + first` 写入 128-bit 行。因此 validator 必须：

1. 读取 64-bit 源码流并令有效长度等于其非空行数；
2. 从 64-bit 字逐对重打包，要求与最终 128-bit 文件逐字节一致；
3. 要求 execplan `Load_Config.config_length` 等于 64-bit 行数；
4. 最后再对照 RTL 奇偶尾半字方程。

若 64-bit 字数为奇数，128-bit 最后一行 high half 才是 transport padding，正确长度为
`2 * rows - 1`。若 64-bit 字数为偶数，即使末行 high half 恰好全零，它仍可能是
语义上真实存在的全零配置字，不能删除。

已确认的历史反例与修复后正例：

- crop FFN GEMM：64-bit 源码流 59 字、128-bit 30 行，可信/RTL 长度 59；
  `128-bit rows × 2` 的错误算法会得到 60；
- crop decode FFN GEMV：64-bit 源码流 78 字、128-bit 39 行，pipeline 下发 78，
  长度正确；末行 high half 虽为全零，但它是第 78 个真实配置字，不是 padding；
- SiLU：64-bit 源码流 50 字、128-bit 25 行，下发 50，同样证明“末行高半字为零”
  不能单独作为 padding 判据。

回归必须覆盖 SiLU、RMSNorm、RoPE、Softmax、GEMM、GEMV 的全部已物化 stage，
并逐实例满足 `programmed length == 64-bit source line count`。该门只裁决本地
`EXECPLAN_LIFECYCLE` 长度，不解除各 family 独立的 route、layout、数值或动态门。

该差异属于 `EXECPLAN_LIFECYCLE`，不能因多发送的全零配置字看似无害而放行。

## 4. mapper seed 必须到达实际 bitstream 子进程

规则 ID：`CDA-DEEPSEEK-MAPPER-SEED-PROPAGATION-001`

设置父进程 `random.seed()` 不等价于固定 mapper 搜索，因为 planner/loader 可能在
mapper 前消费随机状态。双隔离重建必须：

1. 固定 `PYTHONHASHSEED`；
2. 把固定 seed 显式传入实际 `bitstream/main.py --seed`，或提供等价且有收据的参数通道；
3. 两份独立工具副本从空 mapping cache 开始；
4. 两次 mapping penalty 都为 0；
5. 排除已登记的可视化文件后，最终确定性产物逐文件一致。

测试 harness 可在隔离进程边界注入显式 `--seed`，但不得修改活动
`ndp-sim` 源码，并必须在 run receipt 中记录注入机制。由第一次运行生成、第二次运行
复用的共享 mapping cache 不属于双空缓存证据。
