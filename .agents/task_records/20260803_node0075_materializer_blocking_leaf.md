# node0075 materializer first blocking leaf

## Provenance

- date: `2026-08-03`
- independent operator family: `QLinearMatMul`
- node: `node-0075`
- owner thread: `019fc775-8de0-7f10-bc4a-026a4673776f`
- sole mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- startup plan SHA256:
  `6b82860af88b991cb4401fa2f3b36bbda5a2d04ff2e247addb4a5daeaf3375b8`
- ndp-sim HEAD:
  `ec12424516ae0304228dd2321d4e604fe225e04e`

No pre-existing post-split node0075 handler, registry, materializer, mapping,
bitstream, execplan, SCA, E2, or package asset was found.  The existing
node0071-to-node0075 identity-alias integration was consumed read-only.

Startup read receipts, all recomputed from current disk:

- `.agents/agent.md`:
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- `.agents/plan.md`:
  `6b82860af88b991cb4401fa2f3b36bbda5a2d04ff2e247addb4a5daeaf3375b8`
- `.agents/rules/生成前必读索引.md`:
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- `.agents/rules/算子配置规则.md`:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/服务器测试包生成规则.md`:
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- `.agents/rules/INT8_SA点积专项规则.md`:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- identity-alias integration contract:
  `73d831d075317c4bf05aa4ca2f8c541835884f6fa9124fbd9dd5199f591cb0e1`
- identity-alias integration task record:
  `7a727936c9994655b06219cb5092d8b9dc7276a3aa755f16ccccd0643282b12c`
- materializer authorization:
  `36be8174ec9afcb7430761812def6bcd5c78756197cf1fd9b6f449bf4d6077c7`
- repeated-read authorization:
  `be56cf012296f7efc37c76dd522adb2194c6dae467137bf6ceb1778db439b58c`
- operator-family owner split:
  `f786df93feee00c66bffa4096de7e7c550c001cdcd2c3d6d5bcfe11a7121c5a6`

## Decision

Status:
`TERMINATED_AT_FIRST_NONEXPRESSIBLE_HARDWARE_LEAF`.

The current active RTL source
`NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v`
has SHA256
`c6018e762411e14346bfec672b273b826f893b11c5de0cfb38fca674f9d33c4b`.
Its final ANSI port declaration at line 50 is:

```verilog
output[1:0] o_Config,
```

The focused current-disk SystemVerilog-2012 Icarus probe exits 1 with
`Superfluous comma in port declaration list`.  This is the already-synced
Trassic2 master b7acbe5 identity, not an unexplained local edit.  The defect
is a common active-RTL compile stop and cannot be expressed or repaired by
node0075-owned JSON, handler, mapper, or other non-RTL assets.  Functional RTL
mutation is outside this owner's authority.

The minimum next action belongs to the RTL owner: remove only the comma after
the final `o_Config` port and run the full current VCS NDP top filelist
compile/elaboration.  No assumed-fixed-hardware authorization exists for this
independent node0075 owner.

Therefore no target JSON or registered handler was emitted after this
fail-closed stop.  Mapping, bitstream, execplan/SCA and config-bound E2 were
not generated or claimed.  `PACKAGE_RELEASE=NONE`; no server package, upload,
run, or lease occurred.

## A reload accounting

The authorized capacity lower bound remains:

`ceil(N/(A_lifetime*output_columns_per_use)) = ceil(1000/(16*8)) = 8`.

Actual materialization is deliberately reported separately:

| Receipt | Actual |
|---|---:|
| materialized A reload passes | 0 |
| accepted 32-byte A read occurrences | 0 |
| accepted A traffic | 0 bytes |
| unique consumer-accepted bytes | 0 bytes |
| frozen producer-owned unique storage | 32,768 bytes |

If the hardware leaf is removed and exactly eight passes remain sufficient,
the authorized counterfactual is 512 reads per slice, 8,192 total reads,
262,144 accepted traffic bytes, and 32,768 unique storage bytes.  Those
numbers are not current acceptance receipts.  Producer bases were not
reported as consumer reads.

## Frozen W3 instance observation

The frozen node0075 accumulator
`tensor-internal-node-0075-accumulate.npy` has SHA256
`ee8422fe7c20f0cc40adb18abcd0b8b0f9c433a6c2283e8c87262e3a7d419ec3`.
It is INT32 `[16,1000]`, contains 16,000 elements and 993 unique values, spans
`[-44906,121219]`, and has 8,544 negative, zero zero-valued, and 7,456
positive elements.  All 16 rows contain a negative value.

For these frozen values only:

- current GA INT32-to-FP32 model mismatch count: 0;
- sequential `0x3a510db3`, zp=60 tail versus frozen D: 0 mismatches;
- one-round fused model versus frozen D: 0 mismatches;
- fused versus sequential result: 0 mismatches.

Frozen D SHA256 is
`10d974cdab69904bfd3ed7749059e26e16388ba784872f0d432cd2ba14bcbdc8`.
It is UINT8 `[16,1000]` with range `[24,157]`.

This is instance-only avoidance evidence.  It does not prove the full legal
signed INT32 domain and does not close the generic exact-UINT8-tail blocker.

## Blocker delta and rule feedback

- NEW first node0075 leaf:
  `SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA`;
- RETAIN OPEN:
  `SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION`;
- RETAIN OPEN general domain:
  `B_QUANT_TAIL_SIGNED_INT32_INGRESS`;
- NOT REACHED:
  `B_REQUANT_MATMUL_2D_LAYOUT`;
- NOT EMITTED:
  `NODE0075_HANDLER_MATERIALIZER_ENDPOINT`;
- CLOSED: none.

`RULE_CONFIRMATION`: keep the INT8-SA and exact-UINT8-tail general-domain
gates open.  Frozen W3 avoidance is useful instance evidence but is not a
production or family-domain proof.  `RULE_DELTA_PROPOSAL=NONE`.

## Artifacts

- machine contract:
  `contracts/operator_config/node0075_materializer_blocking_leaf_v1.json`
  SHA256
  `f17cf7fc84c6cee591e3afbfd0fc01276f58f0fff40e32a628ca5d0696224111`
- validation report:
  `artifacts/operator_config_validation/r5-node0075-materializer-blocking-leaf-v1/report.json`
  SHA256
  `8f656e6c44588fb344085dee220238db8339c9aacacf1f0d0e09ae4e6d7cb8b5`
- evidence module:
  `resnet50_pipeline/node0075_materializer_blocking_leaf.py`
  SHA256
  `6c3fcdcc069c47427665415be77f82c2601c2351b5d7f232dde01d9a84ac3cb5`
- validator:
  `tools/validate_node0075_materializer_blocking_leaf.py`
  SHA256
  `74fd8f2794c1924881c21c451d9b3e0acc9b7249919ceb0f9e23c87168c0b270`
- tests:
  `tests/test_node0075_materializer_blocking_leaf.py`
  SHA256
  `b6299a973bd7c83b63df4df91909dccac643319ccd6607194757c2e0e4b1066c`

Validation:

```text
python tools/validate_node0075_materializer_blocking_leaf.py
status=PASS_FAIL_CLOSED
first_blocking_leaf=SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA
actual_materialized_passes=0
actual_accepted_traffic_bytes=0
package_release=NONE

python -m unittest tests.test_node0075_materializer_blocking_leaf -v
Ran 3 tests
OK
```
