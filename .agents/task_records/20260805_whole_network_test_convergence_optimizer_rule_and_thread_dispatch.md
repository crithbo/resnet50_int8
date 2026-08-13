# 整网测试收敛优化专项规则与独立会话派发

日期：2026-08-05  
主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
创建请求：`client-new-thread:c54f9248-5090-4066-8ac2-aa3163d8331d`  
正式 task：`019fd276-14c5-7800-94db-87ebfb9ce632`  
标题：`整网测试收敛优化与规则审计`

## 1. 用户目标

建立一个不接管算子族的独立方法优化会话，基于前述服务器错误、当前规则、本地生成器与
validator、机器报告和五个待运行包，研究如何减少服务器测试次数和墙钟，更快完成整网闭环。

## 2. 已发布专项边界

- 新规则：`.agents/rules/整网测试收敛优化专项规则.md`
- dispatch SHA256：`20b3ac75123719ace1910372df3025d1d28f69c43f5ba3867c10cb7bce3fd06a`
- 已接入 `.agents/rules/生成前必读索引.md` 与 `.agents/plan.md`。
- owner 只做方法审计、成本账本、共享 validator/反例设计、测试顺序和规则提案。
- owner 不修改 current package、算子 config/golden/observer/runner、功能 RTL、plan 或其他规则；
  不上传/运行服务器、不取 lease。
- natural terminal、正式 D conjunction、E4/E5、runtime-D absent、workload provenance、禁止
  host 内部 tensor replay 和 RTL 授权门不可降低。

## 3. 首轮输入

- 云端功能 RTL 权威：`xlsjdjdk/Trassic2.0_RTL/master@0ccae916ef61904a64d6cf8ec1d1931b45e428d8`
- 本地 `NDP_copy01/rtl` tree SHA256：
  `c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093`
- current server rule SHA256：
  `36f6596c913120c24725da95e269200ecff4b25130d4eefe8d99d21c7b2e7457`
- current config rule SHA256：
  `30d0b20979e639d6bd9d0ec81f5e920da19733f0b2e3fe7ba751ef7e44b972d1`

当前五个唯一可运行包已精确写入创建提示：GAP v40、serialized Conv v47、QAdd v35、
native Conv p7、node0071→node0075 bank-row v9。owner 不得重建或替换它们。

## 4. 强制交付

1. 服务器轮次浪费机制排行榜及可避免墙钟/次数估算；
2. “规则已有但实现未落实”与“本地过度严格”清单；
3. 共享 validator、负控和反例登记表方案；
4. 当前五包的运行顺序建议；
5. 最多三项可立即由主线裁决的改进；
6. `artifacts/operator_config_validation/r5-whole-network-test-convergence-optimizer-v1/report.json`；
7. `.agents/task_records/20260805_whole_network_test_convergence_optimizer_v1.md`；
8. 主动向主线提交 `OPTIMIZATION_FINDINGS`、`TEST_ORDER_PROPOSAL` 与规则反馈。

## 5. 当前裁决

`RULE_FILE_READY / OWNER_TASK_ACTIVE`。Codex app 已建立正式 task
`019fd276-14c5-7800-94db-87ebfb9ce632`；工作树采用 `startingState=working-tree`，使会话可见
本轮尚未提交的 current 规则和计划。首次 30 秒状态回收显示 owner 已核验 dispatch SHA，并正按
UTF-8 分文件完整重读必读规则；尚未修改 current package 或进入任何服务器动作。
