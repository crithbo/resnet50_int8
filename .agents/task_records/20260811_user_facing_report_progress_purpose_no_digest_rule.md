# 2026-08-11 用户汇报去摘要与版本进展/目的合同

## 用户要求

- 面向用户的汇报不再列出或索要文件大小、SHA/摘要或sidecar；用户回传也无需提供这些字段。
- 默认文件未丢失、传输未损坏；只有本地实际校验发现异常时才报告传输问题。
- 每次汇报必须说明上一正式回传版本已经推进到哪里，以及当前版本为了定位或解决什么。

## 稳定规则裁决

- 唯一语义owner为`.agents/rules/服务器测试包生成规则.md`中的
  `CDA-SERVER-USER-FACING-REPORT-PREVIOUS-PROGRESS-CURRENT-PURPOSE-NO-DIGEST-001`。
- `.agents/agent.md`只保存全项目入口引用，不复制规则正文。
- 用户提交return ZIP或可读取路径即默认构成外部传输身份；不再要求显式“传输无误”声明。
- 用户侧报告顺序固定为：上一正式回传版本进展→当前版本定位/修复目的→必要操作信息与blocker。
- owner→mainline、registry、manifest、task record、validator与内部审计继续静默保留exact机器身份；
  本次变化不放宽CRC、manifest、exact-set、formal result、natural terminal或E0–E5门。

## Changed surface

- `.agents/rules/服务器测试包生成规则.md`
- `.agents/agent.md`
- `contracts/active_rule_registry_v1.json`及owner registry中的活动规则收据随后同步。

未修改package、config、numeric、workload、RTL、active ndp-sim或服务器状态；未执行上传、运行或lease。

