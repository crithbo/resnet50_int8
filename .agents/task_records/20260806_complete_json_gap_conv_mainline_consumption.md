# Complete-JSON 九族回传：GAP 与 Conv 主线消费

日期：2026-08-06

## 总状态

`FAMILY_RESULTS_CONSUMED_9_OF_9_CLOSED`

公共 driver 身份：

- candidate validator:
  `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f`
- family auditor:
  `baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82`

## GAP / global_average_pool

裁决：`COMPLETE_STRICT_JSON_LOCAL_VALIDATED`，claim 仅为
`CONFIG_ONLY_CORRECTNESS_BASELINE`。

- 2/2 lowering stages、8个physical strict JSON、3754 leaves。
- `UNRESOLVED=0`。
- 两个candidate均：
  `contract_valid=true / pass=true / errors=0 / completion_blockers=0`。
- family-set：expected/covered=`2/2`，pass=true。
- 8/8 candidate encoded config与current v40 byte-equal；execplan byte-equal。
- suspected current config defect=0；new candidate defect=0。
- shared-LC/backpressure、跨时钟终止/可见性、tail运行、48 formal D继续为
  `DYNAMIC_ONLY`。

主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/global_average_pool/report.json`
- SHA256:
  `8193916ecafa8d34bd226d09050e010e2673f66c15506056c58d61ea8a51a01e`

owner记录：

- `.agents/task_records/20260806_global_average_pool_complete_json_regeneration_v1.md`
- SHA256:
  `89e6dba7a5a749ac52a5318cff0c7b3d478576ebaefb162ca3603bc3d4909861`

## ConvInt32Accumulate

裁决：`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`。这是合法能力性
`BLOCKED`，不是结构错误。

- 53/53 stages与20个consumer signature classes精确覆盖。
- strict complete JSON=`0`。
- candidate:
  `contract_valid=true / blocked_valid=true / pass=false / errors=0`。
- `completion_blockers=1851`：
  - unresolved leaf=615；
  - unknown source-absent=615；
  - uncovered handler-dependent leaf=615；
  - unsupported handler axes=6。
- first capability gap：pinned upstream没有generic
  `QLinearConv/ConvInt32Accumulate` handler/registry/materializer。
- current test comparison：615 physical leaves中614 `SAME`、1 route-specific
  intentional derivation；suspected current config defect=0、new candidate defect=0。
- serialized/native动态停点不得归因于本次静态config diff。

主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/conv_int32_accumulate/report.json`
- SHA256:
  `99642520fe9954f785cf36e2acce50f7d434c1a5e33185d9721dab89d848cf7f`

共享candidate报告：

- SHA256:
  `3d166d4c274b19b3fdf66b74cc165c61c9d20927647799dba78f209124e7f390`

共享family报告：

- SHA256:
  `5737fa8f238f3204d453e865a94a98057825f3eb5088267a8014cfd1bc6c5327`

owner记录：

- `.agents/task_records/20260806_conv53_complete_json_regeneration_and_current_test_diff.md`
- SHA256:
  `cc7de5b2f857cb383309fa030c9c1c35ca96ec99c55eb61eeec840c09dcb1c17`

## QLinearAdd

裁决：`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`。这是合法能力性
`BLOCKED`，不是结构错误。

- 17/17 lowering stages、102 planned physical stages、17个materialized-consumer
  signature classes精确覆盖。
- 47123 leaves中1954 resolved、45169 `UNRESOLVED`；strict complete JSON=`0`。
- candidate:
  `contract_valid=true / blocked_valid=true / pass=false / errors=0`。
- `completion_blockers=135598`；handler uncovered=`45169`，composition unresolved=`85/85`。
- v35的GA 4-lane/16B无法形成Buffer5 8-bank/32B行，裁决为
  `CONFIG_EXPLAINS`。
- v36的8-lane/32B静态修正保留；Buffer5 accept、MSE wdata、natural terminal、
  stage-local D及full-chain 28D仍为`DYNAMIC_ONLY`。
- 其余16实例为`CURRENT_ABSENT`，不得继承node0007 project JSON为generic authority。

