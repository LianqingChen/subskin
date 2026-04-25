"""
从白白百科创建帖子到用户草稿箱
流程：下载封面图 → 上传到服务器 → 创建帖子 → 添加小白科普标签
"""

import hashlib
import os
import re
import sys
import urllib.request
from pathlib import Path
from datetime import datetime

# 设置环境
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/subskin.db")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from web.backend.database.models import (
    Base, User, CommunityCategory, Post, Tag, PostTag, PostImage,
)
from web.backend.services.community import CommunityService

USER_PHONE = "15810004327"
CATEGORY_ID = 1  # 治疗分享分类
TAG_NAME = "小白科普"

# 文章列表: (title, filename, image_search_keyword, image_url)
# 封面来源：DermNet / Wikimedia Commons (CC licensed)
ARTICLES = [
    {
        "title": "什么是白癜风",
        "file": "introduction/what-is-vitiligo.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Vitiligo_%28skin_condition%29_01.jpg/800px-Vitiligo_%28skin_condition%29_01.jpg",
    },
    {
        "title": "流行病学",
        "file": "epidemiology.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Vitiligo_%28skin_condition%29_02.jpg/800px-Vitiligo_%28skin_condition%29_02.jpg",
    },
    {
        "title": "病因与发病机制",
        "file": "causes/index.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Skin_%28histological_section%29_01.jpg/800px-Skin_%28histological_section%29_01.jpg",
    },
    {
        "title": "诊断方法",
        "file": "diagnosis/diagnosis.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Wood%27s_lamp_examination.jpg/800px-Wood%27s_lamp_examination.jpg",
    },
    {
        "title": "临床分型",
        "file": "diagnosis/classification.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Vitiligo_%28skin_condition%29_01.jpg/800px-Vitiligo_%28skin_condition%29_01.jpg",
    },
    {
        "title": "临床表现",
        "file": "diagnosis/clinical-manifestations.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Vitiligo_2020.jpg/800px-Vitiligo_2020.jpg",
    },
    {
        "title": "治疗原则",
        "file": "treatment/principles.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Dermatologist_examining_patient.jpg/800px-Dermatologist_examining_patient.jpg",
    },
    {
        "title": "药物治疗",
        "file": "treatment/medications.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Medical_prescription_bottles.jpg/800px-Medical_prescription_bottles.jpg",
    },
    {
        "title": "光疗",
        "file": "treatment/phototherapy.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/UV_light_therapy_machine.jpg/800px-UV_light_therapy_machine.jpg",
    },
    {
        "title": "移植治疗",
        "file": "treatment/transplantation.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Skin_graft_operation.jpg/800px-Skin_graft_operation.jpg",
    },
    {
        "title": "中医中药",
        "file": "treatment/chinese-medicine.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Chinese_herbal_medicine_01.jpg/800px-Chinese_herbal_medicine_01.jpg",
    },
    {
        "title": "饮食",
        "file": "lifestyle/diet.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Healthy_food_plate.jpg/800px-Healthy_food_plate.jpg",
    },
    {
        "title": "日常护理",
        "file": "lifestyle/care.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Sunscreen_application.jpg/800px-Sunscreen_application.jpg",
    },
    {
        "title": "心理调节",
        "file": "lifestyle/mental-health.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Peaceful_meditation.jpg/800px-Peaceful_meditation.jpg",
    },
    {
        "title": "临床试验",
        "file": "research/clinical-trials.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Clinical_trial_phases.jpg/800px-Clinical_trial_phases.jpg",
    },
    {
        "title": "新药研发",
        "file": "research/new-drugs.md",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Laboratory_research_01.jpg/800px-Laboratory_research_01.jpg",
    },
]

ENCYCLOPEDIA_DIR = Path(__file__).parent.parent / "web" / "vitepress" / "docs" / "encyclopedia"


def read_markdown(filepath: Path):
    """读取 Markdown 文件，提取标题和去掉 frontmatter 的内容"""
    content = filepath.read_text(encoding="utf-8")
    # 去掉 frontmatter (--- ... ---)
    content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
    # 去掉 enc-callout 警告框
    content = re.sub(r'<div class="enc-callout.*?</div>', "", content, flags=re.DOTALL)
    # 去掉 HTML 注释
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    # 从 frontmatter 提取标题
    title_match = re.search(r"^---\n.*?^title: (.+)$.*?\n---", filepath.read_text(encoding="utf-8"), re.MULTILINE)
    title = title_match.group(1) if title_match else filepath.stem
    return title, content.strip()


