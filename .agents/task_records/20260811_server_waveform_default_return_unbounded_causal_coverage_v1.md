# 默认 VPD、无限大小 formal return 与三族 fresh rebuild 激活

日期：2026-08-11  
owner：`mainline.control` / `019ff027-e7db-72a3-b282-cfad8708da05` / owner epoch 2  
registry epoch：6  
rule：`CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001`  
shared gate epoch：`waveform-mandatory-v2-01ca6d7cd4a4a270`

## 用户裁决

所有可能进入 DUT simulation 的 fresh 服务器包默认启用 VPD；formal return 必须回收全部
`wave.vpd`/shard，波形不设 ZIP、解压、单文件或总量上限，不允许截断、采样或按大小删除。
默认从 `tb_NDP_Top_new_phy` depth 0 保留全层级；只有逐 scope 绑定机器证据、证明与当前卡点
无因果关系时才能裁剪。simulation 已启动但缺波形必须 fail closed；compile 未成功或 simulation
未启动可无波形，但 compile-core 仍必须返回。用户随后限定本轮重建为 GAP、serialized Conv 和
native Conv；QAdd 继续 HOLD。

## 旧包 HOLD 与先前进展

- GAP：v54 已闭合 remote owner-ready 根因；旧 v55 已本地证明 slice-local base 绕行，因旧
  `DUMP_VCD=0` 语义撤入 superseded。fresh 版本只新增 mandatory VPD/runtime-return，用于动态
  验证绕行并一次定位剩余因果。
- serialized Conv：v85b 已把 production compile exit 2 定位到两处 package-local observer
  `arb_req_ready` XMR；旧 v86b 保留 observer/first-error 修复但因旧波形语义撤入 superseded。
  fresh 版本用于越过该 compile 根因，并以全层级 VPD 继续 ACK、natural terminal 与 formal D。
- native Conv：p39 已把 production compile exit 2 定位到两处 package-local observer XMR；
  旧 p40 保留 datahub public-surface/structured-first-error 修复但因旧波形语义撤入 superseded。
  fresh 版本用于越过该 compile 根因，并以全层级 VPD 定位 MSE4 因果。
- QAdd：v57h 旧语义包已在 superseded；本轮未获重建派发，继续
  `HOLD_WAVEFORM_REBUILD_REQUIRED`。

存储审计在激活时为 `pass=true`、pending/tested/superseded=`0/113/45`、
`pending_by_family={}`。没有服务器 upload/run/lease。

## 公共规则与入口

公共入口收据：

| path | bytes | SHA-256 |
|---|---:|---|
| `.agents/agent.md` | 19639 | `dd9c97e80eeda55e4867253b68e1268ee554372f190ee830894b2c0742ec7bed` |
| `.agents/rules/生成前必读索引.md` | 8001 | `34b18b818ecea7931bd9e494c1f93d8ac03c206b5ae058d7049d2de0b1b54347` |
| `.agents/rules/服务器测试包生成规则.md` | 153609 | `a3b53a790fcb50c8199e962aad62f7f535a5623f3465c4e50853858fa6b2a6d1` |
| `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` | 7207 | `1d584d45ff9293e106d991e84319f2ebd4a1c69bcc222725d77f217a10872c39` |
| `contracts/active_rule_registry_v1.json` | 9942 | `f10314efa6d6248d7144b351ea001afdc088d5888b55b313df962969f652c212` |

共享 v2 机器门：

| path | bytes | SHA-256 |
|---|---:|---|
| `schemas/server_waveform_mandatory_plan_v2.schema.json` | 4854 | `18eb2d9acb4ace953cc14c2895bd73bd2d7a027313ab7e29870c07bfde09006d` |
| `schemas/server_waveform_runtime_receipt_v2.schema.json` | 2257 | `c48caae61328df9d3d097048e0ada16eae0e57ee5eab7d4dbea964c24f6abb4b` |
| `tools/server_waveform_mandatory_return.py` | 32490 | `2cc8febaa2854ef94d707d46551fc91ad37eb532fcaab2ec5e86677cfc79af4f` |
| `contracts/server_waveform_mandatory_return_dispatch_v2.json` | 3101 | `3afb5ec39428494e4412a95a8796e5734c7ad2c690f52c8c1282ff1901233b74` |
| `contracts/server_package_build_gate_registry_v1.json` | 13494 | `ef9e43de10e860aeb00eb808461c0510fb13823f9d5a5f8b89b0c8396e3c3fc1` |
| `tests/test_server_waveform_mandatory_return.py` | 12690 | `acfc1bfaf7795e08a397c62b3f239637ed8eb13465b2332914a5bd22322664e3` |

主线 current partial-exit 基线上的 waveform-only 语义合并：

| path | bytes | SHA-256 |
|---|---:|---|
| `schemas/server_post_sim_return_request_v1.schema.json` | 3211 | `897825bea44f1d2bd1c2960c6209ae94b51d92fb073076ef4d284495b0ddfc36` |
| `tools/server_post_sim_return.py` | 66971 | `475ddab18d22589ba969ca064a87880cbc4e5172d3ec35da2d574fb6e83a3436` |
| `contracts/server_post_sim_return_next_fresh_dispatch_v1.json` | 3175 | `d7af5a20ac1dad3b5e724a29c41e2cd41e78ce7417405017c9ea71bad3d62765` |
| `tests/test_server_post_sim_return.py` | 22807 | `c4731431f5117f3f60640164d720fc9a05b3a2bbc54d8163d15b6a2a79375db8` |

该合并明确保留 `PARTIAL_EXIT_RULE_ID`、`_validate_partial_exit_profile`、
`_exercise_partial_exit_plugins`、profile contract 和全部 partial-exit 正负场景，没有用 optimizer
旧 worktree 基线覆盖 current helper。

## 验证与激活

- 主线合并后 focused unittest：31/31 PASS（post-sim + mandatory waveform v2）。
- optimizer 独立基线 focused unittest：40/40 PASS；其中过时 v1 observation test 的依赖不在
  其机械 exact-set，主线未把该孤立测试纳入 active v2 门。
- 9 个 JSON/schema/contract/registry parse PASS。
- active rule registry audit：14 个活动规则、159 个定义、0 duplicate、0 warning/error。
- scoped `git diff --check` PASS。
- 8 MiB VPD 流式复制、ZIP64、identity/SHA 正控 PASS；dump=0、started missing wave、allowlist
  漏波形、硬大小 cap、无证据裁剪、self-inclusion/path escape 均 fail closed。

因此 `SHARED_WAVEFORM_GATE_ACTIVATED` 已发送给 GAP、serialized Conv、native Conv owner；三族
进入 fresh rebuild，且只允许改变 waveform/runtime-return 必要面。QAdd 不在本轮派发集合。

## Claim boundary

共享门与本地测试不证明 production compile、DUT simulation、natural terminal、formal D、E3、
E4 或 E5。没有修改 functional RTL/config/numeric/workload/目标 diagnostic，没有服务器动作。
