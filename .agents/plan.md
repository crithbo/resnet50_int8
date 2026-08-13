# ResNet50 INT8 当前状态与短期计划

最后更新：2026-08-13（原生 production flow non-interference gate activated）

## 0. 文件职责

- 本文件只保留最新状态和最新短期计划；状态变化直接覆盖，不在末尾追加版本过程。
- 旧状态进入 `.agents/history.md` 或 `.agents/history/`；精确证据进入
  `.agents/task_records/` 和机器报告。
- 当前唯一主线会话：`019ff027-e7db-72a3-b282-cfad8708da05`；稳定角色为
  `mainline.control`，owner epoch=`2`。唯一动态指针为
  `contracts/current_session_owner_registry_v1.json`，当前 registry epoch=`6`。动态控制文件不在
  plan 内复制 bytes/SHA，消费时以 current disk 为准。
- 算子 owner 不修改 plan、公共规则或功能 RTL；完成 return 分析或服务器包后必须主动
  向本主线回传。

## 1. 全网最新总账

- ONNX 节点：`78/78`；typed hardware request：`133/133`。
- 正式 E4/E5 闭环：`1/78`，仅 DequantizeLinear node0077；其余不得提前宣称通过。
- 当前没有 `SERVER_RUNNING` lease。

| 算子/范围 | 当前状态 | 最新裁决 |
|---|---|---|
| GAP node0071 | `PACKAGE_BUILDING / NATIVE_FLOW_FRESH` | v60 formal return已消费并归tested；fresh successor正在冻结v60 slice-local绕行与sum_s2宽因果目标重建，修正first-true-error并直接执行原生production flow |
| QLinearAdd node0007 | `PACKAGE_BUILDING / NATIVE_FLOW_FRESH` | v61保持byte-exact pending直到fresh successor全门通过；新包保留identity修复、48个actual signals、双ping-pong端口与tail-round目标，并加入native-flow non-interference合同 |
| MaxPool node0002 | `DEFERRED_BY_USER / COMPLETE_JSON_COMPLETE / TOOL_RULE_COHERENCE_PASS` | pinned exact-stage scope已闭合1/1；461叶闭合，numeric=`LOCAL_SOURCE_PASS`、pipeline=`CONTRADICTED`，current/cloud padding RTL receipt已刷新；padding `null→0`动态归因仍不足 |
| Conv node0004 serialized | `PACKAGE_READY_NOT_RUN / V90B_NATIVEFLOW` | v89b formal return已消费并归tested；v90b保留v88 actual-source基线和纠正后的38-net宽因果目标，不恢复旧ACK comparator，以原生production flow直接裁决v88/v89差异 |
| Conv native four-lane | `PACKAGE_READY_NOT_RUN / P46_NATIVEFLOW` | p45 formal return已消费并归tested；p46保留p42 vector修复与MSE4目标，采用原生production flow，并已补齐stale dump metadata、actual argv、SIM_EXIT、COMPILE_CORE和exact core manifest |
| QuantizeLinear node0074 | `APPROVED_EQUIVALENT / FROZEN_HARDWARE_SLOW_COMPOSITE_HARD_BLOCKED` | hwop-0000-00在real-affine上界下仍最少需82 coefficient segments，超过current SFU容量66；single reciprocal有159个可见transition mismatch，故冻结硬件下全族B路径不可行；node0074消除路径不变 |
| DequantizeLinear | node0077 `E4/E5_PASS_FROZEN / COMPLETE_JSON_COMPLETE` | pinned exact-stage scope已闭合node0072/node0077共2/2，两candidate共832叶完整；node0072同qdomain alias保留，但生产/集成/formal门仍开放 |
| RequantizeUint8 node0001 | `COMPLETE_LOCAL_STRICT_JSON_54_OF_54 / LOCAL_W3_DYNAMIC_EXACT_PASS / NATIVE_BACKEND_OPEN` | 54/54 stages、169,410,176个真实W3 elements本地动态双跑mismatch=0；scalar input transaction占主导，native mapper/encoder、RTL cycle、natural terminal及E3/E4/E5仍开放 |
| View node0073 | `APPROVED_EQUIVALENT_UINT8_ALIAS / COMPLETE_JSON_COMPLETE` | pinned exact-stage scope已闭合1/1，`METADATA_ONLY_ALIAS_NO_COMPUTE`硬件JSON数为0且161叶无UNRESOLVED；运行时accepted lifetime仍待联合return |
| QLinearMatMul node0075 | `V9_RETURN_ANALYZED / WAIT_GAP_PRODUCER_CLOSURE / COMPLETE_JSON_COMPLETE` | v9低bank-row修正有效，但只到node0071 stage01 EXEC_START；node0075未到达，不重复跑同一长前缀 |
| 整网测试收敛优化 | `OBSERVER_ONLY_WIDE_CAUSAL + NATIVE_FLOW_NONINTERFERENCE_ACTIVATED` | observer-only与post-sim合取修复保持；provider closure/短探针 gate 维持撤销。next-fresh exact runner 在 production launch 前只做非干预扫描，真实 cwd/argv/log/exit 自然裁决环境；失败后才做原生 ndp-sim differential |

### 1.1 当前 owner、任务与回传路由（registry epoch 6）

| role | current ACTIVE owner | owner epoch | current task / next action |
|---|---|---:|---|
| `mainline.control` | `019ff027-e7db-72a3-b282-cfad8708da05` | 2 | native-flow non-interference gate 已激活；不派发或重建 current 包，不持续轮询、不执行服务器动作 |
| `family.gap` | `019ff02d-8225-7d21-9779-e46ce4130572` | 2 | `PACKAGE_BUILDING`：重建GAP native-flow fresh successor；只做本地构包，无服务器动作 |
| `family.conv.serialized` | `019ff02d-901b-7f70-a9da-f54e268b5bbe` | 2 | `PACKAGE_READY_NOT_RUN`：v90b已成为唯一serialized pending；等待用户后续运行授权，不执行服务器动作 |
| `family.conv.native` | `019ff02d-974d-7c72-a4d5-de8dbf4ae60c` | 2 | `PACKAGE_READY_NOT_RUN`：p46已成为唯一native Conv pending；等待用户后续运行授权，不执行服务器动作 |
| `family.qlinearadd` | `019ff02d-9e93-7d61-8c98-c928fdea157c` | 2 | `PACKAGE_BUILDING`：从未运行v61重建native-flow fresh successor；v61在fresh全门通过前保持pending |
| `optimizer.whole-network` | `019fd276-14c5-7800-94db-87ebfb9ce632` | 1 | `SHARED_GATE_READY_FROZEN`：observer-only profile/validator和generic process supervisor已验收；只维护共享缺陷，不替family构包或运行服务器 |

完成通知发送前必须从current registry重新解析mainline；旧owner与旧派发thread ID只作provenance。

## 2. 当前 observer-only 构包快照与前代波形裁决

用户已裁决取消 next-fresh 的 VPD、FSDB、VCD、FST，统一改为本机直接读取的 source-bound
observer。actual profile 固定 `DUMP_VCD=0/DUMP_FSDB=0/TB_DUMP_FSDB=0`；宽因果 catalog覆盖
FIRST_DIVERGENCE 上游/当前/下游及状态持有/清除路径，记录全部选中 actual signal 的4-state
transition和end-state。100,000,000 bytes只作软告警，不能截断、采样或按大小删除。GAP、serialized
Conv、native Conv、QAdd均已进入fresh本地构包；旧四个FSDB pending在fresh publication前保持只读，
随后由各family storage manager原子移入superseded。没有upload/run/lease授权，主线派发后不持续轮询。

