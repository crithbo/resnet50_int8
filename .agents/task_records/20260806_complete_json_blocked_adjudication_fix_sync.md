# Complete-JSON BLOCKED 裁决修复主线同步记录

日期：2026-08-06

## 状态

`FRESH_SHARED_DELTA_SYNCED / NINE_FAMILY_RERUN_DISPATCHED`

本轮只同步公共 complete-JSON driver 的合法 `BLOCKED` 裁决实现和永久回归测试；
schema、合同、公共规则、算子配置、功能 RTL、现有服务器测试包及服务器状态均未修改。

## 精确同步文件

- `tools/validate_complete_operator_json_candidate.py`
  - SHA256 `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f`
- `tools/audit_complete_operator_json_family_set.py`
  - SHA256 `baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82`
- `tests/test_complete_operator_json_candidate.py`
  - SHA256 `d51ab72366735b5e7f3039c72cc47b4d28fcb3f92747bae878ccaee03589a717`

未变：

- `tests/test_complete_operator_json_family_set.py`
  - SHA256 `ce041ae94f7172f017d92f366c8fa338f9b4237eb53555304537e6bfe5133aca`

## 裁决语义

- `errors` 只记录结构、身份和账本矛盾。
- `completion_blockers` 收集 unresolved leaf、unknown source-absent、
  unsupported handler axis、uncovered dependent leaf 和 unresolved composition。
- `COMPLETE` 仍要求 `errors=[]` 且 `completion_blockers=[]`。
- 合法 `BLOCKED` 报告必须为：
  - `contract_valid=true`
  - `blocked_valid=true`
  - `pass=false`
- 合法 `BLOCKED` 不再因“未暴露缺口”的假结构错误而失效，也绝不提升为
  `COMPLETE`。

## 验证

- `py_compile`：PASS。
- complete-JSON 单元测试：11/11 PASS。
- 新增永久正控：
  `test_blocked_candidate_reports_real_completion_blocker`。
- `git diff --check`：PASS。

## 边界

- 不修改已同步公共规则 SHA。
- 不生成 mapping、bitstream、execplan、SCA 或服务器测试包。
- 不上传、不运行服务器、不取 lease。
- 九个 family owner 必须以本记录中的新 driver SHA 重跑共享验收；只回传
  `COMPLETE` 或精确 `BLOCKED` 及其 `completion_blockers`。
