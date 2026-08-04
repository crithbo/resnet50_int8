# DequantizeLinear node0072 主线裁决

日期：2026-07-27

## 裁决

接受 node0072 为新的 `CONFIG_ONLY_CORRECTNESS_BASELINE` 和本地 materialized E2：

- typed target→static JSON→final address-bound JSON→mapping→bitstream→
  execplan/SCA→address/lifetime→config-bound physical D→logical inverse 已闭合；
- 32,768 元素 two-stage↔W3、single-mul↔W3、two-stage↔single-mul 均 0 bit
  mismatch；
- 28 slice×4736 bytes physical D，logical valid 131,072 bytes，padding 1,536 bytes；
- 每片 coverage 为 `union(i=0..73)[D_base+i*64,D_base+i*64+64)`；
- 10 个 static→materialized leaf 变化全部有 owner，unexpected=0；
- 两个空 cache 隔离副本的语义产物逐 SHA 相同。

该结论不增加正式 ResNet 三方节点：node0077 仍是唯一正式节点，计数保持 1/78。
node0072 不是正式 target、production/performance 或 E4/E5。

## 配置绕行

node0072 复用 node0077 的 4 ADD→4 MUL 普通 GA 结构，但不复用其 shape、qparam 或动态
批准。zp=0 时单层 4 MUL 数值足够；两级路线使用 8 PE、增加一层依赖/延迟和 384 个
padded element，属于正确性优先的低效率绕行。

## Flatten producer handoff

node0072 已提供：

- owner 与 standalone D allocation；
- logical `fp32[16,2048,1,1]`、strides `[8192,4,4,4]`、span 131,072 bytes；
- 28 片 final D base、每片 4,736-byte coverage；
- addressed graph、layout、final JSON、execplan/SCA 身份；
- config-bound physical D complete。

仍未提供 integrated shared multi-op execplan、跨 node lifetime/visibility、node0073
实际 consumption 和 dynamic final-write accepted，因此
`B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING` 与 View producer endpoint
blocker 不关闭，只将其从“无 producer 地址证据”收窄为“跨节点集成证书缺失”。

## 规则

发布：

- `CDA-DEQUANT-MATERIALIZED-CONSTANT-NORMALIZATION-001`
- `CDA-DEQUANT-NODE0072-CONFIG-ONLY-E2-001`

fp32 bit-string→十进制必须回读 exact binary32；`-0.0→+0.0` 只在非负 typed 域与
完整输出逐 bit 等价证明下批准。

## 身份与发布边界

- contract：
  `cf5172db59a0a7c294e49445f63cd7c61919c3aa4640af180799d2dcef42c60f`
- local E2 report：
  `50e30f52bcc95fb3f3e89b2690bc163c77b4de3d77474dd9fecb569ed5176a43`
- final JSON：
  `de212d8d49bc963bc08a5691879433c165ef2aa938aa2581b56c25e75a92da50`
- bitstream：
  `edf7949e4b308a6105f30f1accd1cc247a0121a43cc2c104bc17c4e3cc8e398b`
- ordered physical D：
  `18db1821f01336dfa641cf35ac08736e3ab7609dda31105bb8bd028dd4b41672`

`PACKAGE_RELEASE=NONE`；server lease/action=0；RTL 修改=0。