2026-08-13 用户另行明确批准 `one-shot-curated-vcd-smoke-r5-n4-v1` 精确例外。它只绑定
`r5_n4_hw_vcdsmoke_causal_v1` 的已冻结 ZIP，通过 package-local TB 标准 `$dumpfile+$dumpvars`
回收一个 selected MSE4 WR instance 的38个显式 alias；不启用 UCLI VCD，不使用全层级或 memory
array，不改变 observer-only 的一般规则。该包位于独立 experimental/activated lane，不进入 formal
pending，不改变四个正式包；只允许一次 production invocation，且当前仍须先恢复服务器 DesignWare
`sim_ver` 或绑定用户批准的 exact replacement。激活不等于 upload/lease/server-run 授权。

首次四族构包发现 `post_sim_return_core` 要求 exact canonical helper，而 observer-only validator 曾把该
helper 内惰性的历史 `.vpd/.fsdb` 兼容字面量误判为 active waveform，导致两个 required gate 交集为空。
该实现逃逸已在 `observer-only-post-sim-conjunction-fix-v1` 修复：只有固定路径、exact canonical
bytes/SHA、同 package ID 且 `waveform_discovery` omitted/null 的 post-sim helper 获得 literal-only
豁免；writer/control、其它文件及所有 active argv/request/member/allowlist 仍严格无波形。四族已按
修复后的 gate 重新派发。

以下 FSDB/VPD/direct-VCD 内容只记录上一版本进展和本轮选择依据，不再是 current 构包语义。

用户已强制 supersede 旧 `DUMP_VCD=0` 运行语义。native p40、serialized v86b、QAdd v57h
与 GAP v55 均已原子移入 superseded，未删除或改写证据，且不得上传或运行。
四份portable formal return均已收到。真实VCS证明当前共享direct-VCD命令
`dump -file ...wave.vcd -type VCD`不受生产UCLI支持：GAP v58、serialized v88b和native p43均在
production compile通过后停于0 ps，后续run未执行；QAdd v59更早在package preflight因v58/v59
身份不一致失败，未触发该Tcl。所有family均HOLD，等待共享方法修正；主线不持续轮询。

用户最新裁决改为FSDB smoke-first：formal return ZIP的权威波形为FSDB，关闭无用VPD。shared FSDB v3
gate已在current disk同步并通过回归。最小smoke s1已由
正式return证明package-local probe保留字导致compile=2；未运行s2虽修复identifier，但其README/派生
命令把server root写成父目录而撤回。fresh s3保留`sequence`到`event_seq_id`修复、日志key与FSDB合同，
并把唯一命令绑定`/home/panqs/ndp/NDP_copy01`。s3使用`DUMP_VCD=0/DUMP_FSDB=1/TB_DUMP_FSDB=0`、无上限回收
package-owned `wave.fsdb`及分片、提供WaveUtils或registered event receipt，并证明同一bash重复执行
只安全重置package-owned cfg/run/evidence/compile；同一fixed simresult下旧return保留、新return以
fresh execution identity命名。用户随后窄幅解除GAP/native Conv/QAdd的本地构包HOLD：三族可先生成并
发布`PACKAGE_READY_NOT_RUN`，但在smoke证明production time advance、FSDB新鲜生成/回收、repeat
isolation与return no-overwrite前不得对这些正式包执行服务器动作；formal serialized successor仍不构建。

用户实际运行了preserved s2。该次compile成功、FSDB writer启动并推进至2.446091 ms，随后simv保持高CPU，
至少42分钟没有新sim-time或日志事件。INT finalizer在writer未静止时归档，出现FSDB/shard identity漂移和
transient lock exact-set错误；因此return仅为`EVIDENCE_INCOMPLETE_INTERRUPTED_RUNTIME_PLATEAU`，且ZIP已发布
不等于远端simv已终止。s2与s3运行面在identity normalization后等价，s3暂停执行。共享进程树终止/reap、
FSDB稳定快照/quiescence及周期sim-time heartbeat门已在
`waveform-retention-fsdb-quiescence-v1-967ef4e72e6c` epoch激活，并已派发serialized family以fresh身份重建smoke。
同一epoch还激活正式return后的增量审查与三槽保留：按signal×window×candidate落不可变chunk，唯一根因后
停止无关扫描；仅在family/mainline双消费、final adjudication与确定性core-only派生完成后，才可淘汰非
CURRENT/BASELINE/CAUSAL的第四份旧重型raw return。

唯一取包入口为`artifacts/operator_config_validation/r5-server-test-packages/pending/`；
该目录只放ZIP。以registry epoch 6的in-flight receipt为唯一current指针；fresh observer-only 发布前的
旧 pending exact-set 为
`{r5_qadd_n7_tailround_lanephase_v61_obswide.zip}`。serialized s4已在v89b成功发布后由storage manager原子移入
superseded，native p44也已在p45成功发布后原子supersede；GAP/QAdd仍只在各自fresh observer-only包
发布成功时轮换。s1已tested、s2已superseded；GAP v58、serialized v88b、
native p43与QAdd v59均已归tested且不得再次运行。

`CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001` 与
`CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001` 已在
`fsdb-authoritative-repeatable-return-v3-0a1dee9757c6` epoch窄幅更新：next-fresh固定
`DUMP_VCD=0/DUMP_FSDB=1/TB_DUMP_FSDB=0`，权威证据为attempt-local无上限FSDB及WaveUtils/registered
event receipt。历史VPD/direct-VCD只作旧return兼容。首个serialized smoke必须以time-0 marker、
time>0、fresh FSDB、query receipt、同bash第二执行exact reset和distinct return证明真实服务器能力；
失败仍须保留raw/core并标`DIAGNOSTIC_EVIDENCE_INCOMPLETE`。

current storage index为`PACKAGE_STORAGE_INDEX.json`，`pass=true`、
pending/tested/superseded=`1/124/54`；pending仅含QAdd v61。serialized v89b、GAP v60和native p45
均已消费正式return并归tested；三者的共同compile结果只证明当前provider闭包失败，不证明单一路径
或服务器环境变化。QAdd v61仍禁止服务器动作，later fresh受provider-aware next-fresh门约束。

GAP v58正式return receipt为
`.agents/task_records/20260812_gap_node0071_v58_return_portable_ucli_capability_block.md`；v54
证明remote owner-ready RTL根因，v55本地证明slice-local-base配置绕行但因旧dump=0语义撤回，
v56动态证明该绕行使sum_s1在全部16个选中slice完成，且remote/global请求与违规均为零。首次偏离
移至sum_s2已启动但未完成、读输入后尚无首次写回；v57只启用已编译的有界只读诊断，用于定位
`SUM_S2_READ_INPUT_SUPPLY_TO_GA_ACCEPT`生命周期。v58 compile/elab/link通过，但unsupported VCD
命令在0 ps阻止run；48候选query为零，sum_s2未执行。配置、数值、workload、功能RTL及绕行冻结。

