# QLinearAdd node0007 v2 return analysis

- status: `FORMAL_RECEIPT_REJECTED_AND_SERVER_COMPILE_FAILED`
- numeric_analysis_repeated: `false`
- dynamic_readback_started: `false`
- new_package_generated: `false`
- source package SHA256:
  `60534faad0894a8b6507687159d43c824dd968f6c6a3386fa7877fc2007bf0bc`
- return ZIP SHA256:
  `cb0055af3866c3a7f8ee26d38836edc96f618faa075857ac2847b55948226f43`
- machine report SHA256:
  `d6f7d871474623a29155f428b48d782858a7237a094100da03f2177593a7896d`

The local `(1)` suffix was ignored for package identity. The ZIP-internal
`install_name` is `r5_qadd_n7_relocated_v2`, and its embedded package manifest
matches both the source ZIP manifest and local package manifest at SHA256
`617dff140f9553bad601fce368dd3981fab5d56662a7a66f49d0831a46b410de`.

The directly corresponding adjacent sidecar
`r5_qadd_n7_relocated_v2_return(1).zip.sha256` is absent. Formal receipt
acceptance therefore fails closed even though the ZIP itself has clean CRC,
safe paths, exact allowlist membership and valid returned-file hashes.

Package and installed preflights both passed, including zero pre-simulation
formal D targets. Compilation then exited 2. The compile log reports:

- `Error-[SFCOR] Source file cannot be opened`
- `native_return_observer.svh` is absent
- the include originates from `tb_NDP_Top_new_phy.sv:5854`

Simulation remained at sentinel exit 125, natural completion is false,
observed readbacks are 0/28 and missing readbacks are 28. The reported
zero mismatch-byte count is not numerically evaluable because simulation never
started.

The execution first divergence is classified
`SERVER_TB_REQUIRED_INCLUDE_MISSING / SERVER_RTL_TB_ENVIRONMENT`. The QAdd
package and installed payload were already accepted before the target server
TB failed to resolve its own include. No package-side config, bitstream,
execplan, SCA or golden change is justified, so the existing package remains
unchanged and no successor package is generated.
