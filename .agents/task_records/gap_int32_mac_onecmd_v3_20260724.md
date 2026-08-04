# GAP int32_mac stock-RTL one-command v3 record

日期：2026-07-24

> **已废止，禁止交付或上传。** 后续本地复核发现正式 SCA_D 回读按 key
> 字典序枚举，不能保证 `slice0..slice15` 的数字身份绑定。该草稿从未发布，
> 由按数字 slice ID 精确绑定的 `gap_int32_mac_stock_rtl_onecmd_v4` 取代。

## 用户操作边界

用户澄清：不是删减测试内容，而是服务器操作不要复杂。最终包保留完整六 stage
配置、golden、身份和动态裁决，服务器用户只需执行：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

脚本自动完成 fresh namespace 安装、包/路径预检、stock RTL 身份采集、隔离
RUN_DIR 编译与 simv 运行、显式 SCA/SCA_D 绑定、结果分析和 allowlist-only 回传。
脚本不调用 Makefile archive target，所有 dump flag 均为 0。

## 必读规则与使用的规则 ID

开始前完整阅读：

- `.agents/rules/服务器测试包生成规则.md`
- `.agents/rules/算子配置规则.md`
- `.agents/rules/GAP_int32_mac_bypass_rules.md`
- `.agents/rules/GAP_probe_v7_validator_rules.md`
- `.agents/rules/GAP_repair_candidate_rules.md`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
- `.agents/plan.md` 第 0.3 节

包中记录的规则 ID：

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

## 生成链与修改文件

本轮先用 `tools/build_gap_int32_mac_local_e2.py` 在新目录
`artifacts/operator_config_validation/gap-int32-mac-bypass-v1/onecmd-v3-local-e2`
重建 execplan/local E2。报告保持：

- `Load_Config=6`
- `Start_Comp=6`
- same-mask completion barrier `=6`
- execplan 10 个 128-bit beat，SHA-256
  `71123c231c9025c9c6d06c6a80480c458f1af91950403f0cc15b06b456ec8741`
- 16 slice × 512 final lines，独立数值 SHA-256
  `f838df652cadb27110ed79084f49fd7e80445277d497e0d6e019c49132b73117`

新增：

- `tools/build_gap_int32_mac_onecmd_server_test.py`
- `tools/gap_int32_mac_server_runtime.py`
- `tests/test_build_gap_int32_mac_onecmd_server_test.py`
- 本任务记录

更新：

- `.agents/rules/GAP_int32_mac_bypass_rules.md`
- `.agents/rules/服务器测试包生成规则.md`
- `.agents/plan.md`
- `contracts/operator_config/gap_int32_mac_bypass_v1.json`

功能 RTL 与本地 `NDP_copy01` 均未修改。包内 `.v/.sv/.vh/.svh` 数量为 0；不含
RTL patch，也不安装 observer。服务器必须已具有只读 TB observer，入口脚本只做
fail-closed preflight。

## 版本裁决

- `gap_int32_mac_stock_rtl_atomic_v1`：用户否决，不再发布；其历史 ZIP 保持只读。
- `gap_int32_mac_stock_rtl_onecmd_v2`：未发布本地草稿；专项 validator 发现复制的
  128-bit bitstream 保留 CRLF，因此不交付、不原地修补。
- `gap_int32_mac_stock_rtl_onecmd_v3`：用全新 install/run/return 身份重建，所有
  128-bit transport 文本统一 LF，通过专项门。

## 最终交付身份

- 目录：
  `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v3`
- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v3.zip`
- ZIP size：`1633602` bytes
- ZIP SHA-256：
  `7a72b0ed75e690baf5a074940572e4caf0fd03e7599ccabd43efe5183d50a695`
- sidecar：
  `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v3.zip.sha256`
- manifest SHA-256：
  `45be8ccc53caba1614aed101f99da7cccd781a695c03df34e258503b04e8639b`
- payload tree SHA-256：
  `3bf54483bb44b2c8ad3714a44e003db71c96f9eac05f860cb04798b7cda8382c`
- payload files：85；ZIP entries：86；functional RTL files：0
- release gate：`candidate_release=false / E2_LOCAL_ONLY`

第二次 fresh build 位于
`artifacts/operator_config_validation/r5-server-test-packages/determinism-onecmd-v3/`
且 ZIP SHA、manifest SHA、payload tree SHA 与正式交付逐字节一致。

本地验证：

- `PREPARE_AND_RUN.sh` Git Bash `bash -n`：通过；
- exact ZIP/sidecar、标准库 server-equivalent preflight：通过；
- GAP int32_mac semantic/memory、one-command package、stock RTL identity 共 26 项
  unittest：全部通过。

## 服务器动态门与回传

入口自动分析：

- 16×512 SCA_D 正式回读逐行 golden；
- 16 个 slice 的 MSE0/MSE3 六 stage 请求数量与有序地址偏移配对；
- 6 次 `EXEC_START` 与 6 次 `COMP_FINISH`；
- bounded GA opcode14 normal-FIFO accepted-input 状态；
- pre-install/post-install/post-run/noop-final stock RTL 身份稳定性。

现有 observer 不能证明每个 `clk_sg` 周期的 FIFO occupancy。因此即使核心动态结果
全通过，包内结果门仍保持 `candidate_release=false`，并列出全周期 FIFO、缺失的
forced skew/stall/resume 覆盖（如自然运行未覆盖）和独立 E5。

预期只回传：

```text
gap_int32_mac_stock_rtl_onecmd_v3_return.zip
gap_int32_mac_stock_rtl_onecmd_v3_return.zip.sha256
```

回传排除 wave、build tree、Make archive 和 nested archive；16 个正式 D readback
直接进入回传，双 MSE 全 slice 的压缩裁决写入 `SERVER_RESULT_GATE.json`，原始日志
只保留代表性的 slice0 MSE0/MSE3。
