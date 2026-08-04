# 2026-08-03 node0075 negative-psum 主线独立复核

## 复核目的

用户明确质疑该问题是否可能像此前 Conv occupancy 一样属于测试误报。主线没有把
node0075 owner 的 testbench 或枚举器直接当作最终权威，而是重新建立两条独立证据链：

1. fresh current-RTL testbench，以数学期望值判定，并加入跨零相邻正控；
2. fresh NumPy/ONNX 全 recurrence 枚举，不 import owner 的
   `node0075_negative_psum_reachability` 实现。

裁决：

`CONFIRMED_REAL_CURRENT_RTL_DEFECT_NOT_FALSE_POSITIVE`。

## current identity

- Trassic source commit：
  `8f2f3181c1103d705cdf9b9722959e7315f8b875`。
- `SA_PE_Float_Control.v` SHA256=
  `4214262e12ab80bf3be867f558d762e134c3122f16df4f7d08063e383242c4e6`。
- `SA_PE_Float_CSA.v` SHA256=
  `ea24759841d990f230f9c33a111f934e107c996a85b2f5ea00c9408ca73d0223`。
- `SA_PE_Mul_Array.v` SHA256=
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`。
- `SA_ALU.v` SHA256=
  `c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06`。

## 独立 packing 与数学复核

- packed weight=`0x01fe11fe`，按 current control 的 MSB→LSB s8 lane 为
  `[1,-2,17,-2]`。
- packed activation=`0x1c0d0100`，MSB→LSB u8 lane 为
  `[28,13,1,0]`。
- lane products=`[28,-26,17,0]`，dot4=`+19`。
- 因此：
  `-20+19=-1`、`-19+19=0`、`-18+19=+1`。
- packing、operand direction 与数学期望均不是沿用 owner report 的解析结果。

## fresh current-RTL 边界 testbench

- testbench：
  `outputs/node0075_negative_psum_reachability/independent_boundary_recheck_tb.sv`。
- bytes=`2278`。
- SHA256=`d284a6546453d2085ea5a25a00991d01082bc98256c6a15b31ea36f880caec13`。
- compiled VVP：
  `outputs/node0075_negative_psum_reachability/independent_boundary_recheck.vvp`。
- bytes=`546470`。
- SHA256=`189a4b70a951353899962aa5ea9d09a1c10b5262be439d893c9ee88814cfc6dc`。
- Icarus compile exit=`0`；VVP simulation exit=`0`。

实际观测：

```text
case            CSA raw     observed    expected     verdict
-20 + 19        80000001    ffffffff    ffffffff     PASS
-19 + 19        80000000    80000000    00000000     FAIL
-18 + 19        7fffffff    00000001    00000001     PASS
  0 + 19        00000013    00000013    00000013     PASS
 +7 + 19        0000001a    0000001a    0000001a     PASS
INT32_MIN + 0   00000000    00000000    80000000     FAIL
```

这组相邻正控排除：

- 整体一个周期采样错位；
- A/B packing 反向；
- dot4 不是 19；
- 所有负 psum 均错误；
- 所有负→正跨零均错误。

精确 cancellation 时，current 内部 `c_Result0_wire=0x80000000`。live RTL 分开产生
`o_IntResult[30:0]`，同时原样复制 `c_Result0_wire[31]`，使低 31 bit 为零而 bit31
保持 1，得到非规范“负零”码 `0x80000000`；INT32 下它就是
`-2147483648`。`INT32_MIN+0` 的独立失败进一步证明该表示不是完整 signed INT32
domain 正确，但 node0075 blocker 只需要第一项真实 W3 exact-cancellation 即已成立。

## fresh 全 recurrence 枚举

- 该程序直接读取冻结 A `.npy`、formal accumulator `.npy` 与 ONNX weight initializer；
  没有 import owner 枚举模块。
- A SHA256=
  `c2d08ebd45a564d63e499b333a9576bbdafc71448ee693c8a199a7cf65193f12`。
- formal accumulator SHA256=
  `ee8422fe7c20f0cc40adb18abcd0b8b0f9c433a6c2283e8c87262e3a7d419ec3`。
- enumerated recurrence=`8,192,000`。
- negative psum=`4,343,952`。
- negative→exact-zero=`272`。
- first stream-order hit=`(m,n,k_group)=(0,65,3)`，`psum=-19`，`dot4=19`。
- mathematical final accumulator mismatch=`0`。

以上计数与 owner report 独立、逐项一致，排除了 owner 枚举实现自身造成 272-hit
误报的可能。

## 最终裁决与边界

- confirmed：
  `B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE`。
- retain open：
  `SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION`。
- node0075：
  `HARDWARE_CAPABILITY_BLOCKED / PACKAGE_RELEASE=NONE`。
- 本轮未修改功能 RTL，未进入 E2，未生成服务器包，未上传/运行服务器。
- 被排除的误报假设：stale RTL、lane packing、operand direction、pipeline latency、
  owner self-confirming TB、owner enumeration bug、synthetic unreachable edge。
- 未证明事项：注释中的 full-width candidate 足以修复；服务器 full VCS；任何
  production/E2/E4/E5。

## machine report

- path：
  `artifacts/operator_config_validation/r5-node0075-negative-psum-mainline-independent-recheck/report.json`。
- bytes=`5989`。
- SHA256=`bcfaa5047b4b5aa1845fc253f0c5da4b7ea1c6f9b221f54cf2a2173899fda10d`。
- JSON parse PASS。
