# 全部当前 owner 任务的清理、Git 与 RTL 边界广播

日期：2026-08-04

主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 广播对象

以下当前计划涉及的 owner 均已通过任务工具收到同一份 receipt-only 通知：

- GAP node0071：`019fa366-cb1f-7ae2-880c-f527be0680cd`
- serialized Conv/SA：`019fa2c1-17df-7122-bcbd-a727aaf173f5`
- QLinearAdd node0007：`019fa2c0-b647-7a91-93bf-d21a173487e3`
- Conv native four-lane：`019fc783-1146-7901-9e40-64d0ed8e052d`
- QLinearMatMul node0075：`019fc775-8de0-7f10-bc4a-026a4673776f`
- QuantizeLinear node0074：`019fa2c0-572b-7f21-ac5a-96e773dde534`
- MaxPool node0002：`019fbe9f-3f2d-7071-806c-1ae72ae96391`
- DequantizeLinear：`019fa2bf-f9a5-7a73-ada3-b2b910721de3`
- RequantizeUint8：`019fa2bf-95cd-7502-82c8-6a48cf12d648`
- Flatten/View node0073：`019fa366-d218-7122-839c-0b52d83faf13`

通知不授权仅因 receipt 启动新工作；暂停任务只读消费，活动任务在下一次实际动作前重读
current 磁盘。

## 统一边界

### 根目录与历史资产

- 根目录项目说明收敛为唯一 `README.md`。
- 旧 `docs/` 与长版 README 归档到
  `.agents/archive/project_docs_20260804/`。
- 历史临时树、失败镜像和旧复现的隔离收据位于
  `.agents/task_records/20260804_root_workspace_cleanup_quarantine.md`。
- `artifacts/q/oldtests0804` 已由用户清空，广播时 entries=`0`。
- `artifacts/q/**`、旧包、旧报告及已不存在路径不得作为 current 输入；缺失本身不是漂移。

### Git

- branch：`codex/senior-operator-test`
- local HEAD：
  `75186a2`
- `origin/codex/senior-operator-test`：
  `75186a2`
- commit：
  `feat: checkpoint ResNet50 INT8 operator validation pipeline`
- checkpoint 包含根目录说明收敛、`.agents` 归档/规则/计划及当时的项目恢复资产。
- checkpoint 后的 e1fb0f7 RTL 同步说明、current mutable plan 和当前 return dispatch 仍是共享
  dirty worktree 增量；不得把 checkpoint 冒充完整 current 磁盘，也不得 reset/checkout/clean
  丢弃增量。

广播时 current 入口：

- `.agents/agent.md`：
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md`（广播前，mutable）：
  `e7fc830496910db2aea2c87ef4bbbcfb16f2f13355e2662e3404b2106d650c23`
- 生成前必读索引：
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`

### RTL

- `Trassic2.0_RTL` 是直接 Git checkout。
- local `HEAD/master/origin/master`：
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- `NDP_copy01/rtl` 与 `Trassic2.0_RTL/code/NDP_rtl`：
  `2260/2260` files byte-equal
- tree digest：
  `70334ce5f9addcfa409d566e7f7215b9870f815a7af3ae647`
- 用户确认真实服务器根也使用 e1fb0f7。
- sync report：
  `artifacts/rtl_sync/trassic_master_e1fb0f7_20260804/report.json`
- sync report SHA256：
  `c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c`

旧 df23e4d/d0aa87f 只可作 package build provenance/history，不得称 current active RTL。既有 ZIP
字节不改；正式 return 仍须回收 actual compiled production identity、natural terminal 与 formal D，
用户确认不能替代 E3/E4/E5。

## 协作约束

- 当前唯一主线/回传目标不变。
- 共享工作树长期 dirty；所有任务禁止 reset/checkout/clean、覆盖或删除其他 family 资产。
- 本族完成 return 分析或服务器包后，必须主动回传结构化结果与规则确证/非同义增量。
- 广播未授权 plan/public rules/functional RTL/其他 family 修改、上传、服务器运行、lease 或清理。
