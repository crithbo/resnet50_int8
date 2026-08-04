# P1-A QLinearAdd 复合后端预设计

日期：2026-07-27  
状态：`PREDESIGN_COMPLETE_MATERIALIZATION_FORBIDDEN`  
覆盖：17/17 QLinearAdd；16 个同 shape residual add，1 个 node0076 broadcast bias add。

## RETURN_ANALYSIS

本轮完成了不产生目标配置的复合后端预设计，并将合同写入：

- `contracts/operator_config/qlinearadd_composite_backend_predesign_v1.json`
- `resnet50_pipeline/qlinearadd_predesign.py`
- `tools/validate_qlinearadd_predesign.py`
- `tests/test_qlinearadd_predesign.py`

17 实例由 typed contract 逐项重建，六 qparam、shape、A/B/Y tensor identity 的规范序列
SHA-256 为：

```text
d7c9f0266527d25a0b166df6788720fa38f24a31061c5cef2c92eb0dd7bc2cca
```

shape 分五类：

1. 3× `[16,256,56,56]`;
2. 4× `[16,512,28,28]`;
3. 6× `[16,1024,14,14]`;
4. 3× `[16,2048,7,7]`;
5. node0076：A/Y `[16,1000]`、B `[1000]` 的 trailing-axis broadcast。

### 可复用与不可复用边界

现有 `add_dequant_uint8CWH_uint8CWH_fp32CWH` 可复用：

- A/B 两条独立 UINT8 read stream；
- buffer0/buffer2→GA 双输入 matching；
- GA UINT8→FP32 ingress；
- normal outbuffer→buffer5→write MSE 的结构；
- LC/MSE/Buffer/GA 字段和拓扑 oracle。

它不能直接复用 affine 数值：

```text
W3:      float32(int32(x)-zp) * scale
template: float32(x)*scale + float32(-zp*scale)
```

二者发生不同的 float32 舍入。对全部 17 组 qparam、每组全部 65,536 个 A/B 标量组合做
穷举，最终 UINT8 出现三个反例：

- node0007：2 对；首对 `A=120,B=232`，W3=`246`，reassociated=`245`;
- node0070：1 对；`A=213,B=1`，W3=`151`，reassociated=`152`。

所以“现有 add-dequant 可复用前半段”必须解释为结构复用；数值实现必须保持 W3
subtract→float32 cast→multiply→add 的顺序，禁止代数重关联。

### 单 stage / 双 stage

- 单 stage fused：`UNDECIDABLE_UNTIL_P0_A`。只有 P0-A tail 的 GA/SFU placement、
  rounding、saturation、normal-outbuffer occurrence 能在同一 occurrence 中接到
  W3 add 后才可选；本轮不宣称可行。
- 双 stage：`STRUCTURALLY_FEASIBLE_NUMERIC_TAIL_PENDING_P0_A`。stage0 输出显式 FP32
  scratch，stage1 消费 P0-A exact tail；scratch 禁止 alias，大小为
  `4*product(Y.shape)`，从 stage0 首写活到 stage1 最后一次 accepted read，并要求
  DRAM visibility 和 completion barrier，禁止隐式跨 stage buffer reuse。

### A/B/Y allocation、address、lifetime

- A：producer-owned tensor region，read stream0→buffer0；活到最后一次 accepted A
  read。
- B residual：producer-owned tensor region，read stream1→buffer2；活到最后一次
  accepted B read。
- B node0076：1000-byte immutable initializer region；逻辑消费 16,000 bytes。每个
  batch 重放同一 1000-byte region，禁止物化 16×copy；最终 validator 必须枚举全部
  request occurrence 和地址序列。
- Y：fresh non-alias region，GA normal outport→buffer5→write stream0；完成最后 accepted
  write 后才对下游可见，活到最后一个 consumer 的最后 accepted read。
- 全部 base 只冻结 16-byte alignment 和 region/non-overlap 条件，不写具体地址。
  机器 lifetime 合同中 17 个 stage 和相关 53 条 inter-node edge 仍全部未绑定。

### LC/backpressure

A/B 共用逻辑 occurrence carrier，以 ready AND 保持 pair matching；Y write 使用独立授权
branch。物化前必须证明完整 ready 图无环、A/B 两路都能进展，并验证
read bytes=Buffer AG supply=GA accepted pair，以及
GA output=buffer5 supply=MSE writes。node0076 的 B replay 每个 A occurrence 必须恰有
一个配对值。

### handler / mapper 接口

