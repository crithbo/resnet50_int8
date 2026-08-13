# CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001 发布记录

日期：2026-08-05  
Owner：主线 `019fbec2-fe93-7e03-9314-cff6f222f33d`  
状态：`RULE_PUBLISHED_AND_PLAN_INTEGRATED`

## 1. 触发反例

QLinearMatMul/node0075 联合包 v5 已通过 package/install/observer preflight 和 production
VCS compile，并启动 simulator；第一条 execplan SCA preload 地址 `0x01706400` 随即被
硬件地址译码为 bank2、row `0x1c19`。该地址低于约定的 aggregate 24MiB，却落入禁用
bank/非法 row，导致518/518 execplan readback为X，CONFIG和stage00均未到达。

精确 return 分析：

- `artifacts/operator_config_validation/r5-node0071-node0075-e1fb0f7-native-v5-return-analysis/report.json`
- bytes=`6648`
- SHA256=`0edc97ff77ed76e65e2b87c6a277b81cc3c599bf1d17747a3c65dd2a5e035ff9`

这证明“总地址未越界、逻辑区间不重叠、SCA可解析”不足以保证服务器可执行。

## 2. 公共规则增量

已在 `.agents/rules/算子配置规则.md` 正式发布：

`CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001`

current rule：

- bytes=`27090`
- SHA256=`30d0b20979e639d6bd9d0ec81f5e920da19733f0b2e3fe7ba751ef7e44b972d1`

规则要求所有 changed final address interval：

1. 按云端权威 RTL/参数/encoder 真实公式解码 bank/row/column/byte-lane；
2. 覆盖 first/final、每个 bank 切换、row 边界和跨界相邻行；
3. 检查 bank enable、row hole、alignment、width wrap、overlap/alias；
4. 证明 SCA、ExecutionPlan、runtime guard、readback/return target 等 direct consumers
   使用同一最终地址；
5. 用 aggregate-in-range-but-invalid-bank-row、跨边界 off-by-one 和 stale consumer
   三类负控 fail closed。

该门只做 metadata/address decode 和少量边界枚举，不运行完整 DUT 仿真，不重算
numeric/W3/golden；byte-identical 地址区间可以复用 current receipt。

服务器包公共规则的 `release_gate_matrix.materialized_config` 已同步消费该门：

- `.agents/rules/服务器测试包生成规则.md`
- bytes=`78081`
- SHA256=`36f6596c913120c24725da95e269200ecff4b25130d4eefe8d99d21c7b2e7457`

## 3. v9 正控

fresh `r5_n71_n75_0cc_bankrow_v9` 将 D、32个CONFIG和ExecutionPlan整体迁移到低
bank-row 区间，最终177个物理区间 `invalid=0`，所有 direct consumers一致：

- ZIP bytes=`3780255`
- ZIP SHA256=`f0034876998f636ea0cdd473f830daed896cc7b315fdb73ab617e59d6f3c8165`
- final audit bytes=`518133`
- final audit SHA256=`2cb1bf2749a7040969a89ae9185394934ca38c403d5b03f41dff6a5b00e7a46e`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `blocking_failures=[]`

本收据只证明本地物理地址可达性与服务器包发布资格；actual compile、stage entry、
natural terminal、8192次actual A reads/hash、144D和E4/E5仍必须由正式return裁决。

## 4. 计划同步

`.agents/plan.md` 已更新到五个当前可运行身份：

- GAP v40
- serialized Conv v47
- native four-lane p7
- QLinearAdd v35
- node0075 bank-row v9

plan bytes=`13835`，SHA256=`03a0d2cd66ea9174320224e21a865f063cd1fb371d7cdb56632861df0d4215d3`。

未修改 functional RTL；未上传或运行服务器；未取 lease。
