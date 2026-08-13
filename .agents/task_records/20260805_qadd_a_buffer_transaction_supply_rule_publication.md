# QLinearAdd A/B input-buffer transaction supply 规则发布

日期：2026-08-05

主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 裁决

正式发布：

`CDA-QADD-A-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`

位置：`.agents/rules/QLinearAdd算子配置规则.md` 第11节。

发布后规则文件：

- bytes：`19428`
- SHA256：
  `28bb859c5f9b8cb5ce5e7ac0dfd81bc06c8b24835d1d3fa4a6062c7c23c0800b`

生成前必读索引已路由 QLinearAdd 专项规则，无需新增同义索引入口。

## 非同义性

既有 `CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001` 约束计算结果从
Buffer5 向 write-MSE 回写的 D 方向供给。本规则约束 op_fp32_add 计算前两侧
producer→Buffer0/2→ARM 的 read-side ingress。两条规则的数据方向、物理 buffer、
consumer、mask 与动态验收边界均不同，不能互相替代。

## 冻结证据

- v29 return report：
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-pairmatrix-v29-return-analysis/report.json`
- bytes：`7404`
- SHA256：
  `6bfc521f1ec22b2e29ed7ec0679e52d5f9e1db91ea832ae998734bdef0b168c9`

v29 已到 op_fp32_add。Buffer0/Buffer2 各只有一笔16B qualified accepted write；ARM 对
8个bank的32B row mask全部有效，导致两侧 ARM accept 与 GA capture 均为0。合法候选
须在同一32B物理row内形成 `[0,16)`、`[16,32)` 精确并集。

## 规则边界

- 两侧 operand 必须分别证明 accepted producer windows 精确等于 ARM masked byte set；
- 总字节数相同但 bank/lane/row/column 分布不等不得放行；
- 单边完成、level sample、缩窄 mask、内部 tensor preload 或延长 timeout不得绕过；
- 删除第二窗口、重复首窗口、gap/overlap、错配单位及缩窄 mask 负控必须 fail closed；
- 修正后必须 fresh 重建完整物化链并保持 workload/numeric/address/golden/formal D 合同。

本轮只发布主线规则；未修改功能 RTL，未上传或运行服务器。
