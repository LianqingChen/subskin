#!/usr/bin/env python
"""将 VitePress 的 Markdown 文件导入到百科全书数据库。

用法:
    python scripts/import_encyclopedia_md.py [--dry-run]
"""

import argparse
import hashlib
import sys
from pathlib import Path
from datetime import datetime, timezone

# 添加项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_category_from_path(filepath: Path, base_dir: Path) -> str:
    """从文件路径推断分类。"""
    rel = filepath.relative_to(base_dir)
    parts = list(rel.parts)
    if len(parts) <= 1:
        return "基础认知"

    # 一级目录映射
    category_map = {
        "introduction": "基础认知",
        "causes": "基础认知",
        "epidemiology": "基础认知",
        "diagnosis": "诊断与检查",
        "treatment": "治疗方法",
        "lifestyle": "生活管理",
        "research": "最新研究",
    }

    first_dir = parts[0] if parts[0] != "encyclopedia" else (parts[1] if len(parts) > 1 else "")
    return category_map.get(first_dir, "其他")


def get_icon_for_category(category: str) -> str:
    """根据分类返回图标。"""
    icon_map = {
        "基础认知": "🔬",
        "诊断与检查": "🩺",
        "治疗方法": "💊",
        "生活管理": "🌿",
        "最新研究": "🧪",
    }
    return icon_map.get(category, "📄")


def extract_frontmatter(content: str) -> tuple:
    """提取 Markdown frontmatter 和正文。"""
    if not content.startswith("---"):
        return {}, content

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}, content

    frontmatter_text = content[3:end_idx].strip()
    body = content[end_idx + 3:].strip()

    metadata = {}
    for line in frontmatter_text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("'\"")

    return metadata, body


def compute_slug(filepath: Path, base_dir: Path) -> str:
    """从文件路径计算 URL slug。"""
    rel = filepath.relative_to(base_dir)
    # 移除 .md 后缀
    path = str(rel).replace(".md", "")
    # 规范化路径
    return path.replace("\\", "/")


def import_encyclopedia(dry_run: bool = False) -> dict:
    """导入百科 Markdown 文件。"""
    md_dir = PROJECT_ROOT / "web" / "vitepress" / "docs" / "encyclopedia"

    if not md_dir.exists():
        print(f"❌ 目录不存在: {md_dir}")
        return {"imported": 0, "skipped": 0, "errors": 0}

    results = {"imported": 0, "skipped": 0, "errors": 0, "articles": []}

    md_files = list(md_dir.rglob("*.md"))
    print(f"📁 找到 {len(md_files)} 个 Markdown 文件")

    if dry_run:
        print("\n--- Dry Run 模式，不写入数据库 ---\n")

    for md_file in sorted(md_files):
        try:
            content = md_file.read_text(encoding="utf-8")
            metadata, body = extract_frontmatter(content)

            slug = compute_slug(md_file, md_dir)
            category = get_category_from_path(md_file, md_dir)
            icon = get_icon_for_category(category)

            title = metadata.get("title", md_file.stem.replace("-", " "))
            summary = metadata.get("description", "")[:200]

            if dry_run:
                print(f"  📄 [{category}] {slug}")
                print(f"     标题: {title}")
                print(f"     内容长度: {len(body)} 字符")
                results["imported"] += 1
            else:
                # 实际导入逻辑由 API 处理
                results["articles"].append({
                    "slug": slug,
                    "title": title,
                    "category": category,
                    "icon": icon,
                    "content": body,
                    "summary": summary,
                    "source_file": str(md_file.relative_to(PROJECT_ROOT)),
                })
                results["imported"] += 1

        except Exception as e:
            print(f"  ❌ 处理 {md_file} 失败: {e}")
            results["errors"] += 1

    return results


def main():
    parser = argparse.ArgumentParser(description="导入百科 Markdown 文件到数据库")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入数据库")
    args = parser.parse_args()

    print("📚 SubSkin 百科内容导入工具")
    print(f"📂 Markdown 目录: web/vitepress/docs/encyclopedia")
    print()

    results = import_encyclopedia(dry_run=args.dry_run)

    print(f"\n{'=' * 50}")
    print(f"✅ 成功: {results['imported']} 个文件")
    print(f"⏭️  跳过: {results['skipped']} 个文件")
    print(f"❌ 错误: {results['errors']} 个文件")

    if args.dry_run and results["articles"]:
        print(f"\n📋 待导入文章列表:")
        for article in results["articles"]:
            print(f"  - {article['slug']} ({article['category']})")

    return results


if __name__ == "__main__":
    main()
