# DequantizeLinear 全族 complete-JSON 再生成 v1

日期：2026-08-06  
family owner：DequantizeLinear  
上级任务：`019fd276-14c5-7800-94db-87ebfb9ce632`  
唯一主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
状态：`FAMILY_COMPLETE_JSON_COMPLETE`

## 1. 边界与结论

- 完整枚举 lowering bundle 中全部 `DequantizeLinear` stage：
  `hwop-0072-00`、`hwop-0077-00`，共 2/2。
- 两者按 materialized-consumer signature 分为 2 个等价类；shape、qparam、
  physical occurrence、stride、padding、动态证据均不同。
- 物化 2 份全新 strict complete JSON；每份 416 leaves，逐 leaf ledger 416/416，
  全族 832/832，`UNRESOLVED=0`。
- 两份 candidate 分别与各自 frozen current final JSON 416/416 leaves 相同。
  未发现 current 配置 leaf 疑似缺陷；静态配置到 final candidate 各有 10 个已声明
  materialization diff（2 个 base + 8 个 typed GA constants）。
- node0072 保持 `CONFIG_ONLY_CORRECTNESS_BASELINE/local materialized E2`；
  node0077 E4/E5 只作冻结成熟正控，未重跑。
- 正式三方节点计数仍为 `1/78`，不得因本地 complete JSON 增加。
- 未生成 mapping、bitstream、execplan、SCA/SCA_D、服务器包；未上传、未运行、
  未申请 lease。

current artifact root：

`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/`

主报告：

- path：
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/report.json`
- SHA256：
  `8bb7199fd8c86afccf62601cac67b89af5503cb4426ee83c6f2b3fdc5981cae5`

## 2. current 规则与公共门收据

完整读取：

| path | SHA256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md`（mutable provenance） | `add16cbf259314ffc04948c4b268766f677d629901e148d970e37a8d99fdf4b0` |
| `.agents/rules/生成前必读索引.md` | `d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6` |
| `.agents/rules/算子配置规则.md` | `52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820` |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| `.agents/rules/DequantizeLinear算子配置规则.md` | `f8cf7d2a041426f2b3348f3d02b570e3e559fe1a77c643a8393e77a2583e15a1` |
| `.agents/rules/DequantizeLinear原子动态合同规则.md` | `cc9e5215d92e55b7440a07954503586c9a6d50f56fe505595341c0ba71358d85` |
| `contracts/operator_config/complete_json_generation_contract_v1.json` | `de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746` |

fresh 公共工具：

- `tools/validate_complete_operator_json_candidate.py`
  SHA256=`4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f`
- `tools/audit_complete_operator_json_family_set.py`
  SHA256=`baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82`

确认并执行的主要 rule IDs：

- `CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001`
- `CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001`
- `CDA-NATIVE-COMPOSITION-BOUNDARY-001`
- `CDA-CONFIG-SEMANTIC-OWNERSHIP-001`
- `CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001`
- `CDA-DEQUANT-ONNX-ORDER-001`
- `CDA-DEQUANT-NO-AFFINE-MAC-001`
- `CDA-DEQUANT-TWO-STAGE-GA-001`
- `CDA-DEQUANT-NORMAL-OUTBUFFER-001`
- `CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001`
- `CDA-DEQUANT-MATERIALIZED-CONSTANT-NORMALIZATION-001`
- `CDA-DEQUANT-NODE0072-CONFIG-ONLY-E2-001`

## 3. target stage 与等价类

### 3.1 hwop-0072-00 / node0072

- op：`DequantizeLinear`
- logical：UINT8 `[16,2048,1,1]` → FP32 `[16,2048,1,1]`
- layout：logical NCHW contiguous；physical CWH `[16,74,1]`，28 slices
- qparam：scale bits `0x3cbf57ec`，scale
  `0.02335735410451889`，zero_point `0`
- topology：4 ADD `(x + -zp)` → 4 MUL `(* scale)`，normal outbuffer
- occurrence：74/slice；A=1184 B/slice；D=4736 B/slice=296×16 B
- valid D：131072 B；physical D：132608 B；padding：1536 B
- DAG：node0071 producer → node0072 → node0073 View
- qdomain/alias：输入保持 node0071 final UINT8 qdomain；没有额外 requant。
  静态 `-0.0` 按专项规则在 final JSON 规范化为 `"0.0"`，不改变数值域。
