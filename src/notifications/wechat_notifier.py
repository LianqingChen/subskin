"""WeChat Notifier for daily automated notifications.

Primary delivery: writes formatted brief to /root/subskin/data/briefings/
for pickup by Hermes cronjob (hermes_daily_brief) which sends via
the Hermes weixin channel.

Fallback: openclaw CLI (may have expired WeChat sessions).
"""

from __future__ import annotations

import subprocess
import tempfile
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from src.exceptions import APIError
from src.utils.incremental_tracker import DailySummary, UpdateType
from src.utils.logger import get_logger


logger = get_logger(__name__)


class WeChatNotifier:
    """WeChat Notifier using OpenClaw CLI command.
    
    This notifier sends daily update summaries to your personal WeChat
    by calling the `openclaw message send` CLI command directly.
    This is the most reliable approach when SubSkin and OpenClaw are
    running on the same machine.
    """
    
    def __init__(
        self,
        channel: str = "openclaw-weixin",
        target: str = "o9cq80xDxxnZ9B-8BCXQkbOXnPag@im.wechat",
        openclaw_path: str = "openclaw",
        timeout: int = 60,
    ) -> None:
        """Initialize the WeChat notifier.
        
        Args:
            channel: OpenClaw channel for WeChat (default: openclaw-weixin)
            target: Target chat ID (your WeChat user ID)
            openclaw_path: Path to openclaw CLI (default: openclaw in PATH)
            timeout: Command timeout in seconds
        """
        self.channel = channel
        self.target = target
        self.openclaw_path = openclaw_path
        self.timeout = timeout
    
    def send_message(self, text: str) -> bool:
        """Send plain text message to WeChat.
        
        Primary: write brief to file for Hermes cronjob pickup.
        Fallback: try openclaw CLI (may be stale/expired).
        
        Args:
            text: Message text to send
            
        Returns:
            True if at least the file was written successfully
        """
        success = False
        
        # PRIMARY: Write brief to file for Hermes delivery
        try:
            brief_dir = "/root/subskin/data/briefings"
            os.makedirs(brief_dir, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            brief_path = os.path.join(brief_dir, f"daily_{date_str}.md")
            with open(brief_path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Briefing written to {brief_path} for Hermes delivery")
            success = True
        except Exception as e:
            logger.error(f"Failed to write briefing file: {str(e)}")
        
        # FALLBACK: Try openclaw CLI
        try:
            cmd = [
                self.openclaw_path,
                "message",
                "send",
                "--channel", self.channel,
                "--target", self.target,
                "--message", "-",
            ]
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if result.returncode == 0:
                logger.info("WeChat message sent successfully via openclaw CLI")
            else:
                logger.warning(f"OpenClaw send failed (exit {result.returncode}): {result.stderr}")
        except Exception as e:
            logger.warning(f"OpenClaw send exception: {str(e)}")
        
        return success
    
    def format_daily_summary(self, summary: dict[str, Any]) -> str:
        """Format daily update summary for WeChat.

        Uses the S/A/B/C/D authority tier framework for source categorization.

        Args:
            summary: Daily summary from incremental tracker (dict)

        Returns:
            Formatted markdown text ready for sending
        """
        from collections import defaultdict

        date_obj = datetime.strptime(summary["date"], "%Y-%m-%d")
        date_str = date_obj.strftime("%Y年%m月%d日")

        source_counts = defaultdict(int)
        source_new_items = defaultdict(list)
        details = summary.get("details", [])
        for d in details:
            source = d.get("source", "other")
            items = d.get("change_details", {}).get("items_collected", 0)
            source_counts[source] += (items or 1)
            title = d.get("resource_title", "")[:80]
            if title:
                source_new_items[source].append(title)

        lines = [
            f"🌿 **SubSkin 每日简报 — {date_str}**\n",
        ]

        tier_map = {
            "pubmed": ("S/A 📜", "PubMed 权威研究论文"),
            "crossref": ("S/A 📜", "CrossRef 学术论文"),
            "semantic_scholar": ("S/A 📜", "Semantic Scholar 学术"),
            "cma": ("C 🏥", "中华医学会科普"),
            "clinical_trials": ("B 💊", "ClinicalTrials 新药试验"),
            "foundation_news": ("B/C 📰", "基金会与行业动态"),
            "omicsdi": ("B 🧬", "OmicsDI 组学数据"),
            "medical_content": ("C/D 📚", "医学科普与用药参考"),
        }

        total_new = 0
        found_any = False
        for crawler_id, (tier_label, name) in tier_map.items():
            count = source_counts.get(crawler_id, 0)
            total_new += count
            if count > 0:
                found_any = True
                items = source_new_items.get(crawler_id, [])
                preview = ""
                if items:
                    first = items[0]
                    preview = f" — {first[:50]}{'...' if len(first) > 50 else ''}"
                lines.append(f"{tier_label} **{name}**: +{count}{preview}")
            else:
                lines.append(f"{tier_label} **{name}**: —")

        if not found_any:
            lines.append("\n🔔 今日所有数据源均无更新。")

        lines.append(f"\n📊 **今日共新增/更新**: {total_new} 项")
        lines.append(f"📁 数据已保存至 `/root/subskin/data/raw/`")

        if total_new > 0:
            lines.append(f"\n💡 今日新增内容可通过[小白助手](/chat)查询最新信息。")

        lines.append(f"\n—— SubSkin · 每日凌晨5点自动采集 · {date_str}")

        return "\n".join(lines)
    
    def send_daily_summary(self, summary: dict[str, Any]) -> bool:
        """Send formatted daily summary to WeChat.
        
        Args:
            summary: Daily summary from incremental tracker
            
        Returns:
            True if sent successfully
        """
        try:
            text = self.format_daily_summary(summary)
            new_papers = summary.get("new_papers", 0)
            new_trials = summary.get("new_trials", 0)
            success = self.send_message(text)
            if success:
                logger.info(
                    f"Daily summary sent: {new_papers} new papers, "
                    f"{new_trials} new trials"
                )
            return success
        except Exception as e:
            logger.error(f"Failed to send daily summary to WeChat: {str(e)}")
            return False
    
    def send_error_alert(self, error_message: str) -> bool:
        """Send error alert to WeChat.
        
        Args:
            error_message: Description of the error
            
        """
        text = (
            "⚠️ **SubSkin 运行告警\n\n"
            f"错误信息: {error_message}\n\n"
            "请检查日志排查问题。"
        )
        return self.send_message(text)
