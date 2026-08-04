# Conv node0004 v4 长时间卡死重审

日期：2026-07-30  
Owner：Conv / SA  
主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 收据

- `.agents/plan.md`：`0a32926c67670a2e1d43cddf809ae7284eb62b8f859772647703bf6ecde36010`，仅 mutable provenance。
- `.agents/rules/服务器测试包生成规则.md`：`2e5cf649cd721f4444b0caca2d1ea6670823c02d9d86784d6d228351ea8c7227`。
- 活动规则：`CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`、`CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001`。
- v4 return：`14ae820aeba624d92189f482603f8777f9fd8c43c01a3e9b455b03fe0e5e0983`。
- v4 return sidecar file：`aba44451471615d1b2a330b17e7354d352cf5e0067e805f24e4c264ae80205ba`。
- 冻结 v4 source package：`61e28a7c218230869ad1a5247023edb9bf8ee9af5a0660124fc8966ce5ad239e`。

## RETURN_ANALYSIS

v4 编译和 elaboration 通过，86 个输入矩阵全部载入，首个 c0 的寄存器启动与
`slice start` 已出现。仿真从 `2446089000 ps` 推进到 `25995990725 ps`，
即 Start_Comp 后约 18,839,921 个 `clk_db` 周期，随后 exit 124。没有自然
terminal。正式 D 为 `present=0 / expected=320 / missing=320 / mismatch=0`；
这不是数值通过。

按活动规则，本轮状态为 `LONG_RUNNING_HANG_PENDING_ROOT_CAUSE`，不能再使用
“observer 没启用”或“多等一会”结束裁决。

## FIRST_DIVERGENCE

最后一个确定进展点是 c0 的 Load_Config / Write_Reg / 第一个 Start_Comp 已到达
slice。第一处未证明边界是 Start_Comp 后首个限定内部事务，最窄区间仍为：

```text
read request/data
  -> read buffer / SA input match
  -> SA transout / buffer5
  -> D request / accepted write data
  -> last_index=0 / slice_cmpt_finish
```

v4 return 没有上述任一边界的 qualified handshake 计数，`sim.log` 在 monitor
初始化后直到 interrupt 也没有新的功能事件。因此不能从同一 return 再缩窄到某条 RTL。

## 穷尽静态审计

已经排除：

1. 编译、elaboration、路径 root binding 和 Start_Comp 前 loader 失败。
2. 类似 QAdd 37632 的 signed-feedback wrap：240 条最终 LC 的 start/stride/end
   均在 signed16 范围内，最大 end=3136，Conv c0 最大 end=56；正 stride 均可达。
3. 非有限 occurrence/address：c0 每片 A/B/C/D 请求分别为
   256/50,176/1,568/12,544，D=200,704 bytes。
4. tail 或后续 barrier 是首因：c1、c2、tail 均未启动；barrier 正在等待 c0 完成。
5. terminal 在源码中完全不存在：`RD_Buffer_AG` 明确接受 last_index=0，
   `WR_Data_Channel` 明确产生 `slice_cmpt_finish`，Execution Manager 明确消费它。

没有被静态证据证明为错误：

- SA `transout_last_index=2`、buffer tag/lifetime、SA output backpressure 和
  D last_index=0 的组合是可表达的；但没有动态 tag/ready 证据证明哪一环实际前进。
- DataC/psum 配置存在，不能据此证明运行时 SA 已接受或输出任何 occurrence。
- 仿真推进很多周期既不能单独证明 stall，也不能单独证明仍在前进。

## HANG_ROOT_CAUSE

`UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT`

这是证据边界，不是把责任归给 RTL。现有证据仍无法区分：

- 读请求未发出；
- 请求已发出但数据未回；
- 数据已回但未进入 SA；
- SA 输入后没有 transout/buffer5 写；
- buffer5 没有进入 D 请求；
- D 请求没有 accepted data；
- D data 已写但 last_index=0/finish 未到；
- 人工中断时仍在持续前进、只是尚未跑完。

## 精确诊断包

仅因现有证据穷尽后仍无法定因，生成：

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v6_hangloc.zip`
- bytes：`5,802,669`
- SHA-256：`2a0ecf7e0218a2a65d37d281ef46343f66e20ca4359cfacf062bf88f89dd1021`
- 状态：`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`
- observer：`9a6cc0f3c4d7e9235199ecc33d2ba4649462b7b64fcc1235aa1ce7f77d53f82e`
- source：冻结 v4 package，不重建 node0004 workload；只保留 c0。
- 功能 RTL entries：0。

诊断机制：

- host 每 60 秒记录 `/proc/uptime` 单调时间、当前 c0、observer bytes 与最后进度摘要；
- simulation 每 262,144 周期记录限定事务单调计数；
- 连续 4 个窗口（1,048,576 周期）无任何限定事务进展时，停止并输出八选一
  `DIAG_DECISION`；
- 8,388,608 周期为诊断预算，不延长 v4 的 12h 运行窗；
- EXIT/HUP/INT/TERM 均回收 host progress、simulation progress、实际 argv、signal
  和最后边界；
- 计数连续增长时只能判“仍在前进未跑完”，自然 terminal 才能判 c0 完成。

两次全新构建 tree/ZIP 完全一致，CRC 通过，专项测试 5/5 PASS。该包不做正式
readback，不是功能修复，不是 Conv candidate，不声明 E4/E5。

原 `r5_n4_hw_v5_observe.zip`
`fb7a36e380c1329c29faf9170a0e117715bdc0d0198bc0568e47298d517844cb`
保持 `QUARANTINED_PENDING_HANG_REVIEW`，禁止上传/运行。

## BLOCKER_DELTA

- ADD：`B_CONV_NODE0004_C0_LONG_RUNNING_HANG_ROOT_CAUSE`
- KEEP：`B_CONV_SERVER_DYNAMIC_RELEASE`
- KEEP：`B_CONV_SERVER_RTL_IDENTITY`
- KEEP：`B_CONV_INT8_SA`
- CLOSE：无

## RULE_DELTA_PROPOSAL

无。活动规则已覆盖本轮 timeout/manual interrupt 与长任务进度定位要求。

## PACKAGE_RELEASE

- 功能候选：`NONE`
- 诊断包：`r5_n4_hw_v6_hangloc.zip`
- 分类：`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`
- 本地未上传、未运行、未检查服务器。
- `numeric_analysis_repeated=false`
- `node0004_workload_rebuilt=false`
- 消费的复用资产：冻结 v4 c0 输入、已接受的最终 JSON/mapping/bitstream/execplan/SCA
  与本地 E2 合同，仅作只读 provenance。
