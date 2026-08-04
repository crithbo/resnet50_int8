# ResNet50 INT8 当前执行计划（GAP v17 前历史快照）

最后更新：2026-08-01

本文件只保留当前状态、唯一可运行包、开放阻塞和下一步。旧版本过程、隔离包与被取代
结论见 `.agents/history/`、`.agents/history.md` 和 `.agents/task_records/`。

## 1. 当前目标与证据边界

目标是同一冻结 ResNet50 输入在三侧逐层一致：

```text
ONNX/W3 golden ↔ config-bound simulator ↔ stock-RTL hardware
```

- ONNX 独立软件公式：78/78。
- typed hardware request：133/133。
- 正式 E4/E5 闭环：1/78，仅 DequantizeLinear node0077；该节点冻结，不再测试。
- Conv node0004、QLinearAdd node0007、GAP node0071 均已有本地 E2 或等价基线，但最新
  server return 都未自然完成，formal D 全缺，不能称 E4/E5、production 或性能通过。
- 功能 RTL 默认冻结；当前三个后继均未修改 `rtl/**`。

## 2. 三条活动服务器主线

### 2.1 Conv/SA node0004

- v22 的 Buffer mode、ROW keep 与三个诊断 feature 均真实生效；compile/run wrapper=0，
  但 DUT 未自然终止，formal D=0/320，E3/E4/E5=false。
- 上游已到 `A/B/C group accept=16/16/8`、`alu_accept=2048`、
  `alu2ob_cycles=32`；随后 PE output、SA group output、Buffer5 write 全为0并连续4窗
  零进展。
- 确定功能 RTL 根因：
  `SA_PE_Outbuffer.sv` 的 RAM 已接受 ALU result，但 occupancy counter 只统计 initial
  C/psum 的四槽写入，漏记 ALU 单槽写入；bias/DataC 关闭时 count 永远为0，输出端
  永远自认 empty。
- 最小硬件修复必须逐 physical pingpong group 按
  `delta = 4*initial_accept + 1*alu_accept - 1*output_read_accept` 做足宽有符号更新。
  不能把两种 write enable 简单 OR：initial 写入是 `+4`，ALU 写入是 `+1`，且可能与
  read 同周期或落入不同 group。
- 当前 `PACKAGE_RELEASE=NONE`、`STATE=WAIT_RTL_FIX`。冻结 v22 workload/config/
  bitstream/execplan/SCA/golden；硬件组修复后先做定向 RTL 验证，再在 repaired RTL 上
  重跑同一冻结 workload。未经修复不得继续运行 v22，也不得生成新的诊断包。

### 2.2 QLinearAdd node0007

- v16 已真实越过 D-buffer 供给修复路径：MSE0 read/consume、GA input/output 均有64条
  qualified 记录，MSE4 两通道各有至少64次 request/write-data accept。
- 本次人工 INT 时 simulation wall=4241.413s；slice-start 后仅推进261501.9 cycles，
  距首个262144-cycle heartbeat尚差642.1 cycles。finite deep trace已经封顶，因而中断前
  后续是否仍进展不可见。
- 正确裁决为
  `MANUAL_INTERRUPT_BEFORE_FIRST_HEARTBEAT_WITH_QUALIFIED_PROGRESS`：不通过动态门，
  也没有证据建立新配置/RTL卡死根因。
- natural terminal=false，formal D=0/28，E3/E4/E5=false。最后一次有效输出侧事务为
  `MSE4 req/wdata ch0/ch1=64/64`（16128787000 ps）；最后一次有效输入侧事务为
  `MSE0→Buffer0 n=64`（16129301000 ps）。其后到INT前约260655 cycles缺少摘要，
  不能据此判卡死或仍在前进。
- v17仅把后端observer heartbeat从262144降到32768 cycles（按v16实测速率约8.9分钟
  一条），继续返回累计qualified握手、MSE4 outstanding、阶段完成和first-request链；
  不增加前端逐事务日志，不改timeout/config/workload/golden/RTL。

