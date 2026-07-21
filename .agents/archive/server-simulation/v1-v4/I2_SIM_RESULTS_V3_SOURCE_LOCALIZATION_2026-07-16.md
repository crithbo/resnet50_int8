# I2 v3 RTL仿真结果与源码定位报告

日期：2026-07-16
结论状态：`returned_incomplete_v3 / root_cause_localized / three_way_not_comparable`

## 1. 结论

v3已经成功关闭v2的P scratch未初始化问题，但暴露出下一处、也是当前最早的确定性配置错误：

> accumulate阶段使用`special_array`产生INT32卷积结果，却把`buffer_config.buffer5.dst_port`配置为`1`。项目encoder、寄存器表和RTL一致规定：`0 = SpecArray`，`1 = GeneArray`。因此RTL把buffer5的写数据源选成了未参与该阶段的GeneralArray，SpecialArray结果没有进入buffer5；MSE4虽能产生P地址、完成旧P的RMW读取，却永远拿不到待写计算数据，最终表现为56个写地址请求、0个write-data握手、0个slice完成、只推进1/9个runtime stage。

这不是DDR预装、scratch初值、Datahub地址FIFO或MSE4写地址生成错误。建议修复点是Conv accumulate JSON生成器，而不是Datahub/DDR RTL。

当前没有post-run Bank dump，故仍不能得到硬件P/D，也不能宣称三方一致。

## 2. 原始证据与源码恢复

### 2.1 v3结果包

- 文件：`sim_results_v3.zip`
- 大小：266,186,788 bytes
- SHA-256：`9b0b15b7c351228f3f3b4d6163ba6da8391f5d1cddff04a22293eed442f172aa`
- ZIP：3,012个entry，其中2,634个文件、378个目录
- 绑定package：`artifacts/w5/hwop-0004-00/hardware_execplan_server_v3/`
- freeze ID：`f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f`
- package manifest SHA-256：`4be4a4aa824545dfff3bf1fcb0f06e0cd86e38a81f9d19e25c271550c3e73e63`

### 2.2 补回的RTL压缩包

| 压缩包 | SHA-256 | entry | 恢复内容 |
|---|---|---:|---:|
| `NDP_copy01/Slice.zip` | `a4e06f4fbb591f64af48753546f3a6127a659ea5f46ca4c8aa16fd1c9f95c17e` | 116 | 补回100个本地0-byte源文件 |
| `NDP_copy01/DDR_Model.zip` | `0503caf26c09311e4bf02fd8111a277841507825772f79c0f7b71c743a696ade` | 162 | 补回77个本地0-byte源文件 |

两个ZIP均无危险路径、无空entry；已有非空本地文件与ZIP内容逐文件一致。只恢复了主源码，不恢复`.old/.bak`备份。恢复后主PHY递归编译清单共有29份filelist、810个唯一源码引用，`missing=0`、`zero-byte=0`。

## 3. v3运行事实

机器报告：`artifacts/w5/hwop-0004-00/hardware_server_run_v3_analysis_precise_v2/comparison.json`

1. 启动前170个probe全部通过：170个目标写入匹配，170个写后MC read-data匹配；P/staged-D scratch已确定性清零，v2的X读取问题已关闭。
2. 期望9个runtime stage，实际只观察到1个stage和28个slice广播。
3. 28个slice完全同构：每个slice的MSE4产生2个P读取和2个P写地址请求；2个旧P读取均返回确定性0、无X。
4. 汇总为56个旧P read return、56个output write request、0个output write-data handshake、0个slice completion。
5. runtime阶段P和staged-D区域的Bank写事务均为0。报告里的`all_phases`大计数是v3 scratch预装，不是运行结果。
6. ZIP没有terminal/sim log、FSDB、28份post-run Bank dump或84份SCA_D输出，所以无法仅凭归档证明进程是永久死锁、被外部终止，还是仍在无新trace事件地运行；但v2/v3均在首个`Start_Comp`后约415 ns停在相同握手边界，支持确定性控制卡点判断。
7. `local_layer0_0-42`、`local_layer0_op0-42_1`、`local_op23-42`以及晚于当前运行时间窗的根级NRM日志属于旧命名空间/其他运行，不能混入v3证据。

