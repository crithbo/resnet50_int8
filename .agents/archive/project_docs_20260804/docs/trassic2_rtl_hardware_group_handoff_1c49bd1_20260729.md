# Trassic2.0 RTL 剩余问题审查报告

审查对象：`xlsjdjdk/Trassic2.0_RTL` `master`
`1c49bd1155a89ff187e29016dc4415e59a55f991`

用途：提交硬件组修复。本文只报告能够由当前 GitHub 源码、服务器
VCS 日志或本地定向 RTL 仿真相互印证的问题；不会把 Icarus 对加密
DDR 模型、unpacked array、generate scope 等支持限制误报为 RTL
问题。

## 1. 结论摘要

当前确认有两项需要修复、一项既有 MaxPool 动态阻塞仍然存在：

| 优先级 | 性质 | 位置 | 当前影响 |
|---|---|---|---|
| P0 | 确定的语法错误 | `SA_PE_Float_Control.v:50-51` | 公共 NDP top 编译失败，Conv、GAP、QAdd 等测试均无法启动 |
| P1 | 确定的 INT32 全域算术错误 | `SA_PE_Float_CSA.v:49-50`，关联 `SA_PE_Float_Control.v:185-190` | `INT32_MIN` 和负数精确抵消边界结果错误；当前 ResNet50 冻结数据尚未证明命中 |
| P1 | 确定的 INT8 MaxPool 流水停滞 | `GA_PE_Inbuffer.sv:527-557` | `int8_max` 连续输入在第二项后停止前进，MaxPool 可能无法自然完成 |

另有一项 reset/X 风险位于 `SA_PE_Mul_Array.v:184-236`，但尚未证明
这些 X/旧值能够越过上层 valid/tag 门成为正式 accepted output，
因此不列为确定的 ResNet50 blocker。

删除 P0 尾逗号后，最新提交涉及的 10 个 SA 文件在
`SA_ALU -> SA_PE_ALU -> SA_PE -> SA_PE_Group` 范围内没有发现第二个
确定的模块、端口或位宽编译错误。完整生产 VCS top 仍必须由硬件组
实际运行确认。

## 2. P0：SA_PE_Float_Control 端口表尾逗号

GitHub 相对路径：

```text
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v
```

问题位置：第 50–51 行。

当前代码：

```verilog
    output              o_AddNZero,
    output[1:0]         o_Config,
   );
```

`o_Config` 已经是 ANSI 端口列表的最后一项，但后面仍保留逗号。
解析器会继续等待下一个端口，遇到 `)` 后报语法错误。服务器两次新
return 均在这里停止：

- Conv node0004：`compile_exit=2`，`run_exit=125`，
  simulation 未启动，正式 readback `0/320`；
- GAP node0071：`compile_exit=2`，simulation 未启动，正式
  readback `0/48`。

VCS 报错 token 在第 51 行的 `)`；Icarus 对同一源码给出的更直接
诊断为：

```text
SA_PE_Float_Control.v:50:
Superfluous comma in port declaration list
```

最小修复：

```diff
-    output[1:0]         o_Config,
+    output[1:0]         o_Config
```

只需删除逗号，不应修改端口名、位宽、顺序或功能代码。

为什么所有算子都受影响：即使 GAP/QAdd 的计算主体走 GA，服务器
仍通过公共 NDP top filelist 编译 SA 源码，所以这一处语法错误会在
算子配置被执行前阻断整个仿真。

## 3. P1：负 INT32 psum 的全域重构错误

GitHub 相对路径：

```text
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_CSA.v
```

问题位置：第 49–50 行。

当前代码：

```verilog
assign o_IntResult[30:0] =
    i_SignC ? ~c_Result0_wire + 1'b1 : c_Result0_wire;
assign o_IntResult[31] = c_Result0_wire[31];
```

相关负数幅值编码位于：

```text
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v:185-190
```

