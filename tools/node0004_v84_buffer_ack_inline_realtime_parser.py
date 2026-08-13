#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from decimal import Decimal
from pathlib import Path

TARGET=("tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
"u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU."
"u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue")
PHASES=("PRE","EDGE","DELTA_1PS","QUARTER_250PS","LATE_750PS")
ORD={p:i for i,p in enumerate(PHASES)}
WIDTHS={"wr":1,"full":1,"all":1,"valid":2,"same":2,"gotten":2,"keep":2,
        "bpmask":2,"bp":2,"mode":2,"row":2,"col":5,"rowtag":7,"coltag":7,
        "expected":2,"xor":2}
PAYLOAD_WIDTH=sum(WIDTHS.values())
LINE=re.compile(
 r"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_inline_realtime_target instance=(?P<instance>\S+) time=(?P<time>\d+) rt=(?P<rt>\d+(?:\.\d+)?) mask=1 "
 r"payload=(?P<payload>\S+) payload_known=(?P<payload_known>\S+) payload_width=(?P<payload_width>\S+) "
 r"seq=(?P<seq>\d+) phase=(?P<phase>PRE|EDGE|DELTA_1PS|QUARTER_250PS|LATE_750PS) ord=(?P<ord>\d+) "
 r"wr=(?P<wr>\S+) full=(?P<full>\S+) all=(?P<all>\S+) valid=(?P<valid>\S+) same=(?P<same>\S+) "
 r"gotten=(?P<gotten>\S+) keep=(?P<keep>\S+) bpmask=(?P<bpmask>\S+) bp=(?P<bp>\S+) "
 r"mode=(?P<mode>\S+) row=(?P<row>\S+) col=(?P<col>\S+) rowtag=(?P<rowtag>\S+) coltag=(?P<coltag>\S+) expected=(?P<expected>\S+) xor=(?P<xor>\S+)")

def known(value:str,width:int)->bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]+",value)) and int(value,16)<1<<width

def encoded(event:dict)->int:
    value=0
    for name,width in WIDTHS.items(): value=(value<<width)|int(event[name],16)
    return value

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--log",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    events=[];foreign=0;invalid=[]
    for number,line in enumerate(a.log.read_text(encoding="utf-8",errors="replace").splitlines(),1):
        match=LINE.search(line)
        if not match: continue
        event=match.groupdict()
        if event["instance"]!=TARGET: foreign+=1;continue
        bad=[name for name,width in WIDTHS.items() if not known(event[name],width)]
        if event["payload_known"]!="1": bad.append("payload_known")
        if event["payload_width"]!=str(PAYLOAD_WIDTH): bad.append("payload_width")
        if not known(event["payload"],PAYLOAD_WIDTH): bad.append("payload")
        elif not bad and int(event["payload"],16)!=encoded(event): bad.append("payload_named_field_mismatch")
        expected=(0 if int(event["full"],16) else int(event["bpmask"],16))
        if known(event["expected"],2) and int(event["expected"],16)!=expected: bad.append("inline_expected_semantic_mismatch")
        if known(event["xor"],2) and int(event["xor"],16)!=(int(event["bp"],16)^expected): bad.append("inline_xor_semantic_mismatch")
        if int(event["ord"])!=ORD[event["phase"]]: bad.append("phase_ordinal_mismatch")
        if bad: invalid.append({"line":number,"fields":sorted(set(bad))});continue
        event["time"]=int(event["time"]);event["rt"]=Decimal(event["rt"]);event["seq"]=int(event["seq"]);events.append(event)
    grouped={};duplicate=False
    for event in events:
        key=(event["instance"],event["seq"]);duplicate|=event["phase"] in grouped.setdefault(key,{})
        grouped[key][event["phase"]]=event
    complete=[row for row in grouped.values() if set(row)==set(PHASES)]
    classes=[];witnesses=[]
    for row in complete:
        values=[row[p] for p in PHASES];rt=[e["rt"] for e in values]
        if not all(rt[i]<rt[i+1] for i in range(4)): cls="REALTIME_PHASE_ORDER_FAIL_CLOSED"
        elif int(row["LATE_750PS"]["xor"],16)!=0: cls="PERSISTENT_INLINE_RHS_MISMATCH_AT_STABLE_LATE_SAMPLE"
        elif int(row["PRE"]["xor"],16)!=0: cls="PRE_EDGE_MISMATCH_SETTLES_TO_INLINE_RHS"
        elif any(row["PRE"][f]!=row["LATE_750PS"][f] for f in ("row","col","rowtag","coltag","mode","gotten")): cls="TOKEN_TRANSITION_WITH_STABLE_INLINE_RHS"
        else: cls="STABLE_INLINE_RHS_MATCH_NO_TOKEN_TRANSITION"
        classes.append(cls);witnesses.append({"seq":values[0]["seq"],"integer_times":[e["time"] for e in values],"realtimes":[str(x) for x in rt],"xor":[e["xor"] for e in values],"classification":cls})
    if invalid: decision="UNKNOWN_WIDTH_FINGERPRINT_OR_ORDINAL_FAIL_CLOSED"
    elif duplicate: decision="DUPLICATE_PHASE_FAIL_CLOSED"
    elif not grouped: decision="NO_EXACT_TARGET_LIVE_EVENT"
    elif len(complete)!=len(grouped): decision="INCOMPLETE_EXACT_TARGET_PHASE_SEQUENCE"
    elif len(set(classes))!=1: decision="MULTIPLE_TARGET_PHASE_CLASSES"
    else: decision=classes[0]
    result={"schema":"node0004-buffer-ack-inline-realtime-decision-v1","decision":decision,"target_instance":TARGET,
      "payload_width_bits":PAYLOAD_WIDTH,"payload_field_widths":WIDTHS,"phases":list(PHASES),"phase_ordinals":ORD,
      "live_event_count":len(events),"foreign_event_count":foreign,"unknown_or_invalid_count":len(invalid),"invalid":invalid,
      "sequence_count":len(grouped),"complete_sequence_count":len(complete),"classes":classes,"witnesses":witnesses,
      "claim_boundary":"Exact slice13/group1/MSE4 42-bit binary-known inline expected/xor samples with strictly ordered $realtime; no natural-terminal, formal-D, numeric, config, or functional-RTL claim."}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True));valid={"PERSISTENT_INLINE_RHS_MISMATCH_AT_STABLE_LATE_SAMPLE","PRE_EDGE_MISMATCH_SETTLES_TO_INLINE_RHS","TOKEN_TRANSITION_WITH_STABLE_INLINE_RHS","STABLE_INLINE_RHS_MATCH_NO_TOKEN_TRANSITION"}
    return 0 if complete and not duplicate and decision in valid else 2

if __name__=="__main__":raise SystemExit(main())
