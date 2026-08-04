#!/usr/bin/env python3
"""Build the one-command stock-RTL package for the authorized human MAC JSON."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/human_mac_int32_uint8_20260727_v1"
NATIVE = BASE / "nativechain_a/model_execplan/output/mac_int32_uint8_graph"
DATA = BASE / "generated_data"
INSTALL = "human_mac_int32_uint8_v2_stock_rtl_fd1"
OUT = BASE / "server_package" / INSTALL
ZIP = OUT.parent / f"{INSTALL}.zip"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def records(root: Path, exclude_manifest: bool = False) -> dict:
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if exclude_manifest and rel == "TEST_PACKAGE_MANIFEST.json":
            continue
        result[rel] = {"size_bytes": path.stat().st_size, "sha256": sha(path)}
    return result


def rewrite_paths(value: dict) -> dict:
    result = json.loads(json.dumps(value))
    for entry in result.values():
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            old = entry["path"]
            if not old.startswith("install/"):
                raise ValueError(f"unexpected native SCA path: {old}")
            entry["path"] = f"install/cfg_pkg/{INSTALL}/" + old[len("install/"):]
    return result


RUNTIME = r'''#!/usr/bin/env python3
import hashlib, json, sys, zipfile
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()

def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def package_preflight(root):
    m=json.loads((root/"TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    actual={}
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        r=p.relative_to(root).as_posix()
        if r!="TEST_PACKAGE_MANIFEST.json":
            actual[r]={"size_bytes":p.stat().st_size,"sha256":sha(p)}
    checks={
      "candidate_release_false":m.get("candidate_release") is False,
      "human_authored_input":m.get("human_authored_input") is True,
      "rtl_entries_zero":not any(Path(x).suffix.lower() in {".v",".sv",".vh",".svh"} for x in actual),
      "files_exact":actual==m.get("files"),
      "sca_cfg_present":(root/"workload/sca_cfg.json").is_file(),
      "sca_cfg_D_present":(root/"workload/sca_cfg_D.json").is_file(),
    }
    return {"schema":"human-mac-package-preflight-v1","passed":all(checks.values()),"checks":checks}

def analyze(package, installed, evidence):
    scad=json.loads((installed/"sca_cfg_D.json").read_text(encoding="utf-8"))
    rows=[]; first=None
    for i in range(28):
        key=f"op0_matrixD_slice{i}"
        rel=Path(scad[key]["path"]).relative_to(f"install/cfg_pkg/{installed.name}")
        got=installed/rel
        gold=installed/f"golden/op0/slice{i:02d}/matrix_D_linearized_128bit.txt"
        ok=got.is_file() and gold.is_file() and got.read_bytes()==gold.read_bytes()
        row={"slice":i,"readback_present":got.is_file(),"golden_present":gold.is_file(),
             "expected_lines":64,"actual_lines":sum(1 for _ in got.open()) if got.is_file() else None,
             "match":ok,"readback_sha256":sha(got) if got.is_file() else None,
             "golden_sha256":sha(gold) if gold.is_file() else None}
        rows.append(row)
        if not ok and first is None: first=row
    status=json.loads((evidence/"run_status.json").read_text(encoding="utf-8"))
    identities=json.loads((evidence/"identity_gate.json").read_text(encoding="utf-8"))
    passed=status.get("compile_exit")==0 and status.get("sim_exit")==0 and identities.get("passed") and all(r["match"] for r in rows)
    result={"schema":"human-mac-stock-rtl-result-v1","passed":passed,
      "classification":"DYNAMIC_CONFIRMED" if passed else "FIRST_DYNAMIC_FAILURE",
      "dynamic_baseline":"NO_DYNAMIC_BASELINE","first_divergence":first,
      "compile_exit":status.get("compile_exit"),"sim_exit":status.get("sim_exit"),
      "formal_readbacks":rows}
    dump(evidence/"result_gate.json",result)
    return result

def make_return(package, ndp, installed, evidence, name):
    result=analyze(package,installed,evidence)
    ret=ndp/f"{name}_return"; ret.mkdir()
    allow=["package_preflight.json","identity_pre.json","identity_post_compile.json",
           "identity_post_run.json","identity_gate.json","run_status.json",
           "compile.log","sim.log","server_command.txt","result_gate.json"]
    for n in allow:
        p=evidence/n
        if p.is_file():
            q=ret/n; q.write_bytes(p.read_bytes())
    rb=ret/"readback"
    for i in range(28):
        p=installed/f"op0/slice{i:02d}/matrix_D_linearized_128bit.txt"
        if p.is_file():
            q=rb/f"slice{i:02d}.txt"; q.parent.mkdir(parents=True,exist_ok=True); q.write_bytes(p.read_bytes())
    receipt={"schema":"human-mac-return-receipt-v1","install_name":name,
      "package_manifest_sha256":sha(package/"TEST_PACKAGE_MANIFEST.json"),
      "result_gate_passed":result["passed"],"returned_files":[]}
    dump(ret/"RETURN_RECEIPT.json",receipt)
    receipt["returned_files"]=[p.relative_to(ret).as_posix() for p in sorted(ret.rglob("*")) if p.is_file()]
    dump(ret/"RETURN_RECEIPT.json",receipt)
    z=ndp/f"{name}_return.zip"
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as f:
        for p in sorted(x for x in ret.rglob("*") if x.is_file()):
            f.write(p,f"{name}_return/{p.relative_to(ret).as_posix()}")
    (Path(str(z)+".sha256")).write_text(f"{sha(z)}  {z.name}\n",encoding="ascii")
    return 0 if result["passed"] else 1

if __name__=="__main__":
    cmd=sys.argv[1]
    if cmd=="preflight":
        r=package_preflight(Path(sys.argv[2])); dump(Path(sys.argv[3]),r); sys.exit(0 if r["passed"] else 1)
    if cmd=="return":
        sys.exit(make_return(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]),Path(sys.argv[5]),sys.argv[6]))
'''


RUN = f'''#!/usr/bin/env bash
set -u
if [ "$#" -ne 1 ]; then echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2; exit 2; fi
case "$1" in /*) ;; *) echo "NDP_copy path must be absolute" >&2; exit 2;; esac
package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
ndp_root="$(cd "$1" && pwd)"
name="{INSTALL}"
cfg_root="${{ndp_root}}/install/cfg_pkg/${{name}}"
run_dir="${{ndp_root}}/run_${{name}}"
evidence="${{ndp_root}}/evidence_${{name}}"
return_zip="${{ndp_root}}/${{name}}_return.zip"
for x in "$cfg_root" "$run_dir" "$evidence" "${{ndp_root}}/${{name}}_return" "$return_zip" "${{return_zip}}.sha256"; do
  if [ -e "$x" ]; then echo "Fresh target exists: $x" >&2; exit 4; fi
done
for x in tb_NDP_Top_new_phy.sv Makefile.tb_NDP_Top_new_phy rtl/filelists/NDP_Top_phy_filelist.f; do
  if [ ! -f "${{ndp_root}}/$x" ]; then echo "Missing stock input: $x" >&2; exit 3; fi
done
mkdir "$evidence"
python3 "$package_root/package_tools/runtime.py" preflight "$package_root" "$evidence/package_preflight.json" || exit 5
identity() {{
  phase="$1"; out="$2"
  (cd "$ndp_root" && find rtl -type f -print0 | sort -z | xargs -0 sha256sum; \
   cd "$ndp_root" && sha256sum tb_NDP_Top_new_phy.sv Makefile.tb_NDP_Top_new_phy rtl/filelists/NDP_Top_phy_filelist.f) > "$out"
}}
identity pre "$evidence/identity_pre.json"
mkdir -p "${{ndp_root}}/install/cfg_pkg"
cp -a "$package_root/workload" "$cfg_root"
mkdir -p "$run_dir"
cmd="timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=$run_dir VCS_EXTRA_OPTS=+incdir+$ndp_root && timeout --foreground --signal=TERM --kill-after=30s 12h $run_dir/sim_results/simv -l $run_dir/sim_results/sim.log +vcs+lic+wait +sim_time=100ms +BITSTREAM=install/bitstream.txt +SCA_CFG=install/cfg_pkg/$name/sca_cfg.json +SCA_CFG_D=install/cfg_pkg/$name/sca_cfg_D.json"
printf '%s\\n' "$cmd" > "$evidence/server_command.txt"
set +e
(cd "$ndp_root" && timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$run_dir" VCS_EXTRA_OPTS="+incdir+$ndp_root") >"$evidence/compile.log" 2>&1
compile_exit=$?
identity post_compile "$evidence/identity_post_compile.json"
sim_exit=125
if [ "$compile_exit" -eq 0 ]; then
  (cd "$ndp_root" && timeout --foreground --signal=TERM --kill-after=30s 12h "$run_dir/sim_results/simv" -l "$run_dir/sim_results/sim.log" +vcs+lic+wait +sim_time=100ms +BITSTREAM=install/bitstream.txt +SCA_CFG="install/cfg_pkg/$name/sca_cfg.json" +SCA_CFG_D="install/cfg_pkg/$name/sca_cfg_D.json")
  sim_exit=$?
  if [ -f "$run_dir/sim_results/sim.log" ]; then cp "$run_dir/sim_results/sim.log" "$evidence/sim.log"; fi
fi
identity post_run "$evidence/identity_post_run.json"
set -e
same_compile=false; same_run=false
cmp -s "$evidence/identity_pre.json" "$evidence/identity_post_compile.json" && same_compile=true
cmp -s "$evidence/identity_pre.json" "$evidence/identity_post_run.json" && same_run=true
printf '{{"passed":%s,"post_compile_same":%s,"post_run_same":%s}}\\n' "$([ "$same_compile" = true ] && [ "$same_run" = true ] && echo true || echo false)" "$same_compile" "$same_run" > "$evidence/identity_gate.json"
printf '{{"compile_exit":%s,"sim_exit":%s}}\\n' "$compile_exit" "$sim_exit" > "$evidence/run_status.json"
python3 "$package_root/package_tools/runtime.py" return "$package_root" "$ndp_root" "$cfg_root" "$evidence" "$name"
'''


def build() -> None:
    if OUT.exists() or ZIP.exists():
        raise SystemExit(f"refusing to overwrite {OUT} or {ZIP}")
    workload = OUT / "workload"
    workload.mkdir(parents=True)
    sca = rewrite_paths(json.loads((NATIVE / "sca_cfg.json").read_text(encoding="utf-8")))
    scad = rewrite_paths(json.loads((NATIVE / "sca_cfg_D.json").read_text(encoding="utf-8")))
    write(workload / "sca_cfg.json", json.dumps(sca, indent=2) + "\n")
    write(workload / "sca_cfg_D.json", json.dumps(scad, indent=2) + "\n")
    shutil.copy2(NATIVE / "install/execplan.txt", workload / "execplan.txt")
    (workload / "cfg_pkg").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        NATIVE / "install/cfg_pkg/op0_quant_from_buffer_int32MN_uint8MN_bitstream_128b.bin",
        workload / "cfg_pkg/op0_quant_from_buffer_int32MN_uint8MN_bitstream_128b.bin",
    )
    for i in range(28):
        src = DATA / f"install/op0/slice{i:02d}/matrix_A_linearized_128bit.txt"
        dst = workload / f"op0/slice{i:02d}/matrix_A_linearized_128bit.txt"
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
        src = DATA / f"golden/op0/slice{i:02d}/matrix_D_linearized_128bit.txt"
        dst = workload / f"golden/op0/slice{i:02d}/matrix_D_linearized_128bit.txt"
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
    (OUT / "provenance").mkdir(parents=True, exist_ok=True)
    shutil.copy2(BASE / "mac_int32_uint8.original.json", OUT / "provenance/mac_int32_uint8.original.json")
    shutil.copy2(BASE / "mac_int32_uint8.corrected_v2.json", OUT / "provenance/mac_int32_uint8.corrected_v2.json")
    shutil.copy2(NATIVE / "jsons/op0_quant_from_buffer_int32MN_uint8MN.json", OUT / "provenance/address_bound_operator.json")
    write(OUT / "package_tools/runtime.py", RUNTIME)
    write(OUT / "PREPARE_AND_RUN.sh", RUN)
    write(OUT / "README.md", f"# Human MAC stock-RTL test\n\nRun only:\n\n`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`\n\nExpected return: `{INSTALL}_return.zip` and `.sha256` sidecar.\n")
    manifest = {
        "schema": "human-authored-mac-int32-uint8-stock-rtl-package-v1",
        "install_name": INSTALL,
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "human_authored_input": True,
        "functional_rtl_modified": False,
        "package_rtl_entries": 0,
        "function": "D_uint8 = A_int32 * 1 + 1 for 28 independent 32x32 slices",
        "random_seed": 20260727,
        "input_domain": {"dtype": "int32", "inclusive_min": 0, "inclusive_max": 254},
        "source_zip": {"absolute_path": r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\mac.zip", "size_bytes": 1620, "sha256": "7b6770dfe038d5e92b810c20fb4a8a620472afd1dc1e3d6837d4e3af54755a55"},
        "original_candidate": {"path": "provenance/mac_int32_uint8.original.json", "size_bytes": 12123, "sha256": "d98929d1c31b6c55d12ea8b232cf76400024d60ebc29d8d4e39c6e3abc8e4db9"},
        "corrected_candidate": {"path": "provenance/mac_int32_uint8.corrected_v2.json", "size_bytes": 13942, "sha256": "24002ec87abd2e1c5f659003c61aa6176d2d7bd18dbfebeae890e11d80b36eb6"},
        "only_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": f"{INSTALL}_return.zip",
        "return_requires_sidecar": True,
    }
    manifest["files"] = records(OUT, exclude_manifest=True)
    write(OUT / "TEST_PACKAGE_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    (OUT / "PREPARE_AND_RUN.sh").chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in OUT.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(f"{INSTALL}/{path.relative_to(OUT).as_posix()}", (2026, 7, 27, 0, 0, 0))
            info.external_attr = ((0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644) << 16)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
    write(Path(str(ZIP) + ".sha256"), f"{sha(ZIP)}  {ZIP.name}\n")
    print(json.dumps({"package": str(OUT), "zip": str(ZIP), "zip_size": ZIP.stat().st_size, "zip_sha256": sha(ZIP)}, indent=2))


if __name__ == "__main__":
    build()
