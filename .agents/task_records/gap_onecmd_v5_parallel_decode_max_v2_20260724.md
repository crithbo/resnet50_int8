# GAP onecmd v5 与并行 Decode FP32 max v2（2026-07-24）

## 结论

本轮只使用 stock functional RTL，没有修改 `NDP_copy01/rtl`，包内也不含
RTL/TB 源文件。

- `gap_int32_mac_stock_rtl_onecmd_v4` 已被本地 TB loader 合同否决：
  16 个 `SCA_D` 条目均缺少 `length`，实际会得到 0 个正式回读矩阵。
- 全新 GAP v5 已生成并通过本地 E2、exact ZIP、两次确定性构建和专项测试。
- 为并行利用服务器等待时间，另生成 DeepSeek Decode FP32 reduction-max v2。
  它已有同算子 E3 历史证据，本包显式补齐 `SCA_CFG_D`，目标是取得 28 片正式
  DDR readback；它不能替代 ResNet INT8 MaxPool。
- 更接近 ResNet 的 `add_dequant` 暂不发包：当前 shape handler 会把授权模板的
  `stream2.dim_stride[2]` 从 1024 派生为 256，尚未由 planner 修正或证明为动态无效。

## 开始前完整阅读

- `.agents/rules/服务器测试包生成规则.md`
- `.agents/rules/算子配置规则.md`
- `.agents/rules/GAP_int32_mac_bypass_rules.md`
- `.agents/rules/GAP_probe_v7_validator_rules.md`
- `.agents/rules/GAP_repair_candidate_rules.md`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
- `.agents/plan.md` 第 0.3 节
- `ndp-sim-ref/model_execplan/readme.md`（仅因交接要求阅读；没有导入、执行或复制）
- `ndp-sim/generate_python_golden/README.md`
- `ndp-sim/generate_python_golden/README_gen_data.md`
- `ndp-sim/model_execplan/README.md`
- `ndp-sim/model_execplan/README_op_json.md`
- `ndp-sim/README_SERVER_PACKAGE_LOCAL.md`

## 使用的规则

- `CDA-GAP-INT32MAC-NONTRANSOUT-001`
- `CDA-GAP-INT32MAC-DUAL-INPUT-001`
- `CDA-GAP-INT32MAC-NORMAL-FIFO-001`
- `CDA-GAP-INT32MAC-TREE-001`
- `CDA-GAP-INT32MAC-STAGE-MEMORY-001`
- `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`
- `CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001`
- `CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001`
- `CDA-GAP-REPAIR-RETURN-RECEIPTS-001`
- `CDA-GAP-D-READBACK-COVERAGE-001`
- `CDA-GA-OUTBUFFER-OCCUPANCY-001`
- `CDA-GA-INVALID-SLOT-ISOLATION-001`
- `CDA-GA-CROSS-BLOCK-INIT-001`
- `CDA-MSE4-MONITOR-EVIDENCE-001`
- `CDA-SERVER-FOCUSED-IDENTITY-001`
- `CDA-SCA-D-TB-READBACK-LENGTH-001`

## GAP v5

### 四类关键修正

1. 每个 `SCA_D` 条目精确为 `base_addr/path/length=512`；单位是 128-bit word。
2. compile/simulation 分别使用 2h/12h wall-clock timeout；`EXIT/HUP/INT/TERM`
   finalizer 尽力生成部分回传。
3. 动态门核对 SCA/SCA_D 精确回显、39 个 preload、16 个 dump、自然完成、
   `Cannot open`/skip/default-softmax 反例。
4. 正式 D 要求每片 512×129 bytes、LF-only、全 128-bit 逐行 golden；
   dual-MSE 要求六级完整绝对地址序列、连续 occurrence、channel/address 一致，
   并拒绝旧的 `sim_results/local` 日志。

### 重建链

```text
configs/gap_int32_mac_bypass_v1/stage-{1..6}/config.json
  -> tools/build_gap_int32_mac_local_e2.py
  -> onecmd-v5-local-e2 (planner/encoder/mapping/bitstream/execplan/SCA provenance)
  -> tools/build_gap_int32_mac_onecmd_server_test.py
  -> primary v5 + independent deterministic v5
```

### 交付身份

