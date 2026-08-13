# GAP node0071 v33 return 主线分发收据

日期：2026-08-04

## 分发身份

- mainline / return target thread：
  `019fbec2-fe93-7e03-9314-cff6f222f33d`
- GAP owner thread：
  `019fa366-cb1f-7ae2-880c-f527be0680cd`
- owner 必须在 return 分析完成及 successor 包完成后主动通知主线。

## 正式 return

- path：
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n71_gap_v33_buffer_ag_idx_pair_diag_return.zip`
- bytes：`134495`
- SHA256：
  `94e1abd19246b773cb3d3dd19c9bcfafa398da35fa09c310c27b8a4fca661daa`
- adjacent sidecar：absent；只按用户担保规则替代外部传输收据，所有内部完整性、身份、
  manifest exact-set、allowlist、逐文件收据及运行结果门均不得放宽。

## 冻结 source

- path：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v33_buffer_ag_idx_pair_diag.zip`
- bytes：`1824172`
- SHA256：
  `5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03`

## current RTL 身份

- Trassic master：
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- `NDP_copy01/rtl` 与 `Trassic2.0_RTL/code/NDP_rtl`：
  `2260/2260` files byte-equal
- tree digest：
  `70334ce5f9addcfa409d566e7f7215b9870f815a7afc813d55f020a3af3ae647`
- 用户已确认真实服务器根也更新到该版本；该确认不能替代正式 return 中的 actual compiled
  production identity、natural terminal、formal D、E3/E4/E5。

## 分发时规则收据

- `.agents/agent.md`：
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md`（分发前，mutable）：
  `dd3a2d4490119f23c0e306f3164453eff678baa274022987440fe80292dea921`
- 生成前必读索引：
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- 服务器测试包生成规则：
  `14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1`
- NDP 硬件字段语义：
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- GAP probe：
  `db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1`
- GAP int32 mac：
  `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b`

## 执行边界

- 原 GAP owner 独占 raw return、数值与本族连续 successor 裁决；主线不重复分析。
- 不重复 numeric/sum/tail/workload/config/golden。
- 若根因唯一，生成 fresh correction；若仍不唯一，生成覆盖全部合理候选的单包
  candidate×observation 高信息增益 successor，并审计 causal keep/drop。
- 默认保留低开销 qualified 卡点证据；不延长 timeout，不改 backpressure、DUT 或 functional RTL。
- fresh 包遵守内层路径缩短与 current path-budget 规则。
- 不修改 plan/public rules/RTL/其他 family；不上传、不运行服务器、不取 lease。
