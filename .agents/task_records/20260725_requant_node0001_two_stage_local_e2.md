# RequantizeUint8 node0001 精确两阶段本地 E2

日期：2026-07-25

## 结论

`r5:hwop-0001-01` 已完成以下本地垂直链路：

```text
不可变 typed request
→ 专项数值/布局合同
→ 9 类 strict JSON + RequantGuard SFU payload
→ 24 occurrence / 48 stage typed graph
→ native planner / mapper / encoder / bitstream / execplan / SCA
→ 最终 JSON、码流、生命周期反解
→ 完整 W3 独立数值回放
→ backend 10 文件配置集物化
→ stage system / local closure / project closure
```

状态为 `LOCAL_E2_COMPLETE_DYNAMIC_PENDING`。`candidate_release=false`，
`formal_target_instance_allowed=false`，`dynamic_baseline=NO_DYNAMIC_BASELINE`。
唯一未关闭项为 `B_REQUANT_SERVER_E4_E5`；不得称为硬件动态闭环、正式
target config 或全体 54 个 Requant stage 的通用放行。

本轮未生成服务器包，未修改任何 `rtl/` 目录内文件。RTL 方程探针只新增在
`tests/rtl/ga_sfu_affine_identity_tb.sv`。

## 生成前读取与身份

生成收据：
`artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/generation_receipt.json`
（文件 SHA-256
`5993ccba612d8566ba470a66930263c8e5d26307955a22200cef82399f1a6cce`）。

专项规则：
`.agents/rules/RequantizeUint8算子配置规则.md`
原始 node0001 生成收据绑定的规则 SHA-256 为
`da99703ae7506c17cb9252bbb85606ec2b93df3781885fd7a009b71aae3ad133`。
后续全族只读分类与 alias-aware 动态门是增量规则，不改变这份冻结 E2 的 JSON、地址或
码流身份；当前规则 SHA 见全族分类读取收据。未来若重新物化 node0001，必须按当前规则
刷新读取收据并使用全新产物身份，不得覆盖本记录。

已绑定公共索引、公共算子规则、NDP LC/MSE/Buffer/GA 字段语义、专项规则、
原生 quant/SFU JSON、实际 ndp-sim consumer 与相关 RTL。typed request 固定为
`r5:hwop-0001-01`，request SHA-256 为
`d1521e88b864c0027fd104b314cc97f67abf10ef0429456a6a35aa57ce22be9e`。

## 数值闭环

- 输入 accumulator shape：`[16,64,112,112]`，共 `12,845,056` 个 int32；
- 负数 `3,246,544` 个，其中 `-1` 为 `80` 个；零为 `112` 个；
- 64 个 multiplier 均为有限正数，输出 zero-point 为 0；
- stage0 先通过 SFU 执行 `max(fp32_convert(acc), +0)`，负转换器异常值只能命中
  slope/intercept 均为 0 的 LUT 区间；
- stage1 逐 channel multiplier，使用 `0x4b400000` round magic、减回并
  `int32touint8` 饱和；
- guard bit mismatch=0，正数转换 mismatch=0，最终 uint8 mismatch=0；
- replay 与 golden payload SHA-256 均为
  `d60d9524c0aa95e634274f95a7d0e51ccf649e5705cf875c57d84f246c749606`。

`RequantGuard.txt` 为 65 个零 breakpoint、66 个零 intercept、66 个 slope
（仅 slope65=1）和 3 个 padding word，共 50×128 bit；payload SHA-256：
`19bfa9a258d3199d5280f3829e3a54dd7d06c4d95294f5b419246e5eb8eebf57`。

## 物化与生命周期

- 3 wave×8 channel shard，共 24 个 occurrence；
- 每个 occurrence 包含 guard 与 round/saturate 两级，共 48 个 stage；
- 所有 48 份最终 materialized JSON strict-valid；
- 所有 48 份最终 bitstream 均已反解 GA opcode、conversion flag、in/outport
  block 与 raw-bit mirror；
