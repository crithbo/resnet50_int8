# Conv node0004 v14 return 与 ping-pong-off 裁决

日期：2026-07-31  
owner：Conv / SA  
唯一回传主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

- 正式 return：
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n4_hw_v14_a_pingpong_fix_return.zip`
- bytes=`28346`
- SHA256=`5a075ae69e0f89aa2da356c9968ea79de099ec7b38e1ba20b19c8a6757d2525d`
- 外部 sidecar file SHA256=`bf75592cb96420b5ab155a91b750ad31f40f0488f19addb1c72792a9a62cda8f`，声明的 name/hash 与 return 精确匹配。
- 冻结 source package：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v14_a_pingpong_fix.zip`
- source SHA256=`4bf890b5ad57d8952226125de4979e96e0c00a1d347d2fb59aec7cabb1cf44b2`
- ZIP CRC、单根、allowlist exact-set、9/9 record size/SHA 均通过。
- package/install/observer preflight 均通过；runtime D 初始不存在；observer SHA
  `a40c522fc3dc962dedcda76291df97bb856315c82ff71fbd593127c541322b0a`
  与 source package、package preflight、observer precompile 四方一致。
- `compile_exit_status=2`，`run_exit_status=125`，`signal_status=NONE`。
- 编译没有完成，因此 simulation 未启动、natural terminal 未出现、真实 canonical
  progress 为 0、formal D 为 0 项。runtime fallback canonical 不是 observer 的动态证据。
- E3=false、E4=false、E5=false；all-missing 且 mismatch 未执行不能解释为通过。

机器报告：

- `contracts/operator_config/node0004_v14_return_analysis_v1.json`
- SHA256=`adc3cc11b2f01189e9ee44c67ea5f6cf523ab53aeef86d00cfed52c2b1f1fb73`
- analyzer：
  `tools/analyze_node0004_v14_return.py`
- SHA256=`7ea420426b628d4a8097e93fba5f199dbc5de5a2841ce48b84ff154916b87fd4`
- analyzer exit=`0`

## FIRST_DIVERGENCE

首分歧在 package-local read-only observer 的 VCS 编译，不在 Conv 配置或功能 RTL：

