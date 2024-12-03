import asyncio
import os
from dotenv import load_dotenv
import logging

from src.notification.telegram import TelegramNotifier

async def test_telegram():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('shirakawago.main')

    # Load environment variables
    load_dotenv()
    
    # Get credentials
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        logger.error("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
        return

    # Initialize notifier
    notifier = TelegramNotifier(token, chat_id)
    
    # Test connection
    logger.info("Testing Telegram connection...")
    if await notifier.test_connection():
        logger.info("Telegram test successful!")
    else:
        logger.error("Telegram test failed!")

if __name__ == "__main__":
    asyncio.run(test_telegram())