主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/report.json`
- SHA256:
  `2ae1bf92242cfc70cce12d64d881589492270d05cebdcc1ad0d0393f959daf50`

共享candidate报告：

- SHA256:
  `d8ef7287b3916f47b3bc1637294538798ddecdf0024abc767b3664d495f695c7`

共享family报告：

- SHA256:
  `aab7003efe49d486daee979f0da7fab7944584c5b0f01cff45585e2e8f4e8caf`

owner记录：

- `.agents/task_records/20260806_qlinearadd_complete_json_regeneration_v1.md`
- SHA256:
  `dd00b6bc94a6698635ed99c48418ea7d42ba68e9c4c3c6e97499620e8cca2f2e`

规则反馈：

- `CDA-QADD-COMPLETE-STRICT-COMPOSITE-TYPED-HANDLER-001`登记为待主线裁决；
  本轮未直接修改公共规则。

## View / Flatten

裁决：`COMPLETE`，以`METADATA_ONLY_ALIAS_NO_COMPUTE`覆盖唯一lowering stage；
这不是伪造空硬件配置。

- 1/1 lowering stage、1个materialized-consumer equivalence class。
- hardware JSON count=`0`，没有生成算术/register JSON。
- 161/161 leaves，`UNRESOLVED=0`。
- candidate:
  `contract_valid=true / pass=true / errors=0 / completion_blockers=0`。
- family-set：expected/covered=`1/1`，pass=true。
- current v9没有View config/member；零stage、零copy alias在owner/id、offset=0、
  UINT8 shape与32768B上静态一致。
- runtime accepted ordering、8192 reads/hash、natural terminal及formal D继续为
  dynamic-only。

主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/view_flatten/report.json`
- SHA256:
  `650b9059ce2253231e446cdce5fe70d4c3af0fd20cfd9a2d322c85b2aecb0aac`

no-config contract：

- SHA256:
  `754af068effe0b80e3657b73d94380789e95f0c446cd7da9bdc823eb5bd02f60`

共享candidate报告：

- SHA256:
  `16e0e3410c8b2bebeff3ef5e3366b7963fa26860368bfc65d183625bb71493e2`

共享family报告：

- SHA256:
  `c14221924db90a60c32224f0d9a82958db44e736cc0813e7164e1fac0b55c428`

owner记录：

- `.agents/task_records/20260806_view_flatten_complete_json_regeneration_v1.md`
- SHA256:
  `9bf4d85defc2d200b6bda7fab5b5a74c578d60b1ab36aeb3288c13cc66517da2`

规则反馈：

- 族内规则更新建议已登记；本轮不修改公共规则，且不削弱metadata-only与
  accepted-lifetime门。

## QuantizeLinear

裁决：`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`。

- 2/2 lowering stages与2个consumer equivalence classes精确覆盖。
- target为两个FP32→UINT8实例；pinned native模板只对其INT32 source exact，
  对目标仅可作structure/primitive参考。
- family ledger=`1032`，其中`UNRESOLVED=1016`；materialized target JSON=`0`。
- 两个candidate均：
  `contract_valid=true / blocked_valid=true / pass=false / errors=0 /
  completion_blockers=1043`。
- first divergence=`EXACT_BINARY32_DIVIDE_RNE`；qparam transport、typed mapper、
  shape schedule及address/lifetime也未闭合。
- node0074已批准的DQ→View→Q成对消除保持有效；它只让冻结实例离开通用divider
  执行路径，不关闭generic Quantize能力门。

主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/quantize_linear/report.json`
- SHA256:
  `00fbea90812f0173da7af975d38ecd90327110a1546e9140f8c1f7214ea7dc19`

两份共享candidate报告：

- node0000:
  `a568a4946e5f7cf00674281164c78c9e64331ce5613bece1dee61e18270ec2ce`
- node0074:
  `751697764374ba23d6d77348ad9075ed71158a147f7d30fc74e52aa7c77f5823`

owner记录：

- `.agents/task_records/20260806_quantize_linear_complete_json_regeneration_v1.md`
- SHA256:
  `dad9ccf45c850abb9b5fb60339ac43439868f9c05ace4d638408a7e671feeba3`

## RequantizeUint8

裁决：`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`。

- 54/54 stages、54 exact signatures、17 capability classes精确覆盖。
- target-required unresolved leaves=`944`；strict target JSON materialized=`0`。
- 54/54 candidate均：
  `contract_valid=true / blocked_valid=true / pass=false / errors=0`。
- aggregate `completion_blockers=4046`：
  uncovered handler-dependent=`1888`、unknown source-absent=`890`、
  unresolved leaves=`890`、unsupported axes=`324`、composition=`54`。
- first break：placeholder native handler不能证明target shape；dtype/qparam/layout/
  address/cross-stage schedule继续依赖未支持轴。
- family auditor的54条stage非COMPLETE发现是预期能力阻塞，不是结构、身份或覆盖错误。
- node0001历史card point没有已证明配置归因；动态observer、terminal、formal-D门保持。

主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/requantize_uint8/report.json`
- SHA256:
  `7273bb78fd231a8364e47de3299455cdb9a46d48da2ced43dff19e6339e50a5a`

