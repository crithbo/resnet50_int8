# QLinearAdd rule/replay receipt refresh

Date: 2026-07-27

Status: `RECEIPTS_CURRENT_NUMERIC_ANALYSIS_NOT_REPEATED`

## RETURN_ANALYSIS

本轮只刷新依赖与 replay/claim 收据，没有重做已经完成的 17-instance 数值分析：

```text
407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc  .agents/rules/算子配置规则.md
3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19  .agents/rules/生成前必读索引.md
981afd5aa0a0ee240c8e6c863cbac0c89dc299344554eb893d707cf96fe0b4ee  .agents/rules/QLinearAdd算子配置规则.md
5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0  .agents/rules/精确UINT8量化尾专项规则.md
a1e19c6e84360641205836f6fa0b172fc0405472b8b2dfdc4c580cc2e0875516  .agents/plan.md (mutable provenance)
```

新增 current-match rule ID：

- `CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`
- `CDA-QADD-STAGE0-THREE-PHYSICAL-STAGES-001`
- `CDA-QADD-BROADCAST-REPLAY-TAIL-ACCOUNTING-001`
- `CDA-QADD-STAGE0-CLAIM-BOUNDARY-001`

生成前索引的 Flatten/View 新路由已读，但不扩大 QLinearAdd ownership。

## Replay boundary

node0076 的 B replay 现在显式记录：

```text
source_producer = hwop-0076-00:B_DEQUANT
source_tensor_identity = hwop-0076-00:B_SCALED
source_delivery = hardware-stage output committed to explicit B_SCALED scratch
allowed_mapping = B_SCALED.base + (logical_output_index % 1000) * sizeof(float32)
host_precomputed_internal_tensor = false
```

该 replay 只改变 add-stage 的读取地址；B-scaled 仍由配置中的正式 B-dequant hardware
stage 计算并写入 scratch。host 不计算 scaled、rounded、saturated、quantized 或 final
tensor，也没有把 singleton diagnostic 当作完整 UINT8 tail。

## Validation

新增 receipt-only validator 路径，使收据更新不重复完整标量数值分析：

```text
python tools/build_qlinearadd_stage0_config_only.py \
  --receipts-only \
  --report artifacts/qlinearadd_stage0_config_only/receipt_refresh_report.json

python tools/validate_qlinearadd_stage0_config_only.py \
  configs/qlinearadd_stage0_config_only/qlinearadd_stage0_config_only_v1.json \
  --contract contracts/operator_config/qlinearadd_stage0_config_only_contract_v1.json \
  --receipts-only
```

结果：

```text
valid=true
numeric_analysis_repeated=false
current_match_dependencies_checked=4
replay_nodes_checked=["node-0076"]
claim=null
```

轻量定向测试：

```text
test_receipt_refresh_and_replay_are_noncomputational: passed
runtime=0.011s
```

## BLOCKER_DELTA

无数值/生产 blocker 关闭。完整 UINT8 tail、最终 Y、native static/address-bound leaf diff、
mapping/bitstream、execplan/SCA 和动态门继续开放。

## PACKAGE_RELEASE

`NOT_GENERATED_NO_LEASE_AND_COMPLETE_QADD_UNCLOSED`。

未修改 plan、rules 或 RTL；未检查服务器文件/身份，未上传、未运行、未生成包。
