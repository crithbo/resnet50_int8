# 2026-08-18 支线执行模式最终裁决：长期子代理模式

- mainline: `44764e6e-52db-4219-bf61-51a72507063e`
- user decision: 用户选择长期（continuable）子代理模式作为支线 owner；此前用户顶层会话迁移被取代。
- server actions: none

## 结论

- 每个已注册支线 role 长期占用一个 continuable 子代理会话；主线用 `send_message` 直接派发，支线完成后回传主线。
- 用户创建的 5 个顶层会话不再担任 registry owner，仅可由用户人工查阅工作区，不再接收主线路派发。
- 工作区邮箱 `outputs/session_mailbox_v1/` 保留为人工审计镜像，不再作为主派发通道。

## CAS 恢复

主线通过 `tools/session_handoff.py` 把 5 个支线从用户顶层会话 CAS 恢复到既有长期子代理：

| role | restored thread_id | owner_epoch |
|---|---|---|
| `family.gap` | `31bd404e-0aaf-4365-88de-b9fbf7be9656` | 5 |
| `family.conv.serialized` | `e37a5e44-44a6-4bfc-87fa-7de7a5a7605d` | 5 |
| `family.conv.native` | `b6895cbd-cad1-4860-9ac7-37f00820c69b` | 5 |
| `family.qlinearadd` | `a2d79b57-88d8-4372-a6d0-a213c6d922aa` | 5 |
| `optimizer.whole-network` | `2297b2a8-2e51-43f6-8fa0-1c3621a63913` | 4 |

machine receipts: `outputs/session_owner_rebind_20260818/12~16_*_restore_subagent_*`。

## claim boundary

本轮只更新 owner registry、plan 与任务记录；未上传/运行服务器、未取 lease、未修改 functional RTL/config/numeric/workload/package。
