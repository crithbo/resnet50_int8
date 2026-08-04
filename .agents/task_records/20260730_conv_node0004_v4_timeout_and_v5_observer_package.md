# node0004 v4 正式 return：外部 timeout 与 v5 observer 运行绑定包

日期：2026-07-30  
owner：Conv / SA  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 活动收据

- plan（mutable provenance）：
  `9cd2328a18ecd961e97db2baa7afa70a68b2ea01f7a92fbdcac25fae80a7e382`
- 生成前索引：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- 服务器测试包规则：
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- INT8-SA 专项规则：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- exact-tail 专项规则：
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

## RETURN_ANALYSIS

正式回传：

```text
ZIP path   = C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n4_hw_v4_rootbind_return.zip
ZIP bytes  = 73490
ZIP SHA256 = 14ae820aeba624d92189f482603f8777f9fd8c43c01a3e9b455b03fe0e5e0983
sidecar SHA256 = aba44451471615d1b2a330b17e7354d352cf5e0067e805f24e4c264ae80205ba
```

sidecar 内容精确绑定同一 ZIP 和文件名，formal receipt 有效。ZIP CRC 通过，10 项
exact-set 通过，`RETURN_ALLOWLIST` 的 9 条 size/SHA 收据全部匹配。

绑定源包：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v4_rootbind.zip
SHA256 = 61e28a7c218230869ad1a5247023edb9bf8ee9af5a0660124fc8966ce5ad239e
```

执行结果：

```text
package_preflight.valid       = true
install_preflight.valid       = true
preloaded D                   = 0
observer SHA/XMR precompile   = pass / 198 constant refs / 0 runtime refs
compile_exit_status           = 0
elaboration                   = 0 error / 1 warning
run_exit_status               = 124
natural terminal              = false
formal D produced             = 0 / 320
missing                       = 320
mismatch records/bytes        = 0 / 0
```

`missing=320 && mismatch=0` 不是数值通过。

机器报告：

```text
artifacts/operator_config_validation/r5-node0004-hw-v4-return-analysis/report.json
SHA256 = b59a6c6f1e514c9ffe885f8a081bd729a0f4296b7a0a9856b3c66cd5baea2690
```

## FIRST_DIVERGENCE

本轮已真实关闭 v3 安装根问题：

- `Using SCA cfg` 和 `Using SCA cfg D` 都回显 v4 根；
- 86 份 c0 execplan/matrix/bitstream 全部传输完成；
- `Cannot open=0`；
- `JSON config: 86 matrices loaded`；
- 随后出现 `Reg Started` 和 `INFO: slice start`。

最后一个确定正证据为：

```text
all 86 c0 payloads transferred
→ Reg Started
→ slice start
```

首个观察到的失败为：

```text
sim.log line 8818: Interrupt at time 25995990725
run_exit_status=124
classification=EXTERNAL_RUNNER_TIMEOUT
```

这不能解释为 RTL 自行死锁。return 还证明 v4 包存在更早的诊断证据缺口：

```text
PACKAGE_OBSERVER_RUNTIME_BINDING_AND_RETURN_MISSING
```

原因：

1. observer 源文件 SHA/XMR preflight 通过，且设计编译成功；
2. 但 simulator argv 没有 `+RETURN_OBSERVER`；
3. sim.log 没有 `[RETURN_OBSERVER] enabled`；
4. collector 没有收集 `return_observer.log`。

所以从 `slice start` 到外部 timeout 的内部状态完全未观测。本轮不能裁决 Conv
数值、lifetime、RTL stall/deadlock 或配置首分歧。

## E3 / E4 / E5

```text
E3 = FAIL
  external timeout、无自然 terminal、formal D=0/320

E4 = FAIL
  E3 失败；兼容 profile 未绑定服务器 RTL source identity

E5 = FAIL
  E4 失败，且无独立通过重跑
```

## v5 包侧合法修复

生成唯一新身份 `r5_n4_hw_v5_observe`：

- 保持 12h timeout 和 fail-closed 结果门不变；
- 启用只读 observer：slice0、stall/heartbeat、deep、accum-state；
- 各事件类有限限流；
- 每 run 写入独立 `return_observer.log`；
- collector 显式 allowlist observer 日志，单日志上限 8 MiB；
- 新身份所需 54 份 SCA/SCA_D 安装根机械重绑定；
- 数值 workload、地址、length、matrix、bitstream、execplan 内容、golden、
  observer 源码和 RTL 均未改变。

验证：

```text
SCA/SCA_D path leaves rebound = 846
stale paths                  = 0
static inputs resolve        = 398
deferred tail inputs         = 128
formal D initially absent    = 320
observer runtime enabled     = true
observer log allowlisted     = true
double-build tree/ZIP equal  = true
ZIP CRC/file count           = pass / 830
directed tests               = 4/4 pass
```

## BLOCKER_DELTA

关闭：

- `B_NODE0004_V3_RETURN_FORMAL_SIDECAR_MISSING`
- `B_NODE0004_V3_STALE_INSTALL_NAMESPACE_IN_SCA`

新增：

- `B_NODE0004_V4_EXTERNAL_RUNNER_TIMEOUT`
- `B_NODE0004_V4_OBSERVER_RUNTIME_BINDING_MISSING`
- `B_NODE0004_V5_DYNAMIC_RERUN_PENDING`

保持：

- `B_NODE0004_DYNAMIC_RESULT_PENDING`
- `B_NODE0004_SERVER_RTL_IDENTITY_UNBOUND`
- `B_NODE0004_NO_DYNAMIC_BASELINE`

## RULE_DELTA_PROPOSAL

无。现有 observer 与 signal-safe partial-return 规则已要求 observer 缺失时
fail closed，并禁止把外部 signal/timeout 写成 RTL 卡死。本次是 package runtime
binding/collector 的实现漏项，已由 v5 validator 和测试补齐。

## PACKAGE_RELEASE

```text
status            = PACKAGE_READY_NOT_RUN
install_name      = r5_n4_hw_v5_observe
zip               = artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v5_observe.zip
zip_sha256        = fb7a36e380c1329c29faf9170a0e117715bdc0d0198bc0568e47298d517844cb
sidecar           = artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v5_observe.zip.sha256
sidecar_sha256    = aec9876d78bee1e5bb0b275b8a31a603ddd47234d7b15a40e2f7e06c83437468
validation        = artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v5_observe.validation.json
validation_sha256 = 73d000f65860f311f83cd8c8043311b8b0eeaebfa914ef8e137ddfec08463464
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
r5_n4_hw_v5_observe_return.zip
r5_n4_hw_v5_observe_return.zip.sha256
```

## 声明

```text
numeric_analysis_repeated=false
node0004_workload_rebuilt=false
source_package_consumed_read_only=true
source_workload_reused=true
server_inspection_outside_return_performed=false
server_upload_or_run_performed=false
```
