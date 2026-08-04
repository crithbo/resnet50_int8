# GA INT8 pipeline0 缺少 downstream-ready 分支

## 1. 问题概述

General Array 的第一级 ALU pipeline 为 INT32 和 FP32 定义了 downstream-ready 条件，
但没有 INT8 分支。第一个 INT8 token 进入 pipeline0 后无法被清除或覆盖，第二个 token
只能停在输入缓冲，随后上游被反压。

INT8 最大值比较器的数值结果本身是正确的；本报告只讨论连续数据流无法前进的问题。

## 2. RTL 文件与信号路径

云端仓库相对路径：

```text
code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv
```

关键位置：

```text
GA_PE_Inbuffer.sv:527-529
GA_PE_Inbuffer.sv:531-557
GA_PE_Inbuffer.sv:200-213
```

信号链：

```text
opcode dtype decode
→ alu_is_int8
→ alu_pipeline0_bp_post
→ ga_pe_alu_pipeline0_clear / enable
→ pipeline0_valid
→ input-buffer bp_pre
```

## 3. 当前错误代码

类型识别本身包含 INT8：

```verilog
assign alu_is_fp32  =
    (!ga_pe_alu_opcode[4] & !ga_pe_alu_opcode[3])
    | ga_pe_alu_opcode[4];

assign alu_is_int32 =
    !ga_pe_alu_opcode[4]
    & ga_pe_alu_opcode[3]
    & ga_pe_alu_opcode[2];

assign alu_is_int8  =
    !ga_pe_alu_opcode[4]
    & ga_pe_alu_opcode[3]
    & !ga_pe_alu_opcode[2];
```

但 downstream-ready 方程只有：

```verilog
assign alu_pipeline0_bp_post =
       (alu_is_int32 && ga_pe_inbuffer_bp_post)
    || (alu_is_fp32  && ga_pe_alu_pipeline1_enable);
```

缺少：

```text
alu_is_int8 对应的 ready 条件
```

而 pipeline0 的状态更新完全依赖 `alu_pipeline0_bp_post`：

```verilog
assign ga_pe_alu_pipeline0_clear =
    !alu_input_valid_bit && alu_pipeline0_bp_post;

assign ga_pe_alu_pipeline0_enable =
    !alu_pipeline0_valid_bit || alu_pipeline0_bp_post;
```

因此 pipeline0 一旦装入 INT8 token，便无法通过 downstream-ready 正常释放。

## 4. 正确计算语义

只要 INT8 结果的下一接收级可以接受数据，pipeline0 就必须允许：

- 当前 token 前进；
- valid 清除或被下一个 token 覆盖；
- ready 反馈给 input buffer。

语义上必须满足标准 ready/valid 不变量：

```text
pipeline_valid && downstream_ready
→ 当前 token 被接受
→ pipeline 可在下一拍接收新 token
```

具体修复表达式应与 INT8 实际后级连接一致，不能机械照搬 INT32/FP32 分支。

## 5. ResNet50 中必须使用该功能的计算

ResNet50 首层 MaxPool 对 UINT8 feature map 执行3×3、stride2最大值归约：

```text
input  : [N, 64, 112, 112]
output : [N, 64,  56,  56]
```

每个输出都需要连续接收多个输入值并更新局部最大值。一次完整推理包含大量 INT8 token，
不可能只靠单个 token 完成。

因此，即使单次 `max(A,C)` 的数值比较正确，只要第二个输入无法进入流水线，MaxPool 就
无法完成任何正常窗口，更不可能完成整个 feature map。

## 6. 最小错误案例

保持 downstream 可接受：

```text
ga_pe_inbuffer_bp_post = 1
```

第一个 INT8 token 进入 pipeline0 后：

```text
pipeline0_valid   = 1
pipeline0_bp_post = 0
pipeline0_enable  = 0
pipeline0_clear   = 0
```

第二个 token 到达时：

```text
input_buffer_matched = 1
input_buffer_bp_pre  = 0
```

第二个 token 停在 input buffer，不能进入 pipeline0；第三个及后续 token 被反压。

在相同 downstream 条件下：

```text
INT32: pipeline0_bp_post=1, pipeline0_enable=1
FP32 : pipeline0_bp_post=1, pipeline0_enable=1
```

这证明缺口只出现在 INT8 分支。

## 7. 对网络结果的影响

可能表现为：

- MaxPool 启动后不自然结束；
- 只有极少量内部 token 被处理；
- 没有完整 output writeback；
- 上游持续被 backpressure；
- 测试超时或输出保持未写状态。

它是数据流停滞问题，而不是可由 output golden 容差接受的数值误差。

## 8. 修复验收条件

最低验收应包含：

1. 连续至少三个 INT8 token 无气泡输入；
2. downstream ready 恒1时每拍均能前进；
3. downstream 随机 stall 后能够恢复；
4. pipeline valid、clear、enable 和 input `bp_pre` 满足 ready/valid 协议；
5. 多 token `int8_max` 数值顺序正确；
6. 完整3×3窗口；
7. 完整112×112到56×56 MaxPool；
8. 输出 token 数、last/last_index 和 writeback 全部正确。

