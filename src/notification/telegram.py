from telegram import Bot
from telegram.error import TelegramError
import asyncio
import logging
from datetime import datetime

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.logger = logging.getLogger('shirakawago.telegram')

    async def send_message(self, message: str) -> bool:
        """
        Send a simple message via Telegram
        Returns True if successful, False otherwise
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            return True
        except TelegramError as e:
            self.logger.error(f"Failed to send Telegram message: {str(e)}")
            return False

    async def test_connection(self) -> bool:
        """
        Test if the bot can connect and send messages
        """
        test_message = (
            "🏡 *Little Gassho-chan Test*\n\n"
            "Connection test successful!\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return await self.send_message(test_message)