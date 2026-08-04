# 2026-07-30 服务器长任务 observer 四向绑定规则发布

## 结论

已在 `.agents/rules/服务器测试包生成规则.md` 发布
`CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`。规则要求任何依赖 package-local
observer 的测试包在进入 `PACKAGE_READY_NOT_RUN` 前，由独立 validator 直接解析最终
ZIP，机械闭合 observer source、package-local include、compile-time enable 与
runtime/return 四向绑定，并执行四个逐项删除负控。

## 触发证据

本规则来自三个互补、已动态复现的包侧失败：

1. QLinearAdd node0007 v5：
   - compile enable macro 已存在；
   - observer source/package-local include 未绑定；
   - VCS 无法打开 `native_return_observer.svh`，compile=2，simulation 未启动。
2. Conv node0004 v6：
   - observer source 与 package-local `+incdir` 已存在；
   - compile command 缺 `+define+NATIVE_RETURN_OBSERVER_ENABLE`；
   - 运行约 102 分钟仍无 observer 实例或进度窗口，诊断包本身失败。
3. GAP node0071 v4：
   - observer source、`+incdir`、runtime plusarg 均存在；
   - compile enable macro 缺失；
   - 40 个 host 样本全部为 `OBSERVER_NOT_CREATED`，无法裁决持续前进或 DUT stall。

这些证据证明 builder 自报、单个脚本字段或 runtime plusarg 都不能替代最终 ZIP 的完整
绑定证明。

## 强制验收

最终 ZIP validator 必须验证：

- 唯一 observer source 的路径、大小、SHA-256 与 fresh-extract 可读性；
- `+incdir` 解析到 package root 内的 observer 目录；
- optional TB observer 分支所需的精确 compile enable macro；
- runtime enable、time-0 enabled receipt、actual compile/simulator argv、observer/progress
  日志、return allowlist 与 `EXIT/HUP/INT/TERM` trap 回收。

定向测试必须分别删除 source、`+incdir`、enable macro、runtime/return binding；四项均
必须返回 `PACKAGE_OBSERVER_BINDING_INCOMPLETE`。缺一时禁止发布、上传或运行。

## 首次执行结果

- QLinearAdd：
  `r5_qadd_n7_nested_lc_progress_bind_v6.zip`，
  SHA-256=`9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90`，
  最终 ZIP 四向绑定与四负控通过。
- Conv：
  v7 因最终 manifest 缺 `observer_binding_four_way` 合同而隔离；
  successor `r5_n4_hw_v8_hangloc_fourway.zip`，
  SHA-256=`44e592e4d6059b22d4ccfa76e17ec5d7a995e6375b1960ed743893e212a70308`，
  最终 ZIP 四向绑定与四负控通过。
- GAP：
  v4 因 compile enable 缺失而隔离；
  successor `r5_n71_gap_v5_obsbind.zip`，
  SHA-256=`159bebac586be3a40ae937736b0368593ced34c7b8128fde7858930b53ebef8d`，
  最终 ZIP 四向绑定与四负控通过。

以上三项均为 `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`，不构成 E3/E4/E5，
未上传、未运行、未修改功能 RTL。

## 关联记录

- `.agents/task_records/20260730_qlinearadd_node0007_v6_four_way_binding_validation.md`
- `.agents/task_records/20260730_conv_node0004_v7_four_way_binding_review.md`
- `.agents/task_records/20260730_gap_node0071_v4_hangloc_return_analysis.md`
