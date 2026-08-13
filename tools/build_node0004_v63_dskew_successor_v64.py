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

import tools.build_node0004_v61_pekeep_fix_successor_v62 as base  # noqa: E402


SOURCE = "r5_n4_hw_v63_runnerdiag"
INSTALL = "r5_n4_hw_v64_dskew_diag"
SOURCE_SHA = "99f50faeed69d89cff3211121661b5331a9e98d8135064b41b76203f7c277712"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
ANALYSIS = ROOT / "outputs/conv_node0004_v63_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v63_return_v64_successor/build"


class BuildError(RuntimeError):
    pass


def configure_base() -> None:
    base.SOURCE = SOURCE
    base.INSTALL = INSTALL
    base.SOURCE_SHA = SOURCE_SHA
    base.SOURCE_ZIP = SOURCE_ZIP
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise BuildError(f"replacement count {count} for {old!r}")
    return text.replace(old, new)


DSKEW_BLOCK = r'''

    // v64: time-aligned qualified transaction ledger for the first
    // prepared-data versus descriptor skew. Existing observer counters are
    // sampled on clk_db negedge, after their qualified posedge updates.
    bit return_obs_ds_enabled;
    integer return_obs_ds_limit;
    integer return_obs_ds_plusarg_status;
    integer return_obs_ds_records;
    longint unsigned return_obs_ds_prev_desc;
    longint unsigned return_obs_ds_prev_prepared;
    longint unsigned return_obs_ds_prev_match;
    longint unsigned return_obs_ds_prev_source_push;
    longint unsigned return_obs_ds_prev_source_pop;
    longint unsigned return_obs_ds_prev_lc13;
    longint unsigned return_obs_ds_prev_lc15;
    longint unsigned return_obs_ds_prev_pe7_write;

    initial begin
        return_obs_ds_enabled = $test$plusargs("RETURN_OBS_DSKEW");
        return_obs_ds_limit = 128;
        return_obs_ds_plusarg_status = $value$plusargs(
            "RETURN_OBS_DSKEW_LIMIT=%d", return_obs_ds_limit
        );
        return_obs_ds_records = 0;
        return_obs_ds_prev_desc = 0;
        return_obs_ds_prev_prepared = 0;
        return_obs_ds_prev_match = 0;
        return_obs_ds_prev_source_push = 0;
        return_obs_ds_prev_source_pop = 0;
        return_obs_ds_prev_lc13 = 0;
        return_obs_ds_prev_lc15 = 0;
        return_obs_ds_prev_pe7_write = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_DSKEW enabled=%0d limit_name=RETURN_OBS_DSKEW_LIMIT limit=%0d schema=DSKEW",
                return_obs_ds_enabled, return_obs_ds_limit
            );
            $fflush(return_obs_fd);
        end
    end

    always @(negedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        integer ds_delta;
        bit ds_changed;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_ds_records = 0;
            return_obs_ds_prev_desc = 0;
            return_obs_ds_prev_prepared = 0;
            return_obs_ds_prev_match = 0;
            return_obs_ds_prev_source_push = 0;
            return_obs_ds_prev_source_pop = 0;
            return_obs_ds_prev_lc13 = 0;
            return_obs_ds_prev_lc15 = 0;
            return_obs_ds_prev_pe7_write = 0;
        end else if (return_obs_ds_enabled && return_obs_active) begin
            ds_changed =
                return_obs_md_desc_hs != return_obs_ds_prev_desc ||
                return_obs_md_prepared_wr != return_obs_ds_prev_prepared ||
                return_obs_mi_match != return_obs_ds_prev_match ||
                return_obs_rb_buf_push != return_obs_ds_prev_source_push ||
                return_obs_rb_buf_pop != return_obs_ds_prev_source_pop ||
                return_obs_lx_13_out != return_obs_ds_prev_lc13 ||
                return_obs_lx_15_out != return_obs_ds_prev_lc15 ||
                return_obs_lp_pe7_write != return_obs_ds_prev_pe7_write;
            ds_delta = return_obs_md_prepared_wr - return_obs_md_desc_hs;
            if (ds_changed && return_obs_ds_records < return_obs_ds_limit &&
                return_obs_fd != 0) begin
                return_obs_ds_records++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | DSKEW_EDGE_V1 | n=%0d desc=%0d desc_pop=%0d prepared=%0d prepared_rd=%0d delta=%0d m_match=%0d m_desc=%0d source_push=%0d source_pop=%0d tag=%0d tag_pop=%0d lc13=%0d lc14=%0d lc15=%0d pe7_wr=%0d pe7_rd=%0d mse1=%0d d_wdata=%0d d_last=%0d desc_terminal=%0d post_desc_push=%0d post_src_push=%0d post_prepare=%0d",
                    $time, return_obs_ds_records,
                    return_obs_md_desc_hs, return_obs_md_fifo_pop,
                    return_obs_md_prepared_wr, return_obs_md_prepared_rd,
                    ds_delta, return_obs_mi_match, return_obs_mi_descriptor,
                    return_obs_rb_buf_push, return_obs_rb_buf_pop,
                    return_obs_dw_tag_accept, return_obs_dw_buf_read_accept,
                    return_obs_lx_13_out, return_obs_lx_14_out,
                    return_obs_lx_15_out, return_obs_lp_pe7_write,
                    return_obs_lp_pe7_read, return_obs_lp_mse_input1,
                    return_obs_dw_wdata_accept,
                    return_obs_dw_wdata_last_accept,
                    return_obs_wt_desc_terminal,
                    return_obs_wt_post_desc_push,
                    return_obs_wt_post_source_push,
                    return_obs_wt_post_prepare
                );
                $fflush(return_obs_fd);
            end
            return_obs_ds_prev_desc = return_obs_md_desc_hs;
            return_obs_ds_prev_prepared = return_obs_md_prepared_wr;
            return_obs_ds_prev_match = return_obs_mi_match;
            return_obs_ds_prev_source_push = return_obs_rb_buf_push;
            return_obs_ds_prev_source_pop = return_obs_rb_buf_pop;
            return_obs_ds_prev_lc13 = return_obs_lx_13_out;
            return_obs_ds_prev_lc15 = return_obs_lx_15_out;
            return_obs_ds_prev_pe7_write = return_obs_lp_pe7_write;
        end
    end

    task automatic return_obs_write_dskew_state(input string event_name);
        integer ds_delta;
        if (return_obs_ds_enabled && return_obs_fd != 0) begin
            ds_delta = return_obs_md_prepared_wr - return_obs_md_desc_hs;
            $fdisplay(
                return_obs_fd,
                "%0t | DSKEW_BOUNDARY_V1 | event=%s desc=%0d desc_pop=%0d prepared=%0d prepared_rd=%0d delta=%0d m_match=%0d m_desc=%0d source_push=%0d source_pop=%0d tag=%0d tag_pop=%0d lc13=%0d lc14=%0d lc15=%0d pe7_wr=%0d pe7_rd=%0d mse1=%0d d_wdata=%0d d_last=%0d desc_terminal=%0d post_desc_push=%0d post_desc_pop=%0d post_src_push=%0d post_src_pop=%0d post_prepare=%0d post_prefetch_no_desc=%0d",
                $time, event_name,
                return_obs_md_desc_hs, return_obs_md_fifo_pop,
                return_obs_md_prepared_wr, return_obs_md_prepared_rd,
                ds_delta, return_obs_mi_match, return_obs_mi_descriptor,
                return_obs_rb_buf_push, return_obs_rb_buf_pop,
                return_obs_dw_tag_accept, return_obs_dw_buf_read_accept,
                return_obs_lx_13_out, return_obs_lx_14_out,
                return_obs_lx_15_out, return_obs_lp_pe7_write,
                return_obs_lp_pe7_read, return_obs_lp_mse_input1,
                return_obs_dw_wdata_accept,
                return_obs_dw_wdata_last_accept,
                return_obs_wt_desc_terminal,
                return_obs_wt_post_desc_push,
                return_obs_wt_post_desc_pop,
                return_obs_wt_post_source_push,
                return_obs_wt_post_source_pop,
                return_obs_wt_post_prepare,
                return_obs_wt_post_prefetch_no_desc
            );
            $fflush(return_obs_fd);
        end
    endtask
'''


