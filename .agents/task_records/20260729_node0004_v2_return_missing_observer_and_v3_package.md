# node0004 v2 正式回传与 package-local observer v3

日期：2026-07-29  
owner：Conv / SA  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 输入身份

- 用户回传：
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_node0004_hw_v2_failclosed_return.zip`
- bytes：`29241`
- SHA-256：
  `bda071d8cfdf96f8ec55369f91d16833ed1dee8e51c511de20af20be123fedb3`
- sidecar：未提供
- 绑定源包：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v2_failclosed.zip`
- 源包 SHA-256：
  `4bc0be9903e877b79cb11a82997ad5d6b5c6eed36666ec5a47771e83eb339446`
- 服务器包规则 SHA-256：
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- plan SHA-256：
  `c19363826061ac6842f1946a1fd860d87917902f3fad199d589a739ab0003b03`
  （mutable provenance）

没有读取、遍历、哈希或检查服务器现有文件/目录/Git/身份；只消费用户提供的
return ZIP 中的正式日志和源包本地身份。

## RETURN_ANALYSIS

机器报告：

- `artifacts/operator_config_validation/r5-node0004-hw-v2-return-analysis/report.json`
- SHA-256：
  `7884aeb695070eb2d55e96a8757c9217cecea21346e45698fa0f0cf0c9ced188`

回传 ZIP CRC 通过，8 项严格 exact-set 与 `RETURN_ALLOWLIST.json` 中 7 条内容
收据逐项匹配：

```text
package_preflight.valid             = true
package_preflight.preloaded_D       = 0
install_preflight.valid             = true
install_preflight.preloaded_D       = 0
compile_exit_status                 = 2
run_exit_status                     = 125
simulation_started                  = false
terminal_observed                   = false
formal_dynamic_readback_count       = 0
```

结果门：

```text
status                              = NODE0004_SERVER_FAILURE
readback_check_count                = 320
missing_count                       = 320
preloaded_target_count              = 0
mismatch_byte_count                 = 0
terminal_and_readback_gate          = false
```

裁决：`V2_RESULT_GATE_FAIL_CLOSED_CONFIRMED`。v1 的预置 D 假 PASS 已关闭；v2
在 compile/run/terminal/readback 任一不满足时正确失败，320 个 missing 没有被
golden 或旧 runtime 文件补齐。

本轮没有 node0004 数值证据，不能计 E4/E5；没有重跑 node0004 W3、mapping、
bitstream、execplan、SCA 或非 Conv 算子。

## FIRST_DIVERGENCE

`compile.log`：

```text
2396 Error-[SFCOR] Source file cannot be opened
2397 Source file "native_return_observer.svh" cannot be opened for reading
2398 'No such file or directory'.
2400 "/home/panqs/ndp/NDP_copy02/tb_NDP_Top_new_phy.sv", 5854
2401 Source info: `include "native_return_observer.svh"
```

分类：

```text
PACKAGE_COMPILE_INCLUDE_PATH_MISSING
PACKAGE_LOCAL_OBSERVER_INCLUDE_BINDING_MISSING
```

绑定的 v2 源包中：

- runtime D target 数量为 0；
- `native_return_observer.svh` entry 数量为 0；
- compile 命令没有 package-local observer include directory。

这是明确的包侧可合法修复问题，而不是 Conv/SA 数值、RTL 功能或服务器 merge
conflict 证据。合法修复不需要修改或安装服务器 TB/RTL：

1. 在包内 `tb_probe/native_return_observer.svh` 携带只读 observer；
2. compile 前核验精确文件 SHA 和 XMR elaboration-constant；
3. 通过 `VCS_EXTRA_OPTS=+incdir+<package_root>/tb_probe` 显式交给 VCS；
4. 将 precompile receipt 纳入 return allowlist。

## v3 包侧修复

新身份：

```text
install_name = r5_n4_hw_v3_obs
status       = PACKAGE_READY_NOT_RUN
```

v3 从冻结 v2 ZIP 展开，不重建数值 workload。冻结 v2 的 `workload/**` 与
`validation/**` 共 823 个文件逐路径、逐大小、逐 SHA 相同。

observer：

```text
package path = tb_probe/native_return_observer.svh
SHA-256     = 47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49
XMR refs    = 198
runtime-indexed generated XMR = 0
server install/write          = false
```

包属性：

```text
package files                    = 830
preloaded runtime D              = 0
functional_rtl_modified          = false
server_rtl_entries               = 0
server_tb_or_observer_install    = 0
package-local observer entries   = 1
result gate fail-closed          = true
return collector                 = explicit allowlist
```

两次全新目录独立构建的 package tree 和 deterministic ZIP 逐字节一致。

定向测试：

```text
Ran 10 tests
OK
```

负控包括 observer 篡改拒绝、v1 预置 D 拒绝、compile failure 不得 PASS、
package-local include 显式绑定、无服务器写、ZIP/sidecar/重复构建绑定。

## BLOCKER_DELTA

关闭：

- `B_NODE0004_PACKAGE_GATE_FAIL_OPEN`
- `B_NODE0004_SERVER_SOURCE_MERGE_CONFLICT`（v2 已越过原冲突位置并解析到 TB
  include；本轮没有再次命中冲突标记）
- `B_NODE0004_PACKAGE_OBSERVER_INCLUDE_PATH`（由 v3 package-local include 修复）

保持：

- `B_NODE0004_DYNAMIC_RESULT_PENDING`
- `B_NODE0004_SERVER_RTL_IDENTITY_UNBOUND`

## RULE_DELTA_PROPOSAL

无新增公共规则文本。v3 直接执行现有
`CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001` 和相对 include 的显式
include-directory/readability/SHA 门。

## PACKAGE_RELEASE

```text
status: PACKAGE_READY_NOT_RUN
install_name: r5_n4_hw_v3_obs
zip: artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v3_obs.zip
zip_sha256: 84c834de989c7912edfd711cd5fb2bdfe51e40998bb493d3e4ec5b99da9a331c
sidecar: artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v3_obs.zip.sha256
validation: artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v3_obs.validation.json
candidate_release: false
functional_rtl_modified: false
server_rtl_entries: 0
server_action: false
```

没有上传、运行或取得 lease。v3 仍须由主线裁决后交付用户运行。

