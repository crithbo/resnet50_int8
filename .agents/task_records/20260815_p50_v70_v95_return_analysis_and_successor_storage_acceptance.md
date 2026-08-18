# p50 / v70 / v95 正式 return 分析与 successor 存储验收

日期：2026-08-15  
主线角色：`mainline.control`  
registry epoch：`6`

## 正式裁决

- GAP v70 已闭合唯一机制级根因：sum_s2 首个 `0..15` placement 写入空 Buffer0 后，第二个
  `1..16` placement 与尚未清除的 bank0..3 重叠并新增 bank4；部分 bank ready 下降使原子
  MRM write-ready 下降，而 ARM 仍等待八个 bank 全部就绪后才读/清，形成互锁。地址/数据 FIFO
  偏斜、normal barrier、ping-pong 与下游 GA/MSE4 已排除为首因。当前等待用户授权 RTL 修复或
  已验证等价配置方案；不再构建诊断 successor。
- Native p50 已证明 metadata 在 prepared-data/output join 处提前耗尽：metadata
  request/write/read/output=`18`，prepared write/read=`20/18`，RD enqueue/dequeue=`23/21`。
  held-full 写请求被误计为进展，导致合法 plateau 被屏蔽并最终命中 3600 秒 wall ceiling。
  根因叶仍在“上游 metadata 少产”与“Buffer tag 多产”之间，fresh p51 只扩展两套索引队列与
  metadata transfer 直接叶子并修正 qualified-progress。
- Serialized v95 已证明 Memory_AG metadata transaction 供应少一个 32-unit transaction：
  `9x32=288`，而 prepared-data `20x16=320` 与期望总量完全一致，因此 data overrun 被排除。
  缺失叶位于三路 tuple 输入及 same/gotten/split-FIFO/keep-release；fresh v96 保留全部 100 个
  predecessor 信号并新增 53 个直接叶子。

## Rule audit

- GAP 提出 qualified-progress hard-gate delta：持续 held level 及 XOR-fold counter 不能刷新
  plateau。该反馈待 shared-method 审计；不影响根因裁决。
- Native 为 `RULE_CONFIRMATION_NO_CHANGE`：共享语义已要求 qualified accept，p50 为包实现逃逸。
- Serialized 为 package implementation + coverage gap；不需要新增同义公共规则，v96 已消费缺口。

## 存储生命周期

- GAP v70 已退休到 tested，GAP 当前无 pending。
- Native p50 已退休到 tested，p51 为 native 唯一 pending。
- Serialized v95 已退休到 tested，v96 为 serialized 唯一 pending。
- QAdd v66 保持唯一 pending，采用已验证 `4/2` 配置 lineage。
- corrected global audit：`pending/tested/superseded=3/46/24`，索引
  `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
  bytes=`369310`，SHA256=`ea4121e2d8e7d2e3e98eaca4dd7482efdb81f03775bfa9372917147f520ee795`。

## 当前可运行包（仍需用户另行授权服务器动作）

- Native：`r5_n4_0cc_p51_metaidxcone`，bytes=`5947691`，
  SHA256=`858a4672a01958726b8eba6a65cbbd1c72be4a33343d4fc9d44cb874d453031f`。
- Serialized：`r5_n4_hw_v96b_tbvcd_memtuple`，bytes=`5238554`，
  SHA256=`b7b7f94e72305f360cff7ecfbe0837df1d65e1f8e9ecab95576ebce652565d06`。
- QAdd：`r5_qadd_n7_tailround_lanephase_v66_cfg42`，bytes=`108658281`，
  SHA256=`f9add4a1f54d922fb76fbe7d7b8a72e4965fea0c27546864fb3032bcad8862bc`。

无 upload、lease、connect 或 server run；无 functional RTL/config/numeric/workload/golden 改动。
