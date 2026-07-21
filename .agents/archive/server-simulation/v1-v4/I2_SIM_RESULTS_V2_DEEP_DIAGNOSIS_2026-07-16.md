# I2 第二轮服务器仿真深度卡点诊断

日期：2026-07-16

## 1. 结论

第二轮真正的首个卡点不在 command engine 的“取下一 stage”，而在第一个 accumulate stage 内部的输出读改写（read-modify-write，RMW）：

```text
Start_Comp
  -> 28 个 slice 均开始 accumulate
  -> 每个 slice 首次读取 P scratch 的两个 128-bit line
  -> 56/56 个返回值均为全 X
  -> 56 个输出写请求已经发出
  -> 0 个写数据握手
  -> 0 个 slice 完成
  -> command engine 等不到 stage-complete，因而停在 1/9
```

因此，“command engine 停在 1/9”是后果，不是最早的故障点。第二轮不能判为硬件数值 mismatch，也不能判为三方通过；状态仍是 `returned_incomplete / three_way_not_comparable`。

## 2. 如何绑定到本次运行

压缩包里混有三个不同时段的 local 日志命名空间：

- 当前目标 `sim_results/local/`：约 `1916988000 ns` 开始；
- `local_op23-42/`：约 `6078273000 ns` 开始并完成；
- `local_layer0_0-42/`：约 `11044172000 ns` 开始并完成。

全局 `gexec2slice.log` 中本次唯一的 runtime `Start_Comp` 在 `1916987000 ns`。只有 `sim_results/local/` 的首事件与它相差约 `1000 ns`，所以诊断器按时间最近原则绑定该命名空间。后两个“能完成”的 local 日志属于其他运行，不能拿来证明当前 `node-0004` 完成。

## 3. 28 个 slice 的一致证据

对 `local/0..27` 全部日志逐个解析，得到完全一致的行为：

- 每个 slice 都读取 P 的 local 128-bit line `0x00250D` 和 `0x00281D`；
- 两次读取的返回均为全 `X`；
- 每个 slice 都发出 2 个输出写请求；
- 每个 slice 的 output write-data handshake 均为 0；
- completed slice 数为 0；
- P 和 staged-D 目标区 Bank 写入数均为 0。

全局合计：

| 指标 | 结果 |
|---|---:|
| slice 数 | 28 |
| 未知输出读返回 | 56 |
| 输出写请求 | 56 |
| 输出写数据握手 | 0 |
| 完成 slice | 0 |

机器报告的首故障阶段为 `slice_output_read_modify_write`，状态为 `stalled_on_unknown_output_read_modify_write`。

## 4. 为什么 86/86 预装通过仍会卡住

v2 的 86 个 probe 只覆盖：

```text
28 slice × (A + B + bias) + accumulate config + execplan = 86
```

它证明 A/B/bias/config/execplan 的服务器 SCA 文本运输已经正确，但没有覆盖运行时 scratch：

- P accumulation buffer；
- requant 前的 staged-D buffer。

服务器终端报告 `JSON config: 262 matrices loaded`，恰好等于 v2 `sca_cfg.json` 的 payload 数量，说明服务器本轮走的是稀疏 SCA 加载路径。v2 SCA 没有声明 P/staged-D 初始化，因此这些地址保持未初始化状态。

`Bank_data` 也不是“完整 Bank RAM 镜像”：slice01～27 每份恰有 37,940 个 32-bit word，而 P 的第一个 128-bit line 是 `0x250D`，对应第一个 32-bit word index 为 `0x250D × 4 = 37,940`。也就是说这些文件正好结束在 P 之前。slice00 因还包含高地址 config/execplan 而覆盖更大地址范围，但本轮实际使用的是 SCA，不会由它填充 P 的零洞。

这不否定 `execplan.txt/Bank_data` 中已声明内容的正确性；问题是服务器 RAM 上电为 X 时，稀疏输入还需要明确初始化运行时 scratch，或者在加载稀疏 Bank_data 前把整个 Bank RAM 清零。

## 5. 修复方案：v3 运行包

已生成面向同一冻结单算子的 v3 包：

```text
artifacts/w5/hwop-0004-00/hardware_execplan_server_v3/
artifacts/w5/hwop-0004-00/hardware_execplan_server_v3.zip
```

v3 保持 Golden、A/B/bias、配置、execplan、350 条前端命令和 9 个 runtime stage 不变，只增加确定性的运行时内存初始化：

- 28 个 P scratch zero payload；
- 56 个 staged-D half zero payload；
- 合计 84 个 runtime scratch payload；
- readback gate 从 86 个 probe 增加到 170 个 probe。

这些 zero payload 是执行前 RAM 初值，不是 Golden P/D 预装；manifest 的 `preloaded_golden_or_output_count` 仍为 0。

推荐服务器使用 `sca_cfg.json`，它显式包含 84 个 scratch zero payload。如果使用 `Bank_data`，必须先清零整个 Bank RAM（或至少逐个清零 `runner_contract.json` 中声明的 runtime scratch range），再 `$readmemb` 覆盖稀疏文件。直接把稀疏 Bank_data 加载到未初始化 RAM 会复现本轮故障。

## 6. 最小测试函数/断言应加在哪里

