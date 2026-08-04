# GA INT8 pipeline0 反压缺口与触发范围报告

日期：2026-07-23  
结论等级：本地 RTL 静态确定；node-0002 与小尺寸原生 INT8 MaxPool 均在服务器复现同类停滞；服务器 RTL/filelist 身份和修复后反事实复测仍待确认。  
适用范围：`General Array / GA_PE_Inbuffer` 的 INT8 opcode 类，不代表所有 INT8 数据、所有 INT8 算子或所有 NDP 计算单元。

## 1. 核心结论

当前本地 RTL 的 `GA_PE_Inbuffer.sv` 在 pipeline0 的下游反压选择中只覆盖：

- INT32：使用 `ga_pe_inbuffer_bp_post`；
- FP32：使用 `ga_pe_alu_pipeline1_enable`。

它没有覆盖 `alu_is_int8`。因此，一个启用的 General Array PE 只要满足以下条件：

1. ALU opcode 被分类为 GA INT8；
2. PE 收到第一个有效输入，使 `alu_pipeline0_valid_bit` 置 1；
3. 同一算子执行期间没有 `slice_rst`；
4. 算子还需要接收第二个或后续有效输入；

pipeline0 就不能再 enable 或 clear，上游 ready 被撤销，后续归约输入无法继续进入。需要连续消费多个输入的 GA INT8 MaxPool 因而会停在结果写回之前。

这不是“输出字节不足以填满 buffer 才不输出”，也不是 INT16/INT32 转 INT8 时的尾包刷新问题；当前缺口在 GA pipeline0 的 valid/ready 控制中，发生在完整结果形成之前。

## 2. 精确触发条件

### 2.1 必须同时满足

| 条件 | 判定方法 | 当前 MaxPool |
|---|---|---|
| 使用 General Array | 配置写入 `general_array.PE_array`，运行经过 `GA_PE_Inbuffer` | 是 |
| PE 被启用并收到有效输入 | `ga_pe_enable=1` 且 `alu_input_valid_bit=1` | 是 |
| opcode 属于 GA INT8 类 | `ga_pe_alu_opcode[4:2] == 3'b010` | 是 |
| 同一执行需要第二项或更多输入 | 第一次输入后仍有窗口/归约数据需要接收 | 是 |
| 中间没有 reset 清除 valid | `rst_n`、`slice_rst` 均不在每项输入之间触发 | 正常执行不会逐项 reset |

只有输入 tensor 的 dtype 写成 `int8` 或 `uint8`，并不足以触发。真正决定是否进入缺口的是 **GA ALU opcode**。

### 2.2 当前工具链中等价于 `int8_max`

RTL 的类型译码为：

```systemverilog
assign alu_is_fp32  = (!ga_pe_alu_opcode[4] & !ga_pe_alu_opcode[3])
                    | ga_pe_alu_opcode[4];
assign alu_is_int32 = !ga_pe_alu_opcode[4] & ga_pe_alu_opcode[3]
                    &  ga_pe_alu_opcode[2];
assign alu_is_int8  = !ga_pe_alu_opcode[4] & ga_pe_alu_opcode[3]
                    & !ga_pe_alu_opcode[2];
```

所以数值为 8～11、即 opcode 高三位为 `010` 的配置都会被 RTL 归入 INT8 类。但当前原生编码器只定义并接受其中一个正式 opcode：

```text
int8_max = 11 = 5'b01011
```

数值 8、9、10 当前没有正式符号定义，也不是现有原生算子。因而在当前仓库和工具链中，“进入该缺口”实际等价于“General Array PE 使用 `int8_max`”。

### 2.3 状态如何锁住

问题逻辑位于
`NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv:554-557`：

```systemverilog
assign alu_pipeline0_bp_post      = (alu_is_int32 && ga_pe_inbuffer_bp_post)
                                 || (alu_is_fp32  && ga_pe_alu_pipeline1_enable);
assign ga_pe_alu_pipeline0_clear  = !alu_input_valid_bit
                                 && alu_pipeline0_bp_post;
assign ga_pe_alu_pipeline0_enable = !alu_pipeline0_valid_bit
                                 || alu_pipeline0_bp_post;
```

代入 `int8_max=5'b01011`：

```text
alu_is_fp32             = 0
alu_is_int32            = 0
alu_is_int8             = 1
alu_pipeline0_bp_post   = 0
```

随后状态为：

1. 复位后 `alu_pipeline0_valid_bit=0`，所以 `pipeline0_enable=1`；
2. 第一个有效输入被接收，下一拍 `alu_pipeline0_valid_bit=1`；
3. `pipeline0_enable=!1||0=0`；
4. `pipeline0_clear=...&&0=0`；
5. valid 既不能被正常消费清除，也不能让 pipeline0 装载下一项；
6. `GA_PE_Inbuffer.sv:207` 又用该 enable 生成上游 `bp_pre`，于是后续有效输入停止推进。

