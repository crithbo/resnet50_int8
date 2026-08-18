# Serialized Conv node0004 v95b return / v96b local-gates-complete

## 上一版本进度与本版本目的

v94b 已把停滞收窄到 prepared-data 与 WR metadata lifetime 不匹配；v95b 保留 73 个 v94 信号并增加 27 个 metadata/data zero-hop driver，目的是在同一次运行中区分“WR_Memory_AG metadata 提前结束”和“Buffer_AG/RD_Buffer 多产生 prepared data”。

v95b exact formal return 完整可读，source package、package manifest、execution/attempt、actual argv/source、VCD member CRC/bytes/full-file SHA 和 final archive timestamp 全部同一身份。production compile=0、simulation_started=true、target_entry=true。运行不是自然结束：共享 runtime-v3 的唯一退出裁决为 `WALL_CEILING`，sim exit=124、signal=NONE；进程树已 TERM/wait/reap，VCD exact set 已稳定归档，但没有 package TB dumpoff/dumpflush marker，因此 return 为 `PARTIAL_EXECUTION_RETURN / DIAGNOSTIC_EVIDENCE_INCOMPLETE`，不能证明 natural terminal、formal-D、E3、E4 或 E5。

## 严格流式分析

712 MB return 未整体载入上下文。`waveforms/causal_cone.vcd` 以 bounded streaming/resume 读到 EOF；100/100 catalog 命中，91,173,218 行，末 timestamp=28,491,039,375 ps，最后有效非 clock 变化=2,446,436,875 ps。持续更新了 `analysis_state.json`、append-only `checkpoints.jsonl`、incremental `report.md`，并只从 1,588 行 causal derivative 做 owner-clock phase 重建。

## DIRECT_CONFIG_EVIDENCE

same-attempt runtime consumer 值为：`mse_mem_idx_mode=100110`（input0/1/2=`KEEP/BUFFER/KEEP`），`mse_mem_idx_keep_last_index=000000110001`（0/3/1），`mse_buf_idx_keep_last_index=01010101`（5/5），transaction total size=32，prepared spatial size=16。配置与实际 consumer 的直接含义是：一个 Memory_AG tuple 授权一个 32-unit transaction，并拆成两个 16-unit descriptor；一个 prepared accept 贡献一个 16-unit group。

## DIRECT_ACTUAL_RTL_EVIDENCE

return 带回 actual compiled `Memory_AG_Idx_Queue.sv`、`WR_Memory_AG.sv`、`WR_Data_Channel.sv`、`Buffer_AG_Idx_Queue.sv`、top connection 及 define/filelist identity。actual `Memory_AG_Idx_Queue` 在 39-63 行提取三个输入的 valid/last/same/last-index，76-135 行实现 same/gotten mask，143-183 行实现每输入 split FIFO，195-217 行形成 all-match/keep-release，233 行仅在 `mem_all_idx_matched & mse_enable` 时入 metadata tuple queue。actual `WR_Data_Channel` 153-166 行保存 metadata request，287-310 行按 `+spatial_size/-metadata transfer size` 更新 prepared occupancy。

本地 NDP_copy01 的若干对应源文件与 return 中 actual compiled bytes 不同；本裁决只使用 return 带回的 actual bytes，不把本地源自动提升为生产源码证据。

## DYNAMIC_EXECUTION_EVIDENCE

完整 owner-clock 重建得到：Memory_AG tuple enqueue=9，metadata transaction finish=9；prepared group accept=20，prepared drain=18。按 actual config 计算，metadata 侧 `9*32=288` units，prepared 侧 `20*16=320` units，差值恰为 32 units；Memory_AG queue 从未 full，末态 empty；prepared_count 末态 32，memory wdata ready=11。

`LAST_PROVEN_GOOD=2,446,426,875 ps`：第 9 个 transaction 的第 18 个 descriptor 仍与 prepared capacity 配对。`FIRST_DIVERGENCE=2,446,428,125 ps`：第 19 个 prepared group 被接受，同时第 18 个/最后一个 metadata descriptor drain，之后没有 metadata capacity。`2,446,431,875 ps` 接受第 20 个 prepared group 后，prepared_count 锁定为 32。

