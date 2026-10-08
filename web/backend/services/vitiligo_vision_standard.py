"""白斑视觉标准（全站唯一）— 测评与变化对比共用的识别规则基座。

SubSkin 全站对白斑的识别只允许一套标准。本模块导出统一的规则文本，
由两条视觉链路共同嵌入 prompt：
- 白斑测评（services/vasi.py / llm_prompt_service.VASI_VISION_PROMPT）
- 白斑变化配对对比（services/spot_compare.PAIR_COMPARE_PROMPT）

统一内容：
1. 皮肤基线规则：白斑永远相对周围正常皮肤判断（Fitzpatrick 基线）；
2. 色素脱失分级：0-3 级（与测评 contrast_to_skin 阈值一致）；
3. 非皮肤排除规则：衣物/背景/参考卡/高光阴影一律不算白斑或复色；
4. 复色三模式定义：毛囊点状 / 边缘内收 / 岛状。

改动本模块 = 全站标准同时变更，务必同步运行 llm-testing 回归集。
"""

SKIN_BASELINE_RULE = """【皮肤基线（先做这一步）】
1. 先观察照片中暴露的皮肤区域，估计整体肤色深浅（Fitzpatrick 分型 I-VI：I 最白，VI 最深）。
2. 白斑/脱色永远是相对于周围正常皮肤而言——必须先认准正常皮肤基线，再判断哪里更白。"""

DEPIGMENTATION_SCALE_RULE = """【色素脱失分级（全站统一标准）】
- 0级(无)：正常肤色，无色素脱失（与正常皮肤对比度 < 0.10）
- 1级(轻度)：轻度色素减退，隐约可见淡白色（0.10-0.20）
- 2级(中度)：明显色素减退，呈乳白色（0.20-0.40）
- 3级(重度)：几乎完全色素脱失，呈瓷白色或纯白色（> 0.40）
复色的定义：白斑区域脱失等级下降（如 2级→1级）或恢复为正常肤色（→0级）。"""

EXCLUSION_RULE = """【非皮肤区域排除（重要，勿误判）】
- 参考卡、衣物、毛发、背景、家具等非皮肤区域：一律排除，不得计为白斑，也不得计为复色。
- 照片高光/反光/过曝、阴影、纹身、疤痕：不属于白斑变化。
- 两图之间因拍摄条件（角度/距离/光线/穿衣）不同造成的差异，不属于病情变化。"""

REPIGMENTATION_MODES_RULE = """【复色（色素回归）三种经典模式】
- 毛囊点状复色：白斑内沿毛孔出现的针尖至米粒大小深色斑点
- 边缘内收/色素带：白斑边界由清晰锐利变模糊，或边缘出现环状色素带使白斑范围向内收缩
- 岛状复色：白斑内部出现成片色素岛并逐渐扩大、融合"""


def standard_rules_text(include_repigmentation_modes: bool = False) -> str:
    """拼装统一标准规则文本，供各视觉 prompt 嵌入。

    Args:
        include_repigmentation_modes: 对比类任务需要复色模式定义，单图识别可省略。
    """
    parts = [SKIN_BASELINE_RULE, DEPIGMENTATION_SCALE_RULE, EXCLUSION_RULE]
    if include_repigmentation_modes:
        parts.append(REPIGMENTATION_MODES_RULE)
    return "\n\n".join(parts)