- integrated lifetime：未闭合。

### 3.2 hwop-0077-00 / node0077

- op：`DequantizeLinear`
- logical：UINT8 `[16,1000]` → FP32 `[16,1000]`
- layout：logical NC contiguous；physical CWH `[16,47,1]`，28 slices
- qparam：scale bits `0x3e01622d`，scale
  `0.12635107338428497`，zero_point `60`
- topology：4 ADD `(x-60)` → 4 MUL `(* scale)`，normal outbuffer
- occurrence：47/slice；A=752 B/slice；D=3008 B/slice=188×16 B
- input padding：每 slice 2 个 UINT8 `60`；D padding 为 +0.0f
- DAG：node0076 producer → node0077 → graph output
- 动态证据：冻结 full-v6 E4 FIRST_DYNAMIC_PASS 与 fresh-identity E5
  REPEATED_DYNAMIC_PASS；本轮未复测。

stage inventory：

- path：
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/stage_inventory.json`
- SHA256：
  `880671de5be1fe5cb9ef9bc893fe62b9c798c2c97896a281b78410cd2b28da0a`

## 4. 原生参考分级与 handler 能力

唯一 pinned native 参考：

- path：`ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json`
- repository commit：`ec12424516ae0304228dd2321d4e604fe225e04e`
- blob：`41c502ce87ac7712c42dcc6214ecb76f3bc4c06b`
- SHA256：`15f5321ab57cb73ca2f650693859657759f834389677451a9a89e66217e9e6da`
- source instance：A
- node0072/node0077 target applicability：C
- 原因：源是 A+B composite Add-Dequant，不能作为 standalone A-only
  Dequant 的完整数值/拓扑/shape authority。

两个 current project config 与两个 current final JSON 均分级 D；它们只作 target
实例证据和逐 leaf 对比，不冒充 upstream authority。

原生 registry 的 add_dequant handler 是 placeholder，只覆盖 composite A+B 的有限
loop/stride patch；存在 registry/JSON 不证明 standalone shape、qparam、layout 或
cross-stage 泛化。本轮使用 `AUTHORIZED_PATCH`，严格限于 lowering bundle 中这两个
明确实例。

参考适用性：

- `reference_applicability.json`
- SHA256=`8e43787d179198c38ba2a69bf3ea7b556f359adc6c285e3f12c1af32e7c20d0d`

handler matrix：

- `handler_capability.json`
- SHA256=`b64390735ee53b68a625a4c7b60653ad55cbb944c61d41fbf5af28b9ca7db04d`
- dependent leaves：228
- uncovered：0

## 5. candidate 与逐 leaf 账本

| stage | candidate SHA256 | contract SHA256 | public result |
|---|---|---|---|
| node0072 | `317f263033d5789988ba7d50985bb166c0df7fb35425b51109ca049efb61e390` | `c56ba06bf2b6ebbd412ac52f4fa1cb51f667f5fa291e70b943df48f67c8a8935` | COMPLETE/PASS |
| node0077 | `1235ef420360750b22cba37d72029e555db7c50c069be8ed741ebf747ca23632` | `998cef009940c9e3389c937bbe74afeb242c24885bc7c7422f3a7822d75924ce` | COMPLETE/PASS |

每份 ledger：

- 416/416 target primitive leaves；
- `UNRESOLVED=0`；
- origin counts：
  `ADDRESS_PLANNER_DERIVED=2`、
  `EXPLICIT_DISABLED=124`、
  `MODEL_DERIVED=24`、
  `RTL_DERIVED=76`、
  `SCHEDULE_DERIVED=190`；
- 明确记录 `SOURCE_ABSENT_NOT_APPLICABLE`、`EXPLICIT_NULL_INACTIVE`、
  `EXPLICIT_ZERO`、`TARGET_REQUIRED_DERIVED`；
- 没有 `SOURCE_ABSENT_UNKNOWN_FOR_TARGET`。

family ledger index：

- `field_provenance_ledger.json`
- SHA256=`c04ca354a11ec407f3141bfdeedf8b1daf1a4aa7a08ed322cce2d66f948d4776`

内部 primitive composition：

- 每 stage 1 个已解析 ADD→MUL boundary；
- producer/consumer 均 FP32；
- one occurrence 的 4-lane byte set 完全相等，16 B；
- 保留 ADD 后 binary32 rounding，再进入 MUL；
- external integrated lifetime 不在该 boundary claim 内。

## 6. 与 current 正在测试配置逐 leaf 对比

- node0072 candidate ↔ current final：416 `SAME`，0 其他。
- node0077 candidate ↔ current final：416 `SAME`，0 其他。
- family 总计：832 `SAME`。
- `SUSPECTED_CURRENT_DEFECT=0`
- `NEW_CANDIDATE_DEFECT=0`
- leaf 级 `DYNAMIC_ONLY=0`

family current diff：

- `current_test_diff.json`
- SHA256=`eac700539e6745f145ded5b27dcfe95c45613fb93b739f4bcd20380e9061c795`

排除的非配置卡点：

- node0072 native production handler/path 不适配；
- node0071→node0072 same-storage/address/coverage/lifetime integrated binding；
- node0072→node0073 accepted write/completion/visibility/lifetime binding；
- node0072 formal E4/E5；
- node0077 atomic-v3 observer temporal incomplete（不推翻 full-v6 formal D）。

## 7. BYPASS_ANNOTATION（node0072）

- `bypass_reason`：
  功能 RTL 冻结，原生 composite add_dequant/placeholder handler 不能证明
  standalone Dequant target。
- `contradicted_or_missing_native_path`：
  无 standalone A-only native exact template/complete handler；原生 B stream、
  buffer2、GROUP1 和 composite topology 对目标不适用。
- `exact_equivalence_scope`：
  frozen node0072 typed instance UINT8 `[16,2048,1,1]`、scale
  `0x3cbf57ec`、zero_point 0、physical 28×1184 words。
- `materialized_configuration_mechanism`：
  两级普通 GA：4 ADD 后 4 MUL；仅 A/D streams；显式 CWH occurrence、padding、
  typed constants 和 frozen A/D base。
- `performance_and_resource_cost`：
  8 个 GA PE、两个算术层、74 occurrence/slice、28 slices、384 physical padding
  elements；无原生单级性能声明。
- `unresolved_production_blocker`：
  `B_DEQUANT_NODE0072_NATIVE_PRODUCTION_PATH`、
  `B_GAP_NODE0071_TO_NODE0072_INTEGRATED_BINDING`、
  `B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING`、
  `B_DEQUANT_NODE0072_FORMAL_E4_E5`。
- `claim_boundary`：
  只证明 local complete strict JSON 与 frozen current final 的实例级配置一致，
  不证明 production、integrated lifetime 或 E4/E5。

## 8. 数值、strict 与负控

输入/golden：

| tensor | SHA256 |
|---|---|
| node0072 UINT8 input | `70e76086c96394b1cc0a50cf316663b4ea1def7f0d0b73568dd83662d6556b55` |
| node0072 FP32 golden | `8d334045de23456fdcfda347c6667c353663d2c1f3bca24c348017794263bf8a` |
| node0077 UINT8 input | `10d974cdab69904bfd3ed7749059e26e16388ba784872f0d432cd2ba14bcbdc8` |
| node0077 FP32 golden | `2c6c5fabc1d41fceee35f06221efb4c64b94fabfe7a0b4680d2acf2186ca0894` |

结果：

- node0072 two-stage ↔ W3 golden：bit mismatch 0；wrong zp=60 负控被拒绝。
- node0077 two-stage ↔ W3 golden：bit mismatch 0；
  single affine-MAC 顺序负控 mismatch 12976。
- 12 个配置负控全部 fail closed：
  composite B leakage、missing D、wrong D mask、D stride=256 coverage、
  qparam drift、single-stage/order；每个 stage 各 6 个。
- strict shadow：2/2 valid，0 invalid。

证据：

- `numeric_formula_validation.json`
  SHA256=`e1852417a76921e0556824e5808066f717e914dcb09e1a882fbff098940d960f`
- `negative_controls.json`
  SHA256=`bda662a693b28699570b3fd4cd835dd5534e06e27afdffff2ec2f9a2ac380fde`
- `config_shadow_validation.json`
  SHA256=`9b4204d8fbbe2c87c36e59fcd9e2acfff01c015ba7a2c665f903807a176d22ba`

## 9. fresh 公共验收

执行入口：

```text
<workspace-python> -m unittest \
  tests.test_dequantize_linear_complete_json_regeneration \
  tests.test_complete_operator_json_candidate \
  tests.test_complete_operator_json_family_set