原生 `OperatorSpec/json_loader` 只有 A/B/B′/C tensor 和全局整数 params，不能承载六个
typed qparam。建议新增 hash-bound typed parameter map：

```text
a_scale, a_zero_point, b_scale, b_zero_point, y_scale, y_zero_point
```

scale 传 exact FP32 bits+value SHA；zero-point 传 exact uint8+value SHA。QLinearAdd
handler 必须消费全部六项并拒绝 missing/extra/type mismatch。mapper 只放置已 typed 的
stage DAG，不得推断 qparam、沿用模板常数 1 或默认省略 output quant。

## DEPENDENCY_ON_QUANT_TAIL

依赖：`R5_GAP_EXACT_UINT8_QUANT_TAIL`。

可以与 P0-A 并行完成、且本轮已冻结：

- 17-instance/five-shape inventory；
- 六 qparam transport envelope；
- W3 float32 运算顺序；
- same-shape/broadcast logical DAG；
- A/B/Y symbolic allocation/address/lifetime；
- 双 stage scratch lifetime；
- A/B shared-LC 与 Y independent-branch 设计；
- native handler/mapper interface gap。

必须等待 P0-A 才能裁决：

- fused single-stage 或 explicit-scratch two-stage 的最终选择；
- output tail GA/SFU opcode、placement、division/reciprocal 顺序；
- nearest-even tie、任意 y_zero_point、UINT8 saturation；
- tail transaction width/occurrence；
- control-register handler 与 mapper 最终约束；
- config-bound simulator 对 tail 的解释。

node0076 的 `y_zero_point=60` 是必测 nonzero-output-zero-point holdout。

## BLOCKER_DELTA

建议新增：

1. `B_QADD_FLOAT32_OPERATION_ORDER`：add-dequant affine reassociation 已被 node0007、
   node0070 的最终 UINT8 反例推翻。
2. `B_QADD_NATIVE_TYPED_HANDLER`：native handler/OperatorSpec 缺六 qparam typed transport。
3. `B_QADD_BROADCAST_ADDRESS_LIFETIME`：node0076 的 1000-byte B replay、16-batch
   occurrence/address 与 nonzero y-zero-point 尚未物化闭合。

继续保持：

- `B_ADD_DUAL_QDOMAIN`
- `B_ADD_UINT8_REQUANT`
- `B_EXECPLAN_TYPED_TRANSPORT`
- `B_ADD_REQUANT_E5`
- `B_SERVER_E4_E5`
- `B_QADD_SPECIALTY_AND_MATERIALIZATION_CONTRACT`

本轮不建议关闭任何 blocker。

## RULE_DELTA_PROPOSAL

主线专项规则建议加入：

- W3 的逐操作 float32 顺序为唯一数值 owner，禁止 `x*scale + (-zp*scale)` 重关联；
- 六 qparam typed transport 的精确 bit/hash、顺序和 fail-closed handler 合同；
- residual/broadcast 两种 DAG；node0076 B region 重放而非展开；
- A/B paired readiness、shared-LC AND backpressure 无环和 Y 独立 branch；
- A/B/Y fresh/non-alias、accepted-handshake lifetime；双 stage 另增 FP32 scratch；
- P0-A tail 未批准时 fused/two-stage selection、output occurrence、mapper/control 更新全部
  保持 unresolved；
- 最终物化必须重新枚举 occurrence/bank/address/lifetime，并完成最终 JSON 合同回读。

## 验证

```text
python -m unittest tests.test_qlinearadd_predesign -v
2 tests passed

python tools/validate_qlinearadd_predesign.py \
  contracts/operator_config/qlinearadd_composite_backend_predesign_v1.json
valid=true
instances=17
lifetime_stages_checked=17
lifetime_edges_checked=53
```

本族测试与 typed-parameter 定向回归共 9 项通过。额外尝试运行既有
`tests.test_stage_state_lifetime_contract` 时，其 `setUpClass` 在重建公共 lowering
合同前因 `.agents/agent.md` generation receipt 与当前工作区不一致而失败；该失败发生在
本族断言之前，属于共享合同/并发工作区身份漂移，不用来放行或否决本预设计。当前
checked-in lifetime 合同仍由本族 validator 按已读 SHA 和 17 stage/53 edge fail-closed
验证。

本轮未修改 `.agents/plan.md`、`.agents/rules/**`、功能 RTL 或其他族资产；未生成目标
JSON、mapping、bitstream、execplan、SCA、服务器包；未检查或运行服务器。
