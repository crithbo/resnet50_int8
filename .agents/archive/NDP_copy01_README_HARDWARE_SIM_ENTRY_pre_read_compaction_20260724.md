# 归档：精简前的 NDP_copy01 硬件仿真入口说明

原标题：`NDP_copy01 硬件仿真入口`。本文件保留 2026-07-24 精简前的历史 runner、
observer 和结果说明，只用于审计；当前入口说明仍位于 `NDP_copy01/` 原路径。

最后更新：2026-07-23（显式 SCA_D 回读参数与防复发门）

本文件只说明`NDP_copy01`目录的活动入口、Make/testbench实际语义、运行环境和证据边界，是对活动实现的说明而非独立权威。当前revision、freeze和下一步看`.agents/plan.md`；package/runner/回传约束看实际包内合同及`.agents/rules/服务器测试包生成规则.md`；旧服务器结果和错误看`.agents/history.md`。若说明与活动Make/TB/runner或真实返回冲突，应修正说明，不得为迎合文字增加启动硬门。

## 1. 目录职责与不可变边界

`NDP_copy01`是Linux/VCS PHY顶层仿真入口。本地长期只需要：

```text
NDP_copy01/
  README_HARDWARE_SIM_ENTRY.md
  Makefile.tb_NDP_Top_new_phy
  tb_NDP_Top_new_phy.sv
  rtl/
```

- `rtl/**`、`tb_NDP_Top_new_phy.sv`及所有`.v/.sv`只读，不得由服务器overlay包含、覆盖或现场修改。
- 服务器源码允许更新；runner只要求主Makefile、主TB和主filelist三个逻辑入口可读，并记录逻辑/物理路径、大小和SHA作为非阻断provenance。不要求Git HEAD、整树SHA、路径位于服务器根内或与本地逐字节一致；源码/接口语义由真实Make/VCS/UCLI执行判定，不在启动前重复扫描。
- `install/`、`run/`、`sim_results/`、simv/csrc、波形和Verdi日志都是服务器临时运行态，不在本地长期保留。
- 原始服务器返回以`sim_result*.zip`或`sim_results*.zip`及其SHA记录长期保存；展开目录和派生分析可重新生成，不作为原始证据。

本机负责package/manifest审计、返回ZIP分析、P/D inverse与三方比较、问题定位和代码回归；真实VCS/Verdi编译仿真只在具备Synopsys依赖和license的Linux服务器运行。

## 2. 三个活动入口

| 文件 | 作用 |
|---|---|
| `Makefile.tb_NDP_Top_new_phy` | VCS compile/sim、参数、UCLI/波形和历史archive target |
| `tb_NDP_Top_new_phy.sv` | 时钟/复位、SCA解析、AXI预装/回读、启动寄存器和完成观察 |
| `rtl/filelists/NDP_Top_phy_filelist.f` | 主PHY编译源集合；递归包含Slice、Datahub、Global、AXI、DDR/PHY等filelist |

架构参数由`rtl/includes/NDP_Parameters.svh`等活动include决定。历史静态基线为2×14=28个slice、9个MC group、每slice 4个bank；服务器更新后应从当前活动源码重新记录provenance，不用旧SHA阻断。

主要功能域：

| 路径 | 功能 |
|---|---|
| `rtl/NDP_Top_phy.sv` | `NDP_Top_new_phy`顶层和全局/AXI/slice/MC-PHY连接 |
| `rtl/slice_with_datahub_phy.sv` | Slice Wrapper、Datahub和MC/PHY集成 |
| `rtl/Slice/` | 执行/配置/时钟管理、GA、SA、IGA、LSU和neighbor stream |
| `rtl/Datahub/` | 本地请求/返回、bank frame和MC通路 |
| `rtl/Global/` | 全局exec/config、任务调度、AXI master和寄存器slave |
| `rtl/AXI_Bus/`、`AXI_Bridge/`、`AXI_IF/` | AXI互连与适配 |
| `rtl/DDR_Model/` | 9组MC、PHY/DRAM仿真模型 |
| `rtl/CDC/`、`rtl/utils/` | 跨时钟域和公共基础模块 |

## 3. Makefile调用语义

历史主调用形式为：

```bash
make -f Makefile.tb_NDP_Top_new_phy compile sim \
  SCA_CFG=/absolute/path/to/sca_cfg.json
```

正式服务器测试不得直接照抄该命令；必须运行当前overlay提供且受hash绑定的`RUN_SERVER_<REV>.sh`，由runner加载批准argv、检查三个入口可读性和必需命令、清理本revision缓存、设置SCA/UCLI/波形参数并保存独立退出状态。runner不在启动前解释服务器HDL/filelist语义；真实Make/VCS错误进入失败归档。

Make变量语义：

