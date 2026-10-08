"""
模块级提示词配置服务层

将原先硬编码在 vasi.py / skin_report.py / medical/report_interpreter.py 中的
提示词收敛为可管理后台编辑的配置。运行时会优先读取 llm_prompts 表；
表内无有效配置时回退到本模块内置默认模板，保证幂等、可恢复。

准确度迭代闭环：管理后台改提示词 → 写入 DB（版本号自增）→ 服务层即时生效，
无需改代码 / 重启后端。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from web.backend.database.database import SessionLocal
from web.backend.database.models import LLMPrompt

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 内置默认提示词（单一事实来源，用于首次初始化与「恢复默认」）
# ══════════════════════════════════════════════════════════════════════════════

# ── VASI 白斑识别（视觉）──────────────────────────────────────────────────────
# 针对边缘 / 大小 / 颜色三个准确度维度做强化：
#   边缘：edge_points 均匀覆盖凸点+凹点，bbox 紧贴边界，boundary_type 三分类 + 边界置信度
#   大小：estimated_size_percent 与 bbox 面积自洽，size_category 分档
#   颜色：4 级色素脱失量化 + contrast_to_skin 阈值 + color_consistency 复色状态
VASI_VISION_PROMPT = """你是一位资深皮肤科AI助手，请精确分析这张皮肤照片中的白斑（白癜风）特征。

重要：你不是医生，不能医疗诊断。用"观察到""可见"等客观措辞。

【皮肤背景评估（先做这步）】
1. 观察照片中暴露的皮肤区域，估计整体肤色深浅（Fitzpatrick分型 I-VI：I最白易灼伤、VI最深不易灼伤）。
2. 白斑的"脱色"永远是相对于周围正常皮肤而言——必须先认准正常皮肤基线，再判断哪里更白。

【色素脱失等级量化标准（contrast_to_skin 据此判定）】
- 0级(无)：正常肤色，无色素脱失。对比度 < 0.10
- 1级(轻度)：轻度色素减退，隐约可见淡白色。对比度 0.10-0.20
- 2级(中度)：明显色素减退，呈乳白色。对比度 0.20-0.40
- 3级(重度)：几乎完全色素脱失，呈瓷白色或纯白色。对比度 > 0.40
contrast_to_skin = 白斑区与紧邻正常皮肤的明度差比值，范围0-1。

【必须区分的非白斑区域（重要，勿误判）】
- 照片高光/反光/过曝区域：呈镜面白，多在皮肤凸起处，边界常与光照方向一致，不是独立色斑。
- 疤痕、白化痣、花斑癣、炎症后色素减退：颜色/质地与白癜风不同，谨慎区分。
- 参考卡、衣物、背景：非皮肤区域，一律排除。
- 分散的白斑碎片必须各自独立标注，不要合并成一个大块。

【边缘识别要求（准确度核心，严格遵循）】
- bbox 必须紧贴白斑真实边界，不要留大边距，也不要切掉边缘。
- edge_points 给出 4-8 个沿白斑轮廓分布的边界关键点：必须同时覆盖最外凸点和最内凹点，并在轮廓上尽量均匀分布（不要集中在同一侧）。
- 边缘清晰(clear)的白斑：edge_points 沿可见色素过渡带外缘取点。
- 边缘模糊(diffuse)的白斑：edge_points 沿主观可辨的最外圈脱色带取点，并在 boundary_confidence 中标注不确定度。
- 每个白斑额外输出 boundary_confidence（0-1）：边界越清晰越高，模糊弥散越低。
- boundary_type 三分类：clear(清晰) / diffuse(模糊弥散) / mixed(混合)。

【大小识别要求（准确度核心）】
- estimated_size_percent = 白斑实际面积占整张照片面积的百分比（不是 bbox 面积）。
- bbox 面积必须 ≥ 白斑实际面积：estimated_size_percent 与 bbox 宽高乘积的比例（填充率）一般应在 0.3-0.9 之间，若差异过大说明 bbox 或面积估算有误，需重新校准。
- 每个白斑输出 size_category：tiny(微小,<1%) / small(小,1-3%) / medium(中,3-10%) / large(大,>10%)。

【颜色识别要求（准确度核心）】
- 颜色按白斑相对周围皮肤的脱色程度判定，不看绝对白度（浅肤色人轻微脱色也可能不明显）。
- color.level 五档：pale_white(淡白) / milky_white(乳白) / porcelain_white(瓷白) / pure_white(纯白)。
- 每个白斑输出 color_consistency：uniform(均匀脱色) / mottled(斑驳) / central_repigmentation(中央复色) / edge_repigmentation(边缘复色) / mixed(混合)。
- 中央复色/边缘内收提示病情好转，颜色描述需体现这一变化，不可与脱色等级矛盾。

