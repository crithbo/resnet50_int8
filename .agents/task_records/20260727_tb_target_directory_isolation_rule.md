# TB 目标目录隔离规则增量

日期：2026-07-27

用户要求：若测试需要修改 TB，只能修改本轮粘贴/命令传入的目标目录中的 TB，
不得修改其他目录下的同名文件。

## 更新

- 文件：`.agents/rules/服务器测试包生成规则.md`
- 规则 ID：`CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001`
- 更新后 SHA-256：
  `e4b4a215a60a3efbca83d00998d9618b17c8fb591aadb0a537828869a276b1ee`

规则要求：

1. TB 写入目标只能由唯一服务器命令显式传入的 `NDP_copyXX` 根目录与 manifest
   相对路径共同确定；
2. 写入前必须规范化并确认唯一、根内、非 symlink/junction 逃逸；
3. 禁止按 basename、递归搜索、glob 或“第一个同名文件”选择目标；
4. 其他目录下的同名 TB 不得修改、覆盖、替换、备份或恢复；
5. install、run 和 restore 始终绑定同一个规范化绝对路径并保存身份收据。

本轮未修改任何 TB、observer、功能 RTL、测试包或服务器回传资产。