def markdown_to_html(md: str) -> str:
    """简单将 Markdown 转成 HTML (支持 ## ### ** ** 等基础语法)"""
    html = md
    # 标题 ## → <h2>
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    # 粗体
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    # 换行 → <p>
    paragraphs = []
    for p in html.split("\n\n"):
        p = p.strip()
        if not p:
            continue
        if p.startswith("<h") or p.startswith("<div") or p.startswith("<p"):
            paragraphs.append(p)
        else:
            # 行内换行 → <br>
            p = p.replace("\n", "<br>")
            paragraphs.append(f"<p>{p}</p>")
    return "\n".join(paragraphs)


def download_image(url: str, save_path: Path):
    """下载图片到本地"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SubSkin/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            save_path.write_bytes(data)
            return data
    except Exception as e:
        print(f"  ⚠️ 下载图片失败: {e}")
        return None


def ensure_tag(db, name: str) -> Tag:
    """确保标签存在"""
    tag = db.query(Tag).filter_by(name=name).first()
    if not tag:
        tag = Tag(name=name, usage_count=0)
        db.add(tag)
        db.flush()
    return tag


def main():
    print("=" * 60)
    print("白白百科 → 帖子草稿箱 转换工具")
    print("=" * 60)

    # 数据库连接
    db_path = Path("data/subskin.db")
    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path.absolute()}")
        return

    engine = create_engine(f"sqlite:///{db_path.absolute()}")
    Session = sessionmaker(bind=engine)
    db = Session()

    # 查找用户
    user = db.query(User).filter_by(phone=USER_PHONE).first()
    if not user:
        print(f"❌ 找不到用户: {USER_PHONE}")
        db.close()
        return
    print(f"✅ 用户: {user.username} (id={user.id}, phone={user.phone})")

    # 确保分类存在
    category = db.query(CommunityCategory).filter_by(id=CATEGORY_ID).first()
    if not category:
        print(f"❌ 找不到分类 id={CATEGORY_ID}")
        db.close()
        return
    print(f"✅ 分类: {category.name}")

    # 确保小白科普标签存在
    tag = ensure_tag(db, TAG_NAME)
    print(f"✅ 标签: {tag.name} (id={tag.id})")

    # 上传目录
    upload_dir = Path("data/uploads/community")
    upload_dir.mkdir(parents=True, exist_ok=True)

    service = CommunityService(db)
    created_count = 0
    skip_count = 0

    for article in ARTICLES:
        title = article["title"]
        filepath = ENCYCLOPEDIA_DIR / article["file"]
        image_url = article["image_url"]

        print(f"\n--- {title} ---")

        # 读取内容
        if not filepath.exists():
            print(f"  ⚠️ 文件不存在，跳过: {filepath}")
            continue

        _, md_content = read_markdown(filepath)
        html_content = markdown_to_html(md_content)
        # 添加医学声明（去掉原警告框，添加简短声明）
        html_content = f'<p><em>⚠️ 本文基于医学文献整理，仅供参考，不构成医疗建议。具体诊疗请咨询执业医师。</em></p>\n{html_content}'

        if not html_content.strip() or len(html_content) < 20:
            print(f"  ⚠️ 内容为空，跳过")
            continue

        # 下载并上传封面图片
        image_urls = []
        if image_url:
            ext = Path(image_url.split("?")[0]).suffix or ".jpg"
            tmp_file = Path(f"/tmp/enc_cover_{hashlib.md5(title.encode()).hexdigest()[:8]}{ext}")
            img_data = download_image(image_url, tmp_file)
            if img_data:
                try:
                    uploaded_url = service.upload_image(
                        user_id=user.id,
                        filename=tmp_file.name,
                        content=img_data,
                    )
                    image_urls = [uploaded_url]
                    print(f"  ✅ 封面图已上传: {uploaded_url}")
                except Exception as e:
                    print(f"  ⚠️ 上传图片失败: {e}")
            if tmp_file.exists():
                tmp_file.unlink()

        # 创建帖子（私密=草稿状态）
        try:
            post = service.create_post(
                user_id=user.id,
                title=title,
                content=html_content,
                category_id=CATEGORY_ID,
                image_urls=image_urls if image_urls else None,
                tag_names=[TAG_NAME],
                is_private=True,  # 草稿状态，不公开
                post_type="long",
            )
            print(f"  ✅ 帖子创建成功: id={post.id}, title={post.title[:30]}")
            created_count += 1
        except Exception as e:
            print(f"  ❌ 创建失败: {e}")
            import traceback
            traceback.print_exc()

    db.close()
    print(f"\n{'=' * 60}")
    print(f"✅ 完成！共创建 {created_count} 篇帖子到 {user.username} 的草稿箱")
    print(f"📌 标签: #{TAG_NAME}")
    print(f"💡 请登录后到「我的日记」查看草稿，审核后设为公开即可发布")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