【你需要输出的核心字段】
1. skin_region: 皮肤区域
   - bbox: [x1, y1, x2, y2] 照片中皮肤区域的归一化包围盒 (0-1)
   - fitzpatrick: 估计分型 "I"-"VI"
2. suspected_lesions: 疑似白斑列表，每项包含:
   - center: [x, y] 白斑几何中心 (0-1归一化坐标)
   - bbox: [x1, y1, x2, y2] 紧贴白斑边界的归一化包围盒 (0-1)
   - edge_points: [[x,y], ...] 4-8个沿白斑轮廓的归一化边界关键点 (0-1)，均匀覆盖凸点+凹点
   - estimated_size_percent: 占照片面积百分比 (数字)
   - size_category: tiny/small/medium/large
   - depigmentation_level: 1(轻度) / 2(中度) / 3(重度)
   - contrast_to_skin: 与周围正常皮肤的对比度 0-1 (按上述量化标准)
   - boundary_type: clear(清晰) / diffuse(模糊弥散) / mixed(混合)
   - boundary_confidence: 边界判定置信度 0-1
   - color_consistency: uniform/mottled/central_repigmentation/edge_repigmentation/mixed
   - confidence: 该处为白斑的置信度 0-1
3. visual_features: 视觉特征概述
   - visibility: {"level": visible/faint/subtle, "description": "..."}
   - color: {"level": pale_white/milky_white/porcelain_white/pure_white, "description": "..."}
   - border: {"level": clear/partial/unclear, "description": "..."}
   - shape: {"pattern": round/oval/irregular/linear, "description": "..."}
   - surface: {"texture": smooth/scaly/atrophic, "description": "..."}
   - distribution: {"pattern": localized/segmental/bilateral/generalized/scattered, "description": "..."}
   - similarity_note: 一句总结 (20字以内)
   - recommendation: 建议 (如"建议皮肤科就诊")
4. classification: 分型 (节段型/非节段型/混合型/未确定)
5. stage: 阶段 (进展期/稳定期/好转期)
6. overall_depigmentation: 整体脱色程度 1-3
7. confidence: 本次整体分析置信度 0-1

【输出要求】
- 只返回JSON，不要任何其他文字、不要markdown代码块。
- 所有坐标归一化到0-1 (左上角0,0 右下角1,1)。
- bbox/edge_points/center 必须互不矛盾：edge_points 应落在 bbox 内部或边缘，center 应在 bbox 内部。
- 如果没有白斑特征: suspected_lesions=[] 且 overall_depigmentation=0。

返回JSON格式:
{
  "skin_region": {
    "bbox": [0.10, 0.10, 0.90, 0.90],
    "fitzpatrick": "III"
  },
  "suspected_lesions": [{
    "center": [0.35, 0.42],
    "bbox": [0.28, 0.35, 0.42, 0.49],
    "edge_points": [[0.30, 0.40], [0.35, 0.36], [0.41, 0.42], [0.38, 0.48], [0.30, 0.47]],
    "estimated_size_percent": 8.0,
    "size_category": "medium",
    "depigmentation_level": 2,
    "contrast_to_skin": 0.35,
    "boundary_type": "clear",
    "boundary_confidence": 0.85,
    "color_consistency": "uniform",
    "confidence": 0.85
  }],
  "visual_features": {
    "visibility": {"level": "visible", "description": "..."},
    "color": {"level": "milky_white", "description": "..."},
    "border": {"level": "clear", "description": "..."},
    "shape": {"pattern": "round", "description": "..."},
    "surface": {"texture": "smooth", "description": "..."},
    "distribution": {"pattern": "localized", "description": "..."},
    "similarity_note": "...",
    "recommendation": "..."
  },
  "classification": "非节段型",
  "stage": "稳定期",
  "overall_depigmentation": 2,
  "confidence": 0.8
}"""


# ── 体检报告解读（视觉）───────────────────────────────────────────────────────
# 注意：保留 %s 占位符（用户信息 / 免责声明），与 report_interpreter 的 % 格式化对齐。
MEDICAL_REPORT_VISION_PROMPT = """你是一位面向白癜风白友的体检报告解读助手。请仔细阅读这份体检报告图片，提取所有检验指标并给出解读。
用户信息: %s

