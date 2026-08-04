# Requant guard-only v4 回传分析与规则更新

日期：2026-07-26

## 结论

`rq_node0001_guardonly_stock_v4` 已通过服务器基础设施、自然完成和身份门，但 guard
功能失败。输入数据完整到达 `GA_RAW`；两份正式 D 共 16 行全部为零且与 golden 不同。
`GA_CONVERT` 与后续 SFU checkpoint 是未观测，不是已观测为零，因此当前只能把首分歧
收窄为：

```text
GA_RAW
  → GA inport conversion / runtime config consumption
  → odd-PE SFU select / valid
  → SFU LUT / ALU
  → normal outbuffer
```

权威分类为 `GA_CONVERT_UNOBSERVED_AFTER_GA_RAW`。根因仍在
`CONFIG_CONSUMPTION | RTL_CONTROL | OBSERVER_EVIDENCE` 之间未裁决。

## 回传身份与动态事实

- return ZIP：55,405 bytes；
  SHA256 `248eeed826d62fb343289b370fa20dbf6bc2d90f3d4aeba315160d5d30628077`；
- 33 entries，解压 577,416 bytes；无危险路径、重复、禁止项；
- `RETURN_RECEIPT` 的 32 个 payload 与 ZIP actual exact-set/size/SHA 全一致；
- compile/sim/run=`0/0/0`，一个 guard stage 在 slice0+1 上自然 start/finish；
- same-mask fence、单次 RequantGuard load、五阶段身份和 observer 恢复均通过；
- MSE0_RDATA=`16/16` 非零，MSE0→Buffer=`16/16` 非零；
- GA_RAW=`64/64`，62 条非零，2 条为输入中预期的零；
- guard JSON 的 inport0 `int32tofp32=true`，最终 parsed bitstream 的 GA inport0
  也声明 conversion enabled；这只证明静态意图，不证明运行期 RTL 已消费并传播该位；
- GA_CONVERT/SFU_INPUT/SFU_ALU/SFU_OUTPUT=`raw=parsed=0`；
- MSE4 observer 仅采到 `8/16`，8 条 payload 均为零，同时存在解耦握手错误；
- 正式 D 两文件各 8 行，16 行全部为零；输出地址未被 SCA preload。

包内 `GUARD_OBSERVER_COVERAGE_OR_PARSE_DIVERGENCE` 路由作废，因为所有 checkpoint
均满足 `raw == parsed`。更新后的 parser 可解析 8 条 MSE4 marker，首分歧函数返回
`GA_CONVERT_UNOBSERVED_AFTER_GA_RAW / UNOBSERVED_NOT_ZERO`。

## 规则与 validator 更新

新增规则：

- `CDA-REQUANT-GUARD-CHECKPOINT-ROUTING-001`
- `CDA-REQUANT-GUARD-V4-DYNAMIC-EVIDENCE-001`

修改文件：

- `.agents/rules/RequantizeUint8算子配置规则.md`
  SHA256 `d1bd49486cc257fe4ab05b25c80ec42228c71090848207ef271f11053b9c0772`
- `tools/requant_atomic_server_runtime.py`
  SHA256 `1db3da51dd6cc9d8fd8bd8c673a3730d670c48bf11f624bd0b5596a13d691d10`
- `tests/test_build_requant_guard_only_onecmd_server_test.py`
  SHA256 `cf76b8184827911f3a6b5ce23ad167b64b1877b9997896d7c24bec964fc1df16`
- `.agents/plan.md`
  SHA256 `52510f22511ca52fd0f0131d67c88497aee6b97c69816d934e4a62e4382bcdeb`
- `server_returns/rq_node0001_guardonly_stock_v4_return_analysis_20260726.json`
  SHA256 `79ef9534c481ca1b436c2f815b6860feb91584cd3f0f77982b6fa1660a4f8da6`

公共服务器规则未重复改写；继续引用已存在的
`CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001`。当前文件 SHA256：
`67018547fbe4e485d3d8c2420821e0c8f65bfec0bab0ecc1099ad9de37e55eb7`。

## 验证

- 机器报告通过 `python -m json.tool`；
- runtime/test 通过 `py_compile`；
- 定向单测
  `test_missing_checkpoint_is_not_mislabeled_as_parse_divergence`：1/1 PASS；
- 使用 v4 原始 observer 日志重放：
  `raw_mse4_marker_count=8`、`parsed_mse4_write_count=8`；
  路由为 `GA_CONVERT_UNOBSERVED_AFTER_GA_RAW`。

## 后继约束

只允许一个冻结语义、全新身份的 guard-only 直接信号定位包。不得启用 round-only、
alias/lifetime 或完整 E4，不得修改 TB/`rtl/**`。新 observer 必须独立采集 MSE4
request/write-data，并把 GA inport 运行期配置、converter 输入/寄存输出、奇数 PE
选路、SFU LUT/ALU、normal outbuffer 划成可判定边界；focused identity 同步覆盖这些
实际消费者。

当前保持：

```text
candidate_release=false
NO_DYNAMIC_BASELINE
B_REQUANT_GUARD_DYNAMIC_DATA_PATH
B_REQUANT_SERVER_E4_E5
```
