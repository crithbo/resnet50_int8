# ResNet50 INT8 v30 current plan snapshot

> 该文件是主线覆盖更新 `.agents/plan.md` 时使用的逐字节快照；活动状态仍只以
> `.agents/plan.md` 为准。

最后更新：2026-08-03

## 0. 文件职责

- 本文件只保留最新状态和最新短期计划，是可覆盖更新的活动快照。
- 状态变化直接改写本文件，不在末尾追加旧过程；被取代内容移入
  `.agents/history.md`，精确证据保留在 `.agents/task_records/` 与机器报告中。
- 当前唯一主线控制会话：`019fbec2-fe93-7e03-9314-cff6f222f33d`。
- 主线维护本文件与 `.agents/rules/**`；算子 owner 不得修改公共 plan/rules/功能 RTL。
- 冲突时以磁盘 current 规则、原始 package/return、机器报告和 task record 为准。

## 1. 全网当前状态

- ONNX 独立软件公式：`78/78`。
- typed hardware request：`133/133`。
- 正式 E4/E5：`1/78`，仅 DequantizeLinear node0077；该节点冻结。
- 当前没有 `SERVER_RUNNING` lease。
- 除 node0077 外，任何算子都不得宣称正式 E4/E5、production 或性能通过。

| 算子/范围 | 当前状态 | 当前裁决 |
|---|---|---|
| GAP node0071 | `PACKAGE_READY_NOT_RUN / V30_ARM_READY_FACTOR_DIAG` | v29 已证明 Buffer0 accept→prepared write→data_vld 无丢失；停点收窄到 selected-bank readiness 或 NRM read barrier |
| QLinearAdd node0007 | `A_B_C_D_PACKAGE_READY_NOT_RUN / SPLIT_V26` | A 双 dequant、B relocation、C FP32-add 累计前缀、D 六阶段+28D full chain 均已物化，推荐 `B→A→C→D` |
| MaxPool node0002 | `RETURN_CONSUMED / DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE` | 按用户/学长特例停止通用 successor，不重跑、不升级 E4/E5 |
| Conv node0004 serialized | `PACKAGE_READY_NOT_RUN / V30_MSE4_DESCRIPTOR_DIAG` | v29 已关闭 DataHub queue→bank drain 假设；当前停点为 16 prepared group 仅释放 14 个 WR descriptor/data group |
| Conv native four-lane | `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE_NONE` | Trassic d0aa87f 下真实 node0003 `-5+5→0` 仍返回 `0x80000000`；不进入 E2/构包，serialized baseline 不受影响 |
| QuantizeLinear node0074 | `APPROVED_EQUIVALENT / WAIT_NODE0075_POST_RTL_FIX` | node0072→View→node0074 成对消除与 metadata alias 已物化；通用 exact-divider blocker 保持链外开放 |
| DequantizeLinear | node0077 `E4/E5_PASS_FROZEN` | node0072 在冻结链中由 UINT8 storage alias 绕过，不重做算术 |
| View node0073 | `APPROVED_EQUIVALENT_UINT8_ALIAS / METADATA_OVERLAY_MATERIALIZED` | `[16,2048,1,1]→[16,2048]`、零 offset、无 copy/replay/relocate 已闭合 |
| QLinearMatMul node0075 | `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE_NONE` | d0aa87f 下完整 8,192,000 recurrence 仍命中 272 个 negative-psum→exact-zero；未进入 materializer/E2/构包 |

## 2. 当前可运行包

### 2.1 GAP node0071 v30

