from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v66_pe1_pair_successor_v67 as previous  # noqa: E402

SOURCE = "r5_n4_hw_v67_pe1_pair_diag"
INSTALL = "r5_n4_hw_v68_pe7_pair_diag"
SOURCE_SHA = "be8fb8fd8cda13282cc1d740a837325ce811f7c1ad52d7efd096d71d56c0e83e"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v67_return_analysis/report.json"
MAPPING = ROOT / "artifacts/operator_config_validation/r5-node0004-pe1-keep-last-index-fix-c0-v62/mapping/conv/op_w0/mapping_cache/72d2720125714878.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v67_return_v68_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"replacement count differs: {old[:100]!r} count={text.count(old)}")
    return text.replace(old, new, 1)


def configure() -> None:
    previous.SOURCE = SOURCE
    previous.INSTALL = INSTALL
    previous.SOURCE_SHA = SOURCE_SHA
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    previous.configure()


def retarget_observer(observer: str) -> str:
    begin = "    // v67 PE1_PAIR_ACTUAL_CONSUMER_BEGIN"
    end = "    // v67 PE1_PAIR_ACTUAL_CONSUMER_END"
    if observer.count(begin) != 1 or observer.count(end) != 1:
        raise BuildError("v67 PE1 block markers differ")
    lo = observer.index(begin)
    hi = observer.index(end, lo) + len(end)
    block = observer[lo:hi]
    block = block.replace("v67 PE1_PAIR", "v68 PE7_PAIR")
    block = block.replace("PE1_PAIR", "PE7_PAIR")
    block = block.replace("PE1 pair", "PE7 pair")
    block = block.replace("PE1 match", "PE7 match")
    block = block.replace("pe1_pair", "pe7_pair")
    block = block.replace("p1_", "p7_")
    block = block.replace("return_obs_p1", "return_obs_p7")
    block = block.replace("IGA_PE[1]", "IGA_PE[7]")
    block = block.replace("iga_pe_outport[1]", "iga_pe_outport[7]")
    block = block.replace("iga_pe_outport_bp_post[1]", "iga_pe_outport_bp_post[7]")
    block = block.replace("iga_lc_outport[9]", "iga_lc_outport[18]")
    block = block.replace("iga_lc_outport_bp_post[9]", "iga_lc_outport_bp_post[18]")
    block = block.replace("lc9", "lc18")
    block = block.replace("LC15/LC9", "logical LC15/LC9 mapped to physical LC17/LC18")

    old_fmt = "mse1_tag=%h mse1_bp=%0d lc15_port=%h"
    new_fmt = ("mse1_tag=%h mse1_bp=%0d pe_mode=%h pe_keep=%h pe_enable=%h "
               "pe_clear=%h bp_mask=%h buffer_last=%0d buffer_index=%h lc15_port=%h")
    block = once(block, old_fmt, new_fmt)
    mse_bp_arg = """                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_bp_pre[1],
"""
    pe = "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[7].u_IGA_PE"
    extra = mse_bp_arg + """                %s.iga_pe_inport_mode,
                %s.iga_pe_keep_last_index,
                %s.u_IGA_PE_Inbuffer.iga_pe_inbuffer_enbale,
                %s.u_IGA_PE_Inbuffer.iga_pe_inbuffer_clear,
                %s.u_IGA_PE_Inbuffer.iga_pe_inbuffer_bp_post_mask,
                %s.u_IGA_PE_Inbuffer.iga_pe_buffer_inport_last_bit,
                %s.u_IGA_PE_Inbuffer.iga_pe_buffer_inport_last_index,
""" % ((pe,) * 7)
    block = once(block, mse_bp_arg, extra)
    observer = observer[:lo] + block + observer[hi:]
    observer = once(observer, 'return_obs_write_pe1_pair("DIAG_DECISION")',
                    'return_obs_write_pe7_pair("DIAG_DECISION")')
    return observer


