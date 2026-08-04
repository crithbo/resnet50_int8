# Conv C0 主线裁决与 fresh composite C1 授权

日期：2026-07-28  
主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 用户授权与边界

用户要求先详细审计活动本地 RTL 与全部精确入口；若 RTL 确有错误且不存在现成精确
入口，则采用纯配置绕行，首个 Conv 固定为 node0004，必须从活动规则、typed request
和正式 W3/model 全新生成。node0004 全部历史 JSON、mapping、bitstream、execplan/SCA、
package、simulator output、local E2 与测试收据均不可信，只作负面历史。

本裁决继续冻结功能 RTL 修改；不检查服务器现有文件、名称或 RTL identity，不上传、不
运行、不授予 server lease。本地最多在完整 node0004 local E2 通过后生成
`PACKAGE_READY_NOT_RUN` 测试包。

## 已验收证据

### C0 主审

- 记录：
  `.agents/task_records/20260728_conv_sa_c0_local_rtl_and_alternative_entry_audit.md`
- SHA256：
  `cf32aca09f09614dab7378bef4edd66da6684d2614f1f330e22932eaf73b5b5e`
- 机器合同：
  `contracts/operator_config/conv_sa_c0_local_rtl_audit_v1.json`
- SHA256：
  `f52f4f65e5582c25980fdb99bc4501c82715a2f00310f2640feb0db8729810c1`

### C0 独立复核与勘误

- 记录：
  `.agents/task_records/20260728_c0_independent_rtl_audit.md`
- SHA256：
  `184b182ff1dda5308803f2775109a4d5f1f76b223b80880eda11e9255a4825c7`
- 机器报告：
  `outputs/c0_independent_rtl_audit_20260728/report.json`
- SHA256：
  `56457db2df7db71078bd0e8e34c805e3a6c118b8605c305a9b0e2f615f3d5b9a`

两份报告独立绑定活动 `NDP_copy01` filelist、encoder/control、SA/GA 直接消费者和 focused
Icarus TB。主线已完整复读报告，不依赖回传摘要作裁决。

## C0 最终裁决

```text
C0_RTL_AND_ENTRY_AUDIT = COMPLETE_DUAL_REPORTS_ACCEPTED
RTL_DEFECT_CONFIRMED = true
NO_EXACT_ALTERNATIVE_ENTRY = true
SERIALIZED_CONFIG_FALLBACK_IS_ONLY_AVAILABLE_EXACT_ROUTE = false
NORMAL_EXACT_ENTRY = false
SA_SERIALIZED_PSUM = false
SA_PRODUCT_PLUS_GA_TREE = proposal-only
```

活动 INT8 SA 有三项独立缺陷：

1. `i_Mode=0` 使 `o_AddNZero=0`，随后 `pipe_FractC/last_C=0`，任意
   `DataC/psum32` 被丢弃；
2. `CSA_4to2` 已左移 carry，`SA_PE_Mul_Array` 再左移一次；
3. 四个合法 `s8×u8` 总范围需要 signed18，stock 第一层只有 signed17 且 `cout`
   断开。

真实 `SA_ALU` TB 已证明 four-ones、four-ones+DataC、K=5 第二 occurrence、正负 wrap、
nonzero-xzp correction 等失败；只有“每 occurrence 单非零 product lane 且 DataC=0”
能精确产生一个产品。因此历史 serialized-SA-psum 结论被正式撤回。

GA opcode14 `int32_mac(A,1,C)` 的组件 TB 对正负、mixed-sign、大乘积与模
`2^32` wrap 逐 bit 通过。node0071 GAP sum-stage local E2 又证明 stage2+ INT32
scratch reload、显式多级 GA tree 与 same-mask barrier 可由 stock RTL/config
物化。这些证据只证明 primitive，不构成现成 Conv typed entry。

## 主线路径选择

