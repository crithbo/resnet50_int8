# Requant SFU numeric / native Decode SiLU 双包交付

- 日期：2026-07-27
- 状态：`PACKAGE_READY_NOT_RUN`
- 范围：只生成、本地封包和验收；未上传、未运行；未修改 `NDP_copy01/rtl/**`
- 服务器唯一命令：`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`

## 包 A：Requant guard-only SFU numeric

- 身份：`rq_node0001_guardonly_sfu_numeric_stock_v1`
- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_numeric_stock_v1.zip`
- bytes：66,563
- SHA256：`8e96d1bbd6e0379b8d33fca251b27bbc40bb32fc56d82418a3ae85e0515e1a1b`
- manifest SHA256：`d4b7ccf7ca24f0c4a940fb863ada3dc5c367797f71dfa04822aba400adbdf4ae`
- 语义冻结：22 个 JSON/mapping/bitstream/execplan/input/SFU/golden/expected-write 文件逐字节不变
- 验收：两次确定性构建一致；唯一一次 fresh-extract 完整自检通过；定向测试 12/12；
  ZIP 33 entries，duplicate/unsafe/`rtl/` 均为 0
- 预期回传：`rq_node0001_guardonly_sfu_numeric_stock_v1_return.zip` 及 `.sha256`
- 边界：仅定位 `SFU_PREPROCESS0_VALID` 后的 capture-edge 数值链；不计 E4/E5

## 包 B：可信原生 Decode SiLU control

- 身份：`decode_silu_fp16N_fp32N_control_stock_v1`
- oracle：`ndp-sim/jsons/decode_silu_fp16N_fp32N.json`
- oracle SHA256：`eafb7ec7cd47006dda15c1fc60d00601563a7a9f7e8ae12da3ce45e57baec6be`
- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/decode_silu_fp16N_fp32N_control_stock_v1.zip`
- bytes：47,209
- SHA256：`3cbabba52e414f38ec33a2e234972fe3455655a6669163e5765d4c1141a62c53`
- manifest SHA256：`4eea577c1227d9a6bd9f4a7ffb5297e22ab667219e9f4b70e79cb77231017ae5`
- payload tree SHA256：`5ecc3e9dd1968e0676aaaa2ce8d8e23bc009390c77f95a13df22f8b15847d630`
- address-bound contract SHA256：`a4a5787aa3bd344f809b897c1bcb0e8a76a40d235c62f8c7aaa493cf15ec0a44`
- golden：按真实 `FIFO_128to64` 低半先行、每 64 bit 内 MSB word 先消费，
  即每行 `[2,3,0,1]`，再逐项回放 RTL BST 和 FP32 fused RNE；两片各 8 行正式 D
- 验收：两次确定性构建一致；唯一一次 fresh-extract 完整自检通过；定向测试 5/5；
  ZIP 24 entries，duplicate/unsafe/`rtl/` 均为 0
- TB 目标隔离：manifest 固定 `native_return_observer.svh`；命令参数根目录和目标均规范化，
  候选写路径为 1，install/verify/run/restore 始终绑定同一路径并保存 preimage 收据
- 预期回传：`decode_silu_fp16N_fp32N_control_stock_v1_return.zip` 及 `.sha256`
- 边界：只裁决共同 SiLU/fp16→fp32/normal-outbuffer/observer 路径；不证明 Requant guard，
  不计 Requant E4/E5

## 读取、规则和发布门

- A 读取收据：`.agents/task_records/20260727_requant_guardonly_sfu_numeric_v1_read_receipt.json`
- B 读取收据：`.agents/task_records/20260727_decode_silu_control_stock_v1_read_receipt.json`
- B 使用公共服务器规则 SHA256：
  `e4b4a215a60a3efbca83d00998d9618b17c8fb591aadb0a537828869a276b1ee`
- 新门：`CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001`
- 两包均为 `candidate_release=false`、`NO_DYNAMIC_BASELINE`，未解除：
  `B_REQUANT_GUARD_DYNAMIC_DATA_PATH`、`B_REQUANT_SERVER_E4_E5`
- `.agents/plan.md` 仅短更新双包状态，更新后 SHA256：
  `c2850d30e26ba7aa58b05f7e606714b124d10ca9fb3b18695fc9f37f4862b127`
