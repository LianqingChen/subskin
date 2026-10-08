"""Deterministic, redacted metadata for the administrator's document archive."""
import re
from datetime import date
from pathlib import PurePosixPath
from typing import Optional

from web.backend.utils.pii_detect import redact_pii

CATEGORIES = {
    "research": "研究分析", "design": "设计方案", "plan": "任务计划",
    "progress": "发现与进度", "review": "验收审查", "deployment": "部署记录",
}
DATE_RE = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")
STAGES = r"task[_-]plan|findings|progress|assessment|design|verification|implementation|review|acceptance|plan|taskplan"
GENERIC = re.compile(r"^(?:" + STAGES + r")$", re.I)
SUFFIX = re.compile(r"[-_](?:" + STAGES + r")$", re.I)


def redact_document(text: str) -> str:
    """Remove recognizable credentials before indexing, rendering or searching."""
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", "[私钥已隐藏]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[凭据已隐藏]", text)
    text = re.sub(r"\b(?:sk-|gh[pousr]_|github_pat_)[A-Za-z0-9_-]{12,}", "[凭据已隐藏]", text)
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+", r"\1[凭据已隐藏]", text)
    text = re.sub(r'''(?im)((?:[\w-]*(?:password|passwd|secret|token|api[_-]?key)[\w-]*|密码|真实姓名|姓名|家庭住址)\s*["']?\s*[:=：]\s*)[^\n|,;]+''', r"\1[敏感信息已隐藏]", text)
    # redact_pii is the shared policy for phone, email, ID and bank-card masking.
    return redact_pii(text)[0]


def document_date(path: str, text: str) -> Optional[str]:
    front = re.match(r"\A---\s*\n([\s\S]*?)\n---(?:\n|$)", text)
    candidates = []
    if front:
        candidates += re.findall(r"(?m)^(?:date|created|created_at):\s*['\"]?(20\d{2}-\d{2}-\d{2})", front.group(1))
    candidates += DATE_RE.findall(path)
    for value in candidates:
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            continue
    return None


def category_for(path: str) -> str:
    p = PurePosixPath(path)
    name = p.stem.lower()
    if p.name == "DEPLOY_LOG.md" or "deployment" in name:
        return "deployment"
    if re.search(r"verification|acceptance|review|audit|验收|审查|审计", name):
        return "review"
    if re.search(r"findings|progress|发现|进度", name):
        return "progress"
    if re.search(r"task[_-]plan|execution.plan|implementation|实施|任务", name):
        return "plan"
    if "/research/" in "/" + path or "/business/" in path or re.search(r"research|研究|分析", name):
        return "research"
    if name.endswith("design") or "设计" in name:
        return "design"
    if re.search(r"(?:^|[-_])plan(?:$|[-_])", name) or path.startswith("docs/plans/"):
        return "plan"
    if "/audits/" in path or "/reviews/" in path:
        return "review"
    return "design"


def metadata(path: str, text: str) -> dict:
    p = PurePosixPath(path)
    title_match = re.search(r"^#\s+(.+?)\s*#*\s*$", text, re.M)
    title = title_match.group(1) if title_match else p.stem
    # A phase file's parent identifies its subject; flat files retain their date.
    topic = str(p.parent) if GENERIC.fullmatch(p.stem) else str(p.with_name(SUFFIX.sub("", p.stem)))
    if p.parent.name not in {"specs", "plans", "design", "research", "hermes_plan", "business", "reviews", "audits", "mvp", "superpowers", "."}:
        topic = str(p.parent)
    topic_name = PurePosixPath(topic).name
    if DATE_RE.search(topic_name):
        topic = topic_name
    paragraphs = re.sub(r"\A---\s*\n[\s\S]*?\n---\s*\n", "", text)
    paragraphs = re.sub(r"```[\s\S]*?```", "", paragraphs)
    lines = [line.strip() for line in paragraphs.splitlines() if line.strip() and not re.match(r"^[#|>\-]", line.strip())]
    summary = re.sub(r"[!*`\[\]]", "", " ".join(lines))[:180]
    source = "/".join(p.parts[:2]) if p.parts[0] == "docs" and len(p.parts) > 2 else (p.parts[0] if len(p.parts) > 1 else "项目根目录")
    return {"title": title[:200], "summary": summary, "date": document_date(path, text),
            "category": category_for(path), "topic": topic, "source": source}