```verilog
assign DataC_int32_unsigned =
    gr_DataC[31] ? ((~gr_DataC[30:0]) + 1'b1) : gr_DataC[31:0];
```

问题不是普通正负数乘加，而是内部负 psum 使用“符号 + 幅值”后，
结果又只对低 31 位取反，最高位仍复制取反前的值。这样会丢失两个
modulo-2^32 边界：

1. `C=-5`，四路点积和为 `+5`
   - 期望：`0x00000000`
   - RTL：`0x80000000`
2. `C=INT32_MIN (0x80000000)`，点积为 `0`
   - 期望：`0x80000000`
   - RTL：`0x00000000`

第 2 个反例还直接暴露了 `DataC_int32_unsigned` 只对低 31 位取补码
造成的 `INT32_MIN` 幅值溢出。

诊断副本中已经验证的一种完整 32 位重构方式为：

```verilog
assign o_IntResult = i_SignC
    ? (~(c_Result0_wire ^ 32'h80000000) + 32'd1)
    : c_Result0_wire;
```

该表达式只是经测试的修复候选，硬件组仍应结合内部编码约定审核。
候选修复通过：

- 两个上述最小反例；
- 普通正/负 psum、跨零、正负 wrap；
- 四路乘积正负极值；
- 20,000 个确定性随机 `s8 × u8 dot4 + int32 psum` 向量。

影响边界：这是通用 INT8 MAC 的全域正确性错误，但当前已冻结的
ResNet50 Conv/GAP W3 数据没有观察到这两个精确边界，故它不是
当前服务器仿真无法启动的原因，也不能用它解释本次 Conv/GAP
compile failure。

## 4. P1：MaxPool 的 INT8 pipeline0 ready 分支缺失

GitHub 相对路径：

```text
code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv
```

类型识别在第 527–529 行：

```systemverilog
assign alu_is_fp32  =
    (!ga_pe_alu_opcode[4] & !ga_pe_alu_opcode[3]) |
    ga_pe_alu_opcode[4];
assign alu_is_int32 =
    !ga_pe_alu_opcode[4] & ga_pe_alu_opcode[3] &
    ga_pe_alu_opcode[2];
assign alu_is_int8  =
    !ga_pe_alu_opcode[4] & ga_pe_alu_opcode[3] &
    !ga_pe_alu_opcode[2];
```

但 pipeline0 的 downstream-ready 方程在第 554–557 行只有 INT32
和 FP32：

```systemverilog
assign alu_pipeline0_bp_post =
       (alu_is_int32 && ga_pe_inbuffer_bp_post)
    || (alu_is_fp32  && ga_pe_alu_pipeline1_enable);
assign ga_pe_alu_pipeline0_clear =
    !alu_input_valid_bit && alu_pipeline0_bp_post;
assign ga_pe_alu_pipeline0_enable =
    !alu_pipeline0_valid_bit || alu_pipeline0_bp_post;
```

缺少 `alu_is_int8` 分支。最新 `1c49bd1` 文件 SHA-256 仍为：

```text
25fa4dd2c6fe8301bc3651d660df72059ea2787c0c26a2841a1d4e439586b518
```

定向仿真使用 `int8_max` opcode、downstream ready=1：

```text
首个 token 后:
P0_VALID=1 P0_BP_POST=0 P0_ENABLE=0 P0_CLEAR=0

第二个 token:
IB_MATCHED=1 BP_PRE0=0 P0_ENABLE=0
```

作为对照，INT32 和 FP32 同条件下
`P0_BP_POST=1, P0_ENABLE=1`，可以继续推进。

这说明 INT8 第一个 token 把 pipeline0 valid 置 1 后，因为
`bp_post` 永远为 0，pipeline0 既不能 clear 也不能接收下一项；
第二项进入 inbuffer 后，输入反压拉低，连续归约停滞。ResNet50
node0002 MaxPool 必须连续消费窗口元素，因而会直接涉及该问题。

