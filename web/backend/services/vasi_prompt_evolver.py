"""
VASI Prompt 自我进化引擎 (Phase 2)

核心原理:
  利用千问云 VLM 的上下文学习 (In-Context Learning) 能力，
  将用户修正过的高质量样本自动转为 few-shot 示例注入 prompt，
  让 VLM 从历史经验中学习，减少重复性错误。

进化闭环:
  样本库新增 → 多样性筛选 → few-shot 组装 → prompt 版本 → shadow eval → 部署/回滚
"""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from web.backend.models.vasi import VasiTrainingSample, VasiModelVersion

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

MAX_FEW_SHOT_EXAMPLES = 3          # 最多3个示例（避免prompt过长）
MIN_SAMPLE_DICE = 0.4              # 最低Dice系数（用户修正显著改善了结果）
DIVERSITY_THRESHOLD = 0.3          # 新示例与已有示例的最低差异度
AUTO_REFRESH_THRESHOLD = 20        # 新增20个高质量样本后自动刷新
MAX_PROMPT_HISTORY = 10            # 保留最近10个prompt版本


# ══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FewShotExample:
    """一个 few-shot 示例"""
    sample_id: int
    body_site: str
    fitzpatrick_type: Optional[str]
    quality_level: Optional[str]
    ai_lesion_count: int
    user_lesion_count: int
    dice_score: Optional[float]
    area_error_pct: Optional[float]
    key_difference: str            # 自然语言描述的差异
    lesson_learned: str            # 学到的经验
    usage_count: int
    diversity_score: float = 1.0   # 用于最大化多样性的评分


@dataclass
class PromptVersion:
    """一个 prompt 版本"""
    version_tag: str
    prompt_hash: str
    prompt_text: str
    few_shot_ids: List[int]
    metrics: Dict[str, float] = field(default_factory=dict)
    sample_count: int = 0
    is_active: bool = False
    created_at: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# PromptEvolver — 主服务
# ══════════════════════════════════════════════════════════════════════════════