- `compile`：调用VCS编译/elaboration，生成`run/sim_results/simv`。
- `sim`：运行simv，并可能调用Makefile历史`archive_sim_results`；正式completion runner应使用受合同约束的no-archive附加target，避免复制全量结果树。
- `SCA_CFG`或`+SCA_CFG=...`：传给testbench的SCA入口；SCA内部payload路径仍按`NDP_copy01`工作目录解析。
- `+SCA_CFG_D=...`：传给testbench的D回读描述。当前TB若没有收到该参数，会把`SCA_CFG`文件名替换为硬编码的`sca_cfg_D_softmax.json`；非softmax包不得依赖该默认值。
- `DUMP_VCD`、`DUMP_FSDB`、`TB_DUMP_FSDB`：正式完成包必须全部显式为0；波形诊断使用独立revision。
- `VCS_EXTRA_OPTS`：可启用已存在的TB编译宏；不能借此修改RTL/TB逻辑。

服务器执行工作目录必须是现有`NDP_copy01`根。overlay是merge-only，不能删除或替换服务器目录。

对当前Make入口，原生包至少应按以下形式同时传入两个配置；`<package>`替换为本轮唯一目录名：

```bash
make -f Makefile.tb_NDP_Top_new_phy compile sim \
  SCA_CFG=install/cfg_pkg/<package>/sca_cfg.json \
  PLUSARGS='+SCA_CFG_D=install/cfg_pkg/<package>/sca_cfg_D.json'
```

若直接调用`simv`，同样必须同时保留两个plusarg。

## 4. SCA、预装与启动

testbench使用逐行字符串逻辑读取SCA，而不是完整JSON parser。它依赖：

- `Exec_Base`
- `Exec_Length`
- `Repeat_Num`
- 每个对象的`base_addr`
- 每个对象的`path`

因此正式生成器必须输出固定pretty JSON结构；禁止服务器现场压成单行、重排对象或手填`Repeat_Num`。

payload ABI为每行一个128-bit AXI word：每行只能有128个`0/1`字符并以LF结束。TB loader本身对短行、非法字符、缺文件等场景不够严格，所以package preflight和runner必须在启动前fail closed，不能把“matrices loaded”数量当作所有payload正确。

预装完成后TB向全局寄存器写入：

```text
0x8000_0000 <- {96'd0, exec_length, exec_base}
0x8000_0010 <- 1
```

执行内容来自SCA中的`install/execplan.txt`；Makefile的历史`+BITSTREAM`参数不是当前主执行计划来源。

## 5. 当前TB观察与运行环境适配

服务器实际TB按`Repeat_Num`固定观察：

1. 等待物理slice0收到`Start_Comp`；
2. 等待物理slice1出现`slice_cmpt_finish`；
3. 重复指定次数后进入回读。

这不是mask-aware完成观察，不能直接证明每个stage的所有目标slice完成。当前package必须通过可机检的stage重排/barrier合同，使最后slice1事件发生在其他目标slice完成之后；runner按冻结observer mode验收，不得要求TB不存在的runtime marker。

服务器RTL可能暴露TB未连接的`m_axi_reserved_clk`。只有经过审计的UCLI可以在不改HDL的情况下force该端口，并且必须证明force/get成功和低高相位确实翻转后才打印成功marker。

TB现有start-only日志宏不能自动抑制全部MC高频日志。正式runner可在本revision临时`sim_results`中把固定、已审计且不参与数值判定的日志精确sink到`/dev/null`；该例外不适用于overlay、install、readback或返回ZIP。

## 6. 回读与结果目录

- `sca_cfg_D.json`声明运行后readback地址、路径和长度。
- 每次运行必须显式同时传入`+SCA_CFG=<本包>/sca_cfg.json`和`+SCA_CFG_D=<本包>/sca_cfg_D.json`。Make入口可把后者放入`PLUSARGS`；直接运行simv时也必须保留。两条路径必须属于同一package。
- 仿真刚启动时先核对`Using SCA cfg file:`和`Using SCA cfg D file:`。若D路径显示`sca_cfg_D_softmax.json`、旧包或不存在文件，应立即停止，不能等待算子完成后再发现回读被跳过。
- 当前项目合同为84个完整语义region，经4 KiB安全分段后形成168个运输文件，再确定性重组28份Bank。
- preload输入位于`install/cfg_pkg/<package>/install/...`等安装树；readback输出位于合同指定的`install/hwop-*`命名空间。watchdog不得把整个install树中的preload当作额外readback。
- 每个readback文件必须是普通文件、非symlink、每行128 bit加LF、行数精确、大小等于`line_count×129`；live/final/offline验收使用同一合同。

testbench打印成功文本、Make返回0、输出文件存在或单个slice完成都不足以证明结果正确。

2026-07-23 的 `decode_max_fp32N_fp32N` 返回证明了这一边界：计算在66 cycles后自然完成，28个slice均写出数据，但由于实际argv遗漏`+SCA_CFG_D`，TB默认寻找`sca_cfg_D_softmax.json`并打印`skip matrix readback`。因此`Simulation completed successfully!`与回读成功必须分开验收；出现`Cannot open`、`skip matrix readback`或意外softmax文件名时，正式回读门失败。禁止复制/改名文件来迁就错误默认值，应修正启动argv。

