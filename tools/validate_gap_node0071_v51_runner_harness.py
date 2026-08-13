#!/usr/bin/env python3
"""Run the exact v51 runner through the existing isolated safe harness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "validate_gap_node0071_v49_runner_harness.py"
INSTALL = "r5_n71_gap_v51_ga_ob_mode_factor_diag"
V52_INSTALL = "r5_n71_gap_v52_ga_read_mse4_direct_diag"
V53_INSTALL = "r5_n71_gap_v53_mse4_route_factor_diag"
V54_INSTALL = "r5_n71_gap_v54_remote_owner_false_accept_diag"


def sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    spec = importlib.util.spec_from_file_location("gap_v49_runner_harness", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.INSTALL = INSTALL
    os.environ["MSYS2_ENV_CONV_EXCL"] = "PATH"

    inherited_write_stubs = module.write_stubs

    def write_stubs(stub: Path, python: Path) -> None:
        inherited_write_stubs(stub, python)
        make = stub / "make"
        text = make.read_text(encoding="utf-8")
        anchor = """# mse4_maskwide=1 selected_mask=0x0000ffff divergence_mask=0x0000fffe owner=clk_sg reporter=clk_db qualified_limit=256
2 | MSE4_MASKWIDE_STATE_V1 | event=QUALIFIED_EDGE n=1 db_cycle=1 ga_rd=0xffff idx_hs=0xffff req=0xffff q_wr=0xffff q_rd=0xffff buf=0xffff prep_wr=0xffff prep_rd=0xffff ob_wr=0xffff ob_rd=0xffff local_req=0xffff local_wdata=0xffff finish=0x0001 idx_v=0x0 req_v=0x0 req_r=0xffff q_full=0x0 q_empty=0xffff buf_v=0x0 buf_r=0xffff hold=0x0 prep_v=0x0 ob_v=0x0 ob_vo=0x0 mem_r=0xffff last=0x0
"""
        addition = anchor + """# ga_ob_conjunction=1 selected_mask=0x0000ffff divergence_mask=0x0000fffe owner=clk_sg reporter=clk_db qualified_limit=256 public_surface=GA_PE.ga_pe_bp_post
3 | GA_OB_CONJ_STATE_V1 | event=QUALIFIED_EDGE n=1 db_cycle=1 wr=0xffff nonempty=0xffff allbp=0xffff rd=0xffff nonempty_now=0x0 allbp_now=0x0 bp0=0x0 bp1=0x0 bp2=0x0 bp3=0x0 bp4=0x0 bp5=0x0 bp6=0x0 bp7=0x0 bp8=0x0 bp9=0x0
# ga_ob_mode_factor=1 selected_mask=0x0000ffff owner=clk_sg reporter=clk_db qualified_limit=128 heartbeat_cycles=1048576 private_xmr_target=GA_PE_Outbuffer.sv
4 | GA_OB_MODE_FACTOR_STATE_V1 | event=QUALIFIED_EDGE n=1 db_cycle=1 alu_req=0xffff normal_mode=0xffff transout_mode=0x0 normal_hs=0xffff transout_hs=0x0 selected_wr=0xffff nonempty=0xffff selected_rd=0xffff
"""
        if INSTALL in (V52_INSTALL, V53_INSTALL, V54_INSTALL):
            addition += """# ga_read_mse4_direct=1 selected_mask=0x0000ffff owner=clk_sg reporter=clk_db qualified_limit=320 heartbeat_cycles=1048576 reused_package_local_surfaces=1
