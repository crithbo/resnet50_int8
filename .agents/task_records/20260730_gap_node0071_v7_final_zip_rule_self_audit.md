# GAP node0071 v7 final-ZIP current-rule self-audit

日期：2026-07-30

唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## CURRENT RULE RECEIPT

包生成后完整复读并 current-match：

```text
.agents/rules/生成前必读索引.md
SHA256=12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f

.agents/rules/服务器测试包生成规则.md
SHA256=7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa

.agents/rules/GAP_int32_mac_bypass_rules.md
SHA256=b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96

.agents/rules/GAP_probe_v7_validator_rules.md
SHA256=2dee42a883bde9c1650710c8312d23e661aeb3c66ef9d1d4e15524af79c33dc7

.agents/rules/精确UINT8量化尾专项规则.md
SHA256=1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e
```

plan 仅 mutable provenance：

```text
SHA256=ec237da2f2094f20b5f7dab12d0723ebe08f1453cbb775c72b1b61567198edb5
```

## V6 CURRENT-RULE DECISION

原 v6：

```text
r5_n71_gap_v6_canonical.zip
SHA256=aeb92c6f6442fa6e04f9207b791ccc4bab32b5ac1584b425c4cc3945f2dbdc38
```

其 final manifest 绑定前一 server-rule SHA，缺少
`CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001` 的 in-package current-match receipt。
新规则禁止仅在包外追写 receipt，因此 v6 保持原字节并隔离：

```text
status=QUARANTINED_DO_NOT_RUN
first_failed_rule_id=CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001
```

## FRESH V7 PACKAGE

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v7_finalaudit.zip
bytes=1790098
SHA256=6ae39b218e622f9937753dd4d4d649b1d2a7420c49ec5ed71d00fe8c26abd068
sidecar SHA256=b535fdab63bca15ace9a49bab94113b7d8456aba281cc8fedb922c80974045f2
```

v7 manifest 保存上述五份 current read receipt、全部适用 rule IDs、
`current_match=true`、明确 N/A 理由与 mutable plan receipt。只改变 package identity、
SCA namespace 和交付收据；73 个冻结 numeric workload 文件逐字节相等，未重跑
sum/tail/workload。

## FINAL ZIP RULE SELF-AUDIT

最终 ZIP/sidecar 独立报告：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v7_finalaudit.final_zip_rule_self_audit.json
SHA256=e2a6a69f439fc52ba48d171cbd1d76cefec007a1107780daa6864c35f1fbd9c9
FINAL_ZIP_RULE_SELF_AUDIT_PASS=true
errors=0
status=PACKAGE_READY_NOT_RUN
```

直接核验：

- sidecar exact、ZIP CRC、125 项 member、manifest exact-set/逐文件 SHA；
- frozen reuse provenance、bootstrap immutability、唯一入口/路径；
- runtime D 在 ZIP 中不存在；
- 默认低开销 progress diagnostics；
- observer source/include/macro/runtime-return 四向；
- qualified-only progress 与 canonical decision；
- fail-closed 动态联合门；
- 70 项 return allowlist exact target set；
- 不安装 TB，不修改功能 RTL（两项明确 N/A）。

独立命令全部 exit 0：

```text
final_zip_canonical_validator_and_negative_controls=0
final_zip_observer_four_way_validator_and_negative_controls=0
fresh_extract_package_runtime_preflight=0
fresh_extract_canonical_self_test_all_controls=0
fresh_extract_runner_bash_syntax=0
```

validator stdout 报告 SHA：

```text
canonical=9675a6bb9ff46a7686d2cab3ccc6ce2af9b3144855e040207067a572f9592bb3
observer_four_way=e7df831b4c9843be3d2b4d35aa07eccf7d3b13f5ec4704795a07441da74368d1
package_preflight=306260f4f897a8b351f52bd86dd843b141f157d941da65db59a190b020740428
canonical_self_test=967a9690abd7b130352ea15e211f8368e8a0cc4b0f1bd852867bda59742b7f85
```

负控全部 fail closed：

- continuous-high level 不增加 qualified delta；
- canonical-prefix summary append；
- 冲突双裁决；
- 缺 reason；
- 缺 boundary；
- observer source 删除；
- `+incdir` 删除；
- compile macro 删除；
- runtime/return binding 删除。

非 canonical 前缀 summary 不覆盖完整 decision；两个 qualified progress window 与完整
active-cycle flat stall window 正控通过。

首次自检 attempt1 因审计器错误查找报告字段名而非 runtime 变量名，误报 result gate
source 缺失；包内实际联合门未变化。attempt1 报告保留为：

```text
r5_n71_gap_v7_finalaudit.final_zip_rule_self_audit.attempt1_failed.json
SHA256=8b8d011e3f9f656ea0f39c059a43549965ae452888bef1dc4eb3ceede8f4ecc9
```

修正审计器匹配 `terminal/missing/mismatch_bytes/all(loader.values())` 后，同一最终 ZIP
复核通过；未修改 v7 ZIP。

## PACKAGE_RELEASE

```text
claim=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
status=PACKAGE_READY_NOT_RUN
candidate_release=false
evidence_level<=E2_LOCAL_ONLY
```

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

```text
r5_n71_gap_v7_finalaudit_return.zip
r5_n71_gap_v7_finalaudit_return.zip.sha256
```

未检查、上传或运行服务器；无 lease；未修改 plan、公共 rules 或功能 RTL。没有重复
GAP sum/tail 数值分析，没有重建或执行 workload。
