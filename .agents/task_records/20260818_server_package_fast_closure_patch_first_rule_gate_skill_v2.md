# 服务器包快速收敛、补丁优先与六聚合门 v2

日期：2026-08-18

## 裁决

本轮将“构包速度慢且成功率未明显提高”裁决为两部分：

- `RULE_SEMANTIC_ERROR`：多个final-ZIP、first-fresh、exact identity与helper门重复组成阻断联合，
  且部分项目不能映射到真实服务器失败；
- `IMPLEMENTATION_ESCAPE`：build profile仍把传输SHA、validator/fixture identity和旧细门当作fresh
  重跑条件，抵消了changed-surface复用。

未裁决为“子代理天然无法触发Skill”。真正的问题是入口没有把Skill触发和持久family owner路由写成
新会话的显式第一步，同时旧profile仍按全量fresh模型执行。

## 实施

1. `agent.md`增加全新会话五步接手流程，并明确family派发、构包/修包、return分析、successor和
   incident必须调用`resnet50-server-package-flow`；注册family不得由临时子代理替代。
2. 服务器规则加入patch-first：未执行的local/pending包修补当前revision；已执行/绑定return后才
   fresh successor；未变资产与PASS门复用，逐错误完整重建禁止。
3. build gate registry保留历史21个gate供诊断，但blocking allowlist只含六个聚合目的；其它统一
   record-only。SHA/validator identity不再是传输阻断。
4. build profile支持`PATCH_UNRUN_REVISION`，要求`prior_server_execution=false`；已执行包原地patch
   fail closed。只运行allowlist内廉价门和final subgate，未变/历史门不重跑。
5. `NDP_copy01`入口移除旧FSDB/Verdi路径，写明current observer-only与package-local TB VCD双模式。

## 验证

- focused unittest：38/38 PASS；
- py_compile：PASS；
- active-rule audit：14/14规则、165个唯一rule definition、0 duplicate/error/warning；
- synthetic build profile：contract PASS，5 blocking、15 record-only、1 not-applicable；
- Skill frontmatter manual quick_validate-equivalent：PASS（bundled脚本环境缺PyYAML，未安装依赖）；
- git diff --check：PASS。

## 边界

本轮未修改`.agents/plan.md`，未修改或重建任何current/pending/tested package，未改config、numeric、
workload或functional RTL，未上传、运行、取lease或连接服务器。natural terminal、正式D、E4/E5、
合法workload provenance和RTL授权门均未降低。
