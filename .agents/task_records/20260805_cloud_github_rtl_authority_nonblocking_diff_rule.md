# 云端 GitHub RTL 权威身份与非阻断差异规则

日期：2026-08-05

## 用户裁决

服务器 RTL 应以云端 GitHub 权威仓库为准。服务器实际 RTL 与本地测试包生成时 expected
identity 不一致时，必须先查云端变更并做算子影响分类；identity difference 本身不得阻止
服务器 compile/run，最多进入 return 身份和影响报告。影响其它算子族时主动通知对应 owner。

## 云端事实

- repository：`xlsjdjdk/Trassic2.0_RTL`
- branch：`master`
- cloud head：`0ccae916ef61904a64d6cf8ec1d1931b45e428d8`
- local expected：`e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- compare：12 commits / 11 files / +497 / -30
- compare URL：
  `https://github.com/xlsjdjdk/Trassic2.0_RTL/compare/e1fb0f7bb2761d6c804867de0c5d2cb77554c48d...0ccae916ef61904a64d6cf8ec1d1931b45e428d8`

p6 return 中不匹配的三个实际编译叶
`Array_Request_Manager`、`Buffer_AG_Idx_Queue`、`RD_Data_Channel`
全部位于上述云端变更集中。云端还改变ROW-LC输入FIFO、SA入口valid条件和全局请求队列深度，
因此影响GAP、serialized/native Conv、QAdd和node0075共享数据路。

## 公共规则修改

新增：

`CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`

核心执行语义：

1. actual/local RTL SHA差异为return provenance，不是simulator前退出条件；
2. compile成功必须继续run；
3. return优先查询云端repository/branch/commit和commit diff；
4. 无关差异不阻断当前算子；相关差异继续消费本次动态结果并通知owner；
5. 云端暂不可访问仍保留动态证据，只限制跨版本E4/E5归属；
6. package-local manifest/observer错误仍保持compile前fail closed，不与服务器RTL差异混淆。

## p6纠偏

p6的public-surface observer修复有效，production compile/elaboration/link成功；但旧runner在第一条
simulator命令前因3/8 identity mismatch退出。该终态由新用户裁决撤销为
`SUCCESSOR_REQUIRED_CLOUD_RTL_NONBLOCKING`。fresh后继必须绑定云端影响审计，并证明模拟的
actual/local SHA差异不会阻止到达simulator stub。

## Claim boundary

本记录证明云端master身份、e1fb0f7→0ccae91差异范围和公共规则裁决；不声称服务器三个actual
文件已逐字节等于cloud head，也不声称任何受影响算子已在新RTL上通过natural terminal或formal D。
