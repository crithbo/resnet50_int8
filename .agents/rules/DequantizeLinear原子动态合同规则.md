# DequantizeLinear 原子动态合同规则

最后更新：2026-07-26

本文件只约束 `node-0077 / hwop-0077-00` 的最小 stock-TB 动态诊断身份。完整算子数值、
GA 拓扑和正式 E4/E5 门仍由 `DequantizeLinear算子配置规则.md` 唯一拥有。

## CDA-DEQUANT-ATOMIC-STOCK-TB-001

全量 node0077 曾在 stock RTL 上出现 28/28 slice `Start Comp`、0/28 `Comp Finish`。
旧 atomic v1 随后自然完成，但动态证据证明其继承的 v5 D buffer-loop 并未闭合。
旧 v5 与 atomic v1 均冻结为失败证据，不再作为“已闭合配置”或新候选的派生源。

修正后的 atomic 身份仍采用：

```text
logical occurrence count = 1
active physical slices = [0, 1]
used_slices = 0b0000000000000000000000000011
Repeat_Num = 1
per-slice shape = CWH [16, 1, 1]
```

slice0+slice1 是活动 stock TB 固定观察 slice0 Start、slice1 Finish 所需的最小 mask，
不代表两个 ONNX 节点或两个 stage。

修正后的完整 Dequant 配置必须先满足
`CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001`，即保留
`GROUP2.ROW_LC.end=4`。atomic 再只允许相对该修正版完整配置改变下列
schedule/address leaf：

- `DRAM_LC.LC1.end: 47 -> 1`
- `DRAM_LC.LC3.end: 47 -> 1`
- A stream shape stride：`[16,16,752] -> [16,16,16]`
- D stream shape stride：`[64,64,3008] -> [64,64,64]`
- address-bound A/D base：分别为 `0x00000000`、`0x00000010`

其余 LC/LC_PE、Buffer、GA、conversion、normal outbuffer、transaction、bank/column、
constant 和 opcode leaf 必须与修正版完整配置逐项一致。不得把
`GROUP2.ROW_LC.end` 缩回 1，不得引入 transout、padding、tail、第二输入、
跨 block feedback 或功能 RTL/TB 修改。

每片输入必须是 16 个确定的 UINT8 值，同时覆盖：

- `0`、`255`
- 小于、等于、大于 zero-point 60
- `59/60/61`

slice1 必须是 slice0 的可验证排列，避免两个 slice 数据不可区分。golden 仍严格执行：

```text
q = float32(uint8(x)) - float32(60)
D = float32(q * float32(bits=0x3e01622d))
```

每 slice：

- A preload：16 bytes / 1 个 128-bit line；
- D formal readback：64 bytes / 4 个 128-bit line；
- accepted MSE4 write：地址 `0x10,0x20,0x30,0x40`，共 4 beat。

全包预期 2 个 A preload、2 个 formal D、8 个 accepted MSE4 write、一次
Start/Finish。必须同时验证：

1. slice0、slice1 均实际 start/finish；
2. 只读 observer 按 `slice_id + 同一地址域` 核对 8 个 accepted write；
3. 两份正式 D 各 4 行、逐 bit 对独立 golden；
4. stock TB 自然进入 SCA_D 并退出；
5. TB 和任意 `rtl/**` 均不修改，禁止 force/deposit、缩短内部 timeout 或驱动式
   observer。

上述证据分为两个正交门：

- `ATOMIC_FUNCTIONAL_SEMANTICS_PASS`：自然 start/finish、stock RTL 身份稳定，且
  输出区未 preload、地址无 alias、正式 D 8 行全覆盖并逐 bit 对 golden；
- `ATOMIC_TEMPORAL_DRAIN_PASS`：只读 observer 另行证明每片 4 个 accepted write，
  且 finish 当周期 address/data outstanding 均为 0。

只有两门都通过才能称 `ATOMIC_CONTRACT_FULL_PASS`。第一门通过而第二门因 observer
漏记、地址域误比或解耦握手配对失败时，分类必须是
`ATOMIC_FUNCTIONAL_PASS_OBSERVER_TEMPORAL_EVIDENCE_INCOMPLETE`：它足以确认最小
CWH16 的配置、码流、算术和最终写回数值路径，并允许进入完整 node0077 E4；但不把
observer 缺口写成硬件通过，也不解除完整 E4/E5 blocker。具体 observer 约束遵循
`CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001`。

observer 若同时报告地址生成前的 linear address 与 remap/路由后的 local request
address，必须分栏保存并各自在同一地址域比较；不得把 post-remap raw address
直接与 pre-remap golden word address 比较。`slice_cmpt_finish` 也不能单独证明
writeback 完成：finish 当周期必须同时满足本 slice 已接受 4 个 MSE4 write，
address/data outstanding 均为 0，随后正式 D 四行均非 `x` 且逐 bit 正确。

