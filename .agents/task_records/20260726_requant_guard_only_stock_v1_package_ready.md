# Requant node0001 guard-only stock v1 包就绪

日期：2026-07-26

状态：`PACKAGE_READY_NOT_RUN`。本包仅是 atomic2 v2 首分歧授权后的
guard-only 只读诊断，不计 node0001 正式 E4/E5，也不允许据此发布 candidate。

## 输入与冻结边界

- atomic2 v2 动态首分歧：
  `GUARD_WRITE_PAYLOAD_ZERO_AFTER_NONZERO_INPUT_PRELOAD`。
- 冻结并逐字节复用：guard JSON、guard mapping/bitstream、两片输入、
  RequantGuard payload、两片 guard golden。
- 未启用 round-only 或 alias-lifetime；未修改 TB、`rtl/**` 或
  `NDP_copy01/native_return_observer.svh`。
- 读取收据：
  `20260726_requant_guard_only_v1_package_read_receipt.json`。

## 修正的两个 validator 问题

1. observer parser 接受 `role=` 后任意空白，并强制
   `raw MSE4 marker count == parsed accepted-write count`；无法解析的原始行不再静默丢失。
2. MSE4 地址分域保存：
   - `transfer_addr`：pre-remap、未加 stream base；
   - `linear_addr`：pre-remap transfer 加 stream base，与
     `expected_mse4_writes.word_address_128b` 同域；
   - `post_remap_addr`：`mse_map_matrix_b` 后的 accepted local request。
   禁止 linear expected 与 post-remap actual 直接比较。

## guard-only 动态合同

- 两个 physical slices `[0,1]`，mask `...0011`；
- 单 guard stage，`Repeat_Num=1`，一个 Start_Comp 和一个同 mask barrier；
- SCA preload=5，正式 guard D readback=2；
- 每片 8 个 accepted MSE4 write，总计 16；
- 只读 checkpoint：
  MSE0 accepted request/rdata、MSE0→Buffer、GA raw/int32-to-fp32、
  SFU input/ALU/output、MSE4 accepted req/wdata。

## 包身份与本地门

- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_stock_v1.zip`
- size：57,157 bytes
- SHA256：
  `18d8c4ed61994b86ad664004ff4487c5b07ca492ff10918dad32d9c4b7133cdc`
- sidecar：同目录 `.zip.sha256`
- 31 package files，ZIP exact-set 通过，`rtl/` entry=0；
- 两次全新构建逐字节一致；
- 全新 ZIP 解压后执行真实 runtime preflight，前后 path/size/SHA
  完全不变，无 `__pycache__`/`.pyc`；
- Requant atomic、guard-only、Dequant atomic 定向测试 19/19 通过。

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

- `rq_node0001_guardonly_stock_v1_return.zip`
- `rq_node0001_guardonly_stock_v1_return.zip.sha256`

## 保持不变的并行包

Dequant 包 B
`dq_node0077_atomic1_stock_v1.zip` 仍为 `PACKAGE_READY_NOT_RUN`，
SHA256
`35a330f7446103da8a93cf0f3d03e1f9517d5d38739c84fbc51a6de924546ccb`。

仍未解除：
`B_REQUANT_GUARD_DYNAMIC_DATA_PATH`、`B_REQUANT_SERVER_E4_E5`。
