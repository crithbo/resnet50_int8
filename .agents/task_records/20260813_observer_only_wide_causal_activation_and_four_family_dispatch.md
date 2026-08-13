# Observer-only 宽因果门激活与四族构包派发

日期：2026-08-13  
owner：`mainline.control` / `019ff027-e7db-72a3-b282-cfad8708da05` / owner epoch 2  
activation epoch：`observer-only-wide-causal-v1`

## 上一版本进展

此前 mandatory VPD/FSDB/direct-VCD 路径分别暴露本机无 decoder、production UCLI 在 0 ps
停止、FSDB 体积/写入静止与高 CPU plateau 等问题。serialized FSDB smoke s2 虽已证明
production compile、time advance 和 FSDB writer 启动，但在 2.446091 ms 后至少 42 分钟没有新的
sim-time/log 事件；中断归档还捕获了 writer 未静止和 identity 漂移。serialized v88b 同时用 actual
compiled source 证明旧 ACK 结论属于 observer/source-identity 语义误报。

## 本版本目的与用户裁决

用户选择 next-fresh 统一采用 source-bound observer-only 宽因果证据，尽力在一轮内定位；取消
VPD、FSDB、VCD、FST 及所有 dump/query 分支。observer evidence aggregate 的十进制
`100000000` bytes 只是软偏好，超限只告警并完整回传，不得成为 hard cap、截断、采样或按大小
删除的依据。此次授权仅包括共享规则/门更新和四族本地 fresh 构包，不包括 upload、lease、服务器
运行或 functional RTL/config/numeric/workload 修改。

## 激活内容

- actual compile/sim profile 固定 `DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0`；exact final ZIP、
  runner、allowlist 或 runtime 出现 waveform member/control/PLI writer 时 fail closed。
- source-bound catalog 覆盖 26 类原子因果角色，并以 candidate × FIRST_DIVERGENCE 上游/当前/
  下游/状态持有清除矩阵证明开放候选两两可区分。
- 只记录 actual DUT net；observer 重算 expected equation 不得替代真实 net，也不得单独支持 RTL
  defect。catalog 绑定 hierarchy/source span/width/owner clock/reset/actual source identity。
- 本机直接读取 signal-id catalog 与 immutable JSONL/TSV chunks；保留全部有序 0/1/X/Z
  transition、exact time/sequence/timescale/width、end state、sim-time heartbeat 和 partial-exit live
  evidence。catalog/plan/chunks/index/parser/matrix/decision 全部进入 formal return exact set。
- 保留 Linux child-subreaper、fresh PGID、内部 timeout、TERM→wait→KILL/reap、repeat-safe exact-owned
  reset、fresh execution identity 与 atomic unique return；归档前改为 close/flush observer chunks，不再
  等待 waveform writer。
- build-gate registry 的 current next-fresh gate 为 `observer_only_wide_causal_final_zip`；旧
  `waveform_observation_final_zip`、`waveform_portable_local_decodability` 与
  `fsdb_process_tree_writer_quiescence` 已退出 current blocking registry，只保留历史 return 兼容证据。

共享 exact-set 由 `contracts/server_observer_only_wide_causal_dispatch_v1.json` 绑定 validator、runtime
supervisor、两份 schema、fixtures 和两套 tests。公共 server rule 只加强既有
`CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001` 与
`CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001`，未增加同义规则 ID。

## 验证与派发

共享聚焦回归 37/37 PASS。canonical 相关回归 186/186 PASS，另有 1 个环境性 skip；active-rule
audit 为 14/14、重复定义为 0。JSON/schema、Python compile 与 exact asset receipt 均通过。

已向 GAP、serialized Conv、native Conv、QAdd 四个 current owner 派发本地 fresh 构包。旧 v59、
s4、p44、v60 在对应 fresh publication 前保持 byte-equal pending；发布成功时由各 family storage
manager 原子移入 superseded。四族须完成 lexical/full-HDL、source-bound、observer-only、runner、
post-sim、partial-exit、first-fresh、final-ZIP 与 storage 门后主动回传 `PACKAGE_READY_NOT_RUN`。

## Claim boundary

本记录只证明共享规则/工具激活、canonical 回归和 build-only 派发。没有生成 family package、没有
服务器动作、没有 production VCS/DUT 结果，也不提升 natural terminal、formal D、E3、E4 或 E5。
主线派发后不持续轮询；只在 family 主动回传、用户提交正式 return 或用户询问时继续处理。
