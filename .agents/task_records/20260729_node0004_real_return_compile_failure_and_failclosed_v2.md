# node0004 真实回传首分歧与 fail-closed v2 包

日期：2026-07-29  
owner：Conv / SA  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 用户授权与边界

用户提供真实回传
`C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_node0004_hw_v1_return.zip`
并明确要求先查错、尝试修复、生成新的测试包、回传主线，再继续其余 52 个 Conv
清单。该显式授权只允许新身份包侧修复，不授权修改功能 RTL。

- `.agents/plan.md` 当前 SHA-256：
  `53bd530998d6a3a57d5ac63302067d66ca46bef3e0e7b4adcba3bb1fbdcf7c35`
  （mutable provenance）；
- 生成前索引：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`；
- 公共算子规则：
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`；
- INT8 SA 专项规则：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`；
- 服务器包规则：
  `72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524`。

没有检查服务器现有文件、目录、Git、身份或名称；只读取用户提供的 return ZIP。
没有上传、运行或取得 lease。

## RETURN_ANALYSIS

输入回传：

- bytes：`6,669,912`；
- SHA-256：
  `d278b3684e22fdcaa9649f0884fe04b4f81ed8876ae069588d9a168f251e7619`；
- ZIP CRC：通过；
- 文件数：8；
- sidecar：用户未提供。

绑定的原包：

- `artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v1.zip`；
- SHA-256：
  `335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989`；
- 与主线冻结身份一致。

机器报告：

- `artifacts/operator_config_validation/r5-node0004-hw-v1-return-analysis/report.json`；
- SHA-256：
  `82f276bd1564b5bae97b99bfd54cd0eadde661122fb806f476f2c22cd494b102`。

本轮没有重复 node0004 数值分析，没有重建 W3、mapping、bitstream、execplan 或
SCA；只消费冻结原包作为只读身份/预置文件证明。

## FIRST_DIVERGENCE

回传状态：

```text
package_preflight.valid = true
compile_exit_status       = 2
run_exit_status           = 125
simulation_started        = false
formal_dynamic_readback   = 0
```

VCS `compile.log` 第 1781 行首先报告 syntax error，第 1783--1785 行把源定位为活动
服务器
`.../Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v:1`，
token 为 `<<<`，原文为：

```text
<<<<<<< HEAD
```

裁决：
`SERVER_SOURCE_MERGE_CONFLICT_COMPILE_FAILURE`。这是活动服务器源码中未解决的
merge-conflict marker；编译没有完成，仿真没有开始，因此该回传不含 Conv 数值、
terminal 或正式 D readback 证据。它不能计 E4/E5，也不能裁决 SA/Conv 配置数值。

此源码问题不能由配置包合法修复。重新运行的前置条件是服务器 owner 清除活动
`SA_PE_Float_Control.v` 的冲突标记并提供可编译源码；本任务没有修改任何 `rtl/**`。

## 原包结果门 fail-open

虽然 compile=2、run=125，回传 `SERVER_RESULT_GATE.json` 却声称：

```text
status              = THREE_PHASE_NODE0004_PASS
readback_count      = 320
missing_count       = 0
mismatch_byte_count = 0
```

逐项绑定证明：

- 原包声明的 320 个 `readback_checks.runtime_path` 全部已在
  `workload/runtime/` 中预置；
- 回传的 320 个 `actual_sha256` 全部等于这些随包预置的 runtime D 文件；
- 回传的 320 个 `golden_sha256` 全部等于包内 golden；
- 编译失败发生在任何 sim 之前。

因此返回的 320/320 不是硬件 readback，而是分析器把未被仿真改写的预置 D 与同包
golden 比较后的假通过。裁决：`PACKAGE_RESULT_GATE_FAIL_OPEN`。

## 包侧修复

新身份：

```text
r5_node0004_hw_v2_failclosed
```

修复严格限于包生成器/运行器：

1. 320 个 runtime D 目标不再随包预置；package preflight 和 post-install preflight
   均要求它们全部不存在；
2. 结果门只有在 `compile_exit_status=0`、全部 sim 的 `run_exit_status=0`、
   `missing=0`、`mismatch=0` 同时成立时才允许 PASS；
3. 返回收集改为明确 allowlist，只含状态、受限 compile/sim log、tail materialization
   和实际产生的 readback，不再递归收集 `simv.daidir` 等编译中间文件；
4. `candidate_release=false`、`evidence_level=E2_LOCAL_ONLY`、
   `functional_rtl_modified=false`、`server_rtl_entries=0`。

关键源码：

- `tools/node0004_assumed_hardware_server_runtime_v2.py`
  SHA-256=`d846e2dfc9927bd12e55841cafdcc887808337f4d2ca077bc6e91c5cd3829602`；
- `tools/build_node0004_assumed_hardware_server_package_v2.py`
  SHA-256=`388b98153c245aaf801aaa1b351f3966ce96ac4e9bb23c69d328d9c9b49a819f`。

两次全新目录独立构建逐文件相同，确定性 ZIP SHA 相同。v2 包文件数为 827；相比
v1 的 1147，恰好去掉 320 个预置 D 目标。

定向测试：

```text
python -m unittest \
  tests.test_node0004_return_analysis \
  tests.test_node0004_assumed_hardware_server_v2 -v

Ran 5 tests
OK
```

负控证明：

- v2 preflight 对 v1 包因 320 个预置 D 目标而 fail closed；
- `compile=2/run=125` 时 v2 gate 为 `NODE0004_SERVER_FAILURE`；
- 未产生 D 时 `missing_count=320`；
- v2 ZIP、sidecar、validation receipt 绑定一致。

## BLOCKER_DELTA

新增/重开：

- `B_NODE0004_SERVER_SOURCE_MERGE_CONFLICT`：服务器活动
  `SA_PE_Float_Control.v:1` 含 `<<<<<<< HEAD`，compile=2；
- `B_NODE0004_DYNAMIC_RESULT_PENDING`：本次没有开始仿真，正式 terminal/readback=0。

关闭：

- `B_NODE0004_PACKAGE_GATE_FAIL_OPEN`：v2 包已禁止预置 D，并把 compile/run status
  纳入 PASS 必要条件；
- `B_NODE0004_RETURN_RECURSIVE_COLLECTION`：v2 改为显式 allowlist。

保持：

- 最终 Trassic2.0_RTL commit identity 未绑定；
- E4/E5 仍为 0；
- 其余 52 Conv 在 node0004 有效动态结果前不得批量封包。

## RULE_DELTA_PROPOSAL

建议主线把以下通用门写入服务器包规则：

1. `readback_checks.runtime_path` 在 package tree 与 post-install tree 中必须不存在；
   golden 只能位于独立 `validation/golden` 命名空间；
2. result gate 必须把 compile、simulation、terminal/readback 三类状态做逻辑与；
   compile/run 非零时禁止只凭文件存在或 hash equality 判 PASS；
3. return collector 必须按 manifest allowlist 收集，禁止递归复制 compile/run tree。

## PACKAGE_RELEASE

```text
status: PACKAGE_READY_NOT_RUN
install_name: r5_node0004_hw_v2_failclosed
zip: artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v2_failclosed.zip
zip_sha256: 4bc0be9903e877b79cb11a82997ad5d6b5c6eed36666ec5a47771e83eb339446
sidecar: artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v2_failclosed.zip.sha256
validation: artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v2_failclosed.validation.json
candidate_release: false
functional_rtl_modified: false
server_rtl_entries: 0
server_action: false
```

该包只有在服务器 owner 先解决活动 RTL 的 merge conflict 后才值得重跑；否则它会
正确返回 compile failure，而不会再次伪造 320/320 PASS。
