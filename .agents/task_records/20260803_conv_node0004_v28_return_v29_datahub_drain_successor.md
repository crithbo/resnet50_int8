# Conv node0004 v28 return → v29 DataHub drain successor

日期：2026-08-03  
owner/provenance：`019fa2c1-17df-7122-bcbd-a727aaf173f5`  
唯一回传主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 1. 范围与收据

本轮按用户最新指令停止 node0075，只处理 node0004 v28 正式 return。没有重算
numeric/W3/qparam/tail/workload/config/golden，没有修改功能 RTL、公共规则或 plan，
没有服务器动作。

post-generation current-match：

- `.agents/agent.md`：
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- `.agents/plan.md`（mutable provenance）：
  `7b1f670e5d12c9bb8ad6d04a00f8a49e8bbd476362790bc7751c08012e62ae5a`
- `.agents/rules/生成前必读索引.md`：
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- `.agents/rules/服务器测试包生成规则.md`：
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- `.agents/rules/INT8_SA点积专项规则.md`：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`：
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

## 2. RETURN_ANALYSIS

return：

- path：
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_hw_v28_dwrite_path_diag_bind_return.zip`
- bytes：`98399`
- SHA256：
  `959b945ebaa40dfcbedbdac73b3fcbb98f5fdf96f3dfa77dde8bd0971009c4a9`
- adjacent sidecar：缺失；按
  `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`
  内容中性。

冻结 source：

- `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v28_dwrite_path_diag_bind.zip`
- bytes：`5832618`
- SHA256：
  `a3b2be33d395356b06c96e8311c017544cbdcc7b3e553006ae582acea176101f`
- source sidecar SHA256：
  `d5ac9edd25b06c8782460170a0c0adb8efadbdfb4ded3dfcb272820810b830f9`

CRC/root/path/duplicate/symlink、RETURN_MANIFEST exact-set/allowlist、source/package/install
identity、package/install preflight、runtime-D absent、observer source/include/macro/runtime/
return 与五个 feature time0 binding 均通过。`compile=0`、`run=0`、`signal=NONE`，
simulation 启动并由诊断预算 `$finish`；DUT natural terminal 未发生。formal D
`expected=320, present=0, missing=320, mismatch=0`，联合结果门为 false，E3/E4/E5
全部为 false。

## 3. qualified 边界裁决

canonical 首窗 qualified progress=`234`，随后连续四个 `262144`-cycle window
`delta=0`。旧 transout threshold 停点已经越过：128 个 accepted terminal 均命中
`last_index=5`，`terminal_ignore=0`。

v28 D-write：

- MSE4 source：`prepare_accept=16`，source-side `wdata_accept=16`；
- sink `clk_sg`：ch0 `req=7,wdata=7,outstanding=0`，ch1 同样 `7/7/0`；
- source write queue state：`queue_count=2, full=1, wr_ready=0`；
- `slice_finish=0`，formal D 仍为 0/320。

跨时钟 source `clk_db` 的 level/counter 不被解释成与 sink `clk_sg` transaction
一一对应；sink accepted counts 才是入口事务权威。因此本轮没有把 source-side
`wdata_accept=16` 与其它计数差异误判成 RTL 重复写。

`LAST_PROVEN_GOOD`：

```text
MSE4_SOURCE_PREPARED_16_CHUNKS_AND_DATAHUB_ACCEPTED_
7_ADDRESS_PLUS_7_DATA_PER_CHANNEL_WITH_ZERO_OUTSTANDING
```

`FIRST_DIVERGENCE`：

```text
DATAHUB_LOCAL_WRITE_QUEUE_HEAD_TO_BANK_CROSSBAR_DRAIN_
WHILE_MSE4_SOURCE_REMAINS_BACKPRESSURED
```

根因尚未唯一：需要区分 queue head X/无 bank match、local read/write arbiter 未呈现
queued write、或 bank match 已建立但 crossbar ready 不断言。没有宣称功能 RTL 缺陷。

## 4. BLOCKER_DELTA

关闭：