## 7. Linux/VCS环境

需要：

- Linux x86_64、GNU make、bash和常见coreutils；
- Synopsys VCS及有效license；
- 当前filelist所需DesignWare、AMBA VIP、DDR/PHY模型和运行库；
- 如使用诊断波形，还需兼容Verdi FSDB PLI和license；
- 足够磁盘容纳编译缓存和临时结果，但正式返回不得归档全量simv/csrc/波形/高频日志。

Windows本机不承担真实compile/sim；WSL也只有在具备完整VCS、模型和license时才可能运行。

## 8. 可靠完成判据

一次服务器结果只有同时满足以下条件才可进入数值验收：

1. package/freeze/runner/argv身份与本地批准值一致；
2. 三个服务器逻辑入口可读，必需命令存在；实际源码、层次和UCLI能力由随后的Make/VCS/UCLI运行证明；
3. VCS编译/elaboration零错误；
4. 全部preload实际打开、格式正确、AXI比较通过且数量精确；
5. reserved clock和observer合同满足，仿真自然结束；
6. process、Make、tee、simulator、watchdog均有独立成功状态；
7. 168个readback文件exact-set、格式/大小/SHA正确；
8. 28份Bank重组和physical inverse成功；
9. Golden↔NDP、Golden↔RTL、NDP↔RTL三组P/staged-D mismatch全部为0。

具体revision、当前冻结身份、生成命令和两轮自检只在`.agents/plan.md`维护，禁止在本文件增加旧版本上传说明。

## 9. Optional 返回观测器

当前本地 TB 在 `endmodule` 前 include `native_return_observer.svh`。该文件只读观察 DUT
和 TB 已有 monitor，不驱动功能信号；默认关闭。服务器必须使用包含这两个本地文件的
source tree 重新 compile，随后才可在 `PLUSARGS` 中启用：

```text
+RETURN_OBSERVER
+RETURN_OBS_SLICE=0
+RETURN_OBS_STALL_CYCLES=4096
+RETURN_OBS_HEARTBEAT_CYCLES=4096
```

输出为 `sim_results/return_observer/return_observer.log`，记录目标 slice 的
CONFIG/exec/finish、MSE/bank 握手汇总、buffer4/5 读写、SA 输入/输出及
buffer↔SA tag/backpressure、八个常规 GA PE 的 pipeline0/backpressure、低频
heartbeat 和持续 `STALL`。日志每个关键事件均 `fflush`，所以仿真被外部终止时仍可
保留最远 checkpoint。更换被观测 slice 只需修改 plusarg，不需要再改 RTL/TB。

GAP 数值错误复现时再加以下两个参数；`RETURN_OBS_DEEP` 只有与
`RETURN_OBSERVER` 同时给出才生效，且每类事件默认只记前 256 条：

```text
+RETURN_OBS_DEEP
+RETURN_OBS_DEEP_LIMIT=256
```

深度模式依次记录 MSE0 地址入队、对外 request 握手、request metadata、DDR
数据消费与重排、MSE0→Buffer0、GA 输入/ALU/输出，以及 MSE4 的 LC0/LC2/PE1
索引和写地址 bias。它仍然只读，不改变 DUT ready/valid、数据或时序。

当前 GAP 定位轮必须重新编译，不能复用旧 `simv`：

```bash
python3 ../tools/install_native_return_observer.py \
  --tb tb_NDP_Top_new_phy.sv \
  --observer native_return_observer.svh

make -f Makefile.tb_NDP_Top_new_phy compile sim DUMP_FSDB=1 \
  PLUSARGS='+SCA_CFG=install/cfg_pkg/gap_hwop0071_sum_graph/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/gap_hwop0071_sum_graph/sca_cfg_D.json +RETURN_OBSERVER +RETURN_OBS_SLICE=0 +RETURN_OBS_DEEP +RETURN_OBS_DEEP_LIMIT=256 +RETURN_OBS_STALL_CYCLES=4096 +RETURN_OBS_HEARTBEAT_CYCLES=4096'
```

安装命令只会在 `tb_NDP_Top_new_phy.sv` 的末尾 `endmodule` 前插入一次 include；
重复运行是幂等的，并显式拒绝 `rtl/` 下的任何路径。

本轮至少回传 `sim_results/return_observer/return_observer.log`、`sim.log`、
slice0 的 `local_mse0_{req,rdata}.log` 和 `local_mse4_{req,wdata}.log`。FSDB
用于最后的周期级复核，但不能替代上述文本证据。

正式返回仍必须包含 `sim.log`、SCA_D 指向的实际 D 文件和既有 gexec/local/SEM 日志。
本地统一验收命令、GAP profile 和分类见
`contracts/native_ndp_server_return_acceptance.md`。