```text
tb_probe/native_return_observer.svh:2405
token is '['
[`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][0],
```

旧表达式先用运行时 group/slice 选择 packed 维度，再尝试选择完整 ROW/COL
packed 范围和末位 A/B bit；VCS 在该 `[` 处语法失败，尚未进入 elaboration/simulation。

合法最小修复只改 package-local observer：

1. 保留原始 per-PE `masked_valid[1:0]`；
2. 用 elaboration-time generate 拆出 A/B 两个 monitor；
3. A/B monitor 的 group/slice 为 unpacked 外层，ROW/COL 为 packed 内层；
4. snapshot 运行时索引 unpacked group/slice 后直接得到 ROW×COL packed 向量。

最小语法 TB：

- `outputs/diagnostics/node0004_v14_return_v1/abpe_observer_aggregate_syntax_tb.sv`
- SHA256=`6694f8a4e7753ca94bc1d1396e2e1829461386d593b5b46c4dcd1c871d15a671`
- Icarus compile exit=`0`，run exit=`0`
- 输出：`PASS ABPE observer aggregate syntax A=1000 B=1000`
- VCS 最终编译仍须由新 return 证明；本地不冒充 E3。

## PINGPONG_OFF_ADJUDICATION

三栏结论：

1. **架构上可表达：true。** Producer 与 SA consumer 均保持 source/buffer0，
   Buffer manager 有 valid hold、backpressure、lifetime clear、address update 与 reuse
   机制，可以设计一个串行单缓冲 schedule。
2. **与当前 node0004 实例等价：false。** 不能只把两端 enable 置 0 后沿用当前
   LC/tag/terminal/bitstream。
3. **当前已证明正确：false。** 没有 fresh both-off
   JSON→mapping→bitstream→execplan/SCA→address/lifetime/terminal→local E2。

确定反例：

- 当前 v14 A 路为 stream0 ping-pong=`1`, last_index=`4`，SA inport0
  ping-pong=`1`, last_index=`4`。
- 第一个被接受的 source0 `(last=1,last_index=4)`：
  - matched-on：输出 logical last 被屏蔽，并在握手后切到 source1；
  - both-off：立即把 source0 last 送给 SA，握手后仍停在 source0。
- 因而 accepted terminal 和后续物理 source 已在第一处边界不同，不是性能差异。
- 若问题理解为 A/B 全部 ingress 都关闭，反例更直接：当前 B 由 stream1 固定写
  buffer2、stream2 固定写 buffer3，而 SA inport1 在二者间 ping-pong；只关闭
  SA inport1 会永久只读 buffer2，buffer3 的 B' 数据被搁置。

聚焦 RTL TB：

- `outputs/diagnostics/node0004_v14_return_v1/pingpong_off_terminal_counterexample_tb.sv`
- SHA256=`88e670f18f020984cab54a2f15f7d120cac95365612958d25530846a987903e6`
- compile exit=`0`，run exit=`0`
- 输出：`PASS node0004 ping-pong-off terminal counterexample`

裁决合同与 validator：

- `contracts/operator_config/node0004_pingpong_off_adjudication_v1.json`
  SHA256=`4e76c978be5edd44f36f382454520e56a2856707427b9471a66f4d731a8cadef`
- `tools/validate_node0004_pingpong_off_adjudication.py`
  SHA256=`2cd7545616f7d1bc82a826ac7693f70e19efee8cd789f8426979d53154057e81`
- validation report
  `artifacts/operator_config_validation/local_reaudit/node0004_v14_return_v1/pingpong_off_adjudication_validation.json`
  SHA256=`7be3d2375c644120f07fd5cc2716a6986e51d2f41c65fc87894d11e5b8cf774f`
- validator exit=`0`。

未来若主线单独授权 both-off，必须按新 schedule 重建 A occurrence 分区、
GROUP0 last owner、buffer0 refill/clear/reuse、A/B/C accepted-tag 对齐与完整物理资产；
不得作为默认值 leaf-only 修改。当前不值得替换 matched v14/v15 路线。

## PACKAGE_RELEASE

v14 隔离原因：`QUARANTINED_PACKAGE_OBSERVER_SYNTAX_COMPILE_FAILURE`。

fresh successor：

- package：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v15_abpe_syntax_fix.zip`
- bytes=`5813960`
- SHA256=`65e5b50b00046d662d219b71054f7f3f64c5794c98bf87dc134b5b3dd09a2130`
- sidecar file SHA256=`64202c079acf9c0af7c243f5eff5611c43da53ecb3376ce7296b9e943fa5af7d`
- status=`PACKAGE_READY_NOT_RUN`
- candidate_release=false
- server RTL entries=0
- 功能 RTL 修改=false
- node0004 配置/bitstream/execplan/SCA/矩阵/golden 均保持 v14；只修 package-local
  read-only observer。
- 单命令：
  `bash r5_n4_hw_v15_abpe_syntax_fix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- 预期 return：
  `r5_n4_hw_v15_abpe_syntax_fix_return.zip` 与相邻 `.sha256`

最终 ZIP 独立自检：

- report：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v15_abpe_syntax_fix.validation.json`
- report SHA256=`280fbbb31c79fd573d8914dbc885f7807f6a2552be2ef6dbda9f2c5e827ee3fd`
- validator：
  `tools/validate_node0004_v15_abpe_syntax_fix_final_zip.py`
- validator SHA256=`5e0684279c010e7e7fd83a075cd7af51bd502e1d0bcaa5298849303d704d4927`
- exit=`0`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- 所有既有 package 负控和新增 observer 语法/身份负控均 fail closed。
- deterministic independent rebuild SHA 与最终 ZIP 相同。

## Active receipts

- `.agents/plan.md`
  `558dce2c256f91bcf537750262b717db00c97ea415849d544cc13d365049a47e`
  （mutable provenance）
- `.agents/rules/生成前必读索引.md`
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`
- `.agents/rules/INT8_SA点积专项规则.md`
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

最终包生成后已重新完整读取这些入口；current-match 均为 true。应用规则包括：

- `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`
- `CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`
- `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`
- `CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`
- `CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-RETURN-RECEIPT-001`
- `CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001`
- `CDA-SA-NODE0004-ASSUMED-FIXED-HARDWARE-001`

## BLOCKER_DELTA

关闭：

- v14 return 身份/allowlist 不确定性；
- v14 package-local observer line 2405 语法首分歧；
- fresh successor 的 observer source/SHA/include/define/runtime/return 四方绑定与最终
  ZIP 自检。

打开：

- `B_NODE0004_V15_DYNAMIC_RETURN_PENDING`。

保持：

- E3/E4/E5 均未建立；
- v14 没有任何有效动态 Conv progress 或 formal D；
- ping-pong both-off 没有当前实例等价性证明。

## RULE_DELTA_PROPOSAL

`NONE`。现有规则已覆盖 return receipt、compile-first、observer binding、动态联合门和
最终 ZIP 自检。本轮没有发现必须写入公共规则的新共因。

## Scope receipts

- `numeric_analysis_repeated=false`
- `node0004_workload_rebuilt=false`
- 消费复用资产：只读消费冻结 v14 source package、v14 local config/physical assets 和
  活动 RTL；v15 沿用 v14 workload/config，只修 observer。
- `.agents/plan.md` 修改=false
- 公共 rules 修改=false
- 功能 RTL 修改=false
- 服务器检查/上传/运行=false
- 因 ping-pong-off 问题另生成包=false
