# QLinearAdd node0007 D-buffer v16 return

- Return ZIP SHA256:
  `edd282954b96340293dfcec78428d9c4b97932eddd218707251040a7e0835b50`.
  The user-attested no-sidecar transport policy was applied; internal CRC, safe root,
  RETURN_MANIFEST exact-set and member receipts all passed.
- Source v16 ZIP/manifest binding, package/install preflight and compile passed.
- The simulation was manually interrupted after 4241.413 s of simulation wall time.
  From slice start to INT it advanced 261501.9 cycles, only 642.1 cycles short of the
  first 262144-cycle heartbeat.
- Before the finite deep trace capped, qualified progress was real:
  64 MSE0→Buffer0 records, 64 read consumes, 64 GA inputs, 64 GA outputs, and 64 accepted
  MSE4 request/write-data transactions on each channel.
- Therefore the returned fallback canonical
  `PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE/FIRST_REQUEST_CHAIN_RETURN_BINDING` is not an
  execution root-cause decision. The correct adjudication is
  `MANUAL_INTERRUPT_BEFORE_FIRST_HEARTBEAT_WITH_QUALIFIED_PROGRESS`.
- No natural terminal occurred and all 28 formal D files are missing; E3/E4/E5 remain
  false. This return does not prove a new configuration/RTL hang root cause.
- A later user decision authorized a backend-only cadence successor because the
  returned log volume was small and the 262144-cycle heartbeat was too sparse for the
  measured simulation speed. The exact last qualified output-side activity was
  `MSE4 req/wdata ch0/ch1=64/64` at 16128787000 ps; the last qualified input-side
  activity was `MSE0_TO_BUFFER0 n=64` at 16129301000 ps. The last textual observer
  line was a non-handshake `DEEP_MSE4_INDEX n=64` state record at 16129338000 ps.
- Fresh successor `r5_qadd_n7_backend_progress_v17.zip` changes only the package
  identity and backend heartbeat cadence from 262144 to 32768 active cycles. It does
  not add frontend per-transaction logging or change timeout, configuration, workload,
  golden data or RTL. Its final-ZIP rule self-audit passed with errors=0, the real
  runner reached the safe compile stub, and all four cadence/rate-gate negative
  controls failed closed.

Machine report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-dbuf-v16-return-analysis/report.json`.