5 | GA_READ_MSE4_DIRECT_V1 | event=QUALIFIED_EDGE n=1 db_cycle=1 mode_normal=0xffff mode_transout=0x0 selected_wr=0xffff nonempty=0xffff selected_rd=0xffff m4_idx=0xffff m4_req=0xffff m4_q_wr=0xffff m4_q_rd=0xffff m4_buf=0xffff m4_prep_wr=0xffff m4_prep_rd=0xffff m4_ob_wr=0xffff m4_ob_rd=0xffff m4_local_req=0xffff m4_local_wdata=0xffff finish=0xffff
"""
        if INSTALL in (V53_INSTALL, V54_INSTALL):
            fields = (
                "ob_rd", *(f"{name}_hs{ch}" for name in ("pre_req","pre_wdata","local_req","local_wdata","global_req_in","global_wdata_in","global_req_out","global_wdata_out") for ch in range(2)), "finish", "remote",
                *(f"{name}_{kind}{ch}" for name in ("pre_req","pre_wdata","local_req","local_wdata","global_req_in","global_wdata_in","global_req_out","global_wdata_out") for kind in ("v","r") for ch in range(2)),
            )
            values = {name: "ffff" for name in fields}
            values["remote"] = "0"
            addition += "# mse4_route_factor=1 selected_mask=0x0000ffff owner=clk_sg reporter=clk_db qualified_limit=384 factor_limit=128 heartbeat_cycles=1048576 state_or_heartbeat_is_progress=0 private_xmr=slice2hub_crossbar_fifo_only\n"
            addition += "6 | MSE4_ROUTE_FACTOR_V1 | event=QUALIFIED_EDGE qn=1 fn=1 db_cycle=1 " + " ".join(f"{name}=0x{values[name]}" for name in fields) + "\n"
        if INSTALL == V54_INSTALL:
            progress=("m4_req_hs0","m4_req_hs1","m4_w_hs0","m4_w_hs1","g_req_wr0","g_req_wr1","g_w_wr0","g_w_wr1","finish")
            violation=("remote_collision","req_owner_mismatch0","req_owner_mismatch1","w_owner_mismatch0","w_owner_mismatch1","req_no_fifo_write0","req_no_fifo_write1","w_no_fifo_write0","w_no_fifo_write1")
            factor=tuple(f"remote{i}" for i in range(5))+tuple(f"owner{i}" for i in range(5))+tuple(f"mse{i}_{kind}{ch}" for i in range(5) for kind in ("req_v","req_r","w_v","w_r") for ch in range(2))+tuple(f"g_{kind}{ch}" for kind in ("req_v","req_r","w_v","w_r") for ch in range(2))
            all_fields=progress+violation+factor
            addition += "# remote_owner_false_accept=1 selected_mask=0x0000ffff owner=clk_sg reporter=clk_db qualified_limit=384 violation_limit=64 factor_limit=128 heartbeat_cycles=1048576 nonprogress_events=VIOLATION_EDGE,FACTOR_EDGE,HEARTBEAT\n"
            addition += "7 | REMOTE_OWNER_FALSE_ACCEPT_V1 | event=QUALIFIED_EDGE qn=1 vn=0 fn=0 db_cycle=1 " + " ".join(f"{name}=0xffff" for name in all_fields) + "\n"
        if text.count(anchor) != 1:
            raise RuntimeError("safe simulator observer anchor differs")
        make.write_text(
            text.replace(anchor, addition, 1), encoding="utf-8", newline="\n"
        )
        mkdir = stub / "mkdir"
        mkdir.write_text(
            """#!/usr/bin/bash
set -u
parents=0
paths=()
for arg in "$@"; do
  case "$arg" in
    -p|--parents) parents=1 ;;
    --) ;;
    -*) exit 64 ;;
    *) paths+=("$arg") ;;
  esac
done
[ "${#paths[@]}" -gt 0 ] || exit 64
python3 - "$parents" "${paths[@]}" <<'PY'
import pathlib,sys
parents=sys.argv[1]=="1"
for raw in sys.argv[2:]:
    pathlib.Path(raw).mkdir(parents=parents,exist_ok=parents)