Golden与配置绑定NDP仍为两方通过：P、D各3,211,264元素、0 mismatch；P SHA为`1ec864...`，D SHA为`2793bbe...`。硬件侧没有候选P/D，三方结论仍是`three_way_not_comparable`。

## 4. 根因证据链

### 4.1 当前JSON确实选错buffer5生产者

- `conv_full.json:443-444`：模板只有`special_array`，但`buffer5.dst_port=1`。
- `tools/generate_conv_1x1_real.py:47`：生成器直接`deepcopy(source)`，后续没有覆盖或校验buffer5生产者。
- `conv_1x1_real.json:443-444,857`：最终accumulate配置仍为`dst_port=1`且使用`special_array`。
- `artifacts/w5/conv_1x1_real/rebuild/detailed_dump.txt:450-452`：正式encoder真实编码为`dst_port value=1 / encoded=['1']`，不是JSON显示错误或运输翻转。

### 4.2 encoder、寄存器表与RTL对位一致

- `ndp-sim-ref/bitstream/config/buffer.py:11`：`0=SpecArray, 1=GeneArray`。
- `ndp-sim-ref/model_execplan/config/register_map_with_groups1.csv:79`：该位映射到RTL `buf_src_id`，语义同上。
- `NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster_Config.sv:22,94`：buffer5的`buf_src_id`注释同样为0选SpecArray、1选GeneArray。
- `NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster_Connect.sv:345-350`：`buf_src_id=1`时，buffer5的`array2arm_wtag/wdata`和backpressure都连接GeneArray；为0时才连接SpecArray。

仓库参考JSON也支持这一解释：

- SA GEMM：`ndp-sim-ref/jsons/prefill_gemm_local.json:358-359,764`，buffer5为0且包含`special_array`。
- GA量化：`ndp-sim-ref/jsons/quant_from_buffer_int32MN_uint8MN.json:198-209`，buffer5为1且包含`general_array`。
- 当前requant阶段使用GeneralArray且buffer5为1，是正确的；错误只在accumulate的SA阶段。

### 4.3 错误如何传播为v3现象

```text
SpecialArray产生accumulate结果
  -> buffer5错误选择GeneArray，SA wtag/wdata未进入buffer5
  -> MSE4的RD_Buffer_AG可以发buffer5读请求，但收不到有效buf2mse_rvalid
  -> WR_Data_Channel的prepared_data计数不增加
  -> wr_data_chl_prepared_data_vld保持0
  -> wr_chl_ob_vld_in保持0
  -> mse2mem_wdata_valid保持0
  -> Datahub写地址FIFO有数据，写数据FIFO为空
  -> 0个Bank写握手、0个slice完成、command engine停在第1/9 stage
```

对应RTL条件：

- `WR_Data_Channel.sv:290`：prepared-data valid依赖内部buffer返回数据计数。
- `WR_Data_Channel.sv:420-421`：写数据启动还要求`wr_data_chl_prepared_data_vld`；v3已证明请求队列和RMW旧值两条腿成立。
- `WR_Data_Channel.sv:524`：最终`mse2mem_wdata_valid`来自上述output buffer valid。
- `slice2hub_crossbar.sv:244`、`Stream_Engine_Connect.sv:263`：MSE4写数据valid直连Datahub，没有隐藏的软件运输层。
- `Datahub/Request_Queue/local_wr_req_queue.sv:50-64`：写地址和写数据进入独立FIFO，只有两者均非空才产生Bank写valid；这与“请求日志有地址、wdata日志为空”精确吻合。

### 4.4 排除的备选原因

- **P scratch仍为X**：排除；v3 56/56旧P返回均为0。
- **MSE4 ping-pong选到硬连0的第二路**：排除；当前`stream2.ping_pong=0`。
- **Datahub拒收写数据**：不支持；data FIFO ready在未满时为1，且trace连一次wdata handshake都没有，最早缺口在Datahub之前。
- **写地址或RMW读地址生成失败**：排除；每slice均有2读+2写请求，读返回也完整。
- **归档只是不含比较工具**：不是当前问题；即使不要求比较工具，归档也没有任何post-run硬件输出，且runtime Bank写为0。

