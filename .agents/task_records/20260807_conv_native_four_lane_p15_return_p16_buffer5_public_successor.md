# Conv native-four-lane p15 formal return → p16 Buffer5 public successor

Date: 2026-08-07  
Owner: `019fc783-1146-7901-9e40-64d0ed8e052d`  
Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Formal p15 return

- Return: `C:\Users\15383\Downloads\r5_n4_0cc_p15_installonly_return.zip`
  - bytes: `1882697`
  - SHA256: `530964b1ea2da55e9f43aaa7224a285fb32159d6da3a2e15646deceb507a4a61`
- Exact source p15:
  - bytes: `45918261`
  - SHA256: `e323e3394124c9b8b655037ac916cc3e3510360cb0097f1f91f60bfb9508c9b8`
- Analysis:
  - `outputs/conv_native_four_lane_0ccae916_p15_return_analysis/report.json`
  - SHA256: `1fa2bcf7b4146c69dcee89f7f494ad4ba003b40234c99a08e3ed86688bb79541`

The return ZIP passed CRC, single-root, safe-path, exact-set, allowlist,
record-hash, install-only layout and NDP-root direct-name/type preservation.
Package/install/path/observer preflights passed, production compile passed,
and actual compile identity was collected. The external `INT` occurred only
after two complete qualified no-progress windows with the same key total
(`314`) and state digest, so this is
`LONG_RUNNING_C0_BACKPRESSURE_STALL_CONFIRMED_BEFORE_EXTERNAL_INT`, not
`PARTIAL_INTERRUPTED`.

Last proven good was c0 exec with request counts `[16,16,16,140,32]`, ARM
requests `[8,7,10,7,6,3]`, ARM responses `[0,3,8,3,4,0]`, 30 accepted SA
inputs, 3 accepted SA outputs and one accepted MSE4 index. First divergence
was the fourth SA output remaining raw-valid while Buffer5-facing ready
remained low; Buffer5 write mask stayed `0xff` and all ARM finish counts
remained zero. The deepest unique leaf was not observable in p15.

p15 was c0 diagnostic only. It contained no formal-D payload by design and
did not pass natural terminal, 27-run, 320D, mismatch-zero, performance or
E3/E4/E5 conjunction.

The exact p15 source manifest contained stale
`observer_binding.source_sha256=ec034728...`; the returned source manifest
was exactly the source bytes with that single value replaced by the actual
observer SHA `9c9c11f...`. Therefore:

- exact p15 source consumable: `false`
- p15 plus one-leaf delivery hotfix diagnostic consumable: `true`
- exact release gate: `false`
- escape: `PACKAGE_LOCAL_DELIVERY_SELF_AUDIT_ESCAPE`

## Fresh p16 successor

Identity: `r5_n4_0cc_p16_b5port`

Unique pickup ZIP:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p16_b5port.zip`

- bytes: `45938384`
- SHA256: `b9dfb0d282013e45328c905c19957523afba81d505bbf5b4600dc82ace6c3611`
- status: `PACKAGE_READY_NOT_RUN`
- class: `PERFORMANCE_DIAGNOSTIC_CANDIDATE`
- candidate release: `false`

Command:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected fixed return:

```text
/home/panqs/ndp/simresult/r5_n4_0cc_p16_b5port_return.zip
/home/panqs/ndp/simresult/r5_n4_0cc_p16_b5port_return.zip.sha256
```

p16 preserves p15 workload, config, mapping, bitstream, execplan, SCA input,
numeric, W3, golden and timeout bytes. SCA_D changes only by the fresh
install/codex_runs identity prefix. Functional RTL/ISA/hardware and active
ndp-sim are not carried or modified.

The fresh observer binding is exact and the real package-local observer guard
passes; a manifest SHA mutation fails closed. The appended diagnostic reads
only public ports of the exact current `Buffer` module at Buffer5:

- ARM producer valid/rw/address/ready/wvalid/clear
- MRM consumer valid/rw/address/strb/ready/clear
- qualified SA acceptance and bounded stable-backpressure snapshots

No new private-state XMR is used. Actual compile identity collection adds
`Buffer.sv`, `Buffer_Manager.sv`, and `Memory_Req_Manager.sv`.

## Final audit receipts

- family final audit:
  `pending_receipts/conv_native_four_lane/r5_n4_0cc_p16_b5port/r5_n4_0cc_p16_b5port.final_zip_audit.json`
  - SHA256: `794f2b71d9b82cb3feacd504369a6578ed256ec27dabd537eacfad71cf58ee19`
  - result: `PACKAGE_READY_NOT_RUN`, valid `true`
- shared runtime-layout report:
  - SHA256: `2d802f68d01a3305d2dd3ce82de71672e2fcedfce8d0e4f15ecd136b51bcaa0a`
  - pass: `true`, errors: `0`
- runtime-layout harness:
  - SHA256: `fbe1556728d46919e479e29f26d66bff3fe9d5a9fcff887be253f091137e0b3a`
- shadow build profile:
  - SHA256: `da22a639c2f71a789957f2fa3c1f033dfcad7c806dd87936d921b2c3677bd4a7`
- deterministic double build: `true`
- normal/preflight-fail/compile-fail/HUP/INT/TERM/missing-install:
  all expected dispositions passed
- NDP root direct name+type exact set: unchanged
- fixed simresult duplicate absence: passed
- exact longest path arithmetic and p12 mutation negatives: passed
- exact observer guard → compile stub → simulator stub positive chain: passed
- changed observer event trace and missing-marker negative: passed
- pending ZIP-only storage audit: passed

Storage rotation:

- p15: `tested/conv_native_four_lane/r5_n4_0cc_p15_installonly`
- p16: unique pending for `conv_native_four_lane`
- storage index SHA256:
  `2d83ff352ad74f94d44e827aaf52cfbb9fc2439bd06168fdd3bf609c6b8d0bb6`

## Claim boundary and rule feedback

p16 has not been uploaded or run. It does not claim production compile,
natural terminal, formal 320D, numeric correctness, performance, E3, E4 or
E5. Production actual/local/cloud identity differences remain nonblocking
provenance after compile and must be adjudicated from the formal return.

`RULE_CONFIRMATION`:

- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- `CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`
- `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`
- `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`

`RULE_DELTA`: none. The p15 escape is an implementation/test omission already
covered by the exact source-binding and exact final-runner positive-control
rules.
