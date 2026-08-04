#!/usr/bin/env python3
"""Mechanically adapt the frozen fd2 human-MAC package to a variable server root."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ZIP = (
    ROOT
    / "artifacts/human_mac_int32_uint8_20260727_v1/server_package"
    / "human_mac_int32_uint8_v3_stock_rtl_fd2.zip"
)
SOURCE_ZIP_SHA256 = "5bcc26c80a995063b6b8c071eea4962426dd0547d782df771c61cf1fa3024e52"
SOURCE_PREFIX = "human_mac_int32_uint8_v3_stock_rtl_fd2/"
SOURCE_INSTALL = SOURCE_PREFIX.rstrip("/")
INSTALL = "human_mac_int32_uint8_v3_runtime_root_v2"
DEFAULT_OUT = (
    ROOT
    / "artifacts/human_mac_int32_uint8_20260727_v1/runtime_root_v2_adaptation"
)
SEMANTIC_PREFIXES = ("workload/", "provenance/")
FORBIDDEN_ADAPTATION_TOKENS = (
    "NDP_" + "copy01",
    "NDP_" + "copy02",
    "NDP_" + "copy03",
    "/NDP_" + "copy",
    "find " + "rtl",
    "find " + "./rtl",
    "sha256sum " + "tb_",
    "git " + "status",
    "git " + "rev-parse",
    "README_HARDWARE_" + "SIM_ENTRY",
    "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b" + "042d7",
)

READ_RECEIPT = [
    {
        "path": ".agents/agent.md",
        "sha256": "5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0",
        "reason": "lane and write boundaries",
    },
    {
        "path": ".agents/plan.md",
        "sha256": "581ee5b55d2d5b1df36d8cfc2937e3a3822c1108c835cbd8669c9d80820d22fe",
        "reason": "current family state",
    },
    {
        "path": ".agents/rules/生成前必读索引.md",
        "sha256": "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7",
        "reason": "generation routing",
    },
    {
        "path": ".agents/rules/算子配置规则.md",
        "sha256": "f7e3f80e7fb4edd2b42d7ff41a70bba55abfde6797013648dfedccdc6385e023",
        "reason": "frozen workload provenance",
    },
    {
        "path": ".agents/rules/NDP硬件字段语义.md",
        "sha256": "a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59",
        "reason": "preserved MAC semantic payload",
    },
    {
        "path": ".agents/rules/GAP_int32_mac_bypass_rules.md",
        "sha256": "f53fecb9106705d113354b4ab81356cbdc8179e602b2f7e584390bafe57e67a8",
        "reason": "human MAC family dynamic boundary",
    },
    {
        "path": ".agents/rules/服务器测试包生成规则.md",
        "sha256": "72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524",
        "reason": "variable-root compatibility profile",
    },
]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def safe_member(name: str) -> str:
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError(f"unsafe source ZIP member: {name}")
    if not name.startswith(SOURCE_PREFIX):
        raise ValueError(f"unexpected source ZIP root: {name}")
    rel = name[len(SOURCE_PREFIX) :]
    if not rel or rel.endswith("/"):
        raise ValueError(f"unexpected non-file ZIP member: {name}")
    return rel


def source_files() -> dict[str, bytes]:
    if sha(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise ValueError("frozen fd2 ZIP identity mismatch")
    with zipfile.ZipFile(SOURCE_ZIP) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate source ZIP member")
        return {safe_member(name): z.read(name) for name in names}


def derive_execution_fragments(source_runner: str) -> tuple[str, str]:
    """Extract, rather than reinvent, the fd2 compile/simulation command."""
    match = re.search(r'^cmd="(.+)"$', source_runner, flags=re.MULTILINE)
    if not match:
        raise ValueError("source runner command receipt not found")
    combined = match.group(1)
    parts = combined.split(" && ", 1)
    if len(parts) != 2:
        raise ValueError("source runner compile/simulation split is ambiguous")
    compile_cmd, sim_cmd = parts
    if "$name" not in sim_cmd:
        raise ValueError("source runner command does not carry its frozen install binding")
    return compile_cmd, sim_cmd


RUNTIME = r'''#!/usr/bin/env python3
import hashlib, json, os, sys, zipfile
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""): h.update(b)
    return h.hexdigest()

def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+"\n",encoding="utf-8",newline="\n")

def records(root,exclude=()):
    out={}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError(f"symlink forbidden: {p}")
        if p.is_file():
            r=p.relative_to(root).as_posix()
            if r not in exclude:
                out[r]={"size_bytes":p.stat().st_size,"sha256":sha(p)}
    return out

def package_preflight(root):
    m=json.loads((root/"TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    actual=records(root,{"TEST_PACKAGE_MANIFEST.json"})
    forbidden=("NDP_"+"copy01","NDP_"+"copy02","NDP_"+"copy03","/NDP_"+"copy",
      "find "+"rtl","find "+"./rtl","sha256sum "+"tb_","git "+"status","git "+"rev-parse",
      "README_HARDWARE_"+"SIM_ENTRY",
      "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b"+"042d7")
    scanned={}
    hits=[]
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        rel=p.relative_to(root).as_posix()
        data=p.read_bytes()
        scanned[rel]=hashlib.sha256(data).hexdigest()
        for token in forbidden:
            if token.encode() in data:
                hits.append({"path":rel,"token":token})
    source_name=m["source_package"]["install_name"]
    sca=json.loads((root/"workload/sca_cfg.json").read_text(encoding="utf-8"))
    scad=json.loads((root/"workload/sca_cfg_D.json").read_text(encoding="utf-8"))
    prefix=f"install/cfg_pkg/{source_name}/"
    path_contract=True
    for obj in list(sca.values())+list(scad.values()):
        if isinstance(obj,dict) and isinstance(obj.get("path"),str):
            p=PurePosixPath(obj["path"])
            if p.is_absolute() or ".." in p.parts or not obj["path"].startswith(prefix):
                path_contract=False
    payload_ok=True
    for rel,rec in m["preserved_semantic_payload"].items():
        p=root/rel
        payload_ok &= p.is_file() and p.stat().st_size==rec["size_bytes"] and sha(p)==rec["sha256"]
    checks={
      "candidate_release_false":m.get("candidate_release") is False,
      "version_unbound":m.get("result_profile")=="VERSION_UNBOUND_DIAGNOSTIC_ONLY",
      "counts_as_E4_false":m.get("counts_as_E4") is False,
      "counts_as_E5_false":m.get("counts_as_E5") is False,
      "human_authored_input":m.get("human_authored_input") is True,
      "files_exact":actual==m.get("files"),
      "semantic_payload_identity":payload_ok,
      "sca_paths_contained":path_contract,
      "rtl_entries_zero":not any(PurePosixPath(x).suffix.lower() in {".v",".sv",".vh",".svh"} or x.startswith("rtl/") for x in actual),
      "forbidden_token_scan_clean":not hits,
      "no_pycache":not any("__pycache__" in PurePosixPath(x).parts or x.endswith(".pyc") for x in actual),
    }
    return {"schema":"human-mac-runtime-root-package-preflight-v2",
      "passed":all(checks.values()),"checks":checks,"forbidden_hits":hits,
      "scanned_control_files":scanned}

def bounded_copy(src,dst,limit=524288):
    if not src.is_file(): return False
    data=src.read_bytes()
    if len(data)>limit:
        half=limit//2
        data=data[:half]+b"\n--- LOG TRUNCATED BY RETURN BUDGET ---\n"+data[-half:]
    dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(data)
    return True

def analyze(package,installed,evidence):
    m=json.loads((package/"TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    status={}
    status_path=evidence/"run_status.json"
    if status_path.is_file():
        status=json.loads(status_path.read_text(encoding="utf-8"))
    rows=[]; first=None
    scad_path=installed/"sca_cfg_D.json"
    if not scad_path.is_file(): scad_path=package/"workload/sca_cfg_D.json"
    scad=json.loads(scad_path.read_text(encoding="utf-8"))
    prefix=f"install/cfg_pkg/{m['source_package']['install_name']}"
    for i in range(28):
        key=f"op0_matrixD_slice{i}"
        rel=Path(scad[key]["path"]).relative_to(prefix)
        got=installed/rel
        gold=installed/f"golden/op0/slice{i:02d}/matrix_D_linearized_128bit.txt"
        if not gold.is_file(): gold=package/f"workload/golden/op0/slice{i:02d}/matrix_D_linearized_128bit.txt"
        got_lines=sum(1 for _ in got.open(encoding="ascii")) if got.is_file() else None
        size_ok=got.is_file() and got.stat().st_size==64*129
        ok=size_ok and gold.is_file() and got.read_bytes()==gold.read_bytes()
        row={"slice":i,"readback_present":got.is_file(),"golden_present":gold.is_file(),
             "expected_lines":64,"actual_lines":got_lines,"expected_bytes":64*129,
             "actual_bytes":got.stat().st_size if got.is_file() else None,"match":ok,
             "readback_sha256":sha(got) if got.is_file() else None,
             "golden_sha256":sha(gold) if gold.is_file() else None}
        rows.append(row)
        if not ok and first is None: first={"phase":"formal_D","detail":row}
    compile_exit=status.get("compile_exit")
    sim_exit=status.get("sim_exit")
    signal=status.get("signal","NONE")
    if compile_exit not in (0,None): first={"phase":"compile","exit":compile_exit}
    elif compile_exit is None: first={"phase":"runner","detail":"compile status unavailable"}
    elif sim_exit not in (0,None): first={"phase":"simulation","exit":sim_exit}
    elif sim_exit is None: first={"phase":"runner","detail":"simulation status unavailable"}
    passed=compile_exit==0 and sim_exit==0 and signal=="NONE" and all(r["match"] for r in rows)
    result={"schema":"human-mac-version-unbound-result-v2","passed":passed,
      "classification":"VERSION_UNBOUND_DIAGNOSTIC_PASS" if passed else "VERSION_UNBOUND_DIAGNOSTIC_FAILURE",
      "result_profile":"VERSION_UNBOUND_DIAGNOSTIC_ONLY","candidate_release":False,
      "counts_as_E4":False,"counts_as_E5":False,"dynamic_baseline":"NO_DYNAMIC_BASELINE",
      "server_source_identity":"INTENTIONALLY_UNBOUND","first_divergence":first,
      "compile_exit":compile_exit,"sim_exit":sim_exit,"signal":signal,
      "formal_readbacks":rows}
    dump(evidence/"SERVER_RESULT_GATE.json",result)
    return result

def make_return(package,server_root,installed,evidence,name):
    result=analyze(package,installed,evidence)
    ret=server_root/f"{name}_return"
    if ret.exists(): raise ValueError(f"return directory already exists: {ret}")
    ret.mkdir()
    for n in ("package_preflight.json","run_status.json","server_command.txt","restore_receipt.json","SERVER_RESULT_GATE.json"):
        p=evidence/n
        if p.is_file(): (ret/n).write_bytes(p.read_bytes())
    bounded_copy(evidence/"compile.log",ret/"compile.log")
    bounded_copy(evidence/"sim.log",ret/"sim.log")
    rb=ret/"readback"
    for i in range(28):
        p=installed/f"op0/slice{i:02d}/matrix_D_linearized_128bit.txt"
        if p.is_file():
            q=rb/f"slice{i:02d}.txt"; q.parent.mkdir(parents=True,exist_ok=True); q.write_bytes(p.read_bytes())
    manifest={"schema":"human-mac-version-unbound-return-v2","install_name":name,
      "package_manifest_sha256":sha(package/"TEST_PACKAGE_MANIFEST.json"),
      "result_gate_passed":result["passed"],"result_profile":"VERSION_UNBOUND_DIAGNOSTIC_ONLY",
      "candidate_release":False,"counts_as_E4":False,"counts_as_E5":False,
      "server_source_identity":"INTENTIONALLY_UNBOUND","returned_files":[]}
    dump(ret/"RETURN_MANIFEST.json",manifest)
    manifest["returned_files"]=[p.relative_to(ret).as_posix() for p in sorted(ret.rglob("*")) if p.is_file() and p.name!="RETURN_MANIFEST.json"]
    dump(ret/"RETURN_MANIFEST.json",manifest)
    z=server_root/f"{name}_return.zip"
    if z.exists() or Path(str(z)+".sha256").exists(): raise ValueError("return ZIP namespace already exists")
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as f:
        for p in sorted(x for x in ret.rglob("*") if x.is_file()):
            info=zipfile.ZipInfo(f"{name}_return/{p.relative_to(ret).as_posix()}",(2026,7,27,0,0,0))
            info.external_attr=(0o100644<<16); info.compress_type=zipfile.ZIP_DEFLATED
            f.writestr(info,p.read_bytes())
    if z.stat().st_size>16*1024*1024:
        raise ValueError("return ZIP exceeds 16 MiB")
    Path(str(z)+".sha256").write_text(f"{sha(z)}  {z.name}\n",encoding="ascii",newline="\n")
    return 0 if result["passed"] else 1

if __name__=="__main__":
    if len(sys.argv)<2: raise SystemExit(2)
    cmd=sys.argv[1]
    if cmd=="preflight":
        result=package_preflight(Path(sys.argv[2]))
        dump(Path(sys.argv[3]),result)
        raise SystemExit(0 if result["passed"] else 1)
    if cmd=="return":
        raise SystemExit(make_return(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]),Path(sys.argv[5]),sys.argv[6]))
    raise SystemExit(2)
'''


def runner(compile_cmd: str, sim_cmd: str) -> str:
    return f'''#!/usr/bin/env bash
set -u
export PYTHONDONTWRITEBYTECODE=1
if [ "$#" -ne 1 ]; then echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root" >&2; exit 2; fi
case "$1" in /*) ;; *) echo "server root path must be absolute" >&2; exit 2;; esac
if [ ! -d "$1" ] || [ ! -x "$1" ]; then echo "server root must resolve to an enterable directory" >&2; exit 2; fi
package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
server_root="$(cd "$1" && pwd -P)" || exit 2
ndp_root="$server_root"
name="{INSTALL}"
source_name="{SOURCE_INSTALL}"
namespace="${{server_root}}/.human_mac_runtime_${{name}}"
workspace="${{namespace}}/workspace"
cfg_root="${{workspace}}/install/cfg_pkg/${{source_name}}"
run_dir="${{namespace}}/run"
evidence="${{namespace}}/evidence"
return_dir="${{server_root}}/${{name}}_return"
return_zip="${{server_root}}/${{name}}_return.zip"
if [ -e "$namespace" ] || [ -e "$return_dir" ] || [ -e "$return_zip" ] || [ -e "${{return_zip}}.sha256" ]; then
  echo "fresh runtime namespace already exists" >&2; exit 4
fi
mkdir -p "$evidence"
namespace_real="$(cd "$namespace" && pwd -P)"
if [ "$(dirname "$namespace_real")" != "$server_root" ]; then
  echo "runtime namespace escaped the supplied root" >&2; exit 6
fi
finalized=0
compile_exit=125
sim_exit=125
observed_signal="NONE"
write_status() {{
  printf '{{"compile_exit":%s,"sim_exit":%s,"signal":"%s"}}\\n' "$compile_exit" "$sim_exit" "$observed_signal" > "$evidence/run_status.json"
}}
finalize() {{
  rc="$1"
  if [ "$finalized" -eq 1 ]; then return; fi
  finalized=1
  write_status
  printf '{{"schema":"no-server-source-touch-v1","required":false,"observer_present":false,"server_source_targets_touched":0,"restore_status":"NOT_REQUIRED"}}\\n' > "$evidence/restore_receipt.json"
  set +e
  python3 -B "$package_root/package_tools/runtime.py" return "$package_root" "$server_root" "$cfg_root" "$evidence" "$name"
  return_rc=$?
  if [ "$return_rc" -ne 0 ] && [ "$rc" -eq 0 ]; then rc="$return_rc"; fi
  return "$rc"
}}
on_signal() {{
  observed_signal="$1"
  code="$2"
  finalize "$code"
  trap - EXIT
  exit "$code"
}}
on_exit() {{
  rc=$?
  finalize "$rc"
  final_rc=$?
  trap - EXIT
  exit "$final_rc"
}}
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
trap on_exit EXIT
python3 -B "$package_root/package_tools/runtime.py" preflight "$package_root" "$evidence/package_preflight.json" || exit 5
mkdir -p "$(dirname "$cfg_root")"
cp -a "$package_root/workload" "$cfg_root"
mkdir -p "$run_dir"
compile_cmd={json.dumps(compile_cmd)}
sim_cmd={json.dumps(sim_cmd)}
printf 'compile_cwd=%s\\ncompile=%s\\nsim_cwd=%s\\nsim=%s\\n' "$server_root" "$compile_cmd" "$workspace" "$sim_cmd" > "$evidence/server_command.txt"
set +e
(cd "$server_root" && eval "$compile_cmd") >"$evidence/compile.log" 2>&1
compile_exit=$?
write_status
if [ "$compile_exit" -eq 0 ]; then
  (cd "$workspace" && eval "$sim_cmd")
  sim_exit=$?
  if [ -f "$run_dir/sim_results/sim.log" ]; then cp "$run_dir/sim_results/sim.log" "$evidence/sim.log"; fi
fi
set -e
exit 0
'''


README = f"""# Human MAC variable-root diagnostic package

