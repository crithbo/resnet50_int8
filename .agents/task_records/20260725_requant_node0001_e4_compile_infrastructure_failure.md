# RequantizeUint8 node0001 stock-RTL E4 编译基础设施失败

日期：2026-07-25

## 裁决

```text
classification = FIRST_DYNAMIC_FAILURE
dynamic_baseline = NO_DYNAMIC_BASELINE
evidence_level = SERVER_INCOMPLETE
failure_class = server_test_infrastructure_compile_failure
simulation_started = false
candidate_release = false
E4 = failed_or_incomplete
E5_generation_allowed = false
same_package_rerun_allowed = false
remaining_blocker = B_REQUANT_SERVER_E4_E5
```

本次失败发生在 VCS 编译阶段，仿真未启动。因此它不是正常完成、RTL 故障、
Requant 语义错误、数值 mismatch 或 hang。

## 回传身份

- 原始 ZIP：`requant_node0001_two_stage_stockrtl_e4_onecmd_v1_return.zip`
- bytes：`38960`
- SHA256：`de580c4c86cc33965991bd3f9489f24950ca71e2bee127eb5fd1192d975f2c00`
- sidecar：用户未提供
- ZIP：23 entries，解压后 514902 bytes
- RETURN_RECEIPT：22/22 payload 的 size/SHA 与 ZIP 一致
- package manifest SHA256：
  `bdbd231990b1913d1099fab312ee148d76f7568ff72303df9a3bb472f73ecb86`
- payload tree SHA256：
  `37b2c37eaca08f7a9153cad166d9dd587613644e389a0737d4bc6c42b14bca42`
- 分析记录：
  `server_returns/requant_node0001_stockrtl_e4_return_analysis_20260725.json`
- 分析记录 SHA256：
  `b23f62f5b2101d1849d98ef3f909791f0b46149ac7ee2b89f89fbf605c349369`

## 第一失败与身份边界

前置 package/installed preflight、128 个输入物化、五阶段 identity、功能 RTL
不变和 TB probe byte-exact 恢复均通过。

第一失败：

```text
checkpoint = compile
compile_exit = 2
sim_exit = 125
run_exit = 2
VCS = Error-[SFCOR] Source file cannot be opened
missing_include = native_return_observer.svh
simulation_started = false
```

服务器 Makefile/filelist 与本地不同但在本轮稳定；这不违反 focused identity，
却证明下一 E4 身份必须按 actual server VCS/include consumer 修正 observer
编译集成与安装生命周期。不能直接重跑同包。

## 动态证据边界

- lifecycle：0 start / 0 finish；
- historical guard：128 个 expected-entry 占位，实际非空证据 0；
- formal D：156 个 expected-entry，实际存在 0；
- numeric comparison：未执行。

因此本次没有产生任何可以裁决 GA/MSE、RTL、Requant 语义或数值的动态证据。
128/156 仅是失败收据中的期望条目数，不得冒充 observer/readback 证据。

## 规则与总账影响

现有服务器包和 Requant 动态门已要求编译成功、observer 有效、三类证据分栏、
正式 D 与 natural completion，因此无需修改算子数值/layout 规则。机器总账累计：

- `server_e4_attempt_count=2`
- `server_e4_first_dynamic_failure_count=2`
- `server_e4_incomplete_count=2`
- `server_e4_compile_infrastructure_failure_count=1`
- `server_e4_compute_started_not_completed_count=1`
- `formal_e4_pass_count=0`
- `formal_e5_pass_count=0`

未生成修复包，未修改任何 `rtl/` 文件。
