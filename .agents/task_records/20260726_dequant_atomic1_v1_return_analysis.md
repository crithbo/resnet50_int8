# Dequant atomic v1 回传裁决与 D buffer 供给修正

日期：2026-07-26

## 裁决

`dq_node0077_atomic1_stock_v1_return.zip` 已完成独立安全解压、内部
`RETURN_RECEIPT` exact-set/size/SHA 验收和动态结果分析。回传 ZIP 为
53,903 bytes，SHA-256 为
`a9ed04a1423c64edb263669aa1a47e0913042bade57c99dc4f681c8bc8b1398c`；
用户未提供外部 sidecar，因此证据可用于失败定位，不可作为 release identity。

compile/sim/run 均为 0，stock TB 自然进入 SCA_D 并退出；slice0、slice1 都有
Start/Finish。每片只接受 1 个 MSE4 write，首 beat 与独立 golden 逐 bit 相同，
但正式 D 后 3 行均为 `x`，finish 当周期仍有 outstanding address。

最终分类：

```text
DEQUANT_CONFIG_D_BUFFER_ROW_UNDERSUPPLY_EARLY_LAST
owner = CONFIG_SEMANTICS
```

## 根因

旧 v5 与 atomic v1 同时具有：

```text
stream2 transaction = idx_size[2] + 1 = 64 bytes
stream2 buf_spatial_size = 16 bytes
GROUP2.ROW_LC trips = 1
```

因此每 occurrence 只向 MSE4 提供 16 bytes，而不是所需 64 bytes。唯一
buffer row 携带 terminal tag，`WR_Data_Channel` 将首 beat 当作 last 并产生
`slice_cmpt_finish`。可信原生
`ndp-sim-ref/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json`
使用 `GROUP2.ROW_LC.end=4`，与 `buffer5.buf_end_row_addr=3` 一致。

本次没有证明功能 RTL 缺陷。应先运行四-row 修正版；只有修正版仍失败，才能继续
向 RTL_CONTROL 收窄。

## 规则与 validator 更新

- 新增 `CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001`；
- 新增动态证据规则 `CDA-DEQUANT-ATOMIC-V1-DYNAMIC-EVIDENCE-001`；
- 原子 observer 必须按同一地址域比较，禁止 post-remap raw address 与
  pre-remap linear golden 直比；
- identity gate 改以规范化布尔事实为准，禁止硬编码过期 status 字符串；
- Dequant validator 新增 64-byte transaction 与 4×16-byte buffer row
  守恒检查，并新增 end=1 的负例测试。

规则身份：

- `.agents/rules/DequantizeLinear算子配置规则.md`：
  `b6c6586422706287625c39792e33eda6b39dc4f8a4cbd24f363b921cbc526b09`
- `.agents/rules/DequantizeLinear原子动态合同规则.md`：
  `0785af08353894f42aa703f06929d2c05944898698fdc819a7b8e0ae6a737199`

## 修正资产

未覆盖旧 v5/atomic v1：

- full config v6：
  `configs/native_ndp_sim/resnet50_dequant_node0077_uint8_fp32_strict_v6/config.json`
  SHA-256
  `72c871e3bb4583302961ead62cabefa8b125281be97b5df61b45a190f18998bb`
- full local E2 v6：
  `artifacts/operator_config_validation/r5-dequant-node0077-e2-v6/local_e2_report.json`
  SHA-256
  `6a024f7da99026b977a4356909c99e7ac1635733fd95173a4f6741795cb965ee`
- atomic config v2：
  `configs/native_ndp_sim/node0077_dequant_atomic_single_stage_stocktb_v2/config.json`
  SHA-256
  `c974e9ca8bdd8635a2cf804bbb90b7c72aae2265084dd4256e4fa267da846718`

v6 完整 JSON 已从可信原生配置重新生成，两个隔离 toolchain 的
mapping/encoder/bitstream/execplan/SCA/SCA_D 输出一致；本地 E2 通过，
`candidate_release=false`。atomic v2 仅物化 JSON/golden/contract，
`server_package=false / NOT_RUN`。

机器报告：
`server_returns/dequant_node0077_atomic1_stock_v1_return_analysis_20260726.json`，
SHA-256
`d05d5768232120b5286c2d0529197b2d80fb4eb5cc1d019ba4eb2ab48b13acc1`。