```text
ZIP:
artifacts/operator_config_validation/r5-server-test-packages/
  gap_int32_mac_stock_rtl_onecmd_v5.zip

bytes:
1636365

SHA-256:
e8b3ae2c694c3a8a516a99541de26f6059ba9b3ba84bc5d8e532ed9db36185b7

sidecar:
artifacts/operator_config_validation/r5-server-test-packages/
  gap_int32_mac_stock_rtl_onecmd_v5.zip.sha256
```

唯一服务器命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

只需回传：

```text
gap_int32_mac_stock_rtl_onecmd_v5_return.zip
gap_int32_mac_stock_rtl_onecmd_v5_return.zip.sha256
```

### 发布门

`candidate_release=false / E2_LOCAL_ONLY`。

尚未解除：

- 16×512 正式服务器 D readback；
- dual input 的真实 skew/stall/resume（若自然覆盖不足则仍开放）；
- normal FIFO 每个 `clk_sg` 周期的完整 occupancy/invalid-slot 证明；
- 六次 barrier 的真实 drain 与跨 stage 写可见性；
- 独立重复 E5；
- 历史 `B_GAP_GA_ACCUM_STATE`（本包绕开 int32_sum，不清除该 blocker）。

## Decode FP32 max v2

### 选择理由与边界

- 同算子旧候选已在服务器自然完成，28/28 个内部 MSE4 低 32-bit 匹配，
  已有 E3 类别证据；
- 本包是新 placement/新身份，仍从 E2 开始，不能继承旧包的正式发布结论；
- `SCA_D` 为 28 片，每片 `length=1`，并改用全新 readback 路径，避免覆盖 golden；
- 输出 ZIP 只有约 54 KiB，适合作为等待 GAP 返回期间的第二个服务器作业；
- 不触发 `int8_max`，不能用于清除 ResNet INT8 MaxPool blocker。

### 交付身份

```text
ZIP:
artifacts/operator_config_validation/r5-server-test-packages/
  decode_max_fp32_stockrtl_onecmd_v2.zip

bytes:
54144

SHA-256:
97991bbb4a56d7636c24808cec353b2d813468309d836893cc82a698a01cec12

sidecar:
artifacts/operator_config_validation/r5-server-test-packages/
  decode_max_fp32_stockrtl_onecmd_v2.zip.sha256
```

唯一服务器命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

只需回传：

```text
decode_max_fp32_stockrtl_onecmd_v2_return.zip
decode_max_fp32_stockrtl_onecmd_v2_return.zip.sha256
```

### 发布门

`candidate_release=false / E2_LOCAL_ONLY_PRIOR_SAME_OPERATOR_E3`。

若本次 28 片完整 128-bit 正式 readback 与 golden 全一致、loader/完成/RTL identity
全部通过，可把本次精确候选判为 E4；仍需独立重复 E5。无论结果如何，都不改变
ResNet INT8 MaxPool 的正交状态。

## 修改与新增文件

- `tools/build_gap_int32_mac_onecmd_server_test.py`
- `tools/gap_int32_mac_server_runtime.py`
- `tests/test_build_gap_int32_mac_onecmd_server_test.py`
- `tools/build_decode_max_onecmd_server_test.py`
- `tools/decode_max_server_runtime.py`
- `tests/test_build_decode_max_onecmd_server_test.py`
- `.agents/rules/GAP_int32_mac_bypass_rules.md`
- `.agents/rules/服务器测试包生成规则.md`
- `.agents/plan.md`
- `.agents/agent.md`
- 本记录

功能 RTL 修改：0。

## 验证结果

- GAP primary/independent ZIP SHA 完全一致；
- Decode primary/independent ZIP SHA 完全一致；
- 两包 exact ZIP file set、sidecar、manifest/tree receipt 通过；
- 两包均无 RTL/TB、波形、build tree、嵌套压缩包；
- GAP 16 个 `SCA_D.length=512`，Decode 28 个 `SCA_D.length=1`；
- 36 项定向测试通过：

```text
tests.test_build_decode_max_onecmd_server_test
tests.test_build_gap_int32_mac_onecmd_server_test
tests.test_gap_int32_mac_reduction_semantics
tests.test_gap_int32_mac_stage_memory
tests.test_gap_stock_rtl_identity
```

本机没有安装可用 Bash/WSL distribution，因此未执行 `bash -n`；脚本的固定 token、
控制结构和两次确定性生成已由 Python 专项校验。服务器入口仍在执行前做完整
fail-closed preflight。
