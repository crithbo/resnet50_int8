# Dequant node0077 stock-RTL E4 one-command v1

状态：服务器 E4 原子包已生成并完成本地静态/语义/确定性校验；尚未在服务器执行。
因此仍为 `candidate_release=false`、`evidence_level=E2_LOCAL_ONLY`，
`B_DEQUANT_SERVER_E4_E5` 未解除。

## 输入与边界

- 唯一语义输入为 Dequant v5 冻结资产；strict JSON、generation receipt、
  semantic contract、local E2 report、stage manifest、bitstream 和 execplan 的委托
  SHA-256 均逐项匹配。
- 原 v5 execplan/bitstream 是 CRLF 文本；服务器 128-bit ABI 禁止 CRLF。打包仅做
  保持 128-bit word 序列不变的 CRLF→LF 规范化，并同时记录原始 SHA 与包内 LF SHA。
- 本轮没有重新调用 planner/mapper/encoder/execplan；复用依据是原完整重建 receipt
  与 exact input identity，不是旧服务器残留或失败包。
- 未修改 `NDP_copy01`，未修改任何 `rtl/`，包内功能 RTL/TB/observer 文件数为 0，
  也不包含 RTL patch。

读取收据：
`.agents/task_records/dequant_node0077_e4_package_read_receipt_20260725.json`。

## 包身份

- install/package：`dequant_node0077_stockrtl_e4_onecmd_v1`
- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/dequant_node0077_stockrtl_e4_onecmd_v1.zip`
- ZIP bytes：`121976`
- ZIP SHA-256：
  `04c6860b6ea08e2ba8f9eab731ad2978792d754e513289adb98bdde78bd86781`
- manifest SHA-256：
  `f8194ea2bab6318d036e1e452faab11037997e4858c47edf409be1f5ed914430`
- payload tree SHA-256：
  `644d2b09685b181fbcc21dd350414a7a3ab67986c28ff4bed521c1af17845b47`
- sidecar：
  `artifacts/operator_config_validation/r5-server-test-packages/dequant_node0077_stockrtl_e4_onecmd_v1.zip.sha256`

两份全新确定性构建与正式构建的 ZIP SHA-256 三者完全相同；ZIP 共 76 个 entry，
exact-set、entry 内容、规范时间戳和 sidecar 均通过专项 validator。

## 唯一服务器命令

解压后进入包目录，只执行：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

脚本自动执行 package preflight、pre-install identity、唯一命名空间安装、
post-install exact-set、全新 RUN_DIR compile/sim、四阶段 stock RTL identity、
E4 分析和 allowlist-only return。VCD/FSDB 均为 0；完整 compile/sim log、build tree、
waveform 和嵌套压缩包不回传。

预期回传：

```text
dequant_node0077_stockrtl_e4_onecmd_v1_return.zip
dequant_node0077_stockrtl_e4_onecmd_v1_return.zip.sha256
```

## E4 动态门

1. 28 个 slice 均出现且仅出现有序的
   `Start Cfg → Cfg Finish → Start Comp → Comp Finish`。
2. 仿真进程自然零退出，TB success marker 恰好一次；无 timeout、fatal、显式 error、
   OOB、Cannot open 或 APB SLVERR。
3. SCA 正式加载 30 个 payload；SCA_D 正式 dump 28 个矩阵。
4. 每片正式 D 回读为 188 条 128-bit 行，即 752 个 fp32；前 750 个与 W3 shard
   golden bit-exact，末 2 个必须为 `0x00000000`。
5. pre-install、post-install、post-run、post-restore(no-op) 的 RTL tree、focused RTL、
   Make/TB/filelist/observer 和安装命名空间保持稳定。
6. return receipt 完整且只包含白名单文件。

E4 通过后只把 blocker 收窄为 `B_DEQUANT_SERVER_E5`；必须等 E4 回传独立验收后，
再生成全新的 package/install/run/return 身份执行 E5。本包不包含 E5，也不声明发布。

## 本地测试

- `python -m py_compile`：builder/runtime 通过。
- `python -m unittest -v tests.test_build_dequant_node0077_onecmd_server_test tests.test_dequantize_linear_vertical`
  ：10/10 通过。
- 包 validator：正式目录与 exact ZIP/sidecar 通过。
- 当前 Windows 环境没有 bash，未执行本地 `bash -n`；服务器入口的命令/token、
  fresh-target、trap、timeout 和路径合同由专项 Python 测试与包 validator 检查。

## 新增/更新文件

- `tools/build_dequant_node0077_onecmd_server_test.py`
- `tools/dequant_node0077_server_runtime.py`
- `tests/test_build_dequant_node0077_onecmd_server_test.py`
- `.agents/task_records/dequant_node0077_e4_package_read_receipt_20260725.json`
- `.agents/task_records/dequant_node0077_stockrtl_e4_onecmd_v1_20260725.md`
- 正式 package 目录、ZIP 与 sidecar

公共规则没有改动；GAP 路线没有触碰。
