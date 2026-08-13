# 增量波形保留与 FSDB 进程树静止门主线激活（2026-08-13）

## 上一版本进度

serialized Conv smoke s2 已证明 production compile、FSDB writer 启动及 2.446091 ms 的仿真时间推进；
随后出现至少 42 分钟 host 高 CPU、无新 sim-time/log 的平台。INT finalizer 在 simulator/writer 未证明
终止且 FSDB exact-set 仍变化时发布 PARTIAL return，并收进瞬态空 lock 成员。因此
`RETURN_ZIP_PUBLISHED` 或 simv root exit 不能代表进程树与波形 writer 已静止；pending s3 与 s2
运行面等价，继续保持禁止运行。

## 当前版本目的与激活

主线把 optimizer 隔离工作树的两个非同义共享增量窄幅同步到 current disk：

- `CDA-SERVER-RETURN-WAVEFORM-INCREMENTAL-REVIEW-RETENTION-001`：按 exact signal set × time window ×
  candidate 写不可变 chunk 和原子 current index；唯一根因后停止无关扫描；同 family/test-track 仅在
  terminal review、family/mainline 双消费、final adjudication 和确定性 core-only return 全闭合后，
  才可按 exact identity 淘汰非 CURRENT/BASELINE/CAUSAL 的第四份旧重型 raw return。
- `CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001`：next-fresh runner 使用 Linux child-subreaper、
  fresh session/process group、内部 timeout 与 TERM→wait→KILL/reap；以 exact sim-time heartbeat 证明
  same-attempt 时间推进，只在 owned process tree 全部静止后对 FSDB/shards 做两次稳定 exact-set 快照。
  失败保留 PARTIAL raw/core return 并标记 `DIAGNOSTIC_EVIDENCE_INCOMPLETE`。

activation epoch：`waveform-retention-fsdb-quiescence-v1-967ef4e72e6c`。
retention 门自本记录起用于 post-adjudication 本地生命周期；quiescence 门自本记录起为
`required_next_fresh`，不追溯改写 current/tested return 或 package。

## Current-disk 同步与验证

机械同步了两套 tool/schema/dispatch/fixture/test/report/task-record exact set，并逐项复核与来源工作树一致。
服务器规则、生成路由、整网优化规则、mandatory FSDB dispatch、build-gate registry 与 pipeline test
均采用窄幅语义合并，保留 current FSDB-only、registered query、lexical、partial-exit 和其它并行增量。

- 两套新门聚焦测试：28/28 PASS。
- current 相关共享回归：198/198 PASS，环境性 skip 1。
- 两个 helper py_compile PASS；JSON/schema 路径由聚焦/共享测试覆盖。
- active-rule audit：14/14 active/registered，163 个唯一规则定义，重复 0，errors/warnings 为空。
- scoped `git diff --check` PASS。

## 控制面与 claim boundary

GAP v59、native p44、QAdd v60 和 serialized smoke s3 的 package bytes/storage disposition 均未修改；
四者继续禁止服务器动作。主线只向 serialized owner 派发 fresh diagnostic smoke 构建：冻结 s2/s3
workload、probe、config、numeric、golden、functional RTL，只允许改 activated process-tree supervisor、
sim-time heartbeat、FSDB stable snapshot/quiescence、return/retention identity 及必要 runner 集成面。
family 完成本地 lexical/full-HDL/FSDB/first-fresh/final-ZIP/runtime/return/storage 门后回传
`PACKAGE_READY_NOT_RUN`；主线不持续轮询，也不 upload/run/lease。

本激活只闭合共享审查/存储生命周期与运行证据完整性方法，不裁决 plateau 的 DUT/RTL/config 根因，
不提升 natural terminal、formal D 或 E3/E4/E5。
