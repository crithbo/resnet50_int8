# node0075 v5 return → bank-row relocation → cloud-aware v9 package ready

日期：2026-08-05  
Owner family：QLinearMatMul / node0075（联合执行只读消费 node0071 producer）  
唯一主线/结构化回传目标：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
最终状态：`PACKAGE_READY_NOT_RUN`、`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`、`candidate_release=false`

## 1. 边界和 current receipt

- 未修改 `.agents/plan.md`、公共规则、functional RTL、node0071/Conv/GAP/QAdd/其他 family 既有资产。
- 未上传、未运行服务器、未取 lease。
- current cloud RTL authority：`xlsjdjdk/Trassic2.0_RTL/master@0ccae916ef61904a64d6cf8ec1d1931b45e428d8`。
- local expected RTL 仅为 hint：`e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`；actual/local/cloud identity 差异在 production compile 成功后不阻断 simulation。
- current receipts：
  - `.agents/agent.md`：`32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
  - `.agents/plan.md`：`0d1c5577f71d565c7ee4fa6a43054db458de53b41f45813ed2bb3b98be30e126`
  - `.agents/rules/生成前必读索引.md`：`93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
  - `.agents/rules/算子配置规则.md`：`d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0`
  - `.agents/rules/NDP硬件字段语义.md`：`603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
  - `.agents/rules/服务器测试包生成规则.md`：`61753f6866f49aca142545394451cd73c4e634a5aa160b066e020b7c9067cedd`
  - `.agents/rules/INT8_SA点积专项规则.md`：`54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
  - `.agents/rules/精确UINT8量化尾专项规则.md`：`1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
  - `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`：`e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba`

## 2. v5 RETURN_ANALYSIS

正式 return：

- path：`C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n71_n75_e1f_native_v5_return.zip`
- bytes：`127533`
- SHA256：`bb9b98ddfb70e1b6474ff56bfcd9f6d3253f28bd7390b0c9f760c0e7bfe738c4`
- adjacent sidecar：absent；仅使用用户 transport attestation，内部 receipt/manifest/source binding 未放宽。

结论：

1. production VCS compile exit `0`，旧 bare `clk_sg/rst_n_sg` scope blocker 已关闭。
2. simulator 和 observer 均真实启动。
3. 首个 execplan SCA preload `0x01706400` 立即触发 `gradd_n is out of range, bank disable`；readback `518/518` 为 X。
4. `0x01706400` 解码为 bank2 / row `0x1c19`，row 超过 enabled 条件 `row < 6144`。node0071 CONFIG、node0075 CONFIG/D 同样落入对应 disabled row。
5. 首分歧发生在 stage00/CONFIG 前；不是 producer→consumer scheduling、数值、golden 或 functional RTL 故障。
6. v5 的 producer/A/stage/formal-D 计数均“未到达/不可观测”，不是实际 0；正式 actual 值保持 `null/unarrived`。

分析报告：

- `artifacts/operator_config_validation/r5-node0071-node0075-e1fb0f7-native-v5-return-analysis/report.json`
- SHA256：`0edc97ff77ed76e65e2b87c6a277b81cc3c599bf1d17747a3c65dd2a5e035ff9`
- status：`RETURN_ANALYSIS_PASS_SUCCESSOR_REQUIRED_BANKROW_RELOCATION`

## 3. 低 bank-row materializer / 联合 E2

地址修复只改变 D/CONFIG/execplan storage placement：

- node0075 D base：`0x002A4800`
- node0075 24 CONFIG：`0x002A4C00..0x002AA800`
- node0071 8 CONFIG：`0x002AAC00..0x002AC800`
- joint Exec base：`0x002ACC00`
- execplan lines：`518`
- stages：node0071 `8` + node0075 `24` = `32`
- `Start_Comp=32`
- opcode110 slots=`8`，但不作 barrier/fence claim
- A preload=`0`
- dump/reload、host copy/precompute/relayout/replay=`0`
- formal D=`144`（node0071 `16` + node0075 `128`）

8-pass 配置事实：

- reload pass count：恰好最小必要 `8`
- configured qualified occurrence：`8192`
- configured traffic：`262144 B`
- unique A byte set：`32768 B`
- occurrence SHA256：`0ef4664aae656101416c20dc248065ff903e774201836b5a196fff3cdb894950`
- 上述仍是 E2 configured occurrence，不冒充服务器 actual acceptance。

golden 已逐阶段物化且被冻结：

- node0071：`48` 个 stage golden（sum/scaled/final，各 16 slice）
- node0075：`384` 个 stage golden（accum/scaled/final，8 pass × 16 slice × 3）
- total：`432`
- 正式终点 D：`144`
- 本 successor 仅地址/配置 consumer 因果片变化，按规则未重跑 byte-equal numeric/W3/golden。

关键 receipt：

- materializer report SHA256：`0376a60b47c037bb9e12385b4be084eb1000c932d9c814108f41383961bf562f`
- integration report SHA256：`97bcee21851b602bdb217758be0fe9718cbea988ee76b3f6adf21fe78eee6fc2`
- integration validation SHA256：`7427288d168168b1c32f488fab0334cfa93c67c066e330a7c750d5b4030aea35`
- integration validation status：`CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_VALIDATION_PASS`

## 4. cloud RTL `0ccae91` 受影响因果锥

精确核对 `e1fb0f7..0ccae91`：12 commits、11 changed files。

node0071→node0075 受影响路径：

- IGA_ROW_LC input FIFO
- Array_Request_Manager request issue
- Buffer_AG queue `24→32`
- RD_Data queue `32→128`
- REQ_OOO/QUEUE/TAG `16→128`
- SA_Inport pingpong valid qualification

定向门：

- 4 个可由 Icarus focused elaboration 的 changed tops 均通过。
- `RD_Data_Channel` 的 Icarus packed-array dynamic-index elaboration 限制在 local/cloud 均是既有工具边界；精确 changed code slice 仅 `RD_CHL_QUEUE_DEPTH 32→128`，记为 `DYNAMIC_ONLY_BOUNDARY`，production compile 留给正式 return。
- bank/row/column width 与 `DDR_ROW_SIZE=6144` 在 cloud commit 未变，因此低地址修复不受影响。
- observer A-request public leaves 未变；private `rd_chl_ib_rd_hs` declaration name/width byte-equal。observer/parser/canonical bytes未变，使用 v5 通过 receipt，不重跑同义 predicate trace。

报告：

- `artifacts/operator_config_validation/r5-node0071-node0075-e1fb0f7-bankrow-relocated-integration-v2/cloud_rtl_0ccae91_impact_audit.json`
- SHA256：`2bb43112d32053ecbd55bac1a262b3ab084a4809f76b11ead04b7ac16376fd1e`
- status：`AFFECTED_CAUSAL_CONE_REVALIDATION_PASS`

## 5. fresh package lineage 与最终 v9

所有 held identity 均保留、不覆盖、不发布：

- v6：`HELD_PRE_AUDIT_EXEC_BASE_HARDCODE_ESCAPE`；外层 SCA Exec_Base 仍为旧 `0x01706400`。
- v7：`HELD_PRE_AUDIT_RETURN_ALLOWLIST_CONTRACT_ESCAPE`；错误增加第 163 个 return member。
- v8：`HELD_PRE_AUDIT_RUNTIME_EXEC_BASE_CONSUMER_ESCAPE`；runtime preflight 仍固定旧 Exec_Base。

v9 修复：

- final SCA `Exec_Base` 与 `ExecutionPlan.base_addr` 均为 `0x002ACC00`。
- return allowlist 保持冻结 v1/`162`；post-compile cloud identity 作为结构化单行进入既有 required `e/observer_binding.txt`。
- package-local runtime 携带原 runtime byte-exact `runtime_base.py`，wrapper 只将唯一 `Exec_Base 0x01706400` consumer guard 精确改为 `0x002ACC00`；collector/canonical/result gate 使用冻结 base。
- final exact physical interval audit：`177` intervals，invalid=`0`。

最终包：

- ZIP：`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_n75_0cc_bankrow_v9.zip`
- bytes：`3780255`
- SHA256：`f0034876998f636ea0cdd473f830daed896cc7b315fdb73ab617e59d6f3c8165`
- sidecar SHA256：`6c65221f7cbdbe79174f3e640da707004ae4f168ce9284f9eab2efbb9f4b547b`
- manifest SHA256：`242abe93ed9d290ff95688d1f4a259e2f349e06b235fde67861221f0ee116350`
- build report SHA256：`f2131e09164681217cda08acba787432070a51927053bdadd3182750983956b1`
- final audit：`artifacts/operator_config_validation/r5-node0071-node0075-0ccae91-bankrow-package-v9/final_zip_self_audit.json`
- final audit SHA256：`2cb1bf2749a7040969a89ae9185394934ca38c403d5b03f41dff6a5b00e7a46e`
- final audit：`PASS`
- release：`PACKAGE_READY_NOT_RUN`
- blocking failures：`[]`

release_gate_matrix：

- package/bootstrap/path/runtime-D：applicable/pass
- runner→compile/finalizer：applicable/pass
- package-local HDL/XMR：applicable/pass（byte-equal receipt + cloud affected-binding audit；future actual production compile 仍为 dynamic gate）
- materialized config/causal ledger/boundary microtrace：applicable/pass
- diagnostic observer/canonical predicate：not_applicable/receipt-reuse/pass
- return/result joint gate：applicable/pass
- cloud GitHub authority nonblocking：applicable/pass

cloud nonblocking positive control 精确结果：

- synthetic actual identity differs from cloud：true
- compile status：`0`
- simulator stub reached：true
- post-compile identity receipt returned：true
- runner exits于 simulator stub sentinel：`87`
- 证明 identity mismatch 本身不在 compile 成功后阻断 simulation；未运行 DUT。

## 6. 当前动态门 / blocker delta

本地/构包 blocker 已清空；`B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED` 继续按用户覆盖为 `NO_EXPLICIT_BARRIER_CLAIM`，未升级为通用 fence/barrier 证明。

下一正式 return 必须动态裁决：

1. actual production compile identity/exit；identity diff 只记录，不在 compile=0 后停机。
2. node0071 producer downstream request/wdata/final slice acceptance 全部完成后，node0075 pass00 first actual A read 才发生。
3. actual A request/data accepted 均为 `8192`，并核对每 pass/slice ordered/hash；未到达计数不得写为 0。
4. 32 stages / 512 slice finishes natural terminal。
5. formal `144 D` 全部存在且 exact match；E3/E4/E5 联合门。

## 7. 规则反馈

`RULE_CONFIRMATION`：

- `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`
- `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- `CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`
- `CDA-CONFIG-BOUNDARY-MICROTRACE-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001`
- `CDA-SERVER-WORKLOAD-PROVENANCE-001`
- `CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001`

