# GAP node0071 v3 timeout return 与 v4 只读进度定位包

- 日期：2026-07-30
- owner：QLinearGlobalAveragePool / node0071
- 唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`
- 功能 RTL 修改：false
- 数值分析重复：false
- sum/tail 重测：false
- 服务器外部检查/上传/运行：false / false / false

## 控制收据

- `.agents/plan.md`：
  `b1623373ee6f5c442807eeb4d2a68ce33e36d5686d98873ff1a3e1587d1eea34`
  （仅 mutable provenance）
- `.agents/rules/服务器测试包生成规则.md`：
  `06ec5cde2920f6aa0f11e4a2ec23d9cec2621015afe706ab8ec83e3d4603089c`
- 生效硬门：
  `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`、
  `CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001`

## RETURN_ANALYSIS

正式 return：

```text
ZIP bytes  = 51991
ZIP SHA256 = a466f809dfc765d245bdca1180cb4422d6142912cdd9a0fcce82d98b2e831d15
sidecar SHA256 = 6594b0ca2860bdf2389ae8627732f8e3ec2c2f92807c5dea66d75a7820f91b1e
```

相邻 sidecar 内容与 ZIP 文件名、SHA 完全一致。ZIP CRC、路径安全、
13 项 exact-set、12 项 return-manifest size/SHA、源包 allowlist 子集与
48 项 required-missing 补集均通过。

绑定冻结源包：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v3_cwd.zip
SHA256 = 3d6c8c580e178717b1c0a9bf70f5c55fd8cbcc8a74c7e9b5673f36b743604c80
```

return 内的 package manifest、`sca_cfg.json`、`sca_cfg_D.json` 与源包逐
字节相等；源 ZIP 与 post-install 均不存在 formal runtime D 目标。
package/install preflight 均通过，25 项 preload、48 项 readback、
`Repeat_Num=8` 均正确。

执行结果：

```text
compile_exit_status       = 0
compile/elaboration       = 0 error / 1 warning
simulation_exit_status    = 125
runner_exit_status        = 124
natural terminal          = false
formal D present/missing  = 0 / 48
missing by role           = 16 sum + 16 scaled + 16 final
mismatch bytes            = 0 (不可评估)
result conjunction        = false
E3 / E4 / E5              = FAIL / FAIL / FAIL
```

`mismatch=0` 与 `missing=48` 同时出现时不能解释为数值通过。

机器报告：

```text
artifacts/operator_config_validation/r5-gap-node0071-v3-return-analysis/report.json
SHA256 = e17e506c1e24d9c7a8129e237051de58b259f87e5ceb11397496d1414f314665
```

## PROGRESS_ADJUDICATION

return 的确定进度：

```text
sim.log:1928/1929  SCA/SCA_D 使用 v3 正式 namespace
sim.log:3871       25 matrices loaded @ 701958000 ps
sim.log:3873       Reg Started
sim.log:3891       first slice start @ 702678000 ps
sim.log:4812       Interrupt at time 30578904375 ps
```

首个 Start_Comp 后仿真时间推进 `29.876226375 ms`，证明 simulator event
time 在推进；它不能单独证明 accepted transaction 仍在推进。

v3 虽携带并通过 package-local observer 的 SHA/XMR precompile，但 actual
simulator argv 没有 `+RETURN_OBSERVER`，sim.log 没有 enabled receipt，
return 也没有 observer log。因而缺少：

- stage / Start_Comp heartbeat；
- accepted read/data/write 与 completion 单调计数；
- last/terminal 状态；
- 声明的 stall window；
- host wall-clock 对 sim-time 的采样。

正式裁决：

```text
execution_state      = LONG_RUNNING_HANG_PENDING_ROOT_CAUSE
progress_adjudication = INSUFFICIENT_TO_DISTINGUISH_PROGRESS_FROM_STALL
hang_root_cause       = UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT
```

这不是把责任归给 RTL；同一 return 不能区分“仍在慢速前进”和“在某个内部
边界停滞”。

## FIRST_DIVERGENCE

最后一个已证明边界：

```text
25 preloads complete -> Reg Started -> first slice start
```

第一个未证明区间：

```text
sum_s1 Start_Comp
  -> LC/MSE0 accepted read
  -> GA accepted/completed output
  -> MSE4 accepted D write
  -> last-data accepted
  -> slice_cmpt_finish
```

