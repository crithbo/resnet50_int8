# 2026-08-05 server package local release-gate applicability and trace rule

## 结论

当前服务器包规则的语义覆盖已经很广，但发布执行仍高度分散。仓库现有89个匹配
`build/validate/revalidate ... server_package/final_audit/hdl_scope` 的版本化脚本；多个算子
每轮复制并扩展独立validator。结果是负控数量持续增加，仍会遗漏最终运行面的真实错误。

本轮裁决：

- `RULE_DELTA_ACCEPTED_AND_PUBLISHED`
- 新规则：
  - `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001`
  - `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
  - `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- 修改文件：`.agents/rules/服务器测试包生成规则.md`
- 生成前必读索引已经路由该公共服务器规则，不新增同义索引项。

## 已观察的重复失败类型

1. package-local HDL/scope：QAdd v19、Conv v23、GAP v36在真实服务器compile前后暴露
   undeclared或拼写错误；
2. runner/finalizer/manifest：unbound variable、required-missing漏项、identity/namespace
   与path manifest字段漏失；
3. observer语义：跨stage scope、错误clock domain、level-as-progress、snapshot parent gate、
   simultaneous push+pop误判final；
4. materialized config：Conv transout threshold、QAdd 16B producer对32B Buffer row。

这些错误大多不是规则完全没有写，而是package-specific validator没有从final ZIP真实
consumer/控制流/物化配置推导验收范围，或负控只验证了mock/expected inventory。

## 新发布门

### 最小阻断集

后续fresh包必须发布`release_gate_matrix`，只让以下会影响服务器执行或结果可信性的门阻断：

- package identity/bootstrap/path/runtime-D；
- fresh-extract真实runner→compile stub→finalizer；
- actual package-local HDL；
- changed materialized config的consumer contract；
- changed observer/canonical的诊断语义；
- return/result联合门。

冻结且byte-equal的numeric/W3/golden、无关RTL域、历史同义负控和报告样式不重复；无因果影响
项只作`record_only`告警。负控按失败机制/等价类合并，同时保留最近同类escape回归。

### 诊断判据trace

changed/required predicate必须用final exact逻辑运行本地事件序列，覆盖：

- 正例与每个conjunct单独为假；
- 边界前/中/后；
- push+pop等同时事件；
- stable level与重复sample；
- stage/reset/clock ownership变化；
- 最近同类escape raw trace。

该门不运行真实DUT、不做服务器环境自检，只防止本地可确定的observer/parser/canonical错误
浪费服务器轮次。

### XMR公开表面优先

p5证明“actual consumer已枚举”和“focused scope通过”仍可能不足：focused wrapper把外部
DUT层级当stub时，可能只验证路径/token形状，没有证明production层级允许读取private leaf。
后续changed observer若有同义公开port/interface，必须优先使用；确需private XMR时，必须
绑定actual目标module bytes/filelist/实例路径，且focused wrapper不得补造目标leaf。该门
不要求服务器侧新增源码身份预检。

## 适用边界

- 本规则发布前已冻结且current的包，不因新增矩阵格式本身重建或hold；下一fresh successor
  开始执行。
- 已因其它current规则hold的包继续满足原解锁条件。
- full-design production elaboration、服务器源码树和真实动态行为仍由服务器自然裁决。
- 配置数值/地址/transaction问题继续由`CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`和专项规则
  负责；新规则只确保该门被列入changed-surface阻断集，不重复定义算子公式。

## 发布收据

- previous server rule SHA256：
  `5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9`
- published server rule SHA256：
  `68fafe7c33e8ac037d94308a0902cdb52afec32f1325d6cee9bc14f70ca9d69d`
- inventory：89个匹配
  `build/validate/revalidate ... server_package/final_audit/hdl_scope`的版本化脚本；
  该数量只用于证明执行分散，不要求一次性重写历史脚本。
- migration：发布前已冻结且current的ZIP不因新矩阵格式本身被hold；下一fresh identity开始
  必须执行`release_gate_matrix`和适用的predicate trace门。