`RULE_DELTA_PROPOSAL`（非同义）：

- ID：`CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001`
- 证据：v5 总地址仍低于 aggregate 24MiB，却因 bank2 row `0x1c19` disabled 在第一个 SCA preload 失败；仅 aggregate capacity 检查不能覆盖物理 address hole。
- 建议：对 changed final address-bound JSON→mapping→bitstream→execplan/SCA interval，按 current bank/row/column fields 解码 first/final/cross-bank lines，并拒绝 disabled physical rows。

## 8. owner tool receipts

- `tools/analyze_node0071_node0075_e1fb0f7_native_v5_return.py`：`cb9fb61e437307a9711d082df62780faee6e2c59dc54b03b395f78ea775322b9`
- `tools/build_node0075_e1fb0f7_bankrow_relocated_materializer_v2.py`：`649b774d890bbfa0315abb18b48ecbe383e66e585077a82b5fd74da2a14b99dc`
- `tools/validate_node0075_e1fb0f7_bankrow_relocated_materializer_v2.py`：`4aba5664ca4fc9c464c5cab753aab9a2cb8ba55327644efaa72f5688251f50e2`
- `tools/build_node0071_node0075_e1fb0f7_bankrow_relocated_integration_v2.py`：`33c2810bfeb497eb84a747a3e918c374480a3ea012cef13973dda8d8bdcfd7b3`
- `tools/validate_node0071_node0075_e1fb0f7_bankrow_relocated_integration_v2.py`：`6b20edcc8540a088fb64e03e5770b71137c5fb814e50c1e0943d802eecae31a9`
- `tools/audit_node0071_node0075_cloud_rtl_0ccae91_impact.py`：`8bc43a08aa36715039adde6498a7c1df7b83b28c683a886de1292e3b1116b6df`
- `tools/build_node0071_node0075_0ccae91_bankrow_package_v6.py`（current 生成 v9）：`82a9257f90283c9e245b0b04da934b26077d12698f31534e35adc763eb341b57`
- `tools/node0071_node0075_bankrow_server_runtime_v2.py`：`a47a1ccfd69f610f0635f54c4f27adfac9a01bf49328fb5ff78d2d49367a47eb`
- `tools/audit_node0071_node0075_0ccae91_bankrow_v7_final_zip.py`（current 审计 v9）：`e017a80fa7a51dc044cc0587f148011b3e35be851953471667b69be28b0d930c`

