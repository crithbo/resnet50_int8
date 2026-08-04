# Requant guard-only stock v3 包交付记录

日期：2026-07-26

`rq_node0001_guardonly_stock_v3` 是 v1 预启动包错误的全新身份替代包。guard JSON、
mapping、bitstream、execplan、输入与 golden 未改变；未启用 round-only 或
alias-lifetime，也未修改、包含或安装任何 `rtl/` 文件。

## 身份

```text
ZIP size=57407
ZIP SHA256=bc5ee98d2fae9ced6b581fa8483b48a1fd5459d164c583059ecb4720c44e7133
payload tree SHA256=2f151f52ddf2a9443d0d8e3e5bae80b1b3eaac96a89c01c68e0974d43b13c7ec
ZIP entries=31
rtl entries=0
pyc/__pycache__ entries=0
status=PACKAGE_READY_NOT_RUN
candidate_release=false
```

本地中间身份 v2 在 builder 自测隔离修正后未覆盖，直接冻结为
`UNPUBLISHED_LOCAL_PREDECESSOR`；服务器交付使用 v3。

## 自检

- 两次隔离构建的 ZIP 逐字节一致；
- exact ZIP 全新解压后的真实 package preflight 通过，包树前后 exact
  path/size/SHA 不变；
- 调用包内真实 `requant_node0001_server_runtime.py install-probe` 成功找到
  `requant_mse4_guard_observer_tail.svh`；
- `verify-probe-installed` 通过；
- `restore-probe` 后 observer 与 preimage 逐字节一致；
- 探针事务前后 package tree 不变；
- Requant guard-only 与 atomic2 定向测试 14/14 通过。

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

预期回传：
`rq_node0001_guardonly_stock_v3_return.zip` 及其 `.sha256`。
