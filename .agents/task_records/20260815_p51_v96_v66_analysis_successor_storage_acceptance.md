# p51 / v96 / QAdd v66 正式回传分析与后继包主线验收

日期：2026-08-15  
主线：`019ff027-e7db-72a3-b282-cfad8708da05`  
registry epoch：`6`

## 正式回传裁决

- serialized v96：production compile 在 package-local probe 的 53 个重复
  `u_Memory_AG_Idx_Queue` XMR 上失败，simulation 未启动。该错误为
  `PACKAGE_LOCAL_TB_PROBE_HIERARCHY_DUPLICATION`；v95 已验证的
  `MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION`
  边界保持不变，三输入 tuple 叶仍待动态裁决。
- native p51：compile/target/VCD 均有效；再次精确证明 metadata 为
  `18*16=288` units、prepared 为 `20*16=320` units，缺一笔 32-unit
  transaction。exact leaf 仍开放于三路 input、same/gotten、split-FIFO 与
  keep-release。p51 还暴露 planned `$dumpoff` 后 VCD timestamp 静止被误判
  freeze、以及 STOP 重复打印 678453 次的共享实现逃逸。
- QAdd v66：exact 4/2 lineage materialize/compile 成功，pretarget matrix preload
  持续推进，但在 target entry 前命中 wall ceiling；因此本轮没有动态验证或
  反证 4/2 修复。旧 32/16 stale-lineage 根因仍成立。

## 规则与运行时裁决

- planned-dumpoff/freeze/STOP 实现逃逸已在既有规则 ID 下激活 semantic-v5：
  `tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3`。
- planned dumpoff 后 VCD timestamp 静止属于预期；使用 owner clock 与 TB
  execution time 完成 grace，并在 freeze 前裁决 dumpoff+grace plateau。
- STOP 必须 one-shot；重复、状态清除或 identity drift 均 fail closed。
- 其余族内 XMR、validator root 参数及发布收据聚合问题均由现有门正确阻断，
  disposition 为 `RULE_CONFIRMATION_NO_CHANGE` 或 package implementation fix，
  没有制造同义公共规则。

## 当前正式 pending

1. native `r5_n4_0cc_p52_memtupleleaf`
   - ZIP：`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p52_memtupleleaf.zip`
   - bytes：`6013257`
   - SHA-256：`fcb8a7b61fcd02be90ddf53b637b00259f208239a8c392cc38a2685da765d22f`
   - purpose：保留 p51 的 106 信号并加入 40 个 tuple/same-gotten/split-FIFO/
     keep-release 直接叶；146 signals、14 candidates、56 matrix rows。
2. serialized `r5_n4_hw_v97b_tbvcd_memtuple_xmrefix`
   - ZIP：`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v97b_tbvcd_memtuple_xmrefix.zip`
   - bytes：`5332235`
   - SHA-256：`bcd94e23123e95742a555897e05eace58a36002219ca110ff3f15ea92e297ad9`
   - purpose：一对一修正 v96 的 53 个重复 XMR identity，保留完整 153-signal
     tuple discriminator 并消费 semantic-v5。
3. QAdd `r5_qadd_n7_tailround_lanephase_v67_cfg42_tg`
   - ZIP：`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_lanephase_v67_cfg42_tg.zip`
   - bytes：`108687211`
   - SHA-256：`dbd18a58144321cdb252a9edf17b3fdc7d4087a00d6458d49bdb5d1a75443740`
   - purpose：保留 validated 4/2 lineage，并以 sparse pretarget safety snapshots
     控制加载阶段增长，在 target 前切换为连续无截断 causal capture。

GAP v70 根因已闭合并归 tested；GAP pending 为空，等待显式 RTL 修复或已证明
等价的配置授权。

## 存储与边界

三次受控单写者事务后，corrected global audit 为
pending/tested/superseded=`3/49/24`，一族至多一个 pending，物理树与索引一致。
没有 upload、lease、connect、server run，也没有 functional RTL/config/numeric/
workload/golden 修改。三个 pending 仅为 `PACKAGE_READY_NOT_RUN`；production
execution、natural terminal、formal-D、E3/E4/E5 仍待用户单独运行授权。
