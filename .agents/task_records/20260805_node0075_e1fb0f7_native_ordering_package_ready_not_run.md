# node0075 e1fb0f7 native-ordering integration PACKAGE_READY_NOT_RUN

日期：2026-08-05  
owner：QLinearMatMul / node0075 independent owner  
唯一结构化回传目标：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 1. 最终裁决

- `PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`
- `candidate_release=false`
- `diagnostic_class=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- `evidence_level=E2_LOCAL_ONLY`
- 未上传、未运行服务器、未取 lease。
- 未修改 functional RTL、`.agents/plan.md`、public rules 或其他 operator family 资产。
- 最终流只使用一个 simulator / 一个 execplan：
  graph external typed UINT8 input → 真实 node0071 8 stages → 正常 command/config
  transition → node0075 8 accum + 8 scale + 8 exact UINT8 round stages。
- 不声明通用 visibility barrier；`opcode110_is_barrier=false`。动态失败优先分类为
  `INSTANCE_SCHEDULING_OR_ORDERING_FIRST_NOT_AUTOMATIC_RTL`。

## 2. current 身份与生成后规则复读

- active RTL commit：
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- RTL checkout：clean。
- RTL sync report：
  `artifacts/rtl_sync/trassic_master_e1fb0f7_20260804/report.json`
  - SHA256：
    `c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c`
- 生成后 current plan：
  `003db92dfd8cc7fc0beda6201d522b79e264cfb982ec9571e7bbe135076af844`
  - plan 是 mutable provenance；其 node0075 裁决仍为
    `DIAGNOSTIC_INTEGRATION_BUILDING / NO_EXPLICIT_BARRIER_CLAIM`，与最终包语义一致。
- current 规则 SHA：
  - agent：
    `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
  - index：
    `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
  - common operator：
    `8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497`
  - NDP hardware：
    `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
  - server package：
    `5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9`
  - INT8 SA：
    `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
  - exact UINT8 tail：
    `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
  - hardware simulator entry：
    `e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba`

## 3. integration E2

目录：
`artifacts/operator_config_validation/r5-node0071-node0075-e1fb0f7-native-ordering-integration-v1`

- report：
  `4c3972f5769530db6e0acd4269b941ea50251b8a7625d610057efb4d4b93964a`
- independent validation：
  `86935aeb40781bb359e6b9cb065dc4f737de2a0074308f1def46476b1c888eea`
- 状态：
  `CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_VALIDATION_PASS`
- 32 ordered stages，518 条 128-bit execplan line，32 个 `Start_Comp`。
- producer prefix 保留 8 个 opcode110 slot，但不赋予 barrier 语义。
- producer/consumer boundary 插入 line 数为 0。
- 为避开 node0075 B pass01 与旧 node0071 config storage 重叠，仅重定位 8 个
  node0071 config storage base 到 `0x016e0000..0x016e1c00`（stride `0x400`）；
  node0071 data address relocation 数为 0。
- graph external typed input：16。
- node0075 B destination：128；每 pass 的 exact B payload 可供 16 个不同 destination
  base 使用，不发生 host relayout。
- A preload：0。
- runtime D preseed：0。
- SCA config：8 个 node0071 + 24 个 node0075，共 32。
- SCA_D / formal readback：144：
  - node0071 final UINT8：16；
  - node0075 final UINT8 fragment：8 pass × 16 slice = 128。

### 逐 stage / slice golden

已生成，不是只生成最终节点 golden：

- node0071：`sum_int32/scaled_fp32/final_uint8 × 16 slice = 48`
- node0075：`accum_int32/scaled_fp32/final_uint8 × 8 pass × 16 slice = 384`
- 合计：432 个 stage/slice golden。
- node0071 的 16 个 final UINT8 golden 与 node0075 的 16 个 A slice byte set
  逐字节相等。

## 4. 恰好 8-pass A consumer

- stock-SA 推导的最小必要 reload：
  `ceil(1000 / (16 * 8)) = 8`
- 实际配置 pass 数：8，不是无界重复。
- 每 pass：
  - 16 slice；
  - 每 slice 64 × 32B accepted-read occurrence；
  - 1024 occurrence；
  - 32768B traffic。
- 全部 8 pass：
  - 8192 × 32B configured qualified consumer occurrence；
  - 262144B configured traffic；
  - unique A byte set 仍为 32768B。
- 以上 `accepted/configured` 数字是 E2 物化合同，不冒充服务器 actual acceptance。
  package-local observer 在服务器端逐事件记录并重新计算每 pass/slice ordered-address
  hash 和 read-byte-set hash；只有实际 8192 条事件闭合才通过动态门。

## 5. fresh server package

最终身份：
`r5_n71_n75_e1f_native_v3`

