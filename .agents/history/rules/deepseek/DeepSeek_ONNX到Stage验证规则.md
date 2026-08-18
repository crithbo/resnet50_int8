# DeepSeek ONNX → Stage → 算子 JSON 本地验证规则

最后更新：2026-07-25

本文件只保存 DeepSeek 专项的模型身份、crop、Stage IR 与可信 JSON 对照规则。公共生成门、
硬件字段公式和 E0～E5 定义仍由 `生成前必读索引.md` 路由。本专项当前只允许形成本地
E2 证据，不生成服务器包。

## 1. 身份分层

规则 ID：`CDA-DEEPSEEK-MODEL-IDENTITY-001`

必须分别记录且不得合并：

1. 原始模型身份：`deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` 的固定 revision；
2. ONNX 转换身份：固定 revision 的 GQA FP16 ONNX 图和外部 tensor 文件；
3. NDP 派生模型身份：`config.json`、crop producer、裁切轴、层选择与产物哈希；
4. 硬件实例身份：op occurrence、slice mask、layout、地址、materialized JSON 和码流。

ONNX Community 转换当前分类固定为 `SEMANTIC_MODEL_MATCH`。在没有逐字节来源链之前，
`original_source_identity=false`；不得写成 ndp-sim 权重提取的
`ORIGINAL_SOURCE_IDENTITY`。

## 2. 显式 crop 合同

规则 ID：`CDA-DEEPSEEK-CROP-EXPLICIT-001`

原模型与 NDP 实例不得按“相同 shape”处理。当前必须验证的派生关系是：

```text
hidden_size:          1536 → 896
intermediate_size:    8960 → 1792
query_heads:            12 → 7
kv_heads:                2 → 1
head_dim:              128 → 128
hidden_layers:           28 → layer 0 only
```

逐 tensor 必须记录源 shape、目标 shape、每轴 half-open slice、存储顺序和消费端：

- norm：`[1536] → [896]`，取 axis0 `[0:896]`；
- Q/O：`[1536,1536] → [896,896]`，两轴均从零裁切；
- K/V：`[1536,256] → [896,128]`，axis0 `[0:896]`、axis1 `[0:128]`；
- gate/up：`[1536,8960] → [896,1792]`；
- down：`[8960,1536] → [1792,896]`；
- Q bias：`[1536] → [896]`；K/V bias：`[256] → [128]`。

`weight_gen.py` 的维度裁切与 `decode_data_loader.py` 的 `layer_idx=0` 消费必须分别绑定；
前者没有自行删除其余层这一事实不得被 `num_hidden_layers=1` 掩盖。若源 tensor 命名、
轴序或 Fortran-order 解释无法唯一确定，立即停止。

## 3. ONNX 子图到 Stage DAG

规则 ID：`CDA-DEEPSEEK-ONNX-STAGE-DAG-001`

ONNX 图只作为模型算子、依赖、dtype/shape 与常量来源。lowering 必须显式输出：

- ONNX node/value 名称和稳定图内 ID；
- fused semantic operator；
- 一个或多个 hardware stage occurrence；
- stage 顺序、producer/consumer、外部输入、广播/归约轴；
- shape 在 crop 前、crop 后、slice 后的三层值；
- padding/tail、layout、qparam 或 `not-applicable`；
- 无法直接从 ONNX 推出的 schedule 字段及其可信 JSON/原生 consumer owner。

不得按算子名称相似直接选择模板。RMSNorm、Softmax、RoPE、GEMM/GEMV 等复合节点必须
对照 ndp-sim 原生 stage DAG；local/remote reduction 取决于归约轴是否跨 slice 分割。

以下五项是注意力 lowering 的强制停门，不得用“各 stage 类型均有可信 JSON”
替代：

- 规则 ID：`CDA-DEEPSEEK-QKV-ALIAS-001`。融合 QKV 必须显式给出
  Q/K/V 的 half-open 区间、crop 后区间、三者共享的归一化输入，以及分离权重/
  bias 与融合 initializer 之间的来源关系；未证明逐字节来源时只允许
  `SEMANTIC_MODEL_MATCH`。
