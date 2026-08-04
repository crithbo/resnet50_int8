# Dequant atomic v2 预计 XMRE 回传确认

日期：2026-07-26

## 结论

旧包 `dq_node0077_atomic1_stock_v2` 的服务器回传与上机前静态预测完全一致：

```text
compile/sim/run = 2/125/2
VCS XMRE count = 5
unresolved instance token = slice_group_gen
simulation_started = false
```

五处错误位于最终拼接 observer 的 1991、1996、2003、2010、2015 行，均为
过程块中的运行期变量 `sid` 被用于：

```text
...slice_group_gen[sid]...u_WR_Memory_AG
```

对应信号为 `mem_ag_ob_chl_wr_hs`、`mem_ag_ob_bp_pre_barrier`、
`transfer_addr_nooff` 和 `mse_stream_base_addr`。这与先前对最终 v2 ZIP observer
静态命中的五处完全相同。

权威分类：

```text
SERVER_TEST_INFRASTRUCTURE_OBSERVER_XMR_ELABORATION_FAILURE
expected_failure_match=true
counts_as_dynamic_attempt=false
counts_as_node0077_e4/e5=false
```

包内通用 `FIRST_DYNAMIC_FAILURE` 标签不采用。0 Start、0 Finish、0 accepted write、
0 formal D 只表示仿真没有启动，不能评价 Dequant v6 的 JSON、4-row D buffer supply、
GA 数值、MSE4 或 completion。

## 身份与回传

- return ZIP：39,815 bytes，SHA256
  `4bd611692f77bee60f8f9919d01f8ff92ffc2197960199eac7ef0352e00f0535`；
- 用户未提供外部 sidecar；
- 24 entries、解压 457,147 bytes，无不安全/重复路径；
- 内部 receipt 的 23 个 payload 与 actual exact-set、size、SHA 全匹配；
- 源包 SHA256
  `6d3f9c52f602131a5f3b4950d8d477b13f03509900e15dc82ad40f9aa80fac71`
  与本地冻结包一致；
- RTL tree 与 11 个 focused RTL 全阶段稳定；
- observer 安装后在 compile finalizer 中恢复为 preimage，未修改 `rtl/**`。

## 后继

既有 `CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001` 已完整覆盖本次问题，不新增
重复规则。旧 v2 package 冻结且禁止重跑；Dequant v6/atomic v2 的本地 JSON、golden、
4-write drain 合同保持有效。后继只需由测试修复任务以全新身份生成
elaboration-constant、只读 observer 的服务器包。

机器裁决：
`server_returns/dq_node0077_atomic1_stock_v2_return_analysis_20260726.json`。