- package：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_n75_e1f_native_v3`
- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_n75_e1f_native_v3.zip`
  - bytes：`3753949`
  - SHA256：
    `cfd37a380bc862a6a3c2d22bff01d0fe9b2ec2a25c04e9bae2bd7982971efae6`
- sidecar：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_n75_e1f_native_v3.zip.sha256`
  - bytes：`95`
  - SHA256：
    `82668cbce3377ce660fef1af38f85bd74e0e60a89e802c698953d8690bf5cf5a`
- manifest：
  - SHA256：
    `098589160058aaab8f9936de0030d802b790e485d6fba29756518363aa1a44c9`
  - package files：502；
  - workload files：491；
  - readback checks：144；
  - manifest-driven return allowlist records：162。
- build report：
  `artifacts/operator_config_validation/r5-node0071-node0075-e1fb0f7-native-ordering-package-v3/build_report.json`
  - SHA256：
    `db1e5823bb1fd0e11e35246fc8042d27bbeb94c296719cfea8eba927efe331f1`
  - deterministic double-build byte equal：true。

唯一服务器命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期 return：
`r5_n71_n75_e1f_native_v3_return.zip`

### 保留但不发布的旧构建

- `r5_n71_n75_e1f_native_v1`：缺少 manifest-driven return allowlist；
- `r5_n71_n75_e1f_native_v2`：canonical parser 尚未拒绝裁决后的 summary-only；
- 两者均维持 `HELD_PENDING_FINAL_ZIP_SELF_AUDIT`，`PACKAGE_RELEASE=NONE`，
  不得进入运行队列。

## 6. final-ZIP self-audit

report：
`artifacts/operator_config_validation/r5-node0071-node0075-e1fb0f7-native-ordering-package-v3/final_zip_self_audit.json`

- SHA256：
  `32de05bb67ff44646bc5c6e1fe4acbd45ae69b225e9dafcc025c0ac397f6429a`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- ZIP CRC/single-root/path traversal/duplicate/symlink/exact-set/sidecar：PASS。
- fresh-extract package preflight / installed workload / runtime-D absent：PASS。
- path budget 正控及三类负控：PASS。
- observer source/include/macro/runtime-return 四向绑定及四类负控：PASS。
- feature enable/limit/time-0/return target 四类负控：PASS。
- canonical decision：
  - 唯一完整记录正控：PASS；
  - 无 qualified progress；
  - canonical 后追加 summary-only；
  - 两条冲突 canonical；
  - 缺 reason/boundary；
  均 fail closed。
- package-local HDL focused Icarus syntax/name-resolution：PASS。
- actual canonical/result consumer equivalence class：17；
  uncovered：0；逐 class consumer typo 均 fail closed。
- declaration delete / consumer misspell / initialization delete：均 fail closed。
- 安全 compile stub 到达 compile 并以唯一 exit 86 走完 finalizer/最小 return：PASS。
- package identity mutation 在 compile 前 fail closed：PASS。
- TERM signal stub 走共享 finalizer并生成部分 return：PASS。
- bootstrap package tree 在全部自检前后逐字节不变。

## 7. blocker delta

关闭或降级为非生成阻塞：

- `B_MATMUL_NODE0075_NATIVE_ORDERING_INTEGRATION_MATERIALIZATION`：
  已由 config-bound E2、独立 validation 和 fresh package 关闭。
- `B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED`：
  不再作为 package-generation blocker；按用户授权改走真实 producer prefix +
  normal command transition，明确保持 `NO_EXPLICIT_BARRIER_CLAIM`。这不等于证明通用
  fence/barrier。

仍需正式服务器 return 才能关闭：

- `B_MATMUL_NODE0075_SERVER_NATURAL_TERMINAL`
- `B_MATMUL_NODE0075_FORMAL_D`
- producer downstream/hub actual acceptance；
- node0075 pass00 first actual read 的顺序门；
- 恰好 8192 × 32B actual accepted A reads 及其逐 pass/slice hash。

## 8. 规则反馈

`RULE_CONFIRMATION`

- `CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001`：
  opcode110 未被冒充为 barrier；本包不作显式 barrier claim。
- `CDA-SERVER-WORKLOAD-PROVENANCE-001`：
  联合流从 graph external typed input 开始，禁止路径均为 false。
- `CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001`：
  144 个 runtime D target 在 package/pre-sim 均不存在。
- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`：
  final ZIP exact observer bytes 的 focused syntax/name-resolution 与状态闭包通过。
- `CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`：
  17 个 actual consumer equivalence class 全覆盖，uncovered=0。
- `CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`、
  `CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`、
  `CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`、
  `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`：
  final ZIP 正负控均通过。

`RULE_DELTA_PROPOSAL=[]`。现有 current 规则已能非同义地表达本轮语义和放行门，
不需要修改 public rules。