- 正式 v29 return：
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n71_gap_v29_mse0_buffer_prep_group0_diag_return(1).zip`，
  bytes=`125678`，SHA256=
  `2b990565c41da4984bb1293ccbaf135a0f92ccee955e11653f25c60fd0c1a0bd`。
  `(1)` 仅为下载重名；无相邻 sidecar 只由用户担保替代外部传输收据。
- return 完整性、source/install/run/return identity、runtime-D-absent、argv 与 observer
  binding 全部通过。compile/simulation/runner=`0/125/125`、signal=`INT`、
  natural terminal=false；formal D expected/present/missing=`48/0/48`，
  E3/E4/E5=false。
- `LAST_PROVEN_GOOD`：active sum_s1 内 8/8 MSE0 producer→Buffer0 accept 全到
  prepared write；2/2 ARM accepted read clear；5/5 prepared read 产生 data_vld；
  下游 GA 48/48 与 MSE4 12/12 保持无丢失。
- `FIRST_DIVERGENCE=BUFFER0_ARM_READ_REQUEST_0xFF_HELD_WITH_BUF2ARM_REQ_READY_0_AFTER_TWO_ACCEPTS`。
- 当前根因区间：
  `buf2arm_rreq_ready = &(~buffer_mask | bank_ready) & ~nrm2buf_rd_barrier`；
  现有证据不能唯一化 selected-bank readiness 与 NRM read barrier。
- v29 的 15,597,566 稳定 whole-tag level 累计已裁决为伪进度；v30 用 valid tag bit
  修正，并只观察 ready 合取因子。

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v30_arm_ready_factor_diag.zip
bytes   1,819,468
SHA256  f0606ebeab52391856a7fb939b6f8c6d02984ae8384117d53d906ba1a9c4a931
sidecar SHA256 b5e9cfde7be51995ed67ae5e7538f63a6ddb8c8f02928d4fab7b68cbf69b94a1
class   DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY
status  PACKAGE_READY_NOT_RUN
command bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
return  r5_n71_gap_v30_arm_ready_factor_diag_return.zip
```

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0；audit SHA256=
  `d105f919eb670f7b374f9687cd09fa742e1a908513f26387c3ab97752784ed94`。
- machine report：
  `artifacts/operator_config_validation/r5-gap-node0071-v29-return-to-v30-closure/report.json`，
  SHA256=`9891750ea46fdef880eb687e00cd7bc7720fe74171c31f60a50f66ea129e4d77`。
- task record：
  `.agents/task_records/20260803_gap_node0071_v29_return_and_v30_arm_ready_factor.md`，
  SHA256=`748ebfe2a7fa13ad0ae187305413bc4d1cd2e07954e0d4621e4a023fb134e097`。

### 2.2 serialized Conv node0004 v30

- 正式 v29 return：
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_hw_v29_datahub_drain_diag_return(1).zip`，
  bytes=`99367`，SHA256=
  `80bc305d70106952a15887e9e72b275d8572126d5dd46d17087523c37656d069`。
- return 完整性/source binding/preflight 全部通过；compile/run=`0/0`，simulation
  启动后由诊断预算 `$finish`，不是 DUT natural terminal；formal D=`0/320`，
  E3/E4/E5=false。
- `LAST_PROVEN_GOOD`：MSE4 DataHub local channels 8/9 各把 7 对 address/data
  经 bank crossbar 正式接受并排空。旧 DataHub local queue drain blocker 已关闭。
- `FIRST_DIVERGENCE=MSE4_WR_MEMORY_DESCRIPTOR_TO_WR_DATA_CHANNEL_RELEASE_OF_FINAL_TWO_PREPARED_GROUPS`。
- MSE4 有 16 个 prepared group，但只有 14 个 WR_Data_Channel write 和 14 个
  sink accept；最终 prepared_count=`32`、RD_Buffer_AG queue_count=`2`、full=`1`。
  尚不能区分 AG 少发最后 descriptor、FIFO 丢失/提前 pop，或 descriptor 存在但
  prepared/output-buffer eligibility 阻断，不宣称 RTL defect。

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v30_mse4_descriptor_diag.zip
bytes   5,837,621
SHA256  0c358f254cac4128a7a320a4201a50f266f1620105fd9b859cf26ac84aa6ad81
sidecar SHA256 d90fac09cf883995082c4187b7d657b3be0f376b13f1e300ec13054f7b1ad8a9
class   DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY
status  PACKAGE_READY_NOT_RUN
command bash r5_n4_hw_v30_mse4_descriptor_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
return  r5_n4_hw_v30_mse4_descriptor_diag_return.zip
```

- v30 只增加 descriptor FIFO 与 prepared-data release qualified 握手诊断；
  workload/config/golden/timeout/backpressure/functional RTL 冻结。
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0；audit SHA256=
  `2779b6313a1f11621cc20a008d8e6336fd46e0ca6bddd6ff46ec12633156e82b`。
- return report：`outputs/conv_node0004_v29_return_analysis/report.json`，
  SHA256=`9adb19b9a64684aa3741f45c879c3e0fbb4a47fdf3b032ba1117362807a19826`。
- successor release SHA256=
  `6c407bae73c7c864c158b3dee81901cb18276afd915534878d8e584306921f72`。
- task record：
  `.agents/task_records/20260803_conv_node0004_v29_return_v30_mse4_descriptor_successor.md`，
  SHA256=`cf84f408b46ac795cb356150aa5a57fd14518c519e746fd71d35e95591c47ce7`。

### 2.3 QLinearAdd node0007 split v26

