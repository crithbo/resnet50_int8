# 三份 TB-VCD return 退出审计与 fresh successor 验收

日期：2026-08-14

## 输入与裁决

- native p48 与 GAP v63 均为 QAdd v63 同类的 package-local false freeze：归档 VCD 时间戳仍推进，但旧 supervisor 信任稀疏/陈旧 display heartbeat，在目标进入前退出。两者均未产生新的 DUT 根因收窄。
- serialized v93d 不是 false freeze。目标已执行，actual ACK 方程 6,151,454/6,151,454 次检查零矛盾；外层 runner 在 shared evaluator 尚未满足完整 plateau 条件时提前给出 `CAUSAL_PLATEAU`，且退出后仍有未 reap 的 owned PID。
- v93d 的有效 VCD 将边界从 v92 的 `RD_Buffer_AG/backpressure` 收窄到 `WR_Data_Channel prepared_data_count=32 -> prepared backpressure/wr_data_chl_ready deassert -> RD_Buffer_AG dequeue stop`。尚需区分 prepared write/read accounting、metadata queue、output-buffer selection/backpressure 与 memory-ready drain。
- natural terminal、formal-D、E3/E4/E5 均未证明。

## 共享退出门

现有公共规则 ID 保持不变，激活 epoch `tb-vcd-exit-mechanism-consistency-v3`：

- shared runtime evaluator receipt 是唯一退出权威；
- exact packaged helper 必须通过 advancing、suspected-only、full-plateau+grace、true-freeze 四态回放；
- final runtime timestamp 必须绑定 quiescent archived VCD 的 full-file SHA/bytes/last timestamp；
- incomplete、unflushed、unclosed 或 unreaped runtime 不得 finalization PASS。

该修正没有 DUT 仿真额外开销；last-timestamp 提取与既有 SHA 扫描融合。

## 当前四族唯一 pending

- serialized Conv：`r5_n4_hw_v94b_tbvcd_wrdrain`
- native Conv：`r5_n4_0cc_p49_tbvcdrt2`
- GAP：`r5_n71_gap_v69_sum_s2_tbvcd_runtimev3clean`
- QAdd：`r5_qadd_n7_tailround_lanephase_v64_tbvcdfix`

四包均为 `PACKAGE_READY_NOT_RUN`，没有 upload、lease、connection 或 server run。package storage audit 通过，pending/tested/superseded=`4/39/23`。

GAP 另提出 package-local Python exact-set compile 与 schema-enabled validator dependency 的共享审计。
裁决为现有 final-ZIP/first-fresh 规则的实现覆盖逃逸，不新增公共 rule ID；canonical epoch
`package-python-schema-runtime-v2-5f7e882949ad`已激活为required-next-fresh，且不追溯HOLD或重建当前四包。
