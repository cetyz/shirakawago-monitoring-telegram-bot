import asyncio
import os
from dotenv import load_dotenv
import logging
from datetime import datetime

from src.notification.telegram import TelegramNotifier
from src.scraper.scraper import ShirakawagoBotScraper, AvailabilityResult

def escape_markdown(text: str) -> str:
    """Escape special characters for Markdown V2 formatting"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text

def format_availability_message(result: AvailabilityResult) -> str:
    """Format the availability result into a readable message for a single date"""
    if result.error:
        return f"❌ Error checking availability: {escape_markdown(result.error)}"
    
    message_parts = [
        f"🏡 *Shirakawago Availability Report*",
        f"Date: {result.date.strftime('%Y-%m-%d')}\n"
    ]
    
    # target_date_str = result.date.strftime("%b %d")  # Format like "Feb 9"
    target_date_str = result.date.strftime("%m").lstrip("0") + '/' +  result.date.strftime("%d").lstrip("0") # Format like "Feb 9"
    print(target_date_str)
    
    for hotel in result.hotels:
        status = "UNKNOWN"
        for date, avail_status in hotel.availability.items():
            if date.startswith(target_date_str):
                status = avail_status
                break
        
        status_emoji = {
            "AVAILABLE": "⭕⭕⭕⭕⭕",
            "ALMOST_FULL": "⚠⚠⚠⚠⚠⚠",
            "BOOKED": "❌",
            "NOT_OPEN": "➖",
            "UNKNOWN": "❓"
        }.get(status, "❓")
        
        hotel_name = escape_markdown(hotel.name)
        date_str = escape_markdown(target_date_str)
        status_str = escape_markdown(status)
        
        message_parts.append(f"*{hotel_name}*:\n{date_str}: {status_emoji} {status_str}")
    
    return "\n\n".join(message_parts)

async def check_and_notify():
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

    # Initialize scraper and notifier
    scraper = ShirakawagoBotScraper()
    notifier = TelegramNotifier(token, chat_id)
    
    # Check availability for specific date
    target_date = datetime(2025, 2, 9)
    logger.info(f"Checking availability for {target_date.date()}")
    
    result = scraper.check_availability(target_date)
    # print(result)
    
    # Format and send message
    message = format_availability_message(result)
    logger.info("Sending availability notification...")
    
    if await notifier.send_message(message):
        logger.info("Notification sent successfully!")
    else:
        logger.error("Failed to send notification")

if __name__ == "__main__":
    asyncio.run(check_and_notify())