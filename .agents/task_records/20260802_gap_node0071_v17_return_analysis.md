# GAP node0071 v17 stage1-flow return 正式裁决

日期：2026-08-02  
实际 GAP analysis owner task：`019fa366-cb1f-7ae2-880c-f527be0680cd`  
唯一回传主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
任务边界：只读解析正式 return、消费冻结源包/本地合同、输出机器报告与本 task record。未重做 numeric/sum/tail/workload/config/golden，未修改 plan/public rules/functional RTL，未访问、上传或运行服务器，未生成后继包。

## 1. Current control receipts

| 文件 | SHA256 |
|---|---|
| `.agents/agent.md` | `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0` |
| `.agents/plan.md` | `7fd915afa1bd150e55c1a4f2e5a3db3af406d06574868ce0b66f412c8b5ba703` |
| `.agents/rules/生成前必读索引.md` | `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f` |
| `.agents/rules/服务器测试包生成规则.md` | `fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025` |
| `.agents/rules/GAP_int32_mac_bypass_rules.md` | `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b` |
| `.agents/rules/GAP_probe_v7_validator_rules.md` | `4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |
| 冻结 v16/v17 task record | `bee0d9691f14422a1bf9755e8321b45b9a8f2ed4c3464717c99b6319ec2fc5f0` |

所有 current SHA 与任务下发值一致；plan 仅作为 mutable provenance。

## 2. Return/source receipt

- Return：`C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n71_gap_v17_stage1_flow_diag_return.zip`
- Return bytes：`155635`
- Return SHA256：`9c8f25bd7f889d047487e7f5687808fefe4525fce401dbc408a70484713c66dd`
- 相邻 sidecar：不存在。按用户传输担保和 `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001` 接受；担保只替代外部 sidecar。
- 冻结源包：`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v17_stage1_flow_diag.zip`
- 源包 bytes：`1800157`
- 源包 SHA256：`d4ff6ba01f96626de2977bbf3ba5216644255b948b872b800c6976ddf3d227d6`
- 源包身份：package/install=`r5_n71_gap_v17_stage1_flow_diag`，run=`run_r5_n71_gap_v17_stage1_flow_diag`，return=`r5_n71_gap_v17_stage1_flow_diag_return`。
- 源包类别：`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`；不是 candidate release。
- 源包 final-ZIP self-audit：PASS，errors=0；报告 SHA256=`6e1536e3827f4179ce5f65fd746b754a689fae5712b02667582cac3410461ad1`。

## 3. Return structural adjudication

- ZIP：23 entries；单一 root 正确；CRC、path safety、duplicate-free、symlink-free 全通过。
- `RETURN_MANIFEST.json` SHA256=`697e85b717c8f58e35a0b8ac02c415d22ee027d35c325ec38ce8e7a604a4e6ae`。
- manifest 状态为 `incomplete`；22 个返回文件逐项 size/SHA 匹配。
- allowlist-only=true；exact-set=true。
- 返回 `PACKAGE_MANIFEST.json` SHA256=`a6d202173b4724112d25054b9581583d6fc595b5e0ff804f5f14e0fd72768f06`，与冻结源包 manifest 逐字节相同。
- return allowlist 共 70 项；48 项 formal D required 全部 absent，optional absent=0；`required_missing` 与实际 absent 集合严格相等。
- `sca_cfg.json` SHA256=`647b738e68dce92c31a35fb07c16d0e9cfb658d5b4dfc7447d00b54a8c4789c0`、`sca_cfg_D.json` SHA256=`ecf8b2f32186b9513876992191cd7b150e5ef88e8cccb08d53479ad4122f34ea`，均与冻结源包 workload 逐字节相同。
- package/install preflight 均 valid；48 个 runtime formal-D target 初始不存在。

## 4. Observer/STAGE1_FLOW enable binding

- package-local observer source SHA、`+incdir`、enable macro、actual compile argv、actual simulator argv、time0 marker、return observer log 全闭合。
- `observer_enabled_and_returned=true`。
- `STAGE1_FLOW_COUNTS_V1` 与 `STAGE1_FLOW_STATE_V1` 实际返回；其零值/计数可作诊断证据。
- STAGE1_FLOW records 不进入 canonical monotonic progress；full/empty/ready/request/tag 等 level 只作状态。
- Observer self-test SHA256=`967a9690abd7b130352ea15e211f8368e8a0cc4b0f1bd852867bda59742b7f85`，status=PASS；持续高 level、summary-only、冲突双裁决、缺 reason、缺 boundary 均 fail closed。

## 5. Compile/run/formal-D 联合门

- compile exit=0；elaboration 0 errors；`simv` 生成。
- simulation exit=125；runner exit=125；signal=`INT`。
- package wall=`23199.253495445 s`；simulation wall=`23142.166744697 s`（约 6.43 h）。
- 最终 simulation time=`233656704375 ps`。
- natural terminal=false。
- formal D：expected=48、present=0、missing=48。
- mismatch bytes=0 但不可评价，不能作为 PASS。
- `SERVER_RESULT_GATE.json` SHA256=`d5a2827ac8b143f1dab685e1a631599b9cfbc72a2699070b90ed79d4ea5d9d35`；联合门=false。
- E3=false，E4=false，E5=false。

## 6. Qualified progress 与最窄停点

已证明的合格事件：

- EXEC_START：`702681000 ps`。
- MSE3→Buffer4 data accept：10 次，`702764000..702832000 ps`。
- MSE0→Buffer0 data accept：10 次，`702772000..702837000 ps`。
- GA input/output accept：32/32。
- MSE4 write-data accept：16；最后一次 `702827000 ps`。
- source-domain edge 计数持续推进到 `93061120`，排除 source clock 停止。

v17 stage1-flow 首个 heartbeat（`1030359000 ps`）已经到最终值，随后 710 个 heartbeat 保持相同：

| 计数 | MSE0 | MSE3 |
|---|---:|---:|
| Buffer-AG index queue accepted write | 14 | 18 |
| Buffer-AG index queue accepted read | 4 | 0 |
| WR_Buffer_AG accepted address write | 4 | 0 |
| WR_Buffer_AG accepted address read | 6 | 10 |
| ARM accepted | 2 | 0 |
| ARM clear | 2 | 0 |

最终 level/state：

- 两个 Buffer-AG index queue 都 full/nonempty（`q_full=0x3`, `q_empty=0x0`）。
- 两个 WR_Buffer_AG output buffer 都 empty/not-full。
- `arm_req=0xffff`、`arm_ready=0x0`、`ga_stored_tag=0x0`；这些只作状态，不计 progress。

注意：write accept 是累计合格事件计数，不等于 FIFO 最终 occupancy；队列深度为 16，最终 full 由状态独立证明。MSE3→Buffer4 的 data accepts 可能消费 EXEC_START 计数清零前已准备的 address/data，因此不证明本轮发生新的 MSE3 Buffer-AG queue dequeue。

### LAST_PROVEN_GOOD

`MSE3_BUFFER_AG_INDEX_QUEUE_ENQUEUE_ACCEPTED`

MSE3 在 EXEC_START 后记录了 18 次合格 queue write，最终 queue full/nonempty；同时两条 producer→Buffer data path 均有 10 次 accept。

### FIRST_DIVERGENCE

`MSE3_BUFFER_AG_INDEX_QUEUE_DEQUEUE_AND_WR_BUFFER_AG_ADDRESS_WRITE_ABSENT`

在 710 个一致 heartbeat、93061120 个持续推进的 source-domain edge 中：

- MSE3 queue read 始终为 0；
- MSE3 WR_Buffer_AG address write 始终为 0；
- queue 最终 full/nonempty。

MSE0 至少完成了 4 次 queue read/address write 后也停止。第一条更严格的缺失边界是 MSE3 的零 dequeue。

### HANG_ROOT_CAUSE

`LONG_RUNNING_HANG_AT_MSE3_BUFFER_AG_BP_PRE_CONJUNCTION_PENDING_LEAF`

本地只读 RTL 方程：

```text
buf_ag_idx_queue_rd_en = mse_buf_ag_bp_post
mse_buf_ag_bp_post = buf_ag_bp_pre
buf_ag_bp_pre =
    !buf_ag_ob_full
  && rd_data_chl_data_ready
  && !nse2mse_req_barrier