serialized v88b interim return以family正式receipt待补；v85b
compile-rootcause证据定位两处package-local XMRE，v86b修复因旧dump-disabled语义撤回，v87b
正式return证明production compile已越过该根因并启动simulation。observer在13/13完整序列的稳定晚采样
均记录bit1 XOR，形成`ACK output versus same-instance inline RHS`的精确实例矛盾；自然终止未出现、
formal D=`0/320`、E3/E4/E5=false。VPD采集链与回传identity有效但为partial，且本地没有
`vpd2vcd`、Verdi或DVE。family已消费共享方法：toolchain与convert均按合同fail closed，conversion
request有效且无需重跑simulation，但没有生成VCD；故尚未证明全局最早VPD转变或枚举实际driver
cone。正式return也未绑定actual compiled DUT RTL文件身份；冻结旧parser错绑slice0/group0是独立
return-completeness缺陷。主线复审裁决为`EVIDENCE_INCOMPLETE`：observer/TB误报已被65个
binary-known五相事件和13/13稳定晚采样强烈反驳，但actual compiled source mismatch仍是实质替代解释，
因此仅能条件性报告RTL错误。不存在保持数学、transaction、lifetime、coverage与formal-D等价的
配置绕行；disable/replay至少损失1/28首轮覆盖并增加stage/sync/traffic，split-row仍走唯一MSE4且
至少增加三次launch/sync。v88b actual compiled target进一步证明真正public ACK为
`{!row_fifo_full,!col_fifo_full}`，而旧observer比较了不同的`buf_idx_queue_bp_pre`方程；因此旧条件性
RTL报告已撤销为`SOURCE_IDENTITY_MISMATCH / OBSERVER_SEMANTIC_FALSE_POSITIVE`。同包也因shared
unsupported VCD命令停在0 ps，等待方法修正，不修改功能RTL。

native p43正式return task record为
`.agents/task_records/20260812_conv_native_four_lane_p43_return_shared_portable_runtime_escape_hold.md`；p39
定位两处package-local XMRE，p40 public-surface修复因旧dump=0语义撤回，p41保留该修复并证明
production compile通过且mandatory VPD有效。独立ledger已见MSE4 wdata 18次，而source-bound probe
报零；首次偏离收敛为package-local observer把两位valid/ready向量按标量比较。p42仅将谓词改为
`(|(valid & ready)) === 1'b1`并刷新派生回执。p43保持该谓词、MSE4目标和全部冻结面，仅加入
same-attempt raw VPD、direct VCD、9-candidate complete query/event与portable return面；本地构包、
exact-ZIP、六退出和new-epoch first-fresh门已通过。正式return中production compile通过，但VCS在
unsupported direct-VCD命令处停于0 ps；MSE4 DUT与query均未执行，目标保持开放并HOLD。

QAdd v59正式return machine receipt为
`outputs/qlinearadd_v59r1421299/qadd_formal_return_hold_receipt.json`；
v57h通过production compile并进入tail-round stage1，最后可信点为Buffer5 request decode，首次
偏离为所选ping-pong port的bank/lane readiness到read accept之间。v58保留目标诊断并通过
mandatory full-hierarchy VPD、first-fresh、final-ZIP、source-bound、runner与storage门。以后
v59却在compile前因`TEST_PACKAGE_MANIFEST.install_name`仍为v58、package/SCA namespace为v59而
preflight fail closed；shared Tcl未执行，历史DUT边界不变。修正身份的fresh successor已证明必要，
但必须等待shared runtime fix后构建。

GAP v55配置绕行已本地验证；它与上述三包的旧运行语义均只作为 superseded 历史证据保留。
旧包的本地`upload_authorized=true`已被本次强制 HOLD 撤销，不是用户服务器授权；
主线与family均不得据此上传、取lease或运行。

node0075当前不在pending唯一取包集合；其继续推进依赖GAP生产者动态闭合。

## 2A. 历史服务器包资产（superseded/tested，不作为current取包入口）

### 2.1 GAP node0071

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v40_lc_supply_conservation_diag.zip
bytes   1,833,762
SHA256  7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4
command bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
return  r5_n71_gap_v40_lc_supply_conservation_diag_return.zip
```

- v37 compile=`0`，MSE0/MSE3各有185次req→inbuffer→prepared→WR accept完整前进；
  随后Buffer_AG queue pending/full，而RD request/prepared/data_vld源链为空。
- 云端权威0cc把Buffer_AG depth从24改为32；`q_enq-q_deq=32`恰为新容量。
  v37 observer用5-bit读取需要6-bit表示的32，因此`full=1/count=0`是observer位宽漂移，
  不是功能FIFO守恒反证。
- v40按`clk_db`用qualified、rate-limited事件同包覆盖MSE0/MSE3 Buffer_AG/Memory_AG
  FIFO守恒、public tag/backpressure、direct RD request consumer与data_vld边界。
- dynamic natural terminal、formal D 48及E4/E5仍待正式return；v37已消费，不得重复运行。

### 2.2 serialized Conv node0004

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v49_lc9_actual_compilefix.zip
bytes   5,868,790
SHA256  2b7faeb4b838133f041432ff707792047d113bf65871aa8936e3f2f4c502e27c
command bash r5_n4_hw_v49_lc9_actual_compilefix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
return  r5_n4_hw_v49_lc9_actual_compilefix_return.zip
```

- v48正式return bytes=`57,414`、SHA256=`91cb18d7e0a1d687597503026ed0155af0c8cf2f491a1712318897122148a27a`；
  内部收据和preflight均PASS，但production compile=`2`、simulation未启动、formal D=`0/320`，
  E3/E4/E5=false。
- 首分歧是package-local observer把MSE3写成
  `MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine`，而0cc真实generate路径为
  `MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine`；10个XMRE均属于同一实际层级错误，
  不是DUT hang、config或numeric根因。
- v49仅修15处MSE3 `WR_MSE→RD_MSE`层级，并加入bounded trigger-only LC9 snapshots；
  numeric/W3/qparam/tail/workload/config/golden/timeout/backpressure/functional RTL/ISA/
  hardware/active ndp-sim全部冻结，符合`HARDWARE_CHANGE_FORBIDDEN`。
- deterministic double build PASS；最终observer中RD occurrences=`15`、WR=`0`；
  wrong branch、missing/sibling/generate-name-drift负控均fail closed；focused syntax、
  predicate/profile、runner/TERM与final-ZIP audit均PASS。
- v49正式return仍须证明LC9→LC7/MSE3真实branch progress、DUT natural terminal、
  formal D `320/320`与E3/E4/E5联合门；默认0或missing D不得冒充通过。
- v47 production compile/run=`0/0`、signal=NONE、simulation started，E3=true；DUT natural
  terminal=false，formal D=`0/320`，故E4/E5=false。
- v47最终LC9 bp=`0x1fbfffffe`，实际仅bit0与bit26为低；0cc真实映射分别为LC7 source slot8
  与MSE3 source slot5/input2。v47却主要观察PE1 source9、MSE4 input1和ROW4，consumer错绑。
- v47 `pe1_in2_accept=LC9 valid && 单支ready`在global LC9 advance=0时把held level逐周期计成
  `1,310,717`次伪事务，不能当作qualified progress。
- v48只纠正package-local observer：覆盖LC7 capture/output、MSE3 input2 capture/match/queue、
  bit0/26变化与LC9全消费者advance；numeric/W3/workload/config/golden/RTL/timeout均冻结。
- v48 deterministic double build、22/22 actual consumer、predicate/scope/feature/runner/TERM和
  9-row release gate均PASS；它仍是诊断包，不证明DUT根因、natural terminal或320D。
- 旧outbuffer occupancy继续为`INVALIDATED_NOT_RTL_BUG`；v47已消费，不得重复运行。

