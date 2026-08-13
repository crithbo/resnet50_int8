# 2026-08-06 human remote add fp16MN/fp32N config-bound analysis

## Scope and authority

- Owner lane: human-authored JSON consumer.
- Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Authorized action: read-only package/config consumption and isolated configuration-level verification.
- Not authorized and not performed: JSON correction, mapping/bitstream/execplan/SCA rebuild, server package, upload/run/lease, functional RTL/ISA/hardware/active ndp-sim modification, or host-generated tensor replay into a runtime.
- Claim ceiling: `LOCAL_E2`; this record does not claim CGRA_SIM, RTL, E3, E4, or E5.

## Input identity and preservation

- Original ZIP: `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/remote_1.zip`
- bytes: `975515`
- SHA256: `fc7f37f4c860273b80287b7e9e7b0fb8a3af1eebd41e599b84fc8083a596aba6`
- ZIP audit: 303 members, 268 files, single root `remote_1`, CRC PASS, unsafe paths 0, duplicate/casefold duplicate names 0, symlinks 0.
- Extracted read-only working copy: `artifacts/human_remote_add_fp16_fp32_20260806_v1/source_extract/remote_1`
- Extracted-file manifest: `artifacts/human_remote_add_fp16_fp32_20260806_v1/extracted_file_sha256.tsv`, 35837 bytes, SHA256 `dd6bf1e8ac5e3a840c3209c5760731c9e5a62471de8745c3c0cb9c80eca1e096`.
- Human operator JSON: `jsons/op0_prefill_add_fp16MN_fp32N_fp32MN.json`, 15883 bytes, SHA256 `07b406315e23e140b406c7fcb4080ea7ed43876e5e2093026c43872f417a2f8b`, `human_authored_input=true`.
- Original ZIP and every supplied JSON/mapping/bitstream/execplan/SCA/data file remained byte-identical.

## Read receipt

The plan changed while the audit was running, so the new plan was fully reread before finalization.

| Path | bytes | SHA256 |
|---|---:|---|
| `.agents/agent.md` | 13174 | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md` | 40135 | `43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70` |
| `.agents/rules/生成前必读索引.md` | 14037 | `2697fec8192f5008a0b5f288a4c38c36e9f493ff85db264479e4c5a88b03b706` |
| `.agents/rules/算子配置规则.md` | 37680 | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` |
| `.agents/rules/NDP硬件字段语义.md` | 14974 | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| `.agents/rules/DeepSeek_ONNX到Stage验证规则.md` | 6698 | `1b36b9844bfcbd3b8f153556543fb9f2cda8975719675106f4cd9997821873ea` |
| `.agents/rules/DeepSeek_码流生命周期增量规则.md` | 5516 | `247f4469572359055af077b631d59f4193cb1735c8932c857f5de94e1a83518a` |

Historical human-MAC audit, formal-return analysis/adjudication, and long-term boundary records were also read before consuming this new family.

Applicable confirmed rule IDs include:

- `CDA-CONFIG-SEMANTIC-OWNERSHIP-001`
- `CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001`
- `CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`
- `CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`
- `CDA-CONFIG-BOUNDARY-MICROTRACE-001`
- `CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001`
- `CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001`
- `CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001`
- `CDA-DEEPSEEK-STAGE-JSON-ORACLE-001`
- `CDA-DEEPSEEK-CONFIG-LENGTH-PADDING-001`

## Operator contract

- op: `prefill_add_fp16MN_fp32N_fp32MN`
- slices: 28
- A: logical `[1,1,32]`, native omitted dtype default fp32, 128 bytes/slice, base `0x00000000`.
- B: logical `[1,32,32]`, fp16, 2048 bytes/slice, base `0x00000080`.
- D: logical `[1,32,32]`, native omitted dtype default fp32, 4096 bytes/slice, base `0x00000880`.
- Physical index: `(m//8)*256 + n*8 + (m%8)`.
- Golden equation: `D_physical = fp32(B_fp16_physical) + tile(repeat(A_fp32[0:32], 8), 4)`.
- Address decode uses `slave[29:25], bank[24:23], row[22:10], column[9:4], subword[3:0]`; all three per-slice regions are legal bank-0 regions and do not overlap.
- SCA/SCA_D encode all 28 slice prefixes at `slice*0x02000000`; all addresses and D lengths (`256` 128-bit lines/slice) match.

