# QLinearAdd node0007 FP32 scratch 行边界主线裁决

日期：2026-07-29

## 输入证据

- 机器合同：
  `contracts/operator_config/qlinearadd_node0007_full_e2_blocker_v1.json`
  SHA-256=`40f265de8cf750908e63a97634b3b906b2b92d832136311899b345c09b125e6d`。
- 分支 task record：
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-full-e2-v1/task_record.json`
  SHA-256=`683b6f3e9fe654cc519baf6d8a3c52ec4c87cce28775023429b2242c8b0325ab`。
- 原生构建 stderr：
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-full-e2-v1/native-build.stderr.log`
  SHA-256=`87ba87ed6993547f36405cffcec2effd680f5248de308afcc8401cfbbabd1811`。
- 裁决前 QLinearAdd 专项规则 SHA-256=
  `981afd5aa0a0ee240c8e6c863cbac0c89dc299344554eb893d707cf96fe0b4ee`。
- 裁决前 plan mutable provenance SHA-256=
  `2946e5080678e3f2f95fa9f834b3ed6f6888914cb4feb9ebef0bde1b563434df`。

## 主线裁决

接受 `CDA-QADD-LARGE-FP32-SCRATCH-ROW-BOUNDARY-001` 并发布到
`.agents/rules/QLinearAdd算子配置规则.md`。

node0007 本轮不是数值失败：

- 未重复 17/17 stage0 数值分析，只消费已冻结的 stage0 与共享 tail 资产；
- 65,536 个 A/B 标量 tail 域证明完成；
- 12,845,056 个逻辑输出、28 slice 共 16,859,136 个物理字节及 padding 的
  config-bound 比较均为 0 mismatch；
- 5/5 mapping/bitstream 均 penalty=0、fallback=false。

首个失败位于最终请求地址编码。stage2 `op_fp32_add` 的
`WRITE_STREAM0` scratch 从 `0x005be000` 延伸到 `0x0080a000`，在 slice0 首次产生
row=6144，而目标要求 `row<6144`。因此当前完整 QLinearAdd local E2 未闭合，
不得生成服务器包或声明 `CONFIG_ONLY_CORRECTNESS_BASELINE`。

## 下一授权

QLinearAdd owner 只允许：

1. 搬移完整 FP32 SUM scratch，或把 SUM stage/scratch 拆为独立 tile；
2. 保持六 qparam、W3 逐操作 FP32 顺序、已验 tail 算术和输入 replay 边界不变；
3. 对每个 slice/tile 重算 request 行列、non-alias、barrier、accepted lifetime、
   occurrence、完整 coverage 与 padding；
4. 从空 mapping state 重建 final JSON、mapping、bitstream、execplan/SCA，并做
   config-bound 比较与确定性重建。

禁止修改功能 RTL、host 预计算内部 tensor、截断或回卷越界 request。完整本地 E2
闭合后才可按当前服务器包规则生成新身份包，并停止于
`PACKAGE_READY_NOT_RUN`。

## 计数与发布边界

- 完整 QLinearAdd local E2：仍为 0。
- QLinearAdd 服务器包：0。
- `R5_QADD_NODE0007_FP32_SUM_ROW_LIMIT`：OPEN，已从未知问题收窄为可执行的
  relocation/split 物理物化任务。
- 本记录不计 E2/E4/E5，不修改 RTL。

发布后身份：

- `.agents/rules/QLinearAdd算子配置规则.md`
  SHA-256=`dd4a8122d771ed5f4dbb9995fd6463ba14b179a72a515d2af5e91d30f2c71269`；
- `.agents/plan.md`
  SHA-256=`f74f45eb990f9c8874c0a7cf1251ce931bd770d1fb1d76b32fe33629d55f782b`
  （mutable provenance）。
