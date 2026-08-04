from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REPOSITORY = "onnx-community/DeepSeek-R1-Distill-Qwen-1.5B-ONNX"
REVISION = "03b7d053945cc9455109f97e20b3a4bf8a61b09b"
DEFAULT_OUTPUT = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/source"
)
IDENTITY_CLASS = "SEMANTIC_MODEL_MATCH"


@dataclass(frozen=True)
class SourceFile:
    repository: str
    revision: str
    source_path: str
    destination_path: str
    size_bytes: int
    sha256: str
    required_for_graph_only: bool

    @property
    def url(self) -> str:
        return (
            f"https://huggingface.co/{self.repository}/resolve/"
            f"{self.revision}/{self.source_path}"
        )


FILES = (
    SourceFile(
        repository="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        revision="e164738bb96d0c534f3634b1640208e07f5b1efc",
        source_path="config.json",
        destination_path="official_model/config.json",
        size_bytes=679,
        sha256="37bd455e9679d2959536270fed49d25cc7c290a64f6e52abb97c71345a9cee41",
        required_for_graph_only=True,
    ),
    SourceFile(
        repository=REPOSITORY,
        revision=REVISION,
        source_path="config.json",
        destination_path="config.json",
        size_bytes=903,
        sha256="032502bca49436f59bdcf12dbb63433f3eb8dd611ef4d1a71b6331e27bd3c66f",
        required_for_graph_only=True,
    ),
    SourceFile(
        repository=REPOSITORY,
        revision=REVISION,
        source_path="onnx/model_fp16.onnx",
        destination_path="onnx/model_fp16.onnx",
        size_bytes=1_496_624_384,
        sha256="0e0f94186141f35235f2cdfc880bd2007faf0e82f8212cd8fedeb2b2fc98f14e",
        required_for_graph_only=True,
    ),
    SourceFile(
        repository=REPOSITORY,
        revision=REVISION,
        source_path="onnx/model_fp16.onnx_data",
        destination_path="onnx/model_fp16.onnx_data",
        size_bytes=2_091_253_760,
        sha256="588bc7892155ac042c08a6391429a899bc652021ad7af070f95662b55552aade",
        required_for_graph_only=False,
    ),
)


class DownloadError(RuntimeError):
    pass


def _sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _verify(path: Path, source: SourceFile) -> dict[str, object]:
    if not path.is_file():
        raise DownloadError(f"downloaded file is missing: {path}")
    actual_size = path.stat().st_size
    if actual_size != source.size_bytes:
        raise DownloadError(
            f"size mismatch for {source.destination_path}: "
            f"{actual_size} != {source.size_bytes}"
        )
    actual_hash = _sha256(path)
    if actual_hash != source.sha256:
        raise DownloadError(
            f"SHA-256 mismatch for {source.destination_path}: "
            f"{actual_hash} != {source.sha256}"
        )
    return {
        "path": path.as_posix(),
        "source_repository": source.repository,
        "source_revision": source.revision,
        "source_path": source.source_path,
        "source_url": source.url,
        "size_bytes": actual_size,
        "sha256": actual_hash,
        "verified": True,
    }


