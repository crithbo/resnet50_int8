# Serialized Conv node0004 v94 return / v95 local-gates-complete

## 上一版本进度

v88b 已证明旧 derived ACK comparator 是 observer/source-identity 语义误报；v93d 把真实停滞边界收窄到 WR_Data_Channel prepared-data occupancy/drain。v94b production compile=0、target_entry=true，73/73 actual-source 信号流式读到 EOF；运行由用户外部 INT 结束，不是自然终止。

## v94 实际定位

LAST_PROVEN_GOOD=2,446,430,625 ps：最后一次 WR drain 成功。FIRST_DIVERGENCE=2,446,431,875 ps：新的 16-entry prepared group 把 occupancy 从 16 推到 32，但没有匹配 WR metadata。最终 prepared_count=32、metadata queue empty、WR output empty/ready、memory wdata ready=11，output/memory downstream backpressure 已排除为主因。动态已证边界是 prepared-data 与 WR-metadata lifetime 不匹配；剩余二选一是 metadata 提前结束或 Buffer/RD data 多生成两组。

cannot-open warning 来自 package TB 轮询尚不存在的 shared_stop.control，非致命；`0001001` 是 sim.log 的 APB 配置读写十六进制回显，没有纯二进制日志行。理论时间接近结束不是 terminal，slice_finish 始终未置位。

## 三层直接证据

DIRECT_CONFIG_EVIDENCE：冻结 stream4 为 write，buf mode=[keep,buffer]、keep_last=[5,5]、spatial_size=16，mem mode=[keep,buffer,keep]、keep_last=[0,3,1]。旧 PE1 keep_last_index=3 修复已经存在，不能用旧值回归解释本次 mismatch。

DIRECT_ACTUAL_RTL_EVIDENCE：v94 return 绑定了 actual compiled WR_Data_Channel、Buffer_AG_Idx_Queue 与 Memory_WR_Stream_Engine 顶层连接。prepared count 按 +spatial_size/-metadata transfer size 更新；metadata FIFO 从 wr_data_chl_req_valid 入队；Buffer aggregate 由 buf_all_idx_matched & mse_enable 入队。v94 未返回 actual compiled WR_Memory_AG 与 Memory_AG_Idx_Queue bytes，本地副本不能被自动提升为 server actual-source 证据。

DYNAMIC_EXECUTION_EVIDENCE：观察到 5 组 prepared-data 写入但只有 3 组 metadata；最终两组无法 drain。`VALIDATED_ROOT_CAUSE` 尚未成立，状态为 `OPEN_UNVALIDATED_MECHANISM`。依照用户最新裁决，本轮不提供 CONFIG_WORKAROUND。

## RULE_GAP_AUDIT

`RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION`：v94 的 inter-heartbeat host poll 会错误重置 plateau 计数；finalizer 用 leaf/signal_id 对 full hierarchy 造成假缺失；缺失 warning-free stop 表示、独立 console return 和 producer direct drivers。v95 已在 package-only 表面落实这些增量。没有连续两次 pre-target package failure，PACKAGE_BUILD_FAILURE_RULE_AUDIT 未触发。

## v95 目的与状态

v95 保留全部 73 个 predecessor signals，新增 27 个 metadata/Buffer last/config-consumer/direct-driver nets，合计 100 个唯一 hierarchy、41 roles、4 boundaries、10 candidates/40 rows；三个 HIGH 候选均有零跳 driver。它将 actual config consumer、Memory_AG queue、WR_Memory transaction/transfer lifetime 与 Buffer last-state 串起来，用于闭合 metadata-ended-early 与 data-overrun 二选一。

runtime-v3 仅把真实 source-heartbeat、30 秒固定 timestamp freeze 样本和 terminal 样本交给共享 evaluator；raw host samples 保留。空控制文件不再停机，只有精确 `CAUSAL_PLATEAU` 令牌触发 dumpoff/flush。

状态：`PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE / STORAGE_WAIT_MAINLINE_SERIAL_RELEASE`。exact-ZIP、full HDL、source-bound、adaptive breadth、post-sim、runner/compile-core、runtime-v3 replay、false-freeze 负控、first-fresh、release-admission、deterministic ZIP 与 focused regression 均通过。没有调用 storage manager，没有发布/轮换 pending，没有 upload/lease/connect/run/server action。

未来唯一命令仅在另行授权并完成 storage publication 后使用：

`bash r5_n4_hw_v95b_tbvcd_metapair/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

本地门禁不证明 v95 production compile/sim、唯一根因、自然终止或 formal-D/E3/E4/E5。
