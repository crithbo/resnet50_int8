from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_n71_gap_v47_stage_transition_rootfix"
INSTALL = "r5_n71_gap_v48_multislice_pipeline_diag"
SOURCE_SHA = "e5e1e010970230fb9f9706bc2dd2381dbfecd2c304fd48e212587827110567ab"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
HELPER = ROOT / "tools/server_package_runtime_layout.py"
HELPER_SHA = "7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a"
SERVER_RULE_SHA = "16f7773796dccf4f27a5e412bb200f7b4190ffb87742d3dd2e466866a7f77dde"
INDEX_SHA = "68c13cbd1461ca2a506174678d22cfdbfdc5aced25ad80150d4e4cacece7f2be"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def deterministic_zip(source: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = f"{source.name}/{path.relative_to(source).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("frozen v47 source SHA mismatch")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("frozen v47 source CRC failure")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"unexpected source roots: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE in text:
            path.write_text(
                text.replace(SOURCE, INSTALL), encoding="utf-8", newline="\n"
            )


OBSERVER_EXTENSION = r'''

    // v48: mask-wide per-slice pipeline information-gain observer.
    // All inputs are existing package-local public monitor/handshake surfaces.
    // Sticky accepted masks are updated only in their owner clocks.  A stable
    // level is state, never monotonic progress.  No DUT signal is driven.
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_cfg_start_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_cfg_finish_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_mse0_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_mse3_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_ga_in_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_ga_out_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_mse4_req_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_mse4_wdata_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_ms_finish_seen;
    logic [9*`GLB_SLICE_NUM-1:0] return_obs_ms_prev_snapshot;
    bit return_obs_ms_enabled;
    longint unsigned return_obs_ms_db_cycles;
    longint unsigned return_obs_ms_emit_count;
    longint unsigned return_obs_ms_heartbeat_cycles;

    initial begin
        return_obs_ms_enabled =
            $test$plusargs("RETURN_OBS_MULTISLICE_PIPELINE");
        return_obs_ms_db_cycles = 0;
        return_obs_ms_emit_count = 0;
        return_obs_ms_heartbeat_cycles = 1048576;
        return_obs_ms_prev_snapshot = '0;
        return_obs_plusarg_status = $value$plusargs(
            "RETURN_OBS_MULTISLICE_HEARTBEAT_CYCLES=%d",
            return_obs_ms_heartbeat_cycles
        );
        #0;
        if (return_obs_enabled && return_obs_ms_enabled &&
            return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "# multislice_pipeline=1 selected_mask=0x0000ffff divergence_mask=0x0000fffe global_owner=clk datapath_owner=clk_sg reporter_owner=clk_db emit_limit=256"
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk or
             negedge u_NDP_Top_new.rst_n) begin
        if (!u_NDP_Top_new.rst_n) begin
            return_obs_ms_cfg_start_seen <= '0;
            return_obs_ms_cfg_finish_seen <= '0;
            return_obs_ms_finish_seen <= '0;
        end
        else if (return_obs_enabled && return_obs_ms_enabled) begin
            for (int g = 0; g < `SLICE_GROUP_SIZE; g++) begin
                for (int s = 0; s < `SLICE_GROUP_NUM; s++) begin
                    if (return_obs_sem_cfg_start_mon[g][s])
                        return_obs_ms_cfg_start_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_sem_cfg_finish_mon[g][s])
                        return_obs_ms_cfg_finish_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_slice_finish_mon[g][s])
                        return_obs_ms_finish_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin
        if (!u_NDP_Top_new.rst_n_sg) begin
            return_obs_ms_mse0_seen <= '0;
            return_obs_ms_mse3_seen <= '0;
            return_obs_ms_ga_in_seen <= '0;
            return_obs_ms_ga_out_seen <= '0;
            return_obs_ms_mse4_req_seen <= '0;
            return_obs_ms_mse4_wdata_seen <= '0;
        end
        else if (return_obs_enabled && return_obs_ms_enabled) begin
            for (int g = 0; g < `SLICE_GROUP_SIZE; g++) begin
                for (int s = 0; s < `SLICE_GROUP_NUM; s++) begin
                    if (return_obs_mse0_buf_hs_mon[g][s])
                        return_obs_ms_mse0_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (return_obs_mse3_buf_hs_mon[g][s])
                        return_obs_ms_mse3_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (|return_obs_ga_input_valid_mon[g][s])
                        return_obs_ms_ga_in_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (|return_obs_ga_outbuffer_wr_mon[g][s])
                        return_obs_ms_ga_out_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (|local_req_hs[g][s][4])
                        return_obs_ms_mse4_req_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                    if (|local_wdata_hs[g][s][4])
                        return_obs_ms_mse4_wdata_seen[
                            g * `SLICE_GROUP_NUM + s] <= 1'b1;
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        logic [9*`GLB_SLICE_NUM-1:0] ms_snapshot;
        bit ms_changed;
        bit ms_heartbeat;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_ms_db_cycles = 0;
            return_obs_ms_emit_count = 0;
            return_obs_ms_prev_snapshot = '0;
        end
        else if (return_obs_enabled && return_obs_ms_enabled &&
                 return_obs_fd != 0) begin
            return_obs_ms_db_cycles++;
            ms_snapshot = {
                return_obs_ms_finish_seen,
                return_obs_ms_mse4_wdata_seen,
                return_obs_ms_mse4_req_seen,
                return_obs_ms_ga_out_seen,
                return_obs_ms_ga_in_seen,
                return_obs_ms_mse3_seen,
                return_obs_ms_mse0_seen,
                return_obs_ms_cfg_finish_seen,
                return_obs_ms_cfg_start_seen
            };
            ms_changed = ms_snapshot != return_obs_ms_prev_snapshot;
            ms_heartbeat =
                (return_obs_ms_db_cycles %
                 return_obs_ms_heartbeat_cycles) == 0;
            if ((ms_changed || ms_heartbeat) &&
                return_obs_ms_emit_count < 256) begin
                return_obs_ms_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | MULTISLICE_PIPELINE_STATE_V1 | event=%s n=%0d db_cycle=%0d cfg_start=0x%0h cfg_finish=0x%0h mse0=0x%0h mse3=0x%0h ga_in=0x%0h ga_out=0x%0h mse4_req=0x%0h mse4_wdata=0x%0h finish=0x%0h",
                    $time,
                    (ms_changed ? "QUALIFIED_EDGE" : "HEARTBEAT"),
                    return_obs_ms_emit_count,
                    return_obs_ms_db_cycles,
                    return_obs_ms_cfg_start_seen,
                    return_obs_ms_cfg_finish_seen,
                    return_obs_ms_mse0_seen,
                    return_obs_ms_mse3_seen,
                    return_obs_ms_ga_in_seen,
                    return_obs_ms_ga_out_seen,
                    return_obs_ms_mse4_req_seen,
                    return_obs_ms_mse4_wdata_seen,
                    return_obs_ms_finish_seen
                );
                $fflush(return_obs_fd);
            end
            return_obs_ms_prev_snapshot = ms_snapshot;
        end
    end
'''


PARSER = r'''from __future__ import annotations
import argparse, json, re
from pathlib import Path

FIELDS = ("cfg_start","cfg_finish","mse0","mse3","ga_in","ga_out",
          "mse4_req","mse4_wdata","finish")
PATTERN = re.compile(r"MULTISLICE_PIPELINE_STATE_V1\s+\|\s+event=(QUALIFIED_EDGE|HEARTBEAT).*?" +
    r"\s".join(fr"{name}=0x([0-9a-fA-F]+)" for name in FIELDS))

def decide(text: str) -> dict:
    rows=[]
    for line in text.splitlines():
        match=PATTERN.search(line)
        if match:
            rows.append({"event":match.group(1), **{
                name:int(value,16)
                for name,value in zip(FIELDS,match.groups()[1:])
            }})
    last=rows[-1] if rows else {name:0 for name in FIELDS}
    per_slice=[]
    for slice_id in range(1,16):
        checkpoints={name:bool(last[name] & (1<<slice_id)) for name in FIELDS}
        first_missing=next((name for name in FIELDS if not checkpoints[name]),None)
        per_slice.append({"slice":slice_id,"checkpoints":checkpoints,
                          "first_missing":first_missing})
    return {
      "schema":"gap-node0071-multislice-pipeline-decision-v1",
      "feature_enabled_marker":
          "# multislice_pipeline=1" in text,
      "state_record_count":len(rows),
      "qualified_record_count":
          sum(row["event"]=="QUALIFIED_EDGE" for row in rows),
      "last_masks":{name:f"0x{last[name]:04x}" for name in FIELDS},
      "per_slice":per_slice,
      "candidate_matrix":{
        "CONFIG_DELIVERY_OR_CFG_FINISH":
          ["cfg_start","cfg_finish"],
        "MSE0_OR_MSE3_ACCEPTANCE":["mse0","mse3"],
        "GA_ACCEPTED_INPUT_OR_OUTPUT":["ga_in","ga_out"],
        "MSE4_REQUEST_OR_WDATA_PAIR":["mse4_req","mse4_wdata"],
        "SLICE_FINISH":["finish"]},
      "claim_boundary":
        "Qualified sticky masks localize first missing slice checkpoint; "
        "stable levels and zero counts do not prove a functional leaf."
    }

def self_test() -> dict:
    full=" ".join(f"{name}=0xfffe" for name in FIELDS)
    cut_values={name:"fffe" for name in FIELDS}; cut_values["ga_out"]="0002"
    cut=" ".join(f"{name}=0x{cut_values[name]}" for name in FIELDS)
    stable=("0 | MULTISLICE_PIPELINE_STATE_V1 | event=HEARTBEAT n=1 db_cycle=8 "
            + full)
    cut_line=("1 | MULTISLICE_PIPELINE_STATE_V1 | event=QUALIFIED_EDGE n=2 "
              "db_cycle=9 " + cut)
    a=decide(stable); b=decide(stable+"\n"+cut_line)
    checks={
      "stable_level_not_extra_progress":a["qualified_record_count"]==0,
      "all_checkpoint_complete":all(x["first_missing"] is None for x in a["per_slice"]),
      "nearest_escape_identified":
        next(x for x in b["per_slice"] if x["slice"]==2)["first_missing"]=="ga_out",
      "simultaneous_event_supported":b["qualified_record_count"]==1,
      "reset_or_absent_marker_fail_closed":
        not decide("")["feature_enabled_marker"],
    }
    return {"schema":"gap-node0071-multislice-predicate-self-test-v1",
            "pass":all(checks.values()),"checks":checks}

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("analyze"); a.add_argument("--observer-log",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    s=sub.add_parser("self-test"); s.add_argument("--output",type=Path,required=True)
    ns=p.parse_args()
    value=self_test() if ns.cmd=="self-test" else decide(
        ns.observer_log.read_text(encoding="utf-8",errors="replace")
        if ns.observer_log.is_file() else "")
    ns.output.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0 if (value.get("pass",True) and
                 (ns.cmd=="self-test" or value["feature_enabled_marker"])) else 1
if __name__=="__main__": raise SystemExit(main())
'''


def patch_observer(package: Path) -> None:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "MULTISLICE_PIPELINE_STATE_V1" in text:
        raise BuildError("v48 observer already present")
    path.write_text(text + OBSERVER_EXTENSION, encoding="utf-8", newline="\n")
    (package / "package_tools/gap_node0071_multislice_pipeline_decision.py").write_text(
        PARSER, encoding="utf-8", newline="\n"
    )


def rewrite_sca_d(package: Path) -> None:
    path = package / "workload/sca_cfg_D.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    old = f"install/cfg_pkg/{INSTALL}/readback/"
    new = f"install/codex_runs/{INSTALL}/{{attempt}}/readback/"
    changed = 0
    for entry in document.values():
        value = entry["path"]
        if not value.startswith(old):
            raise BuildError(f"unexpected SCA-D path: {value}")
        entry["path"] = new + value[len(old) :]
        changed += 1
    if changed != 48:
        raise BuildError(f"expected 48 SCA-D paths, got {changed}")
    write_json(path, document)


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/gap_node0071_complete_server_runtime.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("len(allowlist) != 73", "len(allowlist) != 75")
    old = '''    prefix = PurePosixPath(
        "install", "cfg_pkg", str(manifest["install_name"])
    )
'''
    new = '''    prefix = PurePosixPath(
        "install", "cfg_pkg", str(manifest["install_name"])
    )
    output_prefix = PurePosixPath(
        "install", "codex_runs", str(manifest["install_name"]), "{attempt}"
    )
'''
    if text.count(old) != 1:
        raise BuildError("runtime prefix anchor differs")
    text = text.replace(old, new, 1)
    old = '''        rel = PurePosixPath(str(entry["path"]))
        if rel.parts[: len(prefix.parts)] != prefix.parts:
            raise RuntimeGateError(f"readback path escapes namespace: {key}")
        local = workload.joinpath(*rel.parts[len(prefix.parts) :])
        if local.exists():
            raise RuntimeGateError("formal readback target must be absent")
'''
    new = '''        rel = PurePosixPath(str(entry["path"]))
        if rel.parts[: len(output_prefix.parts)] != output_prefix.parts:
            raise RuntimeGateError(f"readback path escapes run namespace: {key}")
'''
    if text.count(old) != 1:
        raise BuildError("runtime SCA-D preflight anchor differs")
    text = text.replace(old, new, 1)
    old = "def preflight_installed(package_root: Path, cfg_root: Path) -> dict[str, Any]:"
    new = "def preflight_installed(package_root: Path, cfg_root: Path, run_root: Path) -> dict[str, Any]:"
    if text.count(old) != 1:
        raise BuildError("runtime installed signature differs")
    text = text.replace(old, new, 1)
    text = text.replace(
        'target = safe_child(cfg_root, str(record["runtime_path"]))',
        'target = safe_child(run_root, str(record["runtime_path"]))',
        1,
    )
    text = text.replace(
        'actual = safe_child(cfg_root, str(record["runtime_path"]))',
        'actual = safe_child(run_root, str(record["runtime_path"]))',
        1,
    )
    old = '''    source = file_records(package_root / "workload", exclude_manifest=False)
    installed = file_records(cfg_root, exclude_manifest=False)
    if source != installed:
        raise RuntimeGateError("installed workload differs from package")
'''
    new = '''    source = file_records(package_root / "workload", exclude_manifest=False)
    installed = file_records(cfg_root, exclude_manifest=False)
    source_sca_d = source.pop("sca_cfg_D.json", None)
    installed_sca_d = installed.pop("sca_cfg_D.json", None)
    if source != installed:
        raise RuntimeGateError("installed workload differs from package")
    source_doc = load_json(package_root / "workload/sca_cfg_D.json")
    installed_doc = load_json(cfg_root / "sca_cfg_D.json")
    attempt = run_root.name
    normalized = json.loads(json.dumps(installed_doc).replace(attempt, "{attempt}"))
    if source_sca_d is None or installed_sca_d is None or normalized != source_doc:
        raise RuntimeGateError("installed SCA-D attempt projection differs")
'''
    if text.count(old) != 1:
        raise BuildError("runtime installed exact-set anchor differs")
    text = text.replace(old, new, 1)
    old = "result = preflight_installed(args.package_root, args.cfg_root)"
    new = "result = preflight_installed(args.package_root, args.cfg_root, args.run_root)"
    if text.count(old) != 1:
        raise BuildError("runtime installed call differs")
    text = text.replace(old, new, 1)
    anchor = 'ins.add_argument("--cfg-root", type=Path, required=True)'
    if text.count(anchor) != 1:
        raise BuildError("runtime installed parser anchor differs")
    text = text.replace(
        anchor, anchor + '\n    ins.add_argument("--run-root", type=Path, required=True)', 1
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def runtime_contract(package: Path) -> dict[str, object]:
    attempt_max = 10
    root_max = 96
    limit = 240
    additional = [
        f"install/codex_runs/{INSTALL}/{{attempt}}/sim_results/return_observer/return_observer.log",
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/multislice_pipeline_decision.json",
        f"install/codex_runs/{INSTALL}/{{attempt}}/compile/sim_results/compile_driver.log",
    ]
    projected = {
        f"install/cfg_pkg/{INSTALL}/"
        + path.relative_to(package / "workload").as_posix()
        for path in (package / "workload").rglob("*")
        if path.is_file()
    }
    attempt = "a" * attempt_max
    candidates = projected | {
        item.replace("{attempt}", attempt) for item in additional
    }
    longest = max(candidates, key=lambda item: (len(item), item))
    projected_absolute = root_max + 1 + len(longest)
    return {
        "schema": "server_package_runtime_layout_v1",
        "package_id": INSTALL,
        "install_name": INSTALL,
        "runner_member": "PREPARE_AND_RUN.sh",
        "manifest_member": "TEST_PACKAGE_MANIFEST.json",
        "shared_layout_helper": {
            "member": "package_tools/server_package_runtime_layout.py",
            "sha256": HELPER_SHA,
        },
        "tb_cwd": "$server_root",
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "required_preexisting_parents": ["install"],
        "package_creatable_parent_dirs": [
            "install/cfg_pkg",
            "install/codex_runs",
        ],
        "runtime_roots": {
            "cfg_root": f"install/cfg_pkg/{INSTALL}",
            "run_root": f"install/codex_runs/{INSTALL}/{{attempt}}",
            "evidence_root": f"install/codex_runs/{INSTALL}/{{attempt}}/evidence",
            "compile_root": f"install/codex_runs/{INSTALL}/{{attempt}}/compile",
        },
        "payload_mounts": [
            {
                "source_prefix": "workload/",
                "runtime_prefix": f"install/cfg_pkg/{INSTALL}/",
            }
        ],
        "sca_consumers": [
            {
                "plusarg": "SCA_CFG",
                "member": "workload/sca_cfg.json",
                "mode": "read_inputs",
            },
            {
                "plusarg": "SCA_CFG_D",
                "member": "workload/sca_cfg_D.json",
                "mode": "write_outputs",
            },
        ],
        "runner_bindings": {
            "layout_prepare_marker": 'layout_values="$(python3 "$layout_helper" prepare',
            "tb_cwd_marker": 'cd "$server_root"',
            "compile_marker": "echo RUNTIME_LAYOUT_COMPILE_START",
            "simulation_marker": "echo RUNTIME_LAYOUT_SIMULATION_START",
        },
        "path_budget": {
            "attempt_max_chars": attempt_max,
            "declared_target_root_max_chars": root_max,
            "max_projected_absolute_path_chars": projected_absolute,
            "absolute_path_limit_chars": limit,
            "additional_projected_paths": additional,
        },
        "finalizer": {
            "arm_marker": "trap 'finalize $?' EXIT",
            "first_preflight_marker": 'if [ "$#" -ne 1 ]; then',
            "required_scenarios": [
                "normal",
                "preflight_fail",
                "compile_fail",
                "HUP",
                "INT",
                "TERM",
            ],
        },
        "claim_boundary": (
            "Install-only V2 runtime layout and mask-wide read-only diagnostic "
            "transport; no functional, terminal, formal-D, E4 or E5 claim."
        ),
        "_computed": {
            "longest": longest,
            "longest_chars": len(longest),
            "projected_absolute": projected_absolute,
        },
    }


def runner_text() -> str:
    # The identity is fixed once here; expected package contents and SHA values
    # remain manifest-owned.  The finalizer is armed before the first fallible
    # preflight and uses a minimal fail-closed return if layout is unavailable.
    return f'''#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
install_name="{INSTALL}"
package_id="{INSTALL}"
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${{install_name}}_return.zip"
return_sha="$return_zip.sha256"
package_root="$(dirname "${{BASH_SOURCE[0]}}")"
runtime="$package_root/package_tools/gap_node0071_complete_server_runtime.py"
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
observer_guard="$package_root/package_tools/gap_node0071_package_observer_guard.py"
canonical_tool="$package_root/package_tools/gap_node0071_canonical_decision.py"
stage_tool="$package_root/package_tools/gap_node0071_stage_transition_decision.py"
multislice_tool="$package_root/package_tools/gap_node0071_multislice_pipeline_decision.py"
compile_status=125
simulation_status=125
runner_status=125
signal_name=NONE
finalized=0
sim_pid=0
sampler_pid=0
server_root=
cfg_root=
run_root=
evidence_root=
compile_root=
observer_log=
progress_log=
attempt="a$$"

publish_minimal_return() {{
  mkdir -p -- "$result_root" || return 98
  [ -d "$result_root" ] && [ -w "$result_root" ] || return 98
  [ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || return 98
  stage="$result_root/.${{install_name}}.return.$$"
  [ ! -e "$stage" ] || return 98
  mkdir -- "$stage" || return 98
  printf '%s\\n' "$compile_status" >"$stage/compile_exit_status.txt"
  printf '%s\\n' "$simulation_status" >"$stage/simulation_exit_status.txt"
  printf '%s\\n' "$signal_name" >"$stage/signal_status.txt"
  printf '%s\\n' PRECHECK_PARTIAL_RETURN >"$stage/SERVER_RESULT_GATE"
  python3 - "$stage" "$return_zip" "$install_name" <<'PY'
import hashlib,json,os,pathlib,sys,zipfile
stage=pathlib.Path(sys.argv[1]); target=pathlib.Path(sys.argv[2]); identity=sys.argv[3]
files=[]
for p in sorted(stage.iterdir()):
    files.append({{"path":p.name,"size_bytes":p.stat().st_size,
                  "sha256":hashlib.sha256(p.read_bytes()).hexdigest()}})
m={{"schema":"gap-node0071-precheck-partial-return-v1",
   "install_name":identity,"status":"incomplete","allowlist_only":True,
   "required_missing":["layout_or_preflight"],"files":files}}
(stage/"RETURN_MANIFEST.json").write_text(
    json.dumps(m,indent=2,sort_keys=True)+"\\n",encoding="utf-8")
tmp=target.parent/("." + target.name + ".tmp." + str(os.getpid()))
with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(stage.iterdir()):
        z.write(p,f"{{identity}}_return/{{p.name}}")
with zipfile.ZipFile(tmp) as z: assert z.testzip() is None
os.replace(tmp,target)
d=hashlib.sha256(target.read_bytes()).hexdigest()
s=pathlib.Path(str(target)+".sha256.tmp."+str(os.getpid()))
s.write_text(f"{{d}}  {{target.name}}\\n",encoding="ascii")
os.replace(s,pathlib.Path(str(target)+".sha256"))
PY
  rc=$?
  rm -rf -- "$stage"
  return "$rc"
}}

root_snapshot() {{
  python3 - "$server_root" <<'PY'
import json,os,pathlib,sys
root=pathlib.Path(sys.argv[1]); rows=[]
for entry in os.scandir(root):
    kind=("symlink" if entry.is_symlink() else
          "directory" if entry.is_dir(follow_symlinks=False) else
          "file" if entry.is_file(follow_symlinks=False) else "other")
    rows.append({{"name":entry.name,"type":kind}})
print(json.dumps({{"schema":"ndp-root-toplevel-snapshot-v1",
 "entries":sorted(rows,key=lambda x:(x["name"],x["type"]))}},
 sort_keys=True,separators=(",",":")))
PY
}}

sample_progress() {{
  [ -n "$progress_log" ] || return 0
  host_ns="$(date +%s%N)"
  observer_bytes=0
  observer_tail=OBSERVER_NOT_CREATED
  [ ! -f "$observer_log" ] || observer_bytes="$(wc -c <"$observer_log" | tr -d ' ')"
  [ ! -s "$observer_log" ] || observer_tail="$(tail -n 1 "$observer_log" | tr '\\t' ' ')"
  printf '%s\\tobserver_bytes=%s\\t%s\\n' "$host_ns" "$observer_bytes" "$observer_tail" >>"$progress_log"
}}

progress_sampler() {{
  while kill -0 "$sim_pid" 2>/dev/null; do sample_progress; sleep 60; done
  sample_progress
}}

finalize() {{
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT HUP INT TERM
  set +e
  if [ "$sim_pid" -gt 0 ] && kill -0 "$sim_pid" 2>/dev/null; then
    kill -TERM "$sim_pid" 2>/dev/null; wait "$sim_pid" 2>/dev/null
  fi
  if [ "$sampler_pid" -gt 0 ] && kill -0 "$sampler_pid" 2>/dev/null; then
    kill -TERM "$sampler_pid" 2>/dev/null; wait "$sampler_pid" 2>/dev/null
  fi
  if [ -n "$evidence_root" ] && [ -d "$evidence_root" ] &&
     [ -n "$run_root" ] && [ -d "$run_root" ]; then
    sample_progress
    printf '%s\\n' "$compile_status" >"$evidence_root/compile_exit_status.txt"
    printf '%s\\n' "$simulation_status" >"$evidence_root/simulation_exit_status.txt"
    printf '%s\\n' "$original" >"$evidence_root/runner_exit_status.txt"
    printf 'signal=%s\\ncompile_status=%s\\nsimulation_status=%s\\nrunner_status=%s\\npartial=%s\\nfinalizer_reason=EXIT_OR_SIGNAL\\nfixed_result_root=%s\\n' \
      "$signal_name" "$compile_status" "$simulation_status" "$original" \
      "$([ "$signal_name" = NONE ] && [ "$simulation_status" -eq 0 ] && echo false || echo true)" \
      "$result_root" >"$evidence_root/signal_status.txt"
    if [ -s "$observer_log" ] &&
       grep -Fq '[RETURN_OBSERVER] enabled' "$run_root/sim_results/sim.log" &&
       grep -Fq 'multislice_pipeline=1' "$observer_log" &&
       grep -Fq 'MULTISLICE_PIPELINE_STATE_V1' "$observer_log"; then
      printf 'observer_enabled_and_returned=true\\nmultislice_pipeline_enabled=true\\nmultislice_pipeline_records_returned=true\\n' >"$evidence_root/observer_binding.txt"
    else
      printf 'observer_enabled_and_returned=false\\nmultislice_pipeline_enabled=false\\nmultislice_pipeline_records_returned=false\\n' >"$evidence_root/observer_binding.txt"
    fi
    if [ -s "$observer_log" ]; then
      python3 "$stage_tool" analyze --observer-log "$observer_log" \
        --output "$evidence_root/stage_transition_decision.json" >/dev/null 2>&1 || true
      python3 "$multislice_tool" analyze --observer-log "$observer_log" \
        --output "$evidence_root/multislice_pipeline_decision.json" >/dev/null 2>&1 || true
      python3 "$canonical_tool" observe --observer-log "$observer_log" \
        --sim-log "$run_root/sim_results/sim.log" --signal "$signal_name" \
        --simulation-status "$simulation_status" --stall-window-cycles 1048576 \
        --heartbeat-cycles 262144 --manifest "$package_root/TEST_PACKAGE_MANIFEST.json" \
        --output "$evidence_root/canonical_decision.json" >/dev/null 2>&1 || true
    fi
    python3 - "$evidence_root/stage_transition_decision.json" \
      "$evidence_root/multislice_pipeline_decision.json" \
      "$evidence_root/canonical_decision.json" "$signal_name" "$simulation_status" <<'PY'
import json,pathlib,sys
reason="OBSERVER_LOG_ABSENT_OR_PARSER_FAILED_BEFORE_DECISION"
payloads=[
    {{"schema":"gap-stage-transition-decision-v1","status":"FAIL_CLOSED",
     "reason":reason,"natural_terminal":False}},
    {{"schema":"gap-multislice-pipeline-decision-v1","status":"FAIL_CLOSED",
     "reason":reason,"natural_terminal":False}},
    {{"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",
     "reason":reason,"boundary":"OBSERVER_DECISION_UNAVAILABLE",
     "signal":sys.argv[4],"simulation_status":int(sys.argv[5]),
     "natural_terminal":False}},
]
for name,payload in zip(sys.argv[1:4],payloads):
    path=pathlib.Path(name)
    if not path.is_file():
        path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
PY
    python3 "$runtime" analyze --package-root "$package_root" --cfg-root "$cfg_root" \
      --evidence-root "$evidence_root" --run-root "$run_root" \
      --compile-status "$compile_status" --simulation-status "$simulation_status" >/dev/null
    root_gate=96
    root_snapshot >"$evidence_root/ndp_root_toplevel_post.json"
    if [ "$?" -eq 0 ] && [ -f "$evidence_root/ndp_root_toplevel_pre.json" ]; then
      python3 - "$evidence_root/ndp_root_toplevel_pre.json" \
        "$evidence_root/ndp_root_toplevel_post.json" \
        "$evidence_root/ndp_root_toplevel_exact_set.json" <<'PY'
import hashlib,json,pathlib,sys
pre=json.load(open(sys.argv[1],encoding="utf-8"))
post=json.load(open(sys.argv[2],encoding="utf-8"))
same=pre["entries"]==post["entries"]
def digest(value):
    return hashlib.sha256((json.dumps(value,sort_keys=True,separators=(",",":"))+"\\n").encode()).hexdigest()
out={{"schema":"ndp-root-toplevel-exact-set-v1",
     "pre_exact_set":pre["entries"],"post_exact_set":post["entries"],
     "pre_exact_set_sha256":digest(pre["entries"]),
     "post_exact_set_sha256":digest(post["entries"]),
     "ndp_root_toplevel_unchanged":same}}
pathlib.Path(sys.argv[3]).write_text(json.dumps(out,indent=2,sort_keys=True)+"\\n",encoding="utf-8")
raise SystemExit(0 if same else 43)
PY
      root_gate=$?
    fi
    python3 "$runtime" collect --server-root "$server_root" \
      --install-name "$install_name" --evidence-root "$evidence_root" \
      --run-root "$run_root" --cfg-root "$cfg_root" \
      --result-root "$result_root" --package-root "$package_root" >/dev/null
    collection=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] || final="$collection"
    [ "$final" -ne 0 ] || [ "$root_gate" -eq 0 ] || final="$root_gate"
  else
    publish_minimal_return
    publication=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$publication" -eq 0 ] || final="$publication"
  fi
  exit "$final"
}}

on_signal() {{
  signal_name="$1"
  [ "$sim_pid" -le 0 ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}}

trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root" >&2
  exit 2
fi
case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac
for tool in python3 timeout make date tail tr grep sleep; do
  command -v "$tool" >/dev/null 2>&1 || exit 3
done
package_root="$(cd "$package_root" && pwd -P)" || exit 2
runtime="$package_root/package_tools/gap_node0071_complete_server_runtime.py"
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
mkdir -p -- "$result_root" || exit 9
[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9
[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || exit 10
ndp_pre_snapshot="$(root_snapshot)" || exit 12
layout_values="$(python3 "$layout_helper" prepare \
  --server-root "$server_root" --package-id "$package_id" \
  --install-name "$install_name" --attempt "$attempt" --format shell)" || exit 13
eval "$layout_values"
cfg_root="$CFG_ROOT"
run_root="$RUN_ROOT"
evidence_root="$EVIDENCE_ROOT"
compile_root="$COMPILE_ROOT"
observer_log="$run_root/sim_results/return_observer/return_observer.log"
progress_log="$evidence_root/progress_samples.log"
mkdir -p -- "$compile_root/sim_results" "$run_root/sim_results/return_observer" "$run_root/readback"
printf '%s\\n' "$ndp_pre_snapshot" >"$evidence_root/ndp_root_toplevel_pre.json"
cat >"$evidence_root/ndp_root_write_contract.json" <<EOF
{{"schema":"ndp-root-write-contract-v1","server_root":"${{server_root}}",
"result_root":"/home/panqs/ndp/simresult",
"root_internal_write_targets":["install/cfg_pkg/${{install_name}}","install/codex_runs/${{package_id}}/${{attempt}}"],
"existing_first_level_parents":["install"],
"external_write_targets":["/home/panqs/ndp/simresult/${{install_name}}_return.zip","/home/panqs/ndp/simresult/${{install_name}}_return.zip.sha256"]}}
EOF
cp "$package_root/TEST_PACKAGE_MANIFEST.json" "$evidence_root/PACKAGE_MANIFEST.json"
cp "$package_root/diagnostics/progress_contract.json" "$evidence_root/progress_contract.json"
python3 "$runtime" preflight --package-root "$package_root" >"$evidence_root/package_preflight.json" || exit 5
cp -a "$package_root/workload/." "$cfg_root/"
python3 - "$cfg_root/sca_cfg_D.json" "$attempt" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text(encoding="utf-8"))
for value in d.values(): value["path"]=value["path"].replace("{{attempt}}",sys.argv[2])
p.write_text(json.dumps(d,indent=2,sort_keys=True)+"\\n",encoding="utf-8")
PY
python3 "$runtime" preflight-installed --package-root "$package_root" \
  --cfg-root "$cfg_root" --run-root "$run_root" >"$evidence_root/installed_preflight.json" || exit 6
python3 "$observer_guard" --package-root "$package_root" \
  --manifest "$package_root/TEST_PACKAGE_MANIFEST.json" \
  --runner "$package_root/PREPARE_AND_RUN.sh" >"$evidence_root/observer_precompile.json" || exit 7
python3 "$canonical_tool" self-test >"$evidence_root/canonical_decision_self_test.json" || exit 8
python3 "$stage_tool" self-test --output "$evidence_root/stage_transition_predicate_self_test.json" >/dev/null || exit 8
python3 "$multislice_tool" self-test --output "$evidence_root/multislice_pipeline_predicate_self_test.json" >/dev/null || exit 8
printf 'package_start_epoch_ns=%s\\n' "$(date +%s%N)" >"$evidence_root/host_timing.txt"
printf 'RUNTIME_LAYOUT_COMPILE_START\\n' >"$evidence_root/compile_started.marker"
compile_extra_opts="+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe"
printf 'make -C %q -f Makefile.tb_NDP_Top_new_phy compile RUN_DIR=%q VCS_EXTRA_OPTS=%q\\n' \
  "$server_root" "$compile_root" "$compile_extra_opts" >"$evidence_root/actual_compile_argv.txt"
echo RUNTIME_LAYOUT_COMPILE_START
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h make -C "$server_root" \
  -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 \
  RUN_DIR="$compile_root" VCS_EXTRA_OPTS="$compile_extra_opts" \
  >"$compile_root/sim_results/compile_driver.log" 2>&1
compile_status=$?
cp "$compile_root/sim_results/compile_driver.log" "$run_root/sim_results/compile.log" 2>/dev/null
[ "$compile_status" -eq 0 ] || exit "$compile_status"
cd "$server_root"
simv="$compile_root/sim_results/simv"
sim_args=(-l "$run_root/sim_results/sim.log" +vcs+lic+wait
  "+SCA_CFG=$cfg_root/sca_cfg.json" "+SCA_CFG_D=$cfg_root/sca_cfg_D.json"
  +RETURN_OBSERVER +RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512
  +RETURN_OBS_BP_FACTORS +RETURN_OBS_BP_FACTOR_LIMIT=512
  +RETURN_OBS_RD_DATA_PATH +RETURN_OBS_RD_DATA_PATH_LIMIT=512
  +RETURN_OBS_PREP_COUNT_CAUSE +RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512
  +RETURN_OBS_GA_MSE4_FINAL_PAIR +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512
  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0 +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512
  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256
  +RETURN_OBS_COL_AG_MRM_LANE +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256
  +RETURN_OBS_BUFFER_AG_IDX_QUEUE +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256
  +RETURN_OBS_DBCLK_RD_READY +RETURN_OBS_DBCLK_RD_READY_LIMIT=256
  +RETURN_OBS_LC_SUPPLY_CONSERVATION +RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512
  +RETURN_OBS_STAGE_TRANSITION +RETURN_OBS_STAGE_HEARTBEAT_CYCLES=1048576
  +RETURN_OBS_MULTISLICE_PIPELINE +RETURN_OBS_MULTISLICE_HEARTBEAT_CYCLES=1048576
  "+RETURN_OBS_FILE=$observer_log")
printf 'timeout --foreground --signal=TERM --kill-after=30s 12h %q' "$simv" >"$evidence_root/actual_simulator_argv.txt"
printf ' %q' "${{sim_args[@]}}" >>"$evidence_root/actual_simulator_argv.txt"
printf '\\n' >>"$evidence_root/actual_simulator_argv.txt"
cp "$evidence_root/actual_simulator_argv.txt" "$evidence_root/server_command.txt"
echo RUNTIME_LAYOUT_SIMULATION_START
printf 'RUNTIME_LAYOUT_SIMULATION_START\\n' >"$evidence_root/simulation_started.marker"
timeout --foreground --signal=TERM --kill-after=30s 12h "$simv" "${{sim_args[@]}}" &
sim_pid=$!
progress_sampler &
sampler_pid=$!
wait "$sim_pid"
simulation_status=$?
sim_pid=0
kill "$sampler_pid" 2>/dev/null
wait "$sampler_pid" 2>/dev/null
sampler_pid=0
exit "$simulation_status"
'''


def package_records(package: Path) -> dict[str, object]:
    manifest = package / "TEST_PACKAGE_MANIFEST.json"
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest
    }


def patch_manifest(package: Path, contract: dict[str, object]) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["package_name"] = f"{INSTALL}.zip"
    manifest["return_name"] = f"{INSTALL}_return"
    manifest["test_id"] = "r5-gap-node0071-v48-multislice-pipeline-diagnostic"
    manifest["source_package"] = {
        "install_name": SOURCE,
        "sha256": SOURCE_SHA,
        "return_analysis_sha256": "8b8bbcf9b8f332d90aad3fc39ecf47db90b65e028365fe8a83387bd92151bb6d",
    }
    manifest["rule_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA
    manifest["rule_receipts"]["generation_index_sha256"] = INDEX_SHA
    manifest["active_rtl_identity"] = {
        "authority": "cloud_git_object_and_current_local_sync",
        "commit": RTL_COMMIT,
        "claim_boundary": "actual compiled production identity must return dynamically",
    }
    manifest["multislice_pipeline_information_gain_contract"] = {
        "feature": "MULTISLICE_PIPELINE_STATE_V1",
        "plusarg": "+RETURN_OBS_MULTISLICE_PIPELINE",
        "selected_mask": "0x0000ffff",
        "divergence_mask": "0x0000fffe",
        "checkpoints": [
            "cfg_start",
            "cfg_finish",
            "MSE0 accepted",
            "MSE3 accepted",
            "GA accepted input",
            "GA accepted output",
            "MSE4 request accepted",
            "MSE4 write-data accepted",
            "slice finish",
        ],
        "owner_clocks": {
            "cfg_and_finish": "clk",
            "datapath_acceptance": "clk_sg",
            "rate_limited_reporter": "clk_db",
        },
        "qualified_only": True,
        "stable_level_is_progress": False,
        "emit_limit": 256,
        "candidate_matrix_complete_for_current_boundary": True,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
    }
    manifest["runtime_install_contract"] = {
        "schema": "install-only-v2",
        "only_required_preexisting_parent": "install",
        "package_creates": ["install/cfg_pkg", "install/codex_runs"],
        "cfg_root": f"$server_root/install/cfg_pkg/{INSTALL}",
        "run_root": f"$server_root/install/codex_runs/{INSTALL}/<attempt>",
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "helper_sha256": HELPER_SHA,
    }
    manifest["ndp_root_toplevel_contract"] = {
        "root_direct_name_type_exact_set_unchanged": True,
        "required_preexisting_parents": ["install"],
        "package_creatable_parent_dirs": [
            "install/cfg_pkg",
            "install/codex_runs",
        ],
    }
    computed = contract["_computed"]
    manifest["path_length_budget"] = {
        "declared_target_root_max_chars": 96,
        "longest_projected_relative_path": computed["longest"],
        "longest_projected_relative_path_chars": computed["longest_chars"],
        "max_projected_absolute_path_chars": computed["projected_absolute"],
        "absolute_path_limit_chars": 240,
        "pass": computed["projected_absolute"] <= 240,
    }
    manifest["release_gate_matrix"] = [
        {
            "gate_id": "PACKAGE_BOOTSTRAP_RUNTIME_LAYOUT",
            "applicability": "blocking_applicable_changed_runner_and_sca_transport",
            "status": "PASS_PENDING_FINAL_ZIP_SHARED_VALIDATION",
        },
        {
            "gate_id": "PACKAGE_LOCAL_HDL",
            "applicability": "blocking_applicable_changed_observer",
            "status": "PASS_PENDING_FAMILY_HDL_SCOPE_VALIDATION",
        },
        {
            "gate_id": "DIAGNOSTIC_SEMANTICS",
            "applicability": "blocking_applicable_changed_predicate",
            "status": "PASS_PENDING_EXACT_LOGIC_TRACE",
        },
        {
            "gate_id": "MATERIALIZED_CONFIG",
            "applicability": "receipt_reuse_byte_equal_semantics_mechanical_output_path_only",
            "status": "PASS",
        },
        {
            "gate_id": "RETURN_RESULT_CONTRACT",
            "applicability": "blocking_applicable_changed_return_allowlist",
            "status": "PASS_PENDING_FINAL_ZIP_FAMILY_VALIDATION",
        },
    ]
    manifest["candidate_release"] = False
    manifest["package_class"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["evidence_level"] = "E2_LOCAL_COMPLETE_NODE"
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["numeric_analysis_repeated"] = False
    manifest["sum_or_tail_numeric_reexecuted"] = False
    manifest["functional_rtl_modified"] = False
    additions = [
        {
            "source_root": "evidence",
            "source_path": "multislice_pipeline_decision.json",
            "target_path": "evidence/multislice_pipeline_decision.json",
            "required": True,
            "max_bytes": 65536,
            "missing_meaning": "mask-wide pipeline decision absent or parser failed",
        },
        {
            "source_root": "evidence",
            "source_path": "multislice_pipeline_predicate_self_test.json",
            "target_path": "evidence/multislice_pipeline_predicate_self_test.json",
            "required": True,
            "max_bytes": 32768,
            "missing_meaning": "exact mask-wide predicate trace self-test absent",
        },
    ]
    targets = {item["target_path"] for item in manifest["return_allowlist"]}
    for item in additions:
        if item["target_path"] not in targets:
            manifest["return_allowlist"].append(item)
    for item in manifest["return_allowlist"]:
        if item["target_path"].startswith("readback/"):
            item["source_root"] = "run"
    manifest["budgets"]["return_extracted_max_bytes"] += 98304
    manifest["budgets"]["return_zip_max_bytes"] += 65536
    manifest["files"] = package_records(package)
    write_json(path, manifest)
    manifest["files"] = package_records(package)
    write_json(path, manifest)


def build_directory(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise BuildError(f"refusing to overwrite {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gap-v47-source-") as temp:
        shutil.copytree(extract_source(Path(temp)), package)
    replace_identity(package)
    patch_observer(package)
    rewrite_sca_d(package)
    patch_runtime(package)
    shutil.copyfile(HELPER, package / "package_tools/server_package_runtime_layout.py")
    if sha256(package / "package_tools/server_package_runtime_layout.py") != HELPER_SHA:
        raise BuildError("embedded helper SHA mismatch")
    contract = runtime_contract(package)
    write_json(
        package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        {key: value for key, value in contract.items() if key != "_computed"},
    )
    (package / "PREPARE_AND_RUN.sh").write_text(
        runner_text(), encoding="utf-8", newline="\n"
    )
    write_json(
        package / "provenance/v47_to_v48_multislice_pipeline.json",
        {
            "schema": "gap-node0071-v47-to-v48-multislice-pipeline-v1",
            "source_zip_sha256": SOURCE_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "changed_surface": [
                "fresh identity",
                "read-only mask-wide observer/parser",
                "install-only V2 runner",
                "mechanical SCA-D output namespace",
                "manifest and return allowlist",
            ],
            "frozen": [
                "73 numeric/workload/config/golden files",
                "sum and exact uint8 tail semantics",
                "mapping, bitstream and execplan bytes",
                "timeout",
                "backpressure",
                "functional RTL",
            ],
            "server_action": False,
        },
    )
    (package / "README.md").write_text(
        "# GAP node0071 v48 mask-wide pipeline diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "This fresh successor preserves the v47 workload and observes all "
        "slices 1–15 across config delivery, MSE0/MSE3 acceptance, GA input/"
        "output acceptance, MSE4 request/write-data, and slice finish. "
        "Only `$server_root/install` must pre-exist; the package creates its "
        "isolated cfg/run leaves. No user mkdir is required.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        f"Return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    patch_manifest(package, contract)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package = build_directory(args.output.resolve())
    target = args.output.resolve() / f"{INSTALL}.zip"
    deterministic_zip(package, target)
    digest = sha256(target)
    sidecar = Path(str(target) + ".sha256")
    sidecar.write_text(f"{digest}  {target.name}\n", encoding="ascii", newline="\n")
    result = {
        "package": str(package),
        "zip": str(target),
        "bytes": target.stat().st_size,
        "sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
