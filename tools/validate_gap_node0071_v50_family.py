from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v50_ga_ob_conjunction_diag"
SOURCE = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_n71_gap_v49_mse4_maskwide_diag.zip"
)
SOURCE_SHA = "eb2f5f02b3dce69aad51a3319972622b7cff8d594ef9cbf5909efb7c4114d85a"
MARKER = "    // v50: all-slice GA outbuffer read-conjunction information gain."
RTL_PORT = (
    ROOT / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE/GA_PE.sv"
)
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(argv: list[str], cwd: Path, timeout: int = 30) -> dict[str, object]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "argv": argv,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "argv": argv,
            "exit_code": 124,
            "stdout": error.stdout or "",
            "stderr": error.stderr or "",
            "timed_out": True,
        }


def zip_map(path: Path) -> tuple[zipfile.ZipFile, dict[str, bytes]]:
    archive = zipfile.ZipFile(path)
    members = {
        "/".join(name.split("/")[1:]): archive.read(name)
        for name in archive.namelist()
        if name and not name.endswith("/")
    }
    return archive, members


def semantic_checks(extension: str) -> dict[str, bool]:
    return {
        "feature_marker": "# ga_ob_conjunction=1" in extension,
        "qualified_owner_clk_sg":
            "always @(posedge u_NDP_Top_new.clk_sg" in extension,
        "reporter_clk_db": "always @(posedge u_NDP_Top_new.clk_db" in extension,
        "write_update":
            "if (any_wr) return_obs_v50_wr_seen[id] <= 1'b1;" in extension,
        "nonempty_update":
            "if (any_nonempty) return_obs_v50_nonempty_seen[id] <= 1'b1;"
            in extension,
        "allbp_update":
            "if (any_allbp) return_obs_v50_allbp_seen[id] <= 1'b1;"
            in extension,
        "read_update":
            "if (any_rd) return_obs_v50_rd_seen[id] <= 1'b1;" in extension,
        "stable_state_separate":
            '"QUALIFIED_EDGE" : "STATE_EDGE"' in extension,
        "public_port_surface": ".u_GA_PE.ga_pe_bp_post;" in extension,
        "rate_limit": "return_obs_v50_emit_count < 256" in extension,
    }


def project(extension: str) -> str:
    hierarchy = re.compile(
        r"u_NDP_Top_new\.slice_with_datahub_mc_group_gen"
        r"\[return_obs_v50_g\]\s*"
        r"\.u_slice_with_datahub_mc_group\.slice_group_gen"
        r"\[return_obs_v50_s\]\s*"
        r"\.u_slice_wrapper\.u_Slice\.u_General_Array\.u_GA_PE_Group\s*"
        r"\.GA_ROW_PE\[return_obs_v50_r\]\.GA_COL_PE\[(0|2)\]\.GA_PE\s*"
        r"\.u_GA_PE\.ga_pe_bp_post"
    )

    def replace_hierarchy(match: re.Match[str]) -> str:
        slot = "0" if match.group(1) == "0" else "1"
        return (
            "return_obs_v50_ga_bp_stub[return_obs_v50_g]"
            "[return_obs_v50_s][return_obs_v50_r]"
            f"[{slot}]"
        )

    body = hierarchy.sub(replace_hierarchy, extension)
    body = body.replace(
        "logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]\n"
        "          [`GA_ROW_PE_NUM-1:0][1:0][`GA_PE_DST_NUM-1:0]\n"
        "          return_obs_v50_ga_bp_post_mon;",
        "logic [`GA_PE_DST_NUM-1:0] return_obs_v50_ga_bp_post_mon "
        "[4][4][4][2];",
        1,
    )
    body = body.replace(
        "logic [`GA_PE_DST_NUM-1:0][`GLB_SLICE_NUM-1:0] bp_all_dest;",
        "logic [`GA_PE_DST_NUM*`GLB_SLICE_NUM-1:0] bp_all_dest;",
        1,
    )
    body = body.replace(
        "bp_all_dest[d][id] = dest_all[d];",
        "bp_all_dest[d*`GLB_SLICE_NUM+id] = dest_all[d];",
        1,
    )
    for dest in range(10):
        body = body.replace(
            f"bp_all_dest[{dest}]",
            f"bp_all_dest[{dest}*`GLB_SLICE_NUM +: `GLB_SLICE_NUM]",
            1,
        )
    for old, new in (
        ("u_NDP_Top_new.clk_sg", "clk_sg"),
        ("u_NDP_Top_new.rst_n_sg", "rst_n_sg"),
        ("u_NDP_Top_new.clk_db", "clk_db"),
        ("u_NDP_Top_new.rst_n_db", "rst_n_db"),
    ):
        body = body.replace(old, new)
    return """\
`define GLB_SLICE_NUM 16
`define SLICE_GROUP_SIZE 4
`define SLICE_GROUP_NUM 4
`define GA_ROW_PE_NUM 4
`define GA_PE_DST_NUM 10
`define GA_PE_OUTBUFFER_CNT_WIDTH 2
module gap_v50_changed_surface;
  logic clk_sg,clk_db,rst_n_sg,rst_n_db;
  bit return_obs_enabled;
  integer return_obs_fd;
  logic [`GA_PE_DST_NUM-1:0]
        return_obs_v50_ga_bp_stub [4][4][4][2];
  logic return_obs_pair_ga_normal_wr_hs_mon [4][4][4][2];
  logic return_obs_pair_ga_normal_rd_hs_mon [4][4][4][2];
  logic [`GA_PE_OUTBUFFER_CNT_WIDTH-1:0]
        return_obs_ga_ob_count_mon [4][4][4][2];
""" + body + "\nendmodule\n"


