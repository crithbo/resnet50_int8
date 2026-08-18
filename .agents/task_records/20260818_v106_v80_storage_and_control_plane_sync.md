# 2026-08-18 serialized v106 / QAdd v80 存储与控制面同步

状态：`STORAGE_LIFECYCLE_COMPLETE / CONTROL_PLANE_SYNC_COMPLETE / PACKAGE_READY_NOT_RUN`。

## 用户授权与边界

用户明确要求完成两份当前测试包的 managed storage 与主线控制面同步。本记录不授权
upload、lease、connect 或 server run，也不修改功能 RTL、config、numeric、workload 或 golden。

## 当前唯一 pending

- serialized Conv：`r5_n4_hw_v106b_lcdup_return2pflight`
  - managed ZIP：`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v106b_lcdup_return2pflight.zip`
  - bytes=`5991155`
  - SHA-256=`200382857c0310fd4599363564f7e08f0f268c88468e09620deaf85ed81eb116`
  - 独立审查：`outputs/independent_dual_package_final_audit_v2/machine_report.json` 中 serialized v106=`PASS`。
- QLinearAdd：`r5_qadd_n7_tr_v80_w15kqf`
  - managed ZIP：`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tr_v80_w15kqf.zip`
  - bytes=`108884698`
  - SHA-256=`2353572204ef16ccf9142e73bcbc3822c62a28d4c8115fcbae2db195a1f029d9`
  - 独立审查：`outputs/independent_qadd_v80_postpatch_audit_v1/machine_report.json`，`PASS`。
  - source-bound selected wall=`15000` 秒，absolute maximum=`86400` 秒；4/2 配置、64-signal 因果锥与独立保护保持冻结。

## 存储生命周期

两个 family 使用 canonical `tools/manage_server_test_package_storage.py rotate` 串行执行，
每族恰好一次：

1. serialized v102 从 pending 归档 tested，v106 成为 serialized 唯一 pending；
2. QAdd v73 从 pending 归档 tested，v80 成为 QAdd 唯一 pending。

最终 corrected global storage audit：`PASS`；
pending/tested/superseded=`2/61/24`。

- `PACKAGE_STORAGE_INDEX.json` bytes=`496312`
- SHA-256=`a774f0706c79f992f8e64e8fd8942d5d1bd40e2d5ea45ed54029aa10c5044cf0`
- serialized lifecycle receipt：
  `outputs/conv_node0004_v106b_lcdup_return2pflight_release1/storage_lifecycle_complete.json`
  SHA-256=`25fafa721be6f581f9097e827637b36667e39c958af4fbc3cb8f7f8540b80b81`
- QAdd lifecycle receipt：
  `outputs/qadd_v80_w15kqf/STORAGE_LIFECYCLE_COMPLETE.json`
  SHA-256=`a9ac87bc38e2cebc11b6a0cf56a9331dc53d51fcfc10567b1e8db7d3d36dc7ca`

## 控制面裁决

`.agents/plan.md` 与 `contracts/current_session_owner_registry_v1.json` 已窄幅更新：

- serialized 当前指针从 v102 切换为 v106；
- QAdd 当前指针从 v73/8400 秒切换为 v80/15000 秒；
- mainline 当前任务绑定两份唯一 pending 与独立 PASS；
- active-rule receipts 刷新为 current canonical identities；
- GAP/native 与其它 owner、规则语义、存储记录保持不变。

当前仍无 `SERVER_RUNNING` lease。下一步只允许在用户另行明确授权后执行上传和服务器测试。
