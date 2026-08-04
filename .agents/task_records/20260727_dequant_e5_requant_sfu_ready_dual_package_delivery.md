# 2026-07-27 双包本地交付记录

状态：`PACKAGE_READY_NOT_RUN`。本轮仅生成、封包和本地验收；未上传、未运行，
未修改公共规则、`.agents/plan.md`、TB 或 `NDP_copy01/rtl/**`。

## 生成前读取身份

- `.agents/rules/生成前必读索引.md`：
  `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7`
- `.agents/rules/服务器测试包生成规则.md`：
  `b4019910c7ef65f334676a1b3a5679e63b8ac41dcde88b567ada4f096e50fe05`
- `.agents/rules/DequantizeLinear算子配置规则.md`：
  `2374975170515252b1ea2d1c1ffc806af5b757c286322ba91b194c0bac0419d7`
- `.agents/rules/RequantizeUint8算子配置规则.md`：
  `20883fad672123f6f6561633d58b5432ed453feb8f2695e5993f9bfe97b0756e`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`：
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`
- `.agents/plan.md`：
  `1eaf9491aa345c4559915b937161f293d4aaa1bc4f135024632645b7453a7d95`

各包的完整消费者读取身份见各自独立读取收据。

## 包 A：Dequant node0077/v6 正式 E5

- identity：`dequant_node0077_stockrtl_e5_onecmd_v1`
- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/dequant_node0077_stockrtl_e5_onecmd_v1.zip`
- size：153,596 bytes
- SHA256：
  `83cd2db78f99d27f02c2b65a46f9f5c43e94b9ff9a5c50ef0273a0409f1cab68`
- manifest SHA256：
  `dd945f768755d8e937d44d6e258f06e6e9a03d10932a1ec4531543f3bc4fda46`
- sidecar：同路径追加 `.sha256`
- 唯一服务器命令：
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- 预期回传：
  `dequant_node0077_stockrtl_e5_onecmd_v1_return.zip` 及其 `.sha256`
- 发布边界：`candidate_release=false`、`E5_PACKAGE_READY_NOT_RUN`；
  `B_DEQUANT_SERVER_E5` 未解除。

冻结核对：61 个 workload 路径一致，60 个逐字节一致；唯一差异是
`sca_cfg.json` 的新安装命名空间，归一化后逐字节一致，`sca_cfg_D.json`
逐字节一致。门保持 28 slices × 188 formal D 行 = 5,264 行、5,264 raw
request、5,264 raw wdata、tail `+0.0` 和 full inverse。

验收：双次确定性构建一致；仅一次最终 fresh-extract 完整自检通过；
ZIP 86 entries，无重复、越界路径或 `rtl/` entry；bootstrap 86 files /
1,209,439 bytes，运行前后 tree SHA256 均为
`19cd2feb92cac39642ef6f3d99395955f60ca3d62f2d24592ffc0203591c0df2`；
定向测试 3/3 通过。

独立记录：

- `.agents/task_records/20260727_dequant_node0077_full_v6_e5_package_ready.md`
- `.agents/task_records/20260727_dequant_node0077_full_v6_e5_package_read_receipt.json`

## 包 B：Requant node0001 guard-only SFU readiness

- identity：`rq_node0001_guardonly_sfu_ready_stock_v1`
- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_ready_stock_v1.zip`
- size：65,468 bytes
- SHA256：
  `8cb224163271e0ed9166831bf434c88ce10e1f76ed78a42344724f8b5126c2ac`
- manifest SHA256：
  `4365a808c094a08fbbd42e6e6420c134b1a89524593a7e9356f77e3945500234`
- sidecar：同路径追加 `.sha256`
- 唯一服务器命令：
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- 预期回传：
  `rq_node0001_guardonly_sfu_ready_stock_v1_return.zip` 及其 `.sha256`
- 发布边界：`candidate_release=false`，不计 E4/E5；
  `B_REQUANT_GUARD_DYNAMIC_DATA_PATH` 与 `B_REQUANT_SERVER_E4_E5` 未解除。

冻结核对：与 `rq_node0001_guardonly_directsig_stock_v1` 的 JSON、mapping、
bitstream、execplan、input、RequantGuard、golden、formal D、expected writes
共 22 个语义文件逐字节一致；SCA 仅新 identity，归一化后相等。

诊断只保留一个 `PE_SELECTED_INPUT` last-good checkpoint，并新增 opcode、
SFU readiness/LUT、PE post-register 和 preprocess0 的只读观察；保留 lifecycle、
16 个 raw MSE4 request/wdata 和两份 formal D。全部门通过时结果为
`GUARD_ONLY_DIAGNOSTIC_PASS` 且 `first_divergence=null`；否则仅路由至
opcode/config consumption、LUT readiness、PE register/match、observer gap。

验收：双次确定性构建一致；仅一次最终 fresh-extract 完整自检通过；
ZIP 33 entries，无重复、越界路径或 `rtl/` entry；bootstrap 33 files /
294,986 bytes，运行前后 tree SHA256 均为
`1d1ac421072aedcce7010a9beb0c1507a6245d8417c47e5e60eb689307e400e9`；
定向测试 12/12 通过。

独立记录：

- `.agents/task_records/20260727_requant_guardonly_sfu_ready_v1_package_ready.md`
- `.agents/task_records/20260727_requant_guardonly_sfu_ready_v1_read_receipt.json`

## 最终只读复核

- 两个 sidecar 均与实际 ZIP SHA256 一致。
- 两个 ZIP 的 root identity、entry 数、重复项、unsafe path 和 `rtl/` 条目
  均复核通过。
- 轻量定向回归合计 15/15 通过；未重复执行包级完整自检。