def _download(
    source: SourceFile,
    destination: Path,
    *,
    chunk_size: int,
) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        try:
            result = _verify(destination, source)
            result["download_action"] = "reused_verified_final"
            return result
        except DownloadError:
            raise DownloadError(
                f"existing final file has wrong identity; refusing overwrite: "
                f"{destination}"
            )

    partial = destination.with_name(destination.name + ".part")
    offset = partial.stat().st_size if partial.is_file() else 0
    if offset > source.size_bytes:
        raise DownloadError(
            f"partial file is larger than expected; refusing overwrite: {partial}"
        )
    if offset == source.size_bytes:
        if _sha256(partial) != source.sha256:
            raise DownloadError(
                f"complete partial file has wrong SHA-256: {partial}"
            )
        os.replace(partial, destination)
        result = _verify(destination, source)
        result["download_action"] = "promoted_verified_partial"
        return result

    headers = {"User-Agent": "Codex-NDP-semantic-validation/1"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(source.url, headers=headers)
    started = time.monotonic()
    last_report = offset
    mode = "ab" if offset else "wb"
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = int(getattr(response, "status", 200))
            content_range = response.headers.get("Content-Range")
            if offset and status != 206:
                raise DownloadError(
                    f"server ignored resume Range for {source.destination_path}; "
                    "partial file preserved"
                )
            if offset and not (
                isinstance(content_range, str)
                and content_range.startswith(f"bytes {offset}-")
            ):
                raise DownloadError(
            f"unexpected Content-Range for {source.destination_path}: "
                    f"{content_range!r}"
                )
            with partial.open(mode) as stream:
                downloaded = offset
                while True:
                    block = response.read(chunk_size)
                    if not block:
                        break
                    stream.write(block)
                    downloaded += len(block)
                    if downloaded - last_report >= 256 * 1024 * 1024:
                        elapsed = max(time.monotonic() - started, 0.001)
                        mib_s = (downloaded - offset) / elapsed / (1024 * 1024)
                        print(
                            f"{source.destination_path}: "
                            f"{downloaded}/{source.size_bytes} bytes "
                            f"({mib_s:.1f} MiB/s)",
                            flush=True,
                        )
                        last_report = downloaded
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise DownloadError(
            f"download failed for {source.destination_path}; resumable partial "
            f"preserved at {partial}: {error}"
        ) from error

    if partial.stat().st_size != source.size_bytes:
        raise DownloadError(
            f"incomplete download for {source.destination_path}: "
            f"{partial.stat().st_size} != {source.size_bytes}"
        )
    actual_hash = _sha256(partial)
    if actual_hash != source.sha256:
        raise DownloadError(
            f"downloaded partial SHA-256 mismatch for {source.destination_path}: "
            f"{actual_hash} != {source.sha256}"
        )
    os.replace(partial, destination)
    result = _verify(destination, source)
    result["download_action"] = "downloaded_and_verified"
    return result


def _download_with_retries(
    source: SourceFile,
    destination: Path,
    *,
    chunk_size: int,
    retry_limit: int = 40,
) -> dict[str, object]:
    partial = destination.with_name(destination.name + ".part")
    consecutive_no_progress = 0
    for attempt in range(1, retry_limit + 1):
        before = partial.stat().st_size if partial.is_file() else 0
        try:
            return _download(
                source,
                destination,
                chunk_size=chunk_size,
            )
        except DownloadError as error:
            after = partial.stat().st_size if partial.is_file() else 0
            retryable = str(error).startswith(
                ("download failed for ", "incomplete download for ")
            )
            if not retryable or attempt == retry_limit:
                raise
            if after > before:
                consecutive_no_progress = 0
            else:
                consecutive_no_progress += 1
            if consecutive_no_progress >= 5:
                raise DownloadError(
                    f"download made no progress for five retries: "
                    f"{source.destination_path}; partial preserved at {partial}"
                ) from error
            print(
                f"{source.destination_path}: retry {attempt}/{retry_limit} "
                f"after transient read failure; partial={after} bytes",
                flush=True,
            )
            time.sleep(min(attempt, 5))
    raise AssertionError("retry loop exhausted without return")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the pinned DeepSeek GQA FP16 ONNX semantic reference "
            "with resume, size and SHA-256 verification."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
    )
    parser.add_argument(
        "--include-external-data",
        action="store_true",
        help="Also download the 2.09 GB ONNX external tensor data.",
    )
    parser.add_argument(
        "--chunk-mib",
        type=int,
        default=8,
        help="Streaming chunk size in MiB (default: 8).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.chunk_mib <= 0:
        raise DownloadError("--chunk-mib must be positive")
    output_dir = args.output_dir.resolve()
    selected = [
        item
        for item in FILES
        if item.required_for_graph_only or args.include_external_data
    ]
    records = []
    for source in selected:
        destination = output_dir / source.destination_path
        print(
            f"acquire {source.destination_path} from "
            f"{source.repository}@{source.revision}",
            flush=True,
        )
        records.append(
            _download_with_retries(
                source,
                destination,
                chunk_size=args.chunk_mib * 1024 * 1024,
            )
        )

    manifest = {
        "schema": "deepseek-onnx-source-identity-manifest-v1",
        "repository": REPOSITORY,
        "revision": REVISION,
        "identity_classification": IDENTITY_CLASS,
        "original_source_identity": False,
        "intended_use": (
            "ONNX graph semantics and model-shape source for local Stage IR "
            "rule validation"
        ),
        "ndpsim_weight_origin_proven": False,
        "crop_contract_required": True,
        "external_tensor_data_included": args.include_external_data,
        "files": records,
    }
    manifest_path = output_dir / "source_identity_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(f"manifest: {manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DownloadError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