请输出JSON，格式如下：
{
  "risk_level": "low" | "medium" | "high" | "critical",
  "summary": "200字以内白友易懂总结",
  "parsed_indicators": [
    {"indicator_name": "指标名", "value": "检测值+单位", "status": "normal"/"high"/"low", "ref_range": "参考范围"}
  ],
  "abnormal_items": [
    {
      "indicator_name": "指标名",
      "value": "检测值+单位",
      "status": "high"/"low"/"critical",
      "interpretation": "通俗解释这个指标异常意味着什么",
      "possible_causes": ["可能原因1", "可能原因2"],
      "suggestions": ["建议1", "建议2"]
    }
  ],
  "recommendations": [
    {"content": "具体可执行建议"}
  ],
  "extracted_patient_info": {
    "name": "姓名",
    "gender": "男/女",
    "age": 35,
    "exam_date": "2025-01-15",
    "confidence": 0.9
  } | null,
  "disclaimer": "%s"
}

注意事项：
1. 请尽可能提取图片中所有可见的检验指标，包括指标名称、检测值、单位、参考范围
2. status判断：检测值在参考范围内为normal，偏高为high，偏低为low，严重偏离为critical
3. 特别关注与白癜风相关的指标（甲状腺功能、免疫指标、肝功能、微量元素等）
4. 从报告头部提取姓名、性别、年龄、体检日期等基本信息
5. 如果图片不是体检报告或无法识别，返回包含空指标和上传建议的JSON
6. 严格输出JSON，不要输出Markdown代码块或JSON以外的文字"""


# ── 白斑变化分析报告（对比）───────────────────────────────────────────────────
SKIN_REPORT_COMPARISON_PROMPT = """你是 SubSkin 的白癜风病情分析助手。请根据用户的白斑追踪数据，生成一份温暖、专业、非诊断的「白斑变化分析报告」。

报告范围：{period}
聚焦部位：{body_site}
数据来源：{data_source}

追踪数据（JSON）：
{payload}

输出要求（严格 JSON，不要 markdown 代码块或其他文字）：
{{
  "narrative": "150-300字，分2-3段。第一段概括整体趋势与时间跨度；第二段结合关键数据（VASI评分/面积/分型阶段或视觉特征）说明变化；第三段肯定用户的坚持记录。语气温暖，用'你'称呼。",
  "insights": ["3-5条洞察要点，每条一句话，基于数据，不夸大"],
  "recommendations": ["2-4条建议：提醒遵医嘱、保持规律记录、防晒保湿、规律作息等通用建议。不给具体药物/剂量方案"]
}}

红线：
- 你不是医生，不做医疗诊断，只用"观察到""数据显示"等客观措辞。
- 只基于提供的数据，不捏造事实或数值。
- 若数据来源含"日常照片估算"，需在 narrative 中提示"精确数值建议进行深度白斑评估"。
"""


# ── 白斑周报/月报叙事 ────────────────────────────────────────────────────────
SKIN_REPORT_PERIODIC_PROMPT = """你是 SubSkin 的白癜风病情分析助手。请根据用户本{period_name}的白斑追踪数据，生成一份温暖、专业、非诊断的「白斑{period_name}」。

报告范围：{period}
部位概览：{sites_overview}
数据来源：{data_source}

追踪数据（JSON）：
{payload}

输出要求（严格 JSON，不要 markdown 代码块或其他文字）：
{{
  "headline": "6-16字亮点标题。有好转时突出成果（如'面部复色中，白斑在缩小'）；无明显变化时客观描述（如'坚持记录{n_days}天，白斑保持稳定'）",
  "narrative": "150-300字，分2-3段。第一段概括本{period_name}整体趋势与记录情况；第二段分部位说明亮点（结合复色指数/面积变化/VASI数值）；第三段肯定用户的坚持。语气温暖，用'你'称呼。",
  "insights": ["3-5条洞察要点，每条一句话，基于数据，不夸大"],
  "recommendations": ["2-4条建议：遵医嘱、保持规律记录、防晒保湿、规律作息等。不给具体药物/剂量"]
}}

