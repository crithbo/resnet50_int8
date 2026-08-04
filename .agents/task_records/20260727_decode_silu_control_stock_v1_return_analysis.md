# Decode SiLU native control v1 回传裁决

日期：2026-07-27

## 结论

本 control 的共同 SFU 数值路径通过，正式 D 地址覆盖失败。不能把整个结果简单写成
“formal mismatch”，也不能把中间正证据丢掉。

两片各有 8 个物理 SFU PE、2 个输入 occurrence，因此真实 checkpoint 数是每片 16、
合计 32。preprocess capture、coeff、ALU input/result、postprocess、normal outbuffer
input/commit、normal outport 均为 32/32，四个案例逐 bit 等于硬件 SFU golden：

- `-1 → 3dad0980/be3ceb13 → be89b7ea`
- `0 → 3f000000/397ff6ab → 397ff6ab`
- `-4 → bd5f3921/be947a3d → bd9376b2`
- `+4 → 3f86950b/be8e34b8 → 407b637f`

MSE4 16/16 write-data payload 同样正确。因此共同 stock-RTL
`SFU coeff → ALU → postprocess → normal outbuffer → outport → MSE4 wdata`
已证明可工作；这排除共同路径普遍失效，但不证明 RequantGuard 的专属系数表、opcode、
tag 或配置消费正确。

control 的独立错误有两项：

1. 自动门把每片预期 checkpoint 写成 32，真实应为 `8 PE×2 occurrence=16`；
2. 每片正式 D 8 行中只有前 2 行为 binary-known，且仅保存最后 occurrence；后 6 行
   为 X。权威分类是 D occurrence/address coverage alias 或未覆盖，不是
   `line_count=0/parser failure`。本回传尚不足以唯一裁决具体 LC/stream 字段。

所以本 control 分类为
`SHARED_SFU_NUMERIC_NORMAL_OUTBUFFER_MSE4_PAYLOAD_PASS__D_OCCURRENCE_ADDRESS_COVERAGE_FAIL`，
最后可信边界为 `MSE4_WDATA_16_OF_16_BIT_EXACT`，首分歧区间为
`MSE4 accepted address/occurrence carrier → final D row residency/readback`。
不生成 SiLU 重跑包；继续正在生成的冻结 Requant guard-only event-qualified 窄探针。

## 身份

- return ZIP：57,030 bytes；
  SHA256=`182d3dbb160aac768cd37d634cc2ba34584a8524df4cb4983df3cc6691e0f246`
- 外部 sidecar：缺失
- 内部 payload：23/23 exact-set/size/SHA 通过
- source package：47,209 bytes；
  SHA256=`3cbabba52e414f38ec33a2e234972fe3455655a6669163e5765d4c1141a62c53`
- manifest SHA256：
  `4eea577c1227d9a6bd9f4a7ffb5297e22ab667219e9f4b70e79cb77231017ae5`
- compile/sim/run：0/0/0；单 stage 自然完成；RTL/observer identity 通过

## 规则增量

`CDA-REQUANT-NATIVE-SILU-CONTROL-V1-DYNAMIC-EVIDENCE-001`

机器报告：
`server_returns/decode_silu_fp16N_fp32N_control_stock_v1_return_analysis_20260727.json`