唯一可运行包：

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_backend_progress_v17.zip
bytes   38,036,723
SHA256  524325a3dd78aa7e7f699f3b23809cc9f1f432698ab671db30640e031b64b462
class   CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS
status  PACKAGE_READY_NOT_RUN
```

运行与回传：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

```text
r5_qadd_n7_backend_progress_v17_return.zip
```

### 2.3 QLinearGlobalAveragePool node0071

- v15 的 Buffer→GA feature 已真实启用，MSE0→Buffer0 与 MSE3→Buffer4 各accept一次，
  之后没有完整Buffer row、ARM read或GA ingress。
- 本地配置语义与RTL方程确认确定根因：
  `STAGE1_8B_READ_REPEATS_BUFFER_BYTE_LANE_ZERO`。旧GROUP0/GROUP1 COL序列
  `0,4,8,...`低2位恒0；8B transaction因此反复写每个bank的byte lane0，而Buffer
  array-ready要求每个启用bank的四个byte-valid位全1。
- typed materializer现令两组COL产生`0,1,2,3`，准确改四叶：
  GROUP0/GROUP1 `end 32→4`、`stride 4→1`。完整config→mapping→bitstream→集成重建
  通过；仅stage1 bitstream改变，stages2-6、tail、execplan、W3、golden、observer和
  功能RTL保持冻结。
- 新规则 `CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001` 已写入GAP专项规则；
  v16最终ZIP自检PASS=true/errors=0。

唯一可运行包：

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v16_stage1_byte_slots.zip
bytes   1,798,391
SHA256  85ee11406a8f7b67d67d7fd3e82705c3c48c12b01e2a155496cbf7b05679cee5
class   CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS
status  PACKAGE_READY_NOT_RUN
```

运行与回传：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

```text
r5_n71_gap_v16_stage1_byte_slots_return.zip
```

## 3. 当前执行顺序

1. 同一物理服务器根禁止并发。
2. Conv 当前等待功能 RTL 修复，不占用运行位；Group-B在fresh root运行QAdd v17。
3. GAP v16 可在另一份干净、独立服务器根上并行；否则排在QAdd之后。
4. 每次只执行包内唯一 `PREPARE_AND_RUN.sh`，只回传 runner 生成的正式 return ZIP。
   用户已保证传输不调换，默认无需上传相邻 `.sha256`；禁止手工压缩
   run/install/evidence 树替代正式 return。
5. return 到达主线后分发给原算子族任务：
   - Conv/SA：`019fa2c1-17df-7122-bcbd-a727aaf173f5`
   - QLinearAdd：`019fa2c0-b647-7a91-93bf-d21a173487e3`
   - GAP：`019fa366-cb1f-7ae2-880c-f527be0680cd`

## 4. 当前生成与验收硬门

- 复用已接受的 numeric/W3/workload，不因包版本变化重复数值分析。
- final ZIP 形成后重新读取 current 索引、公共服务器规则和本族专项规则。
- `PACKAGE_READY_NOT_RUN` 必须同时满足：
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0、真实 runner→安全 compile stub 正控
  通过、全部要求负控 fail closed。
- 本地检查包自身的语法、identity、namespace、SCA/SCA_D、runtime-D absent、observer
  四向绑定、逐 feature enable/limit/time0/receipt/return target、canonical decision、
  return allowlist 与联合门。
- 普通服务器 runner 只做最小包内预检，不枚举或哈希用户服务器已有
  RTL/TB/Makefile/filelist/Git/README。
- 缺少 return sidecar 不再单独构成 blocker；分析端仍须重算 ZIP SHA，并验证 CRC、
  内部 identity、RETURN_MANIFEST/allowlist/exact-set、源包绑定及动态联合门。
- 超时或人工中断默认按长时间卡死审计；先穷尽本地配置语义与 RTL 方程，只有现有
  return 缺唯一必要边界时才生成窄诊断包。

## 5. 当前开放阻塞

- `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`
- `QADD_NODE0007_V17_BACKEND_PROGRESS_RETURN_PENDING`
- `B_GAP_NODE0071_V16_SERVER_DYNAMIC_RESULT_PENDING`
- `B_QUANT_NODE0074_EXACT_DIVISION`
- `B_QUANT_NODE0074_CONSUMER_ENDPOINT_BINDING`
- shared multi-operator allocator/execplan/coverage/lifetime
- 其余 Conv fresh physical binding 与动态门
- 最终133-stage integration assembly 与逐层三方比较

除 Dequant node0077 外，当前任何算子都不得升级为正式 E4/E5 或 production。

## 6. 当前关键规则收据

| 文件 | SHA256 |
|---|---|
| `.agents/rules/生成前必读索引.md` | `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f` |
| `.agents/rules/服务器测试包生成规则.md` | `fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025` |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| `.agents/rules/INT8_SA点积专项规则.md` | `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce` |
| `.agents/rules/QLinearAdd算子配置规则.md` | `a1faa3319c267b6d6b7f3e9d2b74c45a52b9a347888dc42de0dfb8599ced5964` |
| `.agents/rules/GAP_int32_mac_bypass_rules.md` | `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b` |

规则 SHA 只作本次 current receipt；每次新生成前仍须读取磁盘实际值。
