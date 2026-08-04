# Requant atomic v1 包自检失败

日期：2026-07-26

## 回传身份

```text
rq_node0001_atomic2_stock_v1_return.zip
size=14893
sha256=a41a0d6f850bacae223ce801d73599cefe8b30a45b5d5ac94a9ce5d461bdb374
entries=13
```

回传 allowlist 内 12 条文件记录的 size/SHA 全部正确，但
`RETURN_RECEIPT.status=incomplete`，缺 10 项正式 preflight/install/identity
收据。

## 裁决

```text
classification=SERVER_TEST_INFRASTRUCTURE_PACKAGE_PREFLIGHT_FAILURE
first_divergence=package exact-set check
compile_started=false
simulation_started=false
observer_installed=false
counts_as_atomic_dynamic_attempt=false
counts_as_E4=false
counts_as_E5=false
candidate_release=false
```

`compile/sim/run=125` 是 runner 的“尚未执行”哨兵，不是 timeout 124。所有
stage、MSE4 和 formal D 的 0 计数都表示未开始，不能称作数值或 RTL 失败。

## 根因

atomic runtime 的执行顺序为：

1. Python 启动 `package_tools/requant_atomic_server_runtime.py`；
2. 在 exact-set 校验前导入同目录
   `requant_node0001_server_runtime.py`；
3. Python 默认在包目录写入
   `package_tools/__pycache__/requant_node0001_server_runtime.cpython-*.pyc`；
4. manifest 不包含该运行时新文件，严格 exact-set 必然失败。

已从干净本地包副本复现：

```text
returncode=1
extra=
  package_tools/__pycache__/
    requant_node0001_server_runtime.cpython-312.pyc
missing=[]
```

所以这是包 runtime/bootstrap 缺陷，不是服务器、配置语义或 RTL 问题。

## 最小修正

- 在导入任何包内模块前设置 `sys.dont_write_bytecode=True`；
- `PREPARE_AND_RUN.sh` 第一条 Python 命令前导出
  `PYTHONDONTWRITEBYTECODE=1`；
- exact-set 仍须严格，不能把 `__pycache__`/`.pyc` 加入忽略项；
- 新增“从新解压 ZIP 执行真实入口，执行前后 package tree 逐字节不变”的回归；
- 生成全新 package/install/run/return 身份；配置 JSON、mapping、bitstream
  与功能 RTL 无需因此改变。

本次没有动态首分歧，所以 `guard-only`、`round-only`、`alias-lifetime` 全部
保持关闭。

机器报告：
`server_returns/requant_atomic_v1_preflight_failure_analysis_20260726.json`。
