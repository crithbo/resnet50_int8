# Package release admission 与 TB-VCD runtime v2 主线激活

日期：2026-08-14  
激活名：`package-release-admission-and-tbvcd-runtime-v2`

## 输入

主线消费了 GAP v62/v63 与 QAdd v63/v64 的 `PACKAGE_BUILD_FAILURE_RULE_AUDIT`，以及
`optimizer.whole-network` 的共享审计：

- `outputs/gap_qadd_package_build_failure_shared_rule_audit_v1/report.json`
- `contracts/server_package_release_admission_dispatch_v1.json`
- `contracts/server_tb_vcd_qadd_v63_rule_audit_dispatch_v2.json`

## 裁决

GAP 的 embedded manifest 中间状态逃逸属于现有规则实现缺口，不新增同义规则。现有 final-ZIP、runner
preflight 与 compilefail-core 规则新增共同实现入口 `package_release_admission_runtime_preflight`：

1. manifest 晋升 `PACKAGE_READY_NOT_RUN` 后在 final staging 运行 package-specific preflight；
2. 对 clean extraction 的 exact final ZIP 重跑相同 preflight；
3. 把 extracted manifest 改回 `PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES` 必须以
   `package claim boundary differs` 拒绝；
4. positive assertions 与 observed-negative facts 使用分离的 typed polarity；
5. compile-not-started preflight failure 保留 stdout、stderr 与 nonzero exit。

QAdd v63 的共享裁决在既有
`CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001` 下作非同义收窄，不新增 public rule ID：

- freeze 只消费 same-attempt append VCD timestamps；display integer 非权威；
- heartbeat 为 unsigned width>=64，固定每 16384 owner cycles 输出；
- `$dumpvars` target union 必须与 exact source-bound catalog 相等，module/aggregate over-dump 禁止；
- inline/multiline timescale 均可 streaming/resume；
- target claim 要求 live entry/downstream/first-error；
- partial、unflushed、unreaped、非 exact-set/no-hard-limit evidence 不得 finalization pass。

observer-only 默认路径保持不变。

## 同步与验证

optimizer 报告列出的 27 个共享资产/报告/记录均机械同步并逐项 SHA 复核通过。主线窄幅合并公共规则、
生成索引、optimizer 专项规则、硬件仿真 README 与 build-gate registry；未覆盖并行增量。

- focused shared regression：41/41 PASS；
- broader related regression：127/127 PASS；
- runner/layout/first-fresh/retention 补充回归：44 PASS、1 environment skip；
- `py_compile`、JSON parse、`git diff --check` PASS；
- active-rule audit：14/14 active/registered，164 unique definitions，duplicate=0，errors=0，warnings=0。

## 激活边界

本激活只对后续 next-fresh 生效。GAP v63 与 QAdd v64 的 scoped controls 已由共享审计确认充分，均不
HOLD、不重建、不改字节；serialized v93d 与 native p48 同样不受追溯影响。没有 package storage rotation、
upload、lease、connect、server run、functional RTL、config、numeric 或 workload 动作，也不声称
production execution、natural terminal、formal-D、E3、E4 或 E5。