def compile_projection(source: str, root: Path, name: str) -> dict[str, object]:
    path = root / f"{name}.sv"
    path.write_text(source, encoding="utf-8", newline="\n")
    result = run(
        [str(IVERILOG), "-g2012", "-tnull", "-s",
         "gap_v50_changed_surface", str(path)],
        root,
    )
    result["source_sha256"] = sha_bytes(source.encode())
    result["stderr_sha256"] = sha_bytes(str(result["stderr"]).encode())
    return result


def normalized_identity(value: bytes) -> bytes:
    return value.replace(NAME.encode(), b"r5_n71_gap_v49_mse4_maskwide_diag")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.target_zip.resolve()
    output = args.output.resolve()
    errors: list[str] = []
    target_archive, target_members = zip_map(target)
    source_archive, source_members = zip_map(SOURCE)
    infos = target_archive.infolist()
    names = target_archive.namelist()
    roots = {PurePosixPath(name).parts[0] for name in names if name}
    manifest = json.loads(target_members["TEST_PACKAGE_MANIFEST.json"])
    payload = {
        key: value for key, value in target_members.items()
        if key != "TEST_PACKAGE_MANIFEST.json"
    }
    archive_checks = {
        "crc": target_archive.testzip() is None,
        "single_root": roots == {NAME},
        "path_safe": all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
            for name in names
        ),
        "duplicate_free": len(names) == len(set(names)),
        "symlink_free": all(
            ((info.external_attr >> 16) & 0o170000) != 0o120000
            for info in infos
        ),
    }
    declared = manifest["files"]
    manifest_checks = {
        "exact_set": set(declared) == set(payload),
        "per_file_receipts": all(
            declared[name]["size_bytes"] == len(value)
            and declared[name]["sha256"] == sha_bytes(value)
            for name, value in payload.items()
        ),
        "install_identity": manifest.get("install_name") == NAME,
        "package_identity": manifest.get("package_name") == f"{NAME}.zip",
        "source_binding":
            manifest.get("source_package", {}).get("sha256") == SOURCE_SHA
            and sha(SOURCE) == SOURCE_SHA,
        "class":
            manifest.get("package_class")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release_false": manifest.get("candidate_release") is False,
        "return_allowlist_81": len(manifest["return_allowlist"]) == 81,
    }

    numeric_names = sorted(
        name for name in source_members
        if (
            name.startswith("workload/input/")
            or name.startswith("workload/golden/")
            or (
                name.startswith("workload/install/cfg_pkg/")
                and name.endswith(".bin")
            )
            or name == "workload/install/execplan.txt"
        )
    )
    freeze_checks = {
        "numeric_file_count": len(numeric_names) == 73,
        "numeric_byte_equal": all(
            source_members[name] == target_members[name] for name in numeric_names
        ),
        "sca_identity_only": all(
            source_members[name] == normalized_identity(target_members[name])
            for name in ("workload/sca_cfg.json", "workload/sca_cfg_D.json")
        ),
        "timeout_unchanged":
            b"12h" in source_members["PREPARE_AND_RUN.sh"]
            and b"12h" in target_members["PREPARE_AND_RUN.sh"],
    }

    observer = target_members["tb_probe/native_return_observer.svh"].decode()
    if MARKER not in observer:
        errors.append("v50 observer marker absent")
        extension = ""
    else:
        extension = observer[observer.index(MARKER):]
    semantics = semantic_checks(extension)
    negative_semantics = {
        "delete_read_update_fails_closed":
            not all(semantic_checks(extension.replace(
                "if (any_rd) return_obs_v50_rd_seen[id] <= 1'b1;", "", 1
            )).values()),
        "feature_marker_removed_fails_closed":
            not all(semantic_checks(extension.replace(
                "# ga_ob_conjunction=1", "# ga_ob_conjunction=0", 1
            )).values()),
    }
    rtl_text = RTL_PORT.read_text(encoding="utf-8")
    port_pattern = re.compile(
        r"input\s+\[`GA_PE_DST_NUM-1:0\]\s+ga_pe_bp_post"
    )
    port_checks = {
        "actual_rtl_path": RTL_PORT.is_file(),
        "actual_rtl_sha256": sha(RTL_PORT),
        "public_port_declared":
            port_pattern.search(rtl_text) is not None,
        "extension_uses_exact_public_port": ".u_GA_PE.ga_pe_bp_post;" in extension,
        "delete_port_negative":
            port_pattern.search(port_pattern.sub("", rtl_text, count=1)) is None,
        "rename_use_negative":
            ".u_GA_PE.ga_pe_bp_post;" not in
            extension.replace(".u_GA_PE.ga_pe_bp_post;",
                              ".u_GA_PE.ga_pe_bp_post_typo;"),
        "wrong_sibling_negative":
            ".GA_COL_PE[1]" not in extension,
    }

    with tempfile.TemporaryDirectory(prefix="gap-v50-hdl-") as tmp:
        hdl_root = Path(tmp)
        positive_source = project(extension)
        positive = compile_projection(positive_source, hdl_root, "positive")
        negative_decl = compile_projection(
            positive_source.replace(
                "logic [`GLB_SLICE_NUM-1:0] return_obs_v50_rd_seen;", "", 1
            ),
            hdl_root,
            "negative_declaration",
        )
        negative_typo = compile_projection(
            positive_source.replace(
                "return_obs_v50_rd_seen[id] <= 1'b1;",
                "return_obs_v50_rd_seen_typo[id] <= 1'b1;",
                1,
            ),
            hdl_root,
            "negative_typo",
        )

    with tempfile.TemporaryDirectory(prefix="gap-v50-parser-") as tmp:
        parser_root = Path(tmp)
        parser_path = parser_root / "parser.py"
        parser_path.write_bytes(
            target_members[
                "package_tools/gap_node0071_ga_ob_conjunction_decision.py"
            ]
        )
        predicate_path = parser_root / "predicate.json"
        predicate = run(
            [
                sys.executable,
                str(parser_path),
                "self-test",
                "--output",
                str(predicate_path),
            ],
            parser_root,
        )
        predicate_value = (
            json.loads(predicate_path.read_text(encoding="utf-8"))
            if predicate_path.is_file() else {}
        )

    hdl_checks = {
        "positive_exit_zero": positive["exit_code"] == 0,
        "delete_declaration_exit_nonzero": negative_decl["exit_code"] != 0,
        "typo_use_exit_nonzero": negative_typo["exit_code"] != 0,
    }
    predicate_checks = {
        "exit_zero": predicate["exit_code"] == 0,
        "all_checks_true":
            predicate_value.get("pass") is True
            and all(predicate_value.get("checks", {}).values()),
        "trace": predicate_value,
    }
    all_groups = (
        archive_checks, manifest_checks, freeze_checks, semantics,
        negative_semantics, port_checks, hdl_checks, predicate_checks,
    )
    for group in all_groups:
        for key, value in group.items():
            if key in ("actual_rtl_sha256", "trace"):
                continue
            if value is not True:
                errors.append(f"{key} failed")
    report = {
        "schema": "gap-node0071-v50-family-validation-v1",
        "valid": not errors,
        "errors": errors,
        "archive_checks": archive_checks,
        "manifest_checks": manifest_checks,
        "freeze_checks": freeze_checks,
        "observer_semantics": semantics,
        "negative_semantics": negative_semantics,
        "public_surface_proof": port_checks,
        "hdl_scope": {
            "checks": hdl_checks,
            "positive": positive,
            "negative_declaration": negative_decl,
            "negative_typo": negative_typo,
            "claim_boundary":
                "Focused syntax/scope for the changed extension plus exact current RTL "
                "public-port declaration; not full-design elaboration.",
        },
        "predicate_trace": predicate_checks,
        "source_zip_sha256": sha(SOURCE),
        "target_zip_sha256": sha(target),
    }
    write_json(output, report)
    target_archive.close()
    source_archive.close()
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
