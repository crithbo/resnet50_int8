# Trassic2.0_RTL GitHub master 本地同步与接口裁决

日期：2026-07-29

## 同步结果

通过已登录的 GitHub 会话读取私有仓库
[`xlsjdjdk/Trassic2.0_RTL`](https://github.com/xlsjdjdk/Trassic2.0_RTL)，当前
`master` HEAD 为：

```text
5f2f8d3a2358c090143caa35957c07ff3650ff4c
修改代码冲突
```

GitHub `master` archive 已下载并同步到独立目录：

```text
Trassic2.0_RTL/
```

archive SHA-256：

```text
bdf0ce9f83ba8e0b3e1354bd559f61a4eb3e2a4c6187934c78c880d28e7c3faa
```

命令行 Git 没有登录，直接 clone 卡在凭据阶段；该空克隆已停止并保留为
`Trassic2.0_RTL_failed_clone_20260729_1546/`，没有被当成同步成功。同步目录来自
GitHub authenticated master archive，不含 `.git` metadata，因此后续更新仍需重新取得
远端 HEAD 与 archive。

archive 有 14 组 Windows 大小写冲突/重复路径，全部位于
`AXI_IF/run_axi_write64_merge_bridge_tb/csrc/*.DB`；RTL source 路径无重复。
同步目录包含 2,008 个 Verilog/SystemVerilog/filelist source。

## 与历史本地快照的差异

比较：

```text
NDP_copy01/rtl
Trassic2.0_RTL/code/NDP_rtl
```

结果：

- 历史本地 source：2,010；
- GitHub master source：2,008；
- 差异 source：13；
- 双方同路径但内容变化：11；
- 仅历史本地存在：2；
- 仅 GitHub 存在：0。

11 个变化文件：

1. `Global/global_config_manager.sv`
2. `NDP_Top.sv`
3. `NDP_Top_phy.sv`
4. `Slice/General_Array/GA_Inport/GA_Inport.sv`
5. `Slice/General_Array/GA_PE_Group/GA_PE/GA_PE.sv`
6. `Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv`
7. `Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE.sv`
8. `Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Postprocess.sv`
9. `Slice/Slice_Execution_Manager.sv`
10. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v`
11. `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v`

仅历史本地存在：

- `clk_freq_new.sv`
- `NDP_Top_phy_with_fifo.sv`

最近 GitHub 提交已包含用户所述的硬件修复方向：

- `5cd09eff8d229060471312759be92147f388ae4e`：
  `修改SA_PE计算int8时的计算错误`；
- `c81807554b5e39c040aeae39ffe30aa522f5f6ab`：
  `修改GA Inport中int32转fp32时最小值识别问题`；
- `5f2f8d3a2358c090143caa35957c07ff3650ff4c`：
  `修改代码冲突`。

## `slice_rst` 首分歧

GitHub master 的 `SA_ALU.v` SHA-256 仍为：

```text
42142fb407df4eeb9855b9ed730a1c08eb16d3ab30392ecc3d1e3f9d2abb7f2e
```

它在 `SA_ALU.v:124-127` 实例化 `SA_PE_Mul_Array` 并连接
`.slice_rst(slice_rst)`。

GitHub master 的 `SA_PE_Mul_Array.v` SHA-256 已变为：

```text
081eafbbe625104866ec711bec1683b8eb0a28f9a4f8992514429a0c787d27ee
```

相对历史本地版本，它：

1. 删除 module port `input slice_rst`；
2. 删除 pipeline 的 `else if (slice_rst)` reset branch；
3. 把 INT8 `last_B` 从二次左移的 `{carry_int[30:0],1'b0}` 修正为
   `carry_int[31:0]`。

第 3 项修复了历史重复 carry shift，但前两项与未同步修改的 `SA_ALU` caller 形成确定
compile-interface mismatch。Conv node0004 v3 与 GAP node0071 v2 的服务器 return
恰好都报告相同的 undefined port，故服务器当前行为与 GitHub master 更接近，而不是
由本地主线历史 RTL 导致。

## 主线裁决

- GitHub master 已同步到本地独立目录，可作为最新只读 RTL 参考；
- 不覆盖 `NDP_copy01/rtl`，因为当前 master 已确定无法通过该接口的 elaboration；
- 不生成 Conv v4 或 GAP v3，不修改功能 RTL；
- 硬件 owner 必须先在同一 commit 中统一 `SA_ALU` 与 `SA_PE_Mul_Array` 的
  `slice_rst` 接口，再发布新 commit；
- 新 commit 发布后重新同步该独立目录、核验接口和关键 SHA，再原身份重跑
  node0004 v3 与 GAP v2。

机器记录：
`contracts/rtl_sync/trassic2_github_master_5f2f8d3_sync.json`。
