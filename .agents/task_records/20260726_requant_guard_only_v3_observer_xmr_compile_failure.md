# Requant guard-only stock v3 observer XMRE 编译失败裁决

日期：2026-07-26

## 结论

`rq_node0001_guardonly_stock_v3_return.zip` 是完整 finalizer 回传，但没有进入仿真。
package/installed preflight、observer 安装身份和 include 目录门均通过，VCS 在最终拼接
observer 的五处 cross-module reference 上报 `Error-[XMRE]`：

```text
u_NDP_Top_new...slice_group_gen[sid]...u_WR_Memory_AG
```

这些引用位于过程块 `for (int sid = 0; sid < 2; sid++)` 中；`sid` 是运行期变量，不能作为
generated instance path 的 elaboration 下标。`compile/sim/run=2/125/2`，
`Start/Finish/checkpoint/MSE4/formal D=0/0/0/0/0`。

独立裁决：

```text
status=SERVER_TEST_INFRASTRUCTURE_COMPILE_FAILURE
failure_class=SERVER_TEST_INFRASTRUCTURE_OBSERVER_XMR_ELABORATION_FAILURE
counts_as_dynamic_attempt=false
counts_as_node0001_e4=false
counts_as_node0001_e5=false
```

包内通用 finalizer 的 `FIRST_DYNAMIC_FAILURE` 标签被覆盖。零条 checkpoint 只表示仿真
未启动，不能裁决 guard 的 A read、Buffer、GA、SFU、MSE4、CONFIG、RTL 或数值。
此前组合合同给出的
`GUARD_WRITE_PAYLOAD_ZERO_AFTER_NONZERO_INPUT_PRELOAD`
仍是待定位首分歧；下一项仍只能是 guard-only，不能启用 round-only 或 alias/lifetime。

## 回传与身份

- return ZIP：37,699 bytes，SHA256
  `63bf060f982b1aca3e95de1685df9cf56f47e53af03f91c67c67756bd5f459d5`；
- 用户未提供外部 sidecar；
- ZIP 26 entries、解压 376,432 bytes，无不安全路径、重复路径；
- 内部 `RETURN_RECEIPT` 的 25 个 payload 与实际文件 exact-set、size、SHA256 全一致；
- 冻结源包身份匹配：
  `rq_node0001_guardonly_stock_v3.zip`，57,407 bytes，SHA256
  `bc5ee98d2fae9ced6b581fa8483b48a1fd5459d164c583059ecb4720c44e7133`；
- RTL tree 与 11 个 focused RTL 在全部阶段稳定；
- observer 安装前 SHA256
  `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`，
  安装态为
  `b2c5b42116e992c0521a0688c6c01ac282eac7e5e1f3922fa8ef5a26a383989f`，
  编译后及最终恢复到 preimage，未修改 `rtl/**`。

## 根因与规则增量

本地自检证明了 tail 文件存在、SHA 正确、真实 install/verify/restore 和 package tree
不变，但没有验证最终拼接 observer 的 elaboration 合法性。新增：

- `CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001`：generated instance path
  只能用字面量或包围引用的 `genvar`；禁止过程变量下标；
- `CDA-REQUANT-GUARD-DIAGNOSTIC-EVIDENCE-BOUNDARY-001`：仿真前基础设施失败不推进
  guard 数据通路语义，也不启用其他原子项。

同样的五处运行期 `slice_group_gen[sid]` 已静态命中尚未运行的
`dq_node0077_atomic1_stock_v2.zip`。为避免浪费服务器时间，该包应在上机前撤回，以全新
身份重建；Dequant v6/atomic v2 的 JSON、golden 和语义合同本身不因此失效。

## 本地验证与交接

- analysis JSON 可解析；
- `tests.test_mandatory_read_compaction`：8/8 通过；
- Requant v3 与 Dequant v2 两个最终 ZIP 内的 observer 均精确命中 5 处运行期
  generate-instance XMR；
- 公共规则 SHA 更新后，旧 Dequant v2 builder 的 source-identity 门按预期 fail closed，
  必须由测试修复任务刷新读取收据并以全新身份重建；
- 已把 Requant guard-only 与 Dequant atomic 的双包重建要求发送到测试修复任务；本任务
  未生成、上传或运行新包。

机器裁决：
`server_returns/rq_node0001_guardonly_stock_v3_return_analysis_20260726.json`。
