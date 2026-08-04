# ADR-016：采用哈希绑定的项目补丁版本推进 R5

- 日期：2026-07-23
- 状态：accepted

## 决策

用户已选择“项目补丁版本”来源策略。活动 `ndp-sim` checkout 继续固定在
`ec12424516ae0304228dd2321d4e604fe225e04e` 并保持只读；所有修复只应用到一次性或显式物化的副本，统一身份为
`resnet50-ndp-toolchain-6144-v1`。锁定清单是
`contracts/ndp_patch_toolchain_v1.json`，任何 base commit、源文件 LF-normalized SHA-256、替换集合或补丁后 SHA-256 不一致均失败。

当前补丁只包含四个公共工具修复：

1. 地址规划器目标行数由 8192 修正为 RTL profile 的 6144；
2. DRAM LC 逻辑编号解析改为完整 `.LC<decimal>` 后缀并在不匹配时返回 `None`；
3. 零惩罚退火成功后显式返回 mapping，避免依赖第二轮缓存重试；
4. 退火结果合入而非覆盖既有显式绑定，保留不参与连接搜索的 `GROUP` 等资源。

第四项是在第一次 patched Decode 真实运行中由严格验证器发现：若仅补第三项，首轮零惩罚搜索会丢失 `GROUP0/GROUP1`；旧版漏 return 触发的第二次缓存加载偶然掩盖了该问题。补丁不得被描述为“未修改原版”。

## 证据与边界

- patched Decode mapping：零 penalty、无 fallback、无需错误重试、独立 bit 镜像通过；
- patched Decode execplan：两个隔离副本的 15 个确定性文件逐哈希一致，包、语义和逐请求地址校验通过；
- execplan SHA-256 仍为 `a0d8d9ac24b2277ff0a7222605992bb6a3c81e00882daf2197d94fcbe6aaa87e`，说明合法实例的编码未被改变；
- 这只证明补丁工具链和 Decode 基线，不证明任何 ResNet50 stage 的正式配置或 RTL 数值。

`contracts/resnet50_project_closure.json` 是当前 78 节点/133 stage 的 fail-closed 闭环表。它确认 W3 公式 78/78、W4 两个网络软件场景与 93 条边通过，同时保留正式目标配置 0/133、E4 0、E5 0 的真实状态。历史 `configs/` 中发现的 11 个 stage 候选只记录为 `historical_candidate_only`。

## 后果

后续 mapping/execplan evidence 若使用补丁，必须同时传入同一补丁清单并把它复制、哈希绑定进 bundle。未经 E4/E5，不得把候选推广到同类 shape 或整网。真实服务器入口仍由用户掌握；本项目不能自行发明 loader、启动、等待和回读命令。
