# GAP int32_mac stock-RTL one-command v4 record

日期：2026-07-24

## 用户操作边界

用户澄清：测试内容无需缩减，要求简化的是服务器操作。v4 保留完整六 stage
配置、golden、身份和动态裁决；服务器用户只执行：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

入口自动完成 fresh namespace 安装、包/路径预检、stock RTL 身份采集、隔离
RUN_DIR 编译与 `simv` 运行、显式 SCA/SCA_D 绑定、结果分析和 allowlist-only
回传。脚本不调用 Makefile archive target，所有 dump flag 均为 0。

## 必读规则与使用的规则 ID

开始前完整阅读：

- `.agents/rules/服务器测试包生成规则.md`
- `.agents/rules/算子配置规则.md`
- `.agents/rules/GAP_int32_mac_bypass_rules.md`
- `.agents/rules/GAP_probe_v7_validator_rules.md`
- `.agents/rules/GAP_repair_candidate_rules.md`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
- `.agents/plan.md` 第 0.3 节

包中记录并执行：

- `CDA-GAP-INT32MAC-NONTRANSOUT-001`
- `CDA-GAP-INT32MAC-DUAL-INPUT-001`
- `CDA-GAP-INT32MAC-NORMAL-FIFO-001`
- `CDA-GAP-INT32MAC-TREE-001`
- `CDA-GAP-INT32MAC-STAGE-MEMORY-001`
- `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`
- `CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001`
- `CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001`
- `CDA-GAP-REPAIR-RETURN-RECEIPTS-001`
- `CDA-GAP-D-READBACK-COVERAGE-001`
- `CDA-GA-OUTBUFFER-OCCUPANCY-001`
- `CDA-GA-INVALID-SLOT-ISOLATION-001`
- `CDA-GA-CROSS-BLOCK-INIT-001`
- `CDA-MSE4-MONITOR-EVIDENCE-001`
- `CDA-SERVER-FOCUSED-IDENTITY-001`

## 修改与版本裁决

新增/更新的实现：

- `tools/build_gap_int32_mac_onecmd_server_test.py`
- `tools/gap_int32_mac_server_runtime.py`
- `tests/test_build_gap_int32_mac_onecmd_server_test.py`
- `.agents/rules/GAP_int32_mac_bypass_rules.md`
- `.agents/rules/服务器测试包生成规则.md`
- `.agents/plan.md`
- `contracts/operator_config/gap_int32_mac_bypass_v1.json`

功能 RTL 与本地 `NDP_copy01` 均未修改。包内 `.v/.sv/.vh/.svh` 数量为 0，
不含 RTL patch，也不安装 observer；只对服务器已有 observer 做 fail-closed
预检。

- `gap_int32_mac_stock_rtl_atomic_v1`：用户否决，历史资产只读。
- `onecmd_v2`：未发布；128-bit 文本残留 CRLF，本地门失败。
- `onecmd_v3`：未发布；SCA_D key 的字典序不能保证数字 slice 身份，本地复核失败。
- `onecmd_v4`：按解析后的数字 slice ID `0..15` 绑定正式回读，是唯一允许交付版本。

## 本轮重建与交付身份

本轮从六份当前配置重新生成 planner/encoder、mapping、parsed/64b/128b
bitstream、installed bitstream、execplan、pretty SCA/SCA_D 和 local E2：

`artifacts/operator_config_validation/gap-int32-mac-bypass-v1/onecmd-v4-local-e2`

- 目录：
  `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v4`
- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v4.zip`
- ZIP size：`1634093` bytes
- ZIP SHA-256：
  `51b8fde985372d52133340c88e7dd85000cea3332cfbaa1c93f45b73262b07ff`
- sidecar：
  `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v4.zip.sha256`
- manifest SHA-256：
  `82c0fc7b2a3d67982902fac03be68d66672523771dbc97903f78000bcaaebf19`
- payload tree SHA-256：
  `80ad9126ad5c766de39b19343a864921a46aa773114b6ef5ac10be5d48850471`
- payload files：85；ZIP entries：86；functional RTL files：0
- release gate：`candidate_release=false / E2_LOCAL_ONLY`

第二次 fresh build位于
`artifacts/operator_config_validation/r5-server-test-packages/determinism-onecmd-v4/`，
ZIP SHA、manifest SHA、payload tree SHA 与正式交付逐字节一致。

## 验证与服务器动态门

本地验证包括：

- exact package/ZIP/sidecar 与 server-equivalent preflight；
- `PREPARE_AND_RUN.sh` Git Bash `bash -n`；
- 数字 slice readback 身份专项回归；
- GAP int32_mac semantic/memory、one-command package、stock RTL identity 共 30 项
  回归全部通过；
- 更新后的机器合同 SHA-256：
  `47134849d4cca92e176c6c32ca25fdb543e0563bbabc656928cf125d46428de4`。

入口自动分析：

- 16×512 SCA_D 正式回读逐行 golden；
- 全部 16 个 slice 的 MSE0/MSE3 六 stage 请求数与有序地址偏移配对；
- 6 次 `EXEC_START` 与 6 次 `COMP_FINISH`；
- bounded GA opcode14 normal-FIFO accepted-input 状态；
- pre-install/post-install/post-run/noop-final stock RTL 身份稳定性。

现有 observer 不能证明每个 `clk_sg` 周期的 FIFO occupancy。因此服务器运行前后
均保持 `candidate_release=false`；仍需闭合全周期 FIFO、自然运行未覆盖时的
skew/stall/resume 最小正交实验，以及独立重复 E5。即使绕行路线数值通过，也不
解除历史 `B_GAP_GA_ACCUM_STATE`。

预期仅回传：

```text
gap_int32_mac_stock_rtl_onecmd_v4_return.zip
gap_int32_mac_stock_rtl_onecmd_v4_return.zip.sha256
```

回传排除 wave、build tree、Make archive 和 nested archive；16 份正式 D
readback 直接进入回传，双 MSE 全 slice 裁决写入 `SERVER_RESULT_GATE.json`。