## 5. 为什么软件两方与正式encoder没有提前发现

1. 正式encoder证明字段可以被解析、placement可解、bitstream可稳定生成；它忠实地把错误的`1`编码成`1`，并不判断“SA程序是否应该把buffer5接到SA”。
2. `NDPFuncModel/tools/physical_image_probe.py:66-188`会校验配置文本/hash、SA mode/data type/bias、loop、LC-PE和stream语义，但没有校验`buffer_config.buffer5.dst_port`。
3. 同文件`894-902`的全算子数值走专用`_run_int8_conv_1x1_job`，直接计算Conv/requireant结果，没有逐周期执行RTL的array→buffer5→MSE4→Datahub链。
4. 因而“Golden↔配置绑定NDP 0 mismatch”仍是真实的软件数值事实，但不足以证明bitstream中每个路由控制位正确。这正是本轮RTL仿真的价值。

## 6. 修复方案（本轮未实施）

不要修改v3包或原始v3 ZIP。建议生成新身份的v4：

1. 在`tools/generate_conv_1x1_real.py::build_real_1x1`显式设置`config['buffer_config']['buffer5']['dst_port'] = 0`，不要继续继承模板偶然值。
2. 在生成器和NDP target-config validator增加通用不变量：仅SA作为最终生产者时buffer5必须为0；仅GA作为最终生产者时必须为1；同时存在SA+GA时按最终写回生产者显式声明，禁止猜测。
3. 增加负向测试：将SA Conv的buffer5改成1时，preflight/NDP配置绑定门必须在生成硬件包前失败。
4. 重新生成`conv_1x1_real.json`、语义合同/hash、正式encoder bitstream、typed request、candidate freeze和hardware execplan包；配置与freeze身份改变，必须使用v4目录和新manifest，不能只手改一个JSON或bitstream位。
5. v4启动前仍执行170/170 probe；运行后首先检查MSE4 wdata是否从0变为非0、28个slice是否完成、是否推进到requant stage，再收集post-run Bank做P/D三方比较。
6. 第一stage通过后，还需修复testbench按stage slice mask观察完成的问题：现有`tb_NDP_Top_new_phy.sv:3022-3033`固定以物理slice0观察启动、slice1观察完成，后续7-slice requant mask不保证同时包含二者，会形成下一处确定性阻塞。

## 7. 若v4仍未写数据，最小插桩集合

在slice0先记录下列信号，连续观察首个StartComp后的前1–2 us；不要只记录握手成功：

- 配置：`buf_src_id[5]`、`mse_enable[4]`、`mse_pingpong_enable[4]`。
- SA/GA到buffer5：`spec_array2buf_wtag[0][0]`、`gene_array2buf_wtag[0][0]`、`array2arm_wtag[5]`、`arm2buf_wvalid[5]`、`arm2array_bp_pre[5]`。
- buffer5到MSE4：`se2mrm_req_valid[5]`、`mrm2se_req_ready[5]`、`mrm2se_rvalid[5]`、`buf2mse_rvalid`。
- MSE4写数据门：`wr_chl_queue_empty`、`wr_chl_mask_buf_vld`、`wr_data_chl_prepared_data_cnt`、`wr_data_chl_prepared_data_vld`、`wr_chl_ob_vld_in`、`mse2mem_wdata_valid`。
- Datahub：MSE4对应req 8/9的address/data FIFO empty、ready及Bank write valid。

预期修复后的首个直接证据是：`buf_src_id[5]=0`，SA输出进入`array2arm_*[5]`，buffer5产生`mrm2se_rvalid[5]`，随后`wr_data_chl_prepared_data_vld`和`mse2mem_wdata_valid`出现脉冲。

## 8. 置信边界

根因定位置信度为高：配置值、encoder位、三份规格/RTL语义、参考JSON和v3握手边界五类证据相互一致，并能完整解释28个slice同构失败。

仍保留一个严格边界：v3 ZIP没有内部波形或上述原始valid/ready信号，所以无法用v3归档直接展示“SA有效而GA无效”的那个周期。若需要最终波形级证明，应在v3配置上只增加插桩重跑一次；但从修复效率看，直接生成带`dst_port=0`和相同插桩的v4更有价值。