## 根因裁决

`VALIDATED_ROOT_CAUSE=MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION`，这是已经由 actual config、actual compiled logic 和 dynamic execution 三层共同闭合的精确握手边界。`buffer_data_generation_lifetime_overruns` 被反证：20 个 16-unit prepared groups 正好等于 formal-D 预期的 320 units，并没有多生成。

叶子机制仍是 `OPEN_UNVALIDATED_MECHANISM`：v95 只观察 aggregate all-match/enqueue/empty，没有返回三个输入各自 raw valid/last/same/index、gotten/mask、split FIFO valid/full/empty 和 keep/backpressure release。因此尚不能唯一裁决 input0 KEEP、input1 BUFFER、input2 KEEP、same/gotten suppression 或 split-FIFO/keep-release 中哪个阻止第 10 个 tuple。`CONFIG_WORKAROUND` 继续 withheld；在叶子 direct chain 验证前不推荐生产绕行。

## RULE_GAP_AUDIT 与 v96b

因 production target 实际执行且 metapair 边界已闭合、但叶子未唯一，触发 `RULE_GAP_AUDIT`。结论为 `RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION`，不需要修改共享规则：v95 的 package candidate matrix 缺少 Memory_AG 三输入 formation leaves。

fresh v96b 保留全部 100 个 v95 信号和 adaptive-v4/runtime-v3 语义，新增 53 个 actual-source-bound HIGH leaves，总计 153 signals、41 roles、4 boundaries、15 candidates/60 matrix rows；输入 0/1/2 各有独立 raw/masked/gotten/split-FIFO/keep-release 集合。信号数高于同族第三轮 soft reference，但这是为完成三个输入 pairwise distinction 的明确偏离，未删除任何 LOW evidence。

exact-final-ZIP 的 TB-VCD contract、mode selector、HDL lexical/full frontend、passive/source-bound、runtime preflight、normalizer arity、runner/compile-core、post-sim、runtime-v3 replay、active-rule、package release admission、first-fresh negative controls、deterministic ZIP 和 113/113 focused regression 全部通过。负控覆盖：缺任一 Memory_AG input leaf、candidate exact-set collision、actual-source hash drift、删任一 v95 信号、aggregate-only fallback。

状态：`PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE / STORAGE_WAIT_MAINLINE_SERIAL_RELEASE`。没有调用 storage manager，没有 rotation/publication，没有 upload/lease/connect/run/server action。唯一未来命令仅在另行授权并完成 storage publication 后成立：

`bash r5_n4_hw_v96b_tbvcd_memtuple/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

本地门禁不证明 v96 production compile/sim、叶子根因、自然终止或 formal-D/E3/E4/E5。

## Storage lifecycle completion

Mainline 发出 serialized-only storage release 后，corrected manager pre-audit 以 `pending/tested/superseded=3/45/24` 通过；serialized 唯一 pending 为 v95b。随后只使用 `tools/manage_server_test_package_storage.py rotate` 完成单次受控事务：v95b 与原有 12 个 receipt 一并移入 `tested/conv_serialized_node0004/r5_n4_hw_v95b_tbvcd_metapair/`，其 index evidence 绑定上述 exact formal `return_analysis.json`；v96b exact ZIP 发布到 flat `pending/`，其 28 个 sidecar/gate/analysis/task receipt 发布到 family receipt tree。

corrected post-audit 以 `3/46/24` 通过，serialized sole pending 为 v96b。非 serialized 的 61 个 package、724 个受管文件在事务前后的规范语义摘要完全相同；native p51 和 QAdd v66 未改变，`conflicts=[]`。最终状态：`STORAGE_LIFECYCLE_COMPLETE / GLOBAL_STORAGE_AUDIT_CLEAN`。所有 storage 写入已停止；没有 upload、lease、connect 或 server run。

Machine receipt：`outputs/conv_node0004_v96b_tbvcd_memtuple_release1/storage_release/storage_lifecycle_complete.json`。
