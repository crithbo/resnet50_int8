# 2026-08-05 package-local HDL actual-consumer scope rule publication

## 主线裁决

- current mainline thread：`019fbec2-fe93-7e03-9314-cff6f222f33d`
- source owner：GAP node0071 `019fa366-cb1f-7ae2-880c-f527be0680cd`
- verdict：`RULE_DELTA_ACCEPTED_AND_PUBLISHED`
- published rule：
  `CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`
- target：`.agents/rules/服务器测试包生成规则.md`
- server rule previous SHA256：
  `14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1`
- server rule published SHA256：
  `5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9`
- 生成前必读索引已路由服务器测试包公共规则，本次不新增同义索引项。

## 触发证据

GAP v36 正式 return 在服务器 VCS compile、simulation 启动前失败：

- return bytes：`50471`
- return SHA256：
  `2f8a425164bfb4dbe193e644b3a5c040a8b15b92feb62e5edc197902599852ff`
- frozen source ZIP SHA256：
  `8835bcad4b54f6c0ec5ad225976d71631492477430e73e77f838df1d76cbf1dd`
- compile/simulation/runner：`2/125/2`
- formal D：`0/48`
- exact failing member：`tb_probe/native_return_observer.svh:4614`
- actual unresolved consumer：`return_obs_rd_spatial_mon`
- declared/expected identifier：`return_obs_rd_spatial_size_mon`
- return report：
  `artifacts/operator_config_validation/r5-gap-node0071-v36-return-analysis/report.json`
  SHA256=`2e5ec8fbbdb53e519818f6edea820e2f7d1c0e0ec0c6d23f81f8f75698f8603f`

现有 `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`
已经要求 exact final HDL、scope/name-resolution 与真实 consumer 负控，但实现仍可从
expected identifier inventory 或 mock/focused harness 选择验收对象；v36 的真实 failing
consumer 未进入该范围，导致正控和负控同时逃逸。故该提案不是重述现有原则，而是补足
“验收范围必须由最终 compiled HDL 的实际消费者表达式推导”的机器来源约束。

## 发布内容与边界

新规则要求：

1. 枚举范围内每个 exact final HDL actual consumer expression，并记录 member/span/SHA/
   identifier/declaration/owner；
2. actual consumer 全覆盖、uncovered=`0`，不能由 expected inventory、模板或 mock
   补出目标 identifier；
3. 拼写负控必须直接由实际 source span 变异，逐表达式覆盖或给出机器可核验的等价覆盖类；
4. 负控重跑同一 frontend/scoped semantic closure；
5. final audit 保存覆盖率、变异来源、退出码与 exact ZIP/member identity。

适用范围只含本轮新增/修改或进入必需 canonical/result/progress/return 裁决的
package-local diagnostic identifier/state leaf。它不要求本地 full-design production
elaboration，不把兼容 frontend 通过升级为服务器 RTL/功能证明，也不新增服务器侧检查；
目标是尽量在本地阻止可发现的包侧拼写/scope 错误，同时保留服务器自然暴露专有依赖和
production-only elaboration 差异的能力。

## Successor receipt

GAP owner 已生成 fresh correction：

- identity：`r5_n71_gap_v37_dbclk_rdready_compilefix`
- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v37_dbclk_rdready_compilefix.zip`
- bytes：`1828271`
- SHA256：
  `796312c5c4c5ed941a78fd4a0cf245bb580edac9b1b7ff5960b8e78c3eb8fa7b`
- sidecar SHA256：
  `93fc9c6b84f5983177ae2562056f83584a44ea21bb1366b52fc403b485c140c3`
- final audit SHA256：
  `89be3c51cc3301bad5fd9e7a328b93f6885a197da4bc94bc6835bdb878b21640`
- status：`PACKAGE_READY_NOT_RUN`
- expected return：
  `r5_n71_gap_v37_dbclk_rdready_compilefix_return.zip`

该 successor 关闭 package-local typo，不关闭 GAP 功能、natural terminal 或48项 formal D
blocker；未修改 numeric/config/workload/golden/timeout/backpressure/functional RTL。