def build_directory(output: Path) -> Path:
    configure()
    with tempfile.TemporaryDirectory(prefix="node0004-v68-source-") as td:
        source = base.extract_source(Path(td))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)

    op = package / "tb_probe/native_return_observer.svh"
    observer = retarget_observer(op.read_text(encoding="utf-8"))
    op.write_text(observer, encoding="utf-8", newline="\n")

    rp = package / "PREPARE_AND_RUN.sh"
    runner = rp.read_text(encoding="utf-8")
    if runner.count(" +RETURN_OBS_PE1_PAIR +RETURN_OBS_PE1_PAIR_LIMIT=128") != 2:
        raise BuildError("v67 PE1 runner binding count differs")
    runner = runner.replace("+RETURN_OBS_PE1_PAIR_LIMIT=128", "+RETURN_OBS_PE7_PAIR_LIMIT=128")
    runner = runner.replace("+RETURN_OBS_PE1_PAIR", "+RETURN_OBS_PE7_PAIR")
    rp.write_text(runner, encoding="utf-8", newline="\n")

    runtime_path = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime = runtime_path.read_text(encoding="utf-8")
    runtime = runtime.replace("RETURN_OBS_PE1_PAIR_LIMIT", "RETURN_OBS_PE7_PAIR_LIMIT")
    runtime = runtime.replace("RETURN_OBS_PE1_PAIR", "RETURN_OBS_PE7_PAIR")
    runtime_path.write_text(runtime, encoding="utf-8", newline="\n")

    manifest_path = package / "package_manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_sha, new_sha = old["observer_sha256"], base.sha256(op)
    manifest = base.replace_hash(old, old_sha, new_sha)
    feature = manifest.setdefault("diagnostic_features", {}).pop("RETURN_OBS_PE1_PAIR")
    feature.update({
        "runtime_enable_parameter": "+RETURN_OBS_PE7_PAIR",
        "limit_parameter": "+RETURN_OBS_PE7_PAIR_LIMIT=128",
        "edge_schema": "PE7_PAIR_V1", "boundary_schema": "PE7_PAIR_V1",
        "logical_to_physical_binding": {
            "logical_PE1": "physical_PE7", "logical_LC15": "physical_LC17",
            "logical_LC9": "physical_LC18", "mapping_sha256": base.sha256(MAPPING),
        },
    })
    manifest["diagnostic_features"]["RETURN_OBS_PE7_PAIR"] = feature
    manifest.update({
        "install_name": INSTALL, "source_package_sha256": SOURCE_SHA,
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "observer_sha256": new_sha, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False, "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False, "configuration_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False, "mapping_rebuilt": False,
        "bitstream_rebuilt": False, "execplan_rebuilt": False,
        "sca_semantics_rebuilt": False, "functional_rtl_modified": False,
        "server_action": False,
    })
    base.write_json(package / "provenance/v67_to_v68_pe7_pair.json", {
        "schema": "node0004-v67-to-v68-pe7-pair-v1",
        "source_v67_sha256": SOURCE_SHA,
        "v67_return_sha256": "1ac57340c9c37adae664be47d21364a9011a229ee440509a610238c087257c9b",
        "analysis_sha256": base.sha256(ANALYSIS), "mapping_sha256": base.sha256(MAPPING),
        "package_local_bug_fixed": "v67 observed physical PE1 and physical LC9; logical PE1/LC9 map to physical PE7/LC18",
        "changed_surface": ["fresh identity", "PE1_PAIR feature retargeted and renamed PE7_PAIR",
                            "physical PE7 inbuffer mode/keep/enable/clear/bp-mask boundary"],
        "candidate_observation_matrix": {
            "input0_held_token_cleared_or_blocked": "physical PE7 buffered valid/clear/bp-mask/mode/keep",
            "input2_next_epoch_not_captured": "physical LC18 raw versus input2 enable/buffered valid",
            "both_buffered_not_matched": "buffer valid,last,index/matched/tag",
            "post_match_output_missing": "ALU/outbuffer/PE7 output/MSE4 input1 same-clock ledger",
        },
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure",
                   "functional RTL/ISA/hardware/active ndp-sim"],
    })
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    a = ap.parse_args()
    out = a.output_root.resolve(); out.mkdir(parents=True, exist_ok=True)
    package = build_directory(out)
    archive = out / f"{INSTALL}.zip"; base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v68-repeat-") as td:
        repeat = build_directory(Path(td)); rz = Path(td) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, rz); deterministic = base.sha256(rz) == digest
    if not deterministic: raise BuildError("deterministic rebuild differs")
    sidecar = out / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "node0004-v67-to-v68-pe7-pair-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(archive), "zip_bytes": archive.stat().st_size, "zip_sha256": digest,
        "sidecar": str(sidecar), "deterministic_rebuild_equal": deterministic,
        "source_v67_sha256": SOURCE_SHA, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False, "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False, "functional_rtl_modified": False, "server_action": False,
    }
    base.write_json(out / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
