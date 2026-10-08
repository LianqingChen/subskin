"""Private immutable revision artifacts. No arbitrary URLs or client file paths."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict
from web.backend.exceptions import RGBSegmentationError

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ROOT = Path(
    os.getenv(
        "RGB_SEGMENTATION_DATA_ROOT", str(PROJECT_ROOT / "data" / "rgb_segmentation")
    )
)
JOB_PATTERN = re.compile(r"^[a-f0-9]{32}$")
REVISION_PATTERN = re.compile(r"^[a-f0-9]{64}$")
KINDS = {"source", "image", "skin", "lesion", "uncertain", "excluded", "metadata"}


def job_directory(job_id: str) -> Path:
    if not JOB_PATTERN.fullmatch(job_id):
        raise RGBSegmentationError("NOT_FOUND", "记录不存在", 404)
    return ROOT / "jobs" / job_id


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_input(job_id: str, source: bytes) -> None:
    atomic_write(job_directory(job_id) / "source.bin", source)


def read_input(job_id: str) -> bytes:
    return (job_directory(job_id) / "source.bin").read_bytes()


def write_revision(
    job_id: str, image: bytes, masks: Dict[str, bytes], metadata: Dict[str, Any]
) -> Dict[str, Any]:
    hashes = {key: hashlib.sha256(value).hexdigest() for key, value in masks.items()}
    image_hash = hashlib.sha256(image).hexdigest()
    fingerprint = json.dumps(
        {"image": image_hash, "masks": hashes, "metadata": metadata},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    revision = hashlib.sha256(fingerprint).hexdigest()
    folder = job_directory(job_id) / revision
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    shared_image = job_directory(job_id) / "image.png"
    if (
        shared_image.exists()
        and hashlib.sha256(shared_image.read_bytes()).hexdigest() != image_hash
    ):
        raise RGBSegmentationError(
            "ARTIFACT_INVALID", "照片版本不可覆盖，请新建记录", 409
        )
    if not shared_image.exists():
        atomic_write(shared_image, image)
    values = {"image": image, **masks}
    for key, value in values.items():
        if key not in KINDS:
            raise RGBSegmentationError("ARTIFACT_INVALID", "标注类型无效")
        path = folder / (key + ".png")
        if path.exists() and path.read_bytes() != value:
            raise RGBSegmentationError("ARTIFACT_INVALID", "标注版本冲突", 409)
        if not path.exists():
            if key == "image":
                try:
                    os.link(shared_image, path)
                except FileExistsError:
                    pass
                except OSError:
                    atomic_write(path, value)
            else:
                atomic_write(path, value)
    manifest = {
        "revision": revision,
        "image_sha256": image_hash,
        "mask_hashes": hashes,
        "metadata": metadata,
    }
    atomic_write(
        folder / "metadata.json",
        json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode(),
    )
    return manifest


def read_artifact(job_id: str, revision: str, kind: str) -> bytes:
    if not REVISION_PATTERN.fullmatch(revision) or kind not in {
        "image",
        "skin",
        "lesion",
        "uncertain",
        "excluded",
    }:
        raise RGBSegmentationError("NOT_FOUND", "标注不存在", 404)
    folder = job_directory(job_id) / revision
    try:
        manifest = read_manifest(job_id, revision)
        value = (folder / (kind + ".png")).read_bytes()
        expected = (
            manifest["image_sha256"]
            if kind == "image"
            else manifest["mask_hashes"][kind]
        )
        if hashlib.sha256(value).hexdigest() != expected:
            raise RGBSegmentationError("ARTIFACT_INVALID", "标注校验失败，请重新加载")
        return value
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        raise RGBSegmentationError("NOT_FOUND", "标注不存在", 404)


def read_manifest(job_id: str, revision: str) -> Dict[str, Any]:
    if not REVISION_PATTERN.fullmatch(revision):
        raise RGBSegmentationError("NOT_FOUND", "标注不存在", 404)
    try:
        manifest = json.loads(
            (job_directory(job_id) / revision / "metadata.json").read_text()
        )
        fingerprint = json.dumps(
            {
                "image": manifest["image_sha256"],
                "masks": manifest["mask_hashes"],
                "metadata": manifest["metadata"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if (
            manifest["revision"] != revision
            or hashlib.sha256(fingerprint).hexdigest() != revision
        ):
            raise ValueError()
        if manifest["metadata"]["image"]["sha256"] != manifest["image_sha256"]:
            raise ValueError()
        return manifest
    except (OSError, ValueError, KeyError, TypeError):
        raise RGBSegmentationError("ARTIFACT_INVALID", "标注版本暂不可用")
