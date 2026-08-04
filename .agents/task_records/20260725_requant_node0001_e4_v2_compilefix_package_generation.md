# RequantizeUint8 node0001 E4 v2 编译集成修复包

日期：2026-07-25

## 裁决

`requant_node0001_two_stage_stockrtl_e4_onecmd_v1` 的正式回传不是两分钟完成，
而是在 VCS 编译阶段失败：

- `compile_exit_status=2`，`sim_exit_status=125`，仿真未启动；
- 最早错误为 `tb_NDP_Top_new_phy.sv:5854` 的
  `` `include "native_return_observer.svh" `` 无法解析；
- 0 lifecycle、0 accepted guard write、0 formal D，因此不能裁决配置、RTL 或数值；
- 分类保持 `FIRST_DYNAMIC_FAILURE / NO_DYNAMIC_BASELINE /
  server_test_infrastructure_compile_failure`。

根因是 Requant v1 入口遗漏了已成功用于 Dequant E4 的
`VCS_EXTRA_OPTS="+incdir+${ndp_root}"`。当前 Makefile 从隔离 `RUN_DIR` 启动 VCS，
没有显式 NDP 根目录 include path 时，相对 include 不可见。

## v2 修复边界

新身份：

- package：`requant_node0001_e4_stockrtl_v2`
- install：`requant_node0001_two_stage_stockrtl_e4_onecmd_v2`
- run/evidence/return：均由新 install 身份派生，不能复用 v1。

修复只涉及服务器测试基础设施：

1. 编译调用显式传入 `VCS_EXTRA_OPTS="+incdir+${ndp_root}"`；
2. `install-probe` 后、VCS 前新增 `verify-probe-installed`，逐字节核验 installed
   observer 和 preimage backup，并输出 `tb_probe_precompile_receipt.json`；
3. identity gate 必须同时验收该 precompile receipt；
4. Make driver 输出改存 `compile_driver.log`，VCS 自有 `compile.log` 不再与 shell
   重定向并发写同一文件；两份日志均只回传有界 tail；
5. 编译结束立即事务恢复 observer，原五阶段身份链不变。

未改变 frozen E2 JSON、mapping、bitstream、execplan、SCA/SCA_D 数值语义或地址。
没有修改或打包任何 `rtl/` 文件，functional RTL 仍为 stock。

## 包身份

- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/requant_node0001_e4_stockrtl_v2.zip`
- size：`2076856` bytes
- SHA-256：
  `699d677c1af2832a8fe1773cfc870bb714826d035d724ec20df621006876ee49`
- sidecar：
  `artifacts/operator_config_validation/r5-server-test-packages/requant_node0001_e4_stockrtl_v2.zip.sha256`
- manifest SHA-256：
  `cb4d045025d8fc98c899144fd74a59cb77667ac222c764c7677ff9bdf93b4411`
- payload tree SHA-256：
  `f0728db1aabfd75785f2f75a18f24d6f617fac1c273b5c12e8155ee862c2aade`
- ZIP entries：64
- `rtl/` entries：0
- `candidate_release=false`
- `evidence_level=E2_LOCAL_ONLY`
- blocker：`B_REQUANT_SERVER_E4_E5`

两次独立 fresh build 的 ZIP 大小、SHA 和全部字节一致。exact ZIP/sidecar
validator 通过。

## 本地验证

- package/runner/observer 定向测试：6/6 通过；
- node0001 垂直闭环、native package、包集成的目标回归：11/11 通过；
- 扩展 Requant 集合：22 项中 20 项通过。两项旧 hash-bound 报告失败仅因当前
  `resnet50_r5_lowering_bundle.json` 身份已变化，差异限于 lowering bundle 的
  size/SHA、派生 self-hash 和 family read-receipt semantic hash；公式、通道覆盖、
  node0001 E2 和包内容均未出现差异。本轮不越权重写这两份规则维护资产。
- 本机没有 Bash 可执行文件，未执行 `bash -n`；服务器 VCS 编译仍是 E4 动态门，
  不能由本地检查替代。

## 服务器入口与回传

解压并进入包目录后只执行：

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

预期回传：

- `/home/panqs/ndp/NDP_copy02/requant_node0001_two_stage_stockrtl_e4_onecmd_v2_return.zip`
- `/home/panqs/ndp/NDP_copy02/requant_node0001_two_stage_stockrtl_e4_onecmd_v2_return.zip.sha256`

v2 尚未运行，E4/E5 均未通过。只有正式验收三栏动态证据、48 stage 生命周期、
observer 恢复、focused identity、return receipt 与 `SERVER_RESULT_GATE` 后，才能
把 blocker 收窄到 `B_REQUANT_SERVER_E5`。