```

最终状态已排除 `buf_ag_ob_full` 为 1，但 v17 没有返回其余两个输入因子的独立证据。因此叶级原因只能保持：

```text
rd_data_chl_data_ready == 0
OR
nse2mse_req_barrier == 1
```

不能在现有证据上确定为配置错误、RTL 错误或服务器环境错误；也不能先延长 timeout。

相关只读 RTL SHA：

- `Buffer_AG_Idx_Queue.sv`：`bbf2d8542f29229953395edf28d9a9cfe48030419753ee52bc62cc09e6028e4d`
- `WR_Buffer_AG.sv`：`8db8ad4af47a3ddf911ab18a178fdc5288d7daebe8694c5c7380d8bea4e98c2b`
- `Array_Request_Manager.sv`：`112be21e7e1ec7e7c863086778d887cb09ac39a7f28d59f5e9b3e8c29ca71a49`
- `Buffer.sv`：`461736f72dc25c79b0f12f310f00d90c1da0f1be0d89d3bcc0f8d4cf4a7ca690`
- `GA_PE_Inbuffer.sv`：`25fa4dd2c6fe8301bc3651d660df72059ea2787c0c26a2841a1d4e439586b518`

## 7. Blocker delta

Closed：

- missing adjacent sidecar 在用户担保边界内内容中性。
- ZIP/internal identity/exact-set/allowlist/source binding/config binding/preflight/observer/STAGE1_FLOW enable 全闭。
- 原先宽泛的 Buffer→GA ingress gap 已上移并收窄到 MSE3 Buffer-AG queue dequeue / `buf_ag_bp_pre` conjunction。

Open：

- natural terminal 缺失。
- 48 formal D 全部缺失。
- `buf_ag_bp_pre` 叶级仍未在 read-data readiness 与 request barrier 之间闭合。
- E3/E4/E5 全部开放。

## 8. Proposal only

`RULE_DELTA_PROPOSAL`：

- 建议 ID：`CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001`
- 多输入 ready/backpressure conjunction 的停点诊断必须分别返回每个 conjunct 的 owner 与合格/限频证据；conjunction output 为 0 只能收窄区间，不能指认叶因。
- 仅为 proposal，不修改公共规则。

`SUCCESSOR_PROPOSAL_OR_NONE`：

- 本轮不生成后继。
- 若主线/用户另行授权，仅建议 `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX` successor。
- 73 个 numeric 文件及 sum/tail/workload/config/golden/functional RTL 必须逐字节冻结。
- 唯一新增证据：MSE0/MSE3 的 `buf_ag_ob_full`、`rd_data_chl_data_ready`、`rd_data_chl_data_vld`、prepared-data count、`rd_data_chl_ob_full`、`nse2mse_req_barrier`，并与 `buf_ag_idx_queue_rd_en`/`buf_ag_ob_wr_en` 对齐；stable level 不得计为 progress。

`PACKAGE_RELEASE=NONE`。

## 9. Deliverables and local verification

- 机器报告：`artifacts/operator_config_validation/r5-gap-node0071-v17-return-analysis/report.json`
- 机器报告 SHA256：`79380595960c61cf6610d5ebd5968a51a49c1ac688a1b780af5c75a16d67faca`
- JSON `ConvertFrom-Json`：exit 0。
- Return `Get-FileHash`/size receipt：exit 0。
- ZIP CRC/path/root/exact-set/allowlist/source-binding checker：exit 0。
- Config byte-equality check：exit 0。
- 本 task record SHA 在最终字节冻结后独立计算并由外部结构化回传携带；不在文件内自嵌，避免自引用改变被哈希字节。

工作区修改仅为本机器报告、本 task record，以及用于只读分析的本地 extraction tree；未修改任何冻结功能/控制资产。

## 10. Provenance correction receipt

- 原 `analysis_owner_thread=019fa2ca-72bc-7753-8d58-81e59bc76c88` 是字段错误：该值是旧主线，不是执行本次 v17 return 分析的 owner task。
- 已纠正为实际 GAP owner task `019fa366-cb1f-7ae2-880c-f527be0680cd`。
- `return_target_thread=019fbec2-fe93-7e03-9314-cff6f222f33d` 保持不变，继续表示唯一结构化回传主线。
- 除 provenance 字段、对应机器报告 SHA 收据和本节外，return 证据、裁决、blocker、proposal 与 `PACKAGE_RELEASE=NONE` 均未改变。