分类：

```text
EXTERNAL_TIMEOUT_AFTER_FIRST_START_COMP_WITHOUT_PROGRESS_EVIDENCE
```

## 静态穷尽审计

- 冻结 execplan SHA：
  `0a1d2a0f39693477607910949bc8dccc07404a4c6beeae8508940b2301a51711`；
- 13 条 128-bit、25 条有效 64-bit 指令；
- 1 Clock_Enable、8 Load_Config、8 Start_Comp、8 同 mask barrier；
- stage 顺序为 sum_s1..sum_s6、tail_mul、tail_round；
- 地址、lifetime、coverage 与数值只消费冻结 complete local E2 收据，
  未重算。

本地 `1c49bd1` 只读 RTL 快照证明：

- `Slice_Execution_Manager.sv:300-306,423-449` 在 CMPT 中持续保持
  `sem2iga_exec_start`，直到 `slice_cmpt_finish`；
- `WR_Data_Channel.sv:531-550` 在正式最后一项 D write data 被
  `mem2mse_wdata_ready` 接受后产生 `slice_cmpt_finish`。

因此完成路径在 RTL 中存在；但缺少动态 qualified handshake 计数，不能
证明它在本 workload 上可达或不可达，也没有发现可合法直接修复的确定
配置/RTL 首错。

## BLOCKER_DELTA

关闭：

- `B_GAP_V2_TB_FIXED_RELATIVE_PATH_RUNNER_CWD`
- `B_GAP_SERVER_RTL_COMPILE_INTERFACE`

新增：

- `B_GAP_NODE0071_V3_LONG_RUNNING_HANG_ROOT_CAUSE`
- `B_GAP_NODE0071_V3_PROGRESS_EVIDENCE_ABSENT`
- `B_GAP_NODE0071_V4_DIAGNOSTIC_RETURN_PENDING`

保持：

- `B_GAP_NODE0071_DYNAMIC_RESULT`
- `B_GAP_SERVER_RTL_IDENTITY_UNBOUND`
- `B_GAP_E4_E5`

## RULE_DELTA_PROPOSAL

`NONE`。当前服务器规则已经覆盖 timeout/manual interrupt、先穷尽证据、
不得延时优先重跑，以及下一长任务包必须实际启用并回收进度证据。

## PACKAGE_RELEASE

没有功能候选。仅生成唯一新身份的只读定位包：

```text
install_name = r5_n71_gap_v4_hangloc
status       = DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN
ZIP          = artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v4_hangloc.zip
ZIP bytes    = 1781182
ZIP SHA256   = 3c49472421dbf9e7a1cfc9bab42bdc677db6d2dc2781fb4ad18ff119968ac730
sidecar SHA256 = 5acf5c37b83b37c0117f94b7fcdef1204041684fc2aff9e9163dee176f1e3cf7
validation SHA256 = 9576d18c71f040bd08810187a4cee1c530a87380fb18115d3fe6d714f487d632
```

包边界：

- 73 个冻结 workload 文件逐字节相等；只重绑 fresh install namespace；
- 不重建 GAP sum/tail/config/golden/execplan；
- 不修改功能 RTL；
- 保持原 12h timeout，不用“多等一会”替代定位；
- actual argv 默认启用 package-local read-only observer；
- heartbeat=`262144` cycles，stall window=`1048576` cycles；
- 强制 allowlist 回收 progress contract、actual argv、host timing、
  signal status、progress samples、observer binding 和 observer log；
- formal D 初始目标仍为 0，联合门仍 fail closed；
- 两次 fresh build tree/ZIP 相等；
- ZIP CRC 通过，共 124 项，runtime readback 预置项为 0；
- fresh-extract preflight 不改变包树；
- Git-for-Windows bash 对 runner 做 `bash -n`，语法通过；
- focused tests 3/3 PASS，既有 v3 regression 1/1 PASS。

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

```text
r5_n71_gap_v4_hangloc_return.zip
r5_n71_gap_v4_hangloc_return.zip.sha256
```

声明：

```text
numeric_analysis_repeated=false
sum_tail_retested=false
frozen_v3_source_consumed_read_only=true
frozen_complete_local_e2_consumed=true
functional_fix=false
functional_rtl_modified=false
server_inspection_outside_return=false
server_upload_or_run=false
```