共享summary：

- SHA256:
  `619cbd569955bbf0a2485817d324813bb557bd8bbdd35b7037d38e61900ee560`

共享family报告：

- SHA256:
  `97044b9ebcfe3cf7e9b35c90a8bef6a617cb216b940dfdc7ca097a6e35bfa7e4`

owner记录：

- `.agents/task_records/20260806_requant_complete_json_regeneration_v1.md`
- SHA256:
  `7a6b16bc7a5937af1f2c446d3ebaf8f2ae08b604021062d36af6b173e2ef7c61`

## MaxPoolUint8

裁决：`COMPLETE / CONFIG_COMPLETE_LOCAL_ONLY`；用户此前的deferred状态不变。

- 1/1 lowering stage、1个equivalence class。
- 461 leaves：
  `REFERENCE_EXACT=458 / ADDRESS_PLANNER_DERIVED=2 / RTL_DERIVED=1 /
  UNRESOLVED=0`。
- candidate:
  `contract_valid=true / pass=true / errors=0 / completion_blockers=0`。
- family-set：expected/covered=`1/1`，pass=true。
- pinned native exact源仅有两项planner base address与padding
  `null→0`差异。
- candidate相对current v5实际消费JSON仅padding一叶不同；
  `SUSPECTED_CURRENT_DEFECT=1`，但现有return不足以证明它导致dynamic stop，
  因而归因为`INSUFFICIENT_EVIDENCE`。
- `B_GA_INT8_MAX_FLOW`继续为`CONFIG_EXCLUDED`，不因本次candidate闭合而改变。

主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/maxpool_uint8/report.json`
- SHA256:
  `28863a00d47cbd99502019b8b3e2e778ecec28897075703ef33e322d16664d8b`

strict candidate：

- SHA256:
  `0348ead26469b8ebda0df03979d38f8436bc9f1f6903bafed078b0547d682335`

共享candidate报告：

- SHA256:
  `87c9632e31517e1a5c646f4f1b8a0ca12788118d63d7447edf12c4dc9e8c6ffc`

共享family报告：

- SHA256:
  `65d75ca53e9fe6ad6d3c1e3125beeb99d63f19b8c3992f9a37231c248c28a342`

owner记录：

- `.agents/task_records/20260806_maxpool_node0002_complete_json_regeneration_v1.md`
- SHA256:
  `6777e7a26bbf012153c38e73b18f2fd05dee4da1ee14c909405e66e3132093c5`

规则反馈：

- legacy MaxPool padding RTL hash receipt刷新与
  `OperatorConfigValidator`的stale `ga_int8_max` numeric fact对齐建议已登记；
  二者均不是candidate leaf错误，本轮未直接改规则。

## DequantizeLinear

裁决：`COMPLETE`。

- 2/2 lowering stages、2个materialized-consumer equivalence classes。
- node0072与node0077各416/416 leaves，合计832/832；
  `UNRESOLVED=0 / SOURCE_ABSENT_UNKNOWN_FOR_TARGET=0`。
- 两个candidate均：
  `contract_valid=true / pass=true / errors=0 / completion_blockers=0`。
- family-set：expected/covered=`2/2`，pass=true。
- pinned native `add_dequant`只对自身composite实例为exact authority；对两个
  standalone target仅为primitive参考。placeholder handler通过target-bounded
  `AUTHORIZED_PATCH`闭合228个dependent leaves，未宣称generic能力。
- node0072的UINT8 qdomain alias与`-0.0→+0.0` normalization保持；
  node0077仍是冻结E4/E5正控，没有重跑E4/E5。
- node0072继续保留native production path、node71→72、node72→73集成绑定及
  formal E4/E5四个动态/生产门。

主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/report.json`
- SHA256:
  `8bb7199fd8c86afccf62601cac67b89af5503cb4426ee83c6f2b3fdc5981cae5`

