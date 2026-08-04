# Conv node0004 v15 return 与 v16 current-rule successor

日期：2026-07-31  
owner：Conv / SA  
唯一回传主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

- return：
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n4_hw_v15_abpe_syntax_fix_return.zip`
- bytes=`28328`
- SHA256=`592d792e9f0d647f1a3d43bdc8b3a5bbffb1956d4ff908916d0f6d78cf9a94d2`
- sidecar file SHA256=`3f1af41064bf761235b01ef5d3f1e3fe56fe0e7a4d5d0315b344b9a137959102`
- sidecar name/hash 与 return 精确匹配。
- source v15：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v15_abpe_syntax_fix.zip`
- source SHA256=`65e5b50b00046d662d219b71054f7f3f64c5794c98bf87dc134b5b3dd09a2130`
- CRC、单根、allowlist exact-set、9/9 record size/SHA、source/install/package/observer
  identity 与 preflight 均通过。
- compile=`2`，run=`125`，signal=`NONE`。
- simulation 未启动；natural terminal=false；actual canonical progress=0；formal D=0。
- runtime fallback canonical 不是 observer 动态证据。
- E3=false、E4=false、E5=false；all-missing 不得解释为数值通过。

机器报告：

- `contracts/operator_config/node0004_v15_return_analysis_v1.json`
- SHA256=`768edf05fc2a4776a315bcbdf03ae4e411cd86a9a03dc129d7e87d71651bf879`
- analyzer：
  `tools/analyze_node0004_v15_return.py`
- SHA256=`4a880ea024cae9658adc30a79232cfabaeff0e80bea96f1c2f813c17d7789120`
- exit=`0`

## FIRST_DIVERGENCE

VCS 首错：

```text
tb_probe/native_return_observer.svh:2433
keyword 'endtask' is missing
token is 'end'
```

`return_obs_write_abpe_state` 使用：

```systemverilog
task automatic ...;
  begin
    ...
  end
end
```

最后一行应为 `endtask`。这是 package-local read-only observer 的确定语法错误；
尚未进入 elaboration/simulation，不能归因于 Conv 配置或功能 RTL。

最小修复只将该 task 的最后一个 `end` 改为 `endtask`。聚焦语法 TB：

- `outputs/diagnostics/node0004_v15_return_v1/abpe_observer_task_terminator_syntax_tb.sv`
- SHA256=`b7d12baf082d53283a5d24f2d42712c79000f2d62ecb2e90d456ef17d7420d66`
- Icarus compile=`0`，run=`0`
- 输出：`PASS ABPE observer task endtask syntax`
- 本地语法证明不替代服务器 VCS/E3。

## Current-rule integration

post-generation current receipts：

- plan mutable：
  `532d176ed70fb630dbc797263409887a2d32bafecd5f9af3a21077d56a157bfe`
- index：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- server rule：
  `0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a`
- INT8-SA：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- hardware entry：
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

v16 包内绑定：

- `CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`
- `CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001`
- 以及既有 final-ZIP、observer、canonical、return 联合门。

普通包 runtime：

- 只接收一个用户提供的绝对 server root；
- 不绑定、不枚举、不哈希、不预检既有 server RTL/TB/Makefile/filelist/support/Git/
  README/observer/source tree；
- package-local observer expected SHA 只从 final
  `package_manifest.json:observer_binding_four_way.source.sha256` 读取；
- runner 内 64-hex hard-coded SHA 数量为 0；
- 真实 compile/run 自然裁决服务器环境。

## Runner positive control

从 final ZIP fresh extract 真实执行 `PREPARE_AND_RUN.sh`，使用安全 `make` compile stub：

- package preflight valid；
- fresh namespace install 完成；
- installed preflight valid；
- runtime D absent；
- package-local observer guard 从 manifest 读取 expected SHA，identity valid；
- 实际到达唯一 `make ... compile` 调用；
- compile stub invocation count=`1`；
- stub expected exit=`73`；
- runner actual exit=`73`；
- package tree 执行前后 exact-set/size/SHA 不变。

