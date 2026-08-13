# node0071→node0075 bank-row v9 return：stage01 producer-prefix 裁决

日期：2026-08-06  
Owner family：QLinearMatMul / node0075（只读消费 node0071 producer prefix）  
唯一结构化回传目标：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 1. Scope / current receipts

- 未修改 `.agents/plan.md`、公共规则、functional RTL、node0071/GAP 或其他 family 资产。
- 未上传、未运行服务器、未取 lease。
- current mutable plan 在开始分析时为
  `eb1d47d6e24430cb0c62b91790c46d3003369935ed52185d1377b253c4645bca`；
  并行任务更新后的最终只读收据为
  `9b3d2f7469a5e405ecc9183916eba1dd773880a47801cdbe94def90bb319f7f8`。
- `.agents/agent.md`：
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/rules/生成前必读索引.md`：
  `e3c7ed8a651d9b1d8b4d67e4ec29fe50c6441f8410cb60c9bd7f95359ccd4bf6`
- `.agents/rules/服务器测试包生成规则.md`：
  `36f6596c913120c24725da95e269200ecff4b25130d4eefe8d99d21c7b2e7457`
- `.agents/rules/算子配置规则.md`：
  `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- `.agents/rules/NDP硬件字段语义.md`：
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/INT8_SA点积专项规则.md`：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/精确UINT8量化尾专项规则.md`：
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

## 2. Formal return / source identity

正式 return：

`C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-08\r5_n71_n75_0cc_bankrow_v9_return.zip`

- bytes：`150747`
- SHA256：
  `fb1aef2c0699b5115f1e461cbca827a018359288c06cb6024451bc9ba3486482`
- adjacent sidecar：缺失；只按用户给出的正式路径/bytes/SHA 担保豁免外部 transport。

冻结 source package：

`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_n75_0cc_bankrow_v9.zip`

- bytes：`3780255`
- SHA256：
  `f0034876998f636ea0cdd473f830daed896cc7b315fdb73ab617e59d6f3c8165`
- source manifest SHA256：
  `242abe93ed9d290ff95688d1f4a259e2f349e06b235fde67861221f0ee116350`

内部 receipt 全部闭合：

- return/source ZIP 均 CRC、single-root、path、duplicate、symlink PASS；
- return exact set=`20`；
- `RETURN_MANIFEST` 逐成员 size/SHA 与实际 exact set 一致；
- `RETURN_ALLOWLIST` copied exact set 一致；
- returned source manifest 与冻结 source bytes 相同；
- returned SCA/SCA_D 与冻结 source bytes 相同；
- package preflight：
  `PACKAGE_PREFLIGHT_PASS`，package/workload=`507/491`，
  external/B/CONFIG/formal-D=`16/128/32/144`，A preload=`0`；
- install preflight：`491` 文件 exact；
- runtime-D pre-sim：`144/144` 全部 absent。

## 3. Actual compiled cloud RTL identity

production compile=`0`，所以 actual/cloud identity 差异没有阻止 simulator。

return 共回收 `9` 个实际编译关键 leaf：

- `6/9` bytes/SHA 精确匹配批准的
  `xlsjdjdk/Trassic2.0_RTL/master@0ccae916ef61904a64d6cf8ec1d1931b45e428d8`；
- 以下 `3/9` 位于本算子受影响 Buffer causal cone，且不匹配 0cc Git blob：
  - `Array_Request_Manager.sv` actual
    `7892b4345b3a71024126b57a3a0126c489e0bffa2f520e64fa6cf2ed705f9894`
    vs 0cc
    `026019ed9643b3b7d83bc0888c4f5b89fc4776015524df1c69bacbab5315e557`
  - `Buffer_Manager.sv` actual
    `6605f44341fe5e7edfe8238b25b8836d35ee3100e84fe30fdb2ecabab1249c19`
    vs 0cc
    `2a10aeef9c0115d6e947cde2194e54eb43dd1ded8bf7fee224c8c0be456e7f78`
  - `Buffer_Manager_Cluster.sv` actual
    `1f9f0215bf300509e0ae267576daf530be81c228b801ca9d546b145f773b54ce`
    vs 0cc
    `23b0684ed704a7d91b468deac9e3ddcc4ad34dfb85f81a283a67cb29a8495d16`

本次分析尝试直接读取 GitHub 时因本机 HTTPS credential
`SEC_E_NO_CREDENTIALS` 不可访问；因此：

`AFFECTED_CAUSAL_CONE_CLOUD_RTL_IMPACT_REVIEW_PENDING`

该状态不抹除本次动态事实，也不冒充服务器污染或仿真前终态；但在实际三文件内容未绑定
批准 cloud commit 前，不宣称跨版本 E4/E5。

## 4. Execution chronology

- production compile/run/runner/signal=`0/125/125/INT`；
- `177/177` 个 AXI matrix write/readback 均 PASS；
- execution plan：`Exec_Base=0x002ACC00`，`Exec_Length=518`；
- `Reg Started`、`INFO: slice start` 均出现；
- observer feature time-0 enable PASS；
- snapshots=`558`，其中 heartbeat=`556`、EXEC_START=`1`、
  LONG_RUNNING marker=`1`；
