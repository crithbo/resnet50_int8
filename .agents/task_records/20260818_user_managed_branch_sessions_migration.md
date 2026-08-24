# 2026-08-18 用户管理支线会话迁移与派发

- mainline: `44764e6e-52db-4219-bf61-51a72507063e`
- 结论：`USER_MANAGED_BRANCH_SESSION_MIGRATION_COMPLETE / NO_SERVER_ACTION`
- server actions: none

## 用户指令

用户要求支线以会话形式便于其管理，不要采用子代理；随后创建 5 个顶层会话并指定主线任意绑定、给对应规则和任务。

## 正式 CAS 绑定

主线通过 `tools/session_handoff.py` 对每个支线执行 request/capsule/acceptance/activation/publish，旧子代理 ID 全部退役：

| role | 新用户会话 ID | registry thread_id | owner_epoch |
|---|---|---|---|
| `family.gap` | `session-2be0d6cb-95d9-4e34-80ad-0c105f00ea1f` | `2be0d6cb-95d9-4e34-80ad-0c105f00ea1f` | 4 |
| `family.conv.serialized` | `session-effa2146-ade4-4910-bc1a-d1d987d431a9` | `effa2146-ade4-4910-bc1a-d1d987d431a9` | 4 |
| `family.conv.native` | `session-10e4c2b3-a43b-4012-a115-ca5959676078` | `10e4c2b3-a43b-4012-a115-ca5959676078` | 4 |
| `family.qlinearadd` | `session-6ca9f880-76aa-452b-98f5-e2524c15c220` | `6ca9f880-76aa-452b-98f5-e2524c15c220` | 4 |
| `optimizer.whole-network` | `session-d5f88a6d-825a-470f-9642-ff3f61b126bd` | `d5f88a6d-825a-470f-9642-ff3f61b126bd` | 3 |

machine receipts: `outputs/session_owner_rebind_20260818/`（07 为 optimizer，08~11 为四个 family 的 request/capsule/acceptance/activation/publication）。

## 规则与任务派发

每个新会话的第一轮只读接管文件：

- `outputs/user_session_dispatch_20260818/README.md`（总映射）
- `outputs/user_session_dispatch_20260818/family_gap.md`
- `outputs/user_session_dispatch_20260818/family_conv_serialized.md`
- `outputs/user_session_dispatch_20260818/family_conv_native.md`
- `outputs/user_session_dispatch_20260818/family_qlinearadd.md`
- `outputs/user_session_dispatch_20260818/optimizer_whole_network.md`

各会话保持原有 current_task、pending 包指针与权限边界，不因迁移获得任何新授权。

## claim boundary

本轮只更新 owner registry、plan 与派发文件；未上传/运行服务器、未取 lease、未修改 functional RTL/config/numeric/workload/package。
