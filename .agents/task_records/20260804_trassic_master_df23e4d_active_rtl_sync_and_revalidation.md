# Trassic master df23e4d active RTL sync and directed revalidation

Date: 2026-08-04

Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Scope

The user stated that hardware RTL had been updated and requested a brief
verification followed by resumption of hardware-blocked operator work.
This record covers only:

1. authenticated inspection of the latest private `Trassic2.0_RTL/master`;
2. exact synchronization of the upstream changed RTL member;
3. directed replay of the two already-proven exact-cancellation failures;
4. owner handoff for operator-local W3/E2/materialization work.

No local functional-RTL repair was invented.  No server upload, simulation,
lease, package run or rule edit was performed.

## Upstream identity and exact sync

- repository: `xlsjdjdk/Trassic2.0_RTL`
- branch: `master`
- previous commit:
  `d0aa87f682880a260fb792aaac88f70a23aba414`
- current commit:
  `df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727`
- commit message:
  `优化o_IntResult的赋值逻辑，简化代码并确保符号位正确处理`
- change scope: one file, `+2/-6`
- path:
  `code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_CSA.v`

Before synchronization, the active local member was exactly the authenticated
previous source:

- bytes=`2201`
- SHA256=`429a29a929a508f7562f9c78d4ab2cd4095961296d0e6f65e8419a4444a6145a`

After synchronization, active local, GitHub raw bytes and the frozen selected
source copy are byte-identical:

- bytes=`1951`
- SHA256=`72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3`

The live change removes the old split assignment of the lower 31 bits plus a
separately reconstructed sign bit.  It now assigns the full 32-bit
two's-complement result to `o_IntResult[31:0]`.

## Directed current-source replay

Focused Icarus compilation and VVP execution both exited zero.  The exact
historical failures now pass:

| family | frozen case | previous result | df23e4d result | expected |
|---|---|---:|---:|---:|
| Conv native four-lane | `hwop-0003-00`, `-5+5` | `0x80000000` | `0x00000000` | `0x00000000` |
| QLinearMatMul node0075 | `(m,n,k_group)=(0,65,3)`, `-19+19` | `0x80000000` | `0x00000000` | `0x00000000` |
| adjacent signed control | `-6+5` | `0xffffffff` | `0xffffffff` | `0xffffffff` |

Terminal marker: `RTL_REPAIR_DIRECTED_PASS`.

Testbench:

- `artifacts/rtl_sync/trassic_master_df23e4d_20260804/sa_exact_cancel_df23e4d_tb.sv`
- bytes=`2160`
- SHA256=`15ccc3a1bf78cccc4de1c388055987e817381cc941d8739864da62f117ac2fbb`

Compiled image:

- `artifacts/rtl_sync/trassic_master_df23e4d_20260804/sa_exact_cancel_df23e4d.vvp`
- bytes=`541569`
- SHA256=`14689375b4d8dfb4666102f687a4c3f44865ac8bea8f38a3ffc0ad26467e52b5`

Machine report:

- `artifacts/rtl_sync/trassic_master_df23e4d_20260804/report.json`
- bytes=`4732`
- SHA256=`6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5`

## Adjudication and handoff

The exact current-source arithmetic leaf is closed for the two frozen directed
cases.  This is sufficient to resume the blocked owners, but it is not E2/E4/E5
and does not claim the complete W3 domains.

- Conv native four-lane owner:
  `019fc783-1146-7901-9e40-64d0ed8e052d`
  must bind `df23e4d`, revalidate the required real-W3 reachability/current
  identity, then continue native-four-lane local E2 and package generation if
  the gate closes.
- QLinearMatMul node0075 owner:
  `019fc775-8de0-7f10-bc4a-026a4673776f`
  must rerun the full frozen recurrence/current-source witness, then continue
  handler/materializer/target/mapping/bitstream/execplan/SCA/E2 and package
  generation if the gate closes.  The user-approved minimum eight-pass legal A
  reread diagnostic bypass remains available after materialization.

Both owners must actively notify the mainline after return analysis and after
package completion, including rule confirmation or a non-synonymous rule delta.

## Claim boundary

Not claimed here: full 53-Conv W3 re-enumeration, full node0075 8,192,000
recurrence rerun, config-bound E2, mapping, bitstream, execplan, SCA, server VCS,
natural terminal, formal D, E4/E5 or performance.

`RULE_DELTA_PROPOSAL=NONE`; current identity/arithmetic fail-fast and
owner-completion notification rules remain sufficient.
