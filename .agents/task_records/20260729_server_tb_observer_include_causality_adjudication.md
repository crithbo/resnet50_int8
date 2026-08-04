# 服务器 TB observer include 因果裁决

日期：2026-07-29

## RETURN_ANALYSIS

本轮只做既有服务器 TB、历史快照、任务记录与 QLinearAdd return 的只读
因果核验；未修改 TB、RTL、测试包或服务器文件。

结论：

```text
PRIOR_PROJECT_TB_INSTRUMENTATION_CAUSED_CURRENT_INCLUDE_DEPENDENCY=true
QADD_NUMERIC_OR_CONFIG_FAILURE=false
HARDWARE_RTL_CAUSE=false
```

证据链：

1. `artifacts/server_snapshot_0718_effective/tb_NDP_Top_new_phy.sv`
   SHA-256=`27f8b96f05cade3c48179df6b45138dca5de401d3a0f12222e8e0c57455286c2`，
   不含 `native_return_observer.svh` include。
2. 当前本地/服务器对齐 TB
   `NDP_copy01/tb_NDP_Top_new_phy.sv`
   SHA-256=`e068f7500f0c71c2ba2c756f74a4519c33d13d4afe0fa4cc9f6c9e79b1e3f994`，
   在末尾第 5854 行无条件加入：

   ```systemverilog
   `include "native_return_observer.svh"
   ```

3. `.agents/history/plan_pre_active_compaction_20260724.md:1999-2001`
   明确登记：2026-07-23 为 GAP/通用返回定位新增
   `NDP_copy01/native_return_observer.svh`，并在本地 TB “只新增一条
   include”。observer 当前 SHA-256 为
   `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`。
4. 2026-07-25 的既有编译失败已经证明：从隔离 `RUN_DIR` 编译时，仅在
   NDP 根放置 observer 仍不够；必须显式提供 `+incdir` 并在 compile 前
   验证文件可读。记录见
   `.agents/task_records/20260725_server_observer_include_rule_sync.md`。
5. QLinearAdd `r5_qadd_n7_relocated_v2` 包声明 TB/observer entries=0，
   没有携带 observer，也没有为它提供 package-local include path；服务器
   却继续使用上述带无条件 include 的 TB。结果在
   `tb_NDP_Top_new_phy.sv:5854` 以 missing
   `native_return_observer.svh` 停止，compile=2、simulation 未启动、
   readback=0/28。

因此，无法证明服务器上的那一行由哪条具体 shell 命令写入，但其内容、位置、
时间线和项目记录与此前 Codex/项目的 observer 接入完全一致。当前失败应归因于
“先前测试基础设施修改遗留 + 后续包未声明该依赖”的合同不一致，而不是
QLinearAdd 或硬件 RTL。

## 修复方案

用户已明确授权修改服务器 `rtl/` 外的 TB/支持文件。现有服务器包规则第 6 节
也允许唯一目标、事务式、可恢复的 TB/observer 修改。

推荐修复为可选 include，而不是让所有算子包永久依赖 observer：

```systemverilog
`ifdef NATIVE_RETURN_OBSERVER_ENABLE
`include "native_return_observer.svh"
`endif
```

- 普通 QAdd 包不定义宏，不需要 observer，TB 可直接编译；
- 需要动态内部观测的包携带 package-local observer，并显式提供
  `+define+NATIVE_RETURN_OBSERVER_ENABLE` 与唯一 `+incdir`；
- 安装前后记录 TB preimage/post-install/post-restore SHA，EXIT trap 恢复；
- 不修改 `rtl/**`。

较小但耦合更强的备选是让 QAdd 后继包也携带同一 observer，并显式加入
package-local include path。该方案会迫使所有使用该 TB 的包了解 observer
依赖，因此不作为默认长期方案。

## BLOCKER_DELTA

- RECLASSIFY：
  `SERVER_TB_NATIVE_RETURN_OBSERVER_INCLUDE_MISSING`
  → `PRIOR_PROJECT_TB_INSTRUMENTATION_CONTRACT_MISMATCH`。
- QAdd 数值、JSON、mapping、bitstream、execplan blocker：无新增。
- 最新 GitHub RTL 尾逗号 blocker 与本项正交，继续保持。

## RULE_DELTA_PROPOSAL

NONE。当前服务器包规则已经要求 TB 目标隔离、observer 可读、显式 include
路径、新 compile 身份及事务式恢复；本次是包未消费既有规则能力，不是规则缺失。

## PACKAGE_RELEASE

NONE。本轮仅完成因果裁决，未生成 QAdd v3。

## 直接修补脚本

已交付：

```text
tools/patch_server_tb_optional_observer_include.py
SHA-256=fce7cfa766239669c22d89e3ea18bf07d14d0e02aec6588a98632a96ad6151a4
```

服务器运行：

```bash
python3 patch_server_tb_optional_observer_include.py /home/panqs/ndp/NDP_copy02
```

脚本只解析并修改
`<server_root>/tb_NDP_Top_new_phy.sv`，不递归搜索、不触碰 `rtl/**`。
它要求无条件 observer include 恰好命中一处，创建按 preimage SHA 命名的
TB 备份，原子写入宏保护，并生成
`tb_optional_observer_patch_receipt.json`。重复执行会报告
`ALREADY_GUARDED` 且不再次修改。

本地隔离副本自检：

- `--check`：exit=2，正确报告 `PATCH_REQUIRED`；
- 首次 apply：exit=0，生成 1 个 backup 和 1 份 receipt；
- 第二次 apply：exit=0，idempotent；
- 宏保护行和 include 行数量正确；
- `py_compile` PASS；
- 活动本地 TB 未修改。

## 直接修补脚本

已交付：

```text
tools/patch_server_tb_optional_observer_include.py
SHA-256=fce7cfa766239669c22d89e3ea18bf07d14d0e02aec6588a98632a96ad6151a4
```

服务器运行：

```bash
python3 patch_server_tb_optional_observer_include.py /home/panqs/ndp/NDP_copy02
```

脚本只解析并修改
`<server_root>/tb_NDP_Top_new_phy.sv`，不递归搜索、不触碰 `rtl/**`。
它要求无条件 observer include 恰好命中一处，创建按 preimage SHA 命名的
TB 备份，原子写入宏保护，并生成
`tb_optional_observer_patch_receipt.json`。重复执行会报告
`ALREADY_GUARDED` 且不再次修改。

本地隔离副本自检：

- `--check`：exit=2，正确报告 `PATCH_REQUIRED`；
- 首次 apply：exit=0，生成 1 个 backup 和 1 份 receipt；
- 第二次 apply：exit=0，idempotent；
- 宏保护行和 include 行数量正确；
- `py_compile` PASS；
- 活动本地 TB 未修改。
