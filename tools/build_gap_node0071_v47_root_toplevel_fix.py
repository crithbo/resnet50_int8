#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_n71_gap_v46_stage_transition_mask_diag"
NAME = "r5_n71_gap_v47_stage_transition_rootfix"
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
SOURCE_SHA = "97752ec7a3e11dbc41c814d0dfabfb055e52f897deff48fa53573f8c593ea555"
OUTPUT = (
    ROOT / "artifacts/operator_config_validation"
    / "r5-gap-node0071-v47-stage-transition-rootfix"
)
PACKAGE_FINAL = OUTPUT / "package_final"
ZIP_OUTPUT = OUTPUT / f"{NAME}.zip"
SIDECAR = OUTPUT / f"{NAME}.zip.sha256"
RECEIPTS = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "index": "1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500",
    "server": "b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724",
    "config": "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "gap_mac": "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
    "gap_probe": "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
    "tail": "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
        for path in sorted(p for p in source_root.rglob("*") if p.is_file()):
            relative = path.relative_to(source_root.parent).as_posix()
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def replace_identity(package: Path) -> None:
    for path in sorted(p for p in package.rglob("*") if p.is_file()):
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


def patch_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = (
        'cfg_root="$server_root/install/cfg_pkg/$install_name"\n'
        'run_root="$server_root/run_$install_name"\n'
        'evidence_root="$server_root/evidence_$install_name"\n'
    )
    new = (
        'existing_parent="$server_root/install"\n'
        'workspace_root="$existing_parent/codex_pkg_runs/$install_name"\n'
        'cfg_root="$server_root/install/cfg_pkg/$install_name"\n'
        'run_root="$workspace_root/run"\n'
        'evidence_root="$workspace_root/evidence"\n'
    )
    if old not in text:
        raise ValueError("v46 root path assignment not found")
    text = text.replace(old, new, 1)
    text = text.replace(
        "for tool in python3 timeout make date tail tr grep sleep; do",
        "for tool in python3 timeout make date tail tr grep sleep; do",
        1,
    )
    marker = 'done\nmkdir -p "$result_root" || exit 3\n'
    preflight = r'''done
root_top_snapshot() {
  python3 - "$server_root" <<'PY'
import json, os, pathlib, sys
root=pathlib.Path(sys.argv[1])
items=[]
for entry in os.scandir(root):
    kind=("symlink" if entry.is_symlink() else
          "directory" if entry.is_dir(follow_symlinks=False) else
          "file" if entry.is_file(follow_symlinks=False) else "other")
    items.append({"name":entry.name,"type":kind})
print(json.dumps(sorted(items,key=lambda x:(x["name"],x["type"])),
                 ensure_ascii=False,separators=(",",":")))
PY
}
root_top_before_json="$(root_top_snapshot)" || exit 3
python3 - "$root_top_before_json" <<'PY' || exit 3
import json, sys
items=json.loads(sys.argv[1])
raise SystemExit(0 if {"name":"install","type":"directory"} in items else 1)
PY
mkdir -p "$result_root" || exit 3
'''
    if marker not in text:
        raise ValueError("runner tool preflight marker not found")
    text = text.replace(marker, preflight, 1)
    text = text.replace(
        'for target in "$cfg_root" "$run_root" "$evidence_root"; do',
        'for target in "$cfg_root" "$workspace_root"; do',
        1,
    )
    text = text.replace(
        'mkdir "$evidence_root"\n',
        'mkdir -p "$workspace_root"\n'
        'mkdir "$evidence_root"\n'
        "printf '%s\\n' \"$root_top_before_json\" "
        '>"$evidence_root/ndp_root_toplevel_pre.json"\n',
        1,
    )
    collect_marker = (
        '  python3 "$runtime" collect --server-root "$server_root"'
    )
    root_check = r'''  root_top_after_json="$(root_top_snapshot)"
  root_snapshot_status=$?
  root_top_status=0
  [ "$root_snapshot_status" -eq 0 ] || root_top_status=43
  [ "$root_top_after_json" = "$root_top_before_json" ] || root_top_status=43
  python3 - "$server_root" "$existing_parent" "$workspace_root" "$cfg_root" \
    "$result_root" "$root_top_before_json" "$root_top_after_json" \
    "$root_top_status" "$evidence_root/ndp_root_toplevel_exact_set.json" <<'PY'
import hashlib, json, pathlib, sys
server_root,parent,workspace,cfg,result,before,after,status,out=sys.argv[1:]
def digest(value): return hashlib.sha256((value+"\n").encode()).hexdigest()
record={
 "schema":"ndp-root-toplevel-exact-set-v1",
 "server_root":server_root,
 "pre_exact_set":json.loads(before),
 "post_exact_set":json.loads(after) if after else [],
 "pre_exact_set_sha256":digest(before),
 "post_exact_set_sha256":digest(after) if after else None,
 "ndp_root_toplevel_unchanged":status=="0",
 "existing_toplevel_parents":[parent],
 "root_internal_write_targets":[workspace,cfg],
 "fixed_result_root":result,
 "violation_class":None if status=="0" else
   "SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED",
}
pathlib.Path(out).write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
PY
  printf 'ndp_root_toplevel_status=%s\n' "$root_top_status" \
    >>"$evidence_root/signal_status.txt"
'''
    if collect_marker not in text:
        raise ValueError("runtime collect marker not found")
    text = text.replace(collect_marker, root_check + collect_marker, 1)
    text = text.replace(
        '  [ "$final" -ne 0 ] || [ "$collection_status" -eq 0 ] '
        '|| final="$collection_status"\n',
        '  [ "$final" -ne 0 ] || [ "$collection_status" -eq 0 ] '
        '|| final="$collection_status"\n'
        '  [ "$final" -ne 0 ] || [ "$root_top_status" -eq 0 ] '
        '|| final="$root_top_status"\n',
        1,
    )
    if (
        f'$server_root/run_{NAME}' in text
        or f'$server_root/evidence_{NAME}' in text
    ):
        raise ValueError("root-level run/evidence target survived")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_manifest(path: Path) -> dict[str, Any]:
    m = json.loads(path.read_text(encoding="utf-8"))
    m["package_name"] = NAME
    m["install_name"] = NAME
    m["run_name"] = f"install/codex_pkg_runs/{NAME}/run"
    m["return_name"] = f"{NAME}_return"
    m["test_id"] = "r5-gap-node0071-v47-stage-transition-rootfix"
    m["status"] = "PACKAGE_READY_NOT_RUN"
    m["rule_receipts"] = RECEIPTS
    m["source_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"pending/{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA,
        "disposition": "SUPERSEDED_UNRUN_RULE_REBUILD",
    }
    m["supersedes_package_sha256"] = SOURCE_SHA
    ids = set(m.get("applicable_rule_ids", []))
    ids.add("CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001")
    ids.discard("CDA-SERVER-READONLY-EXTERNAL-WORKDIR-001")
    m["applicable_rule_ids"] = sorted(ids)
    m["ndp_root_toplevel_contract"] = {
        "rule_id": "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
        "preflight_before_any_write": True,
        "direct_child_identity": "sorted name+type exact-set",
        "required_existing_toplevel_parent": "install",
        "root_internal_write_targets": [
            f"install/cfg_pkg/{NAME}",
            f"install/codex_pkg_runs/{NAME}",
        ],
        "forbidden_root_level_targets": [
            f"run_{NAME}",
            f"evidence_{NAME}",
            f"{NAME}_return.zip",
            f"{NAME}_return.zip.sha256",
        ],
        "shared_finalizer_post_snapshot": True,
        "unchanged_required": True,
        "violation_class":
            "SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED",
        "server_result_root": "/home/panqs/ndp/simresult",
    }
    m["release_gate_matrix"]["runner_compile_finalizer"] = {
        "applicability": "applicable_changed_runner_root_workspace",
        "blocking": True,
    }
    addition = {
        "source_root": "evidence",
        "source_path": "ndp_root_toplevel_exact_set.json",
        "target_path": "evidence/ndp_root_toplevel_exact_set.json",
        "required": True,
        "max_bytes": 65536,
        "missing_meaning": "root direct-child pre/post exact-set receipt absent",
    }
    targets = {x["target_path"] for x in m["return_allowlist"]}
    if addition["target_path"] not in targets:
        m["return_allowlist"].append(addition)
        m["budgets"]["return_extracted_max_bytes"] += 65536
        m["budgets"]["return_zip_max_bytes"] += 32768
    path.write_text(
        json.dumps(m, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return m


def refresh_files(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    m["files"] = {
        p.relative_to(package).as_posix(): {
            "size_bytes": p.stat().st_size,
            "sha256": sha(p),
        }
        for p in sorted(x for x in package.rglob("*") if x.is_file())
        if p.name != "TEST_PACKAGE_MANIFEST.json"
    }
    write_json(path, m)


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"fresh output exists: {OUTPUT}")
    if not SOURCE_ZIP.is_file() or sha(SOURCE_ZIP) != SOURCE_SHA:
        raise SystemExit("v46 frozen source mismatch")
    OUTPUT.mkdir(parents=True)
    PACKAGE_FINAL.mkdir()
    with tempfile.TemporaryDirectory(prefix="gap-v47-rootfix-") as raw:
        temp = Path(raw)
        with zipfile.ZipFile(SOURCE_ZIP) as z:
            if z.testzip() is not None:
                raise SystemExit("v46 source CRC failure")
            z.extractall(temp)
        source = temp / SOURCE_NAME
        package = PACKAGE_FINAL / NAME
        shutil.copytree(source, package)
        replace_identity(package)
        runtime = (
            package / "package_tools/gap_node0071_complete_server_runtime.py"
        )
        runtime_text = runtime.read_text(encoding="utf-8")
        runtime_text = runtime_text.replace(
            "len(allowlist) != 72", "len(allowlist) != 73", 1
        )
        runtime.write_text(runtime_text, encoding="utf-8", newline="\n")
        patch_runner(package / "PREPARE_AND_RUN.sh")
        patch_manifest(package / "TEST_PACKAGE_MANIFEST.json")
        (package / "README.md").write_text(
            "# GAP node0071 v47 stage-transition root-workspace fix\n\n"
            "Runner-only fresh replacement for v46. Numeric, workload, config, "
            "golden, observer, timeout, backpressure and functional RTL are "
            "frozen. The runner requires an existing `install` top-level "
            "directory and creates isolated cfg/run/evidence children only "
            "below it. It records sorted root direct-child name+type snapshots "
            "before writes and in the shared finalizer. Return ZIP+sidecar are "
            "published only to server `/home/panqs/ndp/simresult`.\n\n"
            "Run: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`\n",
            encoding="utf-8",
            newline="\n",
        )
        refresh_files(package)
        deterministic_zip(package, ZIP_OUTPUT)
        second = OUTPUT / "determinism-second.zip"
        deterministic_zip(package, second)
        deterministic = ZIP_OUTPUT.read_bytes() == second.read_bytes()
        second.unlink()
        if not deterministic:
            raise SystemExit("deterministic build differs")
        SIDECAR.write_text(
            f"{sha(ZIP_OUTPUT)}  {ZIP_OUTPUT.name}\n",
            encoding="ascii",
            newline="\n",
        )

    with zipfile.ZipFile(SOURCE_ZIP) as z:
        old = {
            n.split("/", 1)[1]: z.read(n)
            for n in z.namelist() if n and not n.endswith("/")
        }
    package = PACKAGE_FINAL / NAME
    excluded = {
        "PREPARE_AND_RUN.sh", "README.md", "TEST_PACKAGE_MANIFEST.json"
    }
    comparable = [
        rel for rel in old
        if rel not in excluded and SOURCE_NAME not in old[rel].decode(
            "utf-8", errors="ignore"
        )
    ]
    byte_equal = all(
        (package / rel).is_file() and (package / rel).read_bytes() == old[rel]
        for rel in comparable
    )
    observer_equal = (
        package / "tb_probe/native_return_observer.svh"
    ).read_bytes() == old["tb_probe/native_return_observer.svh"]
    report = {
        "schema": "gap-node0071-v47-runner-rootfix-build-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "source_zip": str(SOURCE_ZIP.relative_to(ROOT)).replace("\\", "/"),
        "source_zip_sha256": sha(SOURCE_ZIP),
        "target_zip": str(ZIP_OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": ZIP_OUTPUT.stat().st_size,
        "target_zip_sha256": sha(ZIP_OUTPUT),
        "sidecar_sha256": sha(SIDECAR),
        "deterministic_double_build_equal": deterministic,
        "observer_byte_equal": observer_equal,
        "unchanged_nonidentity_nonrunner_members_equal": byte_equal,
        "changed_surface": [
            "fresh identity and SCA namespace text",
            "runner workspace under existing install top-level parent",
            "root exact-set return receipt",
            "manifest/README/current rule receipts",
        ],
        "frozen": [
            "numeric", "workload", "config semantics", "golden", "observer",
            "timeout", "backpressure", "functional RTL",
        ],
        "rule_receipts": RECEIPTS,
    }
    write_json(OUTPUT / "build_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
