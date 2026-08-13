# Four-family native-flow fresh build dispatch

日期：2026-08-13
owner：`mainline.control`
状态：`BUILD_DISPATCHED`

## 用户命令

用户明确要求重新重建四个下一轮测试包。该授权只覆盖本地 fresh package 构建、验证与安全 storage
rotation，不授权 upload、lease、server connection 或 production run。

## 上一版本进度

- GAP v60、serialized Conv v89b、native Conv p45 均已消费 formal return 并归 tested；三者在
  production compile/elaboration 阶段失败，simulation 未启动。
- QAdd v61 已是 `PACKAGE_READY_NOT_RUN`，但生成时间早于 current native-flow non-interference gate，
  尚未运行。
- provider-closure/短探针阻断已撤销；current gate 要求 finalizer 先 arm，然后直接执行真实原生
  production flow，并以 actual cwd/argv/log/exit 自然裁决环境。

## 本版本目的

四个 family 均以 fresh identity 重建：冻结各自 config/numeric/workload/golden/functional RTL 和当前
宽因果 observer target；exact runner 在唯一 `# CODEX_PRODUCTION_LAUNCH` 前不得执行服务器文件、目录、
tool/library/module provider existence 检查、Make dry-run、lookup probe 或独立 attestation；真实失败必须
返回 actual cwd、compile/sim argv、相关 env、SCA_CFG/SCA_CFG_D、Repeat_Num、完整日志、first true error、
exit、simulation_started 与 compile core，并在失败后做 native ndp-sim differential。

专项附加要求：GAP 修正 first-true-error 优先级；serialized Conv 不得恢复已证错误 ACK comparator；native
Conv 补齐 p45 stale/missing compile-fail core evidence；QAdd 保留 v61 的 identity repair、双 ping-pong 分支与
48-signal宽因果目标，v61 仅在 fresh 全部门通过后方可原子 supersede。

## Dispatch

- `family.gap` → `019ff02d-8225-7d21-9779-e46ce4130572`
- `family.conv.serialized` → `019ff02d-901b-7f70-a9da-f54e268b5bbe`
- `family.conv.native` → `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- `family.qlinearadd` → `019ff02d-9e93-7d61-8c98-c928fdea157c`

四条消息均已成功发送。主线不持续轮询；等待各 family 主动回传 `PACKAGE_READY_NOT_RUN` 或明确终止状态。

## Claim boundary

没有修改或运行服务器、RTL、config、numeric、workload、golden；没有 upload/lease/server action。
