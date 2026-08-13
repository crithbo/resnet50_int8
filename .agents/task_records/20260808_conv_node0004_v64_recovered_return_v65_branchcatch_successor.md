# serialized Conv node0004 v64 recovered return → v65 branch-catchup successor

## 结论

用户回收的 v64 return 是正式、可消费结果，不是无价值的残片。ZIP CRC、单根、安全路径、exact-set、allowlist、逐文件收据、source/package/install/observer 身份均闭合；compile=0、run=0、signal=NONE。DUT 未自然结束，正式 D 为 0/320（missing=320、mismatch=0），所以 E3=true、E4=false、E5=false，不能把全缺失解释为数值通过。

v64 证明前两次 descriptor-empty 短缺都会从 delta=1→2 回到 0；第三次在 descriptor=18、prepared=20、descriptor-pop=18 后永久保持 delta=2。此时 Memory_AG index queue 为空且没有完整三输入 match，Buffer_AG row/column/tag queue 与 32-entry prepared store 已满。因此旧“每次固定少两个 descriptor”假设被否定，首分歧收窄为第三次空窗的 shared-LC/address 分支追平与 Buffer 分支容量循环。

旧 `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED` 继续保持 `INVALIDATED_NOT_RTL_BUG`。

## v65

fresh successor=`r5_n4_hw_v65_branchcatch_diag`，分类=`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`、candidate_release=false。只增加 qualified branch-catchup 边界快照，并修复 repeatable runtime 的 collector ABI：runner 传入 6 个参数时 wrapper 现在显式接收并向 base collector 转发 `return_zip`。numeric/W3/qparam/tail/workload/config/golden/timeout/backpressure/functional RTL 全部冻结。

生成期间 generation index/server rule 漂移，首个未发布 build 被拒绝交付；完整复读 current 后以同一未发布 v65 identity fresh 重建。最终 ZIP：

- bytes=5167230
- SHA256=`b78e3c7257a34e23fab6cf046922a488c8e1f17356d6dfa6df11234e882a3816`
- deterministic double build=true
- FINAL_ZIP_RULE_SELF_AUDIT_PASS=true，errors=0

本地 exact runner 隔离夹具覆盖 normal、preflight-fail、compile-fail、HUP、INT、TERM；86/86 SCA 输入由 TB cwd 实际打开；missing matrix、missing bitstream、wrong prefix、bad root、missing argument、unique-tag return collision 均 fail closed。Windows/Git-Bash 的 `/tmp` 映射仅存在于本地夹具，未进入 production runner/manifest/ZIP。

## 证据

- formal return report: `outputs/conv_node0004_v64_recovered_return_analysis/report.json`
- continuous closure report: `outputs/conv_node0004_v64_return_v65_successor/report.json`
- final ZIP audit: `outputs/conv_node0004_v64_return_v65_successor/v65_final_zip_audit.json`
- observer/consumer validator: `outputs/conv_node0004_v64_return_v65_successor/v65_branchcatch_validation.json`
- family runner: `outputs/conv_node0004_v64_return_v65_successor/v65_family_validation.json`
- shared runtime: `outputs/conv_node0004_v64_return_v65_successor/v65_shared_validation.json`
- runner visibility: `outputs/conv_node0004_v64_return_v65_successor/v65_runner_visibility.json`

## 规则反馈

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`。本轮无需非同义公共规则增量：现有 no-sidecar transport、hang-first、continuous closure、repeat execution、fixed simresult、install-only、final-ZIP audit 与 storage rotation 门已经分别捕获 return 身份、动态卡点和 collector ABI 逃逸。

未修改 plan、公共规则、功能 RTL 或其它 family；未上传、未运行服务器、未取 lease。
