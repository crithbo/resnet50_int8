# DequantizeLinear node-0077 单算子垂直闭环

日期：2026-07-24

## 最终裁决（v5）

- 状态：`LOCAL_E2_COMPLETE_BACKEND_AND_GLOBAL_LEDGER_BOUND`
- `candidate_release=false`
- `server_package_generated=false`
- `formal E4=0 / E5=0`
- 唯一剩余门：`B_DEQUANT_SERVER_E4_E5`

v5 是本轮最终本地证据身份。v4 已完成数值、layout、mapping、bitstream、
execplan 与 SCA/SCA_D，但 generation receipt 把整个可变 lowering bundle 文件
SHA 当作 typed request 身份；overlay 写回 lowering 后会造成自循环漂移。v5 将稳定
身份改为不可变的 `request_id + request_sha256 + request_set_sha256`，并从当前
lowering、最终 JSON 和两份空 cache 隔离工具副本完整重建全部下游产物。

最终资产：

- strict JSON：
  `configs/native_ndp_sim/resnet50_dequant_node0077_uint8_fp32_strict_v5/config.json`
  ，SHA-256
  `812c6d861bf41ce89233e16b2bdd1d9d8328aed9e07941070872d6409668bba1`
- generation receipt：
  `contracts/operator_config/node0077_dequant_generation_receipt_v5.json`
  ，文件 SHA-256
  `392194adf3bcd9d585745a0d9a0dfa18e7c3dac6b85ab81fea1bcc0198c879f7`
- semantic contract：
  `contracts/operator_config/node0077_dequant_semantics_evidence_v5.json`
  ，文件 SHA-256
  `c3cb412d61ce1c61af717d000dad1911fba7a37f0ab8917f9a717d65dc3da78a`
- local E2 report：
  `artifacts/operator_config_validation/r5-dequant-node0077-e2-v5/local_e2_report.json`
  ，文件 SHA-256
  `3d059a3e73192b85e37130f474bcfd93e23db9353e728dc9c4158479440487e8`
- stage candidate：
  `configs/stage_codegen/hwop-0077-00-dequant-v1/manifest.json`
  ，文件 SHA-256
  `ee12ab9b5c85467fe9d141fc66cf6371f31de48fdb5a634d2d904f8800a1c120`

最终 E2 仍保持：

- 26 行 128-bit config bitstream：
  `8918be634ce76c574a406060d570e0d0555b2a59e8e05182f00ffb6d1bdc89bd`
- 57 条 64-bit / 29 行 128-bit execplan：
  `5caf5840264c8b93a28fb72f8fb3666a936b5df54b509928e919484ba608ddcd`
- 28 片 SCA_D，每片 188 个 128-bit word
- 物化回环：A=16 bytes/occurrence，D=64 bytes/occurrence，
  47 occurrences/slice，752 elements/slice
- 8 个最终物理 GA 槽均已反解为四个 `add/-60.0f` 与四个
  `mul/scale`，placement penalty=0，fallback=false
- `NDP_copy01/rtl` 前后均为 2265 文件，tree SHA-256
  `58c66eb00d597fd5c51bb2e4c539b877265b88f91c07d72ee8f175c07e1b10ee`

全局机器合同已接入：

- lowering：4 个本地 resolved stage，1 个 candidate config，1 个 zero-copy
- derivation matrix：5 个代表 stage、4 个 JSON projection、1784 个 leaf，
  Dequant 为唯一当前 candidate projection
- project closure：`local_candidate_execplan_chain_count=1`
- formal target config、E4、E5 仍全部为 0

本轮相关回归共 47 项通过：前 43 项覆盖 Dequant、overlay、lowering、
backend、stage system、derivation、lifetime 与 local closure；最后 4 项
`tests.test_project_closure` 在 224.418 秒内通过。

此外修正了通用 patchset validator 的身份边界：patchset manifest 从声明的
`base_commit` Git blob 验证基线，不再被活动 `ndp-sim` 工作树中的无关 mapper
实验阻断；实际 patch application 仍对隔离副本执行源 SHA fail-closed。

## 范围与边界

- 精确对象：`r5:hwop-0077-00 / node-0077`
- 逻辑签名：`DequantizeLinear(uint8[16,1000], fp32[1], uint8[1]) -> fp32[16,1000]`
- 本轮只完成本地 E2 和 stage backend 接入。
- `candidate_release=false`；服务器 E3/E4/E5 未执行。
- 未生成服务器包，未修改或携带任何 `rtl/` 文件。

## 已闭合语义

1. 数值顺序固定为
   `(float32(uint8(x))-60.0f)*float32(0x3e01622d)`。
   真实 W3 16000 个输出逐 bit 相等。
2. 单 affine-MAC 改写在 W3 上有 12976/16000 个逐 bit 反例，禁止使用。
3. GA 固定为四个普通 `add` PE 后接四个普通 `mul` PE：
   `PE00/02/20/22 -> PE10/12/30/32`，不用 transout。