- node0071 stage01：
  `cfg_start/cfg_finish/exec=1/1/1`；
- 最后 snapshot：
  cycle=`145752064`、stage=`1`、slice finish=`0`；
- host observer 总观测约 `40294.326 s`，stage01 约 `37894.121 s`；
- 最终为外部 `INT`，没有 natural terminal、`FINAL_SUMMARY` 或 canonical record。

v9 observer 的 monotonic progress 只覆盖：

- cfg/exec/slice finish；
- stage08 producer D request/wdata；
- stage09..16 node0075 A request/data。

它没有覆盖 stage01 的 MSE0/MSE3 Buffer_AG/Memory_AG/RD qualified
transaction；因此单条 `LONG_RUNNING_HANG_AT_LAST_PROGRESS` 不能唯一证明
stage01 内部实际完全无进展。

## 5. Dynamic gates / claim boundary

producer downstream acceptance→pass00：

- stage08 未到达；
- node0075 pass00 未到达；
- actual ordering=`UNKNOWN/NOT_REACHED`。

node0075 A：

- configured budget 保持 `8192 × 32B = 262144B`、128 个 pass/slice；
- actual read count/traffic/pass-slice hash=`UNKNOWN/NOT_REACHED`；
- result gate 中 event=`0`、128 个空数组 hash 是未到达后的默认聚合，
  不得提升为实际零次 acceptance。

terminal / D：

- stages=`1/32`；
- slice finish=`0/512`；
- formal D expected=`144`，actual=`UNKNOWN/NOT_REACHED`；
- missing=`144`；
- raw mismatch=`0` 不可评估，不得冒充 actual mismatch=0。

联合结论：

```text
NO_EXPLICIT_BARRIER_CLAIM=true
opcode110_is_barrier=false
E3=false
E4=false
E5=false
```

## 6. LPG / FD / HANG_ROOT_CAUSE

`LAST_PROVEN_GOOD`：

> internal source/return/SCA/SCA_D exact binding；全部 preflight；production
> compile=0；177/177 preload；低 bank-row Exec_Base；node0071 stage01
> CONFIG start/finish 与 EXEC_START。

`FIRST_DIVERGENCE`：

> node0071 stage01 EXEC_START 之后、其首个 slice finish 之前；v9 目标计数保持
> 零，但 stage01 内部 qualified progress 不在 v9 observer 覆盖内。

`HANG_ROOT_CAUSE`：

```text
UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT_AT_NODE0071_STAGE01_BUFFER_MEMORY_SUPPLY_BOUNDARY
```

剩余候选为：

1. stage01 仍有内部进展，但 v9 observer blind；
2. stage01 Buffer_AG/Memory_AG/RD supply 已在稳定边界停滞；
3. 三个 actual Buffer leaf 的未绑定版本差异影响同一边界。

## 7. Successor continuous closure

`PACKAGE_RELEASE=NONE`

没有生成新的 node0075 ZIP。精确缺失的 stage01 discriminator 已由 current
GAP/node0071 owner 的唯一高信息增益包覆盖：

`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v40_lc_supply_conservation_diag.zip`

- bytes：`1833762`
- SHA256：
  `7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4`

该包已按 owner-clock 覆盖 MSE0/MSE3 Buffer_AG/Memory_AG FIFO 守恒、public
tag/backpressure、direct RD request consumer 与 data-valid boundary。主线既有编排又明确：
必须先裁决 GAP v40 且不否定 node0071 causal prefix，才运行 node0071→node0075。

所以再生成一个带相同最长 node0071 前缀的 32-stage node0075 观察包，只会重复同一
约 12 小时边界，违反 time-to-root-cause 去重原则。下一必要证据是正式 GAP v40 return；
它未否定 producer prefix 后，bank-row v9 的地址、数值、8-pass 配置资格保持不变，再恢复
完整 32-stage/144D 动态闭环。

## 8. Machine artifacts

- analyzer：
  `tools/analyze_node0071_node0075_0ccae91_bankrow_v9_return.py`
  - SHA256：
    `edb149f66c6c89d905d3e670267060c8dd0d4d4edda3f7a1059588ecee06ac7c`
- machine report：
  `artifacts/operator_config_validation/r5-node0071-node0075-0ccae91-bankrow-v9-return-analysis-v1/report.json`
  - bytes：`13901`
  - SHA256：
    `1e570ce3993780d8c5118ca293e5df2152340347118c6f01149dbcf6c16ddcea`
  - status：
    `RETURN_ANALYSIS_VALID_STAGE01_PREFIX_UNRESOLVED_EXISTING_GAP_V40_REQUIRED`
  - errors：`[]`

## 9. RULE_CONFIRMATION

有证据确认：

- `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`
- `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`
- `CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001`

`RULE_DELTA_PROPOSAL=[]`。current rules 已覆盖本次 identity nonblocking、
未到达零计数、INT hang-first、observer blind boundary 和复用现有唯一诊断包的裁决。
