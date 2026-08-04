# 最小双 Stage 生命周期规则

状态：活动专项规则。公共生成门、证据等级和 RTL 边界只引用
`.agents/rules/生成前必读索引.md` 与 `.agents/agent.md`，本文只定义双 stage 增量语义。

## 1. 范围与样例

- 样例固定为一个 slice 上两个不同的原生普通 GA 算子：
  `prefill_mul_fp32MN_fp32M_fp32MN` 后接
  `prefill_add_fp32MN_fp32MN_fp32MN`。
- 两个 stage 的物理形状固定为 `[1,8,32]`、dtype 固定为 `fp32`；stage0 的
  B 为 `[1,1,32]`，stage1 的 B 为 `[1,8,32]`。
- 这是通用 transport/lifetime E2 probe，不是 ResNet50 正式 target config，
  不替代任何算子专项 E4/E5。

## 2. 强制不变量

### CDA-TWO-STAGE-MATERIALIZED-ROUNDTRIP-001

最终 addressed request、两份 materialized operator JSON、mapping、bitstream、
execplan 与 SCA/SCA_D 必须由同一次 typed request 完整重建，并在两份隔离、空
mapping cache 的工具副本中逐文件一致。不得只验证生成器输入或派生摘要。

### CDA-TWO-STAGE-DATA-ALIAS-001

stage0 的 `D` 与 stage1 的 `A` 必须：

1. 指向同一 producer tensor；
2. dtype、shape、byte count 完全一致；
3. 每个启用 slice 的物理 base address 完全相等；
4. stage1 不得把该 A 重新声明为 external preload。

地址相等只证明 storage alias；可见性还必须由本规则的 barrier 门共同证明。

### CDA-TWO-STAGE-CONFIG-RELOAD-001

两个 stage 都必须在各自 `Start_Comp` 前显式执行主 `Load_Config`。stage1 不得
依赖 stage0 遗留的 active config。两个主 config 必须具有不同地址和不同 payload
identity；配置快照必须在每个 `Start_Comp` 处独立冻结。

### CDA-TWO-STAGE-BARRIER-ORDER-001

每个 `Start_Comp(mask)` 后必须立即出现 `Barrier(mask)`，且在该 barrier 之前
不得发送下一 stage 的 `Load_Config`、`Write_Reg` 或 `Start_Comp`。stage0 barrier
是 stage0 D 对 stage1 A 的最小 write-visibility fence。

### CDA-TWO-STAGE-TERMINATION-001

`Start_Comp` 数、同 mask barrier 数、SCA `Repeat_Num`、runner 预期完成事件数均
必须为 2；完成顺序必须精确为 stage0、stage1。最后一个 barrier 是最终终止门，
缺失时 fail-closed。

### CDA-TWO-STAGE-DUAL-GOLDEN-001

必须同时保留并验证两份独立 golden：

- `D0 = fp32(A0 * B0)`；
- `D1 = fp32(D0 + B1)`。

只检查最终 D1 会掩盖错误的中间写回、地址别名或第二阶段输入来源，因此不能放行。
输入值应选可精确表示的有限 fp32，要求逐 bit 相等。

## 3. 本地 E2 与动态边界

本地 E2 只有在以下项目同时通过时才可称
`MINIMAL_TWO_STAGE_LIFECYCLE_LOCAL_E2_COMPLETE`：

- 原生 JSON→mapping→bitstream→execplan→SCA 双隔离重建一致；
- materialized JSON 反解通过；
- data alias、config reload、barrier、termination 四个门通过；
- 记录式本地数值执行器证明确实按 stage0 写 D0、stage1 从同址读 D0，并分别通过
  D0/D1 bit-exact golden。

即使本地 E2 完成，也必须保持 `candidate_release=false`、`formal_target_config=false`
和 `server_package=false`。RTL 时序可见性、真实完成事件和正式 readback 仍属于后续
E4/E5，且任何后续服务器包必须另行授权。
