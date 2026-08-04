# Requant guard-only SFU-readiness 回传验收

日期：2026-07-27

## 裁决

本轮是有效的动态诊断失败，不计 node0001 E4/E5。guard stage 在 slice0+1 上自然完成，
但 16 条 MSE4 write-data 与两份正式 D 仍全部为零。

包内 `PE_REGISTER_MATCH` 路由已被推翻。RTL 在
`ga_pe_sfu_preprocess_pipeline0_enable` 下执行
`sfu_preprocess_pipeline0_valid_bit <= ib_output_valid_bit`；本回传已经观测到 64 次
寄存后的 preprocess0 valid，因此 capture edge 上游 valid 必然曾为真。只在 posedge
记录变化的 `PE_POST_REGISTER` 零日志是 observer 采样盲点，不是功能首分歧。

权威分类为：

```text
SFU_PREPROCESS0_VALID_PROVEN__NUMERIC_PIPELINE_UNOBSERVED__MSE4_ZERO
```

最后可信边界是 `SFU_PREPROCESS0_VALID`；未观测区间是 preprocess 实际 payload 经
BST/coeff、SFU ALU/postprocess 到 normal outbuffer；下游坏边界是 MSE4/formal D 全零。

## 身份与证据

- return ZIP：65,566 bytes，
  SHA256 `a9c9206fc3f04c77172242cd8356ffb9a3a367f9b5922fda540d528438832ab9`
- source package：65,468 bytes，
  SHA256 `8cb224163271e0ed9166831bf434c88ce10e1f76ed78a42344724f8b5126c2ac`
- RETURN_RECEIPT：32/32 payload exact，allowlist pass
- compile/sim/run：`0/0/0`
- opcode `0x18` 32 次，SFU valid 32 次，compute enable 16 次
- LUT init enable 198 次、end-address 2 次、group compute-valid 2 次
- preprocess0 enable 144 次、寄存 valid 64 次
- `SFU_PREPROCESS0.data=0x3` 只是 enable/valid 状态拼接，不是数值 payload
- MSE4 write-data 16/16 全零；formal D 两片各 8 行全零且未 preload

## 规则和 validator 更新

- `CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001`
- `CDA-REQUANT-SFU-READY-V1-DYNAMIC-EVIDENCE-001`
- `tools/requant_atomic_server_runtime.py`：下游 preprocess0 valid 优先支配上游
  change-only 零日志；新增 `SFU_NUMERIC_PIPELINE_UNOBSERVED` 路由
- `tests/test_build_requant_guard_only_onecmd_server_test.py`：增加 witness dominance
  与 preprocess0 未断言的分流测试
- 公共服务器规则 SHA256：
  `0fec7a4f72246c9e802fb2e91e972c2f636e2721aaeef1194c2d4d3fba103fbc`
- Requant 专项规则 SHA256：
  `5f7bc1fc7087d3aafce0b74982588df9c68abeea583a7ea501c87031c3ef9e52`
- 机器报告：
  `server_returns/rq_node0001_guardonly_sfu_ready_stock_v1_return_analysis_20260727.json`
  SHA256
  `47f91b2cb25b2e81e1385b35fe0cc6739709717c69a22f3b383bfbbf81be584a`

## 下一轮唯一 Requant 诊断

保持 guard JSON、mapping、bitstream、execplan、输入、RequantGuard、golden 全部冻结，
只增加 capture-edge-safe 的实际 payload checkpoint：

`ga_pe_sfu_inport2pre_data → preprocess/BST/coeff → SFU ALU/result/tag →
postprocess → normal outbuffer/outport → MSE4`。

并行的第二包使用可信原生 `decode_silu_fp16N_fp32N.json`，作为相同 stock RTL
SFU/normal-outbuffer 和 observer 的 control。该 control 不计 Requant E4/E5。
round-only、alias/lifetime 和完整 E4 继续禁用。

没有修改 `rtl/`。
