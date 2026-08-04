# Requant node0001 atomic2 stock v2 回传裁决

日期：2026-07-26

## 结论

本次是首个真正进入并自然完成 Requant node0001 原子两阶段计算的服务器运行。编译、
仿真和 runner 均退出 0；slice0+1 上 guard 与 round/saturate 两个 stage 都按同一 mask
自然完成，SCA_D 也完成 4 项正式回读。因此已经排除 bootstrap、编译、stock TB mask、
stage completion、两阶段启动顺序和 timeout 作为本轮首分歧。

数值失败发生在 guard 数据路径：两份非零输入各 8 行在仿真前写入并回读一致；原始
same-clock observer 实际捕获 20/20 次 accepted MSE4 write，其中 guard 16 次、
round/saturate 4 次，但所有 20 个 128-bit payload 都为 0。四份正式 D 共 20 行，
格式和行数正确，但也全部为 0，均不匹配 golden。

裁决：

```text
status=ATOMIC_DYNAMIC_EXECUTION_COMPLETE_NUMERIC_FAIL
classification=FIRST_DYNAMIC_FAILURE
dynamic_baseline=NO_DYNAMIC_BASELINE
first_direct_divergence=GUARD_WRITE_PAYLOAD_ZERO_AFTER_NONZERO_INPUT_PRELOAD
enable_only=guard-only
candidate_release=false
counts_as_node0001_e4=false
counts_as_node0001_e5=false
```

现有证据还不能在 MSE0/Buffer→GA、GA int32-to-fp32、GA/SFU guard 运算和 MSE4
地址/写数据路由之间判定 CONFIG_SEMANTICS 或 RTL root cause。下一包只允许 guard-only，
用只读检查点寻找最早的非零数据消失位置。

## 身份与回传门

```text
return ZIP size=55481
return ZIP SHA256=5d7b691da0b6159eed2ec9927cec766a9b17f53c3b31db536364ea6b46c8b46d
sidecar provided=false
ZIP entries=34
unsafe paths=0
duplicate paths=0
receipt payload=33/33
receipt missing/extra/size/hash mismatch=0/0/0
package manifest SHA256=a204c285f4beed10050883e90dd6b8716ab3dde5f65f337a678207cd00c639fa
source/returned package manifest byte identity=true
```

虽然用户未提供 sidecar，本地已对 ZIP 重新计算 SHA-256；ZIP 内 RETURN_RECEIPT 的
33 项 allowlist payload 与实际内容逐项 size/SHA 一致。pre/post/post-run/post-restore
身份完整；focused RTL 未变；只读 observer 在编译前验证并在编译后逐字节恢复。

## 包内分析器漏计与地址域错误

包内 `MSE4_WRITE_OBSERVER_RECEIPT.json` 报告 `actual_write_count=4`，这一计数不正确。
observer 用 `%s` 输出 guard role 时产生了填充：

```text
role=         guard
```

runtime regex 却只接受紧邻的 `role=guard`，所以漏掉全部 16 条 guard 行，只保留
4 条 `round_saturate`。用允许空白的表达式重解析两份原始日志后得到：

```text
raw accepted writes=20
guard=16
round_saturate=4
zero payload=20
```

该分析器缺陷不改变数值失败结论，但把“写次数缺失”修正为“写次数完整、数据全零”。
此外，当前 expected write 用线性 `word_address_128b`，observer 采样的却是
`WR_Memory_AG` 经 `mse_map_matrix_b` 重排后的 `local_req_addr`。
`WR_Memory_AG.sv:302-351` 明确先重排 `transfer_addr_nooff` 再形成请求地址，且本包
`address_remapping=None` 编码出的默认 remap 并非恒等矩阵。因此当前 raw address 与
线性 word address 的直接比较也不能用于裁决地址错误；后续必须比较同一地址域，或同时
记录 remap 前后地址。

后续包必须修正 parser/输出格式、地址域和原始日志与机器 receipt 的一致性自检。

## 证据

- 原始只读 ZIP：
  `server_returns/rq_node0001_atomic2_stock_v2_return_20260726/raw/rq_node0001_atomic2_stock_v2_return.zip`
- 解压只读证据：
  `server_returns/rq_node0001_atomic2_stock_v2_return_20260726/extracted/rq_node0001_atomic2_stock_v2_return/`
- 机器裁决：
  `server_returns/rq_node0001_atomic2_stock_v2_return_analysis_20260726.json`

本轮未修改 `NDP_copy01/rtl/**`、TB 或功能配置，也未生成服务器修复包。