### 2.3 QLinearAdd node0007

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_cout32_v36.zip
bytes   26,181,302
SHA256  b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382
command bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
return  r5_qadd_n7_cout32_v36_return.zip
```

- v35 compile=`0`，但8h后simulation=`124`、natural=false、formal D=`0/28`。
  FP32 add已产生`9114/9408`行GA输出，输入侧32B rowpair修复有效。
- 新首断点为输出供给：v35仅启用4个GA PE，`4×4B=16B`，而Buffer5要求八bank、
  `8×4B=32B`；动态上GA有活动，但Buffer5 accepted write=`0`，MSE4有req无wdata。
- v36只为op_fp32_add新增native PE10/PE12/PE30/PE32，使输出覆盖8 lane/32B；
  rowpair/address/workload/observer/timeout/numeric/W3/qparam/tail/golden/RTL均冻结。
- final JSON/mapping/bitstream/execplan/SCA从空状态重建；61个有效64-bit配置字打包为
  31个128-bit传输行，末尾高半padding按真实packing合同处理。
- deterministic double build、causal ledger、boundary microtrace、7项配置负控、
  exact-ZIP HDL正控、26/26 actual consumers、runner/EXIT/TERM/path/runtime-D门均PASS。
- v36仍为split-C累计前缀；正式return须证明Buffer5 accepted write、MSE wdata、
  natural terminal及28项局部结果。闭合后下一fresh successor直接提升full-chain正式28D。

### 2.4 Conv native four-lane

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p10_trig.zip
bytes   5,823,887
SHA256  25c9c01fe7feb42ec8de3eef701386420e7ab014ad24630022539d97a9fb03b5
command bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
return  r5_n4_0cc_p10_trig_return.zip
```

- p9b正式return SHA=`96a4d9678b92dd5b74eb010de1fe27303dfc26a856f553623b6a162e999fab0d`；
  internal receipt/source/preflight PASS，compile=`0`、run=`125`、signal=`INT`，
  simulator与c0 exec均到达，但slice_finish=`0`且无natural terminal。
- threshold5已真实跨过p8f旧边界：qualified events从`52,859`推进到
  `139,198,964`，末cycle=`94,860,826`。配置修正保留，不再回退threshold2。
- 末态各MSE req=`16,16,16,14,32`；ARM req=`8,5,10,2,6,3`、resp=`3,2,8,0,4,0`，
  finish全0；SA `28→3`，MSE4 index=`2`。Buffer5大wr_en计数可能是held-level，
  不得冒充accepted transaction。
- actual/cloud唯一差异仍为Array_Request_Manager；identity差异不阻断simulation，但因
  ARM finish全0保留causal risk。剩余候选为actual ARM terminal semantics、
  MSE4 last-index propagation及SA-output→Buffer5 acceptance。
- p10冻结p9b workload/config/mapping/bitstream/execplan/numeric/W3/golden/address，只加入
  always-on bounded triggered causal c0 observer；不改RTL、DUT输入、backpressure或timeout。
- p10 final audit SHA=`d652f31d3f82cc6b84bd40dd8c054b5eb74f08c98782607f7b5639646d1d0b01`，
  predicate trace、focused HDL、runner/finalizer、allowlist、deterministic replay及
  release-gate matrix全PASS。p9b已归tested，p10为本族唯一pending。
- frozen local E2性能反演保持native occurrence、weight、单B流4×下降，
  B+B′物理activation 2×下降；正式性能候选仍需27/27 natural terminal、
  320/320 formal D mismatch=0和actual production identity。

### 2.5 QLinearMatMul node0075 native-ordering integration（已测归档，禁止重复运行）

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/tested/qlinear_matmul_node0075/r5_n71_n75_0cc_bankrow_v9/r5_n71_n75_0cc_bankrow_v9.zip
bytes   3,780,255
SHA256  f0034876998f636ea0cdd473f830daed896cc7b315fdb73ab617e59d6f3c8165
command bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
return  r5_n71_n75_0cc_bankrow_v9_return.zip
```

- 单一 simulator/execplan 执行 graph-external UINT8 input→真实node0071 8 stages→正常
  command/config transition→node0075 24 stages；518行、32个Start_Comp、无额外boundary行。
- 8个opcode110原样保留但明确 `opcode110_is_barrier=false`、
  `explicit_barrier_claim=false`；本包不声称通用visibility fence存在或缺失属于RTL bug。
- A preload=0、runtime D preseed=0；node0075 A reload恰好8 pass，
  E2 configured occurrences=`8192×32B`、traffic=`262144B`、unique=`32768B`。
  这些是配置/E2收据，不冒充服务器actual acceptance。
- formal D共144项：node0071 final 16 + node0075 final fragments 128；runtime前全部不存在。
  observer须证明producer downstream/hub acceptance→pass00 first read、8192次actual reads及hash。
- v5已越过旧SG observer编译问题并启动simulation，但第一条SCA preload
  `0x01706400`解码到bank2、row`0x1c19`，命中禁用bank/非法row；518/518 readback为X，
  CONFIG/stage00、ordering、numeric均未到达。
- v9把node0075 D迁移到`0x002A4800`，24个node0075 config迁移到
  `0x002A4C00..0x002AA800`，8个node0071 config迁移到
  `0x002AAC00..0x002AC800`，ExecutionPlan base=`0x002ACC00`。
- 177个最终物理区间按bank/row/column逐项审计，invalid=0；SCA、ExecutionPlan、
  runtime guard和return direct consumers均绑定同一新地址。v6/v7/v8为隔离身份，不可运行。
- 云端0cc causal cone定向复验通过；actual/local/cloud identity差异在compile成功后
  只记录，不阻断simulation。config-bound native-ordering E2和432份stage golden保持冻结。
- final ZIP exact-set/path/runtime-D/allowlist/observer/focused HDL/actual-consumer
  closure、runner/TERM/canonical、物理bank-row地址门均通过。
- v9正式return SHA=`fb1aef2c0699b5115f1e461cbca827a018359288c06cb6024451bc9ba3486482`；
  internal receipt/source/preload均PASS，production compile=`0`，simulation/runner=`125/125`
  且signal=`INT`。低bank-row修正有效，node0071 stage01 cfg/EXEC_START到达，但停在首个
  slice finish前：terminal=`1/32 stages`、`0/512 slices`。
- node0071 stage08 producer、node0075 pass00、8192 actual reads及128 pass/slice hashes均
  `NOT_REACHED/UNKNOWN`；144D也未到达，raw mismatch=0不可评价，E3/E4/E5=false。
  9个actual cloud leaf中6个匹配，ARM/Buffer Manager/Cluster三个受影响cone leaf不同；
  identity差异未阻止simulation，但跨版本结果归属继续受限。
- v9 observer没有stage01 MSE0/MSE3 Buffer_AG/Memory_AG/RD qualified progress，不能唯一
  解释首slice前停点。缺失边界已由现有GAP v40包完整覆盖，因此`PACKAGE_RELEASE=NONE`；
  先消费GAP v40 return，确认node0071前缀后再恢复32-stage/144D闭环，不重复运行v9。

## 3. 当前硬件与跨族边界

- 云端GitHub `xlsjdjdk/Trassic2.0_RTL/master`是功能RTL权威；当前已确认提交为
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`。本地`Trassic2.0_RTL/master`已直接
  fast-forward到同一提交，`NDP_copy01/rtl`与其2262文件逐字节一致，tree receipt=
  `c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093`；
  未保留旧RTL副本。
