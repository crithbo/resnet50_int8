# Conv/SA RTL 可编译性穷尽审计（GitHub master 1c49bd1）

日期：2026-07-29

## 边界

本次只读审计以下 GitHub master 快照：

```text
commit 1c49bd1155a89ff187e29016dc4415e59a55f991
Trassic2.0_RTL_master_1c49bd1_audit/Trassic2.0_RTL-master/code/NDP_rtl
```

没有修改 `NDP_copy01/rtl`、GitHub 快照原件、功能 RTL、公共规则或
`.agents/plan.md`。唯一临时源码修补位于：

```text
outputs/conv_sa_rtl_compile_audit_1c49bd1/diagnostic_rtl_copy/NDP_rtl
```

没有生成或运行算子服务器包，没有重复 node0004 数值分析。

活动收据：

- plan mutable provenance：
  `fbe18d59d34ed9e7ba99b2a70fc147ff69a5de3731803aa81102d8af2f534ec2`；
- 生成前索引：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`；
- INT8 SA 规则：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`；
- 服务器包规则：
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`。

## 十个 changed files

与上一只读 master 快照 `Trassic2.0_RTL/code/NDP_rtl` 逐文件 SHA-256
比较后，差异恰好为十项，全部位于 SA ALU 族：

1. `Slice/Specialized_Array/SA_PE/SA_PE_ALU.sv`
2. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v`
3. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v`
4. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_CSA.v`
5. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Expadj.v`
6. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Expdiff.v`
7. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Last.v`
8. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_LZA.v`
9. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_SHT.v`
10. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v`

十项完整 base/new SHA、改动行、端口/依赖结论和算子影响记录在机器报告
`outputs/conv_sa_rtl_compile_audit_1c49bd1/report.json`。

## 唯一确定的 changed-set 编译错误

文件：

```text
Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v
```

物理源码第 50–51 行：

```verilog
    output              o_AddNZero,
    output[1:0]         o_Config,
   );
```

`o_Config` 已经是 ANSI port list 的最后一项，却仍保留逗号。解析器因此期待
后续 port，遇到第 51 行 `)` 时失败。服务器 VCS 报：

```text
SA_PE_Float_Control.v:51: token is ')'
```

独立 Icarus 复现为：

```text
SA_PE_Float_Control.v:50:
Superfluous comma in port declaration list
```

因此“line 51 trailing comma”应精确表述为：错误 token 报在第 51 行闭括号，
真正多余的逗号位于第 50 行 `o_Config,`。

最小修复方向只是一处：

```diff
-    output[1:0]         o_Config,
+    output[1:0]         o_Config
```

不得改 port 名、位宽、顺序、闭括号或功能语句。

该文件属于公共 NDP top filelist。Conv 直接使用 SA 数据路；GAP 与 QAdd 即使计算
走 GA，也会在公共 top 编译阶段解析该文件。因此该语法错误同时阻断
Conv/GAP/QAdd 的服务器 compile。

## 逐错暴露结果

只在诊断副本去掉该逗号后，以真实 `vcs_utils_filelist.f` 和 SA filelist
闭包执行：

| 顶层 | 语言模式 | source 数 | 结果 |
|---|---|---:|---:|
| `SA_ALU` | SystemVerilog 2012 | 32 | PASS |
| `SA_PE_ALU` | SystemVerilog 2012 | 32 | PASS |
| `SA_PE` | SystemVerilog 2012 | 32 | PASS |
| `SA_PE_Group` | SystemVerilog 2012 | 33 | PASS |
| `SA_PE_Group` | SystemVerilog 2005 | 33 | PASS |

所有 PASS 均为零编译错误、零 elaboration 错误、零 `-Wall` 消息。

静态闭包同时确认：

- 十个 changed files 在 `NDP_Top_phy_filelist.f` 递归闭包中各出现一次；
- changed modules 和其 `DW02_mult`、`DW01_add`、`CSA_3to2`、
  `CSA_4to2`、`CLA`、`F_64BIT_CTLZ`、`F_32BIT_ADDONE` 依赖均唯一；
- conflict marker 为 0；
- 唯一 include `NDP_Parameters.svh` 存在且唯一；
- `SA_ALU→Mul_Array/CSA/...` 的新 `slice_rst`、`i_SignC`、
  `i_Sub_int8`、`o_SignC` named ports 全部匹配；
- `SA_PE→SA_PE_ALU→SA_ALU` 与
  `Specialized_Array→SA_PE_Group→SA_PE` 的上层端口名一致；
- 未发现第二项能确定阻止 VCS compile/elaboration 的 changed-set
  module、port、位宽、类型、重复/缺失 module/include/macro 问题。

## 工具边界

继续把 Icarus 顶层提升到 `Specialized_Array` 时，首错来自未改文件
`SA_Outport.sv:45-48` 的动态 packed-array index；提升到 `Slice_Wrapper`
时还会遇到未改 GA/IGA 的 Icarus SystemVerilog 支持边界。这些不是十个
changed files 的错误，也没有被分类为 VCS 缺陷。

因此本次可证明的结论是：

```text
confirmed changed-set compile blocker = 1
additional deterministic changed-set blocker = 0
highest local dynamic elaboration pass = SA_PE_Group
```

本地没有 VCS，故硬件组仍须在去掉逗号后跑一次活动完整 VCS
filelist compile/elaboration；不得把 Icarus 的上层工具边界当成 VCS
通过或失败。

## 交付

- 机器报告：
  `outputs/conv_sa_rtl_compile_audit_1c49bd1/report.json`
- 最小诊断 diff：
  `outputs/conv_sa_rtl_compile_audit_1c49bd1/diagnostic_only_remove_trailing_comma.diff`
- 原始失败与逐级 PASS 日志：
  `outputs/conv_sa_rtl_compile_audit_1c49bd1/compile_steps/`

`PACKAGE_RELEASE=NONE`。
