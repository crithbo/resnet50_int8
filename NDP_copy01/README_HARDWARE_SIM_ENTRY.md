# NDP_copy01 硬件仿真入口

最后更新：2026-07-21（入口职责及服务器能力判定口径同步）

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
- `DUMP_VCD`、`DUMP_FSDB`、`TB_DUMP_FSDB`：正式完成包必须全部显式为0；波形诊断使用独立revision。
- `VCS_EXTRA_OPTS`：可启用已存在的TB编译宏；不能借此修改RTL/TB逻辑。

服务器执行工作目录必须是现有`NDP_copy01`根。overlay是merge-only，不能删除或替换服务器目录。

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
- 当前项目合同为84个完整语义region，经4 KiB安全分段后形成168个运输文件，再确定性重组28份Bank。
- preload输入位于`install/cfg_pkg/<package>/install/...`等安装树；readback输出位于合同指定的`install/hwop-*`命名空间。watchdog不得把整个install树中的preload当作额外readback。
- 每个readback文件必须是普通文件、非symlink、每行128 bit加LF、行数精确、大小等于`line_count×129`；live/final/offline验收使用同一合同。

testbench打印成功文本、Make返回0、输出文件存在或单个slice完成都不足以证明结果正确。

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
