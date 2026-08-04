# Trassic2.0 master 1c49bd1 RTL 主线审计与硬件组交接

## RETURN_ANALYSIS

- 审计身份：
  `xlsjdjdk/Trassic2.0_RTL@1c49bd1155a89ff187e29016dc4415e59a55f991`。
- 快照原件和活动 `NDP_copy01/rtl` 未修改；试修仅位于 `outputs/`
  诊断副本。
- 确定 global compile blocker：
  `SA_PE_Float_Control.v:50` 的最后一个 ANSI port 后多余逗号。
  Conv/GAP 新 return 均在该处 compile=2，simulation 未启动。
- 删除该逗号后，最新 10 个 changed SA files 在
  `SA_ALU -> SA_PE_ALU -> SA_PE -> SA_PE_Group` 范围内无第二个
  确定的 module/port/width 编译 blocker；本地无生产 VCS，完整 top
  仍需硬件组确认。
- 确定 full-domain arithmetic defect：
  `SA_PE_Float_CSA.v:49-50` 对负 psum 的拆分重构在
  `C=-5,dot=+5` 和 `C=INT32_MIN,dot=0` 时错误。当前冻结 ResNet50
  未证明命中该边界。
- 确定 MaxPool runtime flow blocker：
  最新 `GA_PE_Inbuffer.sv:527-557` 仍缺 INT8 pipeline0 ready
  分支；最新快照定向仿真复现连续 INT8 token 停滞。
- `SA_PE_Mul_Array.v` reset/data-register 不对称只记风险，未证明
  accepted-output 传播。

## BLOCKER_DELTA

- OPEN P0：`SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA`。
- OPEN P1：`SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION`。
- OPEN P1：`GA_INT8_PIPELINE0_READY_BRANCH_MISSING`。
- REVIEW ONLY：
  `SA_MUL_ARRAY_RESET_DATAPATH_ASYMMETRY`。
- CLOSED CONCERN：最新 18-bit CSA/carry 修复在极值和 20,000 个
  随机向量中未复现历史错误。

## RULE_DELTA_PROPOSAL

NONE。以上属于 RTL 实现问题，不是公共配置规则缺口。

## PACKAGE_RELEASE

NONE。Conv node0004 v3、GAP node0071 v2 包均无需因本轮 RTL 审计
重建；修复服务器 RTL 后原身份重跑。MaxPool 必须在 INT8 handshake
修复后重跑其 GitHub 原始 JSON 测试。

## 交付

- 人工报告：
  `docs/trassic2_rtl_hardware_group_handoff_1c49bd1_20260729.md`
- 机器合同：
  `contracts/rtl_sync/trassic2_master_1c49bd1_remaining_blockers_v1.json`
- 独立 SA 审计：
  `.agents/task_records/20260729_trassic2_master_1c49bd1_sa_independent_audit.md`
- changed-set compile 审计：
  `.agents/task_records/20260729_conv_sa_rtl_compile_exhaustive_audit_1c49bd1.md`
- NDP top filelist 审计：
  `.agents/task_records/20260729_trassic2_master_1c49bd1_ndp_top_compile_blocker_audit.md`

