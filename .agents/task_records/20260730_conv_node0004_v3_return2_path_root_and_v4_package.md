# node0004 v3 return(2) 分析与 v4 安装根重绑定包

日期：2026-07-30  
owner：Conv / SA  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 活动收据

- plan（mutable provenance）：
  `e3e44d47121b6c567b6e4c103b60c8012bbf09e8d904aabf9f1e4a03c016d97f`
- 生成前索引：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- 服务器测试包规则：
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- INT8-SA 专项规则：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- exact-tail 专项规则：
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

## RETURN_ANALYSIS

用户回传：

```text
path   = C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n4_hw_v3_obs_return(2).zip
bytes  = 54735
sha256 = 3e7cde965e5852bc6a900c688461f3498a11cc41563ca39f987cf227ea2c6277
```

`(2)` 不派生新身份；ZIP 内 `install_name=r5_n4_hw_v3_obs`。绑定源包：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v3_obs.zip
sha256 = 84c834de989c7912edfd711cd5fb2bdfe51e40998bb493d3e4ec5b99da9a331c
```

分栏裁决：

1. 外部 formal receipt：相邻
   `r5_n4_hw_v3_obs_return(2).zip.sha256` 不存在，故正式回执 fail closed。
2. ZIP：CRC 通过；10 项 exact-set 通过；`RETURN_ALLOWLIST` 9 条记录的大小和
   SHA 全部匹配。
3. package/install/observer：两份 preflight 均 `valid=true`，预置 D 为 0；
   observer SHA 为
   `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`，
   XMR static gate 198/198，runtime-indexed generated XMR 为 0。
4. compile/elaboration：`compile_exit_status=0`；`simv` 成功生成；
   elaboration 为 0 error、1 warning。上一轮 `slice_rst` interface compile
   failure 不得继承到本轮。
5. simulation：`run_exit_status=124`；仿真已启动，但没有自然 terminal。
6. 正式 D：期望 320、产生 0、missing 320、mismatch record 0、
   mismatch bytes 0。`missing=320 && mismatch=0` 不是数值通过。

机器报告：

```text
artifacts/operator_config_validation/r5-node0004-hw-v3-return2-analysis/report.json
sha256 = 51f7c66982d4bc22e664ba63bdbe447687a40a3747c84fdb747cd87b472fd1d4
```

## FIRST_DIVERGENCE

正式回执层首分歧：

```text
ADJACENT_RETURN_SIDECAR_MISSING
```

执行层首分歧在 `runs/c0/sim.log`：

```text
line 2217: 读取 v3 SCA：
  .../install/cfg_pkg/r5_n4_hw_v3_obs/runs/c0/sca_cfg.json

line 2221: SCA 的第一条 path 却指向旧 v2：
  install/cfg_pkg/r5_node0004_hw_v2_failclosed/runs/c0/install/execplan.txt

line 2235: ERROR: Cannot open file ...
```

c0 共出现 86 条同类 `Cannot open`。回查冻结源包发现：

```text
SCA/SCA_D files             = 54
stale v2 install path leaves = 846
sca_cfg input leaves         = 526
sca_cfg_D formal leaves      = 320
```

因此执行首分歧是
`PACKAGE_SCA_INSTALL_NAMESPACE_MISMATCH`，不是 Conv 数值、生命周期、服务器
RTL 或服务器 TB 缺陷。v3 runner 把 payload 安装到 v3 namespace，但全部 SCA
路径仍指向 v2 namespace，TB 从错误目录找文件；输入未装载后 c0 超时，320 个 D
自然全部缺失。

## E3 / E4 / E5

```text
E3 = FAIL
  run=124、无 natural terminal、formal D=0/320

E4 = FAIL
  E3 未通过；return sidecar 缺失；兼容 profile 未绑定服务器 RTL source identity

E5 = FAIL
  E4 未通过，且无独立新身份通过重跑
```

## 包侧合法修复

生成唯一新身份 `r5_n4_hw_v4_rootbind`。修复严格限于：

- 54 份 `sca_cfg.json` / `sca_cfg_D.json`；
- 846 个 path leaf 的 install prefix；
- runner 和 manifest 的新 package identity。

地址、length、Exec_Base、Exec_Length、Repeat_Num、矩阵、bitstream、execplan
内容、golden、observer 和功能 RTL 均未改变。验证结果：

```text
static inputs resolving under v4 root = 398
deferred tail inputs                  = 128
formal D targets initially absent     = 320
stale install paths                    = 0
non-path JSON semantics equal          = true
v3->v4 changed files                   = 56
v3->v4 byte-identical files            = 774
double-build package tree equal         = true
double-build ZIP equal                  = true
```

定向测试：5/5 PASS；v4 ZIP CRC 通过，830 个文件，单一 ZIP root。

## BLOCKER_DELTA

关闭（由本次真实 return 证明）：

- `B_NODE0004_SERVER_RTL_COMPILE_INTERFACE_MISMATCH`

v4 本地静态修复：

- `B_NODE0004_V3_STALE_INSTALL_NAMESPACE_IN_SCA`

新增：

- `B_NODE0004_V3_RETURN_FORMAL_SIDECAR_MISSING`
- `B_NODE0004_V4_DYNAMIC_RERUN_PENDING`

保持：

- `B_NODE0004_DYNAMIC_RESULT_PENDING`
- `B_NODE0004_SERVER_RTL_IDENTITY_UNBOUND`
- `B_NODE0004_NO_DYNAMIC_BASELINE`

## RULE_DELTA_PROPOSAL

无。现有服务器规则第 4、5 节已经要求 package-local SCA/SCA_D 路径必须从用户
提供的服务器根正确解析，并在 `Cannot open` 时立即失败。本次是 builder/validator
漏检，已由 v4 的逐 leaf path-resolution validator 和定向测试补齐，不是公共规则文本
缺口。

## PACKAGE_RELEASE

```text
status            = PACKAGE_READY_NOT_RUN
install_name      = r5_n4_hw_v4_rootbind
zip               = artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v4_rootbind.zip
zip_sha256        = 61e28a7c218230869ad1a5247023edb9bf8ee9af5a0660124fc8966ce5ad239e
sidecar           = artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v4_rootbind.zip.sha256
sidecar_sha256    = 9eafe4bf394ce2e5aaff650b1428313736baadb572bea7d7d5fbe5aa8ba71f08
validation        = artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v4_rootbind.validation.json
validation_sha256 = d22fde955b557ca40582ca2bbc0ad24efc691cc69026c6db59022ce7b30a7fdd
candidate_release = false
functional_rtl_modified = false
server_rtl_entries = 0
server_action      = false
```

单命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

```text
r5_n4_hw_v4_rootbind_return.zip
r5_n4_hw_v4_rootbind_return.zip.sha256
```

## 声明

```text
numeric_analysis_repeated=false
node0004_workload_rebuilt=false
source_package_consumed_read_only=true
source_workload_reused=true
non_conv_retested=false
server_inspection_outside_return_performed=false
server_upload_or_run_performed=false
```
