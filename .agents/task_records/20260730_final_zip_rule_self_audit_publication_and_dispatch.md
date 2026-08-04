# 2026-07-30 最终 ZIP 规则自检硬门发布与全任务通知

## 主线裁决

公共服务器包规则新增：

`CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`

任何责任会话在测试包生成完成后、报告 `PACKAGE_READY_NOT_RUN` 前，必须重新完整读取
current 生成前索引、公共服务器包规则与本族专项规则，并以最终 ZIP/sidecar 为对象执行
独立交付前自检。生成前读过规则、builder 自报、解包目录或中间 validation 均不能替代。

## 必需回传

- active rule path、SHA-256、适用 rule IDs、`current_match=true`；
- 独立 final-ZIP validator 的命令、cwd、退出码、errors 与报告 SHA；
- 所有必需负控的命令、退出码和 fail-closed 结果；
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`；
- ZIP 路径、bytes、SHA、matching sidecar、单一服务器命令与预期 return。

active rule 在生成期间漂移时，旧自检立即失效，必须复读并对同一最终 ZIP 重验；若新规则
要求改变包内容，则旧包隔离并使用 fresh identity 重建，禁止仅追写 receipt。

## 失败处理

缺收据或任一自检失败固定为：

`PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED`

不得上传、运行、加入主线运行队列或称为候选。主线接收时再次机械核对。

## 通知范围

已向当前全部可执行/保留上下文的责任会话发送同一强制通知：

- RequantizeUint8；
- QuantizeLinear/exact tail；
- QLinearAdd；
- Conv/SA；
- DequantizeLinear；
- 人工 JSON；
- MaxPool；
- QLinearGlobalAveragePool；
- 独立 RTL 审计（仅在未来参与签发包时适用）。

Flatten/View 会话当前为 not-loaded、无服务器包任务；公共规则已覆盖其未来恢复后的任何
封包行为。

## 发布收据

- server-package rule SHA-256：
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`
- dispatch-time plan SHA-256（mutable provenance）：
  `ec237da2f2094f20b5f7dab12d0723ebe08f1453cbb775c72b1b61567198edb5`
