"""Tests for notification modules."""

import pytest
from unittest.mock import patch, MagicMock
from src.notifications.wechat_notifier import WeChatNotifier
from src.notifications.qq_notifier import QQBotNotifier


class TestWeChatNotifier:
    """Test WeChatNotifier."""

    def test_wechat_notifier_instantiation(self):
        """Test that WeChatNotifier can be instantiated."""
        notifier = WeChatNotifier(
            channel="test-channel",
            target="test-target",
            openclaw_path="openclaw",
        )
        assert notifier.channel == "test-channel"
        assert notifier.target == "test-target"
        assert notifier.openclaw_path == "openclaw"

    @patch("subprocess.run")
    def test_wechat_notifier_send_message(self, mock_run):
        """Test sending a message."""
        mock_run.return_value = MagicMock(returncode=0)
        notifier = WeChatNotifier(
            channel="test-channel",
            target="test-target",
            openclaw_path="openclaw",
        )
        result = notifier.send_message("Test message")
        assert result is True
        assert mock_run.called

    @patch("subprocess.run")
    def test_wechat_notifier_send_message_failure(self, mock_run):
        """Test handling of send failure."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Some error")
        notifier = WeChatNotifier(
            channel="test-channel",
            target="test-target",
            openclaw_path="openclaw",
        )
        result = notifier.send_message("Test message")
        assert result is False


class TestQQBotNotifier:
    """Test QQBotNotifier."""

    def test_qq_notifier_instantiation(self):
        """Test that QQBotNotifier can be instantiated."""
        notifier = QQBotNotifier(
            host="http://localhost",
            port=5700,
        )
        assert notifier.base_url == "http://localhost:5700"
        assert notifier.timeout == 30
        assert notifier.max_retries == 3
