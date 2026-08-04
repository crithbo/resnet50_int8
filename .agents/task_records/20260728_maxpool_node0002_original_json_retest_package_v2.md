# MaxPool node0002 原始 JSON 复测包 v2

日期：2026-07-28

## 状态

- `PACKAGE_READY_NOT_RUN`
- 原始 JSON：
  `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json`
- 原始 JSON SHA256：
  `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`
- `source_json_rewritten=false`
- 未检查服务器文件、名称或 RTL 身份；未上传、未运行；无 lease。

## v1 失败分类与 v2 适配

v1 服务器回执在进入安装和 RTL 仿真前失败，首错为
`package exact file set/hash differs`。因此后续缺少 `sca_cfg_D.json`
只是安装复制未执行的连带结果，不构成 MaxPool 功能结论。

按用户要求，v2 去掉 package root 与 installed root 的“整个目录精确文件集”
比较。传输或解压流程增加无关文件不再阻塞。仍保留以下生成前/运行前门：

- manifest install identity；
- 原始 JSON 固定 SHA256；
- `sca_cfg.json` / `sca_cfg_D.json` JSON 结构；
- 11 项输入 SCA 与 4 项输出 SCA_D 路径安全、必需文件存在和大小；
- 输出目标在运行前必须不存在；
- package 内 RTL/TB/observer 项为 0。

## v2 身份

- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/maxpool_node0002_original_json_retest_v2.zip`
- ZIP bytes：`1473117`
- ZIP SHA256：
  `d3ee1bbdd7e4738dbb1b10f644cdeefc65d4e0fd1e5b12edef4267e5f4df7e40`
- sidecar SHA256：
  `81ee40f7b8fb7b83c7e602b4973c4ad25eede24757a2bd540feb8bddc063c2cf`
- validation receipt SHA256：
  `4e21e01ad7fb180a09b9ee589fc2f8f381f56355b2d7994864ffc35844ad16bc`
- payload tree SHA256：
  `c67a9c8e8a92f7e56e31b5046b48736c6adfe9a9ee85820b5f879d3eca890cb2`
- ZIP entries：`37`
- deterministic double build：`true`
- targeted unittest：`5/5 PASS`

## 服务器入口与回传

唯一运行命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
```

预期回传：

- `maxpool_node0002_original_json_retest_v2_return.zip`
- `maxpool_node0002_original_json_retest_v2_return.zip.sha256`

该包仍是 version-unbound diagnostic，不计 E4/E5。
