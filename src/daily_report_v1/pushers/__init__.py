"""推送层：邮件（SMTP）与飞书机器人推送（design.md 4.4 契约）。"""

from .base import BasePusher, PushResult
from .email_pusher import EmailPusher
from .feishu_pusher import FeishuBotPusher

__all__ = ["BasePusher", "PushResult", "EmailPusher", "FeishuBotPusher"]