- 服务器actual/local expected不同本身不得阻止simulation。compile成功后继续运行，
  在return中记录actual/cloud identity和定向causal-cone影响；不影响当前算子的差异不阻断，
  影响其它算子族则通知对应owner。
- 0cc相对e1有12 commits、11 files变化，主要涉及ROW-LC FIFO、ARM、
  Buffer_AG/RD/request queue深度及SA pingpong valid；各在用算子族已完成定向影响复验。
- node0075 已物化 8 accum + 8 scale + 8 exact round，A reload 为实际最小 8 pass，
  并已用同一 simulator/execplan 物化真实node0071 producer prefix。
- 该路径不把 opcode110 计为barrier，也不声称当前缺少通用fence是RTL bug；
  正确性仅由正式return中的实际顺序、读取与D裁决。
- 禁止两次仿真间 dump/reload、A preload、host copy/precompute/replay 或用 producer base
  冒充 consumer acceptance；只读 observer 必须回收 producer downstream/hub acceptance、
  pass00 first read 与8192×32B actual accepted reads，formal D 独立裁决。

## 4. 最新短期计划

1. observer-only宽因果profile已在epoch `observer-only-wide-causal-v1`激活：next-fresh固定`DUMP_VCD=0/DUMP_FSDB=0/TB_DUMP_FSDB=0`，
   禁止VPD/FSDB/VCD/FST和vendor query；保留source-bound actual-signal catalog、4-state event chunks、
   end-state、sim-time heartbeat、canonical decision、repeat reset与execution-bound no-overwrite return。
2. 100,000,000 bytes仅为observer evidence软偏好，超限只warning；hard cap、截断、采样、head/tail或
   size-based deletion固定fail closed。每个known candidate必须在宽因果矩阵中两两可区分。
3. serialized Conv v89b、native p45与QAdd v61已完成，旧s4/p44/QAdd v60已原子supersede；GAP
   fresh artifact已进入pending，但仍等待family主动完成回执后才由主线正式验收。
4. GAP保留slice-local绕行与sum_s2目标；native保留p42 vector修复与MSE4目标；QAdd保留v60身份修复及
   selected-port lane-readiness目标；serialized以v88 actual-source为基线并禁止回引已证误报的旧ACK comparator。
   四族均冻结功能RTL/config/numeric/workload/golden。
5. 通用进程树终止/reap与周期sim-time heartbeat继续适用；归档前改为observer chunk close/flush和稳定
   exact-set，不再等待FSDB writer。compilefail和所有partial exit仍须发布core/已有observer。
6. 历史raw waveform return继续按CURRENT/BASELINE/CAUSAL三槽与双消费规则保护；新observer-only裁决
   不追溯删除旧证据，也不再产生新的raw waveform。
7. `observer-only-post-sim-conjunction-fix-v1` 已激活并通过联合回归；四族以该 exact helper
   inert-compatibility contract 重新构包，主线继续不轮询，只等待主动完成回执。
7. family完成package或命中明确终止点后，必须向动态解析的current mainline提交
   `PACKAGE_READY_NOT_RUN`/终止回执、package/sidecar身份、唯一命令、预期return、final-ZIP
   自检、blocker与规则反馈；主线只验收和更新current pointer，不替family构包。
8. 主线收到回执后核对registry owner/epoch、latest task record、package storage index与
   exact bytes/SHA；只有结构化回执通过才更新本文件的pending exact-set和下一步。
9. 主线派发后不持续轮询，只在family主动回传时验收。当前无`SERVER_RUNNING` lease；上传、服务器
   运行、取lease、functional RTL动作继续需要用户明确授权，本地构包授权不能解释为服务器授权。

### 4A. 历史演进记录（不作为current包或当前运行顺序）

1. native p9b、serialized Conv v47、QAdd v35与node0071→node0075 v9均已消费，不得重复运行；
   当前fresh身份分别为native p10 triggered c0、serialized v49和QAdd split-C v36。
2. GAP v40现为node0075唯一前置诊断：先回收其Buffer_AG/Memory_AG/RD supply边界return；
   若不否定node0071 causal prefix，再生成/运行恢复32-stage natural terminal+144D的fresh
   node0075闭环包。不得用另一个约12h重复前缀诊断替代现有v40。
3. p9b已确认transout threshold修正跨过旧边界，但c0 terminal仍开；先运行p10一次区分
   ARM terminal、MSE4 last-index与SA→Buffer5 acceptance。c0 natural后立即恢复27/320
   full target。GAP/serialized Conv/QAdd当前局部边界一旦闭合，
   同样提升到该族natural terminal + 正式D full target；除非出现同包候选矩阵不能区分的
   新首分歧，不再追加同边界read-only leaf。
4. 每个正式return继续交回原owner，在同一任务内完成分析→修正/高信息增益successor，并主动
   回传主线及规则反馈。compile成功后的actual/local/cloud identity差异只记录并做causal-cone
   审计，不阻断simulation。
5. 优化专项会话为next fresh successor实现共享 final-ZIP driver与按失败机制索引的反例registry；
   先与family validator shadow compare一次。当前五包不重建、不替换、不因迁移扣留。
6. next fresh successor 的rule drift/applicability只走
   `blocking_applicable / receipt_reuse / record_only / not_applicable`；移除非因果hardcoded
   all-rule-SHA阻断，但保留production compile、natural terminal、正式D、E4/E5等真实性门。
7. shared RETURN adjudicator v2保持shadow-only：覆盖stock-TB terminal、observer四向绑定、
   counter终值可达、D覆盖/有效性/范围、qualified progress/timeout/log、provenance/barrier、
   return collection与E4/E5 evidence dominance。当前实现位于优化专项worktree，尚未合入
   主线生成路径；coherence lint唯一报告Requant/node0001缺plan token，本总账已补状态行。
8. 所有以后fresh/changed native adaptation必须执行
   `CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001`、
   `CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001`，组合多个primitive/stage时再执行
   `CDA-NATIVE-COMPOSITION-BOUNDARY-001`；现有冻结包不因规则发布追溯重建。
9. complete-JSON公共合同/schema/validator已同步主工作区，并向Flatten/View、Dequant、
   QLinearMatMul、MaxPool、GAP、Quantize、QAdd、Requant和Conv九个family owner派发。
   各owner只允许产出`COMPLETE`或精确`BLOCKED`的本地合同/报告；本轮禁止生成
   mapping/bitstream/execplan/SCA及任何服务器测试包。公共driver随后完成首个fresh
   delta：合法`BLOCKED`的真实缺口进入`completion_blockers`，结构/身份/账本矛盾仍只进
   `errors`；九族须以11/11 PASS版本重跑，禁止把`blocked_valid=true`提升为`COMPLETE`。
   当前已消费9/9：GAP为`COMPLETE_STRICT_JSON_LOCAL_VALIDATED`；View为零硬件JSON的
   `METADATA_ONLY_ALIAS_NO_COMPUTE / COMPLETE`；ConvInt32Accumulate
   为`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`，其1851项`completion_blockers`
   不含结构错误；QLinearAdd同为合法能力性`BLOCKED`，17/17 stage覆盖但缺少typed
   six-qparam composite handler；Quantize的2/2与Requantize的54/54 stage也因generic
   typed handler/精确数值与address-schedule能力缺失而合法`BLOCKED`；MaxPool的
   461叶完整闭合，但current v5的padding null差异仅为疑似缺陷且未获动态归因；
   Dequantize的node0072/node0077共832叶完整闭合；QLinearMatMul的11568叶、17个
   composition boundary及pinned exact-stage family coverage 2/2全部闭合。最终九族为
   5个`COMPLETE`和4个合法`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`，均未改变现有
   服务器包或动态E3–E5边界。
