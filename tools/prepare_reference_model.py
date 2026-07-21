from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "model_baseline.json"


class ReferenceModelError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _verify(path: Path, expected_sha256: str, label: str) -> None:
    if not path.is_file():
        raise ReferenceModelError(f"{label} is missing: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ReferenceModelError(
            f"{label} SHA-256 mismatch: {actual} != {expected_sha256}: {path}"
        )
    print(f"[ok] {label} sha256={actual} {path}")


def _atomic_write(path: Path, writer: Callable[[Path], None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        writer(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _download(url: str, path: Path) -> None:
    def write(temporary: Path) -> None:
        request = urllib.request.Request(
            url, headers={"User-Agent": "resnet50-int8-reference-preparer/1.0"}
        )
        with urllib.request.urlopen(request) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)

    print(f"downloading {url}")
    _atomic_write(path, write)


def _save_array(path: Path, value: Any) -> None:
    import numpy as np

    def write(temporary: Path) -> None:
        with temporary.open("wb") as stream:
            np.save(stream, value, allow_pickle=False)

    _atomic_write(path, write)


def _build_input(image_path: Path) -> Any:
    import cv2
    import numpy as np
    from PIL import Image

    with Image.open(image_path) as image:
        value = np.array(image.convert("RGB"))
    value = value / 255.0
    value = cv2.resize(value, (256, 256))
    y0 = (value.shape[0] - 224) // 2
    x0 = (value.shape[1] - 224) // 2
    value = value[y0 : y0 + 224, x0 : x0 + 224, :]
    value = (value - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    value = np.transpose(value, axes=[2, 0, 1]).astype(np.float32)
    return np.tile(np.expand_dims(value, axis=0), (16, 1, 1, 1))


def _build_output(model_path: Path, input_value: Any) -> Any:
    import onnx
    import onnxruntime as ort

    onnx.checker.check_model(model_path)
    session = ort.InferenceSession(
        str(model_path), providers=["CPUExecutionProvider"]
    )
    outputs = session.run(None, {session.get_inputs()[0].name: input_value})
    if len(outputs) != 1:
        raise ReferenceModelError(
            f"expected one model output, received {len(outputs)}"
        )
    print(f"onnxruntime={ort.__version__} provider=CPUExecutionProvider")
    return outputs[0]


def prepare(output_root: Path, *, check_only: bool, force: bool) -> None:
    import numpy as np

    contract = _load_contract()
    model_spec = contract["model"]
    run_spec = contract["reference_run"]
    source_spec = contract["source"]

    model_path = output_root / model_spec["filename"]
    input_path = output_root / Path(run_spec["input_path"]).name
    output_path = output_root / Path(run_spec["output_path"]).name
    image_path = ROOT / run_spec["image_path"]

    _verify(image_path, run_spec["image_sha256"], "reference image")
    if check_only:
        _verify(model_path, model_spec["sha256"], "reference model")
        _verify(input_path, run_spec["input_sha256"], "reference input")
        _verify(output_path, run_spec["output_sha256"], "reference output")
        return

    if force or not model_path.is_file():
        _download(source_spec["download_url"], model_path)
    _verify(model_path, model_spec["sha256"], "reference model")

    if force or not input_path.is_file():
        _save_array(input_path, _build_input(image_path))
    _verify(input_path, run_spec["input_sha256"], "reference input")
    input_value = np.load(input_path, allow_pickle=False)
    if list(input_value.shape) != run_spec["input_shape"]:
        raise ReferenceModelError(
            f"reference input shape mismatch: {list(input_value.shape)}"
        )

    if force or not output_path.is_file():
        _save_array(output_path, _build_output(model_path, input_value))
    _verify(output_path, run_spec["output_sha256"], "reference output")
    output_value = np.load(output_path, allow_pickle=False)
    if list(output_value.shape) != run_spec["output_shape"]:
        raise ReferenceModelError(
            f"reference output shape mismatch: {list(output_value.shape)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and reproduce the frozen W1 reference model baseline"
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "artifacts" / "reference_model",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify existing files without downloading or generating",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace model, input, and output before verifying them",
    )
    args = parser.parse_args()
    if args.check and args.force:
        parser.error("--check and --force are mutually exclusive")
    try:
        prepare(args.output_root.resolve(), check_only=args.check, force=args.force)
    except (ReferenceModelError, OSError, ValueError) as error:
        print(f"error: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