- v24 B-control 已自然完成；旧 v20 停点归因 package-local observer，不是 B 配置/
  功能 RTL。fresh v26 是真实 workload 拆分，不是只拆 observer。

| 顺序 | 段 | ZIP | bytes | SHA256 | expected return |
|---:|---|---|---:|---|---|
| 1 | B relocation | `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_b_reloc_v26.zip` | 158248 | `fb3f248bf4031db9f9d7d8168149ece1a80dbeda50843c8bb20834ab3fc58f05` | `r5_qadd_n7_split_b_reloc_v26_return.zip` |
| 2 | A dual dequant | `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_a_dequants_v26.zip` | 26024463 | `d9fa3eb8d94ec83382c5be79150a9ea0d9a04903227405d243edb82dcb5e3978` | `r5_qadd_n7_split_a_dequants_v26_return.zip` |
| 3 | C FP32 prefix | `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_c_fp32_prefix_v26.zip` | 26156775 | `e4c16585707b37170d04311f91c038c37b3c95330ffceed17a23687d913f5d50` | `r5_qadd_n7_split_c_fp32_prefix_v26_return.zip` |
| 4 | D full+28D | `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_d_full_v26.zip` | 38027184 | `b73b13b95f01ea95919cd2eae29415dd04e8a1fff7bc67307099b4c67871d49c` | `r5_qadd_n7_split_d_full_v26_return.zip` |

- 统一命令：`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`。
- 四包双构建、final-ZIP self-audit、HDL/runner/EXIT/TERM/feature/output 正负控均闭合。
- machine report：
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-v26-release/report.json`，
  SHA256=`04b8e736aae54e0c7372d8d39b4e94aa03ba283babfb75c25b533273a7f47c44`。
- task record：
  `.agents/task_records/20260803_qlinearadd_node0007_v24_return_split_v26_release.md`，
  SHA256=`733ab584bb8c42b19ee6a547be2e72f7e5bbeaed888a6ffb6e4583d62b16ef75`。

## 3. 当前 active RTL 与硬件能力门

### 3.1 Trassic source identity

- 权威私有仓库：`xlsjdjdk/Trassic2.0_RTL`，branch=`master`。
- current commit=`d0aa87f682880a260fb792aaac88f70a23aba414`；
  功能提交=`cb11353d4196b4af26aac18b4dcc39ba0027e8bc`。
- GitHub compare 相对旧 `8f2f3181` 只有两个 changed files。同步前三方检查无冲突，
  同步后活动本地文件与新上游成员逐字节相同：

```text
SA_PE_Float_CSA.v
429a29a929a508f7562f9c78d4ab2cd4095961296d0e6f65e8419a4444a6145a