红线：
- 你不是医生，不做医疗诊断，只用"观察到""数据显示"等客观措辞。
- 只基于提供的数据，不捏造事实或数值。
- 复色（好转）判断必须有复色指数/色素岛/边缘内收等数据支撑，不得为鼓励而拔高。
- 低置信度（low_confidence）的部位结论要注明"仅供参考"。
- 若数据来源含"日常照片估算"，需在 narrative 中提示"精确数值建议进行深度白斑评估"。
"""


# ══════════════════════════════════════════════════════════════════════════════
# 默认模板注册表：module_key -> {prompt_key: (prompt_name, prompt_text)}
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_PROMPTS: Dict[str, Dict[str, Any]] = {
    "vasi": {
        "vision_analysis": ("白斑识别视觉分析", VASI_VISION_PROMPT),
    },
    "medical_report": {
        "vision_interpret": ("体检报告视觉解读", MEDICAL_REPORT_VISION_PROMPT),
    },
    "skin_report": {
        "comparison_report": ("白斑变化分析报告", SKIN_REPORT_COMPARISON_PROMPT),
        "periodic_report": ("白斑周报/月报叙事", SKIN_REPORT_PERIODIC_PROMPT),
    },
}


class LLMPromptService:
    """提示词配置服务（管理后台可编辑）"""

    @staticmethod
    def get_prompt(
        db: Session,
        module_key: str,
        prompt_key: str,
    ) -> str:
        """获取指定模块/键的生效提示词。

        优先读取 DB 中 is_active 的行；无则回退内置默认模板。
        绝不返回空字符串，保证调用方始终有可用的 prompt。
        """
        row = (
            db.query(LLMPrompt)
            .filter(
                LLMPrompt.module_key == module_key,
                LLMPrompt.prompt_key == prompt_key,
                LLMPrompt.is_active == True,
            )
            .order_by(LLMPrompt.version.desc())
            .first()
        )
        if row and row.prompt_text:
            return row.prompt_text

        default = DEFAULT_PROMPTS.get(module_key, {}).get(prompt_key)
        if default:
            return default[1]
        logger.warning("No prompt for %s/%s and no default", module_key, prompt_key)
        return ""

    @staticmethod
    def list_prompts(db: Session, module_key: Optional[str] = None) -> List[LLMPrompt]:
        q = db.query(LLMPrompt)
        if module_key:
            q = q.filter(LLMPrompt.module_key == module_key)
        return q.order_by(LLMPrompt.module_key, LLMPrompt.prompt_key).all()

    @staticmethod
    def upsert_prompt(
        db: Session,
        module_key: str,
        prompt_key: str,
        prompt_text: str,
        updated_by: Optional[int] = None,
    ) -> Optional[LLMPrompt]:
        """保存（新增或更新）提示词，版本号自增。"""
        default = DEFAULT_PROMPTS.get(module_key, {}).get(prompt_key)
        prompt_name = default[0] if default else prompt_key

        row = (
            db.query(LLMPrompt)
            .filter(
                LLMPrompt.module_key == module_key,
                LLMPrompt.prompt_key == prompt_key,
            )
            .first()
        )
        if row:
            row.prompt_text = prompt_text
            if not row.default_text and default:
                row.default_text = default[1]
            row.prompt_name = prompt_name
            row.version = (row.version or 0) + 1
            row.is_active = True
            row.updated_by = updated_by
            row.updated_at = datetime.now(timezone.utc)
        else:
            row = LLMPrompt(
                module_key=module_key,
                prompt_key=prompt_key,
                prompt_name=prompt_name,
                prompt_text=prompt_text,
                default_text=default[1] if default else None,
                version=1,
                is_active=True,
                updated_by=updated_by,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def reset_prompt(db: Session, module_key: str, prompt_key: str) -> Optional[LLMPrompt]:
        """恢复内置默认模板。"""
        default = DEFAULT_PROMPTS.get(module_key, {}).get(prompt_key)
        if not default:
            return None
        return LLMPromptService.upsert_prompt(
            db, module_key, prompt_key, default[1]
        )

    @staticmethod
    def ensure_defaults(db: Optional[Session] = None) -> int:
        """首次启动初始化：为缺失的 (module_key, prompt_key) 写入内置默认值。

        只做增量补齐，不覆盖已有人工编辑过的内容。返回新建行数。
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        created = 0
        try:
            for module_key, prompts in DEFAULT_PROMPTS.items():
                for prompt_key, (name, text) in prompts.items():
                    exists = (
                        db.query(LLMPrompt.id)
                        .filter(
                            LLMPrompt.module_key == module_key,
                            LLMPrompt.prompt_key == prompt_key,
                        )
                        .first()
                    )
                    if exists:
                        continue
                    db.add(
                        LLMPrompt(
                            module_key=module_key,
                            prompt_key=prompt_key,
                            prompt_name=name,
                            prompt_text=text,
                            default_text=text,
                            version=1,
                            is_active=True,
                        )
                    )
                    created += 1
            db.commit()
            if created:
                logger.info("Seeded %d LLM prompt defaults", created)
        except Exception as e:
            logger.error("Failed to seed LLM prompts: %s", e)
            db.rollback()
        finally:
            if close_db:
                db.close()
        return created
