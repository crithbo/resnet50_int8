# FSDB 进程树、仿真时间心跳与 writer 静止硬门（2026-08-13）

## 实际反例

serialized Conv smoke s2 已通过 production compile 并推进到 2.446091 ms，但随后出现至少 42 分钟
host 高 CPU、无后续 sim-time/log event。INT finalizer 发布 partial return 时，runtime 与 archive
中的 `wave.fsdb/.chain/.slist/.xlist` 身份漂移，并出现瞬态空 `wave.fsdb.slock`。因此
`RETURN_ZIP_PUBLISHED`、simv root exit 或外层 timeout 均不能证明整个 simulator/FSDB writer 已静止。

return SHA：`cb66cf7fbffc2c09679c98d9a4a8497918c51264345bc9cc1d7ecc8daa91010b`；
family analysis SHA：`89964a60c1c85ec6ab40bd39b26c7f7e1014124ff7fe2da49940c1fde7f181ae`。

## 实现

- 新规则：`CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001`。
- Linux supervisor 启用 `PR_SET_CHILD_SUBREAPER`，在 fresh session/process group 启动实际 simulator；
  内部 timeout/HUP/INT/TERM 执行 TERM → bounded wait → KILL，追踪并回收 root、PGID member、
  descendants 和 double-fork/setsid 后被收养的 escapee。
- 独立 heartbeat 增量读取 exact source-bound sim-time log，绑定连续序号、host monotonic time、
  sim-time 与 timescale；至少一次 same-attempt sim-time advance 才能通过，log 截断/倒退 fail closed。
- 进程树静止后才对 `wave.fsdb*` 做两次间隔快照；exact-set/path/bytes/SHA 必须一致，空文件、
  symlink 和 lock/tmp 成员均 fail closed。
- 失败仍发布 PARTIAL raw/core 证据并标记 `DIAGNOSTIC_EVIDENCE_INCOMPLETE`。

## 共享资产与验证

共享入口：`tools/server_fsdb_runtime_quiescence.py`；schema：
`schemas/server_fsdb_runtime_quiescence_v1.schema.json`；dispatch：
`contracts/server_fsdb_process_tree_quiescence_dispatch_v1.json`；机器报告：
`outputs/fsdb_process_tree_quiescence_gate_v1/report.json`。

聚焦两套新工具 28/28 PASS；共享相关回归 119/119 PASS，环境性 skip 1；py_compile、JSON parse、
diff-check PASS。current/tested package 未修改，未进行服务器动作。

## 激活与 claim boundary

`RULE_DELTA_PROPOSAL=CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001`，仅在主线 current-disk
语义合并后对 next-fresh FSDB package 生效。由于本任务禁止服务器动作，Linux production VCS 的
subreaper/process-tree/heartbeat/stable-snapshot 集成仍需第一个 next-fresh 实跑闭合。本门不裁决
plateau 的 family/DUT/RTL/config 根因，也不提升 natural terminal、formal D 或 E3/E4/E5。