The supplied `matrix_D` files are golden data, not a formal runtime return.

## Mapping and effective-runtime overlay finding

`mapping_review.json` maps:

- logical `stream1` (A vector schedule) -> physical `READ_STREAM0`
- logical `stream0` (B matrix schedule) -> physical `READ_STREAM1`
- logical `stream2` (D write schedule) -> physical `WRITE_STREAM0`

The standalone JSON fields are:

- logical B `stream0.base_addr=0x0`
- logical A `stream1.base_addr=0x80`
- logical D `stream2.base_addr=0x880`

If those loaded JSON fields are interpreted as the terminal state, they read the wrong regions:

- B schedule reads `[0x0,0x800)`, with 128 wrong-region bytes and 128 missing B bytes.
- A schedule reads `[0x80,0x100)` eight times, with 128 wrong-region bytes and all 128 A bytes missing.
- This intermediate-only interpretation gives 28671/28672 element mismatches across 28 slices.

However, the package execution order is `Load_Config -> Write_Reg -> Start_Comp`. The supplied execplan explicitly writes:

- input A base `0x0` to physical `rd_stream0`
- input B base `0x80` to physical `rd_stream1`
- output D remains `0x880` in physical `wr_stream0`

Applying those writes through the mapping restores effective logical bases:

- B logical stream0/physical READ_STREAM1 -> `0x80`
- A logical stream1/physical READ_STREAM0 -> `0x0`
- D logical stream2/physical WRITE_STREAM0 -> `0x880`

Therefore, the apparent JSON base swap is a nonterminal loaded-state artifact, not a final packaged-execution error.

## Configuration-level execution result

Existing entry assessment:

- The current strict read-only config validator was used.
- The generic `NDPFuncModel/tools/physical_image_probe.py` is specialized for int8 accumulate/requant workloads; CGRA_SIM has no exact supplied-JSON entry for this operator. It was not misapplied.
- An isolated config-bound schedule interpreter was added under the human-family tool namespace. It reads the supplied config/mapping/execplan/SCA/data, never writes a runtime tensor, and never feeds a host result back into any execution.

Results:

- isolated interpreter natural completion: yes, 28/28 slices started and finished.
- supplied D completeness: 28/28; every D binary is 4096 bytes and every D text image has 256 complete 128-bit lines.
- A/B/D text-to-binary equivalence: 28/28 for each tensor.
- missing D slices: 0.
- X/Z tokens: 0.
- independent golden equation: 28/28 slices bit-exact.
- effective post-Write_Reg A/B/D region coverage: missing bytes 0; wrong-region bytes 0.
- effective config-bound result: element mismatches 0/28672; byte mismatches 0/114688; first divergence `null`.
- read traffic per slice: B 2048 bytes unique/traffic; A 128 bytes unique with 1024 bytes traffic (8x broadcast reuse); D 4096 bytes unique/traffic.
- 64-bit config rows: 62; execplan `config_length`: 62; 64->128 repack and module/operator/install copies are identical.
- deterministic repeat: byte-identical report SHA256.

This `natural completion` is only the local interpreter finishing; it is not RTL natural completion.

## Structural/control/lifetime audit

- All DRAM loop trip counts are finite and the parent graph is acyclic with shared root LC0.
- Logical A/B/D buffer groups map to physical GROUP0/GROUP1/GROUP4 and buffers 0/2/5.
- All bound buffers are enabled, `buf_full_last_index=3`, `buffer_life_time=1`, `dst_port=1`; read-stream full indices match their bound buffers.
- Static output tag path can reach last-index 0, and stream2 statically covers the entire D region.
- Cycle-level branch ready/valid interaction, lifetime decrement/release under stalls, GA last propagation, the final DDR write-data handshake, and RTL natural completion remain `DYNAMIC_ONLY`.