class VasiPromptEvolver:
    """VLM prompt 自我进化引擎。

    三层 prompt 结构:
      System: 固定角色定义 + 任务框架
      Few-shot: 动态选择的参考案例（从用户修正中学习）
      Task: 当前照片的具体分析要求
    """

    def __init__(self, db: Session):
        self.db = db
        self._current_version: Optional[PromptVersion] = None
        self._current_prompt: Optional[str] = None
        self._loaded = False

    # ── Few-shot 示例选择 ──

    def select_few_shot_examples(
        self,
        body_site: str,
        fitzpatrick: Optional[str] = None,
        max_examples: int = MAX_FEW_SHOT_EXAMPLES,
    ) -> List[FewShotExample]:
        """从训练样本库中筛选最相关的 few-shot 示例。

        筛选策略（按优先级）:
          1. 同部位优先 (body_site match)
          2. 相似肤色优先 (fitzpatrick match)
          3. 高质量优先 (Dice > MIN_SAMPLE_DICE)
          4. 多样性保证 (不同样本间关键差异不重复)
        """
        samples = self._get_candidate_samples(body_site, fitzpatrick)
        if not samples:
            return []

        examples: List[FewShotExample] = []
        used_diffs: set = set()

        for s in samples:
            if len(examples) >= max_examples:
                break

            ex = self._sample_to_example(s)
            if ex is None:
                continue

            # 多样性检查: 新示例的关键差异不能与已有示例重复
            diff_key = self._normalize_key(ex.key_difference)
            if diff_key in used_diffs:
                continue

            # 计算多样性评分
            if examples:
                ex.diversity_score = self._compute_diversity(ex, examples)

            examples.append(ex)
            used_diffs.add(diff_key)

        # 按 相关性 × 多样性 排序
        examples.sort(
            key=lambda e: (0.5 * e.dice_score + 0.5 * e.diversity_score)
            if e.dice_score else 0,
            reverse=True,
        )
        return examples[:max_examples]

    def _get_candidate_samples(
        self, body_site: str, fitzpatrick: Optional[str] = None
    ) -> List[VasiTrainingSample]:
        """获取候选训练样本"""
        query = self.db.query(VasiTrainingSample).filter(
            VasiTrainingSample.is_active == True,
            VasiTrainingSample.user_mask_b64 != None,
            VasiTrainingSample.contour_diff_json != None,
        )

        # 优先同部位
        same_site = query.filter(VasiTrainingSample.body_site == body_site).order_by(
            VasiTrainingSample.dice_score.desc()
        ).limit(20).all()

        # 补充其他部位的样本
        other_sites = query.filter(
            VasiTrainingSample.body_site != body_site
        ).order_by(
            VasiTrainingSample.dice_score.desc()
        ).limit(10).all()

        # 合并: 同部位在前
        candidates = list(same_site) + list(other_sites)

        # 按 Dice 过滤
        candidates = [s for s in candidates if s.dice_score and s.dice_score >= MIN_SAMPLE_DICE]

        # 肤色优先（secondary sort）
        if fitzpatrick:
            candidates.sort(
                key=lambda s: (
                    0 if s.fitzpatrick_type == fitzpatrick else 1,
                    -(s.dice_score or 0),
                )
            )

        return candidates

    def _sample_to_example(self, sample: VasiTrainingSample) -> Optional[FewShotExample]:
        """将训练样本转为 few-shot 示例"""
        try:
            diff_data = json.loads(sample.contour_diff_json or "{}")
        except (json.JSONDecodeError, TypeError):
            diff_data = {}

        # 解析 AI 和用户的白斑数量
        ai_count = self._count_lesions(sample.ai_contours_json)
        user_count = self._count_lesions(sample.user_contours_json)

        # 生成关键差异描述
        key_diff = self._describe_difference(ai_count, user_count, sample.area_error_pct, diff_data)

        # 生成学到的经验
        lesson = self._derive_lesson(ai_count, user_count, sample.dice_score, sample.body_site)

        return FewShotExample(
            sample_id=sample.id,
            body_site=sample.body_site,
            fitzpatrick_type=sample.fitzpatrick_type,
            quality_level=sample.quality_level,
            ai_lesion_count=ai_count,
            user_lesion_count=user_count,
            dice_score=sample.dice_score,
            area_error_pct=sample.area_error_pct,
            key_difference=key_diff,
            lesson_learned=lesson,
            usage_count=sample.usage_count or 0,
        )

    def _count_lesions(self, contours_json: Optional[str]) -> int:
        """从contour JSON中统计白斑数量"""
        if not contours_json:
            return 0
        try:
            contours = json.loads(contours_json)
            if isinstance(contours, list):
                return len(contours)
        except (json.JSONDecodeError, TypeError):
            pass
        return 0

    def _describe_difference(
        self,
        ai_count: int,
        user_count: int,
        area_error_pct: Optional[float],
        diff_data: dict,
    ) -> str:
        """生成人类可读的差异描述"""
        if ai_count > user_count:
            over = ai_count - user_count
            return f"AI 多检测了 {over} 个白斑区域（疑似误判正常皮肤或高光为白斑）"
        elif user_count > ai_count:
            missed = user_count - ai_count
            return f"AI 漏检了 {missed} 个白斑区域（白斑面积小或颜色较浅未被识别）"
        elif area_error_pct and abs(area_error_pct) > 10:
            direction = "偏大" if area_error_pct > 0 else "偏小"
            return f"AI 白斑面积判断{direction}{abs(area_error_pct):.0f}%（边缘定位不够精确）"
        else:
            return "AI 白斑数量和面积基本准确，用户做了细微边界调整"

    def _derive_lesson(
        self,
        ai_count: int,
        user_count: int,
        dice_score: Optional[float],
        body_site: str,
    ) -> str:
        """从差异中推导经验教训"""
        lessons = {
            ("面部", True): "面部骨骼突起处（眉骨、鼻梁、颧骨）的高光区域易被误判为白斑，需结合肤色对比度综合分析",
            ("手部", False): "手指间缝隙处的小面积白斑容易被忽略，需要主动搜索手部所有皮肤褶皱区域",
            ("躯干", True): "躯干区域面积大，AI 可能将乳白色正常皮肤误判为轻度色素脱失，需提高对比度阈值",
            ("手部", True): "手腕、指关节等皮肤褶皱处的高光反射易被误判，需排除这些位置的非白斑区域",
            ("颈部", True): "颈部阴影区域易导致误判，光照不均匀时需要更保守的判断策略",
            ("面部", False): "面部小面积白斑（<2%）容易被忽略，需仔细检查发际线、眉毛周围等边界区域",
            ("足部", False): "足部白斑常分布在趾缝和足底边缘，这些位置容易被忽略",
        }

        # 找到最匹配的经验
        over_detected = ai_count > user_count
        site_short = body_site[:2] if len(body_site) >= 2 else body_site

        for (site_prefix, over_key), lesson in lessons.items():
            if site_prefix in body_site and over_key == over_detected:
                return lesson

        # 通用经验
        if over_detected:
            return "减少对正常肤色高亮区域的误判，只标记明显色素脱失的白斑"
        else:
            return "提高对小面积、低对比度白斑的检测灵敏度，不遗漏任何疑似区域"

    def _normalize_key(self, text: str) -> str:
        """标准化文本为短键，用于去重检查"""
        # 取前30字去重
        return text[:30].strip()

    def _compute_diversity(
        self,
        new_ex: FewShotExample,
        existing: List[FewShotExample],
    ) -> float:
        """计算新示例与已有示例的多样性评分 (0-1)"""
        if not existing:
            return 1.0

        scores = []
        for ex in existing:
            # 部位差异
            site_score = 0.0 if new_ex.body_site == ex.body_site else 1.0
            # 差异类型差异（过检 vs 漏检）
            type_score = 0.0 if (
                (new_ex.ai_lesion_count > new_ex.user_lesion_count)
                == (ex.ai_lesion_count > ex.user_lesion_count)
            ) else 1.0
            scores.append(0.6 * site_score + 0.4 * type_score)

        return sum(scores) / len(scores)

    # ── Prompt 构建 ──

    def build_system_prompt(self) -> str:
        """构建固定的系统 prompt"""
        return """你是一位经验丰富的皮肤科医生，专门从事白癜风（vitiligo）的诊断与分析。
你的任务是在患者上传的照片中识别白斑的位置、范围和色素脱失程度。

【色素脱失等级标准】
- 0级(无): 正常肤色，无色素脱失。对比度 < 0.10
- 1级(轻度): 轻度色素减退，隐约可见淡白色。对比度 0.10-0.20
- 2级(中度): 明显色素减退，呈乳白色。对比度 0.20-0.40
- 3级(重度): 几乎完全色素脱失，呈瓷白色或纯白色。对比度 > 0.40

【重要提醒】
- 区分白斑与照片高光/反光区域
- 区分白斑与疤痕、白化痣等非白斑病变
- 分散的白斑碎片必须独立标注，不要合并
- bbox 必须紧贴白斑边界"""

    def build_few_shot_section(self, examples: List[FewShotExample]) -> str:
        """构建动态 few-shot 示例段落"""
        if not examples:
            return ""

        lines = ["\n【参考案例 — 从历史用户修正中学习】\n"]
        for i, ex in enumerate(examples, 1):
            lines.append(f"案例{i} [{ex.body_site}部位]")
            lines.append(f"  AI 最初检测到 {ex.ai_lesion_count} 个白斑，用户修正后确认为 {ex.user_lesion_count} 个白斑。")
            lines.append(f"  关键差异: {ex.key_difference}")
            lines.append(f"  📝 学到的经验: {ex.lesson_learned}")
            lines.append("")

        return "\n".join(lines)

    def build_task_section(self) -> str:
        """构建任务描述（从现有 prompt 提取核心部分）"""
        return """
================================================================
【检测流程】
================================================================
1. **全量检测**: 仔细扫描整张照片中的所有可见皮肤区域，找出所有疑似白斑，
   包括边界处的小斑点（直径≥皮肤区域3%）。不要遗漏任何一处。
2. **逐斑标注**: 每发现一个独立的白斑斑块，立即标注 bbox + center + edge_points。
3. **边缘点标注**: 对每个白斑，标注3-5个边界关键点（不规则形状的转角处）。
4. **色差识别优先级**: 
   - 最明显的白色/乳白色斑块 → 高置信度 (0.85+)
   - 较淡的色素减退区域 → 中置信度 (0.6-0.85)  
   - 边界模糊的浅色区域 → 低置信度 (0.3-0.6)，仍需标注

================================================================
【自适应肤色分析】
================================================================
1. 判断照片中正常皮肤的基础肤色类型(Fitzpatrick I-VI)
2. 浅色皮肤(I-III): 注意区分正常肤色和轻度白斑。对比度<0.1 大概率不是白斑。
3. 深色皮肤(IV-VI): 提高检测灵敏度。对比度>0.12 即可判定为可疑。

================================================================
返回 JSON（只返回 JSON，不要任何其他文字）:
================================================================
{
  "visual_features": {
    "visibility": {"level": "visible|faint|subtle", "contrast_ratio": 0.0, "description": "..."},
    "color": {"level": "pale_white|milky_white|porcelain_white|pure_white", "skin_fitzpatrick": "III", "description": "..."},
    "border": {"level": "clear|partial|unclear", "sharpness_ratio": 0.0, "description": "..."},
    "shape": {"description": "..."},
    "surface": {"texture": "smooth|scaly|atrophic|other", "description": "..."},
    "distribution": {"pattern": "localized|segmental|bilateral|generalized|scattered", "patch_count": "数量", "description": "..."},
    "similarity_note": "...",
    "recommendation": "..."
  },
  "skin_region": {
    "bbox": [x1,y1,x2,y2], "confidence": 0.9,
    "fitzpatrick_type": "III", "skin_tone_notes": "..."
  },
  "suspected_lesions": [{
    "label": "白斑1",
    "center": [x,y],
    "bbox": [x1,y1,x2,y2],
    "edge_points": [[x1,y1],[x2,y2],[x3,y3]],
    "estimated_size_percent": 5.0,
    "depigmentation_level": 2,
    "contrast_to_skin": 0.35,
    "boundary_type": "clear|diffuse|mixed",
    "confidence": 0.9
  }],
  "overall_depigmentation": 2,
  "vasi_score": 0,
  "area_percentage_estimate": 0,
  "classification": "节段型|非节段型|混合型|未确定",
  "stage": "进展期|稳定期|好转期",
  "body_site_confirmed": "面部|颈部|手部|腹部|背部|上肢|下肢|足部|其他",
  "confidence": 0.8,
  "limitations": ["..."],
  "details": {
    "patch_count_estimate": "总数量",
    "color_type": "纯白|乳白|灰白|淡白",
    "border_clarity": "清晰|模糊|部分清晰",
    "dominant_depigmentation": 2,
    "description": "80字以内的白斑特征描述"
  }
}"""

    def build_prompt(
        self,
        body_site: str,
        fitzpatrick: Optional[str] = None,
        image_quality: str = "good",
        use_few_shot: bool = True,
    ) -> str:
        """构建完整的 VLM prompt: 系统 + few-shot + 任务"""
        parts = [self.build_system_prompt()]

        if use_few_shot:
            examples = self.select_few_shot_examples(body_site, fitzpatrick)
            if examples:
                parts.append(self.build_few_shot_section(examples))

        parts.append(self.build_task_section())
        return "\n".join(parts)

    # ── Prompt 版本管理 ──

    def get_current_prompt(self) -> str:
        self._ensure_loaded()
        """获取当前活跃的 prompt"""
        if self._current_prompt:
            return self._current_prompt

        # Fallback: 返回默认 prompt（无few-shot）
        return self.build_prompt("面部", use_few_shot=False)

    def get_current_version(self) -> Optional[PromptVersion]:
        self._ensure_loaded()
        """获取当前活跃的 prompt 版本"""
        return self._current_version

    def _ensure_loaded(self) -> None:
        """Lazy-load the active version (safe to call on first access)."""
        if self._loaded:
            return
        self._loaded = True
        try:
            self._load_active_version_inner()
        except Exception as e:
            logger.warning("Failed to load active prompt version: %s", e)
            self._current_prompt = self.build_prompt("面部", use_few_shot=False)
            self._current_version = None

    def _load_active_version_inner(self) -> None:
        """从数据库加载当前活跃的 prompt 版本"""
        active = (
            self.db.query(VasiModelVersion)
            .filter(
                VasiModelVersion.is_active == True,
                VasiModelVersion.evolution_layer == "prompt",
            )
            .order_by(VasiModelVersion.deployed_at.desc())
            .first()
        )

        if active and active.changes_json:
            try:
                changes = json.loads(active.changes_json)
                prompt_text = changes.get("prompt_text")
                if prompt_text:
                    self._current_prompt = prompt_text
                    self._current_version = PromptVersion(
                        version_tag=active.version_tag,
                        prompt_hash=changes.get("prompt_hash", ""),
                        prompt_text=prompt_text,
                        few_shot_ids=changes.get("few_shot_ids", []),
                        metrics=json.loads(active.metrics_json or "{}"),
                        sample_count=active.sample_count or 0,
                        is_active=True,
                        created_at=active.deployed_at,
                    )
                    logger.info("Loaded active prompt version: %s", active.version_tag)
                    return
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning("Failed to parse active prompt version: %s", e)

        # No active version: build default
        self._current_prompt = self.build_prompt("面部", use_few_shot=False)
        self._current_version = None

    def _compute_prompt_hash(self, prompt_text: str) -> str:
        """计算 prompt 文本的 hash"""
        return hashlib.md5(prompt_text.encode("utf-8")).hexdigest()[:12]

    def deploy_prompt(self,
        prompt_text: str,
        few_shot_ids: List[int],
        metrics: Optional[Dict[str, float]] = None,
        deployed_by: Optional[int] = None,
    ) -> bool:
        """部署一个新的 prompt 版本。

        1. 将旧版本标记为非活跃
        2. 创建新版本记录
        3. 更新当前 prompt
        """
        # 去激活旧版本
        self.db.query(VasiModelVersion).filter(
            VasiModelVersion.evolution_layer == "prompt",
            VasiModelVersion.is_active == True,
        ).update({"is_active": False})

        prompt_hash = self._compute_prompt_hash(prompt_text)
        version_tag = f"prompt-evo-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{prompt_hash}"

        # 裁剪版本历史
        total = (
            self.db.query(VasiModelVersion)
            .filter(VasiModelVersion.evolution_layer == "prompt")
            .count()
        )
        if total >= MAX_PROMPT_HISTORY:
            oldest = (
                self.db.query(VasiModelVersion)
                .filter(
                    VasiModelVersion.evolution_layer == "prompt",
                    VasiModelVersion.is_active == False,
                )
                .order_by(VasiModelVersion.created_at.asc())
                .limit(total - MAX_PROMPT_HISTORY + 1)
                .all()
            )
            for v in oldest:
                self.db.delete(v)

        version = VasiModelVersion(
            version_tag=version_tag,
            description=f"Prompt evolution: {len(few_shot_ids)} few-shot examples",
            evolution_layer="prompt",
            changes_json=json.dumps({
                "prompt_text": prompt_text,
                "prompt_hash": prompt_hash,
                "few_shot_ids": few_shot_ids,
            }),
            metrics_json=json.dumps(metrics or {}),
            sample_count=len(few_shot_ids),
            is_active=True,
            deployed_at=datetime.utcnow(),
            deployed_by=deployed_by,
        )
        self.db.add(version)
        self.db.commit()

        # 更新当前
        self._current_prompt = prompt_text
        self._current_version = PromptVersion(
            version_tag=version_tag,
            prompt_hash=prompt_hash,
            prompt_text=prompt_text,
            few_shot_ids=few_shot_ids,
            metrics=metrics or {},
            sample_count=len(few_shot_ids),
            is_active=True,
            created_at=datetime.utcnow(),
        )

        self._mark_samples_used(few_shot_ids)
        logger.info("Deployed prompt version: %s (%d examples)", version_tag, len(few_shot_ids))
        return True

    def _mark_samples_used(self, sample_ids: List[int]) -> None:
        """标记训练样本已被使用"""
        if not sample_ids:
            return
        self.db.query(VasiTrainingSample).filter(
            VasiTrainingSample.id.in_(sample_ids)
        ).update(
            {"usage_count": VasiTrainingSample.usage_count + 1, "last_used_at": datetime.utcnow()},
            synchronize_session=False,
        )
        self.db.commit()

    # ── 自动进化触发 ──

    def should_evolve(self) -> Tuple[bool, int]:
        """检查是否应该触发 prompt 进化。

        Returns:
            (should_evolve, new_sample_count) — 新增样本数
        """
        if not self._current_version:
            # 没有当前版本：检查是否已有足够样本
            new_count = self._count_new_samples()
            return (new_count >= AUTO_REFRESH_THRESHOLD, new_count)

        # 有当前版本：检查自上次进化以来新增了多少样本
        last_deploy = self._current_version.created_at
        if not last_deploy:
            return (False, 0)

        new_count = self._count_new_samples(since=last_deploy)
        return (new_count >= AUTO_REFRESH_THRESHOLD, new_count)

    def _count_new_samples(self, since: Optional[datetime] = None) -> int:
        """统计新增的高质量训练样本数"""
        query = self.db.query(VasiTrainingSample).filter(
            VasiTrainingSample.is_active == True,
            VasiTrainingSample.user_mask_b64 != None,
            VasiTrainingSample.dice_score >= MIN_SAMPLE_DICE,
        )
        if since:
            query = query.filter(VasiTrainingSample.created_at >= since)
        return query.count()

    def get_evolution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取 prompt 进化历史"""
        versions = (
            self.db.query(VasiModelVersion)
            .filter(VasiModelVersion.evolution_layer == "prompt")
            .order_by(VasiModelVersion.deployed_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "version_tag": v.version_tag,
                "sample_count": v.sample_count,
                "metrics": json.loads(v.metrics_json or "{}"),
                "is_active": v.is_active,
                "deployed_at": v.deployed_at.isoformat() if v.deployed_at else None,
            }
            for v in versions
        ]

    def rollback(self) -> bool:
        """回滚到上一个 prompt 版本"""
        # 找到最近的非活跃版本
        prev = (
            self.db.query(VasiModelVersion)
            .filter(
                VasiModelVersion.evolution_layer == "prompt",
                VasiModelVersion.is_active == False,
            )
            .order_by(VasiModelVersion.deployed_at.desc())
            .first()
        )

        if not prev:
            logger.warning("No previous prompt version to rollback to")
            return False

        # 去激活当前版本
        self.db.query(VasiModelVersion).filter(
            VasiModelVersion.evolution_layer == "prompt",
            VasiModelVersion.is_active == True,
        ).update({"is_active": False})

        # 激活上一个版本
        prev.is_active = True
        prev.deployed_at = datetime.utcnow()
        self.db.commit()

        # 重新加载
        self._ensure_loaded()
        logger.info("Rolled back to prompt version: %s", prev.version_tag)
        return True


# ══════════════════════════════════════════════════════════════════════════════
# Module-level convenience
# ══════════════════════════════════════════════════════════════════════════════

# ═══ SELF-EVOLVING DISABLED (2026-06-13) — data insufficient for effective RL ═══
def get_prompt_evolver(db: Session) -> VasiPromptEvolver:
    return None  # DISABLED — insufficient training data

    """获取 VasiPromptEvolver 实例"""
    return VasiPromptEvolver(db)
