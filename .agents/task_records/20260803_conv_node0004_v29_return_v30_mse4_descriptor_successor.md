# Conv node0004 v29 return → v30 MSE4 descriptor successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- target mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- numeric/W3/qparam/tail/workload/config/golden repeated: `false`
- functional RTL/public rules/plan modified: `false`
- server upload/run/lease: `false`

## RETURN_ANALYSIS

正式 return `r5_n4_hw_v29_datahub_drain_diag_return(1).zip` 重算为 99,367 bytes，SHA256 `80bc305d70106952a15887e9e72b275d8572126d5dd46d17087523c37656d069`。相邻 sidecar 缺失仅按用户传输担保规则作内容中性处理；ZIP CRC、单根目录、路径安全、duplicate/symlink、RETURN_MANIFEST exact-set/allowlist/per-file receipts、冻结 source v29 身份、package/install preflight、runtime-D absent 均通过。

真实动态门：compile=0、run=0、signal=NONE、simulation 已启动并由诊断预算 `$finish`，但 DUT natural terminal=false；formal D 期望 320、存在 0、缺失 320、mismatch 0。因此联合门=false，E3/E4/E5 均为 false；all-missing 不得由 mismatch=0 解释为数值通过。

## LPG / FD / HANG_ROOT_CAUSE

- LAST_PROVEN_GOOD: `MSE4_DATAHUB_LOCAL_CHANNELS_8_9_EACH_ACCEPTED_ALL_7_ADDRESS_DATA_PAIRS_THROUGH_BANK_CROSSBAR_AND_DRAINED`
- FIRST_DIVERGENCE: `MSE4_WR_MEMORY_DESCRIPTOR_TO_WR_DATA_CHANNEL_RELEASE_OF_FINAL_TWO_PREPARED_GROUPS`
- HANG_ROOT_CAUSE: `UNRESOLVED_AFTER_EXHAUSTIVE_V29_BOUNDARY`

qualified 动态计数显示：16 个 prepared groups、14 次 WR_Data_Channel output write、14 次 sink accept；最终 prepared_count=32、RD_Buffer_AG queue_count=2/full=1。DataHub local channel 8/9 各自接受并经 crossbar 送出 7 对 address/data，最终 queue_full 均为 0。因此 DataHub ingress/bank-match/crossbar/drain 不是首分歧，最后两组停在 MSE4 descriptor 到 WR_Data_Channel release 区间。

现有证据仍不能唯一地区分：WR_Memory_AG 未为最后两组发 descriptor；descriptor FIFO push/pop/head 丢失或提前消费；descriptor 存在但 prepared-data/交替 output-buffer eligibility 阻止释放。没有据此宣称确定功能 RTL 缺陷。

## Current local RTL identity

successor 的 package-local provenance 显式绑定本地活动 RTL commit `d0aa87f682880a260fb792aaac88f70a23aba414` 和同步报告 SHA `fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771`。该绑定只说明本地静态消费者身份；服务器运行 RTL identity 仍未绑定。同步报告仍为 `SOURCE_SYNC_PASS_FUNCTIONAL_REPAIR_NOT_CLOSED`，不得把字节同步当成功能修复。

## BLOCKER_DELTA

- closed: `B_CONV_NODE0004_MSE4_TO_DATAHUB_LOCAL_CHANNEL_DRAIN_UNOBSERVED`
- opened: `B_CONV_NODE0004_MSE4_DESCRIPTOR_TO_WR_DATA_FINAL_TWO_GROUPS_UNOBSERVED`
- kept invalidated: `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`

## PACKAGE_RELEASE

- status: `PACKAGE_READY_NOT_RUN`
- class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- candidate_release: `false`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v30_mse4_descriptor_diag.zip`
- bytes: `5837621`
- SHA256: `0c358f254cac4128a7a320a4201a50f266f1620105fd9b859cf26ac84aa6ad81`
- sidecar SHA256: `d90fac09cf883995082c4187b7d657b3be0f376b13f1e300ec13054f7b1ad8a9`
- command: `bash r5_n4_hw_v30_mse4_descriptor_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return: `r5_n4_hw_v30_mse4_descriptor_diag_return.zip`

v30 仅新增限量 `RETURN_OBS_MSE4_DESCRIPTOR`：qualified 记录 WR_Memory_AG descriptor handshake、descriptor FIFO actual push/pop、memory request、prepared-data write/read、output-buffer write/read；FIFO/count/full/empty、prepared count、selector 和 transaction state 仅作旁证。

双构建相同。最终 ZIP current-rule 独立自检 `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0。focused Icarus 正控 exit0；拼错 leaf、删除 declaration、破坏 task syntax 分别 exit1/1/2；删除 qualified update 虽 frontend exit0，但 semantic closure fail closed。安全 runner 正控抵达 compile/finalizer（预期 runner exit74）；TERM harness/runner 为 0/143；五类 canonical negatives 与四类 feature binding negatives 全部 fail closed。

## RULE_CONFIRMATION

本轮确认 current `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`、`CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`、`CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`、`CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`、`CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`、`CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`、`CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001` 与 `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001` 已覆盖本轮 escape/交付门。本轮无非同义公共规则缺口，不提交 RULE_DELTA_PROPOSAL。

机器报告：`outputs/conv_node0004_v29_return_analysis/successor_release.json`。
