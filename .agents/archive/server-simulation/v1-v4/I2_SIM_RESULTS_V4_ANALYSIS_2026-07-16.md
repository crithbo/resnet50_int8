# node-0004 第四轮RTL仿真结果分析

最后更新：2026-07-16

## 1. 最终判定

`sim_results_v4.zip`不是三方通过结果，状态为`returned_incomplete_v4`、
`three_way_not_comparable`。第四轮仍只执行了9个runtime stage中的第1个accumulate：
28个slice均读回两行确定性0的旧P、发出两次P写地址请求，但没有任何写数据握手、
没有slice完成、没有post-run Bank/SCA_D输出。因此目前不能从硬件侧提取P/D数值。

这轮最重要的新事实不是“修复无效”，而是把故障范围进一步缩小：

1. `buffer5.dst_port: 1 -> 0`的修复位确实到达服务器预装、MC读回和全部28个slice的
   gconfig广播，不存在误用v3配置或安装时丢位；
2. v3与v4的runtime/local/gexec trace逐字节相同，说明这个路由修复是正确的不变量修复，
   但不是当前停顿的充分条件；
3. 当前最早应观察的缺失信号是SpecialArray输出`valid`，而不是继续猜Bank初值、
   execplan地址或buffer5 producer位；
4. 配置链另有一个高优先级冲突：项目GEMM配置使用JSON `outport.mode=row`，正式encoder
   将其编码为1，而RTL把1解释为col-major。官方可执行GEMM样例全部使用JSON `col`
   （编码0，RTL语义row-major）。该项是v5首要候选，但尚未被硬件反事实证明为唯一根因。

## 2. 原始证据与身份边界

| 对象 | 大小 | SHA-256 |
|---|---:|---|
| `sim_results_v3.zip` | 266,186,788 B | `9b0b15b7c351228f3f3b4d6163ba6da8391f5d1cddff04a22293eed442f172aa` |
| `sim_results_v4.zip` | 266,186,780 B | `eb573db4b8cd7b9dd5981bf7fde6db40823d5e8274cbb9c5f58731948208cd00` |

v4 ZIP含3,012个ZIP条目，其中2,634个为分析器消费的文件；未发现绝对路径、`..`或
反斜杠路径，未压缩总量约1.933 GB。分析全程直接读取ZIP，没有创建完整展开目录。

操作者说明本轮使用的是身份刷新前的旧v4服务器包。其已知身份为：

- server ZIP SHA-256：`65d88db885d0f7ee09b46a1d2b1c437ac5fd93858bfffc24d0763493d647b481`；
- freeze ID：`be8dedb6aec1c63f42a041927eabb4cd9479dbd9bdc899218c9c6a54ca9fa8d7`；
- server manifest SHA-256：`62e9f11c9625b6c8490953785d2a1c34f94a8c2783468ba506d9cf5cd04d705e`；
- preflight SHA-256：`97bf735441a1755c7d349bf700b1d4ab133a9f839db2cfda9f06ed6b1cf71ea7`。

当前本地v4后来因模板级证据刷新为freeze ID `dde76763...db59a`。两版运行核心的
accumulate配置、bitstream、execplan、Bank_data和地址合同兼容，但manifest身份不同。
结果ZIP没有terminal/package manifest，故不能仅凭ZIP重新证明完整旧v4身份链；本报告的
trace解析使用当前核心等价包作为合同，并把上述旧v4身份单独登记，不能把机器报告中的
当前freeze字段误解释为服务器实际运行了刷新后的包。

## 3. v4运行事实

机器报告：
`artifacts/w5/hwop-0004-00/hardware_server_run_v4_analysis_compat/comparison.json`。

| 检查 | 结果 |
|---|---:|
| SCA payload加载 | 346项 |
| mandatory preload write | 170/170匹配 |
| mandatory MC read-data | 170/170匹配，无X |
| `Start_Comp`广播 | 28次，即1个stage × 28 slices |
| runtime stage | 1/9 |
| 旧P读返回 | 56/56，全部确定性0 |
| P写地址请求 | 56 |
| P写数据握手 | 0 |
| completed slice | 0/28 |
| P/staged-D runtime写 | 0 |
| post-run Bank/SCA_D | 0 |

每个slice的局部MSE模式也完全一致：MSE0发16次请求只返回12次，MSE1为4/4，
MSE2为0，MSE3发16次请求只返回14次，MSE4完成2次旧P读取并发出2次写地址，
但写数据为0。该模式说明停顿发生在确定性的SA输入/输出或prepared-data链，而不是单一
slice、随机X传播或Bank返回不稳定。

## 4. v3与v4精确差异

两份ZIP的2,634个文件名完全相同；2,604个文件内容完全相同，仅30个文件变化：

- 28份`sim_results/gconfig2slice/slice*/gconfig2slice.log`；
- `sim_results/bank_frame/slice0/bank0_frame.log`；
- `sim_results/bank_frame/slice0/bank0_mc_rdata.log`。

28个slice的gconfig差异完全相同：

```text
v3  10893249000 | 0xfaec0ffe819f6078
v4  10893249000 | 0xf2ec0ffe819f6078
```