This compatibility package accepts exactly one user-supplied absolute server root path.
The directory basename is unrestricted. The runner intentionally does not inspect or bind
the server source tree, build files, testbench, support files, repository state, or version.

Run only after the appropriate server lease is granted:

`bash PREPARE_AND_RUN.sh /absolute/path/to/server_root`

The result is always `VERSION_UNBOUND_DIAGNOSTIC_ONLY`; it cannot count as E4 or E5.
Expected return: `{INSTALL}_return.zip` and its `.sha256` sidecar.
"""


def package_records(root: Path) -> dict[str, dict[str, object]]:
    out = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel == "TEST_PACKAGE_MANIFEST.json":
            continue
        out[rel] = {"size_bytes": path.stat().st_size, "sha256": sha(path)}
    return out


def build(out_root: Path) -> dict[str, object]:
    files = source_files()
    source_manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    compile_cmd, sim_cmd = derive_execution_fragments(
        files["PREPARE_AND_RUN.sh"].decode("utf-8")
    )
    package = out_root / INSTALL
    zip_path = out_root / f"{INSTALL}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    if out_root.exists():
        raise SystemExit(f"refusing to overwrite build root: {out_root}")
    package.mkdir(parents=True)

    preserved = {}
    for rel, data in sorted(files.items()):
        if not rel.startswith(SEMANTIC_PREFIXES):
            continue
        target = package / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        preserved[rel] = {"size_bytes": len(data), "sha256": sha_bytes(data)}

    write(package / "package_tools/runtime.py", RUNTIME)
    write(package / "PREPARE_AND_RUN.sh", runner(compile_cmd, sim_cmd))
    write(package / "README.md", README)
    (package / "PREPARE_AND_RUN.sh").chmod(
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
    )

    manifest = {
        "schema": "human-authored-mac-variable-root-package-v2",
        "install_name": INSTALL,
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "result_profile": "VERSION_UNBOUND_DIAGNOSTIC_ONLY",
        "counts_as_E4": False,
        "counts_as_E5": False,
        "server_source_identity": "INTENTIONALLY_UNBOUND",
        "human_authored_input": True,
        "functional_rtl_modified": False,
        "package_rtl_entries": 0,
        "only_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/server_root",
        "expected_return": f"{INSTALL}_return.zip",
        "return_requires_sidecar": True,
        "source_package": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "size_bytes": SOURCE_ZIP.stat().st_size,
            "sha256": SOURCE_ZIP_SHA256,
            "manifest_sha256": sha_bytes(files["TEST_PACKAGE_MANIFEST.json"]),
            "install_name": SOURCE_INSTALL,
        },
        "source_candidate": source_manifest["corrected_candidate"],
        "authorized_delta": source_manifest["authorized_delta"],
        "read_receipt": READ_RECEIPT,
        "derivation_sources": {
            "frozen_fd2_zip": SOURCE_ZIP_SHA256,
            "current_public_rules": [item["sha256"] for item in READ_RECEIPT],
            "family_builder": {
                "path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
                "sha256": sha(Path(__file__).resolve()),
            },
            "server_tree_or_readme_used": False,
            "execution_command_origin": "frozen fd2 ZIP package-local runner",
        },
        "preserved_semantic_payload": preserved,
        "adaptation_contract": {
            "rule_id": "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
            "accepted_root_arguments": 1,
            "absolute_enterable_directory_only": True,
            "basename_unrestricted": True,
            "fixed_server_file_preflight": False,
            "server_source_scan": False,
            "server_source_identity_gate": False,
            "observer_present": False,
            "server_source_targets_touched": 0,
            "restore_status": "NOT_REQUIRED",
            "fresh_namespace": f".human_mac_runtime_{INSTALL}",
            "forbidden_token_policy_sha256": sha_bytes(
                "\n".join(FORBIDDEN_ADAPTATION_TOKENS).encode("utf-8")
            ),
            "source_of_execution_command": "mechanically extracted from frozen fd2 package runner",
        },
    }
    manifest["files"] = package_records(package)
    write(
        package / "TEST_PACKAGE_MANIFEST.json",
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    )

    scanned_sources = [Path(__file__).resolve()]
    scanned_sources.extend(p for p in package.rglob("*") if p.is_file())
    hits = []
    for path in scanned_sources:
        data = path.read_bytes()
        hits.extend(
            {"path": str(path), "token": token}
            for token in FORBIDDEN_ADAPTATION_TOKENS
            if token.encode("utf-8") in data
        )
    if hits:
        raise ValueError(f"forbidden adaptation tokens: {hits}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in package.rglob("*") if p.is_file()):
            rel = path.relative_to(package).as_posix()
            info = zipfile.ZipInfo(f"{INSTALL}/{rel}", (2026, 7, 27, 0, 0, 0))
            mode = 0o100755 if rel == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
    write(sidecar, f"{sha(zip_path)}  {zip_path.name}\n")
    result = {
        "package": str(package),
        "zip": str(zip_path),
        "sidecar": str(sidecar),
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha(zip_path),
        "manifest_sha256": sha(package / "TEST_PACKAGE_MANIFEST.json"),
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.out_root.resolve())


if __name__ == "__main__":
    main()