对于只需一个输入、并能在 reset 前结束的特殊用法，静态代码不能单独证明一定挂死；真正确定的触发边界是**同一 PE 在一次执行中需要连续接收至少两个有效输入**。现有 MaxPool 配置的 `transout_last_index=3`，显然属于多输入归约。

### 2.4 与 ping-pong、buffer 填满无关

两份原生 MaxPool 配置中：

- 两个 stream 的 `ping_pong` 均为 0；
- 三个 GA inport 的 `pingpong_en` 均为 0；
- 8 个 `int8_max` PE 的 `transout_last_index` 均为 3。

因此关闭 ping-pong 不会绕开本缺口。即使下游 buffer 有空间，`alu_pipeline0_bp_post` 在 INT8 条件下仍为常量 0。

## 3. 当前会触发的算子和实例

对活动 `ndp-sim` 的 53 份 Git 跟踪 `jsons/*.json` 扫描后，只有两份配置包含 `int8_max`，每份都有 8 个 GA PE 命中该路径。
两份配置中的 PE 位置相同：`PE00`、`PE02`、`PE10`、`PE12`、`PE20`、`PE22`、`PE30`、`PE32`。

| 算子/配置 | 形状与用途 | 当前证据 | 判定 |
|---|---|---|---|
| `maxpool_config_16_112_112_stride2_padding1.json` | UINT8 MaxPool，`112×112×16 → 56×56×16`；ResNet50 `node-0002` | 更新 testbench 后曾观察到 28 slice 有读返回和写地址、但写数据为 0 且不自然完成 | **已触发路径；硬件现象与缺口一致** |
| `maxpool_config_16_16_16_stride2_padding1.json` | UINT8 MaxPool，`16×16×16 → 8×8×16`；独立小尺寸裁决算子 | `sim4(2).zip` 正确装载并启动；28 slice 均有读返回和写地址、MSE4 写数据为 0，约 4.977 ms 后被 SIGHUP 终止 | **已触发路径；服务器动态复现** |

对应本地 graph/package 实例为：

- `node0002_maxpool_wave0_graph`：使用 112×112 配置，是既有 node-0002 失败证据；
- `native_int8_maxpool16_r1_graph`：使用 16×16 配置，已在服务器有效启动并复现无写数据停滞；
- `native_int8_maxpool16_r2_graph`：r1 的独立重复生成，只用于本地确定性检查，不是第三种算子。

根仓中名称包含 `maxpool-node0002-*` 的多个候选或历史 revision，若最终仍加载上述 112×112 `int8_max` 配置，就属于同一受影响算子实例，而不是新的受影响 opcode。

## 4. 哪些 INT8 或 Max 算子不会因此触发

| 算子/情况 | 不触发原因 |
|---|---|
| DeepSeek `decode_max_fp32N_fp32N` | GA opcode 是 FP32 `max=00011`，`alu_is_fp32=1`，走已有 pipeline1 反压分支 |
| DeepSeek GA add/mul/max/sum/summac | 当前原生配置使用 FP32 opcode，不进入 `alu_is_int8` |
| GA `int32_sum/int32_sub/int32_mac` | `alu_is_int32=1`，已有 `ga_pe_inbuffer_bp_post` 分支 |
| node-0004 INT8 Conv/accumulate | 主要计算位于 Specialized Array，经过 `SA_PE_Control_Block`，不经过本报告的 `GA_PE_Inbuffer` 缺口 |
| 其他 SA INT8 GEMM/GEMV/Conv | 同上；SA 有自己独立的 INT8 下游反压分支 |
| `int32touint8` 输出转换 | 这是输出转换控制，不会把 GA ALU opcode 自动改成 `int8_max`，不能仅凭输出 dtype 判定触发 |
| 单纯 INT8/UINT8 tensor 搬运 | 没有启用 GA `int8_max` PE 时不会进入缺口 |
| FP32 max | 算法名称同为 max，但 opcode 类型不同；已有服务器自然完成对照 |

因此，不能把“DeepSeek 里有 INT8 数据或量化”当成会触发本问题，也不能用 DeepSeek FP32/SA 算子跑通来反证该问题不存在。

## 5. 源码和编码证据

本次审计绑定：

| 证据 | 身份 |
|---|---|
| 活动原生 `ndp-sim` | `ec12424516ae0304228dd2321d4e604fe225e04e` |
| `GA_PE_Inbuffer.sv` | SHA-256 `25fa4dd2c6fe8301bc3651d660df72059ea2787c0c26a2841a1d4e439586b518` |
| 16×16 MaxPool JSON | SHA-256 `624d675ddde6f386474289d473d1c69559691794f3c1ea775dfc99325cc8f072` |
| 16×112×112 MaxPool JSON | SHA-256 `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1` |

原生仓库只证明这两份 JSON 是 Git 跟踪配置，没有随附 MaxPool 的 RTL/VCS 日志、硬件回读或通过声明。
其 Git 历史和 README 审计见
`contracts/native_ndpsim_maxpool_hardware_record_audit_20260723.md`；不得把“上游原生文件”自动解释为
“上游已经硬件验证通过”。

编码器：