SA_PE_Float_Control.v
00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb
```

- sync report：
  `artifacts/rtl_sync/trassic_master_d0aa87f_20260803/report.json`，
  SHA256=`fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771`。
- task record：
  `.agents/task_records/20260803_trassic_master_d0aa87f_active_rtl_sync.md`，
  SHA256=`9ecce80032be2d9573512928d806fecdbdb31caf7344b516ae88c7762b8409d6`。

### 3.2 d0aa87f 功能复验裁决

- 上游变化真实存在：Control 对负 INT32 使用完整 32-bit magnitude；CSA 启用
  `Int_Res_Sign = c_Result0_wire[31] XOR i_SignC` 并驱动结果 sign bit。
- 但精确抵消时 `c_Result0_wire=0`、旧 psum `i_SignC=1`，上述 XOR 仍输出 sign=1，
  低 31 位为 0，最终仍形成 `0x80000000`，不是数学 0。
- node0075 fresh 全 recurrence：
  planned/enumerated=`8,192,000/8,192,000`、negative psum=`4,343,952`、
  negative→exact-zero=`272`；首例 `-19+19` 仍错。
- node0075 状态：
  `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE`；实际 A reload
  pass/read/traffic=`0/0/0B`。用户授权的最少 8-pass 仍只是修复后的反事实预算。
- node0075 task record：
  `.agents/task_records/20260803_node0075_negative_psum_d0aa87f_revalidation_blocker.md`，
  SHA256=`aa7193ae031014b13bcf0899a56d9bc66c18911e57a6292d6e903a2e4e02f03a`。
- Conv native-four-lane 只重跑真实 `hwop-0003-00` 必要门，未重跑 53-Conv；
  `-5+5→0` 仍得到 `0x80000000`。状态：
  `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE`；未进入 E2/构包。
- Conv native machine report：
  `outputs/conv_native_four_lane_d0aa87f_revalidation/report.json`，
  SHA256=`3020f79c46338c8148c8d86f3e481e92fe368f64d703b775cf27090d46634081`。
- Conv native task record：
  `.agents/task_records/20260803_conv_native_four_lane_d0aa87f_independent_revalidation_blocker.md`，
  SHA256=`f05c10e557d3f041a4a4ee7a817eb7350df0f6467ac35ca38fabf7528efac10c`。
- 两支均确证 current INT8-SA/current-identity/fail-fast 规则充分；无规则增量。

## 4. 最新短期计划

1. 当前可运行包只有 GAP v30、serialized Conv v30、QAdd split v26 A/B/C/D；
   当前无 `SERVER_RUNNING` lease。GAP v29、Conv v29 及所有更早身份禁止重跑。
2. GAP v30 只区分 selected-bank readiness 与 NRM read barrier，不复活已关闭的
   Buffer→prepared/data_vld 或 GA→MSE4 blocker。
3. serialized Conv v30 只区分 WR_Memory_AG descriptor 产生、descriptor FIFO
   push/pop 与 prepared/output-buffer eligibility；继续独立验证 DUT natural terminal
   与 320/320 formal D，不复活旧 occupancy 或 DataHub drain 误判。
4. QAdd split v26 按 `B→A→C→D` 运行；A/B/C 只提供局部/前缀证据，不能替代 D
   的端到端六阶段+28D 联合门。
5. MaxPool 保持用户特例 `DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE`，不重跑、不恢复
   通用诊断，也不把复用 authority 冒充本轮 E4/E5。
6. node0075 与 Conv native-four-lane 在 d0aa87f 下仍被同一 exact-cancellation
   negative-zero 叶阻断。未经新的硬件修复和 current-identity 定向回归通过，不得恢复
   materializer/E2/构包；serialized Conv 正确性路线继续独立推进。
7. serialized Conv 继续作为 correctness-first 非优化基线：约 4× occurrence、
   useful-lane utilization 最多 25%。先用 v30 关闭 node0004 descriptor→WR data
   边界与 320 D；代表节点闭合前不扩展其余 52 个 Conv。
8. 每个 owner 完成 RETURN→successor 或本地 package 后必须主动通知当前主线并提交
   `RULE_CONFIRMATION` 或非同义 `RULE_DELTA_PROPOSAL`。分支不得修改公共规则/plan。
9. 服务器运行期间不要求主线持续盯守。同一物理服务器根目录禁止并发；只执行包内唯一
   `PREPARE_AND_RUN.sh`，只接受 runner 正式 return。

## 5. 当前开放 blocker

- `B_GAP_NODE0071_BUFFER0_ARM_READ_READY_CONJUNCTION_PENDING_BANK_READY_OR_NRM_BARRIER_LEAF`
- `B_CONV_NODE0004_MSE4_DESCRIPTOR_TO_WR_DATA_FINAL_TWO_GROUPS_UNOBSERVED`
- `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`
- `B_CONV_NODE0004_FORMAL_D_320`
- `B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE`
- `B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING`
- `SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION`
- `B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE`
- `B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING`
- `B_QUANT_TAIL_SIGNED_INT32_INGRESS`
- `B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING`
- `B_QADD_V24_B_ONLY_FULL_CHAIN_RESULT_GATE_SCOPE_MISMATCH`
- `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`
- `B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN`
- `B_QUANT_NODE0074_EXACT_DIVISION`
- `B_QUANT_TAIL_EXACT_FP32_DIVISION`
- `B_GA_INT8_MAX_NUMERIC` / `B_GA_INT8_MAX_FLOW` / `B_MAXPOOL_SERVER_E4_E5`
- shared allocator/execplan/coverage/lifetime
- 最终 133-stage integration assembly 与逐层三方比较

## 6. 当前关键规则收据

| 文件 | SHA256 |
|---|---|
| `.agents/agent.md` | `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721` |
| `.agents/rules/生成前必读索引.md` | `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5` |
| `.agents/rules/服务器测试包生成规则.md` | `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48` |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| `.agents/rules/QLinearAdd算子配置规则.md` | `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f` |
| `.agents/rules/INT8_SA点积专项规则.md` | `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce` |
| `.agents/rules/GAP_int32_mac_bypass_rules.md` | `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b` |
| `.agents/rules/GAP_probe_v7_validator_rules.md` | `db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |

以上 SHA 只是 current receipt。任何新生成、封包或 return 裁决前，仍须完整读取磁盘
current 文件并重算身份。