RTL/支持文件身份门必须以规范化布尔事实
`functional_rtl_unchanged=true`、`tb_probe_transactionally_restored=true`
及各 focused/support identity 为准。不得因 receipt 的合法状态字符串新增或改名，
却仍硬编码比较旧字符串而产生伪失败。

## CDA-DEQUANT-ATOMIC-V1-DYNAMIC-EVIDENCE-001

`dq_node0077_atomic1_stock_v1` 的正式回传只作失败定位证据：

- compile/sim/run 均为 0，stock TB 自然进入 SCA_D 并退出；
- slice0、slice1 均 start/finish；
- 每片仅 1 个 accepted MSE4 write，且该首 beat payload 与独立 golden 逐 bit
  相同；
- 每片正式 D 仅首行正确，后 3 行均为 `x`；
- finish 当周期每个 MSE4 channel 仍有 outstanding address。

该证据证明首 4 个元素已经通过 A read、`uint8tofp32`、GA add、GA mul、
normal outbuffer 和首个 MSE4 write；它不证明剩余 12 个元素或完整 CWH16。

最早配置分歧为旧 v5/atomic v1 的 `GROUP2.ROW_LC.end=1`，而可信原生配置、
`buffer5.buf_end_row_addr=3`、64-byte D transaction 与 16-byte
`buf_spatial_size` 共同要求该值为 4。由此产生：

```text
仅 1 个 16-byte D buffer row
-> 首个 write-data beat 携带 last
-> slice_cmpt_finish 提前
-> 后 3 个 128-bit D line 未写入
```

最终分类为
`DEQUANT_CONFIG_D_BUFFER_ROW_UNDERSUPPLY_EARLY_LAST`，主责任域为
`CONFIG_SEMANTICS`。在修正配置重新动态验证前，不得将该现象定性为功能 RTL
completion 缺陷，也不得原样重跑 atomic v1。

该包只用于定位全量 Dequant 的首个动态分歧：

- 无 A request/data → A/MSE-read 子路径；
- A 正确但 GA 无输出 → GA add→mul/normal-outbuffer 子路径；
- GA 输出正确但无 D write → MSE4 writeback 子路径；
- D write 正确但无 finish → completion/tag 子路径。

即使全部通过，也只证明最小 CWH16 合同，不计完整 node0077 E4/E5，不解除
`B_DEQUANT_SERVER_E4_E5`，并保持 `candidate_release=false`。

## CDA-DEQUANT-ATOMIC-V3-DYNAMIC-EVIDENCE-001

`dq_node0077_atomic1_stock_v3` 是修正 D buffer supply 且通过 XMR elaboration 静态门
后的首个自然完成身份。正式回传裁决如下：

- package SHA256 为
  `f77d92165cc32af41e157da27ce4b7141882c8d49871961cab22a41ba668742c`，
  return SHA256 为
  `b08755adfb3dd0665f34d9a0f320accdd9506ac043f7896eab8c62e1ad02e256`；
- compile/sim/run 均为 0；slice0、slice1 均自然 start/finish，stock RTL、TB 和
  observer 的五阶段身份门通过；
- SCA 只在每片 word 0 preload 一行 A；D 从 word 1 开始，未预置 golden，也无
  输出地址 alias；
- 两片正式 D 各 4 行、共 8 行均非 `x`，并逐 bit 等于独立 golden；这动态确认了
  `GROUP2.ROW_LC.end=4` 的 4-row D supply、完整 CWH16 两级 GA 算术、
  normal outbuffer、MSE4 最终写回和 SCA_D 路径；
- v3 observer 仅配对出每片第 1、4 beat。其 pending-address 队列只在
  `mem_ag_ob_chl_wr_hs && mem_ag_ob_bp_pre_barrier` 时入队，却对每个解耦的
  `local_req_hs/local_wdata_hs` 出队，产生
  `missing_pre_remap_address`/`accepted_wdata_without_address`，并丢弃中间
  write-data 证据；这与完整 bit-exact formal D 正交；
- observer 的 expected JSON 使用 slice-local word `[1,2,3,4]`，而其
  `linear_addr` 已加 stream base。slice1 的 `0x200001..0x200004` 必须先减
  `0x200000` 或给期望加 base，不能直接与 `[1..4]` 比较；
- observer 未记录 `STAGE_FINISH` 汇总，因此本回传没有关闭 finish 当周期
  accepted/outstanding 的精确时序门。

最终分类为
`ATOMIC_FUNCTIONAL_PASS_OBSERVER_TEMPORAL_EVIDENCE_INCOMPLETE`。该结果关闭最小
Dequant 功能语义门并允许转入由 v6 完整资产重建的 node0077 E4；它不计完整 E4/E5，
不解除 `B_DEQUANT_SERVER_E4_E5`，也不得称为正式 target config。
