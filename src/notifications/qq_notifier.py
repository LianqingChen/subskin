"""QQ Bot notifier for daily automated notifications.

This module sends daily notifications via go-cqhttp HTTP API.
Based on research findings: go-cqhttp + OneBot v11 protocol is recommended
for daily notifications due to QQ official bot's strict rate limits.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import requests

from src.exceptions import APIError
from src.utils.incremental_tracker import DailySummary, UpdateType
from src.utils.logger import get_logger


logger = get_logger(__name__)


class MessageType(str, Enum):
    """Type of QQ message target."""
    PRIVATE = "private"
    GROUP = "group"


class QQMessageFormat(str, Enum):
    """Message format options."""
    PLAIN = "plain"
    MARKDOWN = "markdown"
    JSON = "json"


class QQBotNotifier:
    """QQ Bot notifier using go-cqhttp HTTP API.
    
    This notifier sends messages to QQ via go-cqhttp running locally
    on Aliyun ECS. It implements retry logic and proper error handling.
    """
    
    def __init__(
        self,
        host: str = "http://127.0.0.1",
        port: int = 5700,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        """Initialize the QQ bot notifier.
        
        Args:
            host: go-cqhttp host (default: localhost)
            port: go-cqhttp HTTP port (default: 5700)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.base_url = f"{host}:{port}"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        
        # Configure session
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "SubSkin-Notifier/1.0"
        })
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to go-cqhttp with retry logic.
        
        Args:
            endpoint: API endpoint (without leading slash)
            data: Request payload
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            APIError: If all retries fail or response indicates error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{self.max_retries}: POST {url}")
                response = self.session.post(
                    url,
                    json=data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Check OneBot v11 response format
                if result.get("status") == "failed" or result.get("retcode") != 0:
                    error_msg = result.get("msg", "Unknown error")
                    logger.warning(f"go-cqhttp API error: {error_msg}")
                    
                    # Some errors are retryable
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        raise APIError(f"go-cqhttp API failed: {error_msg}")
                
                return result
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise APIError(f"Failed to connect to go-cqhttp after {self.max_retries} attempts: {e}")
        
        # Should not reach here
        raise APIError("Request failed after all retries")
    
    def send_private_message(
        self,
        user_id: Union[str, int],
        message: str,
        auto_escape: bool = False
    ) -> Dict[str, Any]:
        """Send private message to a user.
        
        Args:
            user_id: QQ user ID
            message: Message content
            auto_escape: Whether to escape CQ codes
            
        Returns:
            API response
        """
        data = {
            "user_id": str(user_id),
            "message": message,
            "auto_escape": auto_escape
        }
        return self._make_request("send_private_msg", data)
    
    def send_group_message(
        self,
        group_id: Union[str, int],
        message: str,
        auto_escape: bool = False
    ) -> Dict[str, Any]:
        """Send message to a group.
        
        Args:
            group_id: QQ group ID
            message: Message content
            auto_escape: Whether to escape CQ codes
            
        Returns:
            API response
        """
        data = {
            "group_id": str(group_id),
            "message": message,
            "auto_escape": auto_escape
        }
        return self._make_request("send_group_msg", data)
    
    def send_message(
        self,
        message_type: MessageType,
        target_id: Union[str, int],
        message: str,
        auto_escape: bool = False
    ) -> Dict[str, Any]:
        """Generic send message method.
        
        Args:
            message_type: Type of message (private or group)
            target_id: Target user or group ID
            message: Message content
            auto_escape: Whether to escape CQ codes
            
        Returns:
            API response
            
        Raises:
            ValueError: If message_type is invalid
        """
        if message_type == MessageType.PRIVATE:
            return self.send_private_message(target_id, message, auto_escape)
        elif message_type == MessageType.GROUP:
            return self.send_group_message(target_id, message, auto_escape)
        else:
            raise ValueError(f"Unknown message type: {message_type}")
    
    def test_connection(self) -> bool:
        """Test connection to go-cqhttp.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/get_status", timeout=5)
            response.raise_for_status()
            result = response.json()
            return result.get("status") == "ok" or result.get("retcode") == 0
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False
    
    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()


def format_daily_notification(summary: DailySummary) -> str:
    """Format daily notification message from update summary.
    
    Args:
        summary: Daily summary of updates
        
    Returns:
        Formatted message for QQ bot
    """
    date_str = summary["date"]
    if date_str == datetime.now().date().isoformat():
        date_display = "今日"
    else:
        date_display = date_str
    
    # Calculate totals
    total_new = summary["new_papers"] + summary["new_trials"]
    total_updated = summary["updated_papers"] + summary["updated_trials"]
    
    # Build message
    message_lines = [
        "📊 **SubSkin 白癜风知识库 - 每日更新报告**",
        "",
        f"📅 报告日期: {date_display}",
        "",
        "📚 **数据统计**",
        f"• 新增论文: {summary['new_papers']} 篇",
        f"• 新增临床试验: {summary['new_trials']} 项",
        f"• 更新论文: {summary['updated_papers']} 篇",
        f"• 更新试验: {summary['updated_trials']} 项",
        f"• 失败任务: {summary['failed_crawls']} 个",
        f"• 总计更新: {summary['total_updates']} 项",
    ]
    
    # Add recent highlights if available
    if summary["details"]:
        message_lines.extend([
            "",
            "✨ **重点更新**",
        ])
        
        # Show top 5 most recent updates
        for i, detail in enumerate(summary["details"][:5], 1):
            title = detail["resource_title"][:50] + "..." if len(detail["resource_title"]) > 50 else detail["resource_title"]
            source_display = {
                "pubmed": "PubMed",
                "semantic_scholar": "Semantic Scholar",
                "clinical_trials": "ClinicalTrials.gov"
            }.get(detail["source"], detail["source"])
            
            message_lines.append(f"{i}. {title} ({source_display})")
    
    message_lines.extend([
        "",
        "---",
        "💡 本报告由自动化系统生成",
        "⏰ 下次更新: 明日 09:00",
    ])
    
    return "\n".join(message_lines)


def format_error_notification(error_type: str, error_details: str, traceback: Optional[str] = None) -> str:
    """Format error notification message.
    
    Args:
        error_type: Type of error
        error_details: Error details
        traceback: Optional traceback for debugging
        
    Returns:
        Formatted error message
    """
    message_lines = [
        "🚨 **SubSkin 系统错误通知**",
        "",
        f"⏰ 发生时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"❌ 错误类型: {error_type}",
        f"📝 错误详情: {error_details}",
    ]
    
    if traceback:
        # Truncate long tracebacks
        if len(traceback) > 200:
            traceback = traceback[:200] + "..."
        message_lines.extend([
            "",
            "🔧 **调试信息**",
            f"```\n{traceback}\n```",
        ])
    
    message_lines.extend([
        "",
        "---",
        "⚠️ 请及时检查系统日志",
    ])
    
    return "\n".join(message_lines)


def format_system_status_notification(
    crawlers_status: Dict[str, bool],
    last_success_time: Optional[datetime],
    uptime_days: float,
    disk_usage_percent: float,
    memory_usage_percent: float
) -> str:
    """Format system status notification.
    
    Args:
        crawlers_status: Dictionary mapping crawler names to status (True=healthy)
        last_success_time: Last successful crawl time
        uptime_days: System uptime in days
        disk_usage_percent: Disk usage percentage
        memory_usage_percent: Memory usage percentage
        
    Returns:
        Formatted system status message
    """
    # Calculate crawler health
    total_crawlers = len(crawlers_status)
    healthy_crawlers = sum(1 for status in crawlers_status.values() if status)
    crawler_health = "✅" if healthy_crawlers == total_crawlers else "⚠️" if healthy_crawlers > 0 else "❌"
    
    # Format last success time
    if last_success_time:
        time_diff = datetime.now() - last_success_time
        if time_diff < timedelta(hours=1):
            last_success = "刚刚"
        elif time_diff < timedelta(days=1):
            hours = time_diff.total_seconds() // 3600
            last_success = f"{int(hours)}小时前"
        else:
            days = time_diff.days
            last_success = f"{days}天前"
    else:
        last_success = "从未"
    
    message_lines = [
        "🖥️ **SubSkin 系统状态报告**",
        "",
        f"⏰ 报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "📊 **系统指标**",
        f"• 运行时间: {uptime_days:.1f} 天",
        f"• 磁盘使用: {disk_usage_percent:.1f}%",
        f"• 内存使用: {memory_usage_percent:.1f}%",
        "",
        "🕷️ **爬虫状态**",
        f"• 总体健康: {crawler_health} ({healthy_crawlers}/{total_crawlers})",
        f"• 最后成功: {last_success}",
    ]
    
    # Individual crawler status
    message_lines.append("• 详细状态:")
    for crawler_name, is_healthy in crawlers_status.items():
        status_icon = "✅" if is_healthy else "❌"
        message_lines.append(f"  {status_icon} {crawler_name}")
    
    # Health assessment
    if healthy_crawlers == total_crawlers:
        assessment = "✅ 所有系统运行正常"
    elif healthy_crawlers == 0:
        assessment = "❌ 所有爬虫故障，需要立即检查"
    else:
        assessment = "⚠️ 部分爬虫故障，建议检查"
    
    message_lines.extend([
        "",
        "📈 **健康评估**",
        assessment,
        "",
        "---",
        "🔄 下次状态检查: 6小时后",
    ])
    
    return "\n".join(message_lines)


class NotificationManager:
    """Manager for handling different types of notifications."""
    
    def __init__(self, notifier: QQBotNotifier, target_user_id: Union[str, int]):
        """Initialize notification manager.
        
        Args:
            notifier: QQBotNotifier instance
            target_user_id: Target QQ user ID for notifications
        """
        self.notifier = notifier
        self.target_user_id = str(target_user_id)
        self.logger = get_logger(f"{__name__}.NotificationManager")
    
    def send_daily_report(self, summary: DailySummary) -> bool:
        """Send daily update report.
        
        Args:
            summary: Daily summary of updates
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            message = format_daily_notification(summary)
            result = self.notifier.send_private_message(self.target_user_id, message)
            self.logger.info(f"Daily report sent for {summary['date']}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send daily report: {e}")
            return False
    
    def send_error_alert(self, error_type: str, error_details: str, traceback: Optional[str] = None) -> bool:
        """Send error alert notification.
        
        Args:
            error_type: Type of error
            error_details: Error details
            traceback: Optional traceback
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            message = format_error_notification(error_type, error_details, traceback)
            result = self.notifier.send_private_message(self.target_user_id, message)
            self.logger.info(f"Error alert sent: {error_type}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send error alert: {e}")
            return False
    
    def send_system_status(
        self,
        crawlers_status: Dict[str, bool],
        last_success_time: Optional[datetime] = None,
        uptime_days: float = 0.0,
        disk_usage_percent: float = 0.0,
        memory_usage_percent: float = 0.0
    ) -> bool:
        """Send system status notification.
        
        Args:
            crawlers_status: Dictionary mapping crawler names to status
            last_success_time: Last successful crawl time
            uptime_days: System uptime in days
            disk_usage_percent: Disk usage percentage
            memory_usage_percent: Memory usage percentage
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            message = format_system_status_notification(
                crawlers_status,
                last_success_time,
                uptime_days,
                disk_usage_percent,
                memory_usage_percent
            )
            result = self.notifier.send_private_message(self.target_user_id, message)
            self.logger.info("System status report sent")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send system status: {e}")
            return False
    
    def send_custom_message(self, message: str) -> bool:
        """Send custom message.
        
        Args:
            message: Custom message content
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            result = self.notifier.send_private_message(self.target_user_id, message)
            self.logger.info("Custom message sent")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send custom message: {e}")
            return False


def create_notifier_from_env() -> QQBotNotifier:
    """Create QQBotNotifier from environment variables.
    
    Environment variables:
        CQHTTP_HOST: go-cqhttp host (default: http://127.0.0.1)
        CQHTTP_PORT: go-cqhttp port (default: 5700)
        CQHTTP_TIMEOUT: Request timeout in seconds (default: 30)
        CQHTTP_MAX_RETRIES: Max retry attempts (default: 3)
        CQHTTP_RETRY_DELAY: Retry delay in seconds (default: 2.0)
    
    Returns:
        Configured QQBotNotifier instance
    """
    host = os.getenv("CQHTTP_HOST", "http://127.0.0.1")
    port = int(os.getenv("CQHTTP_PORT", "5700"))
    timeout = int(os.getenv("CQHTTP_TIMEOUT", "30"))
    max_retries = int(os.getenv("CQHTTP_MAX_RETRIES", "3"))
    retry_delay = float(os.getenv("CQHTTP_RETRY_DELAY", "2.0"))
    
    return QQBotNotifier(
        host=host,
        port=port,
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay
    )


if __name__ == "__main__":
    """Test script for QQ notifier."""
    import sys
    
    # Simple test
    notifier = create_notifier_from_env()
    
    # Test connection
    if notifier.test_connection():
        print("✅ Connected to go-cqhttp")
    else:
        print("❌ Failed to connect to go-cqhttp")
        sys.exit(1)
    
    # Send test message if target user is configured
    test_user = os.getenv("NOTIFY_USER_ID")
    if test_user:
        try:
            # Create test summary
            test_summary: DailySummary = {
                "date": datetime.now().date().isoformat(),
                "total_updates": 15,
                "new_papers": 8,
                "new_trials": 2,
                "updated_papers": 3,
                "updated_trials": 1,
                "failed_crawls": 1,
                "details": [
                    {
                        "id": 1,
                        "update_type": UpdateType.NEW_PAPER,
                        "resource_id": "PMID12345678",
                        "resource_title": "JAK抑制剂在白癜风治疗中的新进展",
                        "change_details": {"source": "pubmed", "year": 2026},
                        "timestamp": datetime.now().isoformat(),
                        "source": "pubmed"
                    },
                    {
                        "id": 2,
                        "update_type": UpdateType.NEW_TRIAL,
                        "resource_id": "NCT01234567",
                        "resource_title": "Phase 3 Trial of New Vitiligo Treatment",
                        "change_details": {"phase": "PHASE3", "status": "RECRUITING"},
                        "timestamp": datetime.now().isoformat(),
                        "source": "clinical_trials"
                    }
                ]
            }
            
            message = format_daily_notification(test_summary)
            result = notifier.send_private_message(test_user, message)
            print(f"✅ Test message sent: {result.get('message_id', 'N/A')}")
            
        except Exception as e:
            print(f"❌ Failed to send test message: {e}")
            sys.exit(1)
    else:
        print("⚠️ NOTIFY_USER_ID not set, skipping message send test")
    
    notifier.close()
    print("✅ Test completed successfully")