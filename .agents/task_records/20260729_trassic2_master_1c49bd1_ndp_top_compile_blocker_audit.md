# Trassic2 master 1c49bd1 NDP_Top 编译阻塞审计

日期：2026-07-29  
审计身份：`TRASSIC2_MASTER_1C49BD1_NDP_TOP_COMPILE_20260729`  
用户给定 commit：`1c49bd1155a89ff187e29016dc4415e59a55f991`

## 结论

按“活动 filelist + 源定义 + 实例化”三方交叉确认，正式确定项只有一项：

- `Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v:50-51`
- line 50 的末端口声明为 `output[1:0] o_Config,`，line 51 紧接 `);`。
- Icarus 在仅规范化 VCS filelist 语法、未改 RTL 的诊断编译中明确报告：
  `SA_PE_Float_Control.v:50: error: Superfluous comma in port declaration list.`
- 该源由 `filelists/SA_PE_filelist.f:2` 纳入真实活动闭包；模块定义在本文件 line 10，
  `SA_ALU.v:63` 实例化 `u_SA_PE_Float_Control`。
- 影响：compile 不能完成，因此 elaborate、生成仿真可执行文件与 simulation start 均被阻断。
- 最小修复：只删除 line 50 `o_Config` 后的逗号，保留 line 51 `);`；不改变端口和功能语义。

诊断副本仅完成这一候选修复后，相同错误从日志消失。原源 SHA-256：
`c6018e762411e14346bfec672b273b826f893b11c5de0cfb38fca674f9d33c4b`；
诊断副本 SHA-256：
`568f83437a5c57b891e320614d2f188052964fb5569e61f3c6606c5d40b4cabe`。

## 活动闭包与排除边界

- 入口：`filelists/NDP_Top_filelist.f`，SHA-256
  `bbfaed6996c216db947f2cb8f099dd844f657966ef42f602db62b0af5b03a06c`。
- top：`NDP_Top_new`。
- 递归闭包：30 个 filelist、844 个源文件。
- 活动源冲突标记：0。
- 活动源重复 module 定义：0。
- `not_used/**` 与 backup 文件未被活动闭包引用，只作为陈旧噪声排除。

以下均不计 RTL 错误：

1. Icarus 不直接支持 VCS 大写 `-F`；
2. `phy_dram_wrapper.vp` 的 VCS `protected128` 模型；
3. Icarus 对 unpacked localparam assignment pattern、generate scope array 与
   `signed'(...)` 的限制；
4. `DW_ecc`、`DW_fifo_s1_sf`、`DW_sync` 的本机 unknown-module。仓库 DDR 仿真
   `DDR_Model/MC_IP/test/mc_env/sim/Makefile:123` 已用
   `-y /opt/synopsys2/syn/U-2022.12-SP7/dw/sim_ver` 声明生产 vendor library。

没有第二项达到源定义/实例化交叉确认门槛。

## 硬件组最小验证清单

1. 在 commit `1c49bd1155a89ff187e29016dc4415e59a55f991` 上只删除上述逗号。
2. 使用生产 VCS 命令、真实 `NDP_Top_filelist.f`、DDR DesignWare library 完整 compile；
   要求 exit 0，且 `SA_PE_Float_Control.v` 无语法错误。
3. elaborate `NDP_Top_new`；要求 exit 0。
4. 生成仿真可执行文件并做 start-only smoke，至少到首个 clock/reset 调度事件。
5. 保存 commit、源 SHA、compile/elab/start 日志。

## 证据与声明边界

机器报告：
`outputs/rtl_compile_audit_1c49bd1/v1/rtl_compile_blocker_audit_v1.json`。

闭包清单：
`outputs/rtl_compile_audit_1c49bd1/v1/active_closure_manifest.json`，
SHA-256 `3f66953dc075cf5df7455fb8c4b1f113b69b1723bd2985679597ba6b57c2c80c`。

快照原件、活动 RTL、`.agents/plan.md` 与公共规则均未修改。未检查服务器文件/名称/身份，
未上传、未运行、未取得 lease。没有重测 MaxPool 数值，没有消费 MaxPool 复用资产，没有生成或
修改服务器包；`PACKAGE_RELEASE=NONE`，不称 E4/E5。
