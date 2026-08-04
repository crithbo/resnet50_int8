# Requant node0001 原子两阶段 v2 服务器诊断包

日期：2026-07-26

## 裁决

已只消费 `single-occurrence-two-stage` v2，生成全新 stock-RTL
FIRST_DYNAMIC 诊断包。冻结的 slice0-only v1 未被封包或运行；本轮不计
node0001 正式 E4/E5，`candidate_release=false`，
`B_REQUANT_SERVER_E4_E5` 未解除。

包身份：

```text
artifacts/operator_config_validation/r5-server-test-packages/
  rq_node0001_atomic2_stock_v1.zip
size=74100
sha256=4f732020c598ac9e00eec5dddf4a06f84e5f0caf54fb75243d6df7e38922f54b

  rq_node0001_atomic2_stock_v1.zip.sha256
```

唯一服务器命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

```text
rq_node0001_atomic2_stock_v1_return.zip
rq_node0001_atomic2_stock_v1_return.zip.sha256
```

## 重建与动态合同

- 两份 v2 address-bound JSON 分别作为 guard/round 的唯一配置输入。
- 每次封包均从空 mapping cache 的隔离 planner/mapper/encoder 开始。
- 两次完整封包各自又做两次原生重建；确定性文件和最终 ZIP
  均逐字节一致。
- planner 适配只受控更改两个 operator ID 及对应 producer ID；配置 JSON、
  shape、地址、mask、tensor ID 不变。
- 原生 ordinary plan 为 10 个 64-bit command；每个 Start_Comp 后插入同
  mask completion barrier 后为 12 个 command / 6 条 128-bit execplan。
- `Repeat_Num=2`；active slices=[0,1]；mask=`...0011`。
- SCA preload=6：execplan、两个 guard 输入、guard config、RequantGuard、
  round config；round external A preload=0。
- SCA_D=4：两个 guard（各 8 beat）和两个 final（各 2 beat）。
- same-clock read-only observer 预期 accepted MSE4 write：
  guard 16、round 4、合计 20。

## 安全与发布边界

- ZIP 48 entries；`rtl/` entries=0；波形/嵌套压缩包 entries=0。
- 不修改或携带 `tb_NDP_Top_new_phy.sv`、`rtl/**`。
- 不使用 force/deposit/release 或驱动式 observer；不修改 TB 内部
  `RUN_TIME`。
- observer 只事务式安装到根目录 `native_return_observer.svh`，编译后立即
  恢复；保存 pre/install/precompile/post-compile/post-run/post-restore
  身份，恢复失败即 fail-closed。
- 回传为 allowlist-only；允许携带本轮很小的两份 observer log、四份正式
  readback 和两个 lifecycle log，不携带 build tree 或波形。
- 组合失败时按 v2 `first_divergence_routing.json` 最多启用一个对应原子项；
  组合通过时三个附加原子项保持关闭。

## 文件与验证

```text
tools/build_requant_atomic_onecmd_server_test.py
sha256=0c07ffc9ba0456faffccbd70a9ea8f41b9b4db3a8b77263cc279e19d8587d237

tools/requant_atomic_server_runtime.py
sha256=4ed6fcb3d359a8fb7685588e6de465b3bbf3db89d9f4b73f75ea93009494a8c9

tests/test_build_requant_atomic_onecmd_server_test.py
sha256=80da16750efb6eddd14a30dfc5d4731627499e128f1f96a0e7e0b7f9dde84876

.agents/task_records/20260726_requant_atomic_v2_package_read_receipt.json
sha256=89095054b09f74037a64e61beb7baf56d9bd8ac6718d6fb28cf90833c2f8c1d3
```

验证结果：

- 新包 preflight：PASS。
- 模拟安装 exact tree/path preflight：PASS，8 files。
- ZIP/sidecar exact-set、顺序、payload、SHA：PASS。
- 两次完整封包 ZIP byte-identical：PASS。
- Requant 原子包 + v2 语义 + vertical/config-bound/family 定向回归：
  26/26 PASS。

状态：`PACKAGE_READY_NOT_RUN`。