- 规则 ID：`CDA-DEEPSEEK-ATTENTION-NUMERIC-001`。QKT 必须包含
  `1/sqrt(head_dim)`，mask 必须在 softmax 前生效，max 与 sum-reciprocal
  必须覆盖同一完整 key 轴；每个 query/head 的概率和必须在容差内等于 1。
- 规则 ID：`CDA-DEEPSEEK-CROSS-SLICE-ROUTE-001`。跨 slice partial
  reduction 必须逐 producer slice 证明到 consumer 的 N2N 或 DRAM
  gather 路由、地址范围、字节覆盖和 leader 映射；只改变 consumer shape
  或启用 leader slice 不是数据搬运证据。
- 规则 ID：`CDA-DEEPSEEK-PROGRAM-GOLDEN-PARITY-001`。程序图的每个
  input port/source、output tensor、dtype/shape 和 residual 身份必须与
  golden 使用的真实 operand 一致；读取 manifest 但不消费其绑定等价于未绑定。
- 规则 ID：`CDA-DEEPSEEK-KV-LIFETIME-001`。prefill/decode 必须分别
  证明当前 K/V 的写入、cache 可见时点、padding 长度和本轮 attention
  可见范围；past length 正确不能替代 current-token 生命周期。

## 4. 可信 JSON oracle 与正向生成

规则 ID：`CDA-DEEPSEEK-STAGE-JSON-ORACLE-001`

用户确认的两个根只作为配置语义 oracle：

- `jsons/` 中明确分类为算子静态配置的文件；
- `ndp-sim/jsons/` 中固定上游身份、非项目后加/修改的原生算子文件。

对每个代表 stage 先做反解得到字段级合同，再仅从 ONNX/crop/Stage IR 和该合同正向
物化候选。候选与 oracle 比较时必须区分：

- `EXACT_REPLAY`：静态 JSON 逐字段一致；
- `DERIVED_INSTANCE_VALIDATED`：shape/address 等实例字段不同，但 owner、公式和回环完整；
- `RULE_GAP`：生成所需字段无唯一 owner；
- `MODEL_TOPOLOGY_MISMATCH`：ONNX/crop DAG 与原生 graph 不一致；
- `ORACLE_IDENTITY_INVALID`：文件并非固定上游可信原件。

禁止为获得一致而修改 oracle，禁止从 oracle 最终值倒灌未建模字段。

## 5. 覆盖、holdout 与生命周期

规则 ID：`CDA-DEEPSEEK-HOLDOUT-ROUNDTRIP-001`

训练集至少覆盖 elementwise、RMSNorm/reduction、RoPE、Softmax、GEMM/GEMV 五类代表
路径；至少保留一个未参与规则提炼的 stage occurrence 作 holdout。

每个通过项必须同时满足：

1. ONNX/crop → Stage IR 的 shape、dtype、依赖和 occurrence 一致；
2. Stage IR → 最终 JSON 的 leaf owner 完整；
3. 最终 JSON 反解后的 LC/MSE/Buffer/SA/GA/N2N 数量守恒、tag/last 与 lifetime 闭合；
4. JSON → mapping → bitstream → decode 字段/位级回环；
5. 两个空缓存隔离副本逐文件一致；
6. 对 source revision、crop axis、stage type、关键 JSON leaf 和 bitstream 位翻转的篡改均
   fail closed。

native pipeline 若 bitstream 子进程失败后继续执行，验证器必须以缺失/陈旧 provenance
判失败，不能接受下游残留。

## 6. 声明边界

本地通过只表示“当前规则足以复现已覆盖的可信配置语义，并拦截已注入的错误”。它不证明：

- ONNX 与 ndp-sim 权重逐字节同源；
- 未覆盖 stage 或新 shape 已获授权；
- 服务器 stock RTL 已自然完成；
- E4/E5、正式 target config 或整网发布。

服务器动态测试若后续需要，任务只发送给“测试修复”会话；本会话不生成服务器包。