4. HIGH4 物理布局为 28 片，每片 750 个有效元素加 2 个 neutral tail；
   A 为 752 bytes，D 为 3008 bytes。
5. 最终 materialized/address-bound JSON 反解为每片 47 个 occurrence：
   A 每次 16 bytes、D 每次 64 bytes，共覆盖 752 个 fp32 输出元素。
6. typed request 只消费 `x_scale` 和 `x_zero_point`；历史 `affine_offset`
   保留为反例但不进入硬件配置。

## v1/v2/v3 证据演进

- v1 只证明 mapper 输入常量，未证明最终物理 PE 码流槽位；不再作为 E2 放行证据。
- v2 首次使用两份隔离工具链，暴露相同 seed 下 Python hash/set 迭代顺序导致
  `mapping_review` 与 bitstream 不确定；fail closed，未放行。
- v3 增加 `PYTHONHASHSEED=0`、空独立 mapping cache、固定 seed 77。
  两份工具副本的 address-bound JSON、mapping、parsed/64b/128b bitstream、
  execplan、explanation、SCA/SCA_D 和 cfg_pkg 逐文件哈希一致。

## v3 关键身份

- 读取专项规则 SHA-256：
  `ba75b679199aa140a9765b8f44ae335b492f667509f50a0c01f9dfc6cdd3f8e2`
- strict JSON：
  `configs/native_ndp_sim/resnet50_dequant_node0077_uint8_fp32_strict_v3/config.json`
- generation receipt：
  `contracts/operator_config/node0077_dequant_generation_receipt_v3.json`
- semantic contract：
  `contracts/operator_config/node0077_dequant_semantics_evidence_v3.json`
- local E2 report：
  `artifacts/operator_config_validation/r5-dequant-node0077-e2-v3/local_e2_report.json`
- E2 report SHA-256：
  `95188a7396f83492ec098157ee21f952193b4abdc6bfd114cedc846b6cc9adb0`
- address-bound 128-bit config bitstream：26 行，
  SHA-256 `8918be634ce76c574a406060d570e0d0555b2a59e8e05182f00ffb6d1bdc89bd`
- execplan：57 条 64-bit 命令 / 29 行 128-bit，
  SHA-256 `5caf5840264c8b93a28fb72f8fb3666a936b5df54b509928e919484ba608ddcd`
- SCA_D：28 片，每片 188 个 128-bit word。
- `NDP_copy01/rtl`：2265 文件，前后 tree SHA-256
  `58c66eb00d597fd5c51bb2e4c539b877265b88f91c07d72ee8f175c07e1b10ee`。

## 物理码流证明

`detailed_dump.txt` 的八个 144-bit GAPE block 与
`parsed_bitstream.txt` 中 16 个物理 PE 槽逐 bit 对照；仅以下槽有效：

- `PE00/PE02/PE20/PE22`：opcode `add`，constant1 `0xc2700000`
- `PE10/PE12/PE30/PE32`：opcode `mul`，constant1 `0x3e01622d`

随后独立重建 parsed stream 的 CONFIG mask、presence bit、module chunk 和
64/128-bit half reorder，与两个 raw dump 逐 bit 相等。

## 规则/validator 增量

- `CDA-DEQUANT-MAPPING-BINDING-001`：现在包含最终物理槽码流反解，不再把物理
  常量验证推迟到 E4。
- `CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`：逐 occurrence 验证 transaction、
  bank/column、buffer lifetime、地址区间和 SCA_D 覆盖。
- `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`：两份隔离工具副本完整重建并逐文件一致。
- 新增可靠性反例：原生 mapper 的 seed 不足以保证跨进程确定性，必须同时固定
  `PYTHONHASHSEED`。

## 修改文件

- `.agents/rules/DequantizeLinear算子配置规则.md`
- `resnet50_pipeline/dequantize_linear_vertical.py`
- `tests/test_dequantize_linear_vertical.py`
- `resnet50_pipeline/r5_resolution_overlay.py`
- `resnet50_pipeline/stage_config_backend.py`
- `resnet50_pipeline/stage_config_system.py`
- `resnet50_pipeline/ndp_patch_toolchain.py`
- `resnet50_pipeline/stage_json_derivation_matrix.py`
- `resnet50_pipeline/operator_semantics_local_closure.py`
- `resnet50_pipeline/project_closure.py`
- 对应 `tests/` 回归与派生机器合同
- `.agents/plan.md`（仅更新短活动计划的完成状态）

公共 `.agents/agent.md`、`算子配置规则.md` 和
`服务器测试包生成规则.md` 未由本任务改写。

## 当前唯一动态门

`B_DEQUANT_SERVER_E4_E5`：

- 28 片自然完成；
- 每片正式回读 752 个 fp32；
- 前 750 个值逐 bit 对 W3；
- 末 2 个值为 `0x00000000`；
- 无越界、hang、timeout；
- 全新身份 E5 重跑一致。

本地 E2 不解除该门，也不构成服务器动态 known-good baseline；当前分类为
`NO_DYNAMIC_BASELINE`。
