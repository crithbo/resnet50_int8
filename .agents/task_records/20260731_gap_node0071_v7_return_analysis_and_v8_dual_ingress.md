# GAP node0071 v7 formal return analysis and v8 dual-ingress localization

Date: 2026-07-31  
Owner thread: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

- 输入 return：`r5_n71_gap_v7_finalaudit_return.zip`
  - bytes: `105642`
  - SHA-256: `f7ebfd83d56edb189471f617c7f85df89dda0d035038529397e451cd7e7a5d1b`
  - 相邻 sidecar SHA-256:
    `6106f10a69c7f5fb7d4a7b4ac35155a9361616ba55d777320399ab00ef242ba3`
  - sidecar 的 name/hash 精确匹配。
- 绑定源包：`r5_n71_gap_v7_finalaudit.zip`
  - SHA-256: `6ae39b218e622f9937753dd4d4d649b1d2a7420c49ec5ed71d00fe8c26abd068`
  - return 内 `PACKAGE_MANIFEST` 与源包 manifest 字节相同，SHA-256:
    `bfcc0d385ae08913d112c7a32bbb9e646b98232a2e7a2569096655fdca164504`
- ZIP CRC、23 项 RETURN_MANIFEST exact-set、逐项 size/hash、manifest allowlist-only
  均通过；禁止项为 0。
- package/install preflight 均通过；runtime D 初始不存在；25 个 preload、SCA/SCA_D
  echo、actual compile/simulator argv、observer source/incdir/macro/runtime/time0/return/trap
  四向绑定均成立。
- compile exit `0`；simulation/runner exit `125`；signal=`INT`；无自然 terminal。
- 48 项 formal D 全部缺失：
  `16 × {sum_int32, scaled_fp32, final_uint8}`。`mismatch_byte_count=0`
  仅表示没有可比较数据，不能作为 PASS。
- 联合门：
  `compile0=true, simulation0=false, natural_terminal=false,
  formal_exact_set=false, missing0=false, mismatch0=true`，总门 false。
- 动态分类：`FIRST_DYNAMIC_FAILURE + NO_DYNAMIC_BASELINE`，不是 regression。

## PROGRESS_ADJUDICATION

唯一完整 canonical decision：

```text
LONG_RUNNING_HANG_AT_ANY_MSE_READ_DATA_ACCEPTED
reason=no qualified handshake/edge counter advanced for at least stall_window
```

- simulation 墙钟 `14176.185805396 s`，约 3h56m16s。
- 最后完整 summary：`161265879000 ps`；INT：`161341086875 ps`。
- 493 个完整 summary；active cycles `0 -> 128450560`。
- 距最后 qualified progress 平坦 `128188416` cycles，
  等于 `122.25 × 1048576` stall windows。
- qualified 末快照：
  `gexec=3, request=28, rdata=23, wdata=0,
  mse4_req=(1,1), mse4_wdata=(0,0)`。
- buffer4/buffer5 的持续高 level 被明确排除，不算 monotonic progress。
- canonical self-test 与持续高 level、summary append、冲突双裁决、缺 reason、
  缺 boundary 等负控全部 fail closed。

## FIRST_DIVERGENCE / HANG_ROOT_CAUSE

- last-good：
  - MSE4 两路 D write-address request 在 `702692000 ps` 已接受；
  - MSE0→Buffer0 在 `702772000 ps` 有一次 qualified acceptance；
  - MSE0 read consume 持续到 `702786000 ps`。
- first-bad：
  - 8 个活动 regular GA PE 在 `128450560` active cycles 内
    `accepted input=0`；
  - 随后 `GA output=0`、`MSE4 write-data=(0,0)`、无 terminal、48 D 全缺。
- 精确最窄边界：

```text
MSE0_TO_BUFFER0_ACCEPTED
  + READ_STREAM3_PATH_UNOBSERVED
  -> GA_DUAL_OPERAND_ACCEPT_ABSENT
```

