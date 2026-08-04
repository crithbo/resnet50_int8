# Decode SiLU FP16N→FP32N stock-RTL control package v1

状态：`PACKAGE_READY_NOT_RUN`。本记录只覆盖本地生成、封包与验收；未上传、未运行，
`candidate_release=false`，不计 Requant E4/E5，也不能证明 Requant guard/round/alias。

## 冻结语义与重建

- 原生 oracle：`ndp-sim/jsons/decode_silu_fp16N_fp32N.json`
  - SHA-256：`eafb7ec7cd47006dda15c1fc60d00601563a7a9f7e8ae12da3ce45e57baec6be`
- address-bound 派生文件与 oracle 明确分离，未冒充逐字节原文件。
- 两次固定 seed=42、初始 empty mapping cache 的原生全链重建一致：
  - mapping SHA-256：`2b1c7bbe409a349c0ec668dc4030515dc1e99219a74c789b6a1677f25bbd2ff1`
  - bitstream SHA-256：`7327afb213a7e6017bfb9150c92ed8adca6a430f62225a3f7625e896863ed083`
- 语义合同：
  `contracts/operator_config/decode_silu_fp16N_fp32N_control_stocktb_v1.json`
  - SHA-256：`a4a5787aa3bd344f809b897c1bcb0e8a76a40d235c62f8c7aaa493cf15ec0a44`
- 正式 golden 使用真实 SFU 装载顺序 `[2,3,0,1]`、RTL BST 系数选择、
  FP16→FP32 与 exact-rational fused multiply-add 后一次 FP32 RNE；未使用高精度
  `x*sigmoid(x)` 代替硬件近似。每个 32-byte transaction 内使用统一输入值，
  去除了未证明 lane permutation 对 formal D 的影响。

## 包身份

- 目录：
  `artifacts/operator_config_validation/r5-server-test-packages/decode_silu_fp16N_fp32N_control_stock_v1`
- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/decode_silu_fp16N_fp32N_control_stock_v1.zip`
- bytes：`47209`
- ZIP SHA-256：`3cbabba52e414f38ec33a2e234972fe3455655a6669163e5765d4c1141a62c53`
- sidecar：
  `artifacts/operator_config_validation/r5-server-test-packages/decode_silu_fp16N_fp32N_control_stock_v1.zip.sha256`
- manifest SHA-256：`4eea577c1227d9a6bd9f4a7ffb5297e22ab667219e9f4b70e79cb77231017ae5`
- payload tree SHA-256：
  `5ecc3e9dd1968e0676aaaa2ce8d8e23bc009390c77f95a13df22f8b15847d630`
- payload files：`23`（manifest 外）；ZIP `rtl/` entries=`0`
- validation receipt：
  `artifacts/operator_config_validation/r5-server-test-packages/decode_silu_fp16N_fp32N_control_stock_v1_validation.json`

唯一服务器命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

```text
decode_silu_fp16N_fp32N_control_stock_v1_return.zip
decode_silu_fp16N_fp32N_control_stock_v1_return.zip.sha256
```

## 本地门

- 定向测试 `tests.test_decode_silu_control_package`：`5/5 PASS`。
- Python compile：PASS。
- 两个全新目录独立构建：`2/2`，ZIP 逐字节一致。
- 最终 fresh-extract 完整自检：严格只执行一次，PASS。
- fresh package tree 执行前后 exact path/size/SHA 不变；未允许 pyc。
- transactional observer install/verify/restore：PASS，恢复逐字节一致。
- XMR 静态门：检查 463 个 generated-instance reference，运行期实例路径下标 `0`。
- `CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001`：
  唯一目标相对路径 `native_return_observer.svh`，候选写路径数 `1`，
  从唯一命令传入的 NDP root 规范化，install/run/restore 使用同一规范化目标。

## 动态合同与未解除项

- active physical slices：`[0,1]`；单 stage；`Repeat_Num=1`。
- 每片 input `4×128-bit`，formal D `8×128-bit`，两片输入/golden 可区分。
- capture-edge observer 与 Requant A 使用同协议，覆盖 SFU preprocess/BST/coeff/ALU/
  postprocess/normal outbuffer/outport、独立 MSE4 request/wdata。
- 包未运行，动态结果未知；仅用于共同 SFU/normal-outbuffer/observer control。
- Requant guard 数据路径 blocker 与 Requant E4/E5 均未解除。
