# W1-RTL28 必要硬件合同审计（candidate）

状态：`candidate_unapproved`。证据仓库固定为 [`xlsjdjdk/Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`](https://github.com/xlsjdjdk/Trassic2.0_RTL/tree/e3bdebba95dec36ee8eba43caa92a326a88392cd)。本报告不是 `hardware_approval.json`，不批准 W5，不宣称 G1/G4 通过。

机器可读版本见 [`contracts/rtl28_candidate_audit.json`](rtl28_candidate_audit.json)。下述“固定”只表示源码在该 commit 的静态行为已经明确，不表示已 clean elaboration，也不表示配置数值正确或高性能。

## 1. 构建权威与 elaboration 边界

权威 filelist 是 [`code/NDP_rtl/filelists/NDP_Top_filelist.f`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/filelists/NDP_Top_filelist.f#L1-L29)，最终纳入 `slice_with_datahub_new.sv` 和 `NDP_Top.sv`。后者实际声明的是 [`module NDP_Top_new`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/NDP_Top.sv#L7-L78)。因此：

- `NDP_Top` 是权威文件名/filelist stem，不是该 closure 内的 module alias 或 wrapper。
- 活跃 top module 必须写 `NDP_Top_new`。名为 `NDP_Top` 的声明只出现在 `code/NDP_rtl/not_used`，不属于权威 filelist。
- 仓库的 lint 脚本默认 `NDP_Top` 和小写 `filelists/ndp_top_filelist.f`；PowerShell 解析器还会把 `$MC_DIR` 错误地改写成嵌套 filelist 相对目录。见 [`verilator_lint.ps1`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/verilator_lint.ps1#L22-L24) 和其 [filelist 解析](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/verilator_lint.ps1#L118-L180)。

可交给具备供应商环境的 RTL 集成人员重放的候选命令为：

```bash
cd code/NDP_rtl/filelists
export MC_DIR="$PWD/../DDR_Model/MC_IP/rtl"
export DIR_HOME="<approved root resolving Hardware/IP/bus/nic_cgra_0310>"
vcs -full64 -sverilog -top NDP_Top_new -f NDP_Top_filelist.f -l vcs_elab.log
```

本机不能执行这条命令：没有 VCS/Verilator/Slang/Verible；唯一可用的 Icarus 不支持递归 `-F`，把 filelist 临时展开后又在活跃 [`phy_dram_wrapper.vp:99`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/DDR_Model/MC_IP/test/mc_env/tb/quad/phy_dram_wrapper.vp#L99-L100) 的 `protected128` 负载处失败。DDR closure 还要求 [`$MC_DIR`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/DDR_Model/MC_IP/rtl/mc_subsys_top/filelist.f#L1-L13)，NIC filelist 含未给定的 [`${DIR_HOME}` include`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/AXI_Bus/nic400_cgra_0310/nic_cgra_0310.vf#L1-L68)。仓库现有 [`LINT_SUMMARY.md`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/LINT_SUMMARY.md#L1-L35) 是 7 errors/436 warnings 的失败记录，不能当成 clean elaboration。

结论：本审计是静态、受限 elaboration 审计；clean elaboration 仍是明确阻塞项。

## 2. RTL 已固定的 candidate 合同

### 2.1 28-slice mask、WREG 与 HIGH/LOW

参数固定 `SLICE_GROUP_SIZE=14`、`SLICE_GROUP_NUM=2`、`SLICE_NUM=28`，全局命令宽 64 bit，见 [`NDP_Parameters.svh`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/includes/NDP_Parameters.svh#L1-L44)。Slice manager 固定 opcode：CFG `000`、CKEN `001`、WREG `100`、CMPT `101`、BARR 常量 `110`、RST `111`；非 WREG 命令用 `[30:3]` 的 28-bit mask，WREG 用 `[7:3]` 的 5-bit slice id，见 [decode](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/Slice_Execution_Manager.sv#L45-L78)。

WREG 完整字段是：`opcode[2:0] | slice_id[7:3] | reserved[17:8] | addr[31:18] | data[63:32]`。14-bit 地址再分成 `2/2/5/5`：一级 IGA/LSU/SA/GA，二级选择子系统，三级选择 unit，四级是 5-bit leaf register address，见 [WREG 地址层级](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/Slice_Execution_Manager.sv#L90-L179)。WREG 只命中一个 slice，并把选定 leaf valid 脉冲一个 FSM 周期；CFG/CMPT/CKEN 分别等待各自 finish，见 [FSM](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/Slice_Execution_Manager.sv#L247-L325)。BARR 虽有 opcode 常量，但该模块没有 `barr_cmd_vld` 或对应 FSM 状态，不能把它视为已实现的同步原语。

四张逐 slice route map 已固定在 [`NDP_Top.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/NDP_Top.sv#L274-L299)，完整数组保存在 JSON。连接使用 `{HIGH, LOW}`，而 NSE 的 source selector 直接索引两项向量，因此 selector `0=LOW`、`1=HIGH`，见 [`Stream_Engine_Connect.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/LSU/Stream_Engine/Stream_Engine_Connect.sv#L275-L292)。这固定了“选择某条环会连到谁”，但没有替编译器决定某层应该选 HIGH 还是 LOW。

### 2.2 每 slice DRAM 几何

逻辑参数固定为每 slice 4 banks，每 bank 6144 rows × 64 columns，每 column 128 bit（16 bytes）；全局地址字段为 5-bit slice owner + 2-bit local bank + 13-bit row + 6-bit column + 4-bit byte offset，共 30 bit，见 [`NDP_Parameters.svh`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/includes/NDP_Parameters.svh#L92-L155)。由此算得每 slice 24 MiB，28 slices 共 672 MiB；这是参数算术，不是板卡容量批准。

读写 MSE 都以 stream base address 的最高 5 个 bank bits 与 `SLICE_ID` 比较，决定 remote flag，见 [`Stream_Engine_Config.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/LSU/Stream_Engine/Stream_Engine_Config.sv#L190-L210) 和 [write path](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/LSU/Stream_Engine/Stream_Engine_Config.sv#L215-L305)。物理 DRAM wrapper 的明文头却是 13 row bits、7 column bits、144-bit array data，随后进入加密体；逻辑 128-bit 数据、物理 144-bit/ECC 和板级容量的对应关系仍需硬件批准。

### 2.3 SA/GA、INT8、psum、bias 与 requant 边界

SA 固定 8×8=64 PEs，GA 固定 4×4=16 PEs；两者都有 3 个 input groups、1 个 output group，每组 8×32-bit lanes。相关宽度、模式和 opcode 见 [`NDP_Parameters.svh`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/includes/NDP_Parameters.svh#L533-L715)。

SA 的可确认 INT8 行为是：DataA 的每个 byte 按有符号二补码取 magnitude 并单独携带符号，DataB byte 不做符号转换，所以原语表现为 signed-A × unsigned-B，见 [`SA_PE_Float_Control.v`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v#L217-L227)。不能仅凭这里决定 activation/weight 各放 A 还是 B。

psum/bias 路径也可固定：ALU 的 DataC 来自 outbuffer psum feedback；第三输入在 `bias_enable=1` 时作为 initial value，关闭时替换为 0，见 [`SA_PE_Control_Block.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_Control_Block.sv#L138-L175)、[`SA_PE_ALU.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU.sv#L19-L39) 和 [outbuffer feedback](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_Outbuffer.sv#L240-L270)。这只定义“第三输入如何成为初始 psum”，不定义 ResNet50 bias 的布局、符号、channel 顺序或 overflow 约束。

GA 暴露 UINT8→INT32/FP32、INT32→FP32 等输入转换、32-bit per-PE constants 和 INT32/FP32 算术。但是：

- GA output 的 `INT32→UINT8` 只是负数→0、超过 255→255、否则取 `[7:0]`，见 [`GA_Outport.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/General_Array/GA_Outport/GA_Outport.sv#L207-L215)。这里没有 scale、zero point 或 rounding。
- GA PE WREG constant 的 `constant_valid` 条件使用 `INPORT_ID+1`，但把 WREG data 选为 `constant_value` 的条件使用 `INPORT_ID+2`，见 [`GA_PE_Config.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Config.sv#L133-L144)。静态阅读不能消除这一地址错位迹象。
- SA/GA 的 WREG branch 会改 packed config storage，但所审查的 SA、GA PE 和 GA outport `enable/configure_finish` 仍由 streamed configure-valid 路径置位；单次 WREG 命中不能等价为“模块已完成配置并启用”，见 [`Specialized_Array_Config.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/Specialized_Array/Specialized_Array_Config.sv#L40-L94)、[`GA_PE_Config.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Config.sv#L62-L117) 和 [`GA_Outport_Group_Config.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Slice/General_Array/GA_Outport/GA_Outport_Group_Config.sv#L31-L84)。
- 权威 closure 中没有命名为 Conv/convolution、requant、qparam、zero point 或 quantization scale 的字段/模块。现有 SA/GA 是原语，不是完整量化卷积合同。

因此 RTL 能证明“写入某配置字段会改变何种 mux/模式/寄存器”，不能证明“怎样生成数值正确且高性能的 ResNet50 Conv/qparams 配置”。

### 2.4 顶层端口和 global registers

顶层端口固定为 `clk/rst_n`、`apb_clk/apb_rst_n`、`ras_clr`，一个 32-bit APB 控制口，以及完整的 2-bit ID、32-bit address、128-bit data `m_axi_reserved` 五通道接口，字段逐项见 [`NDP_Top.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/NDP_Top.sv#L7-L78)。尽管命名带 `m_axi`，信号方向在 top 表现为 host-facing AXI slave。它通过 bridge 接到 global controller，见 [`NDP_Top.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/NDP_Top.sv#L1486-L1560)。

register arbiter 把 `(addr - 0)[31:28] == 8` 的访问送到寄存器，其余转发到内部 AXI，见 [`global_axi_reg_fwd_arbiter.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Global/global_axi_reg_fwd_arbiter.sv#L113-L180)。三个 128-bit register words 是：

| 地址 | 访问 | 字段与固定行为 |
| --- | --- | --- |
| `0x8000_0000` | RW | `[31:0] init_exec_base_addr`; `[47:32] init_exec_inst_length` |
| `0x8000_0010` | WO | bit 0 start，bit 1 reset；无后续 write handshake 时下一周期自动清零；读回 0 |
| `0x8000_0020` | RO | `[13:0] fetch_cnt`; bit 14 fetch_finish; bit 15 overflow; `[43:16] slice_finish[27:0]` |

字段和 pulse 行为见 [`global_axi_reg_slave.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Global/global_axi_reg_slave.sv#L232-L294)。一个容易误用的细节是：`init_exec_inst_length` 实际控制 128-bit AXI read beats，fetch counter 每个 128-bit response handshake 加一，而 FIFO 再把一 beat 拆成两个 64-bit commands，见 [`global_exec_manager.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Global/global_exec_manager.sv#L40-L134)。固件不能未经批准把该字段当成 64-bit command 数。

## 3. load / start / wait / dump 候选接口

候选流程如下；“候选”表示结构路径存在，板级地址与固件 ABI 尚未批准。

1. `load`：通过 `m_axi_reserved` 向非 `0x8...` 地址写 128-bit execution beats/数据，由 arbiter 转发到内部 AXI。CFG command 可从其 22-bit base/8-bit length 读取 64-bit config words，并 multicast 到 28-bit mask，见 [`global_config_manager.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Global/global_config_manager.sv#L84-L186)。实际 DRAM base、对齐、装载顺序和 APB 初始化尚缺。
2. `start`：写 `0x8000_0000` 的 base/length，再写 `0x8000_0010.bit0=1`。写入确实触发 fetch；但如何构造正确 list 不是寄存器 RTL 能决定的。
3. `wait`：轮询 `0x8000_0020`，检查 fetch_finish、overflow，并要求目标 slice 的 finish bits。finish bit 只在 global queue 空、fetch 完成、local queue 空且 slice ready 时置位，见 [`global_exec_manager.sv`](https://github.com/xlsjdjdk/Trassic2.0_RTL/blob/e3bdebba95dec36ee8eba43caa92a326a88392cd/code/NDP_rtl/Global/global_exec_manager.sv#L276-L293)。timeout/error policy 缺失。
4. `dump`：非寄存器 AXI read 在结构上会被转发，因此 memory readback 可行；但活跃 filelist 没有 top-level dump command、输出地址/布局、completion fence、cache/coherency 或 driver API。testbench 的 VCD/FSDB dump 不是硬件接口。

## 4. 必须由硬件/固件人员批准的精确缺口

| ID | Owner | 必须批准或提供的内容 |
| --- | --- | --- |
| `APR_ELAB_001` | RTL/integration | `NDP_Top_new` + 权威 filelist、`MC_DIR/DIR_HOME`、供应商库/许可证，以及 clean elaboration log |
| `APR_BOARD_002` | board/SoC | `m_axi_reserved` 的物理基址、`0x8` window、转发 DRAM map、APB 初始化、clock/reset、128-bit logical 与 144-bit physical/ECC 对应 |
| `APR_FW_003` | firmware/compiler | 64-bit command ABI、每 128-bit beat 内两个 command 的顺序、length 单位、CFG length、alignment、reset/start/poll 顺序 |
| `APR_INT8_004` | RTL + quant/compiler | signed-A/unsigned-B 的 activation/weight 绑定、byte/lane order、zero-point 处理、accumulator/bias signedness 和 overflow |
| `APR_QPARAM_005` | RTL + quant/compiler | scale 表示、zero point、rounding、saturation、per-channel qparam 布局、完整指令序列，并澄清 GA constant WREG 地址错位 |
| `APR_CONV_006` | compiler/performance | Conv lowering、tile、padding/stride、DRAM placement、buffer lifetime、HIGH/LOW、mask、同步和实测性能配置 |
| `APR_DUMP_007` | board/firmware | 输出 placement、completion fence、readback/dump API、传输尺寸、coherency、比较格式 |
| `APR_WAIT_008` | RTL/firmware | timeout/error policy、是否需要 barrier，并澄清未进入 slice FSM 的 BARR opcode |

核心边界是：RTL 已足以写出“寄存器/command 写入会产生什么局部行为”的 candidate；它仍不足以生成“数值正确且高性能”的正式配置。

## 5. 交接检查与非声明

以下环境结果是本审计最初在隔离worktree中的历史观察，不是当前Local健康状态，也不是RTL证据结论：开始时工作树为clean；`tools/sync_repositories.py verify`因该worktree缺`CGRA_SIM`而失败；当时全量unittest运行63 tests、16 errors，原因是缺`onnx`、三个参考仓和`artifacts/w3/model_graph.json`。依协调要求当时没有同步/安装、没有读取或重算W3。后续Local环境恢复、C0合同迁移和当前全量回归结果以`.agents/history.md`为准，不应把这组历史错误数抄成现状。

本次不修 RTL、不生成 W5 JSON/bitstream、不创建正式批准文件、不声明 G1/G4、clean elaboration、数值正确性或性能通过。
