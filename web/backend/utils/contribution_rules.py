"""Non-clinical contribution rules; unavailable capabilities stay explicit."""

import hashlib
from typing import Optional

VERSION = "2026-10-v1"
LEVELS = [
    {"level": 1, "name": "微光伙伴", "threshold": 0},
    {"level": 2, "name": "添柴伙伴", "threshold": 100},
    {"level": 3, "name": "同行共建者", "threshold": 500},
    {"level": 4, "name": "薪火共建者", "threshold": 1500},
    {"level": 5, "name": "星火守护者", "threshold": 5000},
]
RULES = [
    {
        "kind": "image_accepted",
        "title": "合格图片被采纳",
        "points": 10,
        "enabled": True,
        "note": "去重、质量复核与用途授权通过后，每张计一次",
    },
    {
        "kind": "mask_confirmed",
        "title": "完成图片范围核对",
        "points": 5,
        "enabled": True,
        "note": "本人明确核对且图片被采纳，同图任务计一次",
    },
    {
        "kind": "facts_completed",
        "title": "补充结构化事实",
        "points": 3,
        "enabled": False,
        "note": "采纳与对应授权流程完善后开放，允许回答不知道",
    },
    {
        "kind": "report_accepted",
        "title": "体检资料被采纳",
        "points": 15,
        "enabled": False,
        "note": "体检共建授权开放后计分，不鼓励额外检查",
    },
    {
        "kind": "doctor_reference",
        "title": "资料获得医生确认",
        "points": 20,
        "enabled": False,
        "note": "有认证医生、确认依据和版本后开放",
    },
    {
        "kind": "followup_series",
        "title": "完成同部位随访序列",
        "points": 30,
        "enabled": False,
        "note": "可比序列及随访协议完善后开放",
    },
]
BODY_SITES = [
    ("face", "面部"),
    ("neck", "颈部"),
    ("scalp", "头皮"),
    ("front", "躯干前面"),
    ("back", "躯干后面"),
    ("upper_arm", "上肢近端"),
    ("lower_arm", "上肢远端"),
    ("arms", "上肢（待细分）"),
    ("hands", "手部"),
    ("upper_leg", "下肢近端"),
    ("lower_leg", "下肢远端"),
    ("legs", "下肢（待细分）"),
    ("feet", "足部"),
    ("genitals", "生殖器"),
    ("other", "其他"),
    ("unknown", "待归类"),
]
BODY_ALIASES = {
    "面部": "face",
    "颈部": "neck",
    "头皮": "scalp",
    "手部": "hands",
    "躯干前面": "front",
    "胸部": "front",
    "腹部": "front",
    "chest": "front",
    "abdomen": "front",
    "躯干后面": "back",
    "背部": "back",
    "上背部": "back",
    "下背部": "back",
    "upper_back": "back",
    "lower_back": "back",
    "上肢近端": "upper_arm",
    "上肢远端": "lower_arm",
    "上肢": "arms",
    "左臂": "arms",
    "右臂": "arms",
    "left_arm": "arms",
    "right_arm": "arms",
    "左手": "hands",
    "右手": "hands",
    "left_hand": "hands",
    "right_hand": "hands",
    "下肢近端": "upper_leg",
    "下肢远端": "lower_leg",
    "下肢": "legs",
    "左腿": "legs",
    "右腿": "legs",
    "left_leg": "legs",
    "right_leg": "legs",
    "足部": "feet",
    "左脚": "feet",
    "右脚": "feet",
    "left_foot": "feet",
    "right_foot": "feet",
    "生殖器": "genitals",
    "其他": "other",
}


def body_site_code(value: Optional[str]) -> str:
    """Map facts to broad buckets without guessing finer sites."""
    if value in dict(BODY_SITES):
        return value
    return BODY_ALIASES.get(value or "", "unknown")


def award_key(fingerprint: str, kind: str) -> str:
    """Protocol retries and re-consent do not create another award."""
    return hashlib.sha256((fingerprint + ":" + kind).encode()).hexdigest()


def membership(points: int) -> dict:
    """Give actual progress, including the terminal level."""
    current = max(
        (x for x in LEVELS if x["threshold"] <= points), key=lambda x: x["threshold"]
    )
    upcoming = next((x for x in LEVELS if x["threshold"] > points), None)
    progress = (
        100
        if upcoming is None
        else round(
            100
            * (points - current["threshold"])
            / (upcoming["threshold"] - current["threshold"])
        )
    )
    return {
        "points": points,
        "current": current,
        "next": upcoming,
        "progress": progress,
        "remaining": max(0, upcoming["threshold"] - points) if upcoming else 0,
    }
