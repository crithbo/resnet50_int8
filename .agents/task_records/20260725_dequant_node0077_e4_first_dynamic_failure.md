# DequantizeLinear node0077 stock-RTL E4 首次动态失败

日期：2026-07-25

## 裁决

正式回传已独立验收，结论为：

```text
classification = FIRST_DYNAMIC_FAILURE
dynamic_baseline = NO_DYNAMIC_BASELINE
evidence_level = SERVER_INCOMPLETE
candidate_release = false
E4 = failed_or_incomplete
E5_generation_allowed = false
remaining_blocker = B_DEQUANT_SERVER_E4_E5
```

本次是同门下的首次动态失败，不存在已通过相同动态门的 known-good baseline，因此
不得称为 regression。没有正式 D，亦不得称为 numeric mismatch。

## 回传身份

- 原始 ZIP：`dequant_node0077_stockrtl_e4_onecmd_v1_return.zip`
- bytes：`52318`
- SHA256：`df245117f93b3859b7a5b4bf8cb1c547d2fc90a5f03e3ae82f4ddb0d27d86620`
- sidecar：用户未提供
- ZIP：46 entries，解压后 505567 bytes
- 不安全路径、重复 entry、禁止 payload：均为 0
- RETURN_RECEIPT：45/45 payload 的 size/SHA 与 ZIP 一致
- package manifest SHA256：
  `f8194ea2bab6318d036e1e452faab11037997e4858c47edf409be1f5ed914430`
- 分析记录：
  `server_returns/dequant_node0077_stockrtl_e4_return_analysis_20260725.json`
- 分析记录 SHA256：
  `f861a8cec186f14ddc05dca1844d832e65ada5aee90e89f807223a4268fcdf23`

缺 sidecar 使 ZIP 对 sidecar 的运输身份检查无法完成，但 ZIP 内部 receipt、
package identity 与结果收据彼此一致，且超时/无 completion/无正式 D 已足以
fail closed。

## 已证明与未证明

已证明：

- compile exit=0；
- SCA/SCA_D echo、30 次 preload、global start 正确；
- 28/28 slice 均经历
  `Start Cfg → Cfg Finish → Start Comp`；
- RTL tree、focused RTL 和 support files 四阶段稳定；
- `functional_rtl_unchanged=true`。

最早直接分歧：

```text
compute_started_not_completed
last_proven_boundary = slice Start Comp
```

28 片均未出现 `Comp Finish`；GNU 4 小时 timeout 后 sim/run exit=124。正式
JSON_D dump 为 0，28 份 formal D 全部缺失，因此未执行 golden 数值比较。

当前回传没有目标 MSE/GA handshake observer 或 local request/read/write 证据，
不能进一步区分：

- A read 请求或返回；
- GA add/mul；
- normal outbuffer acceptance；
- MSE4 write request/data；
- completion tag propagation。

## 规则与总账影响

现有 `CDA-DEQUANT-E4-E5-001` 已要求无 timeout、28 片自然完成、正式 D 回读和
golden，因此本次无需改变算子数值/layout 规则；它是既有 fail-closed 门的真实命中。

机器总账新增并绑定：

- `server_e4_attempt_count=1`
- `server_e4_first_dynamic_failure_count=1`
- `server_e4_incomplete_count=1`
- `formal_e4_pass_count=0`
- `formal_e5_pass_count=0`

未生成新包，未修改任何 `rtl/` 文件。
