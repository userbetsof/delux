"""
Клиент для отправки сообщений в Telegram.
Настройки берутся из переменных окружения BOT_TOKEN и CHAT_ID (.env).
"""
import asyncio
import os
from typing import Optional

from dotenv import load_dotenv
from telegram import Bot

load_dotenv()


class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Args:
            bot_token: Токен бота. Если не передан — читается из BOT_TOKEN.
            chat_id: ID чата. Если не передан — читается из CHAT_ID.
        """
        self._token = (bot_token or os.environ.get("BOT_TOKEN", "")).strip()
        self._chat_id = (chat_id or os.environ.get("CHAT_ID", "")).strip()

    @property
    def is_configured(self) -> bool:
        """Проверка, заданы ли токен и chat_id."""
        return bool(self._token and self._chat_id)

    async def send_async(self, message: str) -> bool:
        """
        Асинхронная отправка сообщения в Telegram.
        Returns:
            True при успехе, False при ошибке или если не настроен клиент.
        """
        if not self.is_configured:
            return False
        try:
            bot = Bot(token=self._token)
            await bot.send_message(chat_id=self._chat_id, text=message)
            return True
        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")
            return False

    def send(self, message: str) -> bool:
        """
        Синхронная отправка сообщения (запускает asyncio при необходимости).
        Returns:
            True при успехе, False при ошибке или если не настроен клиент.
        """
        if not self.is_configured:
            return False
        try:
            return asyncio.run(self.send_async(message))
        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")
            return False
