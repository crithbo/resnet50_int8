from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_n71_gap_v49_mse4_maskwide_diag"
INSTALL = "r5_n71_gap_v50_ga_ob_conjunction_diag"
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
SOURCE_SHA = "eb2f5f02b3dce69aad51a3319972622b7cff8d594ef9cbf5909efb7c4114d85a"
RETURN_SHA = "ec3811f7024e8b2ce4e90681d7d9faffbc8f4c5509d3da91ea69d4b9eb86314d"
RETURN_REPORT_SHA = "78d199a04a3dee6b2e0ff4a57870c1ae6963ce5a56da1f8f98c347e46886306e"
SERVER_RULE_SHA = "a8f628413367805d5fe9822233b39460e5386b1ecaf321ba050546a96cd843d8"
INDEX_SHA = "bded239d169c4768ca0c54e93a90eeb0a9285955252995afaf098322a00bd688"


def load_v49():
    path = ROOT / "tools/build_gap_node0071_v49_mse4_maskwide_diag.py"
    spec = importlib.util.spec_from_file_location("gap_v49_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v49 builder utilities")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V49 = load_v49()


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return V49.sha(path)


def write_json(path: Path, value: object) -> None:
    V49.write_json(path, value)


def deterministic_zip(source: Path, target: Path) -> None:
    V49.deterministic_zip(source, target)


