# exact UINT8 quant-tail：26-vs-25 config-only 判别记录

日期：2026-07-27  
owner：QuantizeLinear/shared exact uint8 quant-tail  
主线回传：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 边界与读取收据

- 未修改 `.agents/plan.md`、`.agents/rules/**`、`rtl/**` 或其他算子族资产。
- 未检查服务器文件/名称/身份，未上传、未运行，未生成 mapping、bitstream、
  execplan、SCA 或服务器包。
- `.agents/plan.md` 生成时读取 SHA 为
  `c5120b1cfaf3b97a055f6958d5a76b3c31d1f842a545e5a8c00bb626f52636ec`；
  验证时当前 SHA 已漂移为
  `656a6053db463f670e423421597eb4ab717c88de8660d521f67c951ff84d4b32`。
  二者只作 historical/mutable provenance，不进入语义 current-match 门。
- 语义 current-match 规则：
  - `.agents/rules/算子配置规则.md`
    `407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc`
  - `.agents/rules/精确UINT8量化尾专项规则.md`
    `5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0`
  - `.agents/rules/NDP硬件字段语义.md`
    `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59`
- 路由索引生成时历史收据为 `6ae4c7fe...ce1a4`；本轮末复读当前索引为
  `3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19`。
  与 plan 一样，索引只作 routing provenance，不替代上述语义 current-match 门。
- 最终校验另保存 `final_refresh_receipt`，当次 plan/index 分别为
  `a1e19c6e84360641205836f6fa0b172fc0405472b8b2dfdc4c580cc2e0875516` 与
  `3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19`；
  二者在最终校验时 current-match，但 gate 仍为
  `final_validation_snapshot_provenance_only`，不产生后续永动追写。

## RETURN_ANALYSIS

`input_int32=400`、`multiplier_bits=0x3d828f5c`、`zero_point=0` 的最小判别：

1. stage0 只启用 GA `mul`，INT32 ingress 转 FP32，乘积在 FP32 scratch
   `0x800000` 物化为 `0x41cc0000`（25.5）。
2. stage1 从 scratch raw FP32 ingress，执行
   `MAC(x,1.0,12582912.0)`，再执行
   `INT32_SUB(encoded,0x4b400000-zero_point)`，最后由 GA outport
   `int32touint8` 饱和/打包。
3. 最终配置绑定结果为 26；一阶段 fused negative control 为 25。

这证明显式 scratch 可在该冻结单 occurrence 上隔离 MUL 的 binary32 舍入点，不能证明
完整共享尾域或 production 路径。

相对可信静态
`ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json`，三份最终配置共有 222 个
leaf diff：

- stage0：173
- stage1：25
- fused negative control：24

`materialized_leaf_ownership.json` 对每个 leaf 明确记录 owner、输入来源、公式、旧值、
期望新值、授权与是否 base；validator 从最终 JSON 重新 diff，未声明或超 allowlist
即 fail closed。

最终 occurrence/address 方程
`addr=stream2.base_addr+LC2_value*stream2.dim_stride[0]+byte_in_32B_transaction`
重算覆盖：

- stage0 scratch：4×32 B，`[0x800000,0x800080)`，128/128 B；
- stage1 diagnostic output：1×32 B，`[0x1000000,0x1000020)`，32/32 B；
- fused negative control：1×32 B，`[0x1800000,0x1800020)`，32/32 B。

## BYPASS_ANNOTATION

- `bypass_reason`：原一阶段 `quant_from_buffer` 把 multiplier 与 magic bias 收缩到
  MAC；W3 要求 multiplier 的 binary32 结果先物化/舍入；功能 RTL 已冻结。
- `contradicted_or_missing_native_path`：400×`0x3d828f5c` 的顺序路径为 26，
  one-round fused magic 模型为 25；现有 typed registry 无非收缩共享尾入口。
- `exact_equivalence_scope`：仅 32 元素、每 lane int32=400、zp=0、有限非负、
  HWC8、无 tail、scratch bit-preserving 的冻结诊断 occurrence。
- `materialized_configuration_mechanism`：两次串行原生 JSON + 128 B FP32 scratch +
  barrier；独立一阶段 fused JSON 作负控。
- `performance_and_resource_cost`：两次配置启动；额外 128 B scratch；额外
  128 B write + 128 B read；禁止 fusion；未测 mapping/cycle/contention。
- `unresolved_production_blocker`：完整域等价、signed ingress、magic domain、
  occurrence/tail、typed handler、mapper、execplan/SCA、terminal/readback、
  config-bound RTL dynamic 均未闭合；QuantizeLinear 另缺 exact division。
- `claim_boundary`：`LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE`。

scratch 不是 host 预计算/replay：stage0 是合同内正式 producer，stage1 只按 identity
address mapping 接收其 128 B FP32 output；dtype、word bits、shape、layout 和顺序均不
改变。`scaled/rounded/saturated/final output` 四类 host precompute 均为 false，满足
`CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`。

因此本资产不得称 `CONFIG_ONLY_CORRECTNESS_BASELINE`，`candidate_release=false`。

## node0074 首个不可绕行断点

node0074/hwop-0074-00 的最先断点仍是 `exact_binary32_division`：

- `x_bits=0x3d0f81f1`
- `scale_bits=0x3cbf57ec`
- exact binary32 divide 后 RNE/saturate：2
- `reciprocal_bits=0x422b4095` 的 reciprocal-FMA-magic：1

