from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RTL_ROOT = ROOT / "NDP_copy01/rtl"
INSTALL_NAME = "r5_n4_hw_v51_lc13_lc14_diag"
BEGIN = "// v51 LC13_LC14_ACTUAL_CONSUMER_BEGIN"
END = "// v51 LC13_LC14_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])*)+"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leaf(expression: str) -> str:
    return re.sub(r"\[.*\]$", "", expression.rsplit(".", 1)[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        payload = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    observer = payload.decode()
    block = observer[
        observer.index(BEGIN) : observer.index(END) + len(END)
    ]
    expressions = sorted(set(XMR_RE.findall(block)))
    sv_files = sorted(
        path for path in RTL_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".sv", ".v", ".svh", ".vh"}
    )
    corpus: dict[Path, str] = {}
    for path in sv_files:
        try:
            corpus[path] = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
    bindings = []
    missing = []
    for expression in expressions:
        token = leaf(expression)
        locations = [
            path for path, text in corpus.items()
            if re.search(rf"\b{re.escape(token)}\b", text)
        ]
        if not locations:
            missing.append(expression)
        bindings.append(
            {
                "expression": expression,
                "leaf": token,
                "binding_files": [
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": digest(path.read_bytes()),
                    }
                    for path in locations[:8]
                ],
                "private_xmr": True,
                "clock": "u_NDP_Top_new.clk_db",
                "reset": "u_NDP_Top_new.rst_n_db",
            }
        )
    required = set(expressions)

    def accepts(candidate: str) -> bool:
        found = set(XMR_RE.findall(candidate))
        return (
            found == required
            and all(leaf(item) in {row["leaf"] for row in bindings} for item in found)
            and not missing
        and all(
                "IGA_LC[13]" in item
                or "IGA_LC[14]" in item
                or "IGA_LC[15]" in item
                or "iga_lc_outport" in item
                or item.endswith(".clk_db")
                or item.endswith(".rst_n_db")
                for item in found
            )
        )

    first = expressions[0]
    first_leaf = leaf(first)
    renamed = block.replace(first_leaf, first_leaf + "_typo", 1)
    deleted = block.replace(first, "1'b0", 1)
    wrong_sibling = block.replace("IGA_LC[14]", "IGA_LC[12]", 1)
    checks = {
        "exact_final_span_once": (
            observer.count(BEGIN) == 1 and observer.count(END) == 1
        ),
        "actual_consumer_nonzero": bool(expressions),
        "all_leaf_definitions_found_in_current_rtl": not missing,
        "exact_actual_consumer_set_accepted": accepts(block),
        "owner_clock_reset_exact": (
            "posedge u_NDP_Top_new.clk_db" in block
            and "negedge u_NDP_Top_new.rst_n_db" in block
        ),
    }
    negatives = {
        "leaf_delete_fail_closed": not accepts(deleted),
        "leaf_rename_fail_closed": not accepts(renamed),
        "wrong_sibling_path_fail_closed": not accepts(wrong_sibling),
    }
    checks["actual_consumer_negatives"] = all(negatives.values())
    report = {
        "schema": "node0004-v51-actual-consumer-scope-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "current_rtl": {
            "root": str(RTL_ROOT),
            "cloud_authority_commit": (
                "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
            ),
            "scanned_source_files": len(corpus),
        },
        "observer": {
            "bytes": len(payload),
            "sha256": digest(payload),
            "span_sha256": digest(block.encode()),
            "actual_consumer_count": len(expressions),
        },
        "bindings": bindings,
        "missing": missing,
        "negative_controls": negatives,
        "public_surface_or_xmr_adjudication": {
            "private_xmr_required": True,
            "reason": (
                "The public LC ports expose global output but not selected "
                "input, same-gotten state, or local counter write/read state."
            ),
            "focused_wrapper_fabricated_leaf": False,
            "actual_target_bytes_and_paths_bound": True,
        },
        "claim_boundary": (
            "Static exact-expression/leaf/source binding against current "
            "0cc RTL; server elaboration and dynamic values remain E3."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
