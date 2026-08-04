# 最小双 Stage 生命周期本地 E2 闭环

日期：2026-07-25

状态：`MINIMAL_TWO_STAGE_LIFECYCLE_LOCAL_E2_COMPLETE`

声明边界：

- `candidate_release=false`
- `formal_target_config=false`
- `server_package=false`
- 未修改 `NDP_copy01/rtl/` 或任何其他 `rtl/` 文件
- 这是通用 transport/lifetime 探针，不是 ResNet50 真实 stage 的批量放行

## 1. 规则

专项规则：`.agents/rules/最小双Stage生命周期规则.md`

SHA-256：
`821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171`

新增规则 ID：

1. `CDA-TWO-STAGE-MATERIALIZED-ROUNDTRIP-001`
2. `CDA-TWO-STAGE-DATA-ALIAS-001`
3. `CDA-TWO-STAGE-CONFIG-RELOAD-001`
4. `CDA-TWO-STAGE-BARRIER-ORDER-001`
5. `CDA-TWO-STAGE-TERMINATION-001`
6. `CDA-TWO-STAGE-DUAL-GOLDEN-001`

生成收据绑定了当前公共索引、公共算子配置规则、NDP 字段语义、两个原生算子 JSON、
实际 json loader/address planner/control-register/instruction/output/server-profile
消费者和硬件仿真入口。规则或消费者身份变化后必须重新阅读并重建收据。

## 2. 探针

固定为单 slice、两个不同原生普通 GA 算子：

```text
op0: prefill_mul_fp32MN_fp32M_fp32MN
     A0[1,8,32] * B0[1,1,32] -> D0[1,8,32]

op1: prefill_add_fp32MN_fp32MN_fp32MN
     D0[1,8,32] + B1[1,8,32] -> D1[1,8,32]
```

输入使用可精确表示的有限 fp32；D0、D1 分别保存独立逐 bit golden，单份大小均为
1024 bytes。

## 3. 最终物化结论

- 两份隔离工具副本、两份空 mapping cache、`PYTHONHASHSEED=0`、mapping seed 77
  完整重建；
- addressed request、两个 materialized JSON、两个 mapping、两个 bitstream、
  barrierized execplan、SCA/SCA_D 逐文件一致；
- stage0 materialized GA opcode 为 `mul`，stage1 为 `add`；
- 地址：
  - op0 A：`0x00000000`
  - op0 B：`0x00000400`
  - op0 D / op1 A：`0x00000480`
  - op1 B：`0x00000880`
  - op1 D：`0x00000C80`
- 主 CONFIG：
  - op0：`0x00001400`，payload SHA
    `21336bb7f7e36f799526dcd1cc6f896bd6c9968de09dba4bf8c41177a616862a`
  - op1：`0x00001800`，payload SHA
    `40a8a7ee5035ed2b150c4b567122e9813e8d1e4f42f6ce69e9f52dce5ed4d6e5`
- 两个 stage 均显式主 `Load_Config`；地址与 payload identity 均不同；
- 原生 `insert_server_completion_barriers` 生成 2 次 `Start_Comp`、2 次同 mask
  barrier，最后命令为 barrier；
- SCA `Repeat_Num=2`，runner 的 stage/start/barrier/repeat/sequence 全部为 2 且顺序
  精确为 `op0→op1`；
- 记录式本地执行器先写 D0，再从完全相同地址读入 op1 A，D0/D1 均逐 bit 通过。

## 4. 新发现并固化的可靠性门

原生 `write_install_manifest` 会为 producer-backed 的 `op1_matrixA_slice0` 生成
SCA preload 条目。直接沿用会把尚未计算的中间结果当外部输入预装。

处理方式：

- 原始 native SCA 只读保留为证据；
- runtime SCA 必须删除 `op1_matrixA_slice0`；
- consumer A 的授权来源改为 hash-bound addressed request 中的
  `source=op0` 与 `op0.D == op1.A == 0x00000480`；
- generic hardware frontend 在显式 `runtime_lifecycle` 下检测该 key，出现即
  fail-closed。

这是一项生成/装载边界问题，不是 RTL 修复。

## 5. 修改文件

- `.agents/rules/最小双Stage生命周期规则.md`
- `resnet50_pipeline/minimal_two_stage_lifecycle.py`
- `resnet50_pipeline/hardware_simulation_frontend.py`
- `tools/build_minimal_two_stage_lifecycle.py`
- `tests/test_minimal_two_stage_lifecycle.py`
- `tests/test_stage_state_lifetime_contract.py`
- `tests/test_operator_semantics_local_closure.py`
- `tests/test_project_closure.py`
- `resnet50_pipeline/stage_state_lifetime_contract.py`
- `resnet50_pipeline/operator_semantics_local_closure.py`
- `resnet50_pipeline/project_closure.py`
- `contracts/operator_config/minimal_two_stage_lifecycle_v1.json`
- `contracts/operator_config/stage_state_lifetime_contract_v1.json`
- `contracts/operator_config/operator_semantics_local_closure_v1.json`
- `contracts/resnet50_project_closure.json`
- `.agents/plan.md`

主要产物：

- `artifacts/operator_config_validation/r5-minimal-two-stage-lifecycle-e2-v1/`
- artifact manifest SHA-256：
  `e6466bcfc6e88ef9f6085f756493b38a0389b6a6dc8750e4d34b78b33a61de04`
- local E2 report SHA-256：
  `d95522d5e3767eeefc1ce1681789384c92930c58dd34451081aa6633c3f1c378`
- machine contract canonical SHA：
  `9d09aa0b397bdaecc022eb2ddd1d2d65aca7efe6d58001a39f95fc1ea4fc7bff`

## 6. 验证

已通过的定向回归包括：

- 真实双隔离 native lifecycle 正向闭环；
- D/A 地址篡改 fail-closed；
- producer-backed consumer preload fail-closed；
- `Repeat_Num`、runner completion count、final barrier 篡改 fail-closed；
- stage1 stale config reuse fail-closed；
- 既有单 stage hardware frontend 兼容回归。

本轮共运行 41 项定向 unittest，全部通过；另单独执行
`validate_stage_state_lifetime_contract` 通过，并成功重建
`stage_state_lifetime_contract_v1.json`、
`operator_semantics_local_closure_v1.json` 与
`resnet50_project_closure.json`。`git diff --check` 和相关 Python 编译检查通过。

全局状态只新增“一个通用双 stage E2 probe 已闭合”；133 个真实 stage 仍保持
0 个正式 target config、0 个 E4、0 个 E5。下一项规则维护工作是 Requant 精确数值
路径，并把本探针证明的不变量绑定到真实 producer/consumer edge，而不是直接推广。
