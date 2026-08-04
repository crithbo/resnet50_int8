# Requant guard-only SFU event-edge runtime-root v2 包记录

日期：2026-07-27

## PACKAGE_RELEASE

```text
identity = rq_node0001_guardonly_sfu_eventedge_runtime_root_v2
state = PACKAGE_READY_NOT_RUN
server_lease = NONE
candidate_release = false
counts_as_E4 = false
counts_as_E5 = false
result_profile = VERSION_UNBOUND_DIAGNOSTIC_ONLY
```

ZIP：
`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_eventedge_runtime_root_v2.zip`

- bytes：67,761
- SHA256：
  `5184a096ec1787a774439a88235ae29ebc2102befdd179bd321474023c02f313`
- sidecar：
  `rq_node0001_guardonly_sfu_eventedge_runtime_root_v2.zip.sha256`
- ZIP entry count：38
- payload tree SHA256：
  `d58041693c5e80b81ec345e6a02e38a27d2867e8a066e2f4bfc7a987d872e211`
- `rtl/` entry count：0

唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
```

预期回传：

- `rq_node0001_guardonly_sfu_eventedge_runtime_root_v2_return.zip`
- `rq_node0001_guardonly_sfu_eventedge_runtime_root_v2_return.zip.sha256`

## 当前读取收据

- `.agents/plan.md`：
  `581ee5b55d2d5b1df36d8cfc2937e3a3822c1108c835cbd8669c9d80820d22fe`
- `.agents/rules/生成前必读索引.md`：
  `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7`
- `.agents/rules/服务器测试包生成规则.md`：
  `72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524`
- `.agents/rules/RequantizeUint8算子配置规则.md`：
  `44e8ee38d1361f15d78bf5d7918fa10e4648370153178ad10d044fd5c9d26265`
- 新规则 ID：
  `CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001`

已废弃的服务器规则 SHA `2897fb6a...` 未进入最终包。

## 冻结来源与语义

来源 v1 ZIP 保持只读：

```text
bytes = 78068
sha256 = 31877dcf0f11a52a0822525e8f49312d25807f81884377f748425693c89b4a53
```

v2 从来源 ZIP 的 package-local 内容派生，没有读取、哈希或比较本地
`NDP_copy01/02/03`。23 个冻结语义文件的 path/size/SHA 与 v1 逐项相等，tree SHA256
保持：

`3f6c7116c72dcebcae9102a3d822c7f4d8f1e26b8005af1432e72e461559e222`

仅改变安装 namespace 文本、入口/runtime、README、manifest 和新增兼容收据；
SCA_D、execplan、地址、`Repeat_Num`、`Exec_Length`、workload、golden、
RequantGuard 和 expected writes 均冻结。

## 兼容 profile

- 只接受一个用户提供的绝对、可解析、可进入目录；不限制 basename。
- 不读取、遍历、哈希或比较服务器现有 RTL、Makefile、filelist、TB、support file、
  Git、README、目录树或历史 SHA。
- 不做固定服务器文件 up-front probe；`make` 的实际 compile 入口缺失或不兼容时自然
  失败，并通过 signal-safe finalizer 收集限量日志。
- 唯一允许事务式触碰的服务器既有文件是
  `<user_root>/native_return_observer.svh`；不搜索其他同名文件。
- observer 只读、不驱动；保存精确 byte backup，并只恢复同一路径。
- 删除了继承 base 中不可达的旧 server identity/collect gate，而非仅在入口禁用。
- 包内无功能 RTL。

## 验证

- 两个 fresh build 的最终 ZIP 逐字节一致。
- final ZIP exact-set、sidecar、安全路径、无重复项、无 `rtl/`、无 pycache：PASS。
- source v1 23-file semantic byte identity：PASS。
- 变量 root、无固定 `NDP_copy` basename、无 server source/focused/Git identity
  gate：PASS。
- 定向 unittest：7/7 PASS。
- 最终 fresh-extract self-check：PASS：
  - 任意 root basename 被接受；
  - 只触碰精确 observer；
  - 故意破坏 installed observer 时 restore fail-closed；
  - 恢复正确 installed bytes 后 preimage byte-exact restore；
  - compile entry 缺失时生成 bounded return ZIP+sidecar；
  - return 分类保持 `VERSION_UNBOUND_DIAGNOSTIC_ONLY`；
  - package tree 前后不变，无 pycache。

机器收据：
`artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_eventedge_runtime_root_v2.validation.json`
SHA256
`c3552ab8d4969c49fab553527ac08bb1cd02f7c871f0fe3675225e48ccdb0567`。

## RETURN_ANALYSIS

本轮没有服务器运行或正式 return。动态边界不变：

```text
last_proven_good =
  SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT
first_unobserved =
  selected coefficient SRAM output
  → ALU capture/tag/result
  → postprocess
  → normal outbuffer write
```

收到 v2 return 后，正式 D 与 observer 必须分栏；即使数值通过，也只定位版本未绑定
诊断首分歧，不计 E4/E5。

## BLOCKER_DELTA

```text
keep:
  - B_REQUANT_GUARD_DYNAMIC_DATA_PATH
  - B_REQUANT_SERVER_E4_E5
close: []
add: []
```

## RULE_DELTA_PROPOSAL

```text
[]
```

未修改 `.agents/plan.md`、`.agents/rules/**`、`rtl/**`、其他算子族资产、冻结 v1
package 或旧 return。
