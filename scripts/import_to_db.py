import re
import sys
sys.path.insert(0, '/root/subskin')
from pathlib import Path
from web.backend.database.database import SessionLocal
from web.backend.database.models import EncyclopediaArticle

db = SessionLocal()
md_dir = Path('/root/subskin/web/vitepress/docs/encyclopedia')

category_map = {
    'introduction': '基础认知', 'causes': '基础认知', 'epidemiology': '基础认知',
    'diagnosis': '诊断与检查', 'treatment': '治疗方法',
    'lifestyle': '生活管理', 'research': '最新研究',
}
icon_map = {
    '基础认知': '🔬', '诊断与检查': '🩺', '治疗方法': '💊',
    '生活管理': '🌿', '最新研究': '🧪',
}


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', '', text).strip()


def extract_title_from_frontmatter(content: str, fallback_stem: str) -> str:
    """Extract title from YAML frontmatter's 'title:' field."""
    if content.startswith('---'):
        end = content.find('---', 3)
        if end > 0:
            frontmatter = content[3:end]
            for line in frontmatter.split('\n'):
                stripped = line.strip()
                if stripped.startswith('title:'):
                    return stripped[6:].strip().strip('"\'')
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('# '):
            return stripped[2:].strip()
    return fallback_stem.replace('-', ' ').replace('_', ' ')


def extract_summary(body: str, max_len: int = 100) -> str:
    """Extract a clean text summary from markdown body, skipping disclaimers and JS."""
    text = strip_html(body)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'const\s+\w+\s*=.*?(?=\n)', '', text)
    text = re.sub(r'\*\*|__|\*|_|`|>|\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^---$', '', text, flags=re.MULTILINE)
    text = re.sub(r'⚠️\s*医学声明.*?咨询.*?医师[。．]', '', text, flags=re.DOTALL)
    text = re.sub(r'⚠️\s*免责声明[：:].*?咨询.*?医[师生][。．]', '', text, flags=re.DOTALL)
    text = re.sub(r'具体诊疗请.*?医师[。．]', '', text)
    text = re.sub(r'\{[^}]*\}', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len] + ('…' if len(text) > max_len else '')


count = 0
for md_file in sorted(md_dir.rglob('*.md')):
    content = md_file.read_text(encoding='utf-8')
    if content.startswith('---'):
        end = content.find('---', 3)
        body = content[end + 3:].strip() if end > 0 else content
    else:
        body = content

    rel = md_file.relative_to(md_dir)
    slug = str(rel).replace('.md', '').replace('\\', '/')
    parts = list(rel.parts)
    first_dir = parts[0] if parts[0] != 'encyclopedia' else (parts[1] if len(parts) > 1 else '')
    category = category_map.get(first_dir, '其他')
    icon = icon_map.get(category, '📄')

    title = extract_title_from_frontmatter(content, md_file.stem)
    summary = extract_summary(body)

    manual_summaries = {
        'index': '由病友和医生共同维护的白癜风知识百科库，涵盖病因、诊断、治疗、生活管理等全方位科普内容。',
        'faq/common-questions': '病友们最常问的问题，基于最新医学研究给出客观回答。',
    }
    if slug in manual_summaries:
        summary = manual_summaries[slug]

    existing = db.query(EncyclopediaArticle).filter(EncyclopediaArticle.slug == slug).first()
    if existing:
        existing.title = title
        existing.content = body
        existing.category = category
        existing.icon = icon
        existing.summary = summary
    else:
        article = EncyclopediaArticle(
            slug=slug, title=title, category=category,
            icon=icon, content=body, summary=summary,
        )
        db.add(article)
    count += 1

db.commit()
print(f'Imported {count} articles')
db.close()
