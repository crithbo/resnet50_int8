from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tools.validate_node0004_v65_install_only_runner as wrapper
wrapper.validator.INSTALL = "r5_n4_hw_v75_sourcebound_collectfix"

def _inject(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    anchor = 'python3 "$runtime" preflight --package-root "$package_root"'
    line_end = text.index("\n", text.index(anchor)) + 1
    text = text[:line_end] + 'runner_fail 12 "synthetic post-receipt preflight failure"\n' + text[line_end:]
    runner.write_text(text, encoding="utf-8", newline="\n")

wrapper.validator.inject_post_receipt_preflight_failure = _inject
if __name__ == "__main__":
    raise SystemExit(wrapper.validator.main())