- `B_CONV_NODE0004_D_WRITE_REQUEST_OR_DATA_ABSENT`
- `B_CONV_NODE0004_D_WRITE_ADDRESS_DATA_INGRESS_IMBALANCE`

打开：

- `B_CONV_NODE0004_DATAHUB_LOCAL_WRITE_QUEUE_TO_BANK_DRAIN_UNOBSERVED`

保留：

- `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`
- `B_CONV_NODE0004_FORMAL_D_320`

旧 `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED` 继续保持
`INVALIDATED_NOT_RTL_BUG`，没有复活。

## 5. v29 successor

唯一身份：

- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v29_datahub_drain_diag.zip`
- bytes：`5833915`
- SHA256：
  `4537f98ea18b281aa0f42f8355d7961594bbe0d3cd5991e906d708d9273173bc`
- sidecar bytes：`102`
- sidecar SHA256：
  `a41a2620e0fffeaf17209aeebcc24568aa97d1084e958896b971d97ab4f25128`
- classification：`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- `candidate_release=false`
- expected return：`r5_n4_hw_v29_datahub_drain_diag_return.zip`

唯一命令：

```bash
bash r5_n4_hw_v29_datahub_drain_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

v29 冻结 v28 workload/config/golden/timeout/backpressure/functional RTL，只增加
`RETURN_OBS_DATAHUB_DRAIN`（limit 64）。它对 local channels 8/9 记录：

- qualified address/data FIFO ingress；
- queue head valid、write-side arbiter grant、crossbar accept；
- head address X witness 与 no-bank-match witness；
- bank selector/match/ready 和 queue-full 只作 state corroboration。

## 6. 本地验证与命令退出码

1. return analyzer：exit `0`；报告
   `outputs/conv_node0004_v28_return_analysis/report.json`
   SHA256=`e6cffd8d7cdb2d260a78c541c5107580d98e06f175f5e79749c5a64b99477b33`。
2. v29 builder：exit `0`；两次全新构建 ZIP SHA 相等。
3. focused compatible frontend：
   `C:\iverilog\bin\iverilog.exe -g2012 -s datahub_focus_top ...`，
   positive exit `0`；拼错 consumer leaf exit `1`；删除声明 exit `2`；
   破坏 task syntax exit `2`；删除 qualified update 虽 syntax exit `0`，
   semantic closure validator fail-closed。报告
   `v29_datahub_observer_scope.json`
   SHA256=`e025dd529419748739fb7aa7002b3f233bb5048d10100be888cdf232e77a54e9`。
4. final runner safe-stub：validator exit `0`；safe compile/EXIT runner
   expected exit `74`，TERM harness exit `0`/runner exit `143`；wrong identity、
   canonical 双裁决/缺 reason/缺 boundary/level 伪进度均 fail closed。报告
   `v29_runner_controls.json`
   SHA256=`4b4f8e16fd46abea7092cee548dd035aa1ee5287e31ec6ce5e32a12d392637f8`。
5. 新 feature 四负控：删除 enable、删除 limit、删除 time0 marker、删除 return
   target 均 `valid=false`。
6. final-ZIP validator：exit `0`；
   `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、`errors=[]`。报告
   `v29_final_zip_audit.json`
   SHA256=`d6002657a83740fd9031d5ef41b7460cdc8a41de07d2ea60a27a0f62c864db64`。

机器 release：

- `outputs/conv_node0004_v28_return_analysis/successor_release.json`
- bytes：`6618`
- SHA256：
  `0ac0dbd6cbc3ac8638fb19d0e4e927a04d26fd85e11ac46121984f719bd1f8db`

## 7. RULE_CONFIRMATION

本轮实际确证：

- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`
- `CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`
- `CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`
- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`
- `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`

证据是 v28 按 qualified sink transaction 收窄而不抢判 RTL，及 v29 exact final ZIP
在 focused HDL、state ownership、runner、feature、canonical、identity 和 deterministic
门全部通过。适用范围只到 package/diagnostic controls；不声称服务器 VCS、自然完成、
formal D、功能 RTL 根因或 E3/E4/E5。无需新增同义公共规则。

`PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`。未上传、未运行服务器、未取 lease。