def extract(destination: Path) -> Path:
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("source v49 SHA mismatch")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("source v49 CRC failure")
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
        if not path.is_file():
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

    // v50: all-slice GA outbuffer read-conjunction information gain.
    // Qualified sticky masks are owned by clk_sg.  Current level masks are
    // reporter-only state and never monotonic progress.  The only new XMR
    // consumes the public GA_PE ga_pe_bp_post input port.
    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_DST_NUM-1:0]
          return_obs_v50_ga_bp_post_mon;
    generate
        for (genvar return_obs_v50_g = 0;
             return_obs_v50_g < `SLICE_GROUP_SIZE;
             return_obs_v50_g++) begin : RETURN_OBS_V50_G
            for (genvar return_obs_v50_s = 0;
                 return_obs_v50_s < `SLICE_GROUP_NUM;
                 return_obs_v50_s++) begin : RETURN_OBS_V50_S
                for (genvar return_obs_v50_r = 0;
                     return_obs_v50_r < `GA_ROW_PE_NUM;
                     return_obs_v50_r++) begin : RETURN_OBS_V50_R
                    assign return_obs_v50_ga_bp_post_mon
                        [return_obs_v50_g][return_obs_v50_s]
                        [return_obs_v50_r][0] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_v50_g]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_v50_s]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[return_obs_v50_r].GA_COL_PE[0].GA_PE
                        .u_GA_PE.ga_pe_bp_post;
                    assign return_obs_v50_ga_bp_post_mon
                        [return_obs_v50_g][return_obs_v50_s]
                        [return_obs_v50_r][1] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[return_obs_v50_g]
                        .u_slice_with_datahub_mc_group.slice_group_gen[return_obs_v50_s]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[return_obs_v50_r].GA_COL_PE[2].GA_PE
                        .u_GA_PE.ga_pe_bp_post;
                end
            end
        end
    endgenerate

    logic [`GLB_SLICE_NUM-1:0] return_obs_v50_wr_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v50_nonempty_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v50_allbp_seen;
    logic [`GLB_SLICE_NUM-1:0] return_obs_v50_rd_seen;
    logic [4*`GLB_SLICE_NUM-1:0] return_obs_v50_prev_qualified;
    logic [12*`GLB_SLICE_NUM-1:0] return_obs_v50_prev_state;
    bit return_obs_v50_enabled;
    longint unsigned return_obs_v50_db_cycles;
    longint unsigned return_obs_v50_emit_count;

    initial begin
        return_obs_v50_enabled =
            $test$plusargs("RETURN_OBS_GA_OB_CONJUNCTION");
        return_obs_v50_db_cycles = 0;
        return_obs_v50_emit_count = 0;
        return_obs_v50_prev_qualified = '0;
        return_obs_v50_prev_state = '0;
        #0;
        if (return_obs_enabled && return_obs_v50_enabled &&
            return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "# ga_ob_conjunction=1 selected_mask=0x0000ffff divergence_mask=0x0000fffe owner=clk_sg reporter=clk_db qualified_limit=256 public_surface=GA_PE.ga_pe_bp_post"
            );
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin
        if (!u_NDP_Top_new.rst_n_sg) begin
            return_obs_v50_wr_seen <= '0;
            return_obs_v50_nonempty_seen <= '0;
            return_obs_v50_allbp_seen <= '0;
            return_obs_v50_rd_seen <= '0;
        end
        else if (return_obs_enabled && return_obs_v50_enabled) begin
            for (int g = 0; g < `SLICE_GROUP_SIZE; g++) begin
                for (int s = 0; s < `SLICE_GROUP_NUM; s++) begin
                    bit any_wr, any_nonempty, any_allbp, any_rd;
                    int id;
                    id = g * `SLICE_GROUP_NUM + s;
                    any_wr = 1'b0;
                    any_nonempty = 1'b0;
                    any_allbp = 1'b0;
                    any_rd = 1'b0;
                    for (int r = 0; r < `GA_ROW_PE_NUM; r++) begin
                        for (int slot = 0; slot < 2; slot++) begin
                            any_wr |= return_obs_pair_ga_normal_wr_hs_mon
                                [g][s][r][slot];
                            any_nonempty |=
                                return_obs_ga_ob_count_mon[g][s][r][slot] != 0;
                            any_allbp |=
                                (return_obs_ga_ob_count_mon[g][s][r][slot] != 0) &&
                                (&return_obs_v50_ga_bp_post_mon[g][s][r][slot]);
                            any_rd |= return_obs_pair_ga_normal_rd_hs_mon
                                [g][s][r][slot];
                        end
                    end
                    if (any_wr) return_obs_v50_wr_seen[id] <= 1'b1;
                    if (any_nonempty) return_obs_v50_nonempty_seen[id] <= 1'b1;
                    if (any_allbp) return_obs_v50_allbp_seen[id] <= 1'b1;
                    if (any_rd) return_obs_v50_rd_seen[id] <= 1'b1;
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        logic [`GLB_SLICE_NUM-1:0] nonempty_now, allbp_now;
        logic [`GA_PE_DST_NUM-1:0][`GLB_SLICE_NUM-1:0] bp_all_dest;
        logic [4*`GLB_SLICE_NUM-1:0] qualified_snapshot;
        logic [12*`GLB_SLICE_NUM-1:0] state_snapshot;
        bit changed;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_v50_db_cycles = 0;
            return_obs_v50_emit_count = 0;
            return_obs_v50_prev_qualified = '0;
            return_obs_v50_prev_state = '0;
        end
        else if (return_obs_enabled && return_obs_v50_enabled &&
                 return_obs_fd != 0) begin
            return_obs_v50_db_cycles++;
            nonempty_now = '0;
            allbp_now = '0;
            bp_all_dest = '1;
            for (int g = 0; g < `SLICE_GROUP_SIZE; g++) begin
                for (int s = 0; s < `SLICE_GROUP_NUM; s++) begin
                    int id;
                    bit has_nonempty;
                    logic [`GA_PE_DST_NUM-1:0] dest_all;
                    id = g * `SLICE_GROUP_NUM + s;
                    has_nonempty = 1'b0;
                    dest_all = '1;
                    for (int r = 0; r < `GA_ROW_PE_NUM; r++) begin
                        for (int slot = 0; slot < 2; slot++) begin
                            if (return_obs_ga_ob_count_mon[g][s][r][slot] != 0) begin
                                has_nonempty = 1'b1;
                                dest_all &= return_obs_v50_ga_bp_post_mon
                                    [g][s][r][slot];
                            end
                        end
                    end
                    nonempty_now[id] = has_nonempty;
                    if (!has_nonempty) dest_all = '0;
                    allbp_now[id] = has_nonempty && (&dest_all);
                    for (int d = 0; d < `GA_PE_DST_NUM; d++)
                        bp_all_dest[d][id] = dest_all[d];
                end
            end
            qualified_snapshot = {
                return_obs_v50_rd_seen,
                return_obs_v50_allbp_seen,
                return_obs_v50_nonempty_seen,
                return_obs_v50_wr_seen
            };
            state_snapshot = {
                bp_all_dest, allbp_now, nonempty_now
            };
            changed = qualified_snapshot != return_obs_v50_prev_qualified ||
                      state_snapshot != return_obs_v50_prev_state;
            if (changed && return_obs_v50_emit_count < 256) begin
                return_obs_v50_emit_count++;
                $fdisplay(
                    return_obs_fd,
                    "%0t | GA_OB_CONJ_STATE_V1 | event=%s n=%0d db_cycle=%0d wr=0x%0h nonempty=0x%0h allbp=0x%0h rd=0x%0h nonempty_now=0x%0h allbp_now=0x%0h bp0=0x%0h bp1=0x%0h bp2=0x%0h bp3=0x%0h bp4=0x%0h bp5=0x%0h bp6=0x%0h bp7=0x%0h bp8=0x%0h bp9=0x%0h",
                    $time,
                    (qualified_snapshot != return_obs_v50_prev_qualified ?
                     "QUALIFIED_EDGE" : "STATE_EDGE"),
                    return_obs_v50_emit_count,
                    return_obs_v50_db_cycles,
                    return_obs_v50_wr_seen,
                    return_obs_v50_nonempty_seen,
                    return_obs_v50_allbp_seen,
                    return_obs_v50_rd_seen,
                    nonempty_now, allbp_now,
                    bp_all_dest[0], bp_all_dest[1], bp_all_dest[2],
                    bp_all_dest[3], bp_all_dest[4], bp_all_dest[5],
                    bp_all_dest[6], bp_all_dest[7], bp_all_dest[8],
                    bp_all_dest[9]
                );
                $fflush(return_obs_fd);
            end
            return_obs_v50_prev_qualified = qualified_snapshot;
            return_obs_v50_prev_state = state_snapshot;
        end
    end
'''


PARSER = r'''from __future__ import annotations
import argparse,json,re
from pathlib import Path
Q=("wr","nonempty","allbp","rd")
S=("nonempty_now","allbp_now","bp0","bp1","bp2","bp3","bp4",
   "bp5","bp6","bp7","bp8","bp9")
FIELDS=Q+S
PATTERN=re.compile(r"GA_OB_CONJ_STATE_V1\s+\|\s+event=(QUALIFIED_EDGE|STATE_EDGE).*?"+
    r"\s".join(fr"{name}=0x([0-9a-fA-F]+)" for name in FIELDS))
def decide(text:str)->dict:
    rows=[]
    for line in text.splitlines():
        m=PATTERN.search(line)
        if m:
            rows.append({"event":m.group(1),**{
              name:int(m.group(i+2),16) for i,name in enumerate(FIELDS)}})
    last={name:0 for name in FIELDS}
    for row in rows:
        for name in FIELDS:last[name]=row[name]
    per=[]
    for sl in range(16):
        q={name:bool(last[name]&(1<<sl)) for name in Q}
        first=next((name for name in Q if not q[name]),None)
        blocked=[d for d in range(10) if not (last[f"bp{d}"]&(1<<sl))]
        per.append({"slice":sl,"qualified":q,
                    "first_missing_qualified":first,
                    "blocked_destination_indices_now":blocked})
    return {
      "schema":"gap-node0071-ga-ob-conjunction-decision-v1",
      "feature_enabled_marker":"# ga_ob_conjunction=1" in text,
      "record_count":len(rows),
      "qualified_record_count":sum(x["event"]=="QUALIFIED_EDGE" for x in rows),
      "last_qualified_masks":{n:f"0x{last[n]:04x}" for n in Q},
      "last_state_masks":{n:f"0x{last[n]:04x}" for n in S},
      "per_slice":per,
      "candidate_matrix":{
        "PRODUCER_WRITE":["wr"],
        "OUTBUFFER_NONEMPTY":["nonempty","nonempty_now"],
        "DOWNSTREAM_ALL_DESTINATIONS_READY":["allbp","allbp_now"]+
          [f"bp{d}" for d in range(10)],
        "READ_HANDSHAKE":["rd"]},
      "claim_boundary":"Qualified sticky events only; state masks never count as progress."
    }
def self_test()->dict:
    marker="# ga_ob_conjunction=1\n"
    def line(event,wr,nonempty,allbp,rd):
      return (
        f"1 | GA_OB_CONJ_STATE_V1 | event={event} n=1 db_cycle=1 "
        f"wr=0x{wr:x} nonempty=0x{nonempty:x} allbp=0x{allbp:x} rd=0x{rd:x} "
        f"nonempty_now=0x{nonempty:x} allbp_now=0x{allbp:x} "
        "bp0=0x1 bp1=0x1 bp2=0x1 bp3=0x1 bp4=0x1 "
        "bp5=0x1 bp6=0x1 bp7=0x1 bp8=0x1 bp9=0x1")
    before=decide(marker+line("QUALIFIED_EDGE",0,0,0,0))
    after_wr=decide(marker+line("QUALIFIED_EDGE",1,0,0,0))
    after_nonempty=decide(marker+line("QUALIFIED_EDGE",1,1,0,0))
    after_allbp=decide(marker+line("QUALIFIED_EDGE",1,1,1,0))
    simultaneous=decide(marker+line("QUALIFIED_EDGE",3,3,1,1))
    stable=decide(marker+line("STATE_EDGE",3,3,1,1))
    checks={
      "before_first_write":before["per_slice"][0]["first_missing_qualified"]=="wr",
      "after_write_first_nonempty":
        after_wr["per_slice"][0]["first_missing_qualified"]=="nonempty",
      "after_nonempty_first_allbp":
        after_nonempty["per_slice"][0]["first_missing_qualified"]=="allbp",
      "after_allbp_first_read":
        after_allbp["per_slice"][0]["first_missing_qualified"]=="rd",
      "simultaneous_slice0_complete":
        simultaneous["per_slice"][0]["first_missing_qualified"] is None,
      "simultaneous_slice1_first_allbp":
        simultaneous["per_slice"][1]["first_missing_qualified"]=="allbp",
      "stable_state_not_qualified":stable["qualified_record_count"]==0,
      "feature_bound":simultaneous["feature_enabled_marker"],
      "marker_removed_fails_closed":
        not decide(line("QUALIFIED_EDGE",1,1,1,1))["feature_enabled_marker"],
    }
    return {"schema":"gap-node0071-ga-ob-conjunction-self-test-v1",
            "checks":checks,"pass":all(checks.values())}
def main():
    p=argparse.ArgumentParser(); sp=p.add_subparsers(dest="cmd",required=True)
    a=sp.add_parser("analyze"); a.add_argument("--observer-log",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    s=sp.add_parser("self-test"); s.add_argument("--output",type=Path,required=True)
    ns=p.parse_args()
    value=self_test() if ns.cmd=="self-test" else decide(
      ns.observer_log.read_text(encoding="utf-8",errors="replace")
      if ns.observer_log.is_file() else "")
    ns.output.write_text(json.dumps(value,indent=2,sort_keys=True)+chr(10),
                         encoding="utf-8")
    return 0 if (value.get("pass",True) and
      (ns.cmd=="self-test" or value["feature_enabled_marker"])) else 1
if __name__=="__main__": raise SystemExit(main())
'''


def patch_observer(package: Path) -> None:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "GA_OB_CONJ_STATE_V1" in text:
        raise BuildError("v50 observer already present")
    path.write_text(text + OBSERVER_EXTENSION, encoding="utf-8", newline="\n")
    (package / "package_tools/gap_node0071_ga_ob_conjunction_decision.py").write_text(
        PARSER, encoding="utf-8", newline="\n"
    )


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = (
        'mse4mask_tool="$package_root/package_tools/'
        'gap_node0071_mse4_maskwide_decision.py"'
    )
    if anchor not in text:
        raise BuildError("v49 mse4 tool anchor absent")
    text = text.replace(
        anchor,
        anchor + '\ngaob_tool="$package_root/package_tools/'
        'gap_node0071_ga_ob_conjunction_decision.py"',
        1,
    )
    text = text.replace(
        "       grep -Fq 'MSE4_MASKWIDE_STATE_V1' \"$observer_log\"; then",
        "       grep -Fq 'MSE4_MASKWIDE_STATE_V1' \"$observer_log\" &&\n"
        "       grep -Fq 'ga_ob_conjunction=1' \"$observer_log\" &&\n"
        "       grep -Fq 'GA_OB_CONJ_STATE_V1' \"$observer_log\"; then",
        1,
    )
    text = text.replace(
        "mse4_maskwide_records_returned=true\\n'",
        "mse4_maskwide_records_returned=true\\n"
        "ga_ob_conjunction_enabled=true\\n"
        "ga_ob_conjunction_records_returned=true\\n'",
        1,
    )
    text = text.replace(
        "mse4_maskwide_records_returned=false\\n'",
        "mse4_maskwide_records_returned=false\\n"
        "ga_ob_conjunction_enabled=false\\n"
        "ga_ob_conjunction_records_returned=false\\n'",
        1,
    )
    parser_anchor = (
        'python3 "$mse4mask_tool" analyze --observer-log "$observer_log" '
        '--output "$evidence_root/mse4_maskwide_decision.json" '
        '>/dev/null 2>&1 || true'
    )
    if parser_anchor not in text:
        raise BuildError("v49 parser anchor absent")
    replacement = parser_anchor + "\n" + (
        '      python3 "$gaob_tool" analyze --observer-log "$observer_log" '
        '--output "$evidence_root/ga_ob_conjunction_decision.json" '
        '>/dev/null 2>&1 || true'
    )
    text = text.replace(parser_anchor, replacement, 1)
    parser_commands = [
        (
            "stage_transition",
            'python3 "$stage_tool" analyze --observer-log "$observer_log" '
            '        --output "$evidence_root/stage_transition_decision.json" '
            '>/dev/null 2>&1 || true',
        ),
        (
            "multislice_pipeline",
            'python3 "$multislice_tool" analyze --observer-log "$observer_log" '
            '        --output "$evidence_root/multislice_pipeline_decision.json" '
            '>/dev/null 2>&1 || true',
        ),
        (
            "mse4_maskwide",
            parser_anchor,
        ),
        (
            "ga_ob_conjunction",
            'python3 "$gaob_tool" analyze --observer-log "$observer_log" '
            '--output "$evidence_root/ga_ob_conjunction_decision.json" '
            '>/dev/null 2>&1 || true',
        ),
        (
            "canonical",
            'python3 "$canonical_tool" observe --observer-log "$observer_log" '
            '        --sim-log "$run_root/sim_results/sim.log" '
            '--signal "$signal_name"         '
            '--simulation-status "$simulation_status" '
            '--stall-window-cycles 1048576         '
            '--heartbeat-cycles 262144 '
            '--manifest "$package_root/TEST_PACKAGE_MANIFEST.json"         '
            '--output "$evidence_root/canonical_decision.json" '
            '>/dev/null 2>&1 || true',
        ),
    ]
    for index, (label, old_command) in enumerate(parser_commands):
        if old_command not in text:
            raise BuildError(f"{label} parser receipt anchor absent")
        command = old_command.replace(" >/dev/null 2>&1 || true", "")
        command = command.replace(">/dev/null 2>&1 || true", "")
        prefix = ""
        if index == 0:
            prefix = (
                ': >"$evidence_root/decision_parser_stderr.log"\n'
                '      : >"$evidence_root/decision_parser_status.txt"\n'
            )
        new_command = (
            prefix + command
            + f' >/dev/null 2>>"$evidence_root/decision_parser_stderr.log"\n'
            + f'      printf "{label}=%s\\n" "$?" '
            '>>"$evidence_root/decision_parser_status.txt"'
        )
        text = text.replace(old_command, new_command, 1)
    fallback_args = (
        'python3 - "$evidence_root/stage_transition_decision.json"       '
        '"$evidence_root/multislice_pipeline_decision.json"       '
        '"$evidence_root/mse4_maskwide_decision.json"       '
        '"$evidence_root/canonical_decision.json" "$signal_name" '
        '"$simulation_status" <<\'PY\''
    )
    if fallback_args not in text:
        raise BuildError("v49 fallback anchor absent")
    text = text.replace(
        fallback_args,
        'python3 - "$evidence_root/stage_transition_decision.json"       '
        '"$evidence_root/multislice_pipeline_decision.json"       '
        '"$evidence_root/mse4_maskwide_decision.json"       '
        '"$evidence_root/ga_ob_conjunction_decision.json"       '
        '"$evidence_root/canonical_decision.json" "$signal_name" '
        '"$simulation_status" <<\'PY\'',
        1,
    )
    text = text.replace(
        '{"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',
        '{"schema":"gap-node0071-ga-ob-conjunction-decision-v1","status":"FAIL_CLOSED",\n'
        '     "reason":reason,"natural_terminal":False},\n'
        '    {"schema":"canonical-diagnostic-decision-v1","decision":"FAIL_CLOSED",',
        1,
    )
    text = text.replace(
        '"signal":sys.argv[5],"simulation_status":int(sys.argv[6]),',
        '"signal":sys.argv[6],"simulation_status":int(sys.argv[7]),',
        1,
    )
    text = text.replace(
        "for name,payload in zip(sys.argv[1:5],payloads):",
        "for name,payload in zip(sys.argv[1:6],payloads):",
        1,
    )
    selftest_anchor = (
        'python3 "$mse4mask_tool" self-test --output '
        '"$evidence_root/mse4_maskwide_predicate_self_test.json" '
        '>/dev/null || exit 8'
    )
    if selftest_anchor not in text:
        raise BuildError("v49 self-test anchor absent")
    text = text.replace(
        selftest_anchor,
        selftest_anchor + '\npython3 "$gaob_tool" self-test --output '
        '"$evidence_root/ga_ob_conjunction_predicate_self_test.json" '
        '>/dev/null || exit 8',
        1,
    )
    text = text.replace(
        "+RETURN_OBS_MSE4_MASKWIDE_HEARTBEAT_CYCLES=1048576",
        "+RETURN_OBS_MSE4_MASKWIDE_HEARTBEAT_CYCLES=1048576\n"
        "  +RETURN_OBS_GA_OB_CONJUNCTION",
        1,
    )
    visibility_anchor = 'attempt="a$$"\n\n'
    if text.count(visibility_anchor) != 1:
        raise BuildError("runner error visibility insertion anchor differs")
    text = text.replace(
        visibility_anchor,
        visibility_anchor
        + """runner_fail() {
  code="$1"
  shift
  message="$*"
  printf 'RUNNER_ERROR package=%s code=%s message=%s\\n' \\
    "$package_id" "$code" "$message" >&2
  exit "$code"
}

""",
        1,
    )
    early_failures = {
        '  exit 2\nfi': '  runner_fail 2 "expected exactly one absolute server root argument"\nfi',
        'case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac':
            'case "$1" in /*) ;; *) runner_fail 2 "server root argument is not absolute";; esac',
        '  command -v "$tool" >/dev/null 2>&1 || exit 3':
            '  command -v "$tool" >/dev/null 2>&1 || runner_fail 3 "required runtime tool is unavailable: $tool"',
        'package_root="$(cd "$package_root" && pwd -P)" || exit 2':
            'package_root="$(cd "$package_root" && pwd -P)" || runner_fail 2 "package root cannot be resolved"',
        'server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2':
            'server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server root cannot be resolved"',
        'mkdir -p -- "$result_root" || exit 9':
            'mkdir -p -- "$result_root" || runner_fail 9 "fixed result root cannot be created"',
        '[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9':
            '[ -d "$result_root" ] && [ -w "$result_root" ] || runner_fail 9 "fixed result root is not writable"',
        '[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || exit 10':
            '[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || runner_fail 10 "fixed return target already exists"',
        'ndp_pre_snapshot="$(root_snapshot)" || exit 12':
            'ndp_pre_snapshot="$(root_snapshot)" || runner_fail 12 "NDP root pre-snapshot failed"',
        'layout_values="$(python3 "$layout_helper" prepare   --server-root "$server_root" --package-id "$package_id"   --install-name "$install_name" --attempt "$attempt" --format shell)" || exit 13':
            'layout_values="$(python3 "$layout_helper" prepare   --server-root "$server_root" --package-id "$package_id"   --install-name "$install_name" --attempt "$attempt" --format shell)" || runner_fail 13 "install-subtree layout preparation failed"',
        'python3 "$runtime" preflight --package-root "$package_root" >"$evidence_root/package_preflight.json" || exit 5':
            'python3 "$runtime" preflight --package-root "$package_root" >"$evidence_root/package_preflight.json" || runner_fail 5 "package manifest preflight failed"',
        'python3 "$runtime" preflight-installed --package-root "$package_root"   --cfg-root "$cfg_root" --run-root "$run_root" >"$evidence_root/installed_preflight.json" || exit 6':
            'python3 "$runtime" preflight-installed --package-root "$package_root"   --cfg-root "$cfg_root" --run-root "$run_root" >"$evidence_root/installed_preflight.json" || runner_fail 6 "installed payload preflight failed"',
        'python3 "$observer_guard" --package-root "$package_root"   --manifest "$package_root/TEST_PACKAGE_MANIFEST.json"   --runner "$package_root/PREPARE_AND_RUN.sh" >"$evidence_root/observer_precompile.json" || exit 7':
            'python3 "$observer_guard" --package-root "$package_root"   --manifest "$package_root/TEST_PACKAGE_MANIFEST.json"   --runner "$package_root/PREPARE_AND_RUN.sh" >"$evidence_root/observer_precompile.json" || runner_fail 7 "observer binding precompile guard failed"',
        'python3 "$canonical_tool" self-test >"$evidence_root/canonical_decision_self_test.json" || exit 8':
            'python3 "$canonical_tool" self-test >"$evidence_root/canonical_decision_self_test.json" || runner_fail 8 "canonical decision self-test failed"',
        'python3 "$stage_tool" self-test --output "$evidence_root/stage_transition_predicate_self_test.json" >/dev/null || exit 8':
            'python3 "$stage_tool" self-test --output "$evidence_root/stage_transition_predicate_self_test.json" >/dev/null || runner_fail 8 "stage-transition predicate self-test failed"',
        'python3 "$multislice_tool" self-test --output "$evidence_root/multislice_pipeline_predicate_self_test.json" >/dev/null || exit 8':
            'python3 "$multislice_tool" self-test --output "$evidence_root/multislice_pipeline_predicate_self_test.json" >/dev/null || runner_fail 8 "multislice predicate self-test failed"',
        'python3 "$mse4mask_tool" self-test --output "$evidence_root/mse4_maskwide_predicate_self_test.json" >/dev/null || exit 8':
            'python3 "$mse4mask_tool" self-test --output "$evidence_root/mse4_maskwide_predicate_self_test.json" >/dev/null || runner_fail 8 "MSE4 maskwide predicate self-test failed"',
        'python3 "$gaob_tool" self-test --output "$evidence_root/ga_ob_conjunction_predicate_self_test.json" >/dev/null || exit 8':
            'python3 "$gaob_tool" self-test --output "$evidence_root/ga_ob_conjunction_predicate_self_test.json" >/dev/null || runner_fail 8 "GA outbuffer conjunction predicate self-test failed"',
    }
    for old, new in early_failures.items():
        if text.count(old) != 1:
            raise BuildError(f"runner early failure anchor differs: {old}")
        text = text.replace(old, new, 1)
    final_exit = '  exit "$final"\n}'
    if text.count(final_exit) != 1:
        raise BuildError("runner final status anchor differs")
    text = text.replace(
        final_exit,
        "  printf 'RUNNER_FINAL_STATUS package=%s exit=%s\\n' "
        '"$package_id" "$final" >&2\n'
        + final_exit,
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/gap_node0071_complete_server_runtime.py"
    text = path.read_text(encoding="utf-8")
    if "len(allowlist) != 77" not in text:
        raise BuildError("v49 allowlist count anchor absent")
    path.write_text(
        text.replace("len(allowlist) != 77", "len(allowlist) != 81", 1),
        encoding="utf-8",
        newline="\n",
    )


def records(package: Path) -> dict[str, object]:
    manifest = package / "TEST_PACKAGE_MANIFEST.json"
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest
    }


def patch_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["package_name"] = f"{INSTALL}.zip"
    manifest["return_name"] = f"{INSTALL}_return"
    manifest["test_id"] = "r5-gap-node0071-v50-ga-outbuffer-conjunction-diagnostic"
    manifest["source_package"] = {
        "install_name": SOURCE,
        "sha256": SOURCE_SHA,
        "return_sha256": RETURN_SHA,
        "return_analysis_sha256": RETURN_REPORT_SHA,
    }
    manifest["rule_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA
    manifest["rule_receipts"]["generation_index_sha256"] = INDEX_SHA
    manifest["ga_outbuffer_conjunction_contract"] = {
        "feature": "GA_OB_CONJ_STATE_V1",
        "plusarg": "+RETURN_OBS_GA_OB_CONJUNCTION",
        "selected_mask": "0x0000ffff",
        "divergence_mask": "0x0000fffe",
        "qualified_chain": [
            "normal-mode outbuffer write handshake",
            "outbuffer nonempty",
            "all downstream destinations ready",
            "normal-mode outbuffer read handshake",
        ],
        "destination_ready_width": 10,
        "owner_clock": "clk_sg",
        "reporter_clock": "clk_db",
        "emit_limit": 256,
        "stable_level_is_progress": False,
        "public_surface": "GA_PE.ga_pe_bp_post input port",
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
    }
    manifest["decision_parser_receipt_contract"] = {
        "required_status": "evidence/decision_parser_status.txt",
        "required_stderr": "evidence/decision_parser_stderr.log",
        "shared_signal_and_exit_finalizer": True,
        "fail_closed": True,
    }
    additions = [
        {
            "source_root": "evidence",
            "source_path": "ga_ob_conjunction_decision.json",
            "target_path": "evidence/ga_ob_conjunction_decision.json",
            "required": True,
            "max_bytes": 65536,
            "missing_meaning": "GA outbuffer conjunction decision absent or parser failed",
        },
        {
            "source_root": "evidence",
            "source_path": "ga_ob_conjunction_predicate_self_test.json",
            "target_path": "evidence/ga_ob_conjunction_predicate_self_test.json",
            "required": True,
            "max_bytes": 32768,
            "missing_meaning": "GA outbuffer conjunction predicate self-test absent",
        },
        {
            "source_root": "evidence",
            "source_path": "decision_parser_status.txt",
            "target_path": "evidence/decision_parser_status.txt",
            "required": True,
            "max_bytes": 4096,
            "missing_meaning": "signal-finalizer decision parser status absent",
        },
        {
            "source_root": "evidence",
            "source_path": "decision_parser_stderr.log",
            "target_path": "evidence/decision_parser_stderr.log",
            "required": True,
            "max_bytes": 65536,
            "missing_meaning": "signal-finalizer decision parser stderr receipt absent",
        },
    ]
    targets = {row["target_path"] for row in manifest["return_allowlist"]}
    for row in additions:
        if row["target_path"] not in targets:
            manifest["return_allowlist"].append(row)
    manifest["budgets"]["return_extracted_max_bytes"] += 167936
    manifest["budgets"]["return_zip_max_bytes"] += 98304
    attempt = "a" * 10
    longest = (
        f"install/codex_runs/{INSTALL}/{attempt}/"
        "sim_results/return_observer/return_observer.log"
    )
    root_max = int(
        manifest["path_length_budget"]["declared_target_root_max_chars"]
    )
    manifest["path_length_budget"]["longest_projected_relative_path"] = longest
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(
        longest
    )
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = (
        root_max + 1 + len(longest)
    )
    manifest["release_gate_matrix"] = [
        {
            "gate_id": "PACKAGE_BOOTSTRAP_RUNTIME_LAYOUT",
            "applicability": "blocking_applicable_identity_and_runner_changed",
            "status": "PASS_PENDING_FINAL_ZIP_SHARED_VALIDATION",
        },
        {
            "gate_id": "PACKAGE_LOCAL_HDL",
            "applicability": "blocking_applicable_observer_changed",
            "status": "PASS_PENDING_FAMILY_HDL_SCOPE_VALIDATION",
        },
        {
            "gate_id": "DIAGNOSTIC_SEMANTICS",
            "applicability": "blocking_applicable_predicate_changed",
            "status": "PASS_PENDING_EXACT_TRACE",
        },
        {
            "gate_id": "MATERIALIZED_CONFIG",
            "applicability": "receipt_reuse_byte_equal",
            "status": "PASS",
        },
        {
            "gate_id": "RETURN_RESULT_CONTRACT",
            "applicability": "blocking_applicable_finalizer_and_allowlist_changed",
            "status": "PASS_PENDING_SIGNAL_FINALIZER_VALIDATION",
        },
        {
            "gate_id": "FROZEN_NUMERIC_GOLDEN",
            "applicability": "record_only_byte_equal",
            "status": "PASS",
        },
    ]
    manifest["candidate_release"] = False
    manifest["package_class"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["evidence_level"] = "E2_LOCAL_COMPLETE_NODE"
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["numeric_analysis_repeated"] = False
    manifest["sum_or_tail_numeric_reexecuted"] = False
    manifest["functional_rtl_modified"] = False
    manifest["files"] = records(package)
    write_json(path, manifest)
    manifest["files"] = records(package)
    write_json(path, manifest)


def patch_runtime_contract(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    additions = contract["path_budget"]["additional_projected_paths"]
    additions.extend([
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/"
        "ga_ob_conjunction_decision.json",
        f"install/codex_runs/{INSTALL}/{{attempt}}/evidence/"
        "decision_parser_stderr.log",
    ])
    attempt = "a" * int(contract["path_budget"]["attempt_max_chars"])
    projected = {
        f"install/cfg_pkg/{INSTALL}/"
        + item.relative_to(package / "workload").as_posix()
        for item in (package / "workload").rglob("*")
        if item.is_file()
    } | {item.replace("{attempt}", attempt) for item in additions}
    longest = max(projected, key=lambda item: (len(item), item))
    root_max = int(contract["path_budget"]["declared_target_root_max_chars"])
    contract["path_budget"]["max_projected_absolute_path_chars"] = (
        root_max + 1 + len(longest)
    )
    write_json(path, contract)


def build(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise BuildError(f"refusing to overwrite {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gap-v49-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    patch_runtime_contract(package)
    old = package / "provenance/v48_to_v49_mse4_maskwide.json"
    if old.exists():
        old.unlink()
    write_json(
        package / "provenance/v49_to_v50_ga_ob_conjunction.json",
        {
            "schema": "gap-node0071-v49-to-v50-ga-ob-conjunction-v1",
            "source_zip_sha256": SOURCE_SHA,
            "return_sha256": RETURN_SHA,
            "return_analysis_sha256": RETURN_REPORT_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "changed_surface": [
                "fresh identity",
                "read-only all-slice GA outbuffer conjunction observer/parser",
                "signal-finalizer decision parser status/stderr receipts",
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
        "# GAP node0071 v50 GA outbuffer conjunction diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "This successor preserves the v49 workload and established checkpoints. "
        "It distinguishes GA outbuffer write/nonempty from the all-destination "
        "backpressure/read-request conjunction and read handshake for all slices. "
        "It also returns decision-parser status and stderr from the shared signal "
        "and EXIT finalizer. Stable levels never count as progress.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh "
        "/absolute/path/to/NDP_copy0x`\n\n"
        f"Return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    patch_manifest(package)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    package = build(output)
    target = output / f"{INSTALL}.zip"
    deterministic_zip(package, target)
    digest = sha(target)
    sidecar = Path(str(target) + ".sha256")
    sidecar.write_text(
        f"{digest}  {target.name}\n", encoding="ascii", newline="\n"
    )
    print(json.dumps({
        "package": str(package),
        "zip": str(target),
        "bytes": target.stat().st_size,
        "sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha(sidecar),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
