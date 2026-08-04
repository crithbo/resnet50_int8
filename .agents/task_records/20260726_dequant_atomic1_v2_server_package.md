# Dequant node0077 atomic v2 服务器诊断包

日期：2026-07-26  
状态：`PACKAGE_READY_NOT_RUN`

## 输入与裁决

- v1 首分歧：
  `DEQUANT_CONFIG_D_BUFFER_ROW_UNDERSUPPLY_EARLY_LAST / CONFIG_SEMANTICS`。
- atomic v1 与 atomic v2 配置唯一差异：
  `buffer_loop_configs.GROUP2.ROW_LC.end: 1 -> 4`。
- 修正后供给守恒：`4 rows × 16 bytes = 64-byte D transaction`。
- 未修改本地 `NDP_copy01/rtl/**`、`tb_NDP_Top_new_phy.sv` 或
  `native_return_observer.svh`；包内 `rtl/` entry 为 0。

## 使用规则

- `CDA-SERVER-WORKLOAD-PROVENANCE-001`
- `CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001`
- `CDA-SERVER-ONE-COMMAND-001`
- `CDA-SCA-D-TB-READBACK-LENGTH-001`
- `CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001`
- `CDA-SERVER-NO-DYNAMIC-BASELINE-001`
- `CDA-SERVER-RETURN-RECEIPT-001`
- `CDA-DEQUANT-ONNX-ORDER-001`
- `CDA-DEQUANT-NO-AFFINE-MAC-001`
- `CDA-DEQUANT-TWO-STAGE-GA-001`
- `CDA-DEQUANT-NORMAL-OUTBUFFER-001`
- `CDA-DEQUANT-STREAM-LIFECYCLE-001`
- `CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001`
- `CDA-DEQUANT-ATOMIC-STOCK-TB-001`
- `CDA-DEQUANT-ATOMIC-V1-DYNAMIC-EVIDENCE-001`

读取收据：
`.agents/task_records/20260726_dequant_atomic1_v2_server_package_read_receipt.json`，
SHA256=`4aa78ad5d7124ae08f30637d35a724ae8bb2ddd0d69207ed6e88e0bcbd646e2f`。

## 重建链

从 atomic v2 JSON/typed graph 分别在两个全新隔离目录执行：

`planner -> address planner -> mapper -> encoder -> bitstream -> execplan -> SCA/SCA_D`

两轮原生输出与两轮最终 ZIP 均逐字节一致。关键产物：

- address-bound config SHA256
  `1b462b849b15927a93b76a20a3f321c032913263ce491e5e34aaad099e0b5652`
- mapping review SHA256
  `e37b824932345826acea87f1d1cda4b28cbe25b6bd344500b78e49aca5369719`
- bitstream 128b SHA256
  `974b8f1cabd82d00931662d0c195468474f8f0861dbf6d57ed55d024dd8021ea`
- execplan SHA256
  `30d6870c23824e14157997adac9f18267bc7283ccbb914a9f14c58670ffb7329`
- SCA SHA256
  `9d74072c6e389cc65e1b35ac669923f76f02d9db61228bfc4098344e6ce659ce`
- SCA_D SHA256
  `88a1f6a6006ca588656944a51774cfecb3f6d0f21a63dd401cdf7851069fa0a4`

## Validator 修正

1. observer 同时保存：
   - `transfer_addr`：remap 前 transfer offset；
   - `linear_addr`：remap 前线性 word address；
   - `post_remap_addr`：accepted local request address。
   合同 `word_address_128b` 只与 `linear_addr` 比较，禁止跨域直比。
2. stock identity 不再硬编码 `status == rtl_unchanged`；改为要求
   `functional_rtl_unchanged`、probe precompile/restore、focused RTL、
   support files 和五阶段 identity 布尔事实全部为真。
3. 每片 finish 必须同时满足：
   - accepted request / wdata / paired write 均为 4；
   - address/data outstanding 均为 0；
   - 正式 D 四行全部非 x 且与 golden bit-exact。

## 本地验收

- 相关单元与语义测试：19/19 PASS。
- exact ZIP：39 entries，payload exact-set/order/bytes PASS。
- `rtl/`、Python bytecode、嵌套压缩包：均 0 entry。
- fresh-extract runtime bootstrap 前后 package tree size/SHA 不变。
- fresh-extract observer install、compile 前核验、逐字节恢复 PASS；
  恢复后 package tree 不变。
- `GROUP2.ROW_LC.end=4` 已同时出现在 source config 和新生成
  address-bound config。

## 交付身份

- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/dq_node0077_atomic1_stock_v2.zip`
- size：72,749 bytes
- SHA256：
  `6d3f9c52f602131a5f3b4950d8d477b13f03509900e15dc82ad40f9aa80fac71`
- sidecar：
  `artifacts/operator_config_validation/r5-server-test-packages/dq_node0077_atomic1_stock_v2.zip.sha256`
- manifest SHA256：
  `1075d2498a260c0ed56df835e2622fbef6bc0ac73444e9f6c8490c62b6704bfe`
- 唯一服务器命令：
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- 预期回传：
  `dq_node0077_atomic1_stock_v2_return.zip` 与
  `dq_node0077_atomic1_stock_v2_return.zip.sha256`

本包为 FIRST_DYNAMIC 原子诊断，`candidate_release=false`，
不计 node0077 E4/E5；`B_DEQUANT_SERVER_E4_E5` 未解除。未上传、未运行。