<workspace-python> tools/validate_operator_configs.py \
  artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/complete_json \
  --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/config_shadow_validation.json

<workspace-python> tools/validate_complete_operator_json_candidate.py \
  artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/contracts/node0072-00_candidate_contract.json \
  --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/node0072_public_validation.json

<workspace-python> tools/validate_complete_operator_json_candidate.py \
  artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/contracts/node0077-00_candidate_contract.json \
  --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/node0077_public_validation.json

<workspace-python> tools/audit_complete_operator_json_family_set.py \
  artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/family_set.json \
  --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/family_set_public_audit.json
```

结果：

- unittest：15/15 PASS，exit 0（本族 4 + 公共 11）。
- strict shadow：exit 0。
- node0072 shared candidate：`pass=true`、`contract_valid=true`、
  `errors=0`、`completion_blockers=0`、416/416。
- node0077 shared candidate：`pass=true`、`contract_valid=true`、
  `errors=0`、`completion_blockers=0`、416/416。
- family-set：`pass=true`、expected=2、covered=2、missing=0、
  unexpected=0、errors=0。
- artifact-root forbidden scan：0 ZIP、0 `PREPARE_AND_RUN.sh`、
  0 `TEST_PACKAGE_MANIFEST.json`、0 `SERVER_RESULT_GATE.json`。

fresh reports：

| report | SHA256 |
|---|---|
| node0072 public validation | `f0c327b5db1abec8c929856f0a98349787a444e171b0bb242eb62c11d19337b1` |
| node0077 public validation | `887af45fac524e4d627e0b566ad6efd2ad048e08bc2b451353399006aae24942` |
| family-set | `bc55c0376e9888349f76bc110b12e65d3519f2d807a7514e175cd4d1000fb793` |
| family-set public audit | `45e48f4f26d30787ffeb1403e57788b9d8500f099482f501c9b71721371f8c26` |

首次公共验收曾因 candidate 文件原始 SHA 与 canonical-content SHA 混用而 fail
closed；失败版本已移入
`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear_audit_history/`，
不作为 current 输入。fresh 身份改为直接绑定磁盘 candidate 文件 SHA 后重建并通过。
该历史中不存在任何服务器包。

## 10. 结构化回传

### FAMILY_COMPLETE_JSON_FINDINGS / RETURN_ANALYSIS

- status：`COMPLETE`
- family：`dequantize_linear`
- stages：2/2
- equivalence classes：2
- materialized candidates：2
- candidate/ledger leaves：832/832
- unresolved leaves：0
- public validator errors：0
- public completion blockers：0
- current suspected config defect：0
- current candidate defect：0
- formal three-way count：保持 1/78
- repeated numeric analysis：
  是，仅按本轮新授权重跑本地 formula/W3；没有重跑 node0077 E4/E5，没有重建
  node0072 local E2 后端链。
- consumed frozen assets：
  是，只读消费 lowering、W3 tensor、static/final JSON 和历史 task records。

### BLOCKER_DELTA

`NO_NEW_BLOCKER`。node0072 四项 production/integrated/dynamic blocker 保持；node0077
正式闭环结论不变。

### RULE_DELTA_PROPOSAL

`NONE`。本轮确认公共三条 complete-JSON 规则和 Dequant 两条实例规则足以裁决，
没有非同义规则缺口。

### PACKAGE_RELEASE

`NONE`。未生成、未重建、未修改任何服务器测试包。

### claim boundary

该记录只证明两个 ResNet50 DequantizeLinear target stage 的本地 complete strict JSON、
100% leaf provenance、target-bounded handler capability、内部 ADD→MUL composition
boundary、strict/formula/负控，以及与 frozen current final JSON 的逐 leaf 一致性。
它不生成或证明 mapping、bitstream、execplan、SCA/SCA_D、服务器 package/run、
natural terminal、formal D、新 E3/E4/E5 或整网 integrated address/lifetime。