- 24 条 producer D 与 consumer A 地址及 slice mask 完全一致；
- consumer intermediate 的最终 SCA preload 数为 0；从原生 SCA 中精确移除
  128 个 producer-backed A key，防止覆盖硬件中间结果；
- 48 个 `Start_Comp` 均有同 mask completion fence，`Repeat_Num=48`；
- 24 次相同固定 SFU payload load 在最终 execplan 中只保留一次，且是在首个
  `Start_Comp` 前；
- 两份独立空 cache 工具副本的 486 个非可视化确定性文件逐字节一致；
- 活动 `ndp-sim` 与 `NDP_copy01/rtl` 的 pre/post tree identity 未变化。

## 发现并关闭的本地反例

原生无释放 allocator 会把最终 JSON 放到 row 6174，超过 W4 每 bank 6144 行上限；
validator 正确 fail-closed。最终采用精确 W4 生命周期：

- 每个物理 slice 最多持有 3 wave×2 local shard slot 的外部 A/最终 D；
- guard intermediate 只在同一 occurrence 内存活，在 completion barrier 后复用
  bank1 的单一区域；
- config 放 bank3；
- 所有地址逐 slice 反解并满足 row `<6144`。

这不是放宽地址门，而是把 buffer demand、supply、lifetime 与 barrier 证明写入
planner 输入后重新完整生成。

## 主要产物

- 本地 E2 报告：
  `artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/local_e2_report.json`
  （文件 SHA-256
  `29b24ba2c0ca48348adb7e2c2b7a05508324474f506f0cabcadc1ded4f121990`）；
- 总 artifact manifest：
  `artifacts/operator_config_validation/r5-requant-node0001-two-stage-e2-v1/manifest.json`
  （SHA-256
  `636491b767d17020f54443864dd3dc427a640a917f90010ac4db3cd3889c327f`）；
- 静态配置集：
  `configs/native_ndp_sim/node0001_requant_two_stage_v1/manifest.json`
  （SHA-256
  `5a51a63464936240ed48bc23b1182e4be754adefbdac505c0f6e255917e6aad3`）；
- 机器合同：
  `contracts/operator_config/requant_node0001_two_stage_contract_v1.json`
  （SHA-256
  `a1e6c12d745e8cb8efa0758ca0a237d8ee9ee102b096b00fcd0a7ea3f66f27d9`）；
- backend 物化配置集：
  `configs/stage_codegen/hwop-0001-01-requant-v1/manifest.json`
  （生成时 SHA-256
  `08613f1f42c7597f900ba93374c33bf5bc3d78a17bde3f98cb6326e6247051e3`）。

backend manifest 明确保持 `formal_target_config=false`、
`hardware_execution=false`、`hardware_numeric_match=false`，配置集为 10 个文件且
逐文件与 source config set 语义一致。

## 总账变化

- local lowering resolved：4→5；
- local lowering unresolved：129→128；
- candidate config emission allowed：1→2；
- JSON emitter ready：3→4；
- RTL semantics compatible（局部静态口径）：2→3；
- formal target config：仍为 0/133；
- dynamic release ready、E4、E5：仍均为 0。

## 下一步

1. 本会话先对其余 53 个 Requant 请求逐项检查 multiplier 符号/有限性、输出
   zero-point、输入值域、shape/wave/shard、round/saturation 与两级生命周期，
   只对满足相同精确前提的请求推广；
2. node0001 的无 RTL 改动 stock-RTL E4/E5 任务已交给“测试修复”会话；该会话先生成
   唯一新身份的最小 E4 包并做本地 package validation，未经用户在该会话明确授权不上传
   或运行；
3. E4 必须读取 guard intermediate 与最终 uint8，对完整 golden 校验 24 occurrence、
   48 barrier、单 SFU load、consumer preload=0 及四阶段身份；E5 必须是全新身份重跑；
4. E4/E5 通过前保持 `B_REQUANT_SERVER_E4_E5`，不得产生正式发布声明。