`HANG_ROOT_CAUSE=UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT`。冻结配置使用独立 A/C/D
LC branch，LC 范围小且静态可达；v7 证据排除了 compile、安装、配置文件装载、
observer 绑定、持续 qualified progress、自然完成和 MSE4 write-data 完成。
但 v7 未观测 READ_STREAM3/MSE3→Buffer4 与 GA 每个操作数的 capture/tag match，
因此不能把责任确定归为 CONFIG 或 RTL。

## E3/E4/E5

```text
E3=false
E4=false
E5=false
```

理由：signal INT、无自然 terminal、48/48 formal D 缺失，且该兼容 profile
没有绑定最终服务器 RTL source identity。

## BLOCKER_DELTA

- 已关闭：cwd、package namespace、SCA leaf、observer include/macro/runtime-return
  等既有包基础设施分歧。
- 新确认：真实执行进入后，在 GA dual-operand acceptance 前发生长期停滞。
- 仍开放：MSE3 request/read-data、MSE3→Buffer4 acceptance、Buffer0/Buffer4
  per-operand capture/tag match 三者中的首个丢失边界。
- 没有证据把内部未变化 level 或 mismatch=0 升级为 PASS。

## PACKAGE_RELEASE

由于证据缺口直接阻止 CONFIG/RTL 根因裁决，生成唯一窄诊断后继：

```text
identity=r5_n71_gap_v8_dual_ingress
claim=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
status=PACKAGE_READY_NOT_RUN
```

- 冻结 v7 config/golden/workload/timeout；73 个 numeric workload 文件 exact-tree
  相同；未重跑 GAP sum/tail 数值。
- 仅增加 uncapped qualified counters：
  - MSE0 `mse2buf_wvalid && buf2mse_wreq_ready`
  - MSE3 `mse2buf_wvalid && buf2mse_wreq_ready`
  - GA `ga_pe_inbuffer_enable[0]`
  - GA `ga_pe_inbuffer_enable[2]`
  - GA `pipeline0_enable && alu_input_valid_bit`
- 新记录使用独立 `DUAL_INGRESS_COUNTS` 行，不改变既有 canonical parser、
  progress participants、timeout 或 DUT 行为。
- final ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v8_dual_ingress.zip`
  - bytes: `1791519`
  - SHA-256: `cb1b43b3e8228951a2c62e8de02b36f17291a2561048cb1b36c0a9ed876b5a0f`
- sidecar SHA-256:
  `66504e75d9573cb8a8d1f415a58ed8943da4a18e0149806795aa09d78a4a388a`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`。
- canonical、observer 四向、dual-ingress 四项定向负控、fresh preflight、
  canonical self-test、runner bash syntax 均 exit `0`；所有要求的负控 fail closed。
- 唯一命令：
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- 预期 return：
  `r5_n71_gap_v8_dual_ingress_return.zip` 与相邻 `.sha256`。

## RULE_DELTA_PROPOSAL

建议主线固化但本任务未修改公共规则：

1. 对双输入 GA/FIFO 停滞定位，observer 至少分别统计两个 producer→buffer
   qualified acceptance、每个启用 operand 的 inbuffer capture，以及 joint GA accept。
2. raw buffer level、valid level 或未限定 ready level 不得替代上述 qualified event。
3. all formal readback missing 时，`mismatch_count=0` 必须显式标记为 unevaluable，
   不能满足 PASS。

## Receipts

- index:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- server rules:
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`
- GAP int32:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- GAP dynamic:
  `2dee42a883bde9c1650710c8312d23e661aeb3c66ef9d1d4e15524af79c33dc7`
- exact UINT8 tail:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- plan mutable provenance:
  `e4beaa39dfd5bd3c247d546dc2fc431758e1038cbef806e7b5a8f5b49e09ac6a`
- final audit report:
  `1259d3b6a77f35933f1215e0794a55415d6b6c1970c41a8a993d372bbd656be6`

No server inspection outside the supplied return, no upload, no run, no lease,
no public-rule/plan/functional-RTL modification.
