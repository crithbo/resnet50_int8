# 2026-08-06 package storage rotate moved-evidence 修复

## 触发

native Conv p10→p11f 轮换时，`rotate` 已把 new release evidence 随 package 从 staging
移入 `pending_receipts`，随后仍从旧 staging 路径计算 evidence SHA，导致索引写入阶段
报错。owner 依据实际 p10/p11f 集合恢复了正确索引，package bytes 未受影响。

## 修复

`rotate` 现在在任何移动前：

1. 计算 new/previous evidence SHA；
2. 计算 evidence 若随 package 移动后的目标路径；
3. 完成移动后用预先计算的 SHA 和新目标路径写入 storage index。

外部 evidence 不随包移动时保持原路径；previous evidence 位于
`pending_receipts` 时，索引路径同步指向 `tested`/`superseded` 归档位置。

## 收据

- `tools/manage_server_test_package_storage.py`
  - bytes: 28445
  - SHA256: `981f5cd5cb44e960b30805a5d2f380e117edd57a7746f6eedfb5498739314c94`
- `tests/test_manage_server_test_package_storage.py`
  - bytes: 13468
  - SHA256: `3a893a5973fc583de63630cc5c5b863a76f6dbde34a6e6ccb7f14e4b940d2717`

新增回归覆盖 new evidence 随 staging→pending_receipts 移动、previous evidence 随
pending_receipts→tested 移动，并验证索引中的路径、SHA 与最终文件一致。

验证：

- `tests.test_manage_server_test_package_storage`: 8/8 PASS；
- `py_compile`: PASS；
- `git diff --check`: PASS。

## 边界

未修改或重建任何 ZIP、sidecar、pending/tested/superseded package 内容；未运行服务器；
未修改功能 RTL、配置、mapping、bitstream、execplan、SCA、numeric、W3 或 golden。
