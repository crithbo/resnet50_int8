#!/usr/bin/env python3
"""Validate the variable-root human-MAC adaptation without reading server trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True

INSTALL = "human_mac_int32_uint8_v3_runtime_root_v2"
SOURCE_PREFIX = "human_mac_int32_uint8_v3_stock_rtl_fd2/"
SOURCE_SHA = "5bcc26c80a995063b6b8c071eea4962426dd0547d782df771c61cf1fa3024e52"
SERVER_RULE_SHA = "72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524"
FORBIDDEN = (
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


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def zip_files(path: Path, prefix: str) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate member in {path}")
        out = {}
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name:
                raise ValueError(f"unsafe member: {name}")
            if not name.startswith(prefix) or name.endswith("/"):
                raise ValueError(f"unexpected member: {name}")
            out[name[len(prefix) :]] = z.read(name)
        return out


def validate(candidate: Path, source: Path) -> dict[str, object]:
    candidate_files = zip_files(candidate, INSTALL + "/")
    source_files = zip_files(source, SOURCE_PREFIX)
    manifest = json.loads(candidate_files["TEST_PACKAGE_MANIFEST.json"])
    listed = manifest["files"]
    actual = {
        rel: {"size_bytes": len(data), "sha256": sha_bytes(data)}
        for rel, data in candidate_files.items()
        if rel != "TEST_PACKAGE_MANIFEST.json"
    }
    semantic = {
        rel: data
        for rel, data in source_files.items()
        if rel.startswith(("workload/", "provenance/"))
    }
    semantic_equal = all(candidate_files.get(rel) == data for rel, data in semantic.items())
    semantic_exact = set(manifest["preserved_semantic_payload"]) == set(semantic)
    hits = []
    for rel, data in candidate_files.items():
        hits += [
            {"path": rel, "token": token}
            for token in FORBIDDEN
            if token.encode("utf-8") in data
        ]
    runner = candidate_files["PREPARE_AND_RUN.sh"].decode("utf-8")
    runtime = candidate_files["package_tools/runtime.py"].decode("utf-8")
    checks = {
        "source_zip_sha": sha(source) == SOURCE_SHA,
        "exact_set": listed == actual,
        "semantic_payload_bytes_preserved": semantic_equal and semantic_exact,
        "variable_root_contract": "/absolute/path/to/server_root" in runner
        and "basename" not in runner
        and "server_root=\"$(cd \"$1\" && pwd -P)\"" in runner,
        "no_fixed_server_file_preflight": "Missing stock input" not in runner,
        "no_server_source_scan": ("find " + "rtl") not in runner
        and ("sha256sum " + "tb_") not in runner
        and "identity post" not in runner,
        "natural_compile_failure_path": "eval \"$compile_cmd\"" in runner
        and "compile_exit=$?" in runner,
        "signal_safe_finalizer": all(
            token in runner for token in ("trap 'on_signal HUP", "trap 'on_signal INT", "trap 'on_signal TERM", "trap on_exit EXIT")
        ),
        "restore_handling": '"server_source_targets_touched":0' in runner
        and '"restore_status":"NOT_REQUIRED"' in runner,
        "allowlist_return": 'for n in ("package_preflight.json"' in runtime,
        "version_unbound": manifest["result_profile"]
        == "VERSION_UNBOUND_DIAGNOSTIC_ONLY"
        and manifest["counts_as_E4"] is False
        and manifest["counts_as_E5"] is False,
        "candidate_release_false": manifest["candidate_release"] is False,
        "zero_rtl_entries": not any(
            rel.startswith("rtl/")
            or PurePosixPath(rel).suffix.lower() in {".v", ".sv", ".vh", ".svh"}
            for rel in candidate_files
        ),
        "no_pycache": not any(
            "__pycache__" in PurePosixPath(rel).parts or rel.endswith(".pyc")
            for rel in candidate_files
        ),
        "forbidden_token_audit": not hits,
        "refreshed_server_rule_receipt": any(
            item.get("path") == ".agents/rules/服务器测试包生成规则.md"
            and item.get("sha256") == SERVER_RULE_SHA
            for item in manifest["read_receipt"]
        ),
        "no_superseded_rule_receipt": "2897fb6a" not in candidate.read_bytes().decode(
            "latin1"
        ),
        "derivation_excludes_server_tree": manifest["derivation_sources"][
            "server_tree_or_readme_used"
        ]
        is False,
    }
    return {
        "schema": "human-mac-runtime-root-v2-validation",
        "passed": all(checks.values()),
        "checks": checks,
        "forbidden_hits": hits,
        "candidate_zip": {
            "size_bytes": candidate.stat().st_size,
            "sha256": sha(candidate),
        },
        "source_zip": {"size_bytes": source.stat().st_size, "sha256": sha(source)},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.candidate, args.source)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
