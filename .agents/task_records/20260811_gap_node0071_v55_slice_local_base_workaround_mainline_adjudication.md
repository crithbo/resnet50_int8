# GAP node0071 v55 slice-local base workaround 主线裁决

日期：2026-08-11  
主线：`mainline.control` / `019ff027-e7db-72a3-b282-cfad8708da05` / owner epoch `2`  
family owner：`family.gap` / `019ff02d-8225-7d21-9779-e46ce4130572` / owner epoch `2`  
current registry epoch：`6`

## 1. 用户授权与版本目的

用户已明确授权完成 GAP 配置绕行；本次授权不包含 functional RTL 修改，也不包含服务器上传、
运行或 lease。

- 上一正式回传 v54 的进展：已把失败唯一定位到
  `FUNCTIONAL_RTL_SLICE2HUB_REMOTE_WDATA_READY_NOT_QUALIFIED_BY_PRIORITY_OWNER`，并因当时没有
  repair/workaround 授权停在 `WAIT_RTL_FIX`；
- 当前 v55 的目的：不修改 RTL，通过每个 stage 的 slice-targeted base register 重写，让
  slice1..15 的 active MSE 基址与本 slice 对齐，从而绕开已证实的跨 slice 远端 owner-ready
  依赖，并为 fresh server package 建立冻结的本地候选。

## 2. Family 交付与机器身份

- candidate：`outputs/gap_node0071_v55_slice_local_base_workaround`
- candidate identity：`r5_n71_gap_v55_slice_local_base_workaround`
- validation report：
  `outputs/gap_node0071_v55_slice_local_base_workaround/validation_report.json`，
  bytes=`247457`，SHA-256=`4f3d1f22ac680f05596d024f5e7d56c3524bb52e9cb9138607c3fa73910bb8b3`
- execplan：
  `outputs/gap_node0071_v55_slice_local_base_workaround/r5_n71_gap_v55_slice_local_base_workaround/workload/install/execplan.txt`，
  bytes=`22962`，SHA-256=`8f9df021e70c9ae97c1efc35d3c53fc082a0018fe22c04ef48b85b3d8cd3b413`
- frozen RTL receipt：`slice2hub_crossbar` bytes=`20175`，
  SHA-256=`993db61aa6549a95cc8ee03bba64839d958cec8eddd56ad2b823338818b8ce2d`

Family 报告未构建 server package，未上传、未运行、未取 lease，未声明 E3/E4/E5。

## 3. 主线独立复核

主线对 `validation_report.json` 登记的 76 个 candidate-tree 成员逐一检查存在性、bytes 与
SHA-256，错误集合为空。机器报告与独立检查共同确认：

- status=`LOCAL_CONFIG_WORKAROUND_VALIDATED_NOT_SERVER_RUN`；
- 八份 v54 bitstream byte-identical；numeric 与非 base config 不变；RTL 不变；
- 8 个 stage 均在 `Load_Config` 后、`Start_Comp` 前写入 slice-targeted active base；
- 16 个 slice 的 active MSE 全为本地，`maximum_remote_mse_count_per_operator_execution=0`；
- candidate 为 355 commands、178 条 128-bit line，其中新增 330 个 `Write_Reg`；
- extra tensor copy/scratch/GA 均为 0；SCA input/readback 地址与 slice-local binding 一致；
- `tests.test_operator_config_execplan_validator` 6/6 PASS；
- `tests.test_operator_config_execplan_evidence` 4/4 PASS。

## 4. 主线裁决

`WAIT_RTL_FIX` 作为当前执行状态解除，但 v54 已证明的 functional RTL 根因仍保留为历史事实，
不得改写成“RTL 已修复”。GAP current task 转为：

- status=`PACKAGE_BUILDING`；
- objective=`build a fresh v55 slice-local-base workaround server package without RTL change`；
- next action：family owner 以已验证 v55 candidate 构建 fresh server package，并执行 current
  runner、source-bound、post-sim、waveform/return、frozen-payload、final-ZIP 与 first-fresh gates；
- current in-flight package 仍为 `NONE`，直到 family 提交结构化 `PACKAGE_READY_NOT_RUN` 回执；
- mainline 不替 family 构包；任何服务器 upload/run/lease 仍需另行明确授权。

该裁决只证明本地配置绕行在地址、命令与冻结面上成立，不证明生产 compile、DUT simulation、
natural terminal、formal D 或 E3/E4/E5。

## 5. 规则反馈

`RULE_CONFIRMATION`：current owner/write-scope、配置冻结、execplan 独立解码和 server-package
fresh-successor 门足以约束本轮动作；无 public rule delta。

conflicts=`[]`