actual compile argv：

```text
-f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0
TB_DUMP_FSDB=0 RUN_DIR=<fresh run>/compile
VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+<fresh package>/tb_probe
```

负控：fresh extract 后篡改 package-local observer，使其 SHA 与 final manifest 不同；
runner 在 compile 前 fail closed，compile stub invocation count=`0`。

报告：

- `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v16_abpe_runnerpc.runner_positive_control.json`
- SHA256=`9f363a00cd4995d648c9f6ecf722a30d0269aefc8b2fb62914aab7f7b4fa35e3`
- validator：
  `tools/validate_node0004_v16_runner_positive_control.py`
- SHA256=`6020537d16620fc4daf619ec01008df77c5c73a8f0b8a37cbbd15fb1161a88d9`
- exit=`0`
- status=`RUNNER_PREFLIGHT_TO_COMPILE_POSITIVE_CONTROL_PASS`

该正控仅证明 package runner 控制流，不调用真实 VCS/仿真，不建立 E3/E4/E5。

## PACKAGE_RELEASE

v15：

```text
QUARANTINED_PACKAGE_LOCAL_OBSERVER_MISSING_ENDTASK
```

规则发布前产生的中间 v16 已删除，没有交付或运行。

唯一 fresh final successor：

- package：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v16_abpe_runnerpc.zip`
- bytes=`5814860`
- SHA256=`e0f6d1effba71e505d22203ec2a43b4a538aaeeb515b806f6953603a342bcec1`
- sidecar file SHA256=`b12b0313120e758966517f84ebc7ec70261f0f93cf3db936a9eddad419ba1d71`
- status=`PACKAGE_READY_NOT_RUN`
- candidate_release=false
- server RTL entries=0
- configuration/workload/golden 与 v15 保持一致；
- 仅修 package-local observer `endtask`，并吸收 current runtime/preflight 规则。

单命令：

```bash
bash r5_n4_hw_v16_abpe_runnerpc/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

预期 return：

```text
r5_n4_hw_v16_abpe_runnerpc_return.zip
r5_n4_hw_v16_abpe_runnerpc_return.zip.sha256
```

最终 ZIP 独立自检：

- report：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v16_abpe_runnerpc.validation.json`
- SHA256=`eb9615f7bdc6d3ab07332f4e4e008437cbfcd21b5bfe5765fdee42924f711ff8`
- validator：
  `tools/validate_node0004_v16_final_zip.py`
- SHA256=`a40acc057fc01f73851d12444efb1e78f796e4f52876bd1a09f730113c50156b`
- exit=`0`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- errors=`0`
- all required negative controls fail closed；
- independent rebuild ZIP SHA 与最终 ZIP 相同。

## BLOCKER_DELTA

关闭：

- v15 return receipt/source/allowlist 身份；
- v15 observer missing-endtask 首分歧；
- current server-rule receipt drift；
- runner 第二份 hard-coded observer SHA；
- real runner preflight→install→guard→compile 正向链未证；
- wrong package-local identity compile 前 fail-closed 未证。

打开：

- `B_NODE0004_V16_DYNAMIC_RETURN_PENDING`。

保持：

- E3/E4/E5 均未建立；
- node0004 仍无真实 simulation/natural terminal/formal D；
- server source identity 未绑定，只限制版本归属/production release，不预阻止真实动态事实。

## RULE_DELTA_PROPOSAL

`NONE`。本轮新发布规则已覆盖发现的共因，不再提出重复规则。

## Scope

- `numeric_analysis_repeated=false`
- `node0004_workload_rebuilt=false`
- 只读复用 v15 冻结配置、mapping/bitstream/execplan/SCA、矩阵和 golden；
- `.agents/plan.md` 修改=false
- 公共 rules 修改=false
- 功能 RTL 修改=false
- 服务器检查/上传/运行=false
- 本地安全 compile stub 不是真实服务器动作，也不升级 E3/E4/E5。
