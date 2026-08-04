# Dequant node0077/v6 正式 E5 回传验收

日期：2026-07-27

## 裁决

`dequant_node0077_stockrtl_e5_onecmd_v1` 独立验收为
`E5_PASS / REPEATED_DYNAMIC_PASS`。它与既有 E4 绑定且使用全新的
package/install/run/return 身份，`B_DEQUANT_SERVER_E5` 已关闭。

node0077/v6 现在可计为正式 ResNet50 target config，并完成 stock-RTL E4/E5 动态闭环。
项目总账中的完整三方节点仍需单列的 config-bound simulator 执行腿，不能把本次硬件
重复通过自动改写成 simulator 证据。

## 身份与正式证据

- return ZIP：253,442 bytes，
  SHA256 `ae993cbf7cc51757a6be24f89e72a3e77ac98cba8953ef1510f93e736a71ca66`
- source package：153,596 bytes，
  SHA256 `83cd2db78f99d27f02c2b65a46f9f5c43e94b9ff9a5c50ef0273a0409f1cab68`
- 外部 sidecar 未随用户附件提供；内部 RETURN_RECEIPT 的 105 项 payload 与 ZIP
  实际 payload 逐项 size/SHA 相同，allowlist 和必需文件通过
- compile/sim/run：`0/0/0`
- 28/28 slice 各一次自然 start/finish
- 28×188=5,264 行正式 D；28 份文件的 128-bit/LF ABI 通过并与包内独立 golden
  逐字节一致
- inverse：`float32[16,1000]`，actual/expected SHA256 均为
  `d5aa938813ec8ef7fe51cc2288df5f0e1782c19729a184cef248718ce83a311d`
- observer：5,264 raw request、5,264 raw write-data
- functional RTL unchanged；E4→E5 冻结门为 61 项中 60 项 byte-exact、1 项仅 SCA
  install namespace 归一化

## 更新

- 规则：`CDA-DEQUANT-NODE0077-E5-V6-DYNAMIC-PASS-001`
- 专项规则 SHA256：
  `76c66fb19268061caaeafca5ba2899017f6f0c95326a6350c5fb12f18e710dd2`
- 机器报告：
  `server_returns/dequant_node0077_stockrtl_e5_onecmd_v1_return_analysis_20260727.json`
  SHA256
  `544761cb91681f1b45a611ef92f05de49e771bb354da3c8a43817a8ca0b7728d`

没有修改 `rtl/`，没有生成新的 Dequant 服务器包。
