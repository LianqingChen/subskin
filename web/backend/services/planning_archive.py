"""Read-only, allowlisted repository documents. No database or model calls."""
import hashlib
import os
import stat
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from web.backend.exceptions import PlanningDocumentError
from web.backend.utils.planning_metadata import CATEGORIES, metadata, redact_document

DIRECTORIES = ("research", "docs/research", "hermes_plan", "docs/specs", "docs/plans", "docs/design",
               "docs/business", "docs/reviews", "docs/audits", "docs/mvp", "docs/superpowers")
FILES = ("DEPLOY_LOG.md", "PROJECT_FRAMEWORK.md", "docs/photo-upload-and-ai-kb-requirements.md",
         "docs/upload-photo-ai-knowledgebase-design.md", "docs/vitiligo_area_assessment_research_report.md",
         "docs/MEDICAL_ENCYCLOPEDIA_DESIGN.md", "docs/EDITOR_DECISION.md", "docs/NOTEBOOK_RESEARCH.md")
MAX_BYTES = 1024 * 1024


class PlanningArchive:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self._lock = threading.Lock()
        self._expires = 0.0
        self._entries = {}
        self._warnings = []

    def _allowed(self, path: str) -> bool:
        p = PurePosixPath(path)
        return (not p.is_absolute() and str(p) == path and ".." not in p.parts
                and "\\" not in path and "\x00" not in path and p.suffix.lower() == ".md"
                and (path in FILES or any(path.startswith(d + "/") for d in DIRECTORIES)))

    def _read(self, path: str) -> tuple:
        if not self._allowed(path):
            raise PlanningDocumentError("文档不在收录范围内", 404)
        # Open every component relative to an fd with NOFOLLOW: symlinks cannot
        # escape the allowlist, even if replaced between discovery and reading.
        descriptor = os.open(str(self.root), os.O_RDONLY | os.O_DIRECTORY)
        try:
            parts = PurePosixPath(path).parts
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            handle = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            with os.fdopen(handle, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise PlanningDocumentError("文档不可读取", 404)
                if info.st_size > MAX_BYTES:
                    raise PlanningDocumentError("文档超过1MB，未载入", 413)
                raw = stream.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise PlanningDocumentError("文档超过1MB，未载入", 413)
                return redact_document(raw.decode("utf-8-sig")), info
        except (OSError, UnicodeError) as exc:
            raise PlanningDocumentError("文档不存在或不可读取", 404) from exc
        finally:
            os.close(descriptor)

    def _paths(self):
        for directory in DIRECTORIES:
            base = self.root / directory
            if base.is_symlink() or any(parent.is_symlink() for parent in base.parents if parent != self.root):
                continue
            for parent, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (Path(parent) / d).is_symlink())
                for filename in sorted(files):
                    if filename.lower().endswith(".md"):
                        yield (Path(parent) / filename).relative_to(self.root).as_posix()
        for path in FILES:
            if (self.root / path).exists():
                yield path

    def _scan(self, refresh: bool = False) -> tuple:
        with self._lock:
            if refresh or time.monotonic() >= self._expires:
                entries, warnings = {}, []
                for path in self._paths():
                    try:
                        content, info = self._read(path)
                    except PlanningDocumentError as exc:
                        warnings.append({"path": redact_document(path), "message": str(exc)})
                        continue
                    identity = hashlib.sha256(path.encode()).hexdigest()
                    item = metadata(path, content)
                    item.update(id=identity, path=redact_document(path),
                                updated_at=datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
                                size=info.st_size)
                    # Metadata derived from paths goes through the same redaction.
                    item = {k: redact_document(v) if isinstance(v, str) and k not in {"id", "updated_at"} else v for k, v in item.items()}
                    entries[identity] = {"item": item, "content": content, "path": path,
                                         "stamp": (info.st_mtime_ns, info.st_size)}
                self._entries, self._warnings = entries, warnings
                self._expires = time.monotonic() + 30
            return dict(self._entries), list(self._warnings)

    def list_documents(self, query: str = "", category: str = "", source: str = "", month: str = "",
                       page: int = 1, page_size: int = 20, refresh: bool = False) -> dict:
        entries, warnings = self._scan(refresh)
        items = [entry["item"] for entry in entries.values()]
        categories = Counter(item["category"] for item in items)
        sources = Counter(item["source"] for item in items)
        months = Counter(item["date"][:7] for item in items if item["date"])
        words = query.casefold().split()
        selected = []
        for entry in entries.values():
            item = entry["item"]
            if category and category != item["category"] or source and source != item["source"]:
                continue
            if month and (item["date"] or "")[:7] != month:
                continue
            haystack = (item["title"] + " " + item["path"] + " " + item["topic"] + " " + entry["content"]).casefold()
            if all(word in haystack for word in words):
                selected.append(item)
        selected.sort(key=lambda item: (item["date"] or "", item["updated_at"], item["path"]), reverse=True)
        topic_titles = {}
        for item in sorted(items, key=lambda x: x["category"] in {"plan", "progress", "review"}):
            topic_titles.setdefault(item["topic"], item["title"])
        def decorate(item):
            return {**item, "topic_title": topic_titles[item["topic"]],
                    "related_count": sum(other["topic"] == item["topic"] for other in items)}
        return {"items": [decorate(item) for item in selected[(page - 1) * page_size:page * page_size]],
                "total": len(selected), "page": page, "page_size": page_size,
                "stats": {"documents": len(items), "topics": len(topic_titles),
                          "updated_at": max((i["updated_at"] for i in items), default=None)},
                "categories": [{"value": key, "label": label, "count": categories[key]} for key, label in CATEGORIES.items()],
                "sources": [{"value": key, "label": key, "count": count} for key, count in sorted(sources.items())],
                "months": [{"value": key, "label": key, "count": count} for key, count in sorted(months.items(), reverse=True)],
                "warnings": warnings}

    def get_document(self, identity: str) -> dict:
        entries, _ = self._scan()
        entry = entries.get(identity)
        if not entry:
            raise PlanningDocumentError("文档不存在或已移除", 404)
        content, info = self._read(entry["path"])
        if (info.st_mtime_ns, info.st_size) != entry["stamp"]:
            entries, _ = self._scan(True)
            entry = entries.get(identity)
            if not entry:
                raise PlanningDocumentError("文档不存在或已移除", 404)
        related = sorted([e["item"] for e in entries.values() if e["item"]["topic"] == entry["item"]["topic"]], key=lambda i: (list(CATEGORIES).index(i["category"]), i["path"]))
        return {**entry["item"], "content": content, "related": related}

    def resolve_document(self, path: str) -> dict:
        self._read(path)
        identity = hashlib.sha256(path.encode()).hexdigest()
        self._scan(True)
        return {"id": self.get_document(identity)["id"]}


archive = PlanningArchive(Path(__file__).resolve().parents[3])
