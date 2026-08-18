# QLinearAdd node0007 v66 cfg42 主线验收

- predecessor: `r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3`（未运行；已证32/16 stale lineage；归 `superseded`）
- current package: `r5_qadd_n7_tailround_lanephase_v66_cfg42`
- status: `PACKAGE_READY_NOT_RUN`
- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_lanephase_v66_cfg42.zip`
- bytes: `108658281`
- SHA-256: `f9add4a1f54d922fb76fbe7d7b8a72e4965fea0c27546864fb3032bcad8862bc`
- release receipt: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007/r5_qadd_n7_tailround_lanephase_v66_cfg42/r5_qadd_n7_tailround_lanephase_v66_cfg42.release_receipt.json`

授权且唯一功能差异为 `GROUP2.COL_LC end/stride 32/16 -> 4/2`。两次独立正向重编码确定性得到 `a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f`；恢复32/16的负控重现并拒绝 `a3094e0066c979f53a8aa03c89379841c0df9198ab76009dc38b254c764c2fa0`。JSON→encoder→bitstream→SCA/SCA_D→manifest链已绑定。

动态合同要求依次请求 `0x33333333`、`0xcccccccc`，两次均accept/clear，不重复第一半lane，并继续检查output/terminal/formal-D。RTL、numeric、workload、golden与其余配置冻结。全部本地门禁与存储审计通过；没有upload/run/lease/server action。
