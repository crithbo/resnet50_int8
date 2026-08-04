# Trassic2 master 1c49bd1 SA independent audit

## Scope and receipt

- Unique mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- New snapshot identity supplied by user: GitHub master `1c49bd1155a89ff187e29016dc4415e59a55f991`
- New read-only snapshot: `Trassic2.0_RTL_master_1c49bd1_audit/Trassic2.0_RTL-master/code/NDP_rtl`
- Comparison snapshot: `Trassic2.0_RTL/code/NDP_rtl`
- Comparison identity: `5f2f8d3a2358c090143caa35957c07ff3650ff4c`
- Audited set: the ten byte-different files under `Slice/Specialized_Array/SA_PE`.
- Neither extracted snapshot contains nested Git metadata. The machine report records old/new SHA-256 for every audited leaf; the outer workspace Git identity was not used as snapshot proof.

## RETURN_ANALYSIS

The exact `1c49bd1` snapshot does not compile because the final ANSI port in `SA_PE_Float_Control.v:50` retains a trailing comma before `);` at line 51. This independently reproduces the server VCS first divergence.

After removing only that comma in an `outputs` diagnostic copy, both `SA_ALU` and the 16-lane `SA_PE_ALU` elaborate. The restored `slice_rst` caller/callee interface is internally consistent. The updated 18-bit INT8 CSA/carry path passes positive/negative extrema and 20,000 deterministic pseudo-random signed-u8 dot4 plus int32-psum cases.

A second deterministic full-domain arithmetic defect exists in `SA_PE_Float_CSA.v:49-50`. The split result reconstruction negates only bits 30:0 and preserves the raw bit 31. Two directed boundaries fail:

- `C=-5`, dot `+5`: RTL `0x80000000`, expected `0x00000000`.
- `C=INT32_MIN`, dot `0`: RTL `0x00000000`, expected `0x80000000`.

The internal encoding is corrected by reconstructing the full word:

```verilog
assign o_IntResult = i_SignC
    ? (~(c_Result0_wire ^ 32'h80000000) + 32'd1)
    : c_Result0_wire;
```

That diagnostic-only fix passes all 11 directed cases and 20,000 deterministic random cases.

## Hardware-group findings

### SA-1C49-COMPILE-001 — deterministic compile blocker

- GitHub path: `code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v`
- Lines: 50-51
- Problem code: `output[1:0] o_Config,` followed by `);`
- Why wrong: an ANSI port list cannot retain a comma before the closing parenthesis. Icarus reports `Superfluous comma in port declaration list`; VCS stopped at the closing token.
- ResNet impact: compilation stops before any operator simulation.
- Minimal fix: remove the one comma.
- Validation: compile the untouched source and observe the exact failure; then elaborate `SA_ALU` and `SA_PE_ALU` after the one-character diagnostic fix.

### SA-1C49-INT32-SIGN-BOUNDARY-001 — deterministic arithmetic defect

- GitHub path: `code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_CSA.v`
- Lines: 49-50
- Related encoding: `SA_PE_Float_Control.v:185-190`
- Problem code: lower 31 bits are conditionally negated, while bit 31 is copied from the pre-negation raw result.
- Why wrong: the negative-psum path encodes a bit-31 bias. Split reconstruction loses the modulo-2^32 boundary distinction, mapping exact cancellation to `INT32_MIN` and `INT32_MIN+0` to zero.
- ResNet impact: full-domain INT32 accumulation is incorrect for those occurrences. This audit does not claim that a current ResNet50 tensor was observed to hit the boundary.
- Minimal fix: use the single full-width expression shown above.
- Validation: the two boundary cases, ordinary negative/cross-zero cases, INT32_MIN plus/minus one, four-lane extrema, then the 20,000-case deterministic test.

### SA-1C49-RESET-DATAPATH-RISK-001 — local risk, not an accepted-output proof

- GitHub path: `code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v`
- Lines: control reset at 184-209; unreset data register block at 210-236.
- Problem code: `rst_n/slice_rst` clear only the control registers; the data registers have `always @(posedge clk)` and can still capture on `i_Stall` during `slice_rst`.
- Local evidence: global reset exposes `xxxxxxxx`; a seeded `9` remains `9` through slice reset; `slice_rst+i_Stall` captures `31`, which remains `31` afterward.
- ResNet impact: not established. `SA_ALU` has no local result-valid, so enclosing valid/tag logic may mask all X/stale values. This is not a declared ResNet blocker.
- Minimal next check: prove the enclosing accepted-valid/tag equation suppresses reset cycles and the first invalid post-reset cycle. Only if the contract requires a flushed data path should reset be added to these registers.

## Ten-file disposition

- `SA_PE_ALU.sv`: formatting/alignment only; 16-lane elaboration passes after the unrelated syntax fix.
- `SA_ALU.v`: new sign/reset wiring is port-consistent.
- `SA_PE_Float_Control.v`: compile blocker; participates in negative-psum encoding.
- `SA_PE_Float_CSA.v`: full-domain boundary defect.
- `SA_PE_Mul_Array.v`: 18-bit arithmetic passes tested coverage; reset asymmetry remains a local integration risk.
- `SA_PE_Float_Expadj.v`, `SA_PE_Float_Expdiff.v`, `SA_PE_Float_Last.v`, `SA_PE_Float_LZA.v`, `SA_PE_Float_SHT.v`: refactor/comment/format-only changes; no changed semantic defect identified.

## Diagnostic artifacts and boundary

- Machine report: `outputs/rtl_audit/trassic2_master_1c49bd1_sa_review/sa_independent_audit.json`
- Minimal arithmetic TB: `outputs/rtl_audit/trassic2_master_1c49bd1_sa_review/int8_sa_directed_tb.sv`
- Random arithmetic TB: `outputs/rtl_audit/trassic2_master_1c49bd1_sa_review/int8_sa_random_tb.sv`
- Reset probe TB: `outputs/rtl_audit/trassic2_master_1c49bd1_sa_review/int8_sa_reset_probe_tb.sv`
- Diagnostic source copy: `outputs/rtl_audit/trassic2_master_1c49bd1_sa_review/src`

Only the diagnostic copy contains the syntax and arithmetic trial fixes. No source snapshot, active RTL, plan, or public rule was modified. No server inspection, upload, run, lease, or package generation occurred.

## BLOCKER_DELTA

- Confirmed blocker: exact `1c49bd1` source cannot compile until `SA_PE_Float_Control.v:50` loses its trailing comma.
- Newly confirmed correctness blocker: `SA_PE_Float_CSA.v:49-50` fails two modulo-2^32 boundary classes.
- Closed concern: no counterexample was found for the revised 18-bit CSA/carry transport in directed extrema or 20,000 deterministic random vectors.
- Risk only: unreset datapath creates locally visible X/stale/ghost values, but accepted-output propagation is not proven.

## RULE_DELTA_PROPOSAL

None. These are RTL implementation findings, not a configuration-rule delta.

## PACKAGE_RELEASE

`NO_PACKAGE`: no package was generated or modified.