两份strict candidate：

- node0072:
  `317f263033d5789988ba7d50985bb166c0df7fb35425b51109ca049efb61e390`
- node0077:
  `1235ef420360750b22cba37d72029e555db7c50c069be8ed741ebf747ca23632`

两份共享candidate报告：

- node0072:
  `f0c327b5db1abec8c929856f0a98349787a444e171b0bb242eb62c11d19337b1`
- node0077:
  `887af45fac524e4d627e0b566ad6efd2ad048e08bc2b451353399006aae24942`

共享family报告：

- SHA256:
  `45e48f4f26d30787ffeb1403e57788b9d8500f099482f501c9b71721371f8c26`

owner记录：

- `.agents/task_records/20260806_dequantize_linear_complete_json_regeneration_v1.md`
- SHA256:
  `525ea4f359d56dde5fbacf1809f4ecbc9737dedb5e547e624d3b5ccb218345e3`

## QLinearMatMul / node0075

裁决：candidate=`COMPLETE`；family-set=`COMPLETE`。

- logical stages=`2`：
  `hwop-0075-00 / MatMulInt32Accumulate`与
  `hwop-0075-01 / RequantizeUint8`。
- physical stages=`24`，consumer classes=`6`。
- candidate/ledger=`11568/11568`，`UNRESOLVED=0`。
- composition boundaries=`17 resolved`。
- candidate:
  `contract_valid=true / pass=true / errors=0 / completion_blockers=0`。
- family scope现绑定lowering SHA
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
  及exact IDs `hwop-0075-00/01`。
- public family audit：
  `scope_mode=PINNED_EXACT_STAGE_IDS / expected=covered=2/2 /
  missing=[] / unexpected=[] / errors=[] / pass=true`。
- exact receipts分别绑定
  `MatMulInt32Accumulate/QLinearMatMul`与
  `RequantizeUint8/QLinearMatMul`，没有跨族补齐或绕过。
- current v9逐叶：
  `SAME=11432 / INTENTIONAL_DERIVATION=16 /
  SUSPECTED_CURRENT_DEFECT=120 / NEW_CANDIDATE_DEFECT=0`。
- 120个疑点涉及accum stream1 MSE stride唯一lane、buffer lifetime及inactive
  write mode/keep规范化；它们不解释v5的pre-stage invalid bank-row，但可能影响
  v9进入accumulate后的行为。
- ordering、8192 actual reads/hash、natural terminal、144D继续为dynamic-only。

最终主报告：

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinear_matmul/report.json`
- SHA256:
  `7802ea219c529b4e6393b11699f4a33099dbd1216f681943a84a3f79e69be9a7`

共享candidate报告：

- SHA256:
  `7373ccc930ec9b622949c7b482b29ce847575c3fdc671ca9dcb3104727afc951`

最终family manifest：

- SHA256:
  `a54800f1d115248d96c14a04e54979281f013a83c59184ce86d20865617eab43`

最终共享family报告：

- SHA256:
  `cdcdd8391599a99d35207c4d93b62daa40c758d4c3a4a080537ed863afa2b904`

owner记录：

- `.agents/task_records/20260806_qlinear_matmul_complete_json_regeneration_v1.md`
- SHA256:
  `6f18820cdfccd7226d846b0189d3d7686360782464d2a689dd5e73c04808f9df`

规则反馈：

- `CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001`
  已由真实MatMul反例确证；六类exact scope负控全部fail closed。

## 主线边界

- 不改变GAP v40、QAdd v36、node71→75 v9、serialized Conv v48或native Conv
  p8f的发布身份；不因Quant/Requant能力分析生成新包。
- 不把配置层`COMPLETE`提升为natural terminal、formal D、E3、E4或E5。
- 不把合法`BLOCKED`改写为配置错误、测试失败或RTL bug。
- 本轮没有生成或修改mapping、bitstream、execplan、SCA、服务器ZIP；
  没有上传、运行或获取lease。
