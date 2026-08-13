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

import tools.build_node0004_v70_token_origin_successor_v71 as previous  # noqa: E402

SOURCE = "r5_n4_hw_v71_token_origin_diag"
INSTALL = "r5_n4_hw_v72_token_origin_accept_diag"
SOURCE_SHA = "8cab1c7762496cf25ecde9057388d88c428711a2e52dc5a1e8e610a66840b452"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v71_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v71_return_v72_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"replacement count differs count={text.count(old)}: {old[:120]!r}")
    return text.replace(old, new, 1)


def configure() -> None:
    previous.SOURCE = SOURCE
    previous.INSTALL = INSTALL
    previous.SOURCE_SHA = SOURCE_SHA
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    previous.configure()


def replace_observer(observer: str) -> str:
    begin = "    // v71 TOKEN_ORIGIN_ACTUAL_CONSUMER_BEGIN"
    end = "    // v71 TOKEN_ORIGIN_ACTUAL_CONSUMER_END"
    if observer.count(begin) != 1 or observer.count(end) != 1:
        raise BuildError("v71 token-origin span is not unique")
    start = observer.index(begin)
    stop = observer.index(end, start) + len(end)
    block = observer[start:stop]
    block = block.replace("v71 TOKEN_ORIGIN_ACTUAL_CONSUMER", "v72 TOKEN_ORIGIN_ACCEPT_ACTUAL_CONSUMER")
    block = block.replace("RETURN_OBS_TOKEN_ORIGIN", "RETURN_OBS_TOKEN_ORIGIN_ACCEPT")
    block = block.replace("TOKEN_ORIGIN_EDGE_V1", "TOKEN_ORIGIN_ACCEPT_EDGE_V2")
    block = block.replace("schema=TOKEN_ORIGIN ", "schema=TOKEN_ORIGIN_ACCEPT ")
    block = once(
        block,
        "        bit to_mem_wr, to_buf_wr, to_mem_pop, to_buf_pop, to_desc;",
        "        bit to_mem_wr_attempt, to_buf_wr_attempt, to_mem_full, to_buf_full;\n"
        "        bit to_mem_wr, to_buf_wr, to_mem_pop, to_buf_pop, to_desc;",
    )
    mem_attempt = previous.mse("u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_en")
    buf_attempt = previous.mse("u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en")
    mem_full = previous.mse("u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full")
    buf_full = previous.mse("u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full")
    block = once(
        block,
        f"            to_mem_wr = {mem_attempt};\n            to_buf_wr = {buf_attempt};",
        f"            to_mem_wr_attempt = {mem_attempt};\n"
        f"            to_buf_wr_attempt = {buf_attempt};\n"
        f"            to_mem_full = {mem_full};\n"
        f"            to_buf_full = {buf_full};\n"
        "            // A FIFO write is accepted only when the write attempt sees capacity.\n"
        "            to_mem_wr = to_mem_wr_attempt && !to_mem_full;\n"
        "            to_buf_wr = to_buf_wr_attempt && !to_buf_full;",
    )
    old_fmt = "%0t | TOKEN_ORIGIN_ACCEPT_EDGE_V2 | qn=%0d mem_wr_ev=%0d buf_wr_ev=%0d"
    new_fmt = "%0t | TOKEN_ORIGIN_ACCEPT_EDGE_V2 | qn=%0d mem_wr_attempt=%0d buf_wr_attempt=%0d mem_full=%0d buf_full=%0d mem_wr_ev=%0d buf_wr_ev=%0d"
    block = once(block, old_fmt, new_fmt)
    block = once(
        block,
        "                    $time, return_obs_to_records,\n                    to_mem_wr, to_buf_wr, to_mem_pop, to_buf_pop, to_desc,",
        "                    $time, return_obs_to_records,\n"
        "                    to_mem_wr_attempt, to_buf_wr_attempt, to_mem_full, to_buf_full,\n"
        "                    to_mem_wr, to_buf_wr, to_mem_pop, to_buf_pop, to_desc,",
    )
    return observer[:start] + block + observer[stop:]


def replace_runtime(runtime: str) -> str:
    runtime = runtime.replace('"feature": "RETURN_OBS_TOKEN_ORIGIN"',
                              '"feature": "RETURN_OBS_TOKEN_ORIGIN_ACCEPT"')
    runtime = runtime.replace('"+RETURN_OBS_TOKEN_ORIGIN"',
                              '"+RETURN_OBS_TOKEN_ORIGIN_ACCEPT"')
    runtime = runtime.replace('"+RETURN_OBS_TOKEN_ORIGIN_LIMIT=128"',
                              '"+RETURN_OBS_TOKEN_ORIGIN_ACCEPT_LIMIT=128"')
    runtime = runtime.replace('"feature=RETURN_OBS_TOKEN_ORIGIN"',
                              '"feature=RETURN_OBS_TOKEN_ORIGIN_ACCEPT"')
    return runtime


