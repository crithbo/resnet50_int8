# 项目瘦身清理记录

日期：2026-07-24

本轮按用户明确授权执行不可恢复删除，不建立备份。清理只覆盖用户选定的 A/B/C、
已有独立报告绑定的服务器回传，以及明确未上服务器运行的测试包；身份不清楚的回传、
已实际运行的测试包、活动回归 fixture 和当前 Dequant 工作资产均保留。

## 1. A/B/C

### A：address remapping 生成输出

删除 3 个未跟踪生成目录，共 `1,202,898,941` bytes：

- `ndp-sim/address_remapping/outputs`
- `ndp-sim-ref/address_remapping/outputs`
- `native_ring4_repro_20260722/address_remapping/outputs`

### B：Python 缓存

删除项目内 `__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`、
`.hypothesis` 和 `.pyc/.pyo`。清理前审计值为 `162,289,622` bytes。

### C：Git 安全维护

对根仓库及 `ndp-sim`、`ndp-sim-ref`、`CGRA_SIM`、`NDPFuncModel` 依次执行
`git fsck --full`，完整性均通过；随后使用标准 `git gc`，未使用
`prune=now`，未删除 dangling 对象。

根仓库标准 GC 后仍有 18 个被 Git 明确分类为 garbage 的
`.git/objects/[0-9a-f][0-9a-f]/tmp_obj_*`，共 `201,696,698` bytes。逐个校验
路径和名称后精确删除，再次 `git fsck --full --no-dangling` 通过。

5 个 `.git` 目录合计从 `1,101,911,164` bytes 降至 `582,894,102` bytes，
释放 `519,017,062` bytes。

## 2. 已有报告的服务器回传

删除原始 ZIP、展开树、波形和日志共 `4,854` 个文件、
`3,422,401,586` bytes；保留 18 个小型分析、诊断、acceptance 或安装报告原路径。

根目录以下 9 个原始返回 ZIP 已删除；其字节数、SHA-256 和裁决仍保存在
`.agents/history.md` 的“原始服务器结果 ZIP 台账”：

- `sim_results.zip`
- `sim_results_v2.zip`
- `sim_results_v3.zip`
- `sim_results_v4.zip`
- `sim_results_v6.zip`
- `sim_results_v7.zip`
- `sim_results_v8.zip`
- `sim_results_v9.zip`
- `sim_resultsv10r3.zip`

以下目录仅保留既有小型报告，删除其余回传内容：

- `server_returns/decode_max_fp32_simresults_1`
- `server_returns/gap_hwop0071_configfix_stockrtl_v10_evidence_20260724`
- `server_returns/gap_hwop0071_probe_v4_return_20260723`
- `server_returns/gap_hwop0071_probe_v5_return_20260723`
- `server_returns/gap_hwop0071_probe_v7_return_20260724`
- `server_returns/gap_hwop0071_sim6_20260723`
- `server_returns/gap_int32_mac_onecmd_v4_return_20260724`
- `server_returns/gap_rtl_three_way_identity_20260723`

以下回传目录已有历史/任务记录覆盖，故整目录删除：

- `server_returns/node0004_nopp_r1_sim_results_2`
- `server_returns/gap_hwop0071_configfix_stockrtl_v10_partial_20260724`
- `server_returns/gap_int32_mac_onecmd_v5_run_archive_20260724`

为避免破坏当前回归测试，保留体积很小且被
`tests/test_native_server_return.py` 直接读取的
`server_returns/int8_fp32_pair_20260723` 和
`server_returns/native_int8_maxpool16_sim4_2_20260723`。没有独立报告或精确身份
绑定的其他回传也未删除。

## 3. 从未服务器测试的测试包

删除 7 个明确未运行的 package 身份及其现存目录、ZIP、sidecar：

- `decode_max_fp32_stockrtl_onecmd_v1`
- `decode_max_fp32_stockrtl_onecmd_v2`
- `gap_hwop0071_sum_probe_v6`
- `gap_hwop0071_sum_repair_v8`
- `gap_int32_mac_stock_rtl_atomic_v1`
- `gap_int32_mac_stock_rtl_onecmd_v2`
- `gap_int32_mac_stock_rtl_onecmd_v3`

同时删除只服务于这些未运行包的 5 个确定性构建临时目录：

- `determinism-decode-max-v1`
- `determinism-decode-max-v2`
- `determinism-onecmd-v3`
- `determinism-onecmd-v4`
- `determinism-onecmd-v5`

本节共删除 26 个文件系统目标、`1,055` 个文件、
`267,491,130` bytes。

已实际尝试服务器运行的 probe v1/v4/v5/v7、configfix v10、repair v9 和
GAP int32_mac v4/v5 均保留。当前 Dequant 资产未纳入本轮清理。

## 4. 空间结果

清理前项目审计值：

```text
94,705 files
13,287,419,890 bytes
```

清理后最终值：

```text
74,076 files
7,727,926,560 bytes
```

净减少：

```text
20,629 files
5,559,493,330 bytes
```

按清理前审计值计算，项目从约 `12.375 GiB` 降至约 `7.197 GiB`，净释放约
`5.178 GiB`。各清理项的删除字节合计为 `5,574,098,341`；同期并行任务生成了约
`14,605,011` bytes 的活动资产，因此删除合计略大于项目净减少量。

末次核验结果：

- 5 个 Git 仓库 `git fsck --full --no-dangling` 全部通过；
- 5 个仓库的 Git garbage 合计为 0；
- Python cache 目录为 0，`.pyc/.pyo` 为 0；
- 18 个保留分析/诊断报告均存在；
- 8 个明确保留的已运行 package 身份，其目录、ZIP 和 sidecar 均存在；
- 根目录已报告的 9 个 `sim_results*.zip` 均已删除。