10. 九族规则反馈裁决：Flatten/View族规则已切换到current UINT8
    `node0071D→node0073→node0075A`、32768B、offset0 route；旧FP32 route仅保留
    off-path历史。QAdd typed composite提案由现有six-qparam/stage/broadcast/readiness/
    exact-tail规则覆盖，不新增同义规则。MaxPool validator的numeric/pipeline事实分层
    与padding RTL identity receipt已闭合，不改变数值规则、candidate或服务器资产。
11. 用户授权的四族isolated hash-bound handler/materializer v2已推进到首个真实硬件语义
    断点并fail closed；原
    `WAIT_USER_DECISION_HARDWARE_ISA_OR_SLOW_COMPOSITE_PROOF`已由用户裁决关闭，当前为
    `SLOW_COMPOSITE_PROOF_AUTHORIZED / HARDWARE_CHANGE_FORBIDDEN`。31/31 focused tests PASS，
    四族exact-stage scope与合同结构均有效，但strict hardware JSON仍为0：
    Requantize当时缺signed INT32 ingress、sequential multiply→RNE和integer-zp/saturation
    tail；其后current exact source的signed ingress已由全域proof关闭，但其余tail/组合门不变；
    QLinearAdd缺exact binary32 divide/RNE consumer与node0076 physical broadcast replay；
    Conv的node0004 assumed-fixed授权不能泛化到其余52 stage，615 hardware-surface leaves
    仍无权威；Quantize存在exact divide与reciprocal-multiply输出159/158的具体反例。
    aggregate report SHA-256为
    `ecae3f5a96485064544ce47b9541c07d46c79368b10f3f3d478fbc8be8ff023a`。
    禁止继续猜填JSON或把近似算术提升为exact。用户已明确拒绝
    （A）hardware/ISA capability design，并只授权（B）现有primitive慢速复合路径证明。
    专项依赖顺序固定为`Requant/Quant shared tail→QAdd→Conv`，仅在隔离worktree证明
    数学、typed、topology、address与lifetime可行性；不能证明时必须以反例fail closed。
    全程禁止functional RTL/ISA/hardware与active ndp-sim修改，也禁止
    mapping/bitstream/execplan/SCA、服务器包及upload/run/lease；
    existing current packages/configs、active ndp-sim、functional RTL和E3–E5裁决均不变。
12. MaxPool独立工具/规则一致性维护已完成：
    `CDA-GA-INT8-MAX-NUMERIC-001=LOCAL_SOURCE_PASS`，
    `CDA-GA-INT8-MAX-PIPE-001=CONTRADICTED`；current/cloud authority
    `RD_Data_Channel.sv` 28128B、SHA-256
    `08b35e80c234c6567099c4da5e18ff0a18955e259b7c12bedff72325f744038c`
    byte-equal，padding优先方程已由fresh receipt绑定。机器报告
    `artifacts/operator_config_validation/r5-maxpool-tool-rule-coherence-padding-receipt-v1/report.json`
    当前SHA-256 `c1fa7ec76862204d06512841a184f55f3fe3cedd728a4365edd51160bc05e556`
    为PASS；strict candidate/current v5/current diff均未改变，未生成包或执行服务器动作。
