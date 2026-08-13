# Mandatory unbounded waveform gate v2

日期：2026-08-11  
owner：`optimizer.whole-network` / task `019fd276-14c5-7800-94db-87ebfb9ce632`  
状态：`FINAL_SHARED_WAVEFORM_GATE_READY`

## 输入与读取收据

- `.agents/agent.md` SHA256=`7a6fe116109b2c7953f3e1ff223160801e1d4df4ac6bfffc394c5ce4598294e4`
- `.agents/rules/生成前必读索引.md` SHA256=`a69fc20ca32891912fb85b6060c743b7e25dbfc1ff690591432ccf1c4516bc86`
- `.agents/rules/服务器测试包生成规则.md` SHA256=`3e0bc7e5796492ac3aa091ef7c990aa594aeb64cad929db8b8449fc5fdcca438`
- `.agents/rules/整网测试收敛优化专项规则.md` SHA256=`b8ef4120a644e08aef6e9ce9bc2dc7ceb70b24dfd1d7bcd3f96becee9db4b596`
- `.agents/plan.md` SHA256=`fdf61ede9b62219efd389d1df0242dfbebb0cdd37dc1ccee5318cb07e833306a`

## 完成内容

共享门 epoch=`waveform-mandatory-v2-01ca6d7cd4a4a270`，fingerprint=
`01ca6d7cd4a4a2703317cad447029fa011560dc4ec19bd40a8cce3f49c3aee3c`。

next-fresh package 必须绑定 `DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0`，默认抓取
`tb_NDP_Top_new_phy` depth 0 全层级。仅 path/SHA-bound 证明因果无关的 exact scope
可删除；未知 scope 保留。运行后发现并流式回收磁盘上全部 `wave.vpd`/shard，逐文件记录
bytes/SHA/format/completeness；波形无 ZIP、解压或单文件 byte cap，不截断、不采样、不按大小删除。

正式 return finalizer 的 waveform-only 增量已经在本 worktree 通过测试：

- simulation 已启动而无波形：仍原子发布 compile/core return，但 disposition 固定
  `EVIDENCE_INCOMPLETE`；
- compile/simulation 未启动：允许无波形并保留 compile-core；
- natural：波形 completeness=`COMPLETE`；timeout/HUP/INT/TERM/nonzero：已有波形
  completeness=`PARTIAL`；
- 大文件复制、ZIP 和 SHA 使用流式路径；VPD member 使用 ZIP stored，避免对已压缩格式再次耗时压缩；
- 本地入口支持 return 安全提取、VPD identity、Verdi/DVE/vpd2vcd 发现与打开命令。

## 验证

- focused unittest：`40/40 PASS`；
- `py_compile`：3 个 waveform/return helper PASS；
- 9 个 JSON/schema/contract/fixture parse PASS；
- scoped `git diff --check` PASS；
- 8 MiB synthetic VPD 流式回收、formal return 和 SHA 正控 PASS；
- dump=0、sim-started missing wave、allowlist漏波形、hard cap、无证据裁剪、self-inclusion、
  path escape 等负控均 fail closed。

机器报告：
`artifacts/operator_config_validation/r5-whole-network-waveform-mandatory-return-v2/report.json`，
bytes=`6333`，SHA256=`735362f2db91a70ea11c9ee21694ca9a827004beb8e263975e5a5a3b0777974e`。

## 主线同步边界

新 waveform schema/tool/contract/fixture/tests 与 gate registry 可按机器报告 exact receipt 同步。
但下列四个 post-sim 文件在本 worktree 的基线落后于 current mainline，禁止整文件覆盖：

- `tools/server_post_sim_return.py`
- `schemas/server_post_sim_return_request_v1.schema.json`
- `contracts/server_post_sim_return_next_fresh_dispatch_v1.json`
- `tests/test_server_post_sim_return.py`

必须按
`artifacts/operator_config_validation/r5-whole-network-waveform-mandatory-return-v2/post_sim_waveform_semantic_merge.json`
做 waveform-only 语义合并，并保留主线 `PARTIAL_EXIT_RULE_ID`、profile validator、fixture harness
和所有 partial-exit 正负控。README 未由本 owner 修改；精确提案位于同目录
`README_HARDWARE_SIM_ENTRY.patch`。

## 未覆盖限制与边界

- 未在本地运行 VCS；真实 `wave.vpd` 生成需由同步后的第一份 fresh package 做额外查验；
- 无 vendor viewer 时本地只完成 VPD 身份/提取/打开命令，不能解码其信号语义；
- 无配置 byte cap 不等于无限物理磁盘，服务器仍需满足磁盘、文件系统和 ZIP64 环境条件；
- 没有修改/重建 current 或 pending package，没有 family 派发、服务器动作、RTL/config/numeric、
  public rule、`agent.md` 或 `plan.md` 修改。

波形仅是诊断证据，不替代 qualified observer、natural terminal、formal D、E4/E5、合法 workload
provenance、runtime-D absent、RTL 授权门或禁止 host 内部 tensor replay。