PY
""",
            encoding="utf-8",
            newline="\n",
        )
        mkdir.chmod(0o755)

    module.write_stubs = write_stubs
    def map_harness(package: Path, result_root: Path) -> None:
        runner = package / "PREPARE_AND_RUN.sh"
        text = runner.read_text(encoding="utf-8")
        if module.FIXED_ROOT not in text:
            raise ValueError("production fixed result path absent")
        text = text.replace(module.FIXED_ROOT, module.msys(result_root))
        prefix = "#!/usr/bin/env bash\n"
        harness_path = module.msys(package.parent / "stub") + ":/usr/bin:/bin"
        text = text.replace(
            prefix, prefix + f"export PATH={harness_path!r}\n", 1
        )
        runner.write_text(text, encoding="utf-8", newline="\n")
        helper_path = package / "package_tools/server_package_runtime_layout.py"
        helper = helper_path.read_text(encoding="utf-8")
        anchor = (
            "def _shell_output(receipt: dict[str, Any], "
            "receipt_path: Path | None) -> str:\n"
        )
        temp_literal = str(Path(tempfile.gettempdir()).resolve())
        addition = (
            "def _harness_msys(value: object) -> str:\n"
            "    text = str(value)\n"
            f"    temp = {temp_literal!r}\n"
            "    norm = text.replace('\\\\', '/')\n"
            "    temp_norm = temp.replace('\\\\', '/')\n"
            "    if norm.lower().startswith(temp_norm.lower() + '/'):\n"
            "        return '/tmp/' + norm[len(temp_norm)+1:]\n"
            "    if len(text) >= 3 and text[1] == ':' and "
            "text[2] in '/\\\\':\n"
            "        return '/' + text[0].lower() + "
            "text[2:].replace('\\\\', '/')\n"
            "    return text\n\n\n"
            + anchor
        )
        if helper.count(anchor) != 1:
            raise ValueError("helper shell formatter anchor differs")
        helper = helper.replace(anchor, addition, 1)
        token = 'f"{key}={shlex.quote(str(value))}"'
        if helper.count(token) != 1:
            raise ValueError("helper shell value anchor differs")
        helper_path.write_text(
            helper.replace(
                token, 'f"{key}={shlex.quote(_harness_msys(value))}"', 1
            ),
            encoding="utf-8",
            newline="\n",
        )
        module.refresh_manifest(package)

    module.map_harness = map_harness
    inherited_run_case = module.run_case

    def run_case(*args, **kwargs):
        row = inherited_run_case(*args, **kwargs)
        root = args[1]
        result = root / "simresult"
        zips = sorted(result.glob(f"{INSTALL}_r*_return.zip"))
        sidecars = [Path(str(path) + ".sha256") for path in zips]
        valid = (
            len(zips) == 1
            and len(sidecars) == 1
            and sidecars[0].is_file()
            and sidecars[0].read_text(encoding="ascii").split()
            == [sha(zips[0]), zips[0].name]
        )
        row["finalizer_reached"] = len(zips) == 1
        row["fixed_result_return_published"] = len(zips) == 1
        row["partial_return_published"] = (
            kwargs.get("name") != "normal" and len(zips) == 1
        )
        row["return_zip"] = (
            f"{module.FIXED_ROOT}/{zips[0].name}" if zips else None
        )
        row["return_sidecar"] = (
            f"{module.FIXED_ROOT}/{sidecars[0].name}" if sidecars else None
        )
        row["sidecar_valid"] = valid
        evidence = list(
            (root / "server/install/codex_runs").glob(
                f"{INSTALL}/*/evidence"
            )
        )
        if evidence:
            status = evidence[0] / "decision_parser_status.txt"
            stderr = evidence[0] / "decision_parser_stderr.log"
            row["decision_parser_status"] = (
                status.read_text(encoding="utf-8", errors="replace")
                if status.is_file() else None
            )
            row["decision_parser_stderr"] = (
                stderr.read_text(encoding="utf-8", errors="replace")
                if stderr.is_file() else None
            )
        return row

    module.run_case = run_case
    result = int(module.main())

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--output", type=Path, required=True)
    known, _ = ap.parse_known_args()
    report = json.loads(known.output.read_text(encoding="utf-8"))
    normal = report["scenarios"]["normal"]
    expected = {
        "stage_transition=0",
        "multislice_pipeline=0",
        "mse4_maskwide=0",
        "ga_ob_conjunction=0",
        "ga_ob_mode_factor=0",
        "canonical=0",
    }
    if INSTALL in (V52_INSTALL, V53_INSTALL, V54_INSTALL):
        expected.add("ga_read_mse4_direct=0")
    if INSTALL in (V53_INSTALL, V54_INSTALL):
        expected.add("mse4_route_factor=0")
    if INSTALL == V54_INSTALL:
        expected.add("remote_owner_false_accept=0")
    observed = set((normal.get("decision_parser_status") or "").splitlines())
    report["checks"]["normal_all_decision_parsers_exit_zero"] = (
        expected <= observed
    )
    report["checks"]["normal_decision_parser_stderr_empty"] = (
        normal.get("decision_parser_stderr") == ""
    )
    report["valid"] = all(report["checks"].values())
    report["errors"] = [
        key for key, value in report["checks"].items() if not value
    ]
    report["schema"] = (
        "gap-node0071-v54-runner-harness-v1" if INSTALL == V54_INSTALL else
        "gap-node0071-v53-runner-harness-v1" if INSTALL == V53_INSTALL else
        "gap-node0071-v52-runner-harness-v1" if INSTALL == V52_INSTALL else
        "gap-node0071-v51-runner-harness-v1"
    )
    known.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0 if report["valid"] and result == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
