# Conv stem 单乘积序列化 accumulate 本地 E2 闭合

日期：2026-07-29  
owner：Conv / SA  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 活动收据与授权

- `.agents/plan.md`：
  `d2d4ab7297101614b15ec5f579f1f6060a3da6883c55ee9ffbe388df8794bc08`
  （mutable provenance；不作语义 gate）
- `.agents/rules/生成前必读索引.md`：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/算子配置规则.md`：
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/INT8_SA点积专项规则.md`：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/NDP硬件字段语义.md`：
  `18d71520dd4ededc5edd9bb316acd0cc0421a9a261cf14b28ea6997ddd0e844a`
- `.agents/rules/精确UINT8量化尾专项规则.md`：
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `.agents/rules/RequantizeUint8算子配置规则.md`：
  `5fcd1c9d2f6fa6dd193e369412c46c16b7bd087b570cc607aa0d0f06ba4c7555`
- stem 窄授权：
  `.agents/task_records/20260729_conv_stem_typed_materializer_patchset_authorization.md`
  SHA-256=
  `2a8bb1faf66a801c1a1f2cf718dd10779b5846a2ff5c7512409532797286a185`

授权 preimage 在写入前 current-match。活动 `ndp-sim` 与 `rtl/**` 未修改；patch 只安装到
隔离副本。未检查服务器文件/名称/identity，未上传、未运行、未取得 lease。

## RETURN_ANALYSIS

状态：

```text
r5:hwop-0001-00 accumulate = CONFIG_ONLY_CORRECTNESS_BASELINE / LOCAL_E2
server package             = NONE
E3/E4/E5                   = false
numeric_analysis_repeated  = false
```

本轮 fresh 消费 `r5:hwop-0001-00` typed lowering、正式 ONNX/W3 activation/weight/bias
和已验收 remaining52 数值域；没有消费 node0004 identity、常量、固定尺寸、旧 JSON、
mapping、bitstream、execplan/SCA、package 或 simulator output。

此前物化前 gate
`conv_stem_serialized_materialization_gate_v1.json` 保留为负面历史；主线窄授权后已由
fresh stem patchset/handler、配置、物理资产和本记录取代，不再是 current gate。

### 1. fresh typed materializer 与 patchset

`resnet50_pipeline/ndp_patch_toolchain.py` 仅新增：

- patchset ID：
  `resnet50-ndp-toolchain-6144-conv-stem-serialized-one-product-v1`
- 三个唯一 operator type：
  `resnet50_conv_stem_hwop0001_serialized_wave0/1/2`
- 精确 ABI：
  A=`int8[1,1,9472]`、B=`uint8[1,1,7426048]`、
  C=`int32[1,1,16]`、D=`int32[1,1,200704]`
- used slices 只接受 28 或 8。

patchset：

- `contracts/operator_config/r5_conv_stem_serialized_one_product_patchset_v1.json`
- file SHA-256=
  `91e095b1d39ec0e8b2baaf5d14fc047bbf98fe9a7a4c111e5c7b5ca6ce7dcd30`
- semantic patchset SHA-256=
  `216359f140740c149a28cb8c34a087ae50518cf851e831b457804c1fca6c381a`
- base commit=`ec12424516ae0304228dd2321d4e604fe225e04e`

mapper 三次均为 exact penalty=0、`fallback_used=false`。

### 2. 数值、packing、tail 与 W3

固定实例：

```text
input       uint8  [16,3,224,224]
weight      int8   [64,3,7,7]
output      int32  [16,64,112,112]
stride      2x2
padding     3/3/3/3
x_zp        114
logical K   147
serialized K 148
```

每 occurrence 最多一个非零 `s8*u8` product lane；`k=147` 是全零 weight tail。
DataC 初值逐通道为：

```text
bias[oc] - 114 * sum(weight[oc,0:147]) mod 2^32
```

不存在 host 预计算 partial sum、final accumulator、scaled、rounded、saturated 或 final
UINT8 tensor。activation 是正式 producer output 的值保持 im2col replay；weight/bias
及 correction leaf 均来自冻结常量和显式公式。

完整物理/config-bound W3：

```text
INT32 elements                         12,845,056
config-bound mismatch                  0
normal dot4 occurrences                475,267,072
serialized padded occurrences          1,901,068,288
occurrence ratio                       4.0x
effective lane utilization             24.831081%
```

- physical manifest SHA-256=
  `3432e8ebb30df8bbfaa01afa333c2eb27b9c49d0ecaba9965eb16ae500b12042`
- physical validation SHA-256=
  `b9d64dd3ab6558ffa92e44f14ecc584b5f5e9e6d50fa5d5691caf5c9f3c10bc0`

### 3. 最终 JSON→mapping→bitstream→execplan/SCA

三份最终 JSON 与各自静态 owner 做逐 leaf diff：

```text
non-base leaf diff count = 0
unauthorized changes      = 0
```

base 由 native graph planner、execplan Write_Reg 与 SCA 唯一拥有。隔离 native pipeline
两次执行除 `placement.png` 外逐文件哈希一致：

- final graph SHA-256=
  `b6754251b97dbaba9f3aaeb333956db190372b8b51f55ee0511dcd02c230d9e5`
- execplan SHA-256=
  `a79ac8bf4dd782fce5477fd30260ca0fded55e3a776488edf142978e68da702b`
- execplan validation SHA-256=
  `dc96ffbd6b13a6a6a3b81d0d287474ed95d8328e89a7bb3ffec0f953a34321c7`
- double-run SHA-256=
  `092b12667c101e6f5d7842996bd484ee7782332d6d2978b17cbab023bcf26b34`
- `sca_cfg.json` SHA-256=
  `569d134343a864dadf3d71376892779d8669d21cf536da1fb8110854eab4f71c`
- `sca_cfg_D.json` SHA-256=
  `852bd63b003274f70a41a7a39a6f2594dde91e4e242cd0aad18cc1344487001e`

execplan 为 251 条 64-bit instruction / 126 条 128-bit line，包含三次
`Load_Config→Start_Comp`，slice mask 精确为 28/28/8。

### 4. exact request/address/coverage/lifetime

通用逐请求 validator 因对 64 个平移等价 slice-region 重复构建最高 46 万项 Python
字典而超时；这不是配置或 RTL 失败。本族 validator 未抽样，也未实现第二套 planner：

1. 对每个最终 stream 完整枚举其最终 index tuple 与 16-byte transfer；
2. 逐 word 复核最终 interleave4 remap；
3. 证明每个 target 在每个 bank 内连续且与 SCA/SCA_D exact-set 一致；
4. 按 native planner 的 slice translation 回放全部 64 个 region；
5. 对全部带重数请求生成顺序敏感二进制哈希；
6. 按公共 validator 的 7-hex+LF 格式对全部唯一地址生成排序哈希。

全量结果：

```text
request count with multiplicity        33,354,752
unique 128-bit request addresses       32,953,600
valid request bytes with multiplicity  533,676,032
formal D write bytes                   51,380,224
typed INT32 output bytes               51,380,224
SCA tensor entries                     1,024
SCA exact entries incl. configs        1,027
maximum data row                       6033
row limit exclusive                    6144
config bases                           0x5E4800/0x5E4C00/0x5E5000
post-data alignment gap                16 bytes
alias/wrap/outside-region              0
```

指纹：

- ordered request address SHA-256=
  `8532c541aabbde1d18106d8bf967d18d83544cd82e8646ab0166dddfd4ede824`
- sorted unique address SHA-256=
  `f7faf7d25fa340f5936aeabfe6e2f32580df9cea76a9f0263174514bd5123f9f`
- report SHA-256=
  `74183efff295a781eaebb76ff7b636302881d9f622259dbe09b7d26fee355982`
- native local-E2 bundle SHA-256=
  `261f2186fb9a1a9dfd19a84503a2bbbc4688a293835ce1bb47925ab5e3ae1a87`

### 5. Requant 只读绑定

只读消费：

- `contracts/operator_config/requant_conv53_tail_signature_binding_v1.json`
- SHA-256=
  `0cb706c1f95de010e840b212d3fa7b22cb63e20c4939da1eec52afc56e957fee`
- `r5:hwop-0001-01`：
  `FULL_LOCAL_E2_MATERIALIZED_EXACT_NODE0001`
- profile：
  `TAIL_N16_C64_H112_W112_HWC8`

没有重跑 Requant W3 分类，没有复制其 multiplier。accumulate 输出的逻辑 identity 与
HWC8 地址方程兼容；但本轮未把 accumulate D 与 Requant A 放入同一 multi-operator
graph，故 zero-copy shared address、barrier 和跨 stage lifetime 仍未绑定。完整
Conv UINT8 node 尚未闭合。

## BYPASS_ANNOTATION

```text
bypass_reason:
  stem frozen dot4 range [-101231,95485] has 2,499,984 signed17 violations;
  historical four-lane reduction ignored cout.

contradicted_or_missing_native_path:
  no immutable signed18 four-lane server RTL identity is bound; current server
  compile first stops at SA_ALU/SA_PE_Mul_Array.slice_rst interface mismatch.

exact_equivalence_scope:
  complete frozen W3 stem accumulate only, batch16/C64/H112/W112/K147/xzp114.

materialized_configuration_mechanism:
  28/28/8 waves, one nonzero product lane, DataC correction+psum, padded K148,
  four-bank striping, native mapping/bitstream/execplan/SCA and config-bound inverse.

performance_and_resource_cost:
  4x occurrence, 24.831% lane utilization, 526,685,952 physical input/golden bytes,
  533,676,032 valid request bytes with multiplicity.

unresolved_production_blocker:
  server identity/dynamic E3-E5 absent; accumulate→Requant shared address/lifetime
  is not composed.

claim_boundary:
  CONFIG_ONLY_CORRECTNESS_BASELINE / LOCAL_E2 / accumulate-only; not production,
  not performance release, not server package, not complete Conv UINT8 node.
```

## 机器合同与测试

- contract：
  `contracts/operator_config/r5_conv_stem_serialized_local_e2_v1.json`
- contract SHA-256=
  `5ae714695b732e062193e3a1cbca818bad3a825bb8da077a1ad363c9b3331e12`
- contract validation SHA-256=
  `35abb9b53be95a2d71de4ff843c720133677aeb8b1d77f336a82b2a6eb8271f6`

定向入口：

```powershell
.venv\Scripts\python.exe tools\validate_conv_stem_serialized_local_e2.py
.venv\Scripts\python.exe tools\validate_conv_stem_request_addresses.py
.venv\Scripts\python.exe tools\build_conv_stem_serialized_contract.py
.venv\Scripts\python.exe -m unittest `
  tests.test_ndp_patch_toolchain `
  tests.test_conv_stem_serialized_materialization_gate `
  tests.test_conv_stem_request_address_validator `
  tests.test_conv_stem_serialized_contract -v
```

结果：

```text
physical config-bound validator PASS
request/address validator PASS
contract current-match validator PASS
15/15 focused tests PASS
```

## BLOCKER_DELTA

关闭：

- `B_CONV_STEM_TYPED_MATERIALIZER_AND_HANDLER`
- `B_CONV_STEM_PHYSICAL_COVERAGE`
- `B_CONV_STEM_CONFIG_BOUND_W3`
- `B_CONV_STEM_ACCUMULATE_LOCAL_E2`

保持：

- `B_CONV_STEM_REQUANT_SHARED_ADDRESS_LIFETIME_BINDING`
- `B_CONV_STEM_SERVER_E3_E4_E5`
- `B_NODE0004_DYNAMIC_RESULT_PENDING`
- `B_NODE0004_SERVER_RTL_COMPILE_INTERFACE_MISMATCH`

## RULE_DELTA_PROPOSAL

`NONE`。公共大规模地址规则已经允许压缩报告并要求完整枚举、multiplicity、unique count、
ordered hash 和边界样本；本族 exact compact validator 是该规则的直接实现，不需要新增
公共语义。

## PACKAGE_RELEASE

```text
PACKAGE_RELEASE=NONE
```

node0004 尚无有效动态结果；本轮没有生成 stem 服务器包。
