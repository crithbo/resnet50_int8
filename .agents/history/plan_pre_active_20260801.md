# ResNet50 INT8 当前执行计划（归档于 2026-08-01）

最后更新：2026-08-01

本文件只保留当前状态、开放阻塞和下一步。逐版本过程、已隔离包、旧命令与被取代结论见
`.agents/history/plan_pre_current_compaction_20260731.md`、`.agents/history.md` 和
`.agents/task_records/`。稳定职责看 `.agents/agent.md`，生成与验收规则只看
`.agents/rules/`。

## 1. 当前目标与证据边界

最终目标是同一冻结 ResNet50 输入在以下三侧逐层一致：

```text
ONNX/W3 golden ↔ config-bound simulator ↔ stock-RTL hardware
```

当前事实：

- ONNX 独立软件公式：78/78。
- typed hardware request：133/133。
- 正式完成三方闭环：1/78，仅 DequantizeLinear node0077；已经 E4 首次通过和 E5
  独立重复通过，不再生成或运行该节点测试包。
- Dequant node0072、GAP node0071、QLinearAdd node0007、Conv node0004 已有本地
  config-bound E2 或等价本地正确性基线；这不等于动态硬件通过。
- 当前 Conv 与 QAdd 是已修复确定配置/物化错误的
  `CONFIG_*_FIX / PACKAGE_READY_NOT_RUN`；GAP 是
  `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / PACKAGE_READY_NOT_RUN`。三者都仍不得称
  E4/E5、production 或性能通过。
- 功能 RTL 默认冻结；没有用户本轮明确授权不得修改 `rtl/**`。

## 2. 当前三条服务器测试主线

### 2.1 Conv/SA node0004

当前动态结论：

- v19 已确认真实卡死；compile/run wrapper 成功，但不是 DUT natural terminal，
  formal D=0，E4/E5=false。
- 已确定根因是配置语义错误：
  `BUFFER0_1_MODE0_ADVANCES_ROW_BEFORE_LIFETIME`。
- v19 的 Buffer0/1 `mode=0` 让 ARM 在首次读 row0 后立即请求未写入的 row1；
  服务器证据为 AG 两次入队/出队、Buffer0 两次写入、一次 ARM read，随后
  `addr=1`、row1 invalid、row0 仍全 valid、`ready=0`。
- 最小修复仅把 Buffer0/1 两个 `mode` leaf 从0改为1，使 lifetime 成为内层计数，
  当前 row 完成4次复用后才换行；功能 RTL 未修改。

唯一可运行包：

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v20_buffer_mode_fix.zip`
- bytes：5,819,495
- SHA256：`e67775aed87d2065f51190049a9a7ba05fb98de9ba08a4362901612248f92ead`
- sidecar file SHA256：`6c2db91207f1638c8192ae0d9aa9fe6b67926a6957d4683b17d052ae848615e9`
- classification：`CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`。
- 84个冻结 A/B/C matrix payload 未变；只从两 leaf 修复后的配置重建 mapping、
  bitstream、execplan 和 SCA。
- 运行：`bash r5_n4_hw_v20_buffer_mode_fix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- 预期回传：`r5_n4_hw_v20_buffer_mode_fix_return.zip`；用户默认无需传回 `.sha256`。

### 2.2 QLinearAdd node0007

当前动态结论：

- v13 已确认约55.8分钟真实卡死；observer clock持续前进，但30个采样窗内
  LC/MSE/AG/request qualified事务全为0，formal D=0/28，E3/E4/E5=false。
- 已确定根因是 SCA 物化遗漏：六段 config bitstream 文件与六条 `Load_Config`
  都存在，地址/长度也正确，但 `sca_cfg.json` 没有六条对应的 config preload，
  因而物理 LC enable 始终为0。
- v14 仅新增六条 SCA config preload；冻结 JSON/mapping/bitstream bytes/execplan/
  SCA_D/tensor/golden/W3/六qparam均不变，功能 RTL 未修改。

唯一可运行包：

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_cfgpreload_v14.zip`
- bytes：38,033,509
- SHA256：`78f1aa16b2853173c5b263acb2f1a3b42516a08cc7bb2fd5342f3fd55b918282`
- sidecar file SHA256：`c0903628ebaff73892dc6678041834f401f6b0365e7aa20e0f786614fea87f07`
- claim：`CONFIG_ONLY_CORRECTNESS_BASELINE`。
- 运行：`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- 预期回传：`r5_qadd_n7_cfgpreload_v14_return.zip`；用户默认无需传回 `.sha256`。

### 2.3 QLinearGlobalAveragePool node0071

当前动态结论：

- v12 compile成功后被人工 INT，中断前功能 qualified progress 已平坦
  20,447,232 cycles；48项 formal D 全缺，E3/E4/E5=false。
- 正式证据证明 MSE3→Buffer4 与 MSE0→Buffer0 各 accepted 1次，随后
  `ga_operand0_capture=0`、`ga_operand2_capture=0`、`ga_joint_accept=0`。
- 本地穷尽审计仍未找到确定配置、package 或 RTL 错误；当前唯一必要缺口是
  `Buffer0/4 ARM read accept → GA group0/2 ingress accept → PE operand tag visibility`。
- v13 只增加该窄边界的只读 qualified counters/snapshot；73个冻结 numeric 文件、
  workload/config/golden 与功能 RTL 均不变。