```python
# ndp-sim/bitstream/config/general.py
"max": 3,
"int8_max": 11,
"int32_sum": 12,
```

RTL：

```systemverilog
// NDP_copy01/rtl/includes/NDP_Parameters.svh
`define GA_PE_ALU_OPCODE_FP32_MAX 5'b00011
`define GA_PE_ALU_OPCODE_INT8_MAX 5'b01011
`define GA_PE_ALU_OPCODE_INT32_SUM 5'b01100
```

JSON、编码器和 RTL 对 `int8_max=01011` 的定义一致，排除了符号名称没有编码进 INT8 opcode 的解释。

作为正确结构的旁证，
`NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_Control_Block.sv:232`
为 SA INT8 明确连接了下游：

```systemverilog
((sa_pe_computation_data_type == `SA_PE_COMP_INT8_TYPE)
 && sa_pe_ob2cb_alu_bp_post)
```

GA 对应逻辑缺少同类分支。

## 6. 服务器证据与当前缺口

### 6.1 node-0002

已有项目记录显示，更新 testbench 后的 node-0002 MaxPool：

- 28 个 slice 均出现读请求和读返回；
- MSE4 写地址请求出现；
- 写数据计数仍为 0；
- 算子没有自然完成。

这排除了“完全没有装载或启动”，并与 GA INT8 多输入归约在结果形成前停止推进一致。当前工作区没有把该轮完整原始 MaxPool `sim.log` 单独归档到本报告目录，因此它仍是“动态现象一致”，不是带服务器 RTL 哈希的最终因果闭环。

### 6.2 FP32 对照

`native_deepseek_fp32_max_control_r1_graph` 的 `sim5.zip`：

- 正确加载两份 SCA；
- 30 个矩阵完成预加载；
- 全局完成条件在 65 cycles 后满足；
- 28 个 D 矩阵执行回读；
- 仿真自然成功结束。

此前 `decode_max_fp32N_fp32N_graph` 也在服务器自然完成，并产生 28/28 个有效 MSE4 写数据。两轮 FP32 max 对照说明公共装载、读取、GA 输出、outbuffer、MSE4 写回和完成链在 FP32 路径可工作。

### 6.3 小尺寸 INT8 裁决已有效复现

首份 `sim4.zip` 实际指向旧路径：

```text
install/cfg_pkg/maxpool_node0002_guarded_wave0_v1/sca_cfg.json
```

该文件不存在，testbench 在 JSON 配置装载前报告 `Cannot open`，所以首份结果无效。

随后返回的 `sim4(2).zip` 正确绑定：

```text
install/cfg_pkg/native_int8_maxpool16_r1_graph/sca_cfg.json
install/cfg_pkg/native_int8_maxpool16_r1_graph/sca_cfg_D.json
```

该轮完成 30 个矩阵预加载、29 行 execplan 装载和 138 次 GEXEC→slice 握手；138 次恰好对应
28 次 Clock_Enable 广播、28 次 Load_Config 广播、54 次 Write_Reg 和 28 次 Start_Comp 广播。
28 个 slice 随后各有 47 个 MSE0 读请求、33 个读返回和 2 个 MSE4 写地址请求，但 MSE4
写数据均为 0；没有 slice completed、D 回读或自然 `$finish`，最终在
4,977,136,875 ps 收到外部 SIGHUP。

这与 node-0002 的停滞签名一致，并把动态复现扩展到零 ping-pong、小尺寸、原生静态 JSON 的
独立 INT8 MaxPool。完整日志分析位于
`server_returns/native_int8_maxpool16_sim4_2_20260723/ANALYSIS.md`。

## 7. 最终判定边界

目前可以确定：

1. 本地 `GA_PE_Inbuffer` 对 GA INT8 opcode 缺少 pipeline0 下游反压分支；
2. 当前正式工具链只有 `int8_max` 会进入该类别；
3. 活动原生算子中只有两份 UINT8 MaxPool 配置使用 `int8_max`；
4. ResNet50 node-0002 的服务器停滞现象与该缺口一致；
5. 16×16 原生 UINT8 MaxPool 正确装载和启动后复现 28 slice 有读返回/写地址但无写数据；
6. DeepSeek 的成功算子没有进入该路径，所以不构成反证。

目前还不能确定：

1. 服务器实际编译的 `GA_PE_Inbuffer.sv` 是否与本地 SHA-256 完全一致；
2. 修复 `alu_pipeline0_bp_post` 后同一包是否立即完成；
3. node-0002 是否还同时存在其他独立配置、调度或 RTL 问题。

要把结论升级为服务器因果闭环，应在同一 RTL/filelist build 下：

1. 记录服务器 `GA_PE_Inbuffer.sv` SHA-256；
2. 观察 `alu_pipeline0_valid_bit`、`alu_pipeline0_bp_post`、
   `ga_pe_alu_pipeline0_enable` 与上游 ready；
3. 为 INT8 增加直接下游反压分支后，用同一 INT8 包复测；
4. 同时回归 FP32 max、INT32 GA 和 SA INT8 算子。
