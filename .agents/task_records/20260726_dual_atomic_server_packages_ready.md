# Requant / Dequant 双原子服务器包交付

日期：2026-07-26

状态：`PACKAGE_READY_NOT_RUN`。本记录只证明本地生成与 package 自检；两包均未上传、
未运行，不计正式 E4/E5，`candidate_release=false`。

## 包 A：Requant node0001 atomic2 bootstrap 修正版

```text
install_name=rq_node0001_atomic2_stock_v2
zip=artifacts/operator_config_validation/r5-server-test-packages/
  rq_node0001_atomic2_stock_v2.zip
size=75859
sha256=69a264f4ffca02120f662f1b5749f1a66819f7294bb8af497aa617336cb4e93c
sidecar=rq_node0001_atomic2_stock_v2.zip.sha256
return=rq_node0001_atomic2_stock_v2_return.zip
return_sidecar=rq_node0001_atomic2_stock_v2_return.zip.sha256
```

唯一服务器入口（从解压后的包目录执行）：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

修复范围只包括 bootstrap/runtime：

- shell 在任何 Python 前导出 `PYTHONDONTWRITEBYTECODE=1`；
- Python runtime 在导入包内 common 模块前设置
  `sys.dont_write_bytecode=True`；
- `__pycache__`、`.pyc`、`.pyo` 仍被严格拒绝，不进入 allowlist。

冻结语义对照：

```text
v1 frozen semantic files=39
semantic tree sha256=0043fa6c8163618487fe4b74f378c555430f3933a2a65736d6d9df3d489efdde
operator JSON/mapping/parsed bitstream/64b+128b bitstream/
execplan/golden/expected writes=byte-identical
SCA/SCA_D=仅 install namespace 归一化后相同
```

fresh-extract bootstrap：

```text
files before/after=48/48
bytes before/after=394113/394113
tree sha256 before/after=
  eb2505bd30bb8cdc937215f89802bf4769dc11961cae4906c134583fda574bca
exact path/size/SHA unchanged=true
```

旧 `rq_node0001_atomic2_stock_v1` 禁止重跑；其 preflight 失败仍不计 dynamic
attempt，附加 guard-only/round-only/alias-lifetime 保持关闭。

## 包 B：Dequant node0077 atomic single-stage

```text
install_name=dq_node0077_atomic1_stock_v1
zip=artifacts/operator_config_validation/r5-server-test-packages/
  dq_node0077_atomic1_stock_v1.zip
size=56413
sha256=35a330f7446103da8a93cf0f3d03e1f9517d5d38739c84fbc51a6de924546ccb
sidecar=dq_node0077_atomic1_stock_v1.zip.sha256
return=dq_node0077_atomic1_stock_v1_return.zip
return_sidecar=dq_node0077_atomic1_stock_v1_return.zip.sha256
```

唯一服务器入口（从解压后的包目录执行）：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

冻结输入严格绑定：

```text
config sha256=1e331488ff95d10f5c9b50abde13193b495d24f0230f51b6e4f38f836a9ee290
manifest sha256=fe9103a3a672f9270f0f82c128550d046d9d0511adfc489fd22cfa45722c4318
generation receipt sha256=
  d8f97f5f81b2f3939ab20de86b31dc04b515ead171675ec2913aa3e98bcff04f
semantic contract sha256=
  6cba3fd2c04dd9feb3447c185d4432a1aaba28f15276595c57406b67c64cf74d
local report sha256=
  cf59f82a0b962662e4cdc1983b254e3d79c74e9d02f689090c382c1e7f394cff
```

原子合同：

```text
logical occurrence=1
physical slices=[0,1]
stage=1
Repeat_Num=1
A preload=2 data + execplan/config = 4 SCA entries
formal D=2 entries x 4 lines = 8 lines
accepted MSE4 writes=8
```

planner transport adapter 只补 native typed consumer 所需的 instance、
constant binding 和 raw config identity；冻结 config、typed graph、input、golden、
write/lifecycle 合同不变。完整 package 在两个全新目录独立构建两次并得到逐字节相同 ZIP；
每次 package 构建内的 planner/mapper/encoder/execplan 又双跑一致。

fresh-extract bootstrap：

```text
files before/after=33/33
bytes before/after=255498/255498
tree sha256 before/after=
  abbb82dfcde83c4eed5b47e2242dafc1b1e2751ef8499c3dae4c69b598e3ab88
exact path/size/SHA unchanged=true
```

该包只裁决最小 CWH16 Dequant 原子路径，不计完整 node0077 E4/E5，也不解除
`B_DEQUANT_SERVER_E4_E5`。

## 共同门与验证

- 规则：`CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001`、
  `CDA-SERVER-WORKLOAD-PROVENANCE-001`、
  `CDA-SERVER-ONE-COMMAND-001`、
  `CDA-SERVER-RETURN-RECEIPT-001`；
- 专项：`CDA-REQUANT-ATOMIC-SINGLE-OCCURRENCE-001`、
  `CDA-REQUANT-ATOMIC-STOCK-TB-MASK-COMPAT-001`、
  `CDA-DEQUANT-ATOMIC-STOCK-TB-001`；
- 两包 ZIP 均为 `rtl/ entries=0`，不修改 `tb_NDP_Top_new_phy.sv` 或
  `rtl/**`；只读 observer 只事务式追加到既有根目录 hook
  `native_return_observer.svh`，编译后立即恢复；
- 禁止 force/deposit、禁止缩短内部 TB timeout、VCD/FSDB 全关；
- 回传 allowlist-only，直接生成各自独立 ZIP+sidecar。

联合定向验证：

```text
Requant materialization/package + Dequant materialization/package/full-package
29/29 PASS

final exact package/bootstrap subset
19/19 PASS
```

本地身份稳定：

```text
NDP_copy01/rtl file_count=2265
rtl tree sha256=
  957f7ac25c17e8ad146e2c3d8e389066d001538495744067277ac92cdd079e3f
tb_NDP_Top_new_phy.sv sha256=
  e068f7500f0c71c2ba2c756f74a4519c33d13d4afe0fa4cc9f6c9e79b1e3f994
Makefile.tb_NDP_Top_new_phy sha256=
  528d93f3c7f458d256bdbaf1d9ec39edfbfe5bd8a924e2bf0786914a634f4aba
```

推荐流水：先运行 Requant 修正版；回传两个文件后立即运行 Dequant。回传分析与
第二包运行可以并行，但两个 workload 不合并 ZIP、不共享 install/run/return 身份。
