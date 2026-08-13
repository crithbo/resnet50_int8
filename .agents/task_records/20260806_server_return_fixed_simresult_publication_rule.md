# 2026-08-06 服务器 return 固定 simresult 发布规则

## 用户要求

后续服务器测试包无论从哪个 `NDP_copy0x` 根运行，正常跑完或被外部可捕获信号中断时，
都必须把 return ZIP 与 `.sha256` 发布到：

```text
/home/panqs/ndp/simresult
```

原 `NDP_copy0x`、package/install/run 目录和调用 cwd 不再保留同名结果。

## 本轮输入收据与派发

四份正式 return 已只读核验并分别派发给唯一 family owner：

| package | bytes | SHA256 | 用户中断说明 |
|---|---:|---|---|
| `r5_n71_gap_v41_branch_isolated_config_fix_return.zip` | 162750 | `01b548c257bc1feefa3c2168f6d68afd7b8a41bab403c6b4abdcaced52e88c34` | 可能意外外部中断 |
| `r5_qadd_n7_cout32_v36_return.zip` | 161996 | `ec11d21241650ecf61e5aab6125ba622a9d49f65e989bace5e709358c2ed6136` | 可能意外外部中断 |
| `r5_n4_0cc_p10_trig_return.zip` | 97182 | `568a0c63f0db3e21a63a9fae94a711f91583fabb4f00a1a47ced0d613d721434` | 可能意外外部中断 |
| `r5_n4_hw_v50_dterm_owner_diag_return.zip` | 113782 | `5401413f1586e8b7de4ad6ed2be2f8b2a0b4eea5072a80349b5b3217601e9d8a` | 用户确认跑完 |

前三个 owner 必须先依据 signal/finalizer/last-qualified-progress 区分自然终止、timeout、
INT/TERM 与意外中断；不得把 formal D 缺失或默认 0 直接提升为功能失败。serialized Conv
v50 按用户确认的完整运行结果消费。

## 规则增量

新增非同义规则：

`CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`

核心语义：

1. 固定服务器运行时结果目录，不受 cwd、`NDP_copy0x` 参数或环境变量影响；该绝对路径
   不是本机存储路径，本机不得创建、映射或写入它；
2. normal、compile/sim failure、timeout、diagnostic finish、HUP/INT/TERM 共用
   exactly-once finalizer；
3. ZIP 与 sidecar 直接在固定目录 staging、自检并原子发布，不先在运行根创建最终同名文件；
4. 目标冲突 fail closed，不覆盖旧结果；重跑前成对归档旧 ZIP/sidecar；
5. 发布后 package/install/run/cwd 原位置必须 `duplicate_absent=true`；
6. fresh final-ZIP audit 必须通过本机隔离 harness，以三个不同 root 及
   normal/compile-fail/INT/TERM 正控证明 production runner 固定指向该服务器路径，并对
   目录改写、不可写、冲突、sidecar错误和原位置副本执行负控；harness 映射不得进入
   production runner 或把结果目录变成可配置项；
7. `SIGKILL`、主机掉电和文件系统失效属于 shell trap 无法保证的物理边界，不得伪称覆盖。

适用性为规则发布后的 next fresh package。已冻结待测包不因本规则单独重建；它们的下一份
fresh successor 必须应用。

## 修改收据

- `.agents/rules/服务器测试包生成规则.md`
  - bytes: 90154
  - SHA256: `755672c11626accf38160ddd5e2959cdf8949c0b4483f1243ff6b3a3bdb0ad8c`
- `.agents/rules/生成前必读索引.md`
  - bytes: 14448
  - SHA256: `37f75653e2c5c167a6fb5d178785b9d3f3a3262b78cddf19d34663418c179e88`

`git diff --check` 通过；规则 ID、固定路径与 `duplicate_absent` 均可由文本检索命中。

## 边界

本轮没有重建或修改当前 pending ZIP，没有服务器上传、运行或 lease，没有修改
functional RTL、ISA、hardware、active ndp-sim、算子配置、mapping、bitstream、execplan、
SCA、numeric、W3 或 golden。
