from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.audit_node0004_v78_final_zip as base


PACKAGE = "r5_n4_hw_v79_buffer_ack_equation_diag"


def main() -> int:
    ap=argparse.ArgumentParser()
    for name in ('zip','build-report','source-bound-report','post-sim-report','temporal-report','input-owner-report','ack-equation-report','runner-report','return-contract-report','shared-layout-report','prior-first-fresh-report','output'):
        ap.add_argument('--'+name,required=True,type=Path)
    a=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='n4v79_audit_') as raw:
        intermediate=Path(raw)/'base.json'
        old=sys.argv; base.PACKAGE=PACKAGE
        try:
            sys.argv=['audit-v79','--zip',str(a.zip),'--build-report',str(a.build_report),'--source-bound-report',str(a.source_bound_report),'--post-sim-report',str(a.post_sim_report),'--temporal-report',str(a.temporal_report),'--input-owner-report',str(a.input_owner_report),'--runner-report',str(a.runner_report),'--return-contract-report',str(a.return_contract_report),'--shared-layout-report',str(a.shared_layout_report),'--prior-first-fresh-report',str(a.prior_first_fresh_report),'--output',str(intermediate)]
            base_rc=base.main()
        finally:
            sys.argv=old
        report=json.loads(intermediate.read_text(encoding='utf-8'))
    eq=json.loads(a.ack_equation_report.read_text(encoding='utf-8'))
    with zipfile.ZipFile(a.zip) as z:
        names=set(z.namelist()); prefix=PACKAGE+'/'
        new_members=all(prefix+x in names for x in ('package_tools/node0004_v79_post_sim_plugin.py','package_tools/buffer_input_ack_equation_parser.py','diagnostics/source_bound_probe_plan.json','tb_probe/source_bound_causal_observer.svh','contracts/server_post_sim_return_request.json'))
    report['schema']='conv-node0004-v79-final-zip-audit-v1'
    report['checks']['v79_equation_products_bound']=new_members
    report['checks']['ack_equation_predicate_and_negatives']=eq.get('pass') is True
    report['release_gate_matrix']['changed_observer_collector_parser']['pass'] = report['release_gate_matrix']['changed_observer_collector_parser']['pass'] and new_members and eq.get('pass') is True
    report['report_receipts']['ack_equation']={'path':str(a.ack_equation_report),'bytes':a.ack_equation_report.stat().st_size,'sha256':base.sha(a.ack_equation_report)}
    errors=[k for k,v in report['checks'].items() if not v]
    report['errors']=errors; report['FINAL_ZIP_RULE_SELF_AUDIT_PASS']=not errors
    report['claim_boundary']='Exact final v79 package, generated same-instance Buffer_AG equation boundary, parser negatives and unchanged shared gates only; no server run, natural terminal, formal D, E4 or E5 claim.'
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'pass':not errors,'errors':errors,'base_rc':base_rc})); return 0 if not errors else 1


if __name__=='__main__': raise SystemExit(main())