唯一可运行包：

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v13_buffer_to_ga_diag.zip`
- bytes：1,796,539
- SHA256：`88715902dd818b488990521bcdfa9d9be24f3195e0371c9c25a664a17fc76131`
- sidecar file SHA256：`edd5766863f4cfc156a36ca4714693c66ae681ee7afaa190696c5be48ff9b387`
- classification：`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`。
- 运行：`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- 预期回传：`r5_n71_gap_v13_buffer_to_ga_diag_return.zip`；用户默认无需传回 `.sha256`。

## 3. 其他算子族当前状态

| 算子族 | 当前状态 | 下一条件 |
|---|---|---|
| Dequant node0077 | E4/E5 与 config-bound simulator 已逐 bit 闭合 | 冻结，不再测试 |
| Dequant node0072 | standalone local E2 与 producer storage/base/coverage 已完成 | 等 shared allocator、visibility、lifetime 与 consumer binding |
| Flatten/View node0073 | metadata-only zero-copy owner section 已完成 | 等 node0074 consumer endpoint 与共享生命周期 |
| Quantize node0074 | 无 direct/equivalent exact binary32 division entry；consumer六字段为 null | exact division 能力闭合前不生成 target/package |
| RequantizeUint8 | 53 stage signature binding 已完成；53 multiplier payload 均唯一 | 其余实例需 fresh multiplier/address/lifetime materialization |
| Conv 其余52项 | 22个 schedule signatures 已冻结；stem accumulate local E2完成 | node0004 有效动态基线后再批量物化/封包 |
| MaxPool | 旧物化资产不再作为正证据；当前无活动服务器包 | 等整网首分歧或新的正式 return |
| 整网 endpoint | Dequant/Flatten/Quantize 三 owner section 已齐但未闭合 | exact division、consumer coverage、shared allocator/execplan/lifetime |

## 4. 当前执行顺序

1. 同一物理服务器根不得并发。
2. Group-B 顺序：先运行 Conv v20；正式回传分析完成后，再运行 QAdd v14。
3. GAP v13 只有在另一份干净、独立服务器根上才可并行。
4. 每次只执行包内唯一 `PREPARE_AND_RUN.sh`；只回传 runner 生成的正式 return ZIP。
   runner 可在服务器本地生成并自检 sidecar，但用户默认无需传回。禁止手工压缩
   run/install/evidence 树代替正式 return。
5. return 到达主线后只负责分发，必须由原算子族任务完成分析：
   - Conv/SA：`019fa2c1-17df-7122-bcbd-a727aaf173f5`
   - QLinearAdd：`019fa2c0-b647-7a91-93bf-d21a173487e3`
   - GAP：`019fa366-cb1f-7ae2-880c-f527be0680cd`
6. 超时或人工中断默认按长时间卡死审计；先本地穷尽配置语义和 RTL 方程，只有现有
   return 确实缺少一条必要边界时才生成下一只窄诊断包。

## 5. 当前生成与服务器硬门

- 复用已接受的 numeric/W3/workload；不得因包版本变化重复数值分析。
- 最终源测试包 ZIP 形成后必须重读 current 索引、公共服务器规则和本族专项规则，并直接对
  最终源测试包 ZIP/sidecar 执行独立自检。
- `PACKAGE_READY_NOT_RUN` 的必要条件：
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0、真实 runner 到安全 compile stub
  正控通过、全部要求负控 fail closed。
- 本地严格检查包自身的语法、identity、namespace、SCA/SCA_D、runtime-D absent、
  observer 四向绑定、canonical decision、return allowlist 和联合门。
- 普通服务器 runner 只做最小预检，不枚举或哈希用户服务器已有 RTL/TB/Makefile/
  filelist/Git/README；真实环境不兼容由 compile/run 自然返回。
- 用户已明确保证回传文件不会被调换；缺少相邻 return sidecar 不再单独构成 blocker。
  分析端仍须重算 ZIP SHA，并验证 CRC、内部 identity、RETURN_MANIFEST/allowlist/exact-set、
  源包绑定及动态联合门。
- observer/progress 默认低开销、只读、限流；level 只作状态，事务进度只能来自
  qualified handshake/edge。
- 规则内容中性漂移可用包外 receipt 复验；若新规则要求改变包字节、runner、manifest、
  return schema 或负控，旧包必须隔离并使用 fresh identity。

当前关键规则收据：

| 文件 | SHA256 |
|---|---|
| `.agents/rules/生成前必读索引.md` | `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f` |
| `.agents/rules/服务器测试包生成规则.md` | `88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6` |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| `.agents/rules/INT8_SA点积专项规则.md` | `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce` |
| `.agents/rules/QLinearAdd算子配置规则.md` | `c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b` |

规则 SHA 只作本次 current receipt；每次新生成前仍必须读取磁盘实际值。

## 6. 当前开放阻塞

- `B_NODE0004_V20_DYNAMIC_RETURN_PENDING`
- `QADD_NODE0007_V14_SERVER_DYNAMIC_RESULT_PENDING`
- `B_GAP_NODE0071_BUFFER0_4_ARM_READ_TO_GA_GROUP0_2_INGRESS_TO_PE_TAG`
- `B_QUANT_NODE0074_EXACT_DIVISION`
- `B_QUANT_NODE0074_CONSUMER_ENDPOINT_BINDING`
- shared multi-operator allocator/execplan/coverage/lifetime
- 其余 Conv fresh physical binding 与动态门
- 最终整网 133-stage integration assembly 与逐层三方比较

除 Dequant node0077 外，当前任何算子都不得升级为正式 E4/E5 或 production。
