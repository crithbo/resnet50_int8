# GAP v62 return 与 v63 preflight 修复主线验收

## 上一版本进度

GAP v56 已动态证明 slice-local-base 绕行通过全部 16 个选定 slice 的 sum_s1。v62 保留该绕行，并以 `TB_VCD_BOUNDED_CAUSAL_CONE` 覆盖 sum_s2 input-supply、MSE0、Buffer0、GA、MSE4 及 stage/global finish 的宽因果锥。

## v62 正式 return 裁决

v62 return 的结构、CRC 与 package identity 可消费，但 production compile 未启动：包内 `TEST_PACKAGE_MANIFEST.status` 仍为中间态 `PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES`，而 package runtime 只接受最终态 `PACKAGE_READY_NOT_RUN`，因此 package-local runtime preflight 在 time 0 前 fail closed。

`LAST_PROVEN_GOOD` 仍为 v56 的 sum_s1 全 16 slice 完成；v62 没有动态 observer/VCD 行，不能裁决七个 GAP 因果候选。因为 production compile 与目标均未执行，本次不触发 `RULE_GAP_AUDIT`。

## PACKAGE_BUILD_FAILURE_RULE_AUDIT

同一 fresh v63 在生成 ZIP 前连续两次被本地门阻断：fresh install namespace 曾被误判为 workload 漂移，随后 negative observed flags 又被错误并入 positive `all()`。因此在第三次尝试前触发并完成 `PACKAGE_BUILD_FAILURE_RULE_AUDIT`。

审计把缺口归类为共享 hard-gate coverage gap 加 package-local boolean conjunction bug。v63 在不豁免安全门的前提下落实更严格的包级联取：

- manifest 晋升最终状态后，对 staging tree 执行 package-specific preflight；
- clean extraction 后对 exact final ZIP 再执行相同 preflight；
- 负控将 manifest 改回中间态并要求精确拒绝；
- observed negative facts 与 positive pass booleans 分离；
- preflight stdout、stderr 与 exit 在 compile-not-started return 中可见；
- 重新执行 current-epoch first-fresh 与 final-ZIP 审计。

机器审计位于 `outputs/gap_node0071_v63_sum_s2_tbvcd_preflightfix/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json`。共享规则/门禁层的窄幅复核已路由给 `optimizer.whole-network`；family 未修改公共规则或共享工具。

## Fresh successor

- package：`r5_n71_gap_v63_sum_s2_tbvcd_preflightfix`
- pickup：`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v63_sum_s2_tbvcd_preflightfix.zip`
- 状态：`PACKAGE_READY_NOT_RUN`
- 唯一未来命令：`bash r5_n71_gap_v63_sum_s2_tbvcd_preflightfix/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

v63 保持 v62 的 config、numeric、workload、golden、functional RTL、slice-local workaround 与 sum_s2 因果锥，只改变 fresh identity、manifest 最终状态、preflight 失败可见性及对应门禁。

## Claim boundary

本验收只确认正式 return 的 package-local admission 根因、规则审计触发和 fresh package 本地发布。未执行 upload、lease、connect 或 server run；不声称 production compile/simulation、GAP 动态根因、natural terminal、formal-D、E3、E4 或 E5。