修复方向：在 pipeline0 ready/clear/enable 方程中补齐 INT8
消费路径。根据当前 `ga_pe_alu_result_tag` 第 587–589 行，INT8
结果使用 `alu_input_*`，不是 FP32 的 pipeline1 tag；因此候选方向
是把 INT8 与实际 outbuffer/downstream ready 绑定。但最终表达式
应由硬件组结合 GA_ALU 时序和 outbuffer handshake 决定，不能只
为让仿真前进而常量置 1。

必须保留的回归：

1. 连续至少 3 个 INT8 token，downstream ready=1；
2. downstream ready=0 时不能丢 token；
3. ready 恢复后顺序、last、last_index 不变；
4. 同一修复不得改变 INT32/FP32 路径；
5. 完整 MaxPool 窗口应自然 terminal，正式 D 无缺失。

## 5. 仅风险：SA 乘法阵列的数据寄存器未清零

GitHub 相对路径：

```text
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v
```

第 184–209 行只对控制寄存器处理 `rst_n/slice_rst`；第 210–236
行的数据寄存器使用 `always @(posedge clk)`，没有 reset 分支，
且 `slice_rst` 与 `i_Stall` 同周期时仍可写入。

standalone probe 可观察到：

- 全局 reset 后局部结果为 X；
- slice reset 后旧数据仍保留；
- `slice_rst+i_Stall` 可捕获“幽灵数据”。

但当前证据尚未证明上层 valid/tag 会把这些值作为正式输出接受。
因此本项只要求硬件组确认以下合同，不应先写成 ResNet blocker：

- reset 周期和 reset 后首个无效周期的 result 必须被 valid/tag
  完全屏蔽；
- 若不能证明屏蔽，则数据寄存器也必须受 `rst_n/slice_rst`
  清理，并补 flush/backpressure 回归。

## 6. 已排除或已验证的事项

- 最新提交中旧 `SA_ALU -> SA_PE_Mul_Array.slice_rst` 端口不一致
  已恢复闭合；删除尾逗号后 focused elaboration 通过。
- 18-bit dot4 CSA、carry 去重移位、DataC 普通正负累加通过正负
  极值和 20,000 个随机向量；没有重新发现此前的 4→6、DataC
  被清零、signed17 截断问题。
- 10 个最新变更文件均在活动 filelist 中各出现一次，相关 module
  和 include 定义唯一，未发现 merge conflict marker。
- Icarus 不支持 VCS 加密 DDR `.vp`、部分 unpacked localparam
  assignment pattern、generate 动态索引等；这些属于工具边界，
  不列为硬件修复项。

## 7. 硬件组建议执行顺序

1. 先删除 `SA_PE_Float_Control.v:50` 的尾逗号。
2. 用生产 VCS 的真实 filelist 完整 compile，要求 exit 0。
3. elaborate 实际 NDP top，要求 exit 0。
4. 做 start-only smoke，至少进入 clock/reset 和 testbench。
5. 修复并回归 INT32 负 psum 的两个边界反例。
6. 补齐并回归 MaxPool INT8 pipeline0 handshake。
7. 审核 SA 乘法阵列 reset 数据路径是否由上层 valid/tag 完全屏蔽。
8. 用原身份重跑 Conv node0004 v3、GAP node0071 v2 和 MaxPool
   原始 GitHub JSON 测试包；无需因 RTL 修复重建 workload。

注意：本次 Conv/GAP return 均缺相邻 `.sha256` sidecar，所以即使
后续日志成功，正式回传仍应同时提供 ZIP 和匹配 sidecar。

## 8. 审查边界

- 没有修改 GitHub 快照原件或活动 `NDP_copy01/rtl`。
- 所有试修仅存在于 `outputs/` 隔离诊断副本。
- 本地没有生产 VCS，不能声称完整 top 已通过。
- 没有上传、运行服务器、修改测试包或取得 lease。

