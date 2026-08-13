# Compile provider-closure blocking gate withdrawal

日期：2026-08-13

## 上一版本进度

主线曾激活 `CDA-SERVER-COMPILE-MODULE-PROVIDER-CLOSURE-001`，要求 next-fresh 在原生 production
compile 前聚合 module provider，并在静态闭包不足时运行同 compiler/provider-flags 的短探针。
v88/v89 对照已经证明单一路径状态不能独立裁决编译可用性。

## 本版本目的与裁决

用户最新明确裁决：服务器端不得检查具体文件、目录或 module provider 是否存在；能运行即可，编译完整性
由原生 production compile 自然裁决。主线据此撤销 provider-closure/短探针的 current blocking 权限：

- 从 current build-gate registry 删除 `compile_environment_attestation`；
- 从必读路由、服务器包规则、整网优化规则和 plan 删除 next-fresh provider preflight 要求；
- 不向任何 family 派发，不据此 hold、阻断、重建或旋转包；
- 已实现 tool/schema/dispatch/tests/report 仅保留为历史诊断资产，不得由 runner current 调用；
- 等待 optimizer 提交 `SUPERSEDING_NATIVE_FLOW_RULE_READY` 后再窄幅合并原生 ndp-sim 入口、命令、环境与工作目录差异规则。

## Claim boundary

仅修改主线控制面。没有 package、storage、RTL、config、numeric、workload、upload、lease 或 server action。
