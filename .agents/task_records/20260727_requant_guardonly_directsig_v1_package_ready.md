# Requant node0001 guard-only direct-signal v1 package

- Date: 2026-07-27
- Status: `PACKAGE_READY_NOT_RUN`
- Scope: the unique authorized successor to `rq_node0001_guardonly_stock_v4`
- Dynamic classification: `FIRST_DYNAMIC_DIAGNOSTIC / NO_DYNAMIC_BASELINE`
- Candidate release: `false`
- Counts as node0001 E4/E5: `false / false`
- Functional RTL/TB changes: none
- Package `rtl/**` entries: 0

## Mandatory-read receipt

- Receipt: `.agents/task_records/20260727_requant_guardonly_directsig_v1_read_receipt.json`
- SHA256: `c6aac0818efb00c4863f6032fe4e188ec18e14da0ddd5415ab5901947f61d990`
- Requant rule SHA256: `d1bd49486cc257fe4ab05b25c80ec42228c71090848207ef271f11053b9c0772`
- Server rule SHA256: `67018547fbe4e485d3d8c2420821e0c8f65bfec0bab0ecc1099ad9de37e55eb7`
- Authoritative v4 analysis SHA256: `79ef9534c481ca1b436c2f815b6860feb91584cd3f0f77982b6fa1660a4f8da6`

## Package identity

- Install/run/return identity: `rq_node0001_guardonly_directsig_stock_v1`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_directsig_stock_v1.zip`
- ZIP size: 63,236 bytes
- ZIP SHA256: `715a4b8abdd45b3251c464eba4359cea8af740c75b238a68d956f949524a1939`
- Sidecar: `artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_directsig_stock_v1.zip.sha256`
- Sidecar file SHA256: `fe11e481987141f51479922631463e0674f4d3ac5f0616a04d409bcf10b33e68`
- Manifest SHA256: `ceb1405df42fa3ee6e9480e46d1350f04825bdae6d906c57a8a00b7d3e3c4031`
- Payload tree SHA256: `a9e4952cce6e337cb685c0a244d8e8e144bdb7a96abf7aa2bcc458175b2273a0`
- ZIP exact entries: 33
- Forbidden/RTL/pyc/wave/nested-archive entries: 0
- Validation receipt SHA256: `a898587a02c9453d996082ddd9921224f18256968a59a0d708520c154b9e407d`

Server command from the extracted package directory:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return:

- `rq_node0001_guardonly_directsig_stock_v1_return.zip`
- `rq_node0001_guardonly_directsig_stock_v1_return.zip.sha256`

## Frozen semantic workload

The v4 guard JSON, native mapping/bitstreams, guard-only execplan, SCA/SCA_D
semantics, two slice-distinct inputs, RequantGuard payload, golden and expected
writes are byte-identical. The semantic freeze covers 22 files with tree
SHA256 `71f75503eae94dfb5c7c2b92f0c0bb173bb863da023eca666f18cc79feb720a9`.

The static-intent receipt separately proves:

- guard JSON `general_array.inport.inport0.int32tofp32 == "true"`;
- parsed bitstream `GAInportConfig.int32tofp32 == true`, encoded bit `1`;
- this does not claim runtime consumption or propagation.

## Direct-signal evidence

The read-only observer now records these ordered boundaries:

1. MSE0 read data and Buffer transfer;
2. GA inport runtime conversion bit and decoded conversion flag;
3. inport buffer valid/data;
4. converter input valid/data;
5. converter registered output valid/data;
6. final inport tag/data/ready;
7. odd-column PE selected input valid/data;
8. SFU input, compute enable, LUT address/slope/intercept and preprocess output;
9. SFU ALU/result;
10. normal outbuffer accepted write;
11. MSE4 accepted write data.

MSE4 request and write-data handshakes have independent counters and stable
transaction IDs. Every accepted wdata is logged even when request/address
pairing is unavailable; temporal pairing status is reported separately.
Transfer/pre-remap linear/post-remap addresses remain separate domains.

Focused identity was expanded over all required GA Inport, interconnect, SFU
LUT/PE preprocess/postprocess/comparator/search-tree, GA Outport and prior
MSE/Buffer/PE files.

## Local package acceptance

- Deterministic fresh builds: 2, ZIP byte-identical
- Exact ZIP/sidecar/manifest: pass
- Fresh-extract bootstrap tree: 33 files and 294,168 bytes before/after,
  tree SHA256 `79c973a875bca24f3631b3dff0a1c7e6028d81e3b84c88dc885cde8f359c07c9`
- Observer final concatenation XMR scan: 488 generated-instance references,
  0 runtime-indexed references
- Transactional install/verify/restore: byte-exact pass
- Package tree unchanged by bootstrap and observer transaction: pass
- Directed tests:
  `python -m unittest tests.test_build_requant_guard_only_onecmd_server_test`
  = 10/10 pass
- Local `NDP_copy01/rtl/**` diff: empty

The next server return must identify exactly one earliest boundary as
raw/parsed divergence, unobserved, partial coverage or captured-all-zero.
Responsibility remains `CONFIG_CONSUMPTION | RTL_CONTROL | OBSERVER_EVIDENCE`
until dynamic evidence resolves it.

## Parallel server package B

The already completed independent Dequant full-v6 E4 candidate remains ready:

- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/dequant_node0077_stockrtl_e4_onecmd_v2.zip`
- Size: 147,148 bytes
- SHA256: `2ac27a4856b36bb660c0293ff53f84794464283712f20fe0d84dabfa16b699e0`
- Command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`

The two workloads remain separate ZIPs, install namespaces, run directories and
return identities.
