# Execplan barrier live drain 语义规则发布

日期：2026-08-05

主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 裁决

正式发布：

`CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001`

位置：`.agents/rules/算子配置规则.md` 的 mapping/bitstream/execplan 章节。

发布后规则文件：

- bytes：`19876`
- SHA256：
  `8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497`

生成前必读索引已路由公共算子配置规则，因此无需新增同义索引入口。

## 证据

来源 task record：

`.agents/task_records/20260804_node0075_e1fb0f7_producer_visibility_barrier_field_leaf.md`

SHA256：

`83cdfdecf9640b9111da70a5db8abdd25718bcc46506b7f5a80a9f59f6d1beea`

current e1fb0f7 中 node0071 execplan 存在 opcode `3'b110`，但
`Slice_Execution_Manager.sv` 只有 `BARR_CMD_OP` 常量，没有 barrier valid decode、
FSM/state transition、drain/outstanding/visibility release。IDLE 可把该命令作为 no-op
消费；`Start_Comp` finish 又只证明写数据被入口接受，不能证明目标 memory visibility。

因此，命令存在或执行顺序不能关闭 node0071→node0075 producer visibility blocker。

## 规则边界

- barrier 必须由 current active RTL live decode 为控制状态转移；
- release 必须证明目标 visibility domain 内 writes accepted 且 queue/FIFO drained、
  outstanding=0，或形式等价的有序可见性；
- Start_Comp 串行、finish、last-data ingress、observer 或 host 顺序不得替代；
- 生成前本地 validator 对 no-decode、no-transition、no-drain/visibility 三类反例
  fail closed。

该门贯彻“本地尽量消除可发现错误”的原则，不要求把环境自检搬到服务器；它只阻止生成
一个在 current RTL 中无法表达正确 barrier 语义的服务器包。

本轮未修改 functional RTL，未生成 node0075 联合包，未上传、未运行服务器或取得 lease。
