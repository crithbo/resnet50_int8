#!/usr/bin/env python3
"""Install the read-only return observer into a server TB source tree.

Only ``tb_NDP_Top_new_phy.sv`` is edited.  Functional RTL below ``rtl/`` is
never searched, opened for writing, or patched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


INCLUDE_LINE = '`include "native_return_observer.svh"'
ENDMODULE_RE = re.compile(r"\nendmodule\s*\Z")
RUN_TIME_UNSIZED = "longint RUN_TIME = 100000000000000;"
RUN_TIME_SIZED = "longint unsigned RUN_TIME = 64'd100000000000000;"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def install_observer(
    testbench: Path,
    observer: Path,
    *,
    fix_run_time: bool = False,
) -> dict:
    testbench = testbench.resolve()
    observer = observer.resolve()
    if testbench.name != "tb_NDP_Top_new_phy.sv":
        raise ValueError(
            "refusing to edit a non-TB file; expected tb_NDP_Top_new_phy.sv"
        )
    if "rtl" in {part.lower() for part in testbench.parts}:
        raise ValueError("refusing to edit any file below an rtl directory")
    if not testbench.is_file():
        raise FileNotFoundError(f"missing testbench: {testbench}")
    if not observer.is_file():
        raise FileNotFoundError(f"missing observer include: {observer}")

    observer_payload = observer.read_bytes()
    installed_observer = testbench.parent / "native_return_observer.svh"
    if "rtl" in {part.lower() for part in installed_observer.parts}:
        raise ValueError("refusing to install observer below an rtl directory")
    installed_observer_before = (
        installed_observer.read_bytes() if installed_observer.is_file() else None
    )
    if installed_observer.resolve() != observer:
        installed_observer.write_bytes(observer_payload)

    original = testbench.read_bytes()
    text = original.decode("utf-8")
    run_time_status = "not_requested"
    if fix_run_time:
        unsized_count = text.count(RUN_TIME_UNSIZED)
        sized_count = text.count(RUN_TIME_SIZED)
        if unsized_count == 1 and sized_count == 0:
            text = text.replace(RUN_TIME_UNSIZED, RUN_TIME_SIZED, 1)
            run_time_status = "sized"
        elif unsized_count == 0 and sized_count == 1:
            run_time_status = "already_sized"
        else:
            raise ValueError(
                "cannot safely size RUN_TIME: expected exactly one unsized or "
                "one already-sized declaration"
            )

    include_count = text.count(INCLUDE_LINE)
    if include_count > 1:
        raise ValueError("testbench contains duplicate return-observer includes")
    if include_count == 1:
        status = "already_installed"
        updated_text = text
    else:
        match = ENDMODULE_RE.search(text)
        if match is None:
            raise ValueError("testbench does not end in a unique top-level endmodule")
        status = "installed"
        newline = "\r\n" if "\r\n" in text else "\n"
        replacement = (
            f"{newline}{INCLUDE_LINE}{newline}{newline}endmodule{newline}"
        )
        updated_text = text[: match.start()] + replacement

    updated = updated_text.encode("utf-8")
    if updated != original:
        testbench.write_bytes(updated)

    return {
        "schema": "native-return-observer-install-v2",
        "status": status,
        "run_time_status": run_time_status,
        "testbench": testbench.as_posix(),
        "testbench_sha256_before": _sha256(original),
        "testbench_sha256_after": _sha256(updated),
        "observer_source": observer.as_posix(),
        "observer_installed": installed_observer.resolve().as_posix(),
        "observer_sha256": _sha256(observer_payload),
        "observer_previous_sha256": (
            None
            if installed_observer_before is None
            else _sha256(installed_observer_before)
        ),
        "functional_rtl_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tb",
        type=Path,
        default=Path("NDP_copy01/tb_NDP_Top_new_phy.sv"),
    )
    parser.add_argument(
        "--observer",
        type=Path,
        default=Path("NDP_copy01/native_return_observer.svh"),
    )
    parser.add_argument(
        "--fix-run-time",
        action="store_true",
        help="replace the known unsafe unsized TB RUN_TIME constant",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            install_observer(
                args.tb,
                args.observer,
                fix_run_time=args.fix_run_time,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
