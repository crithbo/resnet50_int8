# 2026-07-29 服务器对齐 RTL 覆盖与编译首分歧复现

## 授权与来源边界

用户明确要求用服务器版本覆盖本地版本并检测问题。服务器 return 包不携带完整 RTL
源码树，因此本轮采用已经通过 GitHub 登录态下载、且与服务器两份 return 首分歧一致的
`xlsjdjdk/Trassic2.0_RTL` `master` 快照作为“服务器对齐版本”：

- commit：`5f2f8d3a2358c090143caa35957c07ff3650ff4c`
- archive：`C:/Users/15383/Downloads/Trassic2.0_RTL-master.zip`
- archive SHA-256：
  `bdf0ce9f83ba8e0b3e1354bd559f61a4eb3e2a4c6187934c78c880d28e7c3faa`
- RTL source root：`Trassic2.0_RTL/code/NDP_rtl`

本轮授权只允许同步/覆盖，不包含由主线修改功能 RTL。

## 可恢复覆盖

原活动目录没有删除，而是整体移动到：

`NDP_copy01/rtl_pre_server_aligned_5f2f8d3a_20260729`

随后将 GitHub/服务器对齐快照复制为：

`NDP_copy01/rtl`

核验结果：

- source files：2257
- active target files：2257
- backup files：2265
- source 与 active target 逐路径 SHA-256 差异：0
- 备份仍存在，可恢复。

关键活动文件：

- `SA_ALU.v`：
  `42142fb407df4eeb9855b9ed730a1c08eb16d3ab30392ecc3d1e3f9d2abb7f2e`
- `SA_PE_Mul_Array.v`：
  `081eafbbe625104866ec711bec1683b8eb0a28f9a4f8992514429a0c787d27ee`
- `SA_PE_Float_Control.v`：
  `8e9ecb2966943fd3758baf4da592ac0da1b26e6484d60f695d3e70929034f79f`
- `GA_Inport.sv`：
  `da2c6a0af7d08bd87f35e95dfa272e0d7f15425f16d57beb4940b246c8006248`

## 实际编译复现

使用 `C:/iverilog/bin/iverilog.exe`、SystemVerilog-2012、真实
`tests/rtl_audit/int8_sa_stock_dot4_tb.sv`，加载完整 `SA_PE_ALU/*.v` 以及
其 DW/CSA/CLA/FCTLZ/FADDONE 依赖进行 elaboration。

结果：

```text
IVERILOG_EXIT=1
NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v:124:
error: port `slice_rst` is not a port of u_SA_PE_Mul_Array.
1 error(s) during elaboration.
```

这与 node0004 v3 和 GAP node0071 v2 的服务器 VCS return 首分歧一致。由于错误发生
在 elaboration，simulation 没有开始，不能产生任何算子数值或 readback 证据。

另外执行了一个只读对照：保持其余全部服务器对齐源码不变，仅在编译命令中把 callee
临时替换为备份版 `SA_PE_Mul_Array.v`
（SHA-256=`89ea1999ffc4a8a8b1459ba86525664ce78baa19a04179b1154e3635e8d2ff35`）。
同一 Icarus elaboration `exit=0`。这把编译回归定位到该 caller/callee 接口变更，而不是
TB、依赖 filelist 或其他模块。此对照不构成功能放行，因为备份 callee 仍含旧的 INT8
carry 方程。

## 问题位置与代码对照

调用端：

`NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v:124-127`

```verilog
SA_PE_Mul_Array u_SA_PE_Mul_Array(
    .clk       (clk),
    .rst_n     (rst_n),
    .slice_rst (slice_rst),
```

被调用端：

`NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v:1-6`

```verilog
module SA_PE_Mul_Array(
    input clk,
    input rst_n,
    input i_Stall,
```

当前被调用模块没有 `slice_rst` 端口。

备份版本表明这不是长期架构约定，而是一次不完整的接口修改：旧
`SA_PE_Mul_Array.v` 同时包含 `input slice_rst` 和
`else if (slice_rst)` pipeline reset branch；GitHub master 删除了两者，但没有同步删除
`SA_ALU` caller 的连接。同时该 revision 把 INT8 `last_B` 从二次左移形式修为
`carry_int[31:0]`。因此不能简单回退整个文件，否则会把 carry 修复一起撤销。

## 给硬件侧的建议

必须在同一个 commit 中统一 caller/callee 接口。兼容风险较低的方向是：

1. 在 `SA_PE_Mul_Array` 恢复 `input slice_rst`；
2. 恢复所需 pipeline state 的 `else if (slice_rst)` reset 语义；
3. 保留已经修正的 `last_B = carry_int[31:0]`，不要恢复二次 carry 左移；
4. 用活动 NDP filelist 完整 compile/elaborate；
5. 编译通过后原身份重跑 node0004 v3 与 GAP node0071 v2，不重建数值 workload。

另一种做法是从 `SA_ALU` 删除 `.slice_rst` 连接，但这会改变 slice reset 对乘法流水状态
的语义，不能仅以“可编译”为理由采用，需要硬件侧证明 reset/flush 行为仍正确。

## 主线裁决

- `SERVER_ALIGNED_RTL_CALLER_CALLEE_INTERFACE_MISMATCH`：确认。
- 这是 RTL 源码接口错误，不是 Conv/GAP 配置错误，也不是测试包 include 问题。
- 当前首编译错误关闭前，不生成新包，不重复数值分析。
- 修复该首分歧后仍需完整 compile；不能提前声称不存在后续编译错误。
- 功能 RTL 修改数：0。

机器合同：

`contracts/rtl_sync/trassic2_server_aligned_5f2f8d3_install_and_compile_v1.json`
