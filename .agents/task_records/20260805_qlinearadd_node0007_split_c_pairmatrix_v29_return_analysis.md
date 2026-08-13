# QLinearAdd node0007 split-C pair-matrix v29 return analysis

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- return bytes/SHA: `209242 / 3839a9985f18483db4a4a784dbc7169103b4168b2a8eb4d3d11df07a96cbe1ff`
- source bytes/SHA: `26171333 / c92985b32e31c30ffcb023a6b637a6b059748e5395e2eabac2a65e3ae79c0af3`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-pairmatrix-v29-return-analysis/report.json`
- machine report SHA: `6bfc521f1ec22b2e29ed7ec0679e52d5f9e1db91ea832ae998734bdef0b168c9`

The user-attested no-sidecar policy covers only external transport. ZIP CRC,
single-root/path safety, RETURN_MANIFEST exact-set/allowlist, all per-file
receipts, source package binding, package preflight and installed preflight
passed.

Execution reached all four split-C starts and completed A dequant, B dequant
and relocation. `op_fp32_add` then ran until the 8-hour timeout:

- compile/simulation/canonical exits: `0 / 124 / 0`
- signal: `NONE`; natural terminal: false
- formal D: `0/28`, missing `28`; mismatch is unevaluable
- E3/E4/E5: false
- actual production RTL commit/tree identity is not present in the return and
  remains unproven even though compile succeeded

The qualified v29 matrix uniquely locates the functional configuration
divergence:

- both MSE0 and MSE1 accepted requests/read data;
- each delivered and wrote one 16-byte block into Buffer0/2;
- both buffers became non-empty, but `buf2arm_rreq_ready=0`;
- Buffer0/2 ARM accepts, GA operand captures, GA pair/accept/output all stayed
  zero for 134,217,728 qualified stall cycles.

The final FP32 config supplies one `[0,16)` input window while Buffer0/2 masks
request all eight physical banks. Active RTL requires every masked bank to have
all four byte-valid bits, i.e. a complete 32-byte row. The native FP32 add
crosscheck instead uses a 32-byte transaction and two Buffer_AG windows
`[0,16)+[16,32)` for A, B and D.

Adjudication:

- `LAST_PROVEN_GOOD=FP32_ADD_MSE0_MSE1_16B_BUFFER_WRITE_ACCEPTED`
- `FIRST_DIVERGENCE=FP32_ADD_BUFFER0_BUFFER2_ARM_READ_ACCEPT_REMAINS_ZERO`
- `HANG_ROOT_CAUSE=UNIQUE_CONFIG_INPUT_BUFFER_TRANSACTION_SUPPLY_MISMATCH_16B_PRODUCED_VS_32B_MASKED_ROW_REQUIRED`

The fresh correction must use 32-byte stream transactions and paired 16-byte
Buffer_AG columns, while halving the inner LC occurrence from 18816 to 9408 so
`8*9408*32=2408448` bytes and the frozen address/order coverage remain exact.
No numeric/W3/qparam/tail/workload/golden analysis was repeated.

Rule feedback is a non-synonymous proposal:
`CDA-QADD-A-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`, extending the existing
write-side conservation principle to read-side Buffer0/2 transaction/window/
mask coverage. Mainline owns publication.
