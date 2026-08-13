#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_n71_gap_v41_branch_isolated_config_fix"
NAME = "r5_n71_gap_v46_stage_transition_mask_diag"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
SOURCE_SHA256 = (
    "11dd499aa99b2d2a67220a0d803e1878da8e1d932f51cee1b0e7c3430e957ed6"
)
TRIGGER_RETURN_SHA256 = (
    "01b548c257bc1feefa3c2168f6d68afd7b8a41bab403c6b4abdcaced52e88c34"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-gap-node0071-v46-stage-transition-mask-diag"
)
PACKAGE_FINAL = OUTPUT / "package_final"
ZIP_OUTPUT = OUTPUT / f"{NAME}.zip"
SIDECAR = OUTPUT / f"{NAME}.zip.sha256"
DECISION_TOOL = ROOT / "tools/gap_node0071_stage_transition_decision.py"
CURRENT_RULES = {
    "agent": ROOT / ".agents/agent.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "gap_mac": ROOT / ".agents/rules/GAP_int32_mac_bypass_rules.md",
    "gap_probe": ROOT / ".agents/rules/GAP_probe_v7_validator_rules.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


class BuildError(ValueError):
    pass


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def deterministic_zip(source_root: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
            relative = path.relative_to(source_root.parent).as_posix()
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            if path.name == "PREPARE_AND_RUN.sh":
                info.external_attr = (0o100755 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def replace_text_identity(package: Path) -> None:
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, NAME),
                encoding="utf-8",
                newline="\n",
            )


OBSERVER_EXTENSION = r'''

    // v46: mask-wide stage-transition information-gain observer.
    // The direct-consumer conjunction is sampled in the global manager owner
    // clock.  It is read-only, summary/edge/heartbeat-only, and never drives
    // the DUT, ready, backpressure, timeout, or configuration.
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_valid_mon;
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_ready_mon;
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_local_empty_mon;
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_exec_level_mon;
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_finish_level_mon;
    logic [`EXEC_BIT_WIDTH-1:0] return_obs_gst_global_data_mon;
    logic return_obs_gst_global_empty_mon;
    logic return_obs_gst_global_rd_mon;
    logic return_obs_gst_mask_match_mon;
    logic return_obs_gst_config_match_mon;
    logic return_obs_gst_gconfig_ready_mon;
    logic return_obs_gst_fetch_finish_mon;

    assign return_obs_gst_valid_mon = u_NDP_Top_new.gexec2slice_valid_gc;
    assign return_obs_gst_ready_mon = u_NDP_Top_new.slice2gexec_ready_gc;
    assign return_obs_gst_local_empty_mon =
        u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.local_queue_empty;
    assign return_obs_gst_global_data_mon =
        u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.global_queue_data_out;
    assign return_obs_gst_global_empty_mon =
        u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.global_queue_empty;
    assign return_obs_gst_global_rd_mon =
        u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.global_queue_rd_en;
    assign return_obs_gst_mask_match_mon =
        u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.mask_match;
    assign return_obs_gst_config_match_mon =
        u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.config_match;
    assign return_obs_gst_gconfig_ready_mon =
        u_NDP_Top_new.u_global_ctrl.gconfig2gexec_ready;
    assign return_obs_gst_fetch_finish_mon =
        u_NDP_Top_new.u_global_ctrl.exec_fetch_finish;

    generate
        for (genvar return_obs_gst_group = 0;
             return_obs_gst_group < `SLICE_GROUP_SIZE;
             return_obs_gst_group++) begin : RETURN_OBS_GST_GROUP
            for (genvar return_obs_gst_slice = 0;
                 return_obs_gst_slice < `SLICE_GROUP_NUM;
                 return_obs_gst_slice++) begin : RETURN_OBS_GST_SLICE
                localparam int RETURN_OBS_GST_FLAT =
                    return_obs_gst_group * `SLICE_GROUP_NUM +
                    return_obs_gst_slice;
                assign return_obs_gst_exec_level_mon[RETURN_OBS_GST_FLAT] =
                    return_obs_sem_exec_start_mon
                        [return_obs_gst_group][return_obs_gst_slice];
                assign return_obs_gst_finish_level_mon[RETURN_OBS_GST_FLAT] =
                    return_obs_slice_finish_mon
                        [return_obs_gst_group][return_obs_gst_slice];
            end
        end
    endgenerate

    bit return_obs_gst_enabled;
    longint unsigned return_obs_gst_edge;
    longint unsigned return_obs_gst_emit_count;
    longint unsigned return_obs_gst_heartbeat_cycles;
    logic [255:0] return_obs_gst_prev_surface;
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_prev_exec;
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_prev_finish;
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_exec_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_gst_finish_seen;
    int return_obs_gst_stage_index;

    initial begin
        return_obs_gst_enabled =
            $test$plusargs("RETURN_OBS_STAGE_TRANSITION");
        return_obs_gst_edge = 0;
        return_obs_gst_emit_count = 0;
        return_obs_gst_heartbeat_cycles = 1048576;
        return_obs_gst_prev_surface = '0;
        return_obs_gst_prev_exec = '0;
        return_obs_gst_prev_finish = '0;
        return_obs_gst_exec_seen = '0;
        return_obs_gst_finish_seen = '0;
        return_obs_gst_stage_index = -1;
        return_obs_plusarg_status =
            $value$plusargs(
                "RETURN_OBS_STAGE_HEARTBEAT_CYCLES=%d",
                return_obs_gst_heartbeat_cycles
            );
        #0;
        if (return_obs_enabled && return_obs_gst_enabled &&
            return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "# stage_transition=1 owner_clock=global_clk heartbeat_cycles=%0d selected_mask_expected=0x0000ffff",
                return_obs_gst_heartbeat_cycles
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk) begin
        logic [`GLB_SLICE_NUM-1:0] gst_mask;
        logic [255:0] gst_surface;
        logic [`GLB_SLICE_NUM-1:0] gst_exec_rise;
        logic [`GLB_SLICE_NUM-1:0] gst_finish_rise;
        bit gst_changed;
        bit gst_heartbeat;
        if (!u_NDP_Top_new.rst_n) begin
            return_obs_gst_edge = 0;
            return_obs_gst_emit_count = 0;
            return_obs_gst_prev_surface = '0;
            return_obs_gst_prev_exec = '0;
            return_obs_gst_prev_finish = '0;
            return_obs_gst_exec_seen = '0;
            return_obs_gst_finish_seen = '0;
            return_obs_gst_stage_index = -1;
        end
        else if (
            return_obs_enabled && return_obs_gst_enabled &&
            return_obs_fd != 0
        ) begin
            return_obs_gst_edge++;
            gst_mask = return_obs_gst_global_data_mon
                [3 +: `GLB_SLICE_NUM];
            gst_exec_rise =
                return_obs_gst_exec_level_mon & ~return_obs_gst_prev_exec;
            gst_finish_rise =
                return_obs_gst_finish_level_mon & ~return_obs_gst_prev_finish;
            if (|(gst_exec_rise & gst_mask)) begin
                return_obs_gst_stage_index++;
                return_obs_gst_exec_seen = gst_exec_rise & gst_mask;
                return_obs_gst_finish_seen = '0;
            end
            else begin
                return_obs_gst_exec_seen |= gst_exec_rise & gst_mask;
            end
            return_obs_gst_finish_seen |= gst_finish_rise & gst_mask;
            gst_surface = {
                16'b0,
                return_obs_gst_fetch_finish_mon,
                return_obs_gst_gconfig_ready_mon,
                return_obs_gst_config_match_mon,
                return_obs_gst_mask_match_mon,
                return_obs_gst_global_rd_mon,
                return_obs_gst_global_empty_mon,
                return_obs_gst_global_data_mon[2:0],
                gst_mask,
                return_obs_gst_finish_level_mon,
                return_obs_gst_exec_level_mon,
                return_obs_gst_local_empty_mon,
                return_obs_gst_ready_mon,
                return_obs_gst_valid_mon
            };
            gst_changed = gst_surface != return_obs_gst_prev_surface;
            gst_heartbeat =
                (return_obs_gst_edge % return_obs_gst_heartbeat_cycles) == 0;
            if (
                (gst_changed || gst_heartbeat) &&
                return_obs_gst_emit_count < 128
            ) begin
                return_obs_gst_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | GEXEC_STAGE_TRANSITION_STATE_V1 | event=%s n=%0d edge=%0d stage=%0d opcode=0x%0h mask=0x%0h ready=0x%0h valid=0x%0h local_empty=0x%0h exec_level=0x%0h finish_level=0x%0h exec_seen=0x%0h finish_seen=0x%0h global_empty=%0b global_rd=%0b mask_match=%0b config_match=%0b gconfig_ready=%0b fetch_finish=%0b",
                    $time,
                    (gst_changed ? "EDGE" : "HEARTBEAT"),
                    return_obs_gst_emit_count,
                    return_obs_gst_edge,
                    return_obs_gst_stage_index,
                    return_obs_gst_global_data_mon[2:0],
                    gst_mask,
                    return_obs_gst_ready_mon,
                    return_obs_gst_valid_mon,
                    return_obs_gst_local_empty_mon,
                    return_obs_gst_exec_level_mon,
                    return_obs_gst_finish_level_mon,
                    return_obs_gst_exec_seen,
                    return_obs_gst_finish_seen,
                    return_obs_gst_global_empty_mon,
                    return_obs_gst_global_rd_mon,
                    return_obs_gst_mask_match_mon,
                    return_obs_gst_config_match_mon,
                    return_obs_gst_gconfig_ready_mon,
                    return_obs_gst_fetch_finish_mon
                );
                $fflush(return_obs_fd);
            end
            return_obs_gst_prev_surface = gst_surface;
            return_obs_gst_prev_exec = return_obs_gst_exec_level_mon;
            return_obs_gst_prev_finish = return_obs_gst_finish_level_mon;
        end
    end
'''


def patch_observer(package: Path) -> None:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "GEXEC_STAGE_TRANSITION_STATE_V1" in text:
        raise BuildError("stage-transition observer already present")
    path.write_text(text + OBSERVER_EXTENSION, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/gap_node0071_complete_server_runtime.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("import json\n", "import json\nimport os\n", 1)
    old = '''def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
) -> dict[str, Any]:
    destination = server_root / f"{install_name}_return"
    archive_path = destination.with_suffix(".zip")
    sidecar = Path(str(archive_path) + ".sha256")
    destination.mkdir(parents=True, exist_ok=False)
'''
    new = '''def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
    result_root: Path,
    package_root: Path,
) -> dict[str, Any]:
    result_root.mkdir(parents=True, exist_ok=True)
    final_archive = result_root / f"{install_name}_return.zip"
    final_sidecar = result_root / f"{install_name}_return.zip.sha256"
    if final_archive.exists() or final_sidecar.exists():
        raise RuntimeGateError(f"fixed result target conflict: {final_archive}")
    token = f"{os.getpid()}"
    destination = result_root / f".{install_name}_return.{token}.staging"
    archive_path = result_root / f".{install_name}_return.{token}.zip.staging"
    sidecar = result_root / f".{install_name}_return.{token}.zip.sha256.staging"
    destination.mkdir(parents=False, exist_ok=False)
'''
    if old not in text:
        raise BuildError("runtime collect signature anchor missing")
    text = text.replace(old, new, 1)
    text = text.replace(
        '''        "files": collected,
    }
''',
        '''        "files": collected,
        "fixed_result_publication": {
            "result_directory": "/home/panqs/ndp/simresult",
            "zip_path": f"/home/panqs/ndp/simresult/{install_name}_return.zip",
            "sidecar_path": f"/home/panqs/ndp/simresult/{install_name}_return.zip.sha256",
            "publication_state": "STAGING_VERIFIED_BEFORE_ATOMIC_RENAME",
            "target_sha256_binding": "ADJACENT_SIDECAR_AFTER_ATOMIC_RENAME",
            "duplicate_absent": True,
        },
    }
''',
        1,
    )
    text = text.replace(
        'relative = f"{destination.name}/{path.relative_to(destination).as_posix()}"',
        'relative = f"{install_name}_return/{path.relative_to(destination).as_posix()}"',
        1,
    )
    old_tail = '''    sidecar.write_text(f"{digest}  {archive_path.name}\\n", encoding="ascii")
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        if any(".." in PurePosixPath(name).parts for name in names):
            raise RuntimeGateError("return ZIP path traversal")
    return {
        "zip": str(archive_path),
        "sha256": digest,
        "required_missing": missing,
        "return_manifest": return_manifest,
    }
'''
    new_tail = '''    sidecar.write_text(
        f"{digest}  {final_archive.name}\\n", encoding="ascii"
    )
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        if any(".." in PurePosixPath(name).parts for name in names):
            raise RuntimeGateError("return ZIP path traversal")
        if archive.testzip() is not None:
            raise RuntimeGateError("return ZIP CRC failure")
    if sidecar.read_text(encoding="ascii").split()[0] != digest:
        raise RuntimeGateError("staging sidecar hash mismatch")
    duplicate_paths = [
        server_root / final_archive.name,
        server_root / final_sidecar.name,
        package_root / final_archive.name,
        package_root / final_sidecar.name,
        run_root / final_archive.name,
        run_root / final_sidecar.name,
        cfg_root / final_archive.name,
        cfg_root / final_sidecar.name,
    ]
    if any(path.exists() for path in duplicate_paths):
        raise RuntimeGateError("same-name return duplicate outside fixed result root")
    archive_path.replace(final_archive)
    sidecar.replace(final_sidecar)
    shutil.rmtree(destination)
    if sha256(final_archive) != digest:
        raise RuntimeGateError("published ZIP hash mismatch")
    if final_sidecar.read_text(encoding="ascii").split()[0] != digest:
        raise RuntimeGateError("published sidecar hash mismatch")
    if any(path.exists() for path in duplicate_paths):
        raise RuntimeGateError("post-publish duplicate outside fixed result root")
    return {
        "zip": str(final_archive),
        "sidecar": str(final_sidecar),
        "sha256": digest,
        "required_missing": missing,
        "return_manifest": return_manifest,
        "publication_state": "PUBLISHED_ATOMIC_RENAME",
        "duplicate_absent": True,
    }
'''
    if old_tail not in text:
        raise BuildError("runtime collect tail anchor missing")
    text = text.replace(old_tail, new_tail, 1)
    if (
        'len(allowlist) != 70' not in text
        or text.count('len(allowlist) != 70') != 1
    ):
        raise BuildError("runtime allowlist cardinality anchor missing")
    text = text.replace(
        'len(allowlist) != 70',
        'len(allowlist) != 72',
        1,
    )
    text = text.replace(
        '''    col.add_argument("--cfg-root", type=Path, required=True)
''',
        '''    col.add_argument("--cfg-root", type=Path, required=True)
    col.add_argument("--result-root", type=Path, required=True)
    col.add_argument("--package-root", type=Path, required=True)
''',
        1,
    )
    text = text.replace(
        '''                args.cfg_root,
            )
''',
        '''                args.cfg_root,
                args.result_root,
                args.package_root,
            )
''',
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'install_name="' + NAME + '"',
        '''manifest="$package_root/TEST_PACKAGE_MANIFEST.json"
mapfile -t manifest_identity < <(python3 - "$manifest" <<'PY'
import json, sys
m=json.load(open(sys.argv[1], encoding="utf-8"))
print(m["install_name"])
print(m["return_name"])
PY
)
install_name="${manifest_identity[0]}"
return_name="${manifest_identity[1]}"''',
        1,
    )
    text = text.replace(
        'return_root="$server_root/${install_name}_return"\n',
        'result_root="/home/panqs/ndp/simresult"\n',
        1,
    )
    text = text.replace(
        'canonical_tool="$package_root/package_tools/gap_node0071_canonical_decision.py"\n',
        'canonical_tool="$package_root/package_tools/gap_node0071_canonical_decision.py"\n'
        'stage_tool="$package_root/package_tools/gap_node0071_stage_transition_decision.py"\n',
        1,
    )
    old_targets = '''for target in "$cfg_root" "$run_root" "$evidence_root" "$return_root"   "${return_root}.zip" "${return_root}.zip.sha256"; do
  [ ! -e "$target" ] || { echo "Fresh target required: $target" >&2; exit 4; }
done
'''
    new_targets = '''mkdir -p "$result_root" || exit 3
[ -d "$result_root" ] && [ -w "$result_root" ] || {
  echo "Fixed result directory unavailable: $result_root" >&2; exit 3;
}
result_zip="$result_root/${return_name}.zip"
result_sidecar="$result_root/${return_name}.zip.sha256"
for target in "$cfg_root" "$run_root" "$evidence_root"; do
  [ ! -e "$target" ] || { echo "Fresh target required: $target" >&2; exit 4; }
done
for target in "$result_zip" "$result_sidecar"; do
  [ ! -e "$target" ] || {
    echo "Fixed result target conflict: $target" >&2; exit 4;
  }
done
'''
    if old_targets not in text:
        raise BuildError("runner target anchor missing")
    text = text.replace(old_targets, new_targets, 1)
    text = text.replace(
        'python3 "$canonical_tool" self-test >"$evidence_root/canonical_decision_self_test.json" || exit 8\n',
        'python3 "$canonical_tool" self-test >"$evidence_root/canonical_decision_self_test.json" || exit 8\n'
        'python3 "$stage_tool" self-test --output "$evidence_root/stage_transition_predicate_self_test.json" >/dev/null || exit 9\n',
        1,
    )
    text = text.replace(
        '  +RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512\n',
        '  +RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512\n'
        '  +RETURN_OBS_STAGE_TRANSITION\n'
        '  +RETURN_OBS_STAGE_HEARTBEAT_CYCLES=1048576\n',
        1,
    )
    # The human-readable command receipt contains the same feature exactly once.
    text = text.replace(
        " +RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512 +RETURN_OBS_FILE=",
        " +RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512"
        " +RETURN_OBS_STAGE_TRANSITION"
        " +RETURN_OBS_STAGE_HEARTBEAT_CYCLES=1048576"
        " +RETURN_OBS_FILE=",
        1,
    )
    text = text.replace(
        '''  printf 'signal=%s
compile_status=%s
simulation_status=%s
runner_status=%s
'     "$signal_name" "$compile_status" "$simulation_status" "$runner_status"     >"$evidence_root/signal_status.txt"
''',
        '''  partial=true
  [ "$signal_name" = NONE ] && [ "$simulation_status" -eq 0 ] && partial=false
  printf 'signal=%s
compile_status=%s
simulation_status=%s
runner_status=%s
partial=%s
finalizer_reason=%s
fixed_result_root=%s
'     "$signal_name" "$compile_status" "$simulation_status" "$runner_status" "$partial" "EXIT_OR_SIGNAL" "$result_root"     >"$evidence_root/signal_status.txt"
''',
        1,
    )
    anchor = '''  if [ "$lc_supply_conservation_ok" = true ]; then
    printf 'lc_supply_conservation_enabled=true\\nlc_supply_conservation_limit=512\\nlc_supply_conservation_records_returned=true\\n' >>"$evidence_root/observer_binding.txt"
  else
    printf 'lc_supply_conservation_enabled=false\\nlc_supply_conservation_limit=UNKNOWN\\nlc_supply_conservation_records_returned=false\\n' >>"$evidence_root/observer_binding.txt"
  fi
'''
    addition = anchor + '''  if [ "$observer_ok" = true ] && grep -Fq 'stage_transition=1' "$observer_log" && grep -Fq 'GEXEC_STAGE_TRANSITION_STATE_V1' "$observer_log"; then
    stage_transition_ok=true
  else
    stage_transition_ok=false
  fi
  if [ "$stage_transition_ok" = true ]; then
    printf 'stage_transition_enabled=true\\nstage_transition_records_returned=true\\nstage_transition_owner_clock=global_clk\\n' >>"$evidence_root/observer_binding.txt"
  else
    printf 'stage_transition_enabled=false\\nstage_transition_records_returned=false\\nstage_transition_owner_clock=UNKNOWN\\n' >>"$evidence_root/observer_binding.txt"
  fi
  python3 "$stage_tool" analyze --observer-log "$observer_log" --output "$evidence_root/stage_transition_decision.json" >/dev/null
  stage_decision_status=$?
  [ "$stage_decision_status" -eq 0 ] || printf 'stage_transition_decision_status=%s\\n' "$stage_decision_status" >>"$evidence_root/signal_status.txt"
'''
    if anchor not in text:
        raise BuildError("runner observer-binding anchor missing")
    text = text.replace(anchor, addition, 1)
    old_collect = '''  python3 "$runtime" collect --server-root "$server_root"     --install-name "$install_name" --evidence-root "$evidence_root"     --run-root "$run_root" --cfg-root "$cfg_root"
'''
    new_collect = '''  python3 "$runtime" collect --server-root "$server_root"     --install-name "$install_name" --evidence-root "$evidence_root"     --run-root "$run_root" --cfg-root "$cfg_root"     --result-root "$result_root" --package-root "$package_root"
'''
    if old_collect not in text:
        raise BuildError("runner collect anchor missing")
    text = text.replace(old_collect, new_collect, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_manifest(package: Path) -> dict[str, Any]:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "package_name": NAME,
            "install_name": NAME,
            "run_name": f"run_{NAME}",
            "return_name": f"{NAME}_return",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "evidence_ceiling": "E2_LOCAL_ONLY",
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "source_package": {
                "name": SOURCE_NAME,
                "sha256": SOURCE_SHA256,
                "disposition": "FORMAL_RETURN_CONSUMED",
            },
        }
    )
    manifest["rule_receipts"] = {
        key: sha(path) for key, path in CURRENT_RULES.items()
    }
    fixed_publish_rule = (
        "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001"
    )
    if fixed_publish_rule not in manifest["applicable_rule_ids"]:
        manifest["applicable_rule_ids"].append(fixed_publish_rule)
        manifest["applicable_rule_ids"].sort()
    causal_rtl = [
        Path("NDP_copy01/rtl/NDP_Top_phy.sv"),
        Path("NDP_copy01/rtl/Global/global_ctrl.sv"),
        Path("NDP_copy01/rtl/Global/global_exec_manager.sv"),
        Path("NDP_copy01/rtl/Slice/Slice_Execution_Manager.sv"),
    ]
    manifest["rtl_authority"] = {
        "cloud_commit": "0ccae916ef61904a64d6cf8ec1d1931b45e428d8",
        "local_synced_tree_receipts": {
            relative.as_posix(): {
                "size_bytes": (ROOT / relative).stat().st_size,
                "sha256": sha(ROOT / relative),
            }
            for relative in causal_rtl
        },
        "actual_compiled_identity":
            "MUST_BE_RECOVERED_FROM_FORMAL_SERVER_RETURN",
        "pre_simulation_identity_mismatch_blocking": False,
    }
    manifest["stage_transition_information_gain_contract"] = {
        "feature": "GEXEC_STAGE_TRANSITION_STATE_V1",
        "owner_clock": "u_NDP_Top_new.clk",
        "selected_mask": "0x0000ffff",
        "qualified_or_rate_limited_only": True,
        "event_record_limit": 128,
        "heartbeat_cycles": 1048576,
        "candidate_matrix": {
            "selected_slice_compute_unfinished": [
                "ready",
                "exec_level",
                "finish_seen",
            ],
            "selected_slice_noncompute_ready_low": [
                "ready",
                "exec_level",
                "valid",
            ],
            "local_queue_consumer_pending": [
                "valid",
                "local_empty",
                "ready",
            ],
            "global_config_ready_block": [
                "opcode",
                "gconfig_ready",
                "config_match",
            ],
            "other_global_mask_factor": [
                "mask_match",
                "global_empty",
                "global_rd",
            ],
        },
        "stable_level_counts_as_progress": False,
        "timeout_changed": False,
        "backpressure_changed": False,
        "functional_rtl_changed": False,
    }
    manifest["fixed_result_publication"] = {
        "rule_id": "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
        "server_only_result_root": "/home/panqs/ndp/simresult",
        "zip_path": f"/home/panqs/ndp/simresult/{NAME}_return.zip",
        "sidecar_path": (
            f"/home/panqs/ndp/simresult/{NAME}_return.zip.sha256"
        ),
        "target_conflict": "FAIL_CLOSED_BEFORE_COMPILE",
        "shared_finalizer_paths": [
            "normal",
            "compile_fail",
            "timeout",
            "HUP",
            "INT",
            "TERM",
        ],
        "duplicate_absent_required": True,
        "local_workspace_creation_forbidden": True,
    }
    manifest["release_gate_matrix"] = {
        "single_matrix": True,
        "package_bootstrap_path_runtime_D": {
            "applicability": "applicable",
            "blocking": True,
        },
        "runner_compile_finalizer": {
            "applicability": "applicable_changed_fixed_publisher",
            "blocking": True,
        },
        "package_local_hdl": {
            "applicability": "applicable_changed_observer",
            "blocking": True,
        },
        "materialized_config": {
            "applicability": "receipt_reuse_byte_equal_v41",
            "blocking": False,
        },
        "diagnostic_semantics": {
            "applicability": "applicable_changed_observer_parser",
            "blocking": True,
        },
        "return_result_conjunction": {
            "applicability": "applicable",
            "blocking": True,
        },
        "frozen_numeric_golden": {
            "applicability": "record_only_byte_equality",
            "blocking": False,
        },
    }
    allowlist = manifest["return_allowlist"]
    additions = [
        {
            "source_root": "evidence",
            "source_path": "stage_transition_decision.json",
            "target_path": "evidence/stage_transition_decision.json",
            "required": True,
            "max_bytes": 16384,
            "missing_meaning":
                "stage-transition predicate decision absent or parser failed",
        },
        {
            "source_root": "evidence",
            "source_path": "stage_transition_predicate_self_test.json",
            "target_path": "evidence/stage_transition_predicate_self_test.json",
            "required": True,
            "max_bytes": 32768,
            "missing_meaning":
                "package-local stage predicate self-test absent",
        },
    ]
    existing = {item["target_path"] for item in allowlist}
    for item in additions:
        if item["target_path"] not in existing:
            allowlist.append(item)
    manifest["budgets"]["return_extracted_max_bytes"] += 49152
    manifest["budgets"]["return_zip_max_bytes"] += 32768
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def refresh_manifest_files(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = {
        item.relative_to(package).as_posix(): {
            "size_bytes": item.stat().st_size,
            "sha256": sha(item),
        }
        for item in sorted(path for path in package.rglob("*") if path.is_file())
        if item.name != "TEST_PACKAGE_MANIFEST.json"
    }
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build() -> dict[str, Any]:
    if OUTPUT.exists():
        raise BuildError(f"fresh output already exists: {OUTPUT}")
    if not SOURCE_ZIP.is_file() or sha(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("frozen v41 source ZIP identity mismatch")
    if not DECISION_TOOL.is_file():
        raise BuildError("stage-transition decision tool missing")

    OUTPUT.mkdir(parents=True)
    PACKAGE_FINAL.mkdir()
    with tempfile.TemporaryDirectory(prefix="gap-v46-build-") as temp_name:
        temp = Path(temp_name)
        with zipfile.ZipFile(SOURCE_ZIP) as archive:
            if archive.testzip() is not None:
                raise BuildError("source ZIP CRC failure")
            archive.extractall(temp)
        source = temp / SOURCE_NAME
        package = PACKAGE_FINAL / NAME
        shutil.copytree(source, package)
        replace_text_identity(package)
        shutil.copy2(
            DECISION_TOOL,
            package / "package_tools/gap_node0071_stage_transition_decision.py",
        )
        patch_observer(package)
        patch_runtime(package)
        patch_runner(package)
        patch_manifest(package)
        (package / "README.md").write_text(
            "# GAP node0071 v46 stage-transition mask diagnostic\n\n"
            "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX; candidate_release=false; "
            "evidence<=E2_LOCAL_ONLY.\n\n"
            "Run exactly:\n"
            "`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`\n\n"
            "The server-only return is atomically published as ZIP+sidecar "
            "under `/home/panqs/ndp/simresult`. The package does not create "
            "that path locally. Numeric/config/golden/bitstream/execplan are "
            "byte-equal to v41; only read-only stage-transition observation, "
            "parser, runner publication and identity metadata change.\n",
            encoding="utf-8",
            newline="\n",
        )
        refresh_manifest_files(package)

        deterministic_zip(package, ZIP_OUTPUT)
        second = OUTPUT / "determinism-second.zip"
        deterministic_zip(package, second)
        deterministic_equal = ZIP_OUTPUT.read_bytes() == second.read_bytes()
        second.unlink()
        if not deterministic_equal:
            raise BuildError("deterministic double build differs")
        SIDECAR.write_text(
            f"{sha(ZIP_OUTPUT)}  {ZIP_OUTPUT.name}\n",
            encoding="ascii",
            newline="\n",
        )

    with zipfile.ZipFile(SOURCE_ZIP) as source_archive:
        source_files = {
            name.split("/", 1)[1]: source_archive.read(name)
            for name in source_archive.namelist()
            if name and not name.endswith("/")
        }
    package = PACKAGE_FINAL / NAME
    frozen_prefixes = (
        "workload/input/",
        "workload/golden/",
        "workload/install/bitstream.txt",
        "workload/install/execution_plan.txt",
        "p/v41/configs/",
        "p/v41/mapping/",
    )
    frozen = [
        rel
        for rel in source_files
        if rel.startswith(frozen_prefixes)
        and rel != "TEST_PACKAGE_MANIFEST.json"
    ]
    frozen_equal = all(
        (package / rel).is_file()
        and (package / rel).read_bytes() == source_files[rel]
        for rel in frozen
    )
    numeric = [
        rel
        for rel in source_files
        if rel.startswith("workload/input/")
        or rel.startswith("workload/golden/")
    ]
    manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    report = {
        "schema": "gap-node0071-v46-stage-transition-build-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "package_release": "LOCAL_BUILD_COMPLETE_PENDING_FINAL_AUDIT",
        "source_zip": str(SOURCE_ZIP.relative_to(ROOT)).replace("\\", "/"),
        "source_zip_sha256": sha(SOURCE_ZIP),
        "target_zip": str(ZIP_OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": ZIP_OUTPUT.stat().st_size,
        "target_zip_sha256": sha(ZIP_OUTPUT),
        "sidecar_sha256": sha(SIDECAR),
        "deterministic_double_build_equal": deterministic_equal,
        "frozen_numeric_input_golden_file_count": len(numeric),
        "frozen_numeric_input_golden_byte_equal": all(
            (package / rel).read_bytes() == source_files[rel] for rel in numeric
        ),
        "frozen_config_mapping_bitstream_execplan_member_count": len(frozen),
        "frozen_config_mapping_bitstream_execplan_byte_equal": frozen_equal,
        "changed_observer": True,
        "changed_runner_fixed_result_publication": True,
        "fixed_server_result_root": "/home/panqs/ndp/simresult",
        "local_fixed_server_result_root_created": False,
        "manifest_file_count": len(manifest["files"]),
        "rule_receipts": manifest["rule_receipts"],
    }
    write_json(OUTPUT / "build_report.json", report)
    return report


def main() -> int:
    report = build()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
