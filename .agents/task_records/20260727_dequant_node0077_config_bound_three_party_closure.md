# Dequant node0077/v6 config-bound 三方总账闭环

日期：2026-07-27

## 裁决

`node0077 / DequantizeLinear / v6` 的独立 config-bound simulator 腿已补齐，
裁决为 `THREE_PARTY_CONFIG_BOUND_CLOSURE_PASS`。该节点可将项目正式 ResNet
三方闭环计数从 `0/78` 更新为 `1/78`。

执行器不是两级软件公式摘要。它逐项消费并约束：

- 最终 strict v6 JSON 的 `uint8tofp32`、8 个 GA PE、opcode、constant 和 `src_id` DAG；
- E5 冻结包中的最终 bitstream、mapping、execplan、SCA 与 SCA_D；
- 28 片、每片 752-byte 的 physical A；
- 每片 188 行 128-bit 的 physical D 输出 ABI；
- 冻结 `CDA-DEQUANT-LAYOUT-HIGH4-001` inverse。

上游 `NDPFuncModel` 当前没有通用 Dequant `uint8tofp32 + GA add/mul` 执行入口；
CGRA_SIM 的单级 affine Dequant 顺序已被专项反例否决。因此本记录使用项目专属
PE-graph config interpreter，并将其边界明确限定为功能 config-bound 执行；
RTL timing 只由既有正式 E4/E5 提供。

## 运行入口

```powershell
$env:PYTHONPATH='.'
& 'C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/build_dequant_node0077_config_bound_simulator.py
& 'C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_dequant_node0077_config_bound_simulator -v
```

## 输入身份

- strict v6 config:
  `72c871e3bb4583302961ead62cabefa8b125281be97b5df61b45a190f18998bb`
- E5 frozen package:
  `83cd2db78f99d27f02c2b65a46f9f5c43e94b9ff9a5c50ef0273a0409f1cab68`
- package-local LF bitstream:
  `b67569ff8aa92bbf0f81286e475a047d12ff2ad20d97f73cf4a63eae8822a11f`
  （CRLF source-v6 identity 为
  `c8ff24957d847df9b5f191b257567fec123605e24d1083fd6fdedc5375e674d3`，
  执行器证明唯一差异为换行规范化）
- package-local LF execplan:
  `af79d9a1ed7acc1ede0bf0fe6223e7826cc714489235dcca40b1846d7cff7910`
  （CRLF source-v6 identity 为
  `5caf5840264c8b93a28fb72f8fb3666a936b5df54b509928e919484ba608ddcd`）
- E4 analysis:
  `c7d1380f6dd365b6349e050390a5e112125906eb04a73fcd54a3dec412bfe35f`
- E5 analysis:
  `544761cb91681f1b45a611ef92f05de49e771bb354da3c8a43817a8ca0b7728d`
- E4 return ZIP:
  `79b3ea77d7a1651ee77181cffe7264d86da59f47fffa17277d603d8a727272d4`
- E5 return ZIP:
  `ae993cbf7cc51757a6be24f89e72a3e77ac98cba8953ef1510f93e736a71ca66`

启动必读实际 SHA：

- agent:
  `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0`
- plan:
  `81d57f8143c495b9c2d7e0a33f4eeeb3824ba1b318b03a3b3731552ce045016d`
- 生成前必读索引:
  `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7`
- 公共算子规则:
  `f7e3f80e7fb4edd2b42d7ff41a70bba55abfde6797013648dfedccdc6385e023`
- NDP 硬件字段语义:
  `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59`
- Dequant 专项:
  `76c66fb19268061caaeafca5ba2899017f6f0c95326a6350c5fb12f18e710dd2`
- Dequant 原子合同:
  `cc9e5215d92e55b7440a07954503586c9a6d50f56fe505595341c0ba71358d85`

## 三方比较

所有比较均覆盖逻辑 `float32[16,1000]` 的 16,000 个元素：

- golden ↔ simulator：PASS，0 bit mismatch，max abs error 0；
- golden ↔ E4 hardware：PASS，0 bit mismatch，max abs error 0；
- golden ↔ E5 hardware：PASS，0 bit mismatch，max abs error 0；
- simulator ↔ E4 hardware：PASS，0 bit mismatch，max abs error 0；
- simulator ↔ E5 hardware：PASS，0 bit mismatch，max abs error 0；
- E4 ↔ E5 hardware：PASS，0 bit mismatch，max abs error 0。

专项规则要求逐 bit 相等，因此实际比较采用 `atol=0`、`rtol=0`。三方均无
NaN；比较器仍 fail-closed 要求 NaN payload bits 一致。28 片 simulator
physical D 均为 188 行，每片前 750 个 fp32 有效，末尾两个 word 均为
`0x00000000`。冻结 inverse 后 simulator SHA 为
`d5aa938813ec8ef7fe51cc2288df5f0e1782c19729a184cef248718ce83a311d`。

## 硬件证据分层交接

依据
`.agents/task_records/20260727_test_repair_to_family_threads_handoff.md`
第 1、2 节，本总账同时绑定以下三层硬件证据：

1. atomic v3：
   `ATOMIC_FUNCTIONAL_PASS_OBSERVER_TEMPORAL_EVIDENCE_INCOMPLETE`。两片各四行
   formal D 全部 binary-known 且逐 bit 对 golden，证明最小 CWH16 数值功能路径；
   observer 的解耦 request/wdata 队列及地址域缺口不推翻 formal D，但 temporal
   drain 未闭合，因此不计 E4/E5。
2. full v6 E4：`FIRST_DYNAMIC_PASS`，正式 28×188 physical D、inverse、
   temporal raw count 和 stock-RTL identity 首次通过。
3. 全新身份 full v6 E5：`REPEATED_DYNAMIC_PASS`，独立重复通过相同正式门。

E4/E5 只构成 hardware 腿，不自动构成 simulator 证据；独立 config-bound
simulator 腿仍由本记录的 PE-graph executor 提供。

## 输出身份

- machine report:
  `artifacts/operator_config_validation/r5-dequant-node0077-config-bound-simulator-v1/three_party_report.json`
  SHA256 `f0db3202d250bbba3b40ccd02731ad1a676938bca9e54a2a9de988c5798fde95`
- machine contract:
  `contracts/operator_config/dequant_node0077_config_bound_simulator_v1.json`
  SHA256 `7cb0a7224944db5ee3b7e5b8bb3ccaedf5ee2f2e7f9673982bc2bee181c55c33`
- physical D:
  `artifacts/operator_config_validation/r5-dequant-node0077-config-bound-simulator-v1/physical_d/`
  共 28 个全新 128-bit/LF 文件；逐片 SHA 记录在 machine report。
- validator/test:
  `tests/test_dequant_node0077_config_bound_simulator.py`
  SHA256 `b6ea7e0217c5e36c45e73df1e5946bab39c523115f42b6d7b0a619cc24765107`
- test result：6/6 PASS。

## 回传主线

`BLOCKER_DELTA`：

- close `B_DEQUANT_CONFIG_BOUND_SIMULATOR_LEG`
- open: none

`RULE_DELTA_PROPOSAL`：

- 建议新增可复用三方总账门：config-bound executor 必须同时绑定最终 JSON、
  编码 bitstream 身份、execplan/SCA、physical input/output 和同一批准 inverse，
  才能计入正式三方节点。

未修改 `.agents/plan.md`、`.agents/rules/**`、任何 `rtl/**` 或冻结 v6 资产；
未生成或运行新的 Dequant 服务器包。
