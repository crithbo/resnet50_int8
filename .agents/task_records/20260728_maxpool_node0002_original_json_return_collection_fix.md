# MaxPool node0002 原始 JSON 复测包回传采集修复

日期：2026-07-28

## 状态

- `RETURN_COLLECTION_INFRASTRUCTURE_FIX_COMPLETE`
- 只修改通用/当前 MaxPool server runtime 与定向测试。
- 未修改 MaxPool 算子 JSON、workload、builder 语义、公共规则、活动计划、功能 RTL。
- 未检查服务器文件、名称或 RTL，未上传、未运行。
- 旧 `maxpool_node0002_original_json_retest_v2.zip` 内嵌修复前 runtime，不能据此声称
  本修复已进入包；fresh rebuild 必须从当前 runtime 重新复制并产生全新包身份。

## 精确根因

`collect()` 先用 `_copy_tail()` 把
`run/sim_results/compile_driver.log` 的限长尾部写入：

```text
<return staging>/logs/compile_driver_tail.log
```

随后又调用 `add(tail, "logs/compile_driver_tail.log", ...)`。`add()` 将目标解析为同一个
staging 文件，并无条件执行：

```python
shutil.copyfile(source, destination)
```

因此 source 与 destination 为同一规范化路径，触发 `SameFileError`。该异常发生在
return ZIP/sidecar 创建之前，所以即使 compile 已经失败并有可回传日志，也不会形成标准
失败回传。

## 修复

文件：
`tools/maxpool_node0002_original_json_server_runtime.py`

`add()` 现在在复制前分别规范化 source/destination：

1. 两者不同：要求 destination 尚不存在，再执行 `shutil.copyfile()`；
2. 两者相同：不重复复制，直接把 staging 中已完成限长的日志登记进 allowlist；
3. 不同 source 试图占用既有 destination 时 fail closed；
4. 原有 source 必须是普通非 symlink 文件、单文件不超过 8 MiB、relative path 安全、
   forbidden path/suffix、ZIP/extracted budget 与 sidecar 校验全部保持。

这使 staging-tail 登记幂等，但没有放宽回传路径或大小门。

## 复现测试

新增测试：
`test_compile_failure_collection_records_staged_tail_without_samefile_copy`

测试构造独立的 package/evidence/run/server 根：

- `SERVER_RESULT_GATE.status=SERVER_TEST_INFRASTRUCTURE_COMPILE_FAILURE`；
- `compile_exit_status=1`、`sim_exit_status=125`；
- `run/sim_results/compile_driver.log` 存在；
- `_copy_tail()` 与 `add()` 的 source/destination 精确碰撞；
- `sca_cfg_D.json` 为空，模拟 compile 前未产生正式 readback。

验收结果：

- `maxpool_node0002_original_json_retest_v2_return.zip` 已创建；
- 同名 `.sha256` sidecar 已创建且哈希匹配；
- return receipt 无 required missing；
- ZIP 内存在且逐字节匹配
  `logs/compile_driver_tail.log`；
- classification 保持
  `SERVER_TEST_INFRASTRUCTURE_COMPILE_FAILURE`，不计 E4/E5。

定向验证：

```text
python -m unittest tests.test_build_maxpool_node0002_original_json_retest -v
6/6 PASS
python -m py_compile tools/maxpool_node0002_original_json_server_runtime.py tests/test_build_maxpool_node0002_original_json_retest.py
PASS
git diff --check -- tools/maxpool_node0002_original_json_server_runtime.py tests/test_build_maxpool_node0002_original_json_retest.py
PASS
```

## 身份

- runtime SHA256：
  `c996b8250b3277646e38c28319ab7c0d24a1ba439ea84cc5465eff0a748c6b3a`
- tests SHA256：
  `506d6f72f4d524391ab038422ed0fe6c34eccbd6441f22e87e597d658cc366bb`
- builder（未改）SHA256：
  `6fcda24136ec44f4afde062e236b85a08a431e1ee8fd0710e8a8358c46ef5acc`

## 读取收据

- `.agents/rules/生成前必读索引.md`
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`
  `72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

适用规则：

- `CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001`
- `CDA-SERVER-RETURN-RECEIPT-001`
- `CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001`
- `CDA-SERVER-NO-DYNAMIC-BASELINE-001`

## Fresh rebuild 交接

builder 在 `_build_directory()` 中把当前
`tools/maxpool_node0002_original_json_server_runtime.py` 复制到 package 的
`package_tools/`。因此 fresh rebuild 不需要第二份手工补丁；它必须：

1. 从当前 runtime 生成全新 install/package/return 身份；
2. 保留 deterministic double build、ZIP exact-set 和 sidecar 自检；
3. 用当前 6-test suite 复验内嵌 runtime；
4. 不复用或原地覆盖旧 v2 ZIP。

