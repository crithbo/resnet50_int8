# Trassic2.0 master b7acbe5 同步与 QLinearAdd return 分发

## RETURN_ANALYSIS

- 已通过登录态 GitHub 页面确认私有仓库
  `xlsjdjdk/Trassic2.0_RTL` 的最新 `master` 为
  `b7acbe55340ca7e98ead70335156f555929c0777`，提交说明为“修复语法问题”。
- 下载归档 SHA-256 为
  `3573d0c03f24d6433a655536653caf45702a0b71441590a09e375f0ed0f7334c`。
- 新快照根为
  `Trassic2.0_RTL_master_b7acbe5_sync/Trassic2.0_RTL-master/code/NDP_rtl`。
  Git archive 中 15 个 AXI 仿真生成物为 Unix symlink，Windows 同步时跳过；
  它们不属于活动 RTL/filelist。其余 2242 个文件已完整抽取。
- 原活动 `NDP_copy01/rtl` 已完整保存在
  `NDP_copy01/rtl_pre_github_b7acbe5_20260729`。新快照已覆盖到
  `NDP_copy01/rtl`；源与活动目录均为 2242 个文件，逐相对路径 SHA
  差异为 0，排序树 SHA-256 均为
  `62cc16b630046e7a1ed09351de8065e37764e2afb4c881f44d2f84e57c55bdc7`。
- 最新 GitHub 源码仍含确定的编译错误：
  `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v:50`
  的最后一个 ANSI port `o_Config` 后仍有逗号，下一行直接为 `);`。
  文件 SHA 为
  `c6018e762411e14346bfec672b273b826f893b11c5de0cfb38fca674f9d33c4b`；
  对同步后的活动文件运行 focused Icarus 仍以
  `Superfluous comma in port declaration list`、exit=1 失败。
  因此本次云端提交并未在仓库 `code/NDP_rtl` 当前内容中消除该已知
  global compile blocker。

## QLinearAdd return

- return 已分发给原 QLinearAdd 会话
  `019fa2c0-b647-7a91-93bf-d21a173487e3` 正式分析，主线未重复数值分析。
- ZIP 内身份为 `r5_qadd_n7_relocated_v2`；原测试包 SHA
  `60534faad0894a8b6507687159d43c824dd968f6c6a3386fa7877fc2007bf0bc`
  三方绑定一致，package/install preflight 通过，28 个 runtime D
  均未预置。
- 当前 return 缺少直接对应的
  `r5_qadd_n7_relocated_v2_return(1).zip.sha256`，所以正式收据首先
  fail-closed。
- 执行首分歧为服务器 TB 在
  `tb_NDP_Top_new_phy.sv:5854` 无条件 include
  `native_return_observer.svh`，但编译 include path 中没有该文件：
  `compile=2`、simulation 未启动、formal readback=`0/28`。
- 这不是 QLinearAdd 数值、JSON、mapping、bitstream 或 execplan
  失败；也不是本轮同步的 `code/NDP_rtl` 能自动修复的问题。
  服务器 root/TB 环境必须让该 include 可解析，或将 TB 改为不对
  不携带 observer 的包进行无条件 include。现有 QAdd v2 包不重建。

## BLOCKER_DELTA

- OPEN P0：`SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA`，最新 GitHub
  `b7acbe5` 仍 source-current-match。
- OPEN P1：`SA_INT32_NEGATIVE_PSUM_BOUNDARY`。最新源码仍有
  `C=-5,dot4=+5` 与 `C=INT32_MIN,dot4=0` 两个全域反例；当前未声明
  ResNet W3 已命中该边界。
- OPEN P1：`GA_INT8_PIPELINE0_READY`。它直接影响 GA INT8/MaxPool，
  不属于本次 QAdd FP32 路径。
- CLOSED：`SA_MUL_ARRAY_SLICE_RST_CALLER_CALLEE_MISMATCH`。当前
  `SA_ALU` caller 与 `SA_PE_Mul_Array` callee 均包含 `slice_rst`，
  focused SA hierarchy 已通过。
- OPEN：`QADD_RETURN_ADJACENT_SIDECAR_MISSING`。
- OPEN：`SERVER_TB_NATIVE_RETURN_OBSERVER_INCLUDE_MISSING`。
- 保持：QLinearAdd E4/E5=false；没有动态数值证据。

独立审计进一步确认：`b7acbe5` 与 `1c49bd1` 的全部共同活动 RTL
路径内容差异为 0；少掉的 16 项仅为 15 个 AXI 仿真归档 `.so` 和一份
旧审计日志。只在诊断副本删除尾逗号后，`SA_ALU → SA_PE_ALU →
SA_PE → SA_PE_Group` 均通过，未发现第二个确定的 SA module/port/width
编译 blocker。完整报告见
`.agents/task_records/20260729_conv_sa_b7acbe5_latest_source_compile_audit.md`。

## RULE_DELTA_PROPOSAL

NONE。既有 sidecar、联合结果门和 package/server 边界规则已足够分类。

## PACKAGE_RELEASE

NONE。QLinearAdd 原 v2 包保持不变；服务器环境修复并提供 sidecar 后
使用原身份、fresh namespace 重跑。