The current strict shadow validator returns exit 1 only for `SCHEMA.UNKNOWN_FIELD` at `$.mul_shape`. This field is extra unconsumed metadata; it does not affect the already supplied bitstream/execplan result, but a future strict native rebuild must remove or explicitly contract it rather than silently ignore the fail-closed result.

Direct consumer receipts were read at ndp-sim HEAD `ec12424516ae0304228dd2321d4e604fe225e04e`; `output_writer.py` SHA256 `f91fef24890231bec90a321466d54578498df1713c26bdd8b79de069162ce18`, `control_registers.py` SHA256 `de296642364ddc1be2ca3f1163871c1098460d14bcb250290ebac4f5512bdc08`. Both files were already dirty in the shared worktree, so HEAD is not claimed as their byte identity; only the direct SHA receipts are used.

## RETURN_ANALYSIS

- Status: `LOCAL_E2_PASS / CONFIG_EXCLUDED / DYNAMIC_REQUIRED`.
- Last trusted boundary: complete supplied A/B/D images plus independent bit-exact golden equation.
- First divergence: none after the package's ordered execplan Write_Reg overlay.
- Intermediate nonterminal divergence: standalone loaded JSON A/B bases before Write_Reg.
- Numeric: 28/28 effective slices exact, 0 element mismatches, 0 byte mismatches.
- Formal D: not present; the package contains golden D only.
- RTL natural completion: not evaluated.
- E3/E4/E5: false/not claimed.

## BLOCKER_DELTA

- Closed at LOCAL_E2: effective A/B wrong-region concern; supplied golden correctness; 28-slice D completeness; config-length/repack consistency.
- Remains open: `B_HUMAN_REMOTE_ADD_RTL_NATURAL_TERMINAL_AND_BUFFER_LIFETIME_DYNAMIC`.
- Remains open for future rebuild only: `B_HUMAN_REMOTE_ADD_STRICT_SCHEMA_MUL_SHAPE_UNKNOWN_FIELD`.
- No server blocker was consumed because no server action was authorized.

## RULE_CONFIRMATION / RULE_DELTA_PROPOSAL

Existing semantic-ownership, materialized-roundtrip, causal-ledger, bank-row, and native-reference applicability rules were confirmed.

Proposed reusable rule (for mainline review only; public rules were not edited):

`CDA-CONFIG-EFFECTIVE-RUNTIME-OVERLAY-001`

> When a packaged execution performs `Load_Config` followed by ordered `Write_Reg` operations before `Start_Comp`, audit both the loaded config image and the effective pre-start register state. Resolve each Write_Reg physical resource through mapping evidence before classifying a JSON base/stride mismatch. A loaded-state mismatch that is deterministically neutralized before Start_Comp must be reported as an intermediate nonterminal divergence, not as the packaged execution's first divergence. Missing/ambiguous ordering or mapping fails closed.

Impact: native materialized configs, execplan analyzers, and human JSON audits that contain mapped logical stream keys plus physical register overlays.

## PACKAGE_RELEASE

`NONE` — no server package was requested or generated.

## Machine evidence

- Main report: `artifacts/human_remote_add_fp16_fp32_20260806_v1/config_bound_analysis/report.json`, 79452 bytes, SHA256 `9c097a33f7114b1178bab31d9af3bb9a68cc8cfc3f946a13ea8fd9292af3a4fc`.
- Deterministic repeat: same bytes/SHA.
- Strict shadow report: `artifacts/human_remote_add_fp16_fp32_20260806_v1/config_bound_analysis/operator_config_shadow_report.json`, 5805 bytes, SHA256 `1eee98d254c5f645f1332d87574e99126939561eea7275e6c300fbf2e3fa63fd`.
- Receipt: `artifacts/human_remote_add_fp16_fp32_20260806_v1/analysis_receipt.json`, 6595 bytes, SHA256 `85fe388357c720dc0a084db336fe757a655c044efbe3b63404f489b6e040a572`.
- Analyzer: `tools/analyze_human_remote_add_fp16_fp32_config_bound_v1.py`, 34819 bytes, SHA256 `b78f2d132208c1ee853730a38b9105e9eb9953810695159aab486a6ad760b65a`.

