# Human MAC int32→uint8 corrected-v2 stock-RTL package

## Outcome

The user-authorized second correction was used as the only operator candidate.
The native planner/mapper/encoder/execplan/SCA/SCA_D chain was rebuilt twice in
fresh isolated copies and matched byte-for-byte after binding the current
zero-cost native mapping. A single stock-RTL server package is ready.

This is an unreleased test candidate (`candidate_release=false`,
`evidence_level=E2_LOCAL_ONLY`). It is not a hardware dynamic result.

## Human input binding and authorized corrections

- source ZIP: `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\mac.zip`
  - bytes: 1620
  - SHA256: `7b6770dfe038d5e92b810c20fb4a8a620472afd1dc1e3d6837d4e3af54755a55`
- original JSON:
  - bytes: 12123
  - SHA256: `d98929d1c31b6c55d12ea8b232cf76400024d60ebc29d8d4e39c6e3abc8e4db9`
- authorized corrected-v2 JSON:
  - bytes: 13942
  - SHA256: `24002ec87abd2e1c5f659003c61aa6176d2d7bd18dbfebeae890e11d80b36eb6`
- correction 1: eight GA opcodes `mac` → `int32_mac`.
- correction 2: add the three-PE LC branch so read and write streams no longer
  share one direct LC producer.

The manifest explicitly records `human_authored_input=true`; the original and
both provenance-relevant corrected/address-bound JSONs are retained.

## Native rebuild

- mapper result: exact zero constraint cost.
- frozen current-run mapping cache:
  - SHA256: `6799229712eb82ee0aabb07cc3612edd4c9ae04af24d2e04ce1a8a960bdf9bfc`
- address-bound 128-bit bitstream:
  - SHA256: `778f8bf0bd7c18c19704a7d5f9fe7be5bc2b3624237c84593f566302492e4df2`
- execplan:
  - 57 commands
  - SHA256: `212a42f8dd33eee33e847988ed62ef268d22cb1aab7870f7bfdeecc5d50293c5`
- SCA:
  - SHA256: `d7be558771ce6ac2be0ab431c4c80b9432e2948ddb3bb85fbfe8f1d23b626a5e`
- SCA_D:
  - 28 formal readbacks, each 64 × 128-bit lines
  - SHA256: `fd5a52e87065b72fe8a24be337b45c288ad210c83622794d35226ce439e75e45`

## Fixed random test

- generator: NumPy PCG64
- seed: 20260727
- shape: 28 independent slices of int32 `[32,32]`
- domain: inclusive `[0,254]`
- golden: `(input + 1).astype(uint8)`
- input per slice: 4096 bytes / 256 × 128-bit lines
- golden per slice: 1024 bytes / 64 × 128-bit lines
- data manifest SHA256:
  `0c43df2f52e95a991257c5622de3303a1ff403c847782acf48a29692c216e264`

## Package

- directory:
  `artifacts/human_mac_int32_uint8_20260727_v1/server_package/human_mac_int32_uint8_v2_stock_rtl_fd1`
- ZIP:
  `artifacts/human_mac_int32_uint8_20260727_v1/server_package/human_mac_int32_uint8_v2_stock_rtl_fd1.zip`
- bytes: 138950
- SHA256: `5618d827dc3a64ca03699d9299ca0d71b44f53d1aecc2dc623f663d17b2a1fcf`
- manifest SHA256:
  `cb0e85b0bc251722eba6a1fa2a0a041cf64c4a1f584955e3c039f93a527ad7d3`
- ZIP entries: 67
- package RTL entries: 0
- deterministic ZIP rebuild: two fresh rebuilds and the delivered ZIP all
  matched the same SHA256.
- local package preflight: PASS.

Server command:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected formal return:

- `human_mac_int32_uint8_v2_stock_rtl_fd1_return.zip`
- `human_mac_int32_uint8_v2_stock_rtl_fd1_return.zip.sha256`

The runner compiles and runs stock RTL without an observer, with VCD/FSDB
disabled, explicit `+SCA_CFG` and `+SCA_CFG_D`, and unchanged completion and
timeouts. It hashes the RTL tree plus TB/Makefile/filelist before compile,
after compile, and after run. The result gate compares every formal D readback
exactly with its corresponding golden and reports the first divergent slice.
Missing receipts/readbacks fail closed. With no dynamic baseline, a failure is
classified `FIRST_DYNAMIC_FAILURE / NO_DYNAMIC_BASELINE`.

## Reusable rule increments for the main rules owner

1. A human-function JSON that directly fans one LC occurrence to both a read
   and write stream should be structurally audited against mapper exclusivity;
   a neutral three-PE branch may be required even when arithmetic semantics are
   unchanged.
2. Integer MAC intent must use the encoder's `int32_mac` token; the generic
   `mac` token selects FP32 MAC.
3. For standalone function checks, constrain random input so the README's
   unspecified overflow behavior is not exercised, and record the domain and
   seed in the manifest.
