# DeepSeek Softmax 增量规则

适用范围：DeepSeek prefill GQA 中融合 Softmax 经显式 crop contract 展开为
scale+mask、row max、sub+exp、sum+reciprocal、normalize 五个 stage。公共
身份、生成门和证据等级不在本文重复。

## CDA-DEEPSEEK-SOFTMAX-MASK-STRIDE-OWNER-001

`prefill_mac_fp32MN_fp32MN_fp32MN` 的 C 端口承载可跨 attention head/slice
复用的 mask。其物理步进不能从 A/D 的 `[1,S,S]` shape 机械复制。对于当前
`S=32` 的可信模板及可信物化包，C 的 `dim_stride` 必须保持
`[32,512,null]`；A/D 的相应 stride 为 `[32,1024,null]`。

Stage 必须用 `write_reg_hint=softmax_mask_reuse_rows` 显式声明这个所有权；
缺少 hint 时不得由 shape 推断为 512，也不得静默覆盖模板为 1024。

## CDA-DEEPSEEK-SOFTMAX-EXP-BUFFER-LAYOUT-001

`prefill_sub_SFU_fp32MN_fp32M_fp32MN` 的 A 端口在当前可信物化包中使用以下
16 项 buffer 空间顺序：

```text
[0,1,8,9,2,3,10,11,4,5,12,13,6,7,14,15]
```

Stage 必须用 `write_reg_hint=softmax_exp_m8_n_interleave` 显式选择该布局。
默认 `[0..15]` 只能作为另一个布局合同使用，不能因 shape 相同而替代可信
Softmax 布局。

## CDA-DEEPSEEK-SOFTMAX-NORMALIZED-ROUNDTRIP-001

加入上述两个 hint 后，必须从 Stage 完整重建 mapping、64/128-bit
bitstream、execplan 和 SCA/SCA_D，并满足：

1. 五份最终 materialized JSON 与 `jsons/softmax/jsons/` 的可信实例逐字段
   相等；
2. 两次空 cache 隔离运行的非可视化文件逐字节一致；
3. 每个 stage 的 `Load_Config` 长度等于同轮 64-bit 源码流行数；
4. 五 stage 的顺序、SFU `Ex/REC` 加载点和 D 覆盖不变。

通过这些条件关闭规则归一化后的结构/配置 E2。上游 raw prefill Stage 仍可保持
只读，但项目活动 Stage producer 必须把两个 hint 作为已登记叶子写入
`layer0_prefill.rule_normalized.json`；family materializer 不得临时补值。活动
producer、最终 JSON 和双隔离生命周期全部通过后，
`B_DS_SOFTMAX_STAGE_LAYOUT_HINT_GAP` 对项目活动链路关闭。

## CDA-DEEPSEEK-SOFTMAX-PAYLOAD-COVERAGE-001

可信包中的零长度 install/output tensor 只能证明路径集合，不能证明 Softmax
数值。正式本地数值闭环至少需要非空的每片输入、row max、exp、reciprocal
sum 与最终 FP16 输出，并验证每行和约为 1、mask 后元素和独立软件公式。

