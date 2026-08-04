# 根目录可恢复整理收据

日期：`2026-08-04`

主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 裁决

本轮只整理根目录中已经确定为临时、重复、失败镜像或历史复现的未跟踪对象。未直接删除
任何内容；全部对象以原目录树可逆移动到：

`artifacts/q/0804`

选择短归档前缀是为了避免 QAdd 临时树的深层成员在 Windows 上超过路径字符限制。第一次
较长的归档前缀在复验时暴露长路径，随后整体移动到上述短前缀；相对目录树和内容不变。

## 移动范围

- 空 shell write probe 与空 return extraction parent；
- GAP v28 read-only return extraction tree；
- QAdd split signal/TERM scratch tree；
- 历史 return analysis scratch；
- 孤立 focused-compile `a.out`；
- 失败 Trassic clone；
- 已被 current `Trassic2.0_RTL`/df23e4d 取代的 1c49bd1、b7acbe5 镜像；
- 历史 native ring4 reproduction tree。

共移动 `6589` 个文件、`509945703` bytes。每个原始根的 files/bytes/tree SHA256、旧路径、
新相对路径和理由均记录在：

`artifacts/q/0804/manifest.json`

tree receipt 定义为：

`SHA256(UTF8(join(sorted(relative_path|bytes|file_sha256), LF)))`

## 明确保留

- `.agents`、current plan/rules/task records；
- `artifacts/operator_config_validation` 中所有当前包、audit、report；
- `server_returns` 与用户正式 return；
- `configs`、`contracts`、`jsons`、`outputs`；
- `NDP_copy01`、current `Trassic2.0_RTL`；
- `resnet50_pipeline`、`tools`、`tests`。

## 验证

- 移动前确认全部 source/destination 规范化绝对路径位于当前 workspace；
- 候选范围内 root Git tracked file=`0`；
- reparse/symlink scan 未发现命中；
- 移动后逐项重算十个 tree receipt，全部与 manifest 一致；
- 十个旧根路径全部不存在；
- 十二个活动根全部存在；
- manifest JSON parse PASS；
- `ROOT_CLEANUP_VERIFIED=true`。

本轮没有 reset、checkout、clean、覆盖、服务器动作、功能 RTL 修改、package/return 删除
或 plan/rules 修改。归档内容可按 manifest 原路径逐项恢复。

