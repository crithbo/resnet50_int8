# 服务器测试包最短取用路径扁平化

日期：2026-08-06  
状态：`COMPLETE`

## 用户要求

测试包人工取用位置只保留最短路径。必要的完整验证收据可以放在其它位置，但待测目录
不得继续使用`family/package-id`嵌套；每个在测算子仍只保留一个最新版本包。

## 最终布局

```text
pending/<package-id>.zip
pending_receipts/<family>/<package-id>/
tested/<family>/<package-id>/
superseded/<family>/<package-id>/
```

`pending/`是唯一人工取包入口，只含4个ZIP，目录数为0。ZIP sidecar、validation、
final-audit及其它release receipts已无损迁移到`pending_receipts/`。用户无需取用或
单独回传这些校验收据。历史tested与
superseded整包归档结构不变。

## 当前待测包

1. GAP v40：`pending/r5_n71_gap_v40_lc_supply_conservation_diag.zip`，
   SHA-256 `7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4`。
2. serialized Conv v49：`pending/r5_n4_hw_v49_lc9_actual_compilefix.zip`，
   SHA-256 `2b7faeb4b838133f041432ff707792047d113bf65871aa8936e3f2f4c502e27c`。
3. QLinearAdd v36：`pending/r5_qadd_n7_cout32_v36.zip`，
   SHA-256 `b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382`。
4. native four-lane Conv p9b：`pending/r5_n4_0cc_p9b_tx5.zip`，
   SHA-256 `d85429b61e8270d0c4108bfdcdf3a66bce44a437b8aab96b0412a5555dffb085`。

四个ZIP的bytes/SHA均与迁移前一致。总包计数保持pending=4、tested=40、
superseded=23。

## 规则与实现

- `.agents/rules/服务器测试包生成规则.md`：bytes=85333，
  SHA-256 `5540e9c724e9c313e9a874a8251ad291328d4df80f01382ca091520893e757a1`。
- `.agents/rules/生成前必读索引.md`：bytes=14037，
  SHA-256 `2697fec8192f5008a0b5f288a4c38c36e9f493ff85db264479e4c5a88b03b706`。
- `tools/manage_server_test_package_storage.py`：bytes=27693，
  SHA-256 `a8f0d7a80014b7ff68e0eddd220737069206e85c27f7c2af64bc4f1f94a87d39`。
- `tests/test_manage_server_test_package_storage.py`：bytes=10596，
  SHA-256 `1248ffd2ece1706673f77220858d99847c98023a7270706af265580b6a2902b1`。
- `PACKAGE_STORAGE_INDEX.json`：bytes=88217，
  SHA-256 `3e2c18523643b2fc2cb6a8938501c488018b45d69ea621bd45ac7edb85aa79e7`。

工具新增`flatten-pending`和`compact-pending`迁移命令；`apply-manifest`与`rotate`
均直接生成ZIP-only扁平pickup路径，并把sidecar及其它非取包收据分离到
`pending_receipts/`。index继续用family metadata执行每族最多一个pending的检查。

## 验证

- `py_compile`：PASS。
- package storage unittest：7/7 PASS。
- actual tree audit：PASS。
- pending文件数=4、目录数=0；只有4个ZIP。
- pending family唯一性：4/4 PASS。
- `git diff --check`：PASS。

## 边界

本轮只改变本地存放路径和轮转工具。未改ZIP、sidecar、包内identity、config、
workload、golden、functional RTL、ISA或硬件；未上传、运行服务器或获取lease。
