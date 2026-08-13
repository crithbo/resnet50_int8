#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

TARGET = ("tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
"u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU."
"u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue")
PHASES = ("PRE", "EDGE", "DELTA_1PS", "QUARTER_250PS", "LATE_750PS")
WIDTHS = {"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,
          "bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7}
PAYLOAD_WIDTH = sum(WIDTHS.values())
LINE = re.compile(
 r"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance=(?P<instance>\S+) time=(?P<time>\d+) mask=1 "
 r"payload=(?P<payload>\S+) payload_known=(?P<payload_known>\S+) payload_width=(?P<payload_width>\S+) "
 r"seq=(?P<seq>\d+) phase=(?P<phase>PRE|EDGE|DELTA_1PS|QUARTER_250PS|LATE_750PS) "
 r"wr=(?P<wr>\S+) full=(?P<full>\S+) all=(?P<all>\S+) valid=(?P<valid>\S+) same=(?P<same>\S+) "
 r"gotten=(?P<gotten>\S+) keep=(?P<keep>\S+) bpmask=(?P<bpmask>\S+) bp=(?P<bp>\S+) "
 r"mode=(?P<mode>\S+) row=(?P<row>\S+) col=(?P<col>\S+) rowtag=(?P<rowtag>\S+) coltag=(?P<coltag>\S+)")

def known(value: str, width: int) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]+", value)) and int(value, 16) < 1 << width

def encoded(event: dict) -> int:
    value = 0
    for name, width in WIDTHS.items(): value = (value << width) | int(event[name], 16)
    return value

def equation(event: dict) -> str:
    expected = 0 if int(event["full"], 16) else int(event["bpmask"], 16)
    return "MATCH" if int(event["bp"], 16) == expected else "MISMATCH"

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--log",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    events=[]; foreign=0; invalid=[]
    for number,line in enumerate(a.log.read_text(encoding="utf-8",errors="replace").splitlines(),1):
        m=LINE.search(line)
        if not m: continue
        event=m.groupdict()
        if event["instance"] != TARGET: foreign += 1; continue
        bad=[n for n,w in WIDTHS.items() if not known(event[n],w)]
        if event["payload_known"] != "1": bad.append("payload_known")
        if event["payload_width"] != str(PAYLOAD_WIDTH): bad.append("payload_width")
        if not known(event["payload"],PAYLOAD_WIDTH): bad.append("payload")
        elif not bad and int(event["payload"],16) != encoded(event): bad.append("payload_named_field_mismatch")
        if bad: invalid.append({"line":number,"fields":bad}); continue
        event["time"]=int(event["time"]); event["seq"]=int(event["seq"]); events.append(event)
    grouped={}; duplicate=False
    for event in events:
        key=(event["instance"],event["seq"]); duplicate |= event["phase"] in grouped.setdefault(key,{})
        grouped[key][event["phase"]]=event
    complete=[row for row in grouped.values() if set(PHASES) <= set(row)]
    classes=[]; witnesses=[]
    for row in complete:
        pre,edge,delta,quarter,late=(row[p] for p in PHASES)
        times=[pre["time"],edge["time"],delta["time"],quarter["time"],late["time"]]
        strictly_edge_free = pre["time"] < edge["time"] < delta["time"] < quarter["time"] < late["time"]
        eq={p:equation(row[p]) for p in PHASES}
        post_stable=all(row["QUARTER_250PS"][f] == row["LATE_750PS"][f] for f in WIDTHS)
        token_changed=any(pre[f] != late[f] for f in ("row","col","rowtag","coltag","mode","gotten"))
        if not strictly_edge_free: cls="PHASE_TIME_COLLISION_FAIL_CLOSED"
        elif eq["LATE_750PS"] == "MISMATCH": cls="PERSISTENT_STABLE_WINDOW_EQUATION_MISMATCH"
        elif eq["PRE"] == "MISMATCH" and eq["LATE_750PS"] == "MATCH": cls="PRE_EDGE_ACK_MISMATCH_SETTLES_AFTER_EDGE"
        elif eq["PRE"] == "MATCH" and eq["LATE_750PS"] == "MATCH" and token_changed: cls="EDGE_LOCAL_TOKEN_TRANSITION_WITH_STABLE_EQUATION"
        elif eq["PRE"] == "MATCH" and eq["LATE_750PS"] == "MATCH": cls="STABLE_EQUATION_NO_TOKEN_TRANSITION"
        else: cls="UNCLASSIFIED_STABLE_PHASE_SEQUENCE"
        classes.append(cls); witnesses.append({"seq":pre["seq"],"times":times,"equation":eq,"post_stable":post_stable,"token_changed":token_changed,"classification":cls})
    if invalid: decision="UNKNOWN_OR_WIDTH_INVALID_PAYLOAD_FAIL_CLOSED"
    elif duplicate: decision="DUPLICATE_PHASE_FAIL_CLOSED"
    elif not grouped: decision="NO_EXACT_TARGET_LIVE_EVENT"
    elif len(complete)!=len(grouped): decision="INCOMPLETE_EXACT_TARGET_PHASE_SEQUENCE"
    elif len(set(classes))!=1: decision="MULTIPLE_TARGET_PHASE_CLASSES"
    else: decision=classes[0]
    result={"schema":"node0004-buffer-ack-stable-phase-decision-v1","decision":decision,"target_instance":TARGET,
      "payload_width_bits":PAYLOAD_WIDTH,"payload_field_widths":WIDTHS,"phases":list(PHASES),"live_event_count":len(events),
      "foreign_event_count":foreign,"unknown_or_width_invalid_count":len(invalid),"unknown_or_width_invalid":invalid,
      "sequence_count":len(grouped),"complete_sequence_count":len(complete),"classes":classes,"witnesses":witnesses,
      "sequences":{str(k[1]):v for k,v in grouped.items()},
      "claim_boundary":"Exact slice13/group1/MSE4 38-bit binary-known stable pre-edge and strictly edge-free post-edge samples only; no natural-terminal, formal-D, numeric, config or RTL claim."}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True))
    valid={"PERSISTENT_STABLE_WINDOW_EQUATION_MISMATCH","PRE_EDGE_ACK_MISMATCH_SETTLES_AFTER_EDGE","EDGE_LOCAL_TOKEN_TRANSITION_WITH_STABLE_EQUATION","STABLE_EQUATION_NO_TOKEN_TRANSITION"}
    return 0 if complete and not duplicate and decision in valid else 2

if __name__ == "__main__": raise SystemExit(main())
