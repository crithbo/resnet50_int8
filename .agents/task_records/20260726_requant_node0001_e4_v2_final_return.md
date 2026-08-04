# Requant node0001 全量 E4 v2 正式回传裁决

日期：2026-07-26

## 身份

```text
requant_node0001_two_stage_stockrtl_e4_onecmd_v2_return.zip
size=67937
sha256=0edfd1dda28b82cf52dc01c9e51f4b3d4854fb34819626fa5bc72c52322d1197
entries=26
```

`RETURN_RECEIPT.json` 的 25 条 allowlist 文件记录全部与 ZIP 内 size/SHA
一致，无额外项、无缺项。包内 manifest SHA256
`cb4d045025d8fc98c899144fd74a59cb77667ac222c764c7677ff9bdf93b4411`
与本地冻结全量 v2 逐字节一致。

这是此前 `12.zip` 中途快照所对应同一次服务器运行的正式 finalizer 回传。
`12.zip` 仍不另计 attempt；本正式回传应计为一次正式 E4 失败尝试。

## 裁决

```text
status=E4_FAIL_OR_INCOMPLETE
classification=FIRST_DYNAMIC_FAILURE
dynamic_baseline=NO_DYNAMIC_BASELINE
evidence_level=SERVER_INCOMPLETE
compile_exit=0
sim_exit=124
run_exit=124
candidate_release=false
E5_allowed=false
remaining_blocker=B_REQUANT_SERVER_E4_E5
```

## 已证明

- package/installed preflight 通过；
- VCS compile 通过；
- observer 在 compile 前逐字节验证，compile 后恢复；
- functional RTL、focused RTL 和 support identity 通过；
- 48/48 stage start、48/48 finish、48/48 same-mask barrier 全部自然完成；
- 失败不是计算 stage 卡在第 1 个，也不是 RTL compile 失败。

## 运行不能结束的根因

活动 `tb_NDP_Top_new_phy.sv` 的外层完成循环不是 mask-aware：

```text
每次固定等待 physical slice0 Start_Comp
随后固定等待 physical slice1 slice_cmpt_finish
重复 Repeat_Num=48 次
```

全量 v2 的 mask 按 slice 组轮换，单个 stage 并不同时包含 slice0 和 slice1。
因此 TB 实际形成三次跨 stage 错误配对：

```text
stage0  slice0 start -> stage12 slice1 finish  (839509 cycles)
stage16 slice0 start -> stage28 slice1 finish  (839518 cycles)
stage32 slice0 start -> stage44 slice1 finish  (839318 cycles)
```

stage44 后 TB 等待第四个 slice0 start；剩余 stage46/47 只启用 slice1+5，
之后不再有 slice0 start。尽管执行计划已在 `25972316000` 完成 stage47，
TB 主流程仍永久停在该等待中，最终被 runner 的 12 小时外部 timeout 终止为
124。

分类：

```text
STOCK_TB_COMPLETION_MASK_INCOMPATIBLE
```

这不是“正式 D 太大所以只是慢”，而是确定的 TB 完成观察与 mask schedule
不兼容。

## 数值证据边界

SCA_D 未开始：156/156 正式回读文件都不存在，`JSON_D ... dumped` 和
`Simulation completed successfully` 均未出现。因此不能称为 final UINT8
或 resident guard 数值不匹配。

历史 guard observer 门也未闭合：128/128 项均地址不连续，每项只有
13327/13328 个 unique address，预期 25088；总 coverage 约 53.124%。
回传没有携带 raw observer logs，且无正式 D，所以该栏只能证明 observer
gate 失败，不能进一步区分真实 MSE4 写错误与 observer 的地址单位/请求到
wdata 配对错误，也不能据此定性 RTL bug。

## 下一动作

禁止原样重跑全量 v2。应先运行已生成的
`rq_node0001_atomic2_stock_v1.zip`；它的 guard/round 两个 stage 均启用
slice0+slice1，正交消除本次 TB 完成 mask blocker，同时保留两阶段语义和
20 个 accepted MSE4 write 证据。

机器分析：
`server_returns/requant_node0001_e4_v2_final_return_analysis_20260726.json`。

## 规则维护总账登记

本次正式回传已登记到 `contracts/resnet50_project_closure.json`：

```text
all server E4 attempts = 3
Requant node0001 formal E4 attempts = 2
formal E4 passes = 0
formal E5 passes = 0
current Requant failure class = STOCK_TB_COMPLETION_MASK_INCOMPATIBLE
v2 lifecycle start/finish/same-mask fence = 48/48/48
formal D files = 0
guard observer root cause resolved = false
```

三次正式 E4 attempt 分别为：

1. Dequant node0077：compute started、未完成、无正式 D；
2. Requant node0001 v1：observer include 编译基础设施失败；
3. Requant node0001 v2：48 stage 全完成，但 stock TB completion tracker 与轮换
   mask 不兼容，SCA_D 前 timeout。

`12.zip` 与第 3 项是同一次运行，仍不另计。observer gate fail 只登记为 unresolved
evidence gate，不登记为 RTL/config root cause。

总账身份：

```text
contracts/resnet50_project_closure.json
sha256=c1e8b44d16d74e9e69ab255041f1fe46e1c750bfd0d6e5b097281267224905da
```

因 Requant 专项规则 SHA 已在前序任务更新，本轮一并刷新直接 hash-bound 的 stage
backend、stage config system、derivation matrix、state/lifetime 和 local closure；
project-closure 定向测试 4/4 PASS。