def build_directory(output: Path) -> Path:
    configure()
    with tempfile.TemporaryDirectory(prefix="node0004-v72-source-") as td:
        source = base.extract_source(Path(td))
        package = output / INSTALL
        if package.exists():
            raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)

    observer_path = package / "tb_probe/native_return_observer.svh"
    observer_path.write_text(replace_observer(observer_path.read_text(encoding="utf-8")),
                             encoding="utf-8", newline="\n")

    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    old_argv = " +RETURN_OBS_TOKEN_ORIGIN +RETURN_OBS_TOKEN_ORIGIN_LIMIT=128"
    new_argv = " +RETURN_OBS_TOKEN_ORIGIN_ACCEPT +RETURN_OBS_TOKEN_ORIGIN_ACCEPT_LIMIT=128"
    if runner.count(old_argv) != 2:
        raise BuildError("v71 token-origin actual argv count differs")
    runner_path.write_text(runner.replace(old_argv, new_argv), encoding="utf-8", newline="\n")

    runtime_path = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime_path.write_text(replace_runtime(runtime_path.read_text(encoding="utf-8")),
                            encoding="utf-8", newline="\n")

    manifest_path = package / "package_manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_observer_sha = old["observer_sha256"]
    new_observer_sha = base.sha256(observer_path)
    manifest = base.replace_hash(old, old_observer_sha, new_observer_sha)
    old_feature = manifest.setdefault("diagnostic_features", {}).pop("RETURN_OBS_TOKEN_ORIGIN")
    manifest["diagnostic_features"]["RETURN_OBS_TOKEN_ORIGIN_ACCEPT"] = {
        **old_feature,
        "runtime_enable_parameter": "+RETURN_OBS_TOKEN_ORIGIN_ACCEPT",
        "limit_parameters": ["+RETURN_OBS_TOKEN_ORIGIN_ACCEPT_LIMIT=128"],
        "edge_schema": "TOKEN_ORIGIN_ACCEPT_EDGE_V2",
        "qualification": {
            "mem_queue_write": "mem_ag_idx_queue_wr_en && !mem_ag_idx_queue_full",
            "buf_queue_write": "buf_ag_idx_queue_wr_en && !buf_ag_idx_queue_full",
            "queue_pop": "queue_rd_en && !queue_empty",
            "descriptor_accept": "wr_data_chl_req_valid && wr_data_chl_req_ready",
        },
        "state_only_fields": ["write_attempt", "queue_full", "backpressure", "queue_data", "queue_empty"],
        "parser_policy": "count only qualified *_ev fields; attempts/full/levels never advance progress",
    }
    manifest.update({
        "install_name": INSTALL,
        "source_package_sha256": SOURCE_SHA,
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "observer_sha256": new_observer_sha,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False,
        "mapping_rebuilt": False,
        "bitstream_rebuilt": False,
        "execplan_rebuilt": False,
        "sca_semantics_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    })
    base.write_json(package / "provenance/v71_to_v72_token_origin_accept.json", {
        "schema": "node0004-v71-to-v72-token-origin-accept-v1",
        "source_v71_sha256": SOURCE_SHA,
        "v71_return_sha256": "5d424c2865d9b98f183e85794a9bbf89f827efcc79e2fc81ee4d9cfb70202340",
        "analysis_sha256": base.sha256(ANALYSIS),
        "last_proven_good": "V70_DESCRIPTOR_18_AND_PREPARED_GROUP_18_JOIN_DRAIN_WITH_BUFFER_POP_21",
        "first_divergence": "V71_TOKEN_ORIGIN_RECORD_12_COUNTS_BUFFER_QUEUE_WRITE_ATTEMPT_WHILE_BUF_BP_IS_ZERO",
        "fix": "qualify Memory_AG and Buffer_AG queue writes with !queue_full and expose attempt/full separately",
        "changed_surface": ["fresh identity", "token-origin event qualification", "runtime feature binding"],
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure",
                   "functional RTL/ISA/hardware/active ndp-sim"],
    })
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    out = args.output_root.resolve()
    out.mkdir(parents=True, exist_ok=True)
    package = build_directory(out)
    archive = out / f"{INSTALL}.zip"
    base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v72-repeat-") as td:
        repeat = build_directory(Path(td))
        repeat_zip = Path(td) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("deterministic rebuild differs")
    sidecar = out / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "node0004-v71-to-v72-token-origin-accept-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(archive),
        "zip_bytes": archive.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v71_sha256": SOURCE_SHA,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(out / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