13. complete-JSON family scope 迁移继续收紧但不改变候选裁决：
    ConvInt32Accumulate 已绑定 lowering
    `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
    与53个有序exact stage IDs，coverage=53/53，仍仅因合法capability BLOCKED而
    family audit `pass=false`；View绑定`hwop-0073-00`并exact 1/1 PASS；
    DequantizeLinear绑定`hwop-0072-00`、`hwop-0077-00`并exact 2/2 PASS；
    RequantizeUint8绑定54个有序exact stage IDs并exact 54/54，仍仅因54个合法
    non-COMPLETE candidate而family `pass=false`；MaxPool绑定`hwop-0002-00`
    并exact 1/1 PASS；GAP绑定`hwop-0071-00`、`hwop-0071-01`并exact 2/2 PASS；
    QuantizeLinear绑定`hwop-0000-00`、`hwop-0074-00`并exact 2/2，仍仅因两份
    合法non-COMPLETE candidate而family `pass=false`；QLinearAdd绑定17个有序exact
    stage IDs并exact 17/17，仍因原candidate合法BLOCKED而`pass=false`；
    QLinearMatMul此前已绑定`hwop-0075-00`、`hwop-0075-01`并exact 2/2 PASS。
    至此九族133/133 unique lowering stage、134 family memberships全部使用
    `PINNED_EXACT_STAGE_IDS`并绑定同一lowering SHA；唯一重复membership为
    `hwop-0075-01`，由generic Requant与target-specific MatMul有意共享。
    `exact_scope_cross_family_audit.json` SHA-256
    `8478ef700a76ec917be9376741b29c3aa12dae5cfd7997de16ac4fc7c613c672`
    为PASS；candidate、ledger、handler/current diff与动态门均未改变，没有构包或服务器动作。
14. 常态触发式因果观测公共方法已发布：
    `CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001` 与
    `CDA-WHOLE-NET-ONE-ROUND-OBSERVABILITY-COMPLETENESS-FIRST-001` 要求下一份会实际
    进入DUT simulation的fresh successor先形成完整
    `候选→source/queue/consumer/internal/output/terminal/formal-D边界→触发快照→canonical`
    判别合同。常态只保留stage-gated定宽计数/时间戳/守恒摘要，异常用六类有界trigger；
    禁止逐事务文本、默认全波形、DUT drive、host内部tensor replay与改变timeout/背压语义。
    `50%` slowdown仅为非阻断偏好，超过时报告和优化但不得删除必要边界；无同事件A/B时
    保持`PENDING_FRESH_BOUND_PROFILE`。该条“current不追溯”已被2026-08-13用户observer-only四族
    fresh重建裁决显式取代；next-fresh包须
    绑定exact final HDL、owner clock/reset、actual consumer/predicate后才能进入family
    final-ZIP release gate。公共设计报告
    `artifacts/operator_config_validation/r5-triggered-causal-observability-v1/report.json`
    SHA-256 `8a83588236344f6656d6600617c6ccd10487a273880a89bb47a117bd812bb610`
    为`DESIGN_VALID_BINDING_AND_CALIBRATION_PENDING`，不证明服务器运行或E4/E5。
15. Requant slow-composite proof的早期规则分歧已完成全域证明并窄幅闭合：
    cloud-authority lineage中的`GA_Inport.sv`当前镜像SHA-256
    `2d27c3bc339c58c8335ae79a6341bec54d27694801c036a0af8099e29b2a18cb`，
    `ga_inport_int32_min = sign && lower31==0`实际识别`0x80000000`，并具有GRS
    ties-to-even路径；源码注释仍写`0xFFFF_FFFF`但与表达式不一致，不能用注释裁决功能。
    全`4,294,967,296/4,294,967,296`输入逻辑覆盖、`184,549,375` representative
    equation checks、focused RTL 15/15均mismatch=0。Requant规则现将当前primitive绑定到
    exact commit/blob/source/consumer，并把旧`-1`/INT32_MIN失败限定到历史source SHA
    `42a7ac1d…e17`。只关闭signed ingress numeric子叶；sequential multiply→independent
    RNE、integer-zp/saturation、magic-wrap、typed/topology/address/lifetime和全部动态门
    继续开放，current package/config/RTL与服务器状态不变。
16. existing-primitive slow-composite interim已产生两项分离裁决：
    Quant `hwop-0000-00` 的固定scale=`0x3c98d99a`、zp=`114`在一个比真实硬件更宽松的
    real-affine模型中，adaptive exact transition/tie-envelope DP仍至少需要82个
    coefficient segments，超过current SFU的66项容量（65 breakpoints），single reciprocal
    另有159个可见transition mismatch；因此冻结硬件下Quant family的B路径
    `HARD_IMPOSSIBLE`，`hwop-0074-00`单项仅`NOT_PROVEN`不改变全族状态。
    Requant则已在corrected signed ingress上证明全INT32域5PE数值图：
    `per-channel mul→3-region SFU clamp[-256,256]→magic→intsub→integer zp→uint8`。
    该证明尚未升级strict JSON；只剩duplicate-breakpoint BST address、
    single-operator selector/tag/backpressure与54-stage multiplier supply三类物理门。
    interim report SHA-256
    `9cc03b1f65621375c17d024baf568c0bd779f442dac29712f9526efddefb8ea5`，
    direct tests 6/6 PASS；报告精确路径/bytes待专项final receipt补齐。无规则、backend、
    package、server或RTL动作。
17. QLinearAdd existing-primitive slow-composite已证明reachable-domain数值与只读9PE拓扑
    可行，但尚不构成strict JSON。DP对17个stage各枚举65536对，共`1,114,112` pairs，
    最少/最多只需`1/3` SFU segments，超过66容量的stage为0；12项只需1 segment，
    `0011/0049/0053/0057/0070`需3 segments，严格padded 66 coefficients/65 breakpoints
    且`x>=breakpoint` dispatch mismatch=0。9PE selector顺序为
    `4,4,1,3,4,3,4,3`，PE32→outport6/src1；旧4-lane pending状态已被正式supersede，
    stale状态必须由validator阻断。single-FMA dequant仍有`2888/8704` bit mismatches，
    reciprocal反例继续保留。optimizer isolated worktree报告
    `artifacts/operator_config_validation/r5_existing_primitive_slow_composite_proof_v1/qlinearadd/report.json`
    bytes=`18,691`、SHA-256
    `2759381f660496d57be7891efd2716c253276d13256b1fe22ccabdeae0e5e491`，
    tests 10/10、negatives 7/7 PASS。隔离six-qparam typed materializer属于既有B路径授权，
    但按用户依赖顺序必须等待Requant physical proof闭合后再执行；仍禁止
    mapping/bitstream/execplan/SCA/ZIP/server及RTL/ISA/hardware修改。
18. Requant 5PE physical proof已关闭两类边界并收敛到唯一multiplier supply blocker：
    65个threshold为rank0..31=`-256`、rank32..64=`+256`，current upper-bound BST
    equality向右，reachable地址精确为`{0,32,65}`，focused RTL 10/10 PASS；
    4×4链`PE00→PE01→PE10→PE11→PE12`的source/destination selectors
    `4/4,3/7,4/4,4/4`、完整tag/data/backpressure与terminal
    `PE12(row1,col2)→outport5/src0`均由current source方程闭合。54/54 ordered multiplier
    payload identity、26,561元素、shape/hash/min/max也全部闭合，但53/54 stage
    `min!=max`；现有registered stream/quant handler仍为placeholder，尚无方程把
    exact payload bits/channel axis绑定到每个sample/spatial occurrence的PE00 input1、
    address、broadcast/serialization与lifetime。node0001的64项min/max
    `3.840008033773046e-10 / 0.001863094512373209`证明single fixed constant不可行。
    规则`CDA-REQUANT-PER-CHANNEL-MULTIPLIER-OCCURRENCE-SUPPLY-001`已发布；报告
    `artifacts/operator_config_validation/requant_5pe_physical_boundaries_v1/report.json`
    SHA-256 `0daab3582284b338c09072f81bcb7d5e3fcde8dc1917ad1d99dadcee84efc2a1`，
    blocked_valid=true、errors=0。strict/materialization与全部动态门不变。
19. Requant multiplier occurrence-supply proof进一步关闭exact payload、channel axis、scalar
    与one-lane supply子叶：直接解析正式ONNX 129个FP32 initializer并按sequential float32
    公式重建26,561个元素，54/54 byte SHA逐项等于lowering/evidence；53个Conv的axis0
    精确绑定output C，native B layout `[M_outer8,m8]`按`B_base+4*c`跨N广播；
    MatMul `hwop-0075-01` scalar bits=`0x3a510db3`可由PE00 constant 32-bit capture持久供应。
    唯一首断点精化为`CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1`：
    node0001 channel0 `0x3a013ecf`到PE00，但channel1 `0x3925d60c`按8-wide native lane
    到PE10；5PE链的PE10已保留给magic，而multiplier只在PE00消费。current handler只改
    IGA loop end与A/B/D stride，没有B spatial remap/size、inport1 lane remap/mask、
    PE00 lane phase/keep boundary或lane-phase loop。报告
    `artifacts/operator_config_validation/requant_multiplier_occurrence_supply_v1/report.json`
    SHA-256 `ee54376962896214a2327aa5bb61fdb1d450e16521abe2f7d89326f5fea50f04`，
    blocked_valid=true、errors=0、tests 2/2 PASS。下一步只允许在隔离B路径证明现有
    hardware fields能否表达lane-phase serialization；不得改RTL/ISA或进入strict/backend/
    package/server。
20. Requant lane-phase serialization已在existing hardware field equation层证明53/53可表达，
    不需要动态lane mux：对channel `c`从`B_base+4*c`精确读取4B；buffer2 col0使用
    `buf_spatial_stride=[0,1,2,3]`、`buf_spatial_size=4`并只开lane0 mask；GA inport1
    只开lane0，经group1/source0送PE00.inport1；PE00 keep跨已证明的serialized occurrence
    loop保持`B[c]`，再由buffer validity/clear/backpressure装载`c+1`。每个原8-wide
    group拆成8个scalar phases；性能未测。证明组合绑定pinned ndp-sim
    `ec124245…`的4B scalar memory→bank0→GA lane0与B/buffer2/inport1/PE00 keep原生路径，
    并核current memory/buffer/request/inport方程；53个Conv全部LC/index/stride/address
    capacity PASS，`(4*c)%16∈{0,4,8,12}`保证每个payload不跨16B beat。原channel1
    `0x3925d60c→PE10`反例被scalar phase绕开而未豁免。报告
    `artifacts/operator_config_validation/requant_lane_phase_serialization_isolated_v1/report.json`
    SHA-256 `1fa2ad8e55be5e4d67e11b2001386dd8a92dafef61da6bb9883d8ea9a68c75ba`，
    pass=true、errors=0、tests 2/2 PASS。下一步按依赖顺序先生成隔离Requant strict JSON
    materializer并过complete-JSON门；只有该门闭合后才启动QAdd materializer。backend、
    mapping/bitstream/execplan/SCA/package/server与dynamic/E4/E5继续禁止。
21. 上述field expressibility现已有optimizer隔离worktree的exact machine receipt：53个
    per-channel stage均证明`shard→phase0..7→N-inner`双射，A/D地址为
    `base+4*((shard*N+n)*8+phase)`；B使用`idx_size=[3,0,null]`、total `4B`、
    stride `4`、spatial size `4`与lane0 mask，PE00 input1 keep跨N保持。MatMul
    `hwop-0075-01`明确标为`prior_scalar_supply_consumed`且`phase_count=0`，没有伪造
    phase coverage。隔离报告
    `artifacts/operator_config_validation/r5_requant_lane_phase_serialization_proof_v1/report.json`
    bytes=`206,014`、SHA-256
    `dcaebda9691bee613163ca3f5504764599c38c865bbee0bc414166533526e469`；
    direct tests 5/5、negative controls 9/9、py_compile均PASS。
    `B_REQUANT_5PE_PHYSICAL_MULTIPLIER_SUPPLY`仅在JSON field expressibility层关闭。
    这些文件未复制到主工作区；主线只登记exact receipt。optimizer现继续已授权的隔离
    Requant strict materializer，QAdd继续等待其strict complete-JSON gate；禁止范围不变。
22. Requant strict materializer随后已正式闭合并取代第21项的“执行中”状态：
    54/54 strict operator JSON全部通过，包含53个Conv per-channel scalar-phase stage和
    1个MatMul scalar stage；multiplier bits共26,561个，provenance leaves=`50,095`，
    `UNRESOLVED=0`。shared candidate validator为54/54 PASS、errors=0、
    completion_blockers=0；`PINNED_EXACT_STAGE_IDS` family-set
    expected/covered=`54/54`，missing/unexpected/duplicate/type/SHA错误均空；
    tests 23/23及负控全部PASS。正式报告
    `artifacts/operator_config_validation/r5_requant_scalar_phase_strict_json_v1/report.json`
    SHA-256 `9b426c6731be52e5a68eec300d6765cc1589cec2c1a3decea66fad107cdf9ddf`。
    关闭`B_REQUANT_CONV53_SCALAR_PHASE_STRICT_MATERIALIZATION`与
    `B_COMPLETE_JSON_REQUANT_SEQUENTIAL_RNE_ZP_SATURATION_COMPOSITE_CAPABILITY`；
    backend/dynamic/guard/E4/E5继续开放。较早的optimizer multiplier-payload PASS仅作
    provenance阶段证据，不得把主线回退到strict candidate IN_PROGRESS。QAdd依赖门已
    关闭，其隔离six-qparam strict materializer现为ACTIVE；仍禁止backend/package/server。
23. 服务器包存储已从flat目录迁为`pending/tested/superseded`三态并建立
    `PACKAGE_STORAGE_INDEX.json`。当前68个包全部保持原字节：pending=`4`、tested=`41`、
    superseded=`23`；pending仅含GAP v40、serialized Conv v49、QAdd v36、native Conv
    p10，四个family各恰好一份。QLinearMatMul v9已有正式return，归入tested并等待
    GAP v40裁决，禁止重复运行。后续fresh包必须执行
    `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`与
    `tools/manage_server_test_package_storage.py rotate`：旧pending有正式return才进入
    tested；未运行/中间/隔离身份进入superseded；禁止删除、覆盖或同族多pending。
    用户取包入口进一步扁平化为`pending/<package-id>.zip`，该目录只留4个ZIP；
    sidecar、validation/final-audit等全部移入
    `pending_receipts/<family>/<package-id>/`，无需用户主动取用或单独回传。
24. QLinearAdd six-qparam strict materializer已正式闭合并取代第22项末尾的`ACTIVE`：
    17/17 lowering stages均生成local relocatable strict JSON；shared candidate 17/17 PASS，
    provenance leaves=`17,588`、`UNRESOLVED=0`，pinned exact family-set expected/covered=
    `17/17`。node0076采用16次硬件重复source-B读取，`materialized_by_host=false`且
    `host_precomputed_internal_tensor=false`。关闭six-qparam typed materialization、
    exact divide/RNE slow composite与node0076 broadcast replay三个complete-JSON blocker；
    backend/dynamic与server E4/E5继续开放。未生成mapping/bitstream/execplan/SCA/ZIP，
    pending QAdd v36 ZIP身份与SHA保持不变，取用路径已压缩为扁平`pending/`。
25. 整网测试收敛优化专项会话`019fd276-14c5-7800-94db-87ebfb9ce632`的通信边界已
    明确：它不承担主线常规进度广播、存储规则同步、其它family状态或无关消费回执。
    仅当信息直接涉及其当前事项、需要其执行/裁决、改变其输入或边界、或构成专项阻塞时
    才可派发；专项自身的正式完成/阻塞回传仍必须发送主线。
26. Requant 54-stage隔离backend动态审计已闭合本地W3数值层：54/54 stages、
    `169,410,176`个真实W3 elements两次全量运行均`mismatch=0`，exact phases=`28,353`，
    external scratch=`0`。pinned cycle model下scalar line requests=`254,096,264`，
    ideal exact 8-lane what-if=`63,528,816`，故当前裁决为
    `SCALAR_INPUT_TRANSACTION_DOMINATED`；不得据此提案优先做fence或8-lane RTL。
    export-emulator不等于native mapper/encoder，generic quant handler仍是placeholder，
    因而blocker收窄为
    `B_REQUANT_SCALAR_PHASE_NATIVE_MAPPER_ENCODER_AND_CYCLE_EXECUTION`，natural terminal、
    E3/E4/E5均未提升。权威报告保留在优化专项worktree，SHA-256
    `ec6656400761a5c3dc1e6c1879a08b314ac7741a8b68562f6835c71d2f4bc454`。
27. native Conv p9b正式return已证明`transout_last_index=5`跨过p8f旧停点，但未闭合
    c0 terminal：qualified events=`139,198,964`、slice_finish=`0`。首分歧收窄到
    actual ARM terminal semantics、MSE4 last-index传播、SA-output→Buffer5 accepted
    三候选。唯一fresh p10以bounded triggered observability同包覆盖三者；p9b整套归
    tested，p10以ZIP-only短路径成为本族唯一pending。p9b无正式320D，E3/E4/E5均未提升。

## 5. 当前开放 blocker

- GAP：v58在0 ps命中shared UCLI portable escape，sum_s2未执行；等待shared fix。natural terminal、
  formal D 48及E3/E4/E5仍开放。
- QAdd：v59在compile前命中manifest install_name/SCA namespace身份错误；修正后继等待shared fix。
  历史selected-port lanes-not-ready边界、full-chain natural、28D及E3/E4/E5继续开放。
- serialized Conv：旧ACK RTL矛盾已确认为observer/source-identity误报；v88b同时在0 ps命中shared
  portable escape。等待shared fix；natural terminal、formal D 320及E3/E4/E5继续开放。
- native Conv：p43 compile通过但在0 ps命中shared portable escape；MSE4可信wdata/slice-finish、
  c0 natural、formal D 320及E3/E4/E5仍开放。
- node0075：等待GAP生产者动态闭合后，再裁决producer acceptance→pass00 first read、
  8192 actual reads/hash、natural terminal与144D。
- 最终整网：shared allocator/execplan/coverage/lifetime与133-stage integration assembly。

## 6. 当前规则入口

- `.agents/rules/生成前必读索引.md`
- `.agents/rules/算子配置规则.md`
- `.agents/rules/NDP硬件字段语义.md`
- `.agents/rules/服务器测试包生成规则.md`
- `.agents/rules/整网测试收敛优化专项规则.md`
- 当前目标算子专项规则
