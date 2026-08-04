# ADR-013：9 份 legacy 算子配置的规范化裁决

日期：2026-07-23

状态：accepted；P0 身份冻结和 P1 裁决已执行，R3 已在 ADR-015 退出。原始 JSON 保持只读；6 份配置的规范化动作已获语义/原生字段编码层批准，3 份 padding 配置仍缺算子合同，其中 4 份配置的完整 bitstream 对照被原生 mapper 阻断。R3 退出不自动授权改写源配置或 `ndp-sim`。

## 1. 执行边界

- 活动 `ndp-sim` 固定为 `ec12424516ae0304228dd2321d4e604fe225e04e`，只读使用。
- 规范化只发生在内存和临时目录；55 份活动 `ndp-sim/jsons/*.json` 均未改写。
- 原生 encoder 在临时复制的 `bitstream` 工具树中执行，避免其 `mapping_cache` 回写源仓。
- 固定 `seed=42`、`heuristic_iterations=10000`、`heuristic_restarts=10`、`PYTHONHASHSEED=0`。
- 比较四个核心产物：`mapping_review.json`、`parsed_bitstream.txt`、`modules_dump_64b.bin`、`modules_dump_128b.bin`。
- 字段级探针直接执行原生 `ReadStreamEngineConfig`/`WriteStreamEngineConfig` 的 `FIELD_MAP` 和 `_encode_field`；它只证明被改字段的编码，不冒充完整 mapping/bitstream 证明。

P0 报告为 `artifacts/operator_config_validation/p0-baseline-20260723.json`，SHA-256 为 `161d5ac9578c9bc63d374fee4c277bedce80dea2efd5fdb82cb89681d5a31990`。P1 报告为 `artifacts/operator_config_validation/p1-legacy-adjudication-20260723.json`，SHA-256 为 `ffce86a17edef91b04a1e0a1fc1c70d7be5c290bc9a9d874207101d15e038a9c`。

## 2. 结果

| 类别 | 文件 | 原生字段等价 | 完整核心产物等价 | 裁决 |
|---|---|---:|---:|---|
| `None→0` padding | `avgpool_config_2048_7_7.json` | 是 | 是 | 仍阻塞：缺少“padding byte 必须为 0”的算子合同 |
| `None→0` padding | `maxpool_config_16_112_112_stride2_padding1.json` | 是 | 是；使用已哈希的本地零代价 cache 复核 | 仍阻塞：缺少“padding byte 必须为 0”的算子合同 |
| `None→0` padding | `maxpool_config_16_16_16_stride2_padding1.json` | 是 | 未证明，mapper 阻断 | 仍阻塞：缺算子合同，且需补 mapping 证据 |
| 删除 write 端 read-only 字段 | `node0004_accumulate_wave0.json` | 是 | 是 | 规范化动作获批；源改写仍等 R3 |
| 删除 write 端 read-only 字段 | `node0004_accumulate_wave0_nopp_r1.json` | 是 | 是 | 规范化动作获批；源改写仍等 R3 |
| 删除 write 端 read-only 字段 | `prefill_add_V_fp16MN_fp32N_fp16MN.json` | 是 | 是 | 规范化动作获批；源改写仍等 R3 |
| `mem_idx_mode: 0→null` | `prefill_gemm_local.json` | 是 | 未证明，mapper 阻断 | typed-null 规范化获批；完整 bitstream 待补 |
| `mem_idx_mode: 0→null` | `prefill_gemm_local_qkt.json` | 是 | 未证明，mapper 阻断 | typed-null 规范化获批；完整 bitstream 待补 |
| `mem_idx_mode: 0→null` | `prefill_gemm_ring_4slice.json` | 是 | 未证明，mapper 阻断 | typed-null 规范化获批；完整 bitstream 待补 |

汇总：9/9 规范化副本通过严格 JSON 校验，9/9 被改字段由原生编码器证明等价，5/9 获得零 penalty 且四个核心产物逐字节一致，4/9 的完整 bitstream 对照被 mapping 阶段阻断；6/9 的规范化动作获批，3/9 仍缺 padding 算子合同；9/9 原始 legacy 文件身份均为 `intentional-reject`。

## 3. mapper 阻断不是配置不等价

`maxpool 16×16` 的原始与规范化副本都在 10000 次搜索上限停在同一类约束，最佳 penalty 为 1；三个 prefill GEMM 的双方都停在最佳 penalty 6。它们没有生成完整核心产物，因此不能把空产物或共同失败解释成“bit-equivalent”，也不能写成“bitstream differs”。

现有 6 份本地 cache 的树 SHA-256 为 `1331cf292309a19f44939d2048c94b51ee888536daff1db60217ada71c3bd3a6`，不是可移植输入。只读复制后仅命中 `maxpool 112×112`；该 cache 可作为本机重放证据，不能替代提交到仓库的 mapping/provenance 闭包。

原生 direct mapping 也不能作为回退：`bitstream/config/mapper.py:161` 在 DRAM LC 名称未匹配正则时仍执行 `return row * 10 + col`，导致四个待补案例双方均抛出 `UnboundLocalError`。本轮不修改 `ndp-sim`，只把它登记为后续 mapper 可达性/原生工具修复项。

## 4. 决策

1. 原始 9 份 JSON 继续保留为可重放 legacy 输入，但在严格/development 身份中统一为 `intentional-reject`。
2. write 端多余字段是 encoder 忽略的 schema 漂移；未来修生成器时删除，不把未知字段白名单化。
3. 整数 `0` 与 typed null 在当前原生 `mem_idx_mode` mapper 中都编码为 0；未来开发配置只允许 typed null。完整 bitstream 证明缺口单独归因于 mapper，不撤销字段规范化裁决。
4. `padding_reg_value=None` 虽由原生 encoder 静默编码为 0，但严格规则继续拒绝；只有绑定 operator dtype/qparam/layout 且证明 0 是正确 padding byte 后，才能物化为显式 0。
5. R4 只更新活动规则；源 JSON、生成器和 `ndp-sim` 继续保持不变，任何实现修复按 R5 来源策略另行授权。

## 5. 后续顺序

encoded-bit、mapping、execplan、CONFIG、remap 地址和 SCA/qparam/layout/provenance 已由 ADR-014/ADR-015 完成。遗留下一步仅是为 4 个 mapping-blocked 配置补可移植零代价 mapping，或在 R5 来源策略获批后修复原生 mapper；在此之前不得升级它们的证据身份。
