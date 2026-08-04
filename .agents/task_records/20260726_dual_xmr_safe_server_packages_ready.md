# Requant guard-only v4 / Dequant atomic v3 XMR-safe 双包

日期：2026-07-26

## 裁决

两份后继包均已生成并完成本地验收，状态为
`PACKAGE_READY_NOT_RUN`。本轮只修复 observer/runtime/validator 的
generated-instance XMR elaboration 基础设施；未改 TB、未改
`NDP_copy01/rtl/**`，也未改变两份冻结的 JSON、mapping、bitstream、
execplan、SCA 语义、输入、golden 或 expected writes。

旧包继续冻结：

- `rq_node0001_guardonly_stock_v3`：
  `SERVER_TEST_INFRASTRUCTURE_OBSERVER_XMR_ELABORATION_FAILURE`；
- `dq_node0077_atomic1_stock_v2`：同一失败类，正式回传证明
  `simulation_started=false`。

两者均不计 dynamic attempt/E4/E5，禁止重跑。

## 修复

规则 `CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001` 已落到公共
package/runtime gate：

- 深层 WR Memory AG XMR 只在 `generate for(genvar ...)` 中连接到只读代理；
- 过程块的 `sid/ch/lane/row/slot` 只索引本地信号数组；
- 静态 validator 只检查 known generated-instance path，不禁止普通
  `proxy[sid][ch]`；
- fresh-extract 的真实 install/verify/restore 事务会对最终拼接 observer
  再执行相同 fail-closed gate；
- 未使用 `-v2k_generate`、force/deposit 或 timeout 绕行。

## 包身份

### Requant guard-only

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_stock_v4.zip`
- size：59,283 bytes
- SHA256：`c0ba6d7a56ccf1d8eb8306e78ec4e96fbcbcdda123ef9e5b2e9d39df32ebc24c`
- sidecar：同路径 `.zip.sha256`
- ZIP entries：32；`rtl/`=0；nested archive/wave=0
- 23 个冻结语义文件与 v3 byte-identical；SCA 仅 install identity
  归一化后相等
- tail / combined observer generated-instance 引用分别 66 / 401，
  runtime-indexed generated-instance=0
- `candidate_release=false`，不计 node0001 E4/E5

### Dequant atomic

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/dq_node0077_atomic1_stock_v3.zip`
- size：75,376 bytes
- SHA256：`f77d92165cc32af41e157da27ce4b7141882c8d49871961cab22a41ba668742c`
- sidecar：同路径 `.zip.sha256`
- ZIP entries：41；`rtl/`=0；nested archive/wave=0
- 32 个冻结语义/生成证据文件与 v2 byte-identical；SCA 仅 install
  identity 归一化后相等
- tail / combined observer generated-instance 引用分别 12 / 347，
  runtime-indexed generated-instance=0
- `candidate_release=false`，不计 node0077 E4/E5

## 验证

- 每包两次确定性构建，ZIP byte-identical；
- 每包 exact ZIP fresh extract 完整 package self-check 恰执行一次；
- bootstrap 前后 exact package tree size/SHA 不变；
- 实际 observer install/verify/restore 事务通过并逐字节恢复；
- 定向测试 18/18 通过；
- `NDP_copy01/rtl` 前后 tree SHA256 均为
  `175021f21cedeb3203675dbeedb22566a93a9378752c2a9266145cc3db3ea6cc`。

读取收据：
`.agents/task_records/20260726_dual_xmr_safe_server_packages_read_receipt.json`
（SHA256
`f8c2b72ff343af19028e3177d5b0d3aba9203639ef8e35433a7d2ae824c5e14d`）。

机器交付：
`artifacts/operator_config_validation/r5-server-test-packages/dual_xmr_safe_packages_delivery_20260726.json`。

## 服务器入口

两包必须分别解压、分别运行，不得合并到同一 run：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期分别回传 ZIP 与其 `.sha256`。本轮没有上传或启动服务器运行。
