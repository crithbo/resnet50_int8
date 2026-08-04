# 2026-08-04 工作区旧测试资产隔离

## 用户授权

用户明确允许丢弃并删除已经被更新结果推进、后续不会再使用的过去测试包和测试报告。由于一次性永久递归删除约 22 GB 的范围过大，执行层安全门拒绝不可逆删除；主线采用等价但可恢复的隔离搬移，未绕过安全门。

## 裁决

- 状态：`QUARANTINED_RECOVERABLE_NOT_PURGED`
- 隔离根：`artifacts/q/oldtests0804`
- 隔离 payload 文件数：34331
- 隔离 payload 字节数：22370926271
- 加上隔离说明文件后的目录总计：34332 files / 22370927910 bytes。
- 没有 tracked deletion/rename；隔离后 `git status --short --untracked-files=no` 仍只有既有 52 个 tracked modifications。
- 没有修改功能 RTL、公共规则、算子配置、服务器状态或当前 package bytes。
- 根目录 `jsons.zip` 作为输入参考归档移动到
  `artifacts/reference_archives/jsons_20260722.zip`，未删除。

## 隔离范围

1. 已被 GAP v33 取代的旧 GAP 包、解压树、smoke、return 提取和失败候选。
2. 已被 serialized Conv v35 取代的旧 serialized Conv 包、解压树、旧边界分析和旧 compile audit。
3. 已被 QLinearAdd v29 / 冻结 D-v26 取代的旧 QAdd 包、解压树、失败/误诊断候选和旧 smoke。
4. 已被 Dequant node0077 E4-v2/E5-v1、MaxPool v5 取代的部分旧原子包和旧 MaxPool 包。
5. 旧 server candidates、旧 quarantine、旧 local reaudit、明确 scratch/empty 目录。
6. 已由 current df23e4d 证据取代的旧 1c49bd1/b7acbe5/d0aa87f 审计树。

## 明确保留

- `r5_n71_gap_v33_buffer_ag_idx_pair_diag.zip`
- `r5_n4_hw_v35_rowlc4_bufag_diag.zip`
- `r5_qadd_n7_split_c_pairmatrix_v29.zip`
- `r5_qadd_n7_split_d_full_v26.zip`
- `r5_conv_native_four_lane_df23e4d_perf_v1.zip`
- `r5_n2_maxpool_ndpsim_native_v5.zip`
- `dequant_node0077_stockrtl_e4_onecmd_v2.zip`
- `dequant_node0077_stockrtl_e5_onecmd_v1.zip`
- current native Conv E2、df23e4d RTL sync、node0075 df23e4d 证据
- current rules/plan/task records、source code、functional RTL、W3/W5 和冻结 numeric/golden

## 验证

- 隔离后活动 server-package 根：1217 files / 959534246 bytes。
- 隔离后活动 outputs：142 files / 68271969 bytes。
- 隔离后活动 server_returns：471 files / 16006759 bytes。
- 所有明确保留路径逐项存在。
- native-four-lane owner 已停止写入、提交 KEEP 清单；隔离完成后主线已通知其可恢复 fresh p4 构建，且不得引用隔离区。

## 永久删除边界

本轮没有永久删除隔离区。若用户再次明确要求 purge，应只删除
`artifacts/q/oldtests0804`，并在删除前复核当前 package/RTL/owner 状态；不得扩大到 `artifacts/q/0804` 的早期根目录清理隔离、W3/W5、current outputs 或其他路径。
