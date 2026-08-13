# 2026-08-11 规则正交化、会话换届与 next-fresh 构包派发

## 用户授权与边界

- 用户要求在 `agent.md` 中给出各会话必读规则，按最新 return 修正规则，完成会话换届后归档本项目历史会话，并开始按新规则构建下一轮测试包。
- 本轮允许：公共规则/schema/tool/test、owner registry、handoff capsule/acceptance/activation、创建/归档 Codex 会话、next-fresh 本地构包。
- 本轮禁止：服务器上传/运行/lease、functional RTL、硬件/ISA、active ndp-sim、现有 return 与 frozen package 内容修改。
- optimizer thread `019fd276-14c5-7800-94db-87ebfb9ce632` 是换届 campaign 明确豁免，继续保持当前专项 owner。

## 活动规则收敛

- `.agents/rules/` 从 23 份收敛为 14 份；9 份旧规则原字节迁入 `.agents/history/rules/`，统一入口为 `.agents/history/rules/README.md`。
- `contracts/active_rule_registry_v1.json` 固定 exact active set、layer、semantic owner、read profile 与 SHA；活动规则审计要求 exact-set、单一 CDA definition owner、历史默认不读。
- `agent.md` 新增 `role_id → 共同必读 + 角色增量必读` 矩阵；主线、GAP、serialized/native Conv、QAdd、基础设施、optimizer 与 human-JSON 均禁止无关族规则扩张。

## 最新 return 驱动的两项非同义门

1. `CDA-SERVER-RUNNER-SET-U-DEFINITION-BEFORE-USE-001`
   - 冻结反例：QAdd v57d 在 `set -u` 下先展开 `run_root` 后赋值，preflight/compile/simulation 前退出。
   - next-fresh exact runner 必须聚合枚举 normal/preflight/compile/signal/finalizer 路径的定义前使用；映射 `server_start`。
2. `CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001`
   - 冻结反例：native p38 与 serialized v84b 均只回 `compile=2`，没有 bootstrap-safe actual argv/source identity/bounded log/first-error。
   - next-fresh 必须在 compile 前落盘并由 core finalizer 收回上述证据；映射 `server_start + return`。

共享实现：

- `schemas/server_runner_return_resilience_v1.schema.json`
- `tools/validate_server_runner_return_resilience.py`
- `fixtures/server_runner_return_resilience_v1/`
- `tests/test_server_runner_return_resilience.py`
- `contracts/server_package_build_gate_registry_v1.json::runner_return_resilience`

所有错误一次聚合，最终 ZIP 只复核 exact bytes 一次；可选格式/完整日志/非裁决统计仍为 `record_only`。

## 下一轮 family dispatch

- serialized Conv：从 v84b formal return 出发生成 fresh successor，保持 config/numeric/workload/RTL 不变；新增 bootstrap-safe compile argv/source/first-error core return，并执行新 runner gate + first-fresh independent exact-ZIP audit。
- native Conv：从 p38 formal return 出发生成 fresh successor，保持 config/numeric/workload/RTL 不变；同样闭合 compile-fail root-cause evidence。
- QAdd：v57f 已是 runner-only 修正版 pending；新 owner 先以 exact ZIP 对新 gate 做 first-fresh 审计。若 exact bytes 不能满足新门，则用 fresh identity 做 runner/return-only successor；不得改 config/numeric/workload。
- GAP：保持 `WAIT_RTL_FIX`；硬件修改仍被用户禁止，不构包。

## 验证与 claim boundary

- active-rule audit：14/14，duplicate CDA definitions=0，history exclusion PASS。
- runner/return resilience：6 tests PASS；永久负控覆盖 v57d-shaped unbound、compile evidence 缺失、attempt-root bootstrap 与 late finalizer、post-contract ZIP mutation。
- Python AST parse PASS；`git diff --check` PASS。
- 本记录不声称 production compile/simulation、natural terminal、正式 D、E4/E5 或服务器成功；next-fresh package identity 由换届后的 family owner 回传。