def extract_and_reidentify(output: Path) -> Path:
    configure_base()
    with tempfile.TemporaryDirectory(prefix="node0004-v64-source-") as temp:
        source = base.extract_source(Path(temp))
        package = output / INSTALL
        if package.exists():
            raise BuildError("refusing to overwrite v64 package")
        shutil.copytree(source, package)
    base.replace_identity(package)
    return package


def patch_observer(package: Path) -> tuple[str, str]:
    path = package / "tb_probe/native_return_observer.svh"
    old_sha = base.sha256(path)
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '                return_obs_write_lc13_lc14_state("DIAG_DECISION");\n',
        '                return_obs_write_lc13_lc14_state("DIAG_DECISION");\n'
        '                return_obs_write_dskew_state("DIAG_DECISION");\n',
    )
    if "RETURN_OBS_DSKEW" in text:
        raise BuildError("source observer already contains DSKEW feature")
    text += DSKEW_BLOCK
    path.write_text(text, encoding="utf-8", newline="\n")
    return old_sha, base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    needle = "+RETURN_OBS_LC13_LC14 +RETURN_OBS_LC13_LC14_LIMIT=128"
    if text.count(needle) != 2:
        raise BuildError("runner LC13/L14 plusarg occurrence count differs")
    text = text.replace(
        needle,
        needle + " +RETURN_OBS_DSKEW +RETURN_OBS_DSKEW_LIMIT=128",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    needle = '''    {
        "feature": "RETURN_OBS_LC13_LC14",
        "enable": "+RETURN_OBS_LC13_LC14",
        "limits": ("+RETURN_OBS_LC13_LC14_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_LC13_LC14", "enabled=1", "limit=128",
        ),
    },
'''
    addition = needle + '''    {
        "feature": "RETURN_OBS_DSKEW",
        "enable": "+RETURN_OBS_DSKEW",
        "limits": ("+RETURN_OBS_DSKEW_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_DSKEW", "enabled=1", "limit=128",
        ),
    },
'''
    text = replace_once(text, needle, addition)
    path.write_text(text, encoding="utf-8", newline="\n")


def update_metadata(package: Path, old_observer_sha: str, new_observer_sha: str) -> None:
    readme = package / "README.md"
    readme.write_text(
        "# node0004 v64 D prepared/descriptor skew diagnostic\n\n"
        "v64 freezes the complete v63 functional payload, including the "
        "dynamically validated PE1 keep_last_index=3 fix. It adds only a "
        "qualified, time-aligned observer ledger that records when prepared "
        "D data first outruns live write descriptors and correlates the "
        "Memory_AG, Buffer_AG, LC13/14/15, PE7 and write-channel counters.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    base.write_json(
        package / "provenance/v63_to_v64_dskew_diagnostic.json",
        {
            "schema": "node0004-v63-to-v64-dskew-diagnostic-v1",
            "source_v63_sha256": SOURCE_SHA,
            "v63_return_analysis": {
                "path": ANALYSIS.relative_to(ROOT).as_posix(),
                "sha256": base.sha256(ANALYSIS),
                "last_proven_good": (
                    "LC18 index3 terminal accepted by PE7 and LC17 advances"
                ),
                "first_divergence": (
                    "prepared total20 exceeds descriptor total18"
                ),
            },
            "changed_surface": [
                "fresh package/install/return identity",
                "RETURN_OBS_DSKEW runtime-gated observer block",
                "simulator argv and feature binding for RETURN_OBS_DSKEW",
                "manifest/return-contract identity projection",
            ],
            "candidate_observation_matrix": {
                "data_prepare_ahead_of_descriptor": (
                    "delta becomes positive before a descriptor-terminal epoch"
                ),
                "descriptor_eligibility_capacity_cycle": (
                    "delta reaches two while Memory_AG match/descriptor counters "
                    "stop and upstream qualified counters stop"
                ),
                "buffer_owner_lifetime_exceeds_epoch": (
                    "source/tag qualified counters advance after terminal while "
                    "descriptor counter does not"
                ),
                "interburst_terminal_semantic_split": (
                    "descriptor terminal occurs, later descriptor resumes, and "
                    "only one side carries the epoch transition"
                ),
            },
            "frozen": [
                "PE1 keep_last_index=3 config and bitstream",
                "mapping/execplan/SCA semantics",
                "numeric/W3/qparams/tail/workload/golden",
                "all existing observer predicates",
                "timeout/backpressure",
                "functional RTL/ISA/hardware/active ndp-sim",
            ],
        },
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = base.replace_hash(manifest, old_observer_sha, new_observer_sha)
    manifest.update(
        {
            "install_name": INSTALL,
            "source_package_sha256": SOURCE_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "mapping_rebuilt": False,
            "bitstream_rebuilt": False,
            "execplan_rebuilt": False,
            "sca_semantics_rebuilt": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
            "observer_sha256": new_observer_sha,
        }
    )
    manifest["v63_return_reanalysis"] = {
        "return_sha256": (
            "87ed7fab2c214b260f5a7ec9761e4e47581fcd321bb458e2a32f9a5d52456109"
        ),
        "silent_exit_escape_closed": True,
        "pe_keep_fix_dynamic_pass": True,
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_expected": 320,
        "first_divergence": (
            "D_DATA_PREPARE_TOTAL20_EXCEEDS_DESCRIPTOR_TOTAL18"
        ),
    }
    manifest.setdefault("diagnostic_features", {})["RETURN_OBS_DSKEW"] = {
        "runtime_enable_parameter": "+RETURN_OBS_DSKEW",
        "limit_parameter": "+RETURN_OBS_DSKEW_LIMIT=128",
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1",
        "edge_schema": "DSKEW_EDGE_V1",
        "boundary_schema": "DSKEW_BOUNDARY_V1",
        "clock": "u_NDP_Top_new.clk_db",
        "reset": "u_NDP_Top_new.rst_n_db",
        "progress_semantics": "qualified counters only; levels are corroboration",
    }
    matrix = manifest.get("release_gate_matrix", [])
    for item in matrix:
        if item.get("gate_id") == "PACKAGE_LOCAL_HDL":
            item["changed_surface"] = [
                "tb_probe/native_return_observer.svh DSKEW ledger"
            ]
        if item.get("gate_id") == "DIAGNOSTIC_SEMANTICS":
            item["changed_surface"] = [
                "RETURN_OBS_DSKEW qualified ledger",
                "exact simulator argv and runtime feature receipt",
            ]
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)


def build_directory(output: Path) -> Path:
    package = extract_and_reidentify(output)
    old_observer_sha, new_observer_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    update_metadata(package, old_observer_sha, new_observer_sha)
    return package


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = [
        output / INSTALL,
        output / f"{INSTALL}.zip",
        output / f"{INSTALL}.zip.sha256",
        output / f"{INSTALL}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v64 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v64-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v64 deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v63-to-v64-dskew-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v63_sha256": SOURCE_SHA,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(output / f"{INSTALL}.validation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
