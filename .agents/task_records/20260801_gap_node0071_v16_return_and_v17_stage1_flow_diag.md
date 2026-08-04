# GAP node0071 v16 return 与 v17 stage1-flow 定位包

日期：2026-08-01

## 裁决

v16 不是“计算量大但仍在缓慢推进”。在有效配置启动后，它产生了真实的两路
Buffer 输入、GA 输入/输出以及 MSE4 写事务，但随后连续
40,632,320 个 active cycles 没有任何 qualified handshake 增长。

v16 的 stage1 byte-slot 修复已经生效；本轮不能重新归因到旧的
8B byte-lane 配置错误。

现有 return 与本地 RTL/配置方程只能把首错收窄到：

```text
MSE0 Buffer-AG queue
  -> Buffer0 byte-valid / clear / ARM
  -> GA stored operand0 tag
```

在这个区间内，当前证据不能唯一选择一个配置叶，也不能证明一个功能 RTL
叶错误。按“先本地穷尽、仍缺唯一必要边界才生成测试包”的规则，未猜改配置，
只生成 v17 后端只读定位包。

## v16 动态证据

- return ZIP SHA256：
  `dec639e4adf98282951dfc1a7913ea6942140e6c372ad29be19ffdae094bdbef`
- source v16 ZIP SHA256：
  `85ee11406a8f7b67d67d7fd3e82705c3c48c12b01e2a155496cbf7b05679cee5`
- compile=0，simulation=125，runner=125，signal=INT。
- natural terminal=false；formal D=0/48；mismatch=0 不可评价。
- sim wall=5184.038102402s；total wall=5242.443063849s。
- canonical：
  `LONG_RUNNING_HANG_AT_MSE4_WRITE_DATA_ACCEPTED`。
- qualified final:
  - MSE0→Buffer0 accept=10；
  - MSE3→Buffer4 accept=10；
  - GA input/output=32/32；
  - MSE4 request ch0/ch1=9/9；
  - MSE4 write-data ch0/ch1=8/8。
- 最后 GA input/output 分别在 702807000/702809000ps；
  最后 MSE4 write-data 在 702827000ps。

## 本地穷尽复核

已对照最终配置语义与下列活动 RTL：

- `Buffer_AG_Idx_Queue.sv`
- `WR_Buffer_AG.sv`
- `Array_Request_Manager.sv`
- `Buffer.sv`
- `GA_PE_Inbuffer.sv`

确认：

- stage1 COL 序列为 0/1/2/3，8B 数据覆盖四个 byte slot；
- Buffer-AG ROW keep 阈值与 COL terminal 不冲突；
- WR_Buffer_AG full 阈值与当前 ROW terminal 一致；
- Buffer0/4/5 mode 与 lifetime 对本 stage1 的本地语义一致；
- GA 可以保存先到的一侧 operand，另一侧晚到不构成确定错误。

因此没有合法依据猜改 mode、lifetime、address、keep 或 GA 配置。

## v17 定位范围

v17 新增两类限流记录：

- `STAGE1_FLOW_COUNTS_V1`
- `STAGE1_FLOW_STATE_V1`

它们只读返回：

- MSE0/MSE3 Buffer-AG queue enqueue/dequeue/full/empty；
- WR_Buffer_AG output-buffer write/read/count；
- Buffer0/4 全 byte-valid 状态与 clear；
- ARM request/ready/rw/address/counter；
- GA 已保存 operand0/operand2 tag。

这些状态不进入 canonical monotonic-progress 判定，不驱动 DUT，不改变
timeout、config、mapping、bitstream、execplan、SCA、golden 或功能 RTL。

## Package release

```text
identity  r5_n71_gap_v17_stage1_flow_diag
class     DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
status    PACKAGE_READY_NOT_RUN
bytes     1800157
SHA256    d4ff6ba01f96626de2977bbf3ba5216644255b948b872b800c6976ddf3d227d6
```

最终 ZIP 自检：

```text
FINAL_ZIP_RULE_SELF_AUDIT_PASS=true
errors=0
safe compile stub reached=true, exit=86
wrong identity compile reached=false, exit=5
all required negative controls fail closed=true
```

额外语法筛查：

- 用实际 `tb_NDP_Top_new_phy.sv`、package-local include path 与
  `NATIVE_RETURN_OBSERVER_ENABLE` 预处理，exit=0，v17 marker=1；
- 将预处理后的 observer 单独置入语法 shell，Icarus 报
  `syntax error` 数量=0；
- 非零 elaboration 只来自没有 DUT 层级的 shell 中预期的 XMR 无法绑定和
  Icarus 功能边界；不能替代服务器 VCS 动态 compile/elaboration 门。

运行：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

```text
r5_n71_gap_v17_stage1_flow_diag_return.zip
```

用户已担保传输不调换，return sidecar 可不上传；内部
RETURN_MANIFEST/allowlist/exact-set/source binding/动态联合门仍必须验证。

## 声明边界

`numeric_analysis_repeated=false`；
`sum_tail_workload_reexecuted=false`；
`config_rebuilt=false`；
`functional_rtl_modified=false`；
`server_action=false`。