```text
PATH_FRESH_COMPOSITE_CONFIG_C1 = AUTHORIZED
NEW_CONV_BYPASS_GENERATION_ALLOWED = COMPOSITE_C1_ONLY
SA_INTERNAL_SERIALIZED_PSUM_GENERATION_ALLOWED = false
NORMAL_STOCK_SA_GENERATION_ALLOWED = false
FUNCTIONAL_RTL_MODIFICATION_ALLOWED = false
```

授权 Conv/SA 会话从允许来源全新设计 node0004：

```text
SA single product (DataC=0)
→ formal INT32 product scratch
→ GA int32_mac(A,1,C) pairwise tree
→ explicit bias / -x_zp*sum(weight) additive leaf
→ fresh node0004 exact UINT8 tail
→ complete UINT8 logical output
```

所有加法为模 `2^32`，奇数层显式补零。host 不得预计算内部 product、partial sum、
accumulate、scaled、rounded、saturated 或 final tensor；bias/xzp correction 只能作为
由正式常量与 qparam 派生、具有明确 owner 的硬件 additive leaf。

## C1 生成前与封包前停止门

配置/物化阶段必须关闭：

- `B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP`：
  `(n,oc,oh,ow,k)→byte`、bank/column、terminal、valid-byte coverage；
- `B_CONV_GA_EXACT_ALTERNATIVE_TYPED_TOPOLOGY`：
  A/C dual-stream、tag/last/last_index、normal FIFO、typed/manual materializer；
- product scratch write drain→GA reload 的 barrier、visibility、accepted lifetime；
- node0004 64-term tree、bias leaf、padding、final INT32 endpoint；
- fresh qparam/physical layout/per-channel tail transport、rounding、saturation；
- final JSON→mapping→bitstream→execplan/SCA→address/lifetime→config-bound inverse；
- 3,211,264-byte完整 UINT8 logical output 对正式 W3 逐 bit一致。

在上述 local E2 完整通过前：

```text
candidate_release = false
server_package_allowed = false
PACKAGE_RELEASE = NONE
```

完整 local E2 通过后才允许按服务器测试包规则和本地活动 package README 生成全新
`PACKAGE_READY_NOT_RUN`。封包前必须重新完整读取生成前索引、公共算子规则、NDP 字段、
INT8 SA、exact UINT8 tail、Requant 与服务器测试包规则，并保存 current SHA 收据。

## 已准备的并行依赖

- node0004 fresh exact-tail 依赖：
  `.agents/task_records/20260728_node0004_exact_uint8_tail_fresh_c1_dependency.md`；
  正式 W3 3,211,264 元素软件公式 0 mismatch，但 signed ingress、typed qparam
  transport 与物理 endpoint 尚未闭合。
- Conv53 Requant binding：
  `.agents/task_records/20260728_requant_node0004_conv53_exact_tail_binding.md`；
  node0004 为 trusted-source-only，其余 52 项只复用既有分类，没有重测。

## BLOCKER_DELTA

```text
ADD  B_SA_INT8_DATAC_PSUM_GATED_ZERO
ADD  B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP
ADD  B_CONV_GA_EXACT_ALTERNATIVE_TYPED_TOPOLOGY
KEEP B_SA_INT8_DUPLICATE_CARRY_SHIFT
KEEP B_SA_INT8_REDUCTION_WIDTH
KEEP B_CONV_INT8_SA
KEEP B_CONV_BIAS_PSUM
KEEP B_SA_SERIALIZED_FALLBACK_MATERIALIZATION
KEEP B_QUANT_TAIL_SIGNED_INT32_INGRESS
KEEP B_QUANT_TAIL_TYPED_BINDING
KEEP B_EXECPLAN_TYPED_TRANSPORT
CLOSE B_NODE0004_C0_DEPENDENCY
```

关闭 `B_NODE0004_C0_DEPENDENCY` 只表示 C0 审计已完成；不关闭 accumulate、tail、
layout、typed transport 或 package gate。

## 声明边界

本轮只完成控制面裁决、规则更新与 C1 授权。没有生成新的 node0004 配置或服务器包，
没有提升 E2/E4/E5/三方计数，也没有恢复任何旧 node0004 资产。
