from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records


PKG_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_qadd_n7_split_c_fp32_prefix_v26"
TARGET_NAME = "r5_qadd_n7_split_c_ingress_v28"
SOURCE = PKG_ROOT / SOURCE_NAME
TARGET = PKG_ROOT / TARGET_NAME
ZIP = PKG_ROOT / f"{TARGET_NAME}.zip"
SOURCE_SHA = "e4c16585707b37170d04311f91c038c37b3c95330ffceed17a23687d913f5d50"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"preimage count differs: {old!r}: {text.count(old)}")
    return text.replace(old, new)


def materialize(dst: Path) -> Path:
    out = dst / TARGET_NAME
    shutil.copytree(SOURCE, out)

    for relative in ("workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"):
        sca_path = out / relative
        sca_text = sca_path.read_text(encoding="utf-8")
        if SOURCE_NAME not in sca_text:
            raise ValueError(f"old namespace absent from {relative}")
        sca_path.write_text(
            sca_text.replace(SOURCE_NAME, TARGET_NAME),
            encoding="utf-8",
            newline="\n",
        )

    native = out / "tb_probe/native_return_observer.svh"
    native_text = native.read_text(encoding="utf-8")
    native_text += '\n`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"\n'
    native.write_text(native_text, encoding="utf-8", newline="\n")
    for name in (
        "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh",
        "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
    ):
        shutil.copy2(ROOT / "tools" / name, out / "tb_probe" / name)
    shutil.copy2(
        ROOT / "tools/qlinearadd_node0007_fp32_ingress_canonical_v19.py",
        out / "package_tools/qlinearadd_node0007_fp32_ingress_canonical_v19.py",
    )

    runner = out / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    text = text.replace(SOURCE_NAME, TARGET_NAME)
    text = replace_once(
        text,
        'qlinearadd_node0007_split_canonical_v25.py"',
        'qlinearadd_node0007_fp32_ingress_canonical_v19.py"',
    )
    text = replace_once(
        text,
        "  feature_argv=false",
        "  feature_argv=false",
    )
    text = replace_once(
        text,
        "if [ -s \"$evidence_root/actual_simulator_argv.txt\" ] && grep -q '+RETURN_OBS_DEEP' \"$evidence_root/actual_simulator_argv.txt\"; then feature_argv=true; fi",
        "if [ -s \"$evidence_root/actual_simulator_argv.txt\" ] && grep -q '+RETURN_OBS_DEEP' \"$evidence_root/actual_simulator_argv.txt\" && grep -q '+QADD_FP32_INGRESS_OBSERVER' \"$evidence_root/actual_simulator_argv.txt\"; then feature_argv=true; fi",
    )
    text = replace_once(
        text,
        "if [ -s \"$run_root/sim_results/sim.log\" ] && grep -q '\\[RETURN_OBSERVER\\] enabled for slice' \"$run_root/sim_results/sim.log\"; then feature_time0=true; fi",
        "if [ -s \"$run_root/sim_results/sim.log\" ] && grep -q 'QADD_FP32_INGRESS_OBSERVER_V19_TIME0' \"$run_root/sim_results/sim.log\"; then feature_time0=true; fi",
    )
    text = replace_once(
        text,
        "if [ -s \"$observer_log\" ] && grep -q '# Native NDP return observer v4' \"$observer_log\"; then feature_snapshot=true; fi",
        "if [ -s \"$observer_log\" ] && grep -q '# QADD_FP32_INGRESS_OBSERVER_V19 ' \"$observer_log\"; then feature_snapshot=true; fi",
    )
    text = text.replace("feature=QADD_SPLIT_C", "feature=QADD_SPLIT_C_FP32_INGRESS")
    text = replace_once(
        text,
        "  +RETURN_OBS_HEARTBEAT_CYCLES=16384",
        "  +RETURN_OBS_HEARTBEAT_CYCLES=1048576\n  +QADD_FP32_INGRESS_OBSERVER",
    )
    runner.write_text(text, encoding="utf-8", newline="\n")

    progress = out / "diagnostics/progress_contract.json"
    contract = json.loads(progress.read_text(encoding="utf-8"))
    contract.update(
        {
        "schema": "qlinearadd-node0007-split-c-ingress-progress-v28",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "heartbeat_cycles": 1048576,
            "feature_plusarg": "+RETURN_OBSERVER +RETURN_OBS_DEEP +QADD_FP32_INGRESS_OBSERVER",
            "minimum_monotonic_windows": 3,
            "diagnostic_boundary": "OP_RELOCATION_PAD_COMP_FINISH_TO_OP_FP32_ADD_FIRST_GA_INPUT_ACCEPT",
            "qualified_internal_counters": [
                "mse0_mse1_req_accept",
                "mse0_mse1_rdata_accept",
                "mse0_mse1_to_buffer_accept",
                "buffer0_buffer2_write_accept",
                "buffer0_buffer2_arm_read_accept",
                "buffer0_buffer2_array_delivery",
                "ga_operand0_operand1_capture",
                "ga_pair_accept_first_output",
            ],
        }
    )
    progress.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    readme = out / "README.md"
    rtext = readme.read_text(encoding="utf-8").replace(SOURCE_NAME, TARGET_NAME)
    rtext += (
        "\nThis is a narrow split-C FP32-ingress diagnostic successor. "
        "It does not claim split-C completion or full-chain numeric correctness.\n"
    )
    readme.write_text(rtext, encoding="utf-8", newline="\n")

    manifest_path = out / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET_NAME
    manifest["claim"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_split_c_ingress_v28_server_package.py"
    )
    manifest["source_assets"]["split_c_v26_source_zip"] = {
        "path": f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE_NAME}.zip",
        "sha256": SOURCE_SHA,
        "immutable": True,
    }
    manifest["observer_contract"].update(
        {
            "runtime_plusargs": [
                "+RETURN_OBSERVER",
                "+RETURN_OBS_DEEP",
                "+QADD_FP32_INGRESS_OBSERVER",
            ],
            "time0_marker": "QADD_FP32_INGRESS_OBSERVER_V19_TIME0",
            "return_target": "runs/return_observer.log",
            "qualified_counter_clock": "clk_sg",
            "snapshot_clock": "clk_db",
            "level_is_progress": False,
            "diagnostic_scope": "MSE0+MSE1 req/rdata through Buffer0+2 and dual GA ingress",
        }
    )
    manifest["split_segment_contract"]["claim_boundary"] = (
        "split-C diagnostic only through first qualified FP32 GA output"
    )
    manifest["final_zip_rule_self_audit"] = {
        "required": True,
        "status": "PENDING_POST_BUILD_DIRECT_FINAL_ZIP_AUDIT",
    }
    manifest["files"] = file_records(out, exclude_manifest=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return out


def main() -> int:
    if sha(PKG_ROOT / f"{SOURCE_NAME}.zip") != SOURCE_SHA:
        raise ValueError("frozen split-C source ZIP identity differs")
    if TARGET.exists() or ZIP.exists():
        raise ValueError("fresh v27 identity already exists")
    with tempfile.TemporaryDirectory(prefix="qadd-c-v28-a-") as a, tempfile.TemporaryDirectory(prefix="qadd-c-v28-b-") as b:
        pa = materialize(Path(a))
        pb = materialize(Path(b))
        za = Path(a) / f"{TARGET_NAME}.zip"
        zb = Path(b) / f"{TARGET_NAME}.zip"
        deterministic_zip(pa, za)
        deterministic_zip(pb, zb)
        if sha(za) != sha(zb):
            raise ValueError("deterministic double build differs")
        shutil.copytree(pa, TARGET)
        shutil.copy2(za, ZIP)
    sidecar = ZIP.with_suffix(".zip.sha256")
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    print(json.dumps({"zip": str(ZIP), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP), "sidecar_sha256": sha(sidecar)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
