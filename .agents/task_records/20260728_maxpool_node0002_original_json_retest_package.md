# MaxPool node0002 原始 JSON 复测包

日期：2026-07-28

## PACKAGE_RELEASE

```text
status=PACKAGE_READY_NOT_RUN
test_id=r5_maxpool_node0002_original_json_retest_v1
family=MaxPoolUint8
instance=node-0002 / r5:hwop-0002-00
dynamic_baseline=NO_DYNAMIC_BASELINE
candidate_release=false
counts_as_E4=false
counts_as_E5=false
server_uploaded=false
server_run=false
lease=none
```

测试包：

```text
artifacts/operator_config_validation/r5-server-test-packages/
  maxpool_node0002_original_json_retest_v1.zip
```

- bytes：`1,473,174`
- SHA-256：`99fddd9c23cef9b712e4065f1b5eb8b74288ed233560f12d27ba4b612bdc6670`
- sidecar：
  `maxpool_node0002_original_json_retest_v1.zip.sha256`
- sidecar SHA-256：
  `663817d18268c618a6fe39ca6cc5a512c30a49b959019c39081db0f011693aa8`
- 唯一服务器命令：

  ```bash
  bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
  ```

- 预期回传：
  `maxpool_node0002_original_json_retest_v1_return.zip` 与同名 `.sha256`
  sidecar。

## 原 JSON 不可变边界

活动输入固定为：

```text
ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json
```

- bytes：`19,762`
- SHA-256：
  `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`
- 包内副本与活动文件逐 byte 相同；
- `source_json_rewritten=false`；
- 没有修改 JSON 的 stream、GA、PE、loop、stride、base、terminal 或任何其他
  leaf；
- 仅把 `sca_cfg.json` 与 `sca_cfg_D.json` 内 payload path 加上本包的全新
  `install/cfg_pkg/maxpool_node0002_original_json_retest_v1/` 命名空间前缀。
  配置 bitstream、execplan、地址、长度、输入和 golden 均保持冻结。

该包复用原 JSON 经官方 encoder 生成的冻结 bitstream。两个运行 stage 分别使用
slice0 与 slice1 的真实 ResNet tile；每个 stage 均要求 `int8_max` PE 连续消费多项
输入，因此不会把单输入特例误当成 MaxPool 通过。

## 动态验收门

包内不安装 observer，不修改 TB，不包含或修改任何功能 RTL；服务器根 basename
不受限制，也不读取、遍历、哈希或比较服务器已有 RTL、Makefile、filelist、TB、
Git 或源码树身份。

运行后按以下顺序裁决：

1. compile 与 simulation 独立退出状态；
2. 两份 SCA 路径回显与自然完成标记；
3. 四个正式 D transport segment 的 exact-set、128-bit/LF ABI 与长度；
4. slice0、slice1 各 `50,176` bytes 输出对独立 unsigned MaxPool golden；
5. 任一停滞、无自然完成、缺正式 D 或数值不一致均保持
   `FIRST_DYNAMIC_FAILURE/NO_DYNAMIC_BASELINE`；
6. 即使全部通过，因服务器源码身份未绑定也只记
   `VERSION_UNBOUND_DIAGNOSTIC_PASS`，不得计 E4/E5。

## 本地自检

- 两个全新目录独立构建，最终 ZIP 逐 byte 相同；
- ZIP entries：37；
- payload tree SHA-256：
  `4fd33a643688674699cd9c6a5f036497befae9c5d91afea2709465e71533dfff`；
- 解压后真实 runtime preflight：PASS；
- package bootstrap 前后 exact tree 不变；
- SCA references：11；
- SCA_D references：4；
- RTL entries：0；
- TB/observer entries：0；
- 定向 unittest：5/5 PASS；
- `git diff --check`：PASS。

验证收据：

```text
artifacts/operator_config_validation/r5-server-test-packages/
  maxpool_node0002_original_json_retest_v1.validation.json
```

SHA-256：
`594c2593c399de82791559576ff28c6b1a55e84c8ab559b2c000812f9b59c976`。

生成器/运行时/测试：

- `tools/build_maxpool_node0002_original_json_retest.py`
  @ `528f5315969e9be8f5c8f77ecfbee056a5744492fbc73e8e2acea2d82dc57d07`
- `tools/maxpool_node0002_original_json_server_runtime.py`
  @ `b92b9aa4ba5c3de60ee80b1e7aaf6ad6c59a84adcca35dd69aefc667953259b7`
- `tests/test_build_maxpool_node0002_original_json_retest.py`
  @ `204018edb9534da8e8eb59df527932e2967d054f00b9063290ea954bf9487989`

## BLOCKER_DELTA

- close：无；
- keep：`B_GA_INT8_MAX_FLOW`、`B_GA_INT8_MAX_NUMERIC`、
  `B_MAXPOOL_SERVER_E4_E5`；
- package generation 不推翻本地 E2，也不预判服务器结果。

## RULE_DELTA_PROPOSAL

无。现有服务器版本未绑定 profile、原 workload provenance、SCA_D 正式 readback、
无动态基线分类和返回收据规则足以约束本包。
