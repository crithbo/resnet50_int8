# 三份正式 return 分发与用量限制恢复审计

日期：2026-08-05

主线/return target：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## Return 分发

### QLinearAdd node0007 split-C v29

- owner：`019fa2c0-b647-7a91-93bf-d21a173487e3`
- return bytes/SHA256：
  `209242 / 3839a9985f18483db4a4a784dbc7169103b4168b2a8eb4d3d11df07a96cbe1ff`
- source bytes/SHA256：
  `26171333 / c92985b32e31c30ffcb023a6b637a6b059748e5395e2eabac2a65e3ae79c0af3`
- adjacent sidecar：absent；只豁免外部传输收据。

### serialized Conv node0004 v36

- owner：`019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return bytes/SHA256：
  `102854 / f98d448113aafb78c80cbab6cd002e8b783325082a79ae98cf265ffebc38bca5`
- source bytes/SHA256：
  `5845330 / 08a7d79c50896c18665d551c32522fc39f0f90f4802a8797caa024f4ac474bc2`
- adjacent sidecar：absent；只豁免外部传输收据。

### Conv native-four-lane historical v1

- owner：`019fc783-1146-7901-9e40-64d0ed8e052d`
- return bytes/SHA256：
  `121996 / 8166c8dd85aece80714d051c7d88591f181e4bd35c5c74dc91aa90554867fd44`
- exact source v1 bytes/SHA256：
  `46027937 / 5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f`
- current p4 SHA256：
  `c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e`
- v1 return 必须绑定 v1，不得冒充 p4 return；v1/p4 均不得覆盖。

三个 owner 均已由任务工具成功唤醒并进入 in-progress。

## 用量限制审计

- GAP latest turn 明确 `failed`，错误为 usage limit；它在 v33 RETURN_ANALYSIS 后、successor
  构建完成前中断。主线已从 machine report/冻结资产断点恢复同一 owner，禁止重做 raw
  return 或覆盖 v33。
- node0075 latest turn completed；`PACKAGE_RELEASE=NONE` 的首因是 e1fb0f7 barrier opcode
  没有 live decode/drain/visibility semantics，不是用量限制。用量限制只阻止 owner task
  record 落盘；该 record 已恢复：
  `.agents/task_records/20260804_node0075_e1fb0f7_producer_visibility_barrier_field_leaf.md`，
  SHA256=`83cdfdecf9640b9111da70a5db8abdd25718bcc46506b7f5a80a9f59f6d1beea`。
- serialized Conv、QAdd、native Conv、Quantize、MaxPool、Dequant、Requant、View 的最新
  审计 turn 均 completed；没有证据表明它们因用量限制遗留已收 return。

若 GAP 同一任务再次因账号级用量硬限制失败，应回传 `QUOTA_BLOCKED`，不得留下未审计
半成品。

## Current 边界

- active RTL：
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- NDP RTL tree：
  `70334ce5f9addcfa409d566e7f7215b9870f815a7af3ae647`
- existing ZIP immutable；
- actual compile identity、natural terminal、formal D 仍由正式 return 证明；
- 不修改功能 RTL，不上传、不运行服务器、不取 lease。