该反例为正有限 FP32，raw FP32 ingress 字段可表达，也不依赖 signed INT32 ingress
反例；因此 exact division 在 typed handler、mapper、occurrence、tail、terminal 之前
已阻止生成真实 node0074 target。node0074 target JSON 未生成。

Flatten node0073 integrated E2 对 node0074-A 的依赖只记录为
`DEPENDENCY_RECORDED_ENDPOINT_NOT_MATERIALIZED`：

- final same-storage identity；
- final `consumer_base=producer_base+view_offset`；
- 32,768 个 FP32 元素、131,072 B 的 accepted read coverage；
- alias storage 存活至最后一次 accepted node0074-A read。

上述 storage/base/offset/coverage/lifetime 的最终值全部保持 `null`，
`provisional_address_allowed=false`、`target_endpoint_claimed=false`。exact division
未闭合前不得用 provisional endpoint 提升 Flatten integrated E2。

## RULE_DELTA_PROPOSAL

`NO_PUBLIC_RULE_CHANGE_REQUESTED`。

现行
`CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001`、
`CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`、
`CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001`
和精确 UINT8 量化尾规则已覆盖本轮停止/声明边界。若以后 mapping/bitstream/execplan/SCA
和动态证据闭合，可再向主线提议把“两阶段 scratch 必须逐 word 保持 stage0 binary32
结果、并保留 fused negative control”提升为共享 recipe；当前证据不足，不建议写公共
规则。

## BLOCKER_DELTA

- `B_EXACT_TAIL_CONFIG_ONLY_FULL_DOMAIN`：当前只闭合 singleton 26-vs-25 判别，
  非完整合法/冻结 ResNet 实例域。
- `B_EXACT_TAIL_NATIVE_TRANSPORT`：typed handler、mapper、address-bound
  materializer、mapping、bitstream、execplan/SCA 未闭合。
- `B_EXACT_TAIL_DYNAMIC_TERMINAL`：未执行 config-bound RTL simulator，
  terminal/readback 未证明。
- `B_QUANT_NODE0074_EXACT_DIVISION`：FP32 exact divide 无已证纯配置原语，最小
  反例为 2-vs-1。
- `B_QUANT_NODE0074_FLATTEN_ENDPOINT_BINDING`：等待 final same-storage、
  base+offset、131,072 B accepted read coverage 与 accepted-lifetime；当前只记录
  依赖，禁止 provisional 地址，且该门从属于 exact-division 首断点。
- `B_EXACT_TAIL_SIGNED_AND_MAGIC_DOMAIN`：negative INT32 ingress 与 magic 有效域
  仍需独立全域处理。

## PACKAGE_RELEASE

```text
candidate_release=false
server_package=false
PACKAGE_RELEASE=NONE
server_files_inspected=false
server_run=false
```

## 资产身份

- capability contract：
  `dedd0e467a31ecb42cd3e76faddb55901286b97fb2311fc4052d0a157dbd8c6e`
- capability report：
  `f73c9eace3547ea5d02f976d43d63a1236258dcbeb8a77c286235047f6a2b7e1`
- discriminator contract：
  `82ab3276a8ae9ee35aeda366756dd4525dfac77c6e3ed40cf395d7a011f8a477`
- generator/validator module：
  `9be94cfe19635c3224643427d0e1a275a0ef1391f6704f7af07a0b58a69af90f`
- build CLI：
  `a70f6296f416c3120ea4a2143733ee2ee342b21aeeebbf9da64db284323c6e5f`
- validate CLI：
  `cb56258c2079d66d4afbdc20151a91d2e43d23267a8f8778b517419b2214d62e`
- family test：
  `f005e3b874fbe8d39f4eeb41207b095c4a697919e13e8d9bb94387926de380bb`
- stage0 config：
  `007d90efa1b4487de7cd56b5ffd3580eacf4abc298267dba7cc5971c52566b7e`
- stage1 config：
  `f1db320f32a0e94d198abdc0ec4b6d743d66feadc26c1833663897de121ffb93`
- fused negative control：
  `88b13db96c460db56eb97b52f3ec053afadc7d6780d1b37421f3885312755501`
- leaf ownership：
  `c2187c6b73a8cbde238c4a4a73f590cabadce5f623a170ddef206fe67270301d`
- manifest：
  `9800cce794f357b222f58fa53f393382d0cb90f6c0ce5dddb2b7ec79f986b4f0`
- discriminator report：
  `1a10cd4697af0e8e36e8d814fff783f99d920267caaa539d9760d400166739c0`
- generic strict config report（3/3 valid）：
  `6896c94dd8f34abbfa6beb64898b9af93871e4eb5f95a0e76dfd6aeb69d4a564`

## 本地验证

```text
python -m unittest tests.test_exact_uint8_quant_tail_capability
5/5 PASS

python -m unittest tests.test_exact_uint8_quant_tail_rounding_discriminator
6/6 PASS

python tools/validate_exact_uint8_quant_tail_capability.py
PASS_PROPOSAL_VALID_NO_UNCONDITIONAL_PURE_CONFIG

python tools/build_exact_uint8_quant_tail_rounding_discriminator.py
PASS_LOCAL_CONFIG_BOUND_26_VS_25_DIAGNOSTIC

python tools/validate_exact_uint8_quant_tail_rounding_discriminator.py
PASS_LOCAL_CONFIG_BOUND_26_VS_25_DIAGNOSTIC

python tools/validate_operator_configs.py <three diagnostic configs>
3/3 strict configs valid
```