服务器Bank预装与MC回读中的对应128-bit配置beat也一致变化：

```text
v3  0xfaec0ffe819f6078dffc7b1fff8f607f
v4  0xf2ec0ffe819f6078dffc7b1fff8f607f
```

这精确证明`dst_port`修复位经过了“安装payload -> Bank写入 -> MC读回 -> 28-slice广播”。
除这30份配置运输证据外，全部runtime/local/gexec trace逐字节相同。因此应撤销
“buffer5生产者位就是当前最早且唯一根因”的强结论，保留“该位原先确实错误且必须修复”。

## 5. 源码定位与候选排序

### 5.1 已证明正确的buffer5选择关系

`Buffer_Manager_Cluster_Connect.sv`规定buffer0～4为读buffer、buffer5为唯一array写buffer；
buffer5根据`buf_src_id[5]`在GeneArray和SpecArray之间选择。`Slice_cdc.sv`把SA输出接到
`spec_array2buf_wtag[0][0]`。因此SA-only accumulate选择0、GA-only requant选择1的生成器
不变量仍然正确，不能回退。

但现有trace只证明配置beat到达slice广播口，没有内部寄存器值或SA输出valid日志。
若内部`buf_src_id[5]`已经是0而SA从未产生valid，改变选择器不会改变runtime trace；这与
本次现象完全相容。

### 5.2 高优先级候选：SA outport主序标签/编码相反

- RTL `SA_Outport_Connect.sv`明确写明`0=row_major, 1=col_major`；
- 正式encoder `ndp-sim-ref/bitstream/config/special.py`却把JSON `col`编码为0、`row`编码为1；
- `config/utils/excel_config.py`又写`col:1 row:0`，与RTL一致但与encoder标签相反；
- `config_generator_ver2.py`和`config_nse.py`的GEMM式配置均使用数值0；
- 上游三份可执行GEMM JSON使用`outport.mode=col`，三份GEMV JSON使用`row`，没有
  GEMM+`row`参考例；本项目`conv_full.json`和`conv_1x1_real.json`却是GEMM+`row`。

当前SA配置低位为`...819f6078`；只把JSON outport改为`col`预计编码为
`...819f6070`。这很可能是历史标签反转造成的配置错误。不过8×8阵列转置通常也可能只
改变输出次序，不一定完全禁止valid，因此在观察内部信号或做v5单变量实验前不能写成
已证明根因。

### 5.3 次优先级候选：SA输入/邻居/tag生命周期未完成

全部slice都呈现MSE0 `12/16`、MSE3 `14/16`，而MSE1 `4/4`。该确定性缺口可能来自
SA inport、neighbor ring、tag/last-index或backpressure，使SA尚未形成任何完整输出。
现有ZIP没有SA/array内部trace，不能仅靠MSE地址日志区分“输入未齐”与“输出valid被抑制”。

## 6. v5必须增加的最小插桩

下一轮不应仅再改一个JSON后盲跑。先在testbench/RTL trace中对slice0增加以下时序信号，
必要时再广播统计28个slice：

1. `buf_src_id[5]`，证明配置寄存器内部最终值为0；
2. `sa_outport_group_out_tag.valid`及对应data/tag；
3. `spec_array2buf_wtag[0][0].valid/data`；
4. `array2arm_wtag[5].valid/data`；
5. `arm2array_bp_pre[5]`，确认buffer5是否给SA ready；
6. buffer5写请求valid、写数据valid和入队计数；
7. MSE4 prepared/data gate及缺失条件；
8. SA各inport收到的有效token计数、last/tag和阻塞源。

建议在第一个`Start_Comp`后设置有界watchdog：若MSE4已发出写地址而指定周期内从未出现
SA output valid，打印上述信号快照并`$fatal`。这样一次运行即可区分：

```text
内部buf_src_id错误 -> 配置寄存器/位序问题
buf_src_id正确但SA无valid -> SA输入、mode、outport或tag问题
SA有valid但spec_array2buf无valid -> CDC/连接问题
spec_array2buf有valid但buffer5无数据 -> buffer选择/backpressure问题
buffer5有数据但MSE4无wdata -> prepared/MSE写链问题
```

## 7. 下一执行方案

1. 保留`sim_results_v4.zip`为不可变原始证据，不删除；本轮未完整展开，无展开目录需清理。
2. 把当前v4标记为`returned_incomplete`，不再复跑同一包期待不同结果。
3. 先提交上述最小插桩；静态确认信号层级在VCS elaboration中存在。
4. 以当前刷新后的身份为基线创建全新v5，不修改旧v4。v5做单变量修正：保持
   `buffer5.dst_port=0`，把GEMM SA outport从JSON `row`改为`col`，并对编码0/RTL row-major
   增加跨encoder/RTL不变量测试。
5. 重新生成配置、bitstream、request、preflight、freeze和server ZIP，保存v4/v5唯一位差。
6. 虚拟机先跑slice0短watchdog诊断；观察到SA output valid和buffer5 write data后再跑完整
   28-slice/9-stage及post-run Bank。
7. 只有完整P/D输出存在后才运行三方比较；本轮不升级G6/G8。
