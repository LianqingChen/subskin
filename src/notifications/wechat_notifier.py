"""WeChat Notifier for daily automated notifications via OpenClaw.

This module sends daily notifications to your personal WeChat via OpenClaw
WeChat plugin. It uses the openclaw CLI command to send messages, which is
the most reliable way when running locally on the same server.
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
        """Send plain text message to WeChat using openclaw CLI.
        
        Args:
            text: Message text to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Use --message - to read message from stdin
            cmd = [
                self.openclaw_path,
                "message",
                "send",
                "--channel", self.channel,
                "--target", self.target,
                "--message", "-",
            ]
            
            logger.debug(f"Running: {' '.join(cmd)} (reading from stdin)")
            
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode == 0:
                logger.info("WeChat message sent successfully via openclaw CLI")
                return True
            else:
                logger.error(f"Failed to send WeChat message. Exit code: {result.returncode}")
                logger.error(f"Stderr: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send WeChat message: {str(e)}")
            return False
    
    def format_daily_summary(self, summary: dict[str, Any]) -> str:
        """Format daily update summary for WeChat.
        
        Args:
            summary: Daily summary from incremental tracker (dict)
            
        Returns:
            Formatted markdown text ready for sending
        """
        from datetime import datetime
        date_obj = datetime.strptime(summary["date"], "%Y-%m-%d")
        date_str = date_obj.strftime("%Y年%m月%d日")
        
        # Count by source category
        from collections import defaultdict
        source_counts = defaultdict(int)
        details = summary.get("details", [])
        for d in details:
            source = d.get("source", "other")
            source_counts[source] += d.get("change_details", {}).get("items_collected", 1)
        
        lines = [
            f"🌿 **SubSkin 每日更新摘要 - {date_str}**\n",
            "### 📊 按信息来源分类\n",
        ]
        
        # 分类统计 - 按照整理好的信息来源框架
        categories = [
            ("📜", "官方期刊与学术论文", "pubmed"),
            ("🏥", "医院官媒与临床机构", "clinical"),
            ("🌿", "特色诊疗指南", "traditional"),
            ("💊", "新药研发与临床试验", "clinical_trials"),
            ("📰", "新闻媒体与官方报道", "news"),
            ("💬", "患者社区", "community"),
        ]
        
        new_papers = summary.get("new_papers", 0)
        new_trials = summary.get("new_trials", 0)
        updated_trials = summary.get("updated_trials", 0)
        total_papers = summary.get("total_papers", 0)
        total_trials = summary.get("total_trials", 0)
        new_papers_with_summary = summary.get("new_papers_with_summary", 0)
        
        total_new = 0
        for emoji, name, key in categories:
            count = source_counts.get(key, 0)
            total_new += count
            if count > 0:
                lines.append(f"{emoji} **{name}**: +{count} 篇")
            else:
                lines.append(f"{emoji} **{name}**: 无更新")
        
        # JAK inhibitor trials (special focus for this project)
        jak_trials = [t for t in details if t.get("update_type") == "new_trial" and 
                     t.get("change_details", {}).get("is_jak", False)]
        if jak_trials:
            lines.append(f"\n🔬 重点关注: JAK 抑制剂相关试验: {len(jak_trials)} 项")
            for trial in jak_trials[:3]:  # Show top 3
                status_emoji = "🟢"  # Default to active
                lines.append(f"  {status_emoji} {trial.get('resource_title', 'Untitled')[:60]}...")
            if len(jak_trials) > 3:
                lines.append(f"  ...还有 {len(jak_trials) - 3} 项")
        
        # Total stats
        lines.append(f"\n### 📈 累计总量")
        lines.append(f"- 累计收录论文: **{total_papers + total_new}** 篇")
        lines.append(f"- 累计收录临床试验: **{total_trials}** 项")
        
        if new_papers_with_summary > 0:
            lines.append(f"- 完成AI翻译总结: {new_papers_with_summary} 篇")
        
        if new_papers > 0 or new_trials > 0:
            lines.append(f"\n✅ 数据已保存到 `/root/subskin/data/raw/`，可随时查看完整内容。")
        
        lines.append(f"\n—— SubSkin 项目 · 用AI缩短医学前沿和普通患者之间的知识鸿沟")
        
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
