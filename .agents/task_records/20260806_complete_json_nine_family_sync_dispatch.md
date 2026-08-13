# Complete-JSON 公共同步后的九 family 派发

日期：2026-08-06  
主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 公共同步身份

- `.agents/rules/算子配置规则.md`
  SHA256=`52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820`
- `.agents/rules/生成前必读索引.md`
  SHA256=`d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6`
- `contracts/operator_config/complete_json_generation_contract_v1.json`
  SHA256=`de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746`
- `tools/validate_complete_operator_json_candidate.py`
  SHA256=`c24a6fe103ebba3ece557bfd76417907f41847dd5550013f7fd45b047f49be0a`
- `tools/audit_complete_operator_json_family_set.py`
  SHA256=`f7efd5cc471bf13d77a1224444f5b49a92bf82c446a99b757dc2fc7fe635f184`
- 主线公共回归：`10/10 PASS`。

## 已通知 owner

1. Flatten/View：`019fa366-d218-7122-839c-0b52d83faf13`
2. DequantizeLinear：`019fa2bf-f9a5-7a73-ada3-b2b910721de3`
3. QLinearMatMul/node0075：`019fc775-8de0-7f10-bc4a-026a4673776f`
4. MaxPool：`019fbe9f-3f2d-7071-806c-1ae72ae96391`
5. GAP：`019fa366-cb1f-7ae2-880c-f527be0680cd`
6. QuantizeLinear：`019fa2c0-572b-7f21-ac5a-96e773dde534`
7. QLinearAdd：`019fa2c0-b647-7a91-93bf-d21a173487e3`
8. RequantizeUint8：`019fa2bf-95cd-7502-82c8-6a48cf12d648`
9. Conv/SA：`019fa2c1-17df-7122-bcbd-a727aaf173f5`

## 统一任务边界

各owner只执行本族：

- complete candidate contract；
- 逐leaf field provenance ledger；
- handler capability；
- current-test diff；
- 按适用性执行composition boundary；
- family-set manifest及两个共享validator。

输出只能为`COMPLETE`或带精确unresolved leaves的`BLOCKED`。本轮硬禁止：

- mapping、bitstream、execplan、SCA生成或修改；
- 服务器测试包生成或修改；
- 上传、服务器运行、lease；
- plan/public rules/functional RTL/其他family修改。

所有owner完成后必须主动回传本主线。派发成功，不代表任何family已经COMPLETE，也不改变
现有package release或E3/E4/E5状态。