该报告最初形成时尚未识别服务器 testbench/RTL 源。现已确认源码入口位于`NDP_copy01/`：主Makefile为`NDP_copy01/Makefile.tb_NDP_Top_new_phy`，testbench为`NDP_copy01/tb_NDP_Top_new_phy.sv`，RTL filelist为`NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f`。以下插桩点现在可以直接映射到该testbench；完整文件地图和现状审查见`NDP_copy01/README_HARDWARE_SIM_ENTRY.md`。本轮仍只审查，不修改仿真源码。

### 6.1 preload 结束、启动 command engine 之前

这是最早且最便宜的定位点。对 `runner_contract.json -> preload.readback_gate.probes` 的 170 个地址逐项读取，检查“不含 X 且与 expected 完全一致”。至少打印 P/staged-D 每个 range 的首尾 word。

```systemverilog
if ($isunknown(preload_rdata))
  $fatal(1, "preload X: slice=%0d addr=%h data=%h", slice_id, addr, preload_rdata);
if (preload_rdata !== expected)
  $fatal(1, "preload mismatch: slice=%0d addr=%h exp=%h got=%h",
         slice_id, addr, expected, preload_rdata);
```

### 6.2 slice 输出读返回握手处

在现有 `Local Read Data Monitor` 对应的 `rvalid && rready` 位置，将请求地址和返回值关联，并在 MSE/output RMW 读到 X 时立即失败：

```systemverilog
if (mse_rvalid && mse_rready && $isunknown(mse_rdata))
  $fatal(1, "output RMW read X: slice=%0d line=%h data=%h",
         slice_id, mse_read_line_addr, mse_rdata);
```

这条断言能把故障从“跑到超时”前移到首次坏返回，当前 trace 中应在两个 P line 首次返回时触发。

### 6.3 输出写请求到写数据的 watchdog

当前 56 个 request 全部没有 write-data。写请求被接受后启动小计数器；若限定周期内没有 `wdata_valid && wdata_ready`，打印请求地址、RMW 返回、valid mask 和 MSE/FSM 状态：

```systemverilog
if (wr_req_accepted)
  write_wait_cycles <= 0;
else if (waiting_for_write_data)
  write_wait_cycles <= write_wait_cycles + 1;

if (waiting_for_write_data && write_wait_cycles > WRITE_DATA_TIMEOUT)
  $fatal(1, "write-data stall: slice=%0d addr=%h rmw=%h state=%0d mask=%h",
         slice_id, wr_addr, rmw_data, mse_state, valid_mask);
```

### 6.4 command engine stage-complete 聚合处

只有前三级都无异常且 28 个 slice 均完成后，才继续检查 command engine 的 `all_slice_done -> fetch next exec beat`。应打印每个 slice 的 done 位图、当前 stage index、已消费 beat 和下一 fetch 地址，避免把下游等待误判成 command engine 自身错误。

## 7. 下一轮判定顺序

1. 服务器核对 v3 ZIP SHA；
2. 选择 SCA 路径并确认终端为 `JSON config: 346 matrices loaded`，或 Bank RAM 先清零后加载 Bank_data；
3. `Start_Comp` 前真实回读 170/170 probes；
4. 确认 28 个 slice 的 P 首次 RMW 读取不含 X；
5. 确认出现 output write-data handshake 和 28 个 slice completion；
6. 确认 command engine 连续推进 9 个 stage；
7. 导出 28 份 post-run Bank dump；
8. 再运行 P/D inverse 和三方逐元素比较。

若 170/170 未通过，不启动计算；若通过但 P 仍读 X，故障在回读端口与计算端口所见 RAM 不一致或地址映射；若 P 非 X 但无 write-data，则在 MSE4 写数据生成/FSM；若 slice 全完成但仍 1/9，才定位 command engine 聚合/取下一 stage。

## 8. 证据与身份

- 原始返回压缩包：`sim_results_v2.zip`（继续保留为只读依据）；
- 深度机器报告：`artifacts/w5/hwop-0004-00/hardware_server_run_v2_deep_diagnosis/comparison.json`；
- 深度报告 SHA-256：`f8d32170b9879c56c5a12a80876a4f4c99cc2860f504d37f9a071632be463b61`；
- v3 ZIP：`artifacts/w5/hwop-0004-00/hardware_execplan_server_v3.zip`；
- v3 ZIP SHA-256：`1aa7f79f1534df45aeea9d208bbd401fa3055156bb8fa5667eff572d98344bde`；
- v3 manifest SHA-256：`4be4a4aa824545dfff3bf1fcb0f06e0cd86e38a81f9d19e25c271550c3e73e63`；
- v3 准备报告：`artifacts/w5/hwop-0004-00/hardware_execplan_server_v3_preparation.json`；
- 稀疏 Bank_data 未先清零的负向证据：`artifacts/w5/hwop-0004-00/hardware_execplan_server_v3_bankdata_without_zero_init_negative_check.json`。

最后一项失败是预期的负向检查：它证明“只加载稀疏 Bank_data 到 X RAM”不够，不能把它解释为 v3 SCA 包失败。硬件三方比较仍需等待服务器按上述顺序重跑并返回 post-run dump。